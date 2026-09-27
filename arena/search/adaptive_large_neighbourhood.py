"""Objective-feedback operator adaptation with a bounded Metropolis walk."""
from dataclasses import dataclass
import math
import random

from arena.scheduling.domain import SchedulePlan, ScheduleProblem
from .destroy_repair import (
    DestroyOperator, RepairOperator, _validate_bounds, _horizon_upper,
    _select_items, _destroy, _repair, _changed_placements,
)
from .objective import PlanObjective, PlanObjectiveConfig, score_state
from .state import SearchState, SessionPlacement


@dataclass(frozen=True, slots=True)
class AdaptiveLargeNeighbourhoodConfig:
    objective: PlanObjectiveConfig
    horizon_days: int
    destroy_count: int
    max_iterations: int
    reaction_factor: float
    initial_temperature: float
    cooling_rate: float
    minimum_temperature: float
    reward_best: float
    reward_accepted: float
    reward_rejected: float
    max_evaluations: int | None = None
    seed: int = 0

    def __post_init__(self) -> None:
        _validate_bounds(self)
        for name in ('reaction_factor', 'initial_temperature', 'cooling_rate',
                     'minimum_temperature', 'reward_best', 'reward_accepted', 'reward_rejected'):
            value = getattr(self, name)
            if (isinstance(value, bool) or not isinstance(value, (int, float))
                    or not math.isfinite(value) or value <= 0):
                raise ValueError(f'{name} must be finite and positive')
        if self.reaction_factor > 1 or self.cooling_rate > 1:
            raise ValueError('reaction_factor and cooling_rate must be <= 1')
        if self.minimum_temperature > self.initial_temperature:
            raise ValueError('minimum_temperature must not exceed initial_temperature')
        if not self.reward_best > self.reward_accepted > self.reward_rejected:
            raise ValueError('Require reward_best > reward_accepted > reward_rejected > 0')


def _roulette(weights: dict, rng: random.Random):
    # Scaling avoids overflow when several finite weights approach float max.
    scale = max(weights.values())
    scaled = tuple((operator, weight / scale) for operator, weight in weights.items())
    target = rng.random() * sum(weight for _, weight in scaled)
    cumulative = 0.0
    for operator, weight in scaled:
        cumulative += weight
        if target < cumulative:
            return operator
    return scaled[-1][0]  # Floating-point rounding at the final boundary.


def _update_weight(old: float, reaction: float, reward: float) -> float:
    # The exact convex combination lies between its operands. Preserve that
    # invariant even if both products underflow for subnormal positive rewards.
    return max(min(old, reward), (1 - reaction) * old + reaction * reward)


@dataclass(frozen=True, slots=True)
class AdaptiveLargeNeighbourhoodResult:
    initial_state: SearchState
    final_state: SearchState
    initial_objective: PlanObjective
    final_objective: PlanObjective
    last_state: SearchState
    last_objective: PlanObjective
    iterations: int
    evaluations: int
    accepted_repairs: int
    rejected_repairs: int
    failed_repairs: int
    termination_reason: str
    final_temperature: float
    best_objective_history: tuple[float, ...]
    walk_objective_history: tuple[float, ...]
    accepted_changes_history: tuple[tuple[SessionPlacement, ...], ...]
    operator_history: tuple[tuple[DestroyOperator, RepairOperator, str], ...]
    destroy_weights: tuple[tuple[DestroyOperator, float], ...]
    repair_weights: tuple[tuple[RepairOperator, float], ...]

    @property
    def improved(self) -> bool:
        return self.final_objective.total < self.initial_objective.total

    @property
    def total_improvement(self) -> float:
        return self.initial_objective.total - self.final_objective.total


@dataclass(frozen=True, slots=True)
class AdaptiveLargeNeighbourhoodSearch:
    config: AdaptiveLargeNeighbourhoodConfig

    def improve_state(self, initial: SearchState) -> AdaptiveLargeNeighbourhoodResult:
        cfg = self.config
        _horizon_upper(initial, cfg.horizon_days)
        rng = random.Random(cfg.seed)
        current = best = initial
        initial_objective = current_objective = best_objective = score_state(initial, cfg.objective)
        iterations = evaluations = rejected = failed = 0
        best_history, walk_history = [initial_objective.total], [initial_objective.total]
        changes, operators = [], []
        destroy_weights = dict.fromkeys(DestroyOperator, 1.0)
        repair_weights = dict.fromkeys(RepairOperator, 1.0)
        temperature = cfg.initial_temperature
        while True:
            if iterations >= cfg.max_iterations:
                reason = 'iteration_budget'
                break
            if cfg.max_evaluations is not None and evaluations >= cfg.max_evaluations:
                reason = 'evaluation_budget'
                break
            if not current.placements:
                reason = 'no_schedulable_items'
                break
            iterations += 1
            destroy = _roulette(destroy_weights, rng)
            repair = _roulette(repair_weights, rng)
            selected = _select_items(current, cfg.destroy_count, destroy, rng)
            candidate = _repair(_destroy(current, selected), cfg.horizon_days, repair, rng)
            reward = cfg.reward_rejected
            if candidate is None:
                failed += 1
                outcome = 'failed'
            else:
                cost = score_state(candidate, cfg.objective)
                evaluations += 1
                delta = cost.total - current_objective.total
                if delta <= 0 or rng.random() < math.exp(-delta / temperature):
                    changes.append(_changed_placements(current, candidate))
                    current, current_objective = candidate, cost
                    walk_history.append(cost.total)
                    outcome, reward = 'accepted', cfg.reward_accepted
                    if cost.total < best_objective.total:
                        best, best_objective = current, cost
                        best_history.append(cost.total)
                        outcome, reward = 'best', cfg.reward_best
                else:
                    rejected += 1
                    outcome = 'rejected'
            operators.append((destroy, repair, outcome))
            destroy_weights[destroy] = _update_weight(destroy_weights[destroy], cfg.reaction_factor, reward)
            repair_weights[repair] = _update_weight(repair_weights[repair], cfg.reaction_factor, reward)
            temperature = max(cfg.minimum_temperature, temperature * cfg.cooling_rate)
        return AdaptiveLargeNeighbourhoodResult(initial, best, initial_objective, best_objective,
            current, current_objective, iterations, evaluations, len(changes), rejected, failed,
            reason, temperature, tuple(best_history), tuple(walk_history), tuple(changes),
            tuple(operators), tuple(destroy_weights.items()), tuple(repair_weights.items()))

    def improve_plan(self, problem: ScheduleProblem, plan: SchedulePlan) -> AdaptiveLargeNeighbourhoodResult:
        return self.improve_state(SearchState.from_plan(problem, plan))
