"""Pure session mechanics and persistent construction state; no selection policy."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from types import MappingProxyType
from typing import Mapping

from arc_scheduler.engine.domain import Allocation, ScheduleItem, SchedulePlan, ScheduleProblem

ATOMIC = frozenset({'UNDER_20_MINUTES', 'UNDER_1_HOUR', 'UNDER_4_HOURS'})
SPLIT_COUNTS = MappingProxyType({'UNDER_8_HOURS': 2, 'UNDER_16_HOURS': 2, 'OVER_16_HOURS': 3})


def effective_bucket(item: ScheduleItem) -> str:
    return 'UNDER_20_MINUTES' if item.is_residual else item.duration_category


def session_pieces(item: ScheduleItem) -> tuple[Decimal, ...]:
    """Conserve remaining work exactly, in percent of TOTAL work.

    Keep historical rounded pieces when they conserve work; otherwise collapse
    to one exact positive remainder rather than manufacture rounded-up work.
    """
    remaining = item.remaining_fraction * Decimal('100')
    if remaining <= 0:
        return ()
    bucket = effective_bucket(item)
    if bucket in ATOMIC:
        return (remaining,)
    try:
        count = SPLIT_COUNTS[bucket]
    except KeyError as exc:
        raise ValueError(f'Unknown duration category: {bucket}') from exc
    base = (remaining / Decimal(count)).quantize(Decimal('0.01'))
    pieces = [base] * count
    pieces[-1] += remaining - sum(pieces, Decimal('0'))
    positive = tuple(piece for piece in pieces if piece > 0)
    return positive if sum(positive, Decimal(0)) == remaining else (remaining,)


@dataclass(frozen=True, slots=True)
class SessionAction:
    """One proposed session; zero-based index identifies its frozen piece."""
    item_id: int
    session_index: int
    scheduled_date: date


@dataclass(frozen=True, slots=True)
class Readiness:
    lower_bound: date | None
    missing_prerequisites: frozenset[int] = frozenset()
    calendar_exhausted: bool = False


def readiness(problem: ScheduleProblem, state: ScheduleState, item_id: int) -> Readiness:
    """Completion-based readiness; anchors deliberately do not enter it."""
    if state.problem != problem:
        raise ValueError('State belongs to a different problem')
    item = problem.item_by_id[item_id]
    prerequisites = problem.direct_prerequisites(item_id)
    missing = prerequisites - state.completion.keys()
    if missing:
        return Readiness(None, frozenset(missing))
    lower = max(problem.today, item.release_date or problem.today)
    for pk in sorted(prerequisites):
        try:
            following = state.completion[pk] + timedelta(days=1)
        except OverflowError:
            return Readiness(None, calendar_exhausted=True)
        lower = max(lower, following)
    return Readiness(lower)


@dataclass(frozen=True, slots=True)
class ScheduleState:
    """Persistent, problem-bound state. Derived indexes cannot be supplied by callers.

    Supplied allocations are checked by replay, never repaired. Partial states
    need not be complete plans; validate_plan remains the final authority.
    """
    problem: ScheduleProblem
    allocations: tuple[Allocation, ...] = ()
    usage: Mapping[tuple[date, str], int] = field(init=False)
    completion: Mapping[int, date] = field(init=False)
    next_rank_by_date: Mapping[date, int] = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, 'allocations', tuple(self.allocations))
        usage, completion, ranks, rows = {}, {}, {}, {}
        for row in self.allocations:
            item = self.problem.item_by_id[row.item_id]
            prior = rows.setdefault(row.item_id, [])
            pieces = session_pieces(item)
            if len(prior) >= len(pieces) or row.percentage != pieces[len(prior)]:
                raise ValueError('Allocation does not match next session piece')
            lower = max(self.problem.today, item.release_date or self.problem.today)
            for pk in self.problem.direct_prerequisites(row.item_id):
                if pk not in completion:
                    raise ValueError('Prerequisite is not complete')
                try:
                    lower = max(lower, completion[pk] + timedelta(days=1))
                except OverflowError as exc:
                    raise ValueError('Readiness exceeds calendar') from exc
            if row.scheduled_date < lower:
                raise ValueError('Placement before readiness')
            if prior and row.scheduled_date < prior[-1].scheduled_date:
                raise ValueError('Sessions must be appended in date order')
            if not prior and item.anchor_date is not None and row.scheduled_date != item.anchor_date:
                raise ValueError('Anchor violation')
            if row.execution_rank != ranks.get(row.scheduled_date, 1):
                raise ValueError('Unexpected execution rank')
            ranks[row.scheduled_date] = row.execution_rank + 1
            key = (row.scheduled_date, effective_bucket(item))
            usage[key] = usage.get(key, 0) + 1
            prior.append(row)
            total = sum((r.percentage for r in prior), Decimal(0))
            expected = item.remaining_fraction * Decimal(100)
            if total > expected:
                raise ValueError('Session pieces exceed remaining work')
            if len(prior) == len(pieces) and total == expected:
                completion[row.item_id] = row.scheduled_date
        for name, value in [('usage', usage), ('completion', completion), ('next_rank_by_date', ranks)]:
            object.__setattr__(self, name, MappingProxyType(value))

    def place(self, action: SessionAction) -> ScheduleState:
        """Append one hard-legal session, preserving this state; capacity is soft."""
        item = self.problem.item_by_id[action.item_id]
        index = sum(row.item_id == action.item_id for row in self.allocations)
        pieces = session_pieces(item)
        if action.session_index != index or index >= len(pieces):
            raise ValueError('Action is not the next session')
        row = Allocation(action.item_id, action.scheduled_date, pieces[index],
                         self.next_rank_by_date.get(action.scheduled_date, 1))
        return ScheduleState(self.problem, self.allocations + (row,))

    def to_plan(self) -> SchedulePlan:
        return SchedulePlan(self.allocations)


@dataclass(frozen=True, slots=True)
class SessionCandidate:
    action: SessionAction
    bucket: str
    usage_before: int
    capacity: int
    overload_allowed: bool

    @property
    def excess_after(self) -> int:
        return max(0, self.usage_before + 1 - self.capacity)


def session_candidates(state: ScheduleState, item_id: int, *,
                       horizon: date | None = None) -> tuple[SessionCandidate, ...]:
    """All next-session dates in ascending order, including soft overload.

    An inclusive horizon is mandatory for undated work and late fallbacks.
    An anchor fixes the first session even beyond a deadline, but never repairs
    a readiness conflict. A supplied horizon always bounds enumeration.
    """
    problem = state.problem
    item = problem.item_by_id[item_id]
    if item.due_date is None and horizon is None:
        raise ValueError('Undated work requires an explicit finite horizon')
    ready = readiness(problem, state, item_id)
    if ready.lower_bound is None:
        return ()
    prior = [row for row in state.allocations if row.item_id == item_id]
    index = len(prior)
    pieces = session_pieces(item)
    if sum(pieces, Decimal(0)) != item.remaining_fraction * Decimal(100):
        raise ValueError('Frozen session pieces do not conserve remaining work')
    if index >= len(pieces):
        return ()
    lower = max(ready.lower_bound, prior[-1].scheduled_date if prior else ready.lower_bound)
    if not prior and item.anchor_date is not None:
        lower_anchor = item.anchor_date
        if lower_anchor < lower or (horizon is not None and lower_anchor > horizon):
            return ()
        days = (lower_anchor,)
    else:
        upper = item.due_date
        if upper is None or lower > upper:
            if horizon is None:
                raise ValueError('Late fallback requires an explicit finite horizon')
            upper = horizon
        elif horizon is not None:
            upper = min(upper, horizon)
        days = tuple(lower + timedelta(days=i) for i in range((upper - lower).days + 1))
    bucket = effective_bucket(item)
    limit = problem.capacity_by_duration.get(bucket)
    if limit is None:
        raise ValueError(f'No capacity definition for {bucket}')
    return tuple(SessionCandidate(SessionAction(item_id, index, day), bucket,
                                  state.usage.get((day, bucket), 0), limit,
                                  day in problem.overload_dates) for day in days)
