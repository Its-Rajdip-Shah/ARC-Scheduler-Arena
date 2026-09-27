"""Bounded strict-improvement large neighbourhood search."""
from dataclasses import dataclass
import random

from arena.scheduling.domain import SchedulePlan, ScheduleProblem
from .destroy_repair import (
    DestroyOperator, RepairOperator, _validate_bounds, _horizon_upper,
    _select_items, _destroy, _repair, _changed_placements,
)
from .objective import PlanObjective, PlanObjectiveConfig, score_state
from .state import SearchState, SessionPlacement


@dataclass(frozen=True, slots=True)
class LargeNeighbourhoodConfig:
    objective: PlanObjectiveConfig
    horizon_days: int
    destroy_count: int
    destroy_operator: DestroyOperator
    repair_operator: RepairOperator
    max_iterations: int
    max_evaluations: int | None = None
    seed: int = 0

    def __post_init__(self) -> None:
        _validate_bounds(self)
        if not isinstance(self.destroy_operator, DestroyOperator):
            raise ValueError('destroy_operator must be a DestroyOperator')
        if not isinstance(self.repair_operator, RepairOperator):
            raise ValueError('repair_operator must be a RepairOperator')


@dataclass(frozen=True, slots=True)
class LargeNeighbourhoodResult:
    initial_state: SearchState
    final_state: SearchState
    initial_objective: PlanObjective
    final_objective: PlanObjective
    iterations: int
    evaluations: int
    accepted_repairs: int
    termination_reason: str
    objective_history: tuple[float, ...]
    accepted_changes_history: tuple[tuple[SessionPlacement, ...], ...]

    @property
    def improved(self) -> bool:
        return self.final_objective.total < self.initial_objective.total

    @property
    def total_improvement(self) -> float:
        return self.initial_objective.total - self.final_objective.total


@dataclass(frozen=True, slots=True)
class LargeNeighbourhoodSearch:
    config: LargeNeighbourhoodConfig

    def improve_state(self, initial: SearchState) -> LargeNeighbourhoodResult:
        cfg = self.config
        _horizon_upper(initial, cfg.horizon_days)
        rng = random.Random(cfg.seed)
        current = initial
        initial_objective = current_objective = score_state(initial, cfg.objective)
        iterations = evaluations = 0
        history, changes = [initial_objective.total], []
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
            selected = _select_items(current, cfg.destroy_count, cfg.destroy_operator, rng)
            candidate = _repair(_destroy(current, selected), cfg.horizon_days, cfg.repair_operator, rng)
            if candidate is None:
                continue
            cost = score_state(candidate, cfg.objective)
            evaluations += 1
            if cost.total < current_objective.total:
                changes.append(_changed_placements(current, candidate))
                current, current_objective = candidate, cost
                history.append(cost.total)
        return LargeNeighbourhoodResult(initial, current, initial_objective, current_objective,
            iterations, evaluations, len(changes), reason, tuple(history), tuple(changes))

    def improve_plan(self, problem: ScheduleProblem, plan: SchedulePlan) -> LargeNeighbourhoodResult:
        return self.improve_state(SearchState.from_plan(problem, plan))
