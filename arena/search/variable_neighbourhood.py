"""Ordered variable-neighbourhood descent and seeded basin search."""
from dataclasses import dataclass
from enum import Enum
import random

from arena.scheduling.domain import SchedulePlan, ScheduleProblem
from .moves import Move, apply_move
from .neighbourhoods import (
    NeighbourhoodConfig, all_moves, relocate_session_moves,
    swap_session_moves, shift_item_moves,
)
from .objective import PlanObjective, PlanObjectiveConfig, score_state
from .state import SearchState


_FAMILIES = (relocate_session_moves, swap_session_moves, shift_item_moves)


class VariableNeighbourhoodMode(str, Enum):
    VND = 'vnd'
    VNS = 'vns'


@dataclass(frozen=True, slots=True)
class VariableNeighbourhoodConfig:
    objective: PlanObjectiveConfig
    neighbourhood: NeighbourhoodConfig
    mode: VariableNeighbourhoodMode
    max_iterations: int | None = None
    max_evaluations: int | None = None
    seed: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.mode, VariableNeighbourhoodMode):
            raise ValueError('mode must be a VariableNeighbourhoodMode instance')
        for name in ('max_iterations', 'max_evaluations'):
            value = getattr(self, name)
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError(f'{name} must be None or an exact nonnegative int')
        if type(self.seed) is not int:
            raise ValueError('seed must be an exact int')


@dataclass(frozen=True, slots=True)
class VariableNeighbourhoodResult:
    initial_state: SearchState
    final_state: SearchState
    initial_objective: PlanObjective
    final_objective: PlanObjective
    iterations: int
    evaluations: int
    accepted_moves: int
    accepted_excursions: int
    termination_reason: str
    objective_history: tuple[float, ...]
    accepted_moves_history: tuple[Move, ...]

    @property
    def improved(self) -> bool:
        return self.final_objective.total < self.initial_objective.total

    @property
    def total_improvement(self) -> float:
        return self.initial_objective.total - self.final_objective.total


@dataclass(frozen=True, slots=True)
class VariableNeighbourhoodSearch:
    config: VariableNeighbourhoodConfig

    def improve_state(self, initial: SearchState) -> VariableNeighbourhoodResult:
        if self.config.mode is VariableNeighbourhoodMode.VNS:
            return self._improve_vns(initial)
        current = initial
        initial_objective = score_state(initial, self.config.objective)
        current_objective = initial_objective
        iterations = evaluations = 0
        objective_history = [initial_objective.total]
        accepted_history: list[Move] = []
        k = 0

        def finish(reason: str) -> VariableNeighbourhoodResult:
            return VariableNeighbourhoodResult(initial, current, initial_objective,
                current_objective, iterations, evaluations, len(accepted_history),
                len(accepted_history), reason, tuple(objective_history), tuple(accepted_history))

        while k < len(_FAMILIES):
            if self.config.max_iterations is not None and iterations >= self.config.max_iterations:
                return finish('iteration_budget')
            if self.config.max_evaluations is not None and evaluations >= self.config.max_evaluations:
                return finish('evaluation_budget')
            iterations += 1
            moves = _FAMILIES[k](current, self.config.neighbourhood)
            selected_move = None
            selected_state, selected_objective = current, current_objective
            for move in moves:
                if self.config.max_evaluations is not None and evaluations >= self.config.max_evaluations:
                    return finish('evaluation_budget')
                neighbour = apply_move(current, move)
                if neighbour is None:
                    raise RuntimeError('C4.1 neighbourhood emitted an illegal or no-op move')
                cost = score_state(neighbour, self.config.objective)
                evaluations += 1
                if cost.total < selected_objective.total:
                    selected_move, selected_state, selected_objective = move, neighbour, cost
            if selected_move is None:
                k += 1
            else:
                current, current_objective = selected_state, selected_objective
                accepted_history.append(selected_move)
                objective_history.append(current_objective.total)
                k = 0
        return finish('local_optimum')

    def _improve_vns(self, initial: SearchState) -> VariableNeighbourhoodResult:
        """Commit only whole excursions ending at a proven local optimum."""
        rng = random.Random(self.config.seed)
        incumbent = initial
        initial_objective = score_state(initial, self.config.objective)
        incumbent_objective = initial_objective
        iterations = evaluations = 0
        objective_history = [initial_objective.total]
        accepted_history: list[Move] = []
        k = 0

        def finish(reason: str) -> VariableNeighbourhoodResult:
            return VariableNeighbourhoodResult(initial, incumbent, initial_objective,
                incumbent_objective, iterations, evaluations, len(accepted_history),
                len(objective_history) - 1, reason,
                tuple(objective_history), tuple(accepted_history))

        def budget_reason() -> str | None:
            if self.config.max_iterations is not None and iterations >= self.config.max_iterations:
                return 'iteration_budget'
            if self.config.max_evaluations is not None and evaluations >= self.config.max_evaluations:
                return 'evaluation_budget'
            return None

        while k < len(_FAMILIES):
            reason = budget_reason()
            if reason is not None:
                return finish(reason)
            iterations += 1
            moves = _FAMILIES[k](incumbent, self.config.neighbourhood)
            if not moves:
                k += 1
                continue

            shake_move = moves[rng.randrange(len(moves))]
            trial_state = apply_move(incumbent, shake_move)
            if trial_state is None:
                raise RuntimeError('C4.1 neighbourhood emitted an illegal or no-op move')
            if self.config.max_evaluations is not None and evaluations >= self.config.max_evaluations:
                return finish('evaluation_budget')
            trial_objective = score_state(trial_state, self.config.objective)
            evaluations += 1
            trial_moves = [shake_move]

            while True:
                reason = budget_reason()
                if reason is not None:
                    return finish(reason)
                iterations += 1
                moves = all_moves(trial_state, self.config.neighbourhood)
                selected_move = None
                selected_state, selected_objective = trial_state, trial_objective
                for move in moves:
                    if self.config.max_evaluations is not None and evaluations >= self.config.max_evaluations:
                        # Nothing in this excursion has changed the incumbent.
                        return finish('evaluation_budget')
                    neighbour = apply_move(trial_state, move)
                    if neighbour is None:
                        raise RuntimeError('C4.1 neighbourhood emitted an illegal or no-op move')
                    cost = score_state(neighbour, self.config.objective)
                    evaluations += 1
                    if cost.total < selected_objective.total:
                        selected_move, selected_state, selected_objective = move, neighbour, cost
                if selected_move is None:
                    break
                trial_state, trial_objective = selected_state, selected_objective
                trial_moves.append(selected_move)

            if trial_objective.total < incumbent_objective.total:
                incumbent, incumbent_objective = trial_state, trial_objective
                accepted_history.extend(trial_moves)
                objective_history.append(incumbent_objective.total)
                k = 0
            else:
                k += 1
        return finish('local_optimum')

    def improve_plan(self, problem: ScheduleProblem, plan: SchedulePlan) -> VariableNeighbourhoodResult:
        return self.improve_state(SearchState.from_plan(problem, plan))
