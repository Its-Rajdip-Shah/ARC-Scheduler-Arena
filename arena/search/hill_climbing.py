"""Deterministic strict hill climbing over the frozen C4.1 foundation."""
from dataclasses import dataclass
from enum import Enum

from arena.scheduling.domain import SchedulePlan, ScheduleProblem
from .moves import Move, apply_move
from .neighbourhoods import NeighbourhoodConfig, all_moves
from .objective import PlanObjective, PlanObjectiveConfig, score_state
from .state import SearchState


class ImprovementStrategy(str, Enum):
    FIRST = 'first'
    BEST = 'best'


@dataclass(frozen=True, slots=True)
class HillClimbConfig:
    objective: PlanObjectiveConfig
    neighbourhood: NeighbourhoodConfig
    strategy: ImprovementStrategy
    max_iterations: int | None = None
    max_evaluations: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.strategy, ImprovementStrategy):
            raise ValueError('strategy must be an ImprovementStrategy instance')
        for name in ('max_iterations', 'max_evaluations'):
            value = getattr(self, name)
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError(f'{name} must be None or an exact nonnegative int')


@dataclass(frozen=True, slots=True)
class HillClimbResult:
    initial_state: SearchState
    final_state: SearchState
    initial_objective: PlanObjective
    final_objective: PlanObjective
    iterations: int
    evaluations: int
    accepted_moves: int
    termination_reason: str
    objective_history: tuple[float, ...]
    accepted_moves_history: tuple[Move, ...]

    @property
    def improved(self) -> bool:
        return self.final_objective.total < self.initial_objective.total

    @property
    def total_improvement(self) -> float:
        """Initial minus final total; positive means improvement."""
        return self.initial_objective.total - self.final_objective.total


@dataclass(frozen=True, slots=True)
class HillClimber:
    config: HillClimbConfig

    def improve_state(self, initial: SearchState) -> HillClimbResult:
        """Improve a complete state; budgets count scans and neighbour scores.

        At scan boundaries iteration limits precede evaluation limits. A full
        unsuccessful scan establishes local optimality even at an exact budget
        boundary; a truncated BEST scan never commits its tentative candidate.
        """
        current = initial
        initial_objective = score_state(initial, self.config.objective)
        current_objective = initial_objective
        iterations = evaluations = 0
        objective_history = [initial_objective.total]
        accepted_history: list[Move] = []

        def finish(reason: str) -> HillClimbResult:
            return HillClimbResult(
                initial, current, initial_objective, current_objective,
                iterations, evaluations, len(accepted_history), reason,
                tuple(objective_history), tuple(accepted_history),
            )

        while True:
            if self.config.max_iterations is not None and iterations >= self.config.max_iterations:
                return finish('iteration_budget')
            if self.config.max_evaluations is not None and evaluations >= self.config.max_evaluations:
                return finish('evaluation_budget')

            iterations += 1
            moves = all_moves(current, self.config.neighbourhood)
            selected_move = None
            selected_state = current
            selected_objective = current_objective
            for move in moves:
                if self.config.max_evaluations is not None and evaluations >= self.config.max_evaluations:
                    # Only BEST can have a tentative improvement here. Discard it.
                    return finish('evaluation_budget')
                neighbour = apply_move(current, move)
                if neighbour is None:
                    raise RuntimeError('C4.1 all_moves emitted an illegal or no-op move')
                neighbour_objective = score_state(neighbour, self.config.objective)
                evaluations += 1
                if neighbour_objective.total < selected_objective.total:
                    selected_move = move
                    selected_state = neighbour
                    selected_objective = neighbour_objective
                    if self.config.strategy is ImprovementStrategy.FIRST:
                        break

            if selected_move is None:
                return finish('local_optimum')
            current = selected_state
            current_objective = selected_objective
            accepted_history.append(selected_move)
            objective_history.append(current_objective.total)

    def improve_plan(self, problem: ScheduleProblem, plan: SchedulePlan) -> HillClimbResult:
        """Strict C4.1 conversion followed by improvement; owns no constructor."""
        return self.improve_state(SearchState.from_plan(problem, plan))
