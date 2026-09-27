"""Seeded Metropolis search with geometric cooling."""
import math
import random
from dataclasses import dataclass

from arena.scheduling.domain import SchedulePlan, ScheduleProblem
from .moves import Move, apply_move
from .neighbourhoods import NeighbourhoodConfig, all_moves
from .objective import PlanObjective, PlanObjectiveConfig, score_state
from .state import SearchState, SessionPlacement


@dataclass(frozen=True, slots=True)
class SimulatedAnnealingConfig:
    objective: PlanObjectiveConfig
    neighbourhood: NeighbourhoodConfig
    initial_temperature: float
    cooling_rate: float
    minimum_temperature: float
    seed: int = 0
    max_iterations: int | None = None
    max_evaluations: int | None = None

    def __post_init__(self) -> None:
        for name in ('initial_temperature', 'cooling_rate', 'minimum_temperature'):
            value = getattr(self, name)
            if (isinstance(value, bool) or not isinstance(value, (int, float))
                    or not math.isfinite(value) or value <= 0):
                raise ValueError(f'{name} must be finite and positive')
        if self.cooling_rate >= 1:
            raise ValueError('cooling_rate must be less than one')
        if self.minimum_temperature > self.initial_temperature:
            raise ValueError('minimum_temperature must not exceed initial_temperature')
        if type(self.seed) is not int:
            raise ValueError('seed must be an exact int')
        for name in ('max_iterations', 'max_evaluations'):
            value = getattr(self, name)
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError(f'{name} must be None or an exact nonnegative int')


@dataclass(frozen=True, slots=True)
class SimulatedAnnealingResult:
    initial_state: SearchState
    final_state: SearchState
    initial_objective: PlanObjective
    final_objective: PlanObjective
    last_state: SearchState
    last_objective: PlanObjective
    iterations: int
    evaluations: int
    accepted_moves: int
    rejected_moves: int
    termination_reason: str
    final_temperature: float
    best_objective_history: tuple[float, ...]
    walk_objective_history: tuple[float, ...]
    accepted_moves_history: tuple[Move, ...]

    @property
    def improved(self) -> bool:
        return self.final_objective.total < self.initial_objective.total

    @property
    def total_improvement(self) -> float:
        return self.initial_objective.total - self.final_objective.total


@dataclass(frozen=True, slots=True)
class SimulatedAnnealing:
    config: SimulatedAnnealingConfig

    def improve_state(self, initial: SearchState) -> SimulatedAnnealingResult:
        current = best = initial
        initial_objective = score_state(initial, self.config.objective)
        current_objective = best_objective = initial_objective
        iterations = evaluations = 0
        best_history = [initial_objective.total]
        walk_history = [initial_objective.total]
        accepted_history: list[Move] = []
        rng = random.Random(self.config.seed)
        temperature = self.config.initial_temperature
        rejected = 0

        def finish(reason: str) -> SimulatedAnnealingResult:
            return SimulatedAnnealingResult(initial, best, initial_objective,
                best_objective, current, current_objective, iterations, evaluations,
                len(accepted_history), rejected, reason, temperature,
                tuple(best_history), tuple(walk_history), tuple(accepted_history))

        while True:
            if self.config.max_iterations is not None and iterations >= self.config.max_iterations:
                return finish('iteration_budget')
            if self.config.max_evaluations is not None and evaluations >= self.config.max_evaluations:
                return finish('evaluation_budget')
            if temperature < self.config.minimum_temperature:
                return finish('temperature_floor')
            moves = all_moves(current, self.config.neighbourhood)
            if not moves:
                return finish('no_neighbour')
            move = moves[rng.randrange(len(moves))]
            neighbour = apply_move(current, move)
            if neighbour is None:
                raise RuntimeError('C4.1 all_moves emitted an illegal or no-op move')
            cost = score_state(neighbour, self.config.objective)
            iterations += 1
            evaluations += 1
            delta = cost.total - current_objective.total
            if delta <= 0 or rng.random() < math.exp(-delta / temperature):
                current, current_objective = neighbour, cost
                accepted_history.append(move)
                walk_history.append(cost.total)
                if cost.total < best_objective.total:
                    best, best_objective = current, cost
                    best_history.append(cost.total)
            else:
                rejected += 1
            temperature *= self.config.cooling_rate

    def improve_plan(self, problem: ScheduleProblem, plan: SchedulePlan) -> SimulatedAnnealingResult:
        return self.improve_state(SearchState.from_plan(problem, plan))
