"""Complete immutable date decisions, separate from construction state."""
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType
from typing import Mapping

from arena.scheduling.domain import Allocation, SchedulePlan, ScheduleProblem
from arena.scheduling.mechanics import effective_bucket, session_pieces
from arena.scheduling.validation import validate_plan


@dataclass(frozen=True, slots=True, order=True)
class SessionPlacement:
    item_id: int
    session_index: int
    scheduled_date: date


@dataclass(frozen=True, slots=True)
class SearchState:
    problem: ScheduleProblem
    placements: tuple[SessionPlacement, ...]

    def __post_init__(self) -> None:
        rows = tuple(sorted(self.placements, key=lambda p: (p.item_id, p.session_index)))
        object.__setattr__(self, 'placements', rows)
        items = self.problem.item_by_id
        expected = {(i.item_id, k) for i in self.problem.items
                    for k in range(len(session_pieces(i)))}
        identities = [(p.item_id, p.session_index) for p in rows]
        if len(set(identities)) != len(rows) or set(identities) != expected:
            raise ValueError('Expected each canonical session identity exactly once')
        grouped = self.placements_by_item
        for p in rows:
            item = items[p.item_id]
            if type(p.scheduled_date) is not date:
                raise ValueError('Session date must be a calendar date')
            if p.scheduled_date < max(self.problem.today, item.release_date or self.problem.today):
                raise ValueError('Session before today/release')
            if p.session_index == 0 and item.anchor_date is not None and p.scheduled_date != item.anchor_date:
                raise ValueError('First session must match anchor')
        for group in grouped.values():
            if any(a.scheduled_date > b.scheduled_date for a, b in zip(group, group[1:])):
                raise ValueError('Sessions must be nondecreasing by index')
        for edge in self.problem.dependencies:
            before, after = grouped.get(edge.prerequisite_id), grouped.get(edge.dependent_id)
            if before and after and before[-1].scheduled_date >= after[0].scheduled_date:
                raise ValueError('Search requires feasible dependency precedence (including anchors)')

    def __hash__(self) -> int:
        # ScheduleProblem contains an unhashable mappingproxy. Equal problems
        # still produce equal keys; no copied problem or mutable cache is needed.
        p = self.problem
        return hash((p.today, p.items, p.dependencies,
                     tuple(sorted(p.capacity_by_duration.items())),
                     tuple(sorted(p.overload_dates)), self.placements))

    @property
    def placements_by_item(self) -> Mapping[int, tuple[SessionPlacement, ...]]:
        groups = {}
        for p in self.placements:
            groups.setdefault(p.item_id, []).append(p)
        return MappingProxyType({k: tuple(v) for k, v in groups.items()})

    def start(self, item_id: int) -> date:
        return self.placements_by_item[item_id][0].scheduled_date

    def completion(self, item_id: int) -> date:
        return self.placements_by_item[item_id][-1].scheduled_date

    def session_date(self, item_id: int, session_index: int) -> date:
        for p in self.placements:
            if (p.item_id, p.session_index) == (item_id, session_index):
                return p.scheduled_date
        raise KeyError((item_id, session_index))

    def usage(self, day: date, bucket: str) -> int:
        items = self.problem.item_by_id
        return sum(p.scheduled_date == day and effective_bucket(items[p.item_id]) == bucket
                   for p in self.placements)

    @classmethod
    def from_plan(cls, problem: ScheduleProblem, plan: SchedulePlan) -> 'SearchState':
        result = validate_plan(problem, plan)
        if result.violations:
            raise ValueError(f'Invalid plan: {result.violations}')
        if result.infeasibilities:
            raise ValueError(f'Canonical infeasibilities are not searchable: {result.infeasibilities}')
        groups = {}
        for row in plan.allocations:
            groups.setdefault(row.item_id, []).append(row)
        placements = []
        for item in sorted(problem.items, key=lambda i: i.item_id):
            rows = sorted(groups.get(item.item_id, ()), key=lambda r: (r.scheduled_date, r.execution_rank))
            if tuple(r.percentage for r in rows) != session_pieces(item):
                raise ValueError('Plan percentages do not match canonical session pieces')
            placements.extend(SessionPlacement(item.item_id, k, r.scheduled_date) for k, r in enumerate(rows))
        return cls(problem, tuple(placements))

    def to_plan(self) -> SchedulePlan:
        pieces = {i.item_id: session_pieces(i) for i in self.problem.items}
        ranks, rows = {}, []
        for p in sorted(self.placements, key=lambda p: (p.scheduled_date, p.item_id, p.session_index)):
            ranks[p.scheduled_date] = ranks.get(p.scheduled_date, 0) + 1
            rows.append(Allocation(p.item_id, p.scheduled_date,
                                   pieces[p.item_id][p.session_index], ranks[p.scheduled_date]))
        return SchedulePlan(tuple(rows))
