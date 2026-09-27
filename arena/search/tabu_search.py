"""State-based tabu search over complete legal schedules."""
from dataclasses import dataclass

from arena.scheduling.domain import SchedulePlan, ScheduleProblem
from .moves import Move, apply_move
from .neighbourhoods import NeighbourhoodConfig, all_moves
from .objective import PlanObjective, PlanObjectiveConfig, score_state
from .state import SearchState, SessionPlacement


@dataclass(frozen=True, slots=True)
class TabuConfig:
    objective: PlanObjectiveConfig
    neighbourhood: NeighbourhoodConfig
    tabu_tenure: int
    max_iterations: int | None = None
    max_evaluations: int | None = None

    def __post_init__(self) -> None:
        if type(self.tabu_tenure) is not int or self.tabu_tenure <= 0:
            raise ValueError('tabu_tenure must be an exact positive int')
        for name in ('max_iterations', 'max_evaluations'):
            value = getattr(self, name)
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError(f'{name} must be None or an exact nonnegative int')


@dataclass(frozen=True, slots=True)
class TabuResult:
    initial_state: SearchState
    final_state: SearchState
    initial_objective: PlanObjective
    final_objective: PlanObjective
    last_state: SearchState
    last_objective: PlanObjective
    iterations: int
    evaluations: int
    accepted_moves: int
    termination_reason: str
    best_objective_history: tuple[float, ...]
    walk_objective_history: tuple[float, ...]
    accepted_moves_history: tuple[Move, ...]

    @property
    def improved(self) -> bool:
        return self.final_objective.total < self.initial_objective.total

    @property
    def total_improvement(self) -> float:
        return self.initial_objective.total - self.final_objective.total


def _admissible(candidate: SearchState, cost: PlanObjective, best: PlanObjective,
                tabu_until: dict[tuple[SessionPlacement, ...], int], iteration: int) -> bool:
    return tabu_until.get(candidate.placements, 0) < iteration or cost.total < best.total


@dataclass(frozen=True, slots=True)
class TabuSearch:
    config: TabuConfig

    def improve_state(self, initial: SearchState) -> TabuResult:
        current = best = initial
        initial_objective = score_state(initial, self.config.objective)
        current_objective = best_objective = initial_objective
        iterations = evaluations = 0
        best_history = [initial_objective.total]
        walk_history = [initial_objective.total]
        accepted_history: list[Move] = []
        tabu_until: dict[tuple[SessionPlacement, ...], int] = {
            initial.placements: self.config.tabu_tenure,
        }

        def finish(reason: str) -> TabuResult:
            return TabuResult(initial, best, initial_objective, best_objective,
                current, current_objective, iterations, evaluations,
                len(accepted_history), reason, tuple(best_history),
                tuple(walk_history), tuple(accepted_history))

        while True:
            if self.config.max_iterations is not None and iterations >= self.config.max_iterations:
                return finish('iteration_budget')
            if self.config.max_evaluations is not None and evaluations >= self.config.max_evaluations:
                return finish('evaluation_budget')
            iterations += 1
            moves = all_moves(current, self.config.neighbourhood)
            selected = None
            for move in moves:
                if self.config.max_evaluations is not None and evaluations >= self.config.max_evaluations:
                    return finish('evaluation_budget')
                neighbour = apply_move(current, move)
                if neighbour is None:
                    raise RuntimeError('C4.1 all_moves emitted an illegal or no-op move')
                cost = score_state(neighbour, self.config.objective)
                evaluations += 1
                if not _admissible(neighbour, cost, best_objective, tabu_until, iterations):
                    continue
                if selected is None or cost.total < selected[2].total:
                    selected = move, neighbour, cost
            if selected is None:
                return finish('no_admissible_move')
            move, current, current_objective = selected
            tabu_until[current.placements] = iterations + self.config.tabu_tenure
            accepted_history.append(move)
            walk_history.append(current_objective.total)
            if current_objective.total < best_objective.total:
                best, best_objective = current, current_objective
                best_history.append(best_objective.total)

    def improve_plan(self, problem: ScheduleProblem, plan: SchedulePlan) -> TabuResult:
        return self.improve_state(SearchState.from_plan(problem, plan))
