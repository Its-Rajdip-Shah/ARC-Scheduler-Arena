"""Exhaustive tiny-instance search over hard-legal session dates."""

from dataclasses import dataclass
from datetime import date, timedelta
from time import perf_counter

from arena.scheduling.domain import SchedulePlan, ScheduleProblem
from arena.scheduling.mechanics import session_pieces
from arena.scheduling.validation import validate_plan
from arena.search.objective import PlanObjective, PlanObjectiveConfig, score_state
from arena.search.state import SearchState, SessionPlacement


@dataclass(frozen=True, slots=True)
class ExactOracleConfig:
    objective: PlanObjectiveConfig
    horizon_days: int
    max_sessions: int
    max_nodes: int

    def __post_init__(self) -> None:
        if not isinstance(self.objective, PlanObjectiveConfig):
            raise ValueError('objective must be PlanObjectiveConfig')
        for name in ('horizon_days', 'max_sessions', 'max_nodes'):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise ValueError(f'{name} must be a nonnegative integer')


@dataclass(frozen=True, slots=True)
class ExactOracleResult:
    problem: ScheduleProblem
    config: ExactOracleConfig
    status: str
    state: SearchState | None
    objective: PlanObjective | None
    nodes_visited: int
    leaves_evaluated: int
    elapsed_seconds: float
    proven_lower_bound: float | None

    @property
    def plan(self) -> SchedulePlan | None:
        return None if self.state is None else self.state.to_plan()


@dataclass(frozen=True, slots=True)
class OptimalityGap:
    heuristic_objective: PlanObjective
    absolute: float
    relative: float | None


@dataclass(frozen=True, slots=True)
class ExactOracle:
    config: ExactOracleConfig

    def solve(self, problem: ScheduleProblem) -> ExactOracleResult:
        started = perf_counter()
        try:
            upper = problem.today + timedelta(days=self.config.horizon_days)
        except OverflowError as exc:
            raise ValueError('Horizon exceeds calendar') from exc

        item_by_id = problem.item_by_id
        pieces_by_id = {i.item_id: session_pieces(i) for i in problem.items}
        if sum(map(len, pieces_by_id.values())) > self.config.max_sessions:
            raise ValueError('Instance exceeds max_sessions')
        decisions = tuple((item_id, index)
                          for item_id in problem.topological_order()
                          for index in range(len(pieces_by_id[item_id])))
        chosen: dict[tuple[int, int], date] = {}
        completed: dict[int, date] = {}
        nodes_visited = leaves_evaluated = 0
        truncated = False
        best_state = best_objective = best_key = None

        def dfs(k: int) -> None:
            nonlocal nodes_visited, leaves_evaluated, truncated
            nonlocal best_state, best_objective, best_key
            if nodes_visited == self.config.max_nodes:
                truncated = True
                return
            nodes_visited += 1

            if k == len(decisions):
                state = SearchState(problem, tuple(
                    SessionPlacement(item_id, index, day)
                    for (item_id, index), day in chosen.items()
                ))
                leaves_evaluated += 1
                cost = score_state(state, self.config.objective)
                key = tuple(p.scheduled_date for p in state.placements)
                if (best_objective is None or cost.total < best_objective.total
                        or (cost.total == best_objective.total and key < best_key)):
                    best_state, best_objective, best_key = state, cost, key
                return

            item_id, index = decisions[k]
            item = item_by_id[item_id]
            lower = max(problem.today, item.release_date or problem.today)
            if index == 0:
                for prerequisite in problem.direct_prerequisites(item_id):
                    if not pieces_by_id[prerequisite]:
                        continue
                    try:
                        following = completed[prerequisite] + timedelta(days=1)
                    except OverflowError:
                        return
                    lower = max(lower, following)
            else:
                lower = max(lower, chosen[item_id, index - 1])

            if index == 0 and item.anchor_date is not None:
                days = (item.anchor_date,) if lower <= item.anchor_date <= upper else ()
            else:
                days = (lower + timedelta(days=offset)
                        for offset in range((upper - lower).days + 1))

            final_session = index == len(pieces_by_id[item_id]) - 1
            for day in days:
                chosen[item_id, index] = day
                if final_session:
                    completed[item_id] = day
                dfs(k + 1)
                del chosen[item_id, index]
                if final_session:
                    del completed[item_id]
                if truncated:
                    break

        dfs(0)
        if best_state is not None:
            plan = best_state.to_plan()
            validation = validate_plan(problem, plan)
            assert not validation.violations and not validation.infeasibilities
            assert SearchState.from_plan(problem, plan) == best_state
        if truncated:
            status, bound = 'node_limit', None
        elif best_state is None:
            status, bound = 'infeasible', None
        else:
            status, bound = 'optimal', best_objective.total
        return ExactOracleResult(
            problem, self.config, status, best_state, best_objective,
            nodes_visited, leaves_evaluated, perf_counter() - started, bound,
        )


def gap_to_optimum(
    result: ExactOracleResult, heuristic_plan: SchedulePlan,
) -> OptimalityGap:
    """Certified gap within the result's horizon and objective configuration."""
    if result.status != 'optimal' or result.state is None or result.objective is None:
        raise ValueError('Gap requires a proven optimal result with a state and objective')
    heuristic_state = SearchState.from_plan(result.problem, heuristic_plan)
    upper = result.problem.today + timedelta(days=result.config.horizon_days)
    if any(p.scheduled_date > upper for p in heuristic_state.placements):
        raise ValueError('Heuristic placement exceeds oracle horizon')
    cost = score_state(heuristic_state, result.config.objective)
    optimum = result.objective.total
    absolute = cost.total - optimum
    if absolute < 0:
        raise ValueError('Heuristic objective is below the claimed optimum')
    relative = absolute / optimum if optimum > 0 else (0.0 if absolute == 0 else None)
    return OptimalityGap(cost, absolute, relative)
