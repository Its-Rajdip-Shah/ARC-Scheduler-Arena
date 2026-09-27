"""Private partial schedules; only complete, distinct repairs cross the boundary."""
from collections import deque
from dataclasses import dataclass
from datetime import date
from enum import Enum
import random

from .objective import PlanObjectiveConfig
from .state import SearchState, SessionPlacement


class DestroyOperator(str, Enum):
    RANDOM = 'random'
    TEMPORAL = 'temporal'
    DEPENDENCY = 'dependency'


class RepairOperator(str, Enum):
    EARLIEST = 'earliest'
    RANDOM = 'random'


def _validate_bounds(config) -> None:
    if not isinstance(config.objective, PlanObjectiveConfig):
        raise ValueError('objective must be an explicit PlanObjectiveConfig')
    for name in ('horizon_days', 'destroy_count', 'max_iterations', 'max_evaluations'):
        value = getattr(config, name)
        if name == 'max_evaluations' and value is None:
            continue
        minimum = 1 if name == 'destroy_count' else 0
        if type(value) is not int or value < minimum:
            raise ValueError(f'{name} must be an exact integer >= {minimum}')
    if type(config.seed) is not int:
        raise ValueError('seed must be an exact integer')
    if config.horizon_days > date.max.toordinal() - date.min.toordinal():
        raise ValueError('Configured horizon exceeds calendar')


def _horizon_upper(state: SearchState, horizon_days: int) -> int:
    if type(horizon_days) is not int or horizon_days < 0:
        raise ValueError('horizon_days must be an exact nonnegative integer')
    upper = state.problem.today.toordinal() + horizon_days
    if upper > date.max.toordinal():
        raise ValueError('Configured horizon exceeds calendar')
    return upper


def _select_items(state: SearchState, count: int, operator: DestroyOperator,
                  rng: random.Random) -> tuple[int, ...]:
    """Selection order: sample, seed-distance-ID, or sorted-neighbour BFS then distance-ID."""
    if type(count) is not int or count <= 0:
        raise ValueError('destroy count must be a positive exact integer')
    if not isinstance(operator, DestroyOperator):
        raise ValueError('Expected DestroyOperator')
    groups = state.placements_by_item
    eligible = tuple(sorted(groups))
    count = min(count, len(eligible))
    if not count:
        return ()
    if operator is DestroyOperator.RANDOM:
        return tuple(rng.sample(eligible, count))
    seed = rng.choice(eligible)
    starts = {pk: rows[0].scheduled_date.toordinal() for pk, rows in groups.items()}
    temporal = sorted(eligible, key=lambda pk: (abs(starts[pk] - starts[seed]), pk))
    selected = [seed]
    if operator is DestroyOperator.DEPENDENCY:
        adjacent = {pk: set() for pk in eligible}
        for edge in state.problem.dependencies:
            a, b = edge.prerequisite_id, edge.dependent_id
            if a in adjacent and b in adjacent:
                adjacent[a].add(b)
                adjacent[b].add(a)
        seen, queue = {seed}, deque([seed])
        while queue and len(selected) < count:
            for pk in sorted(adjacent[queue.popleft()]):
                if pk not in seen:
                    seen.add(pk)
                    queue.append(pk)
                    selected.append(pk)
                    if len(selected) == count:
                        break
    selected_ids = set(selected)
    selected.extend(pk for pk in temporal if pk not in selected_ids)
    return tuple(selected[:count])


@dataclass(frozen=True, slots=True)
class _PartialSchedule:
    original: SearchState
    removed_item_ids: tuple[int, ...]
    retained: tuple[SessionPlacement, ...]


def _destroy(state: SearchState, item_ids: tuple[int, ...]) -> _PartialSchedule:
    removed = tuple(sorted(set(item_ids)))
    if not set(removed) <= state.placements_by_item.keys():
        raise ValueError('Only items with sessions can be destroyed')
    return _PartialSchedule(state, removed,
                            tuple(p for p in state.placements if p.item_id not in removed))


def _repair(partial: _PartialSchedule, horizon_days: int, operator: RepairOperator,
            rng: random.Random) -> SearchState | None:
    """One forward repair, without backtracking or scoring incomplete decisions."""
    original = partial.original
    upper = _horizon_upper(original, horizon_days)
    if not isinstance(operator, RepairOperator):
        raise ValueError('Expected RepairOperator')
    problem, groups = original.problem, original.placements_by_item
    placed = {(p.item_id, p.session_index): p for p in partial.retained}
    retained_ids = {p.item_id for p in partial.retained}
    removed = set(partial.removed_item_ids)
    for pk in problem.topological_order():
        if pk not in removed:
            continue
        item = problem.item_by_id[pk]
        lower = max(problem.today, item.release_date or problem.today).toordinal()
        for prerequisite in sorted(problem.direct_prerequisites(pk)):
            if prerequisite in groups:
                lower = max(lower, placed[prerequisite, len(groups[prerequisite]) - 1]
                            .scheduled_date.toordinal() + 1)
        ceiling = date.max.toordinal()
        for dependent in sorted(problem.direct_dependents(pk)):
            if dependent in retained_ids:
                ceiling = min(ceiling, placed[dependent, 0].scheduled_date.toordinal() - 1)
        for old in groups[pk]:
            old_day = old.scheduled_date.toordinal()
            lo, hi = lower, min(upper, ceiling)
            if old.session_index == 0 and item.anchor_date is not None:
                anchor = item.anchor_date.toordinal()
                lo, hi = max(lo, anchor), min(hi, anchor)
                fallback = old_day > upper and lower <= anchor <= ceiling
            else:
                fallback = old_day > upper and lower <= old_day <= ceiling
            # The original out-of-horizon date sorts after all in-horizon dates.
            size = max(0, hi - lo + 1)
            if not size and not fallback:
                return None
            index = 0 if operator is RepairOperator.EARLIEST else rng.randrange(size + int(fallback))
            ordinal = lo + index if index < size else old_day
            placed[pk, old.session_index] = SessionPlacement(pk, old.session_index, date.fromordinal(ordinal))
            lower = ordinal  # Same-day continuation is legal.
    try:
        candidate = SearchState(problem, tuple(placed.values()))
    except ValueError as exc:
        raise RuntimeError('Destroy/repair contract emitted an invalid complete state') from exc
    return None if candidate == original else candidate


def _changed_placements(before: SearchState, after: SearchState) -> tuple[SessionPlacement, ...]:
    """Replacement rows in identity order, replayed atomically; these are not C4.1 Moves."""
    if before.problem != after.problem:
        raise ValueError('Changes require the same problem')
    return tuple(new for old, new in zip(before.placements, after.placements, strict=True) if old != new)
