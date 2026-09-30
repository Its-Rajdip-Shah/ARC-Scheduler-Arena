"""Immutable pure-Python scheduling domain.

This module deliberately knows nothing about Django or PlanningItem.

ARC owns canonical truth. Algorithms receive a frozen ScheduleProblem and
return a frozen SchedulePlan. They cannot mutate hierarchy, dependencies,
priority, progress, dates, or any other canonical workload state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True, slots=True, order=True)
class DependencyEdge:
    """One explicit canonical prerequisite -> dependent edge."""

    prerequisite_id: int
    dependent_id: int

    def __post_init__(self) -> None:
        if self.prerequisite_id == self.dependent_id:
            raise ValueError("Dependency cannot be a self-edge.")


@dataclass(frozen=True, slots=True)
class ScheduleItem:
    """One algorithm-visible executable workload item."""

    item_id: int
    duration_category: str
    priority_position: int | None

    release_date: date | None
    due_date: date | None
    anchor_date: date | None

    percent_completed: Decimal
    remaining_fraction: Decimal

    is_residual: bool = False

    # Observational snapshot of canonical scheduled_date, not a constraint.
    existing_scheduled_date: date | None = None

    # Explicit human ordering intent inside this task's Focus duration
    # bucket on anchor_date. Final global execution_rank remains disposable
    # scheduler output and may interleave other Focus buckets.
    anchor_order: int | None = None

    def __post_init__(self) -> None:
        if not Decimal("0") <= self.percent_completed <= Decimal("100"):
            raise ValueError("percent_completed must be in [0, 100].")

        if not Decimal("0") <= self.remaining_fraction <= Decimal("1"):
            raise ValueError("remaining_fraction must be in [0, 1].")

        if self.anchor_order is not None:
            if self.anchor_date is None:
                raise ValueError(
                    "anchor_order requires anchor_date."
                )

            if self.anchor_order < 1:
                raise ValueError(
                    "anchor_order must be positive."
                )


@dataclass(frozen=True, slots=True)
class ScheduleProblem:
    """Complete immutable input visible to a scheduling algorithm.

    ``dependencies`` contains only explicit canonical edges.

    Transitive relationships are derived from the DAG and are never written
    back as invented canonical dependencies.
    """

    today: date
    items: tuple[ScheduleItem, ...]
    dependencies: tuple[DependencyEdge, ...]
    capacity_by_duration: Mapping[str, int]
    overload_dates: frozenset[date] = frozenset()

    _item_by_id_cache: Mapping[int, ScheduleItem] = field(
        init=False,
        repr=False,
        compare=False,
    )
    _item_ids_cache: frozenset[int] = field(
        init=False,
        repr=False,
        compare=False,
    )
    _direct_prerequisites_cache: Mapping[int, frozenset[int]] = field(
        init=False,
        repr=False,
        compare=False,
    )
    _direct_dependents_cache: Mapping[int, frozenset[int]] = field(
        init=False,
        repr=False,
        compare=False,
    )
    _topological_order_cache: tuple[int, ...] = field(
        init=False,
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        ids = tuple(item.item_id for item in self.items)

        if len(ids) != len(set(ids)):
            raise ValueError("ScheduleProblem item IDs must be unique.")

        item_ids = set(ids)
        edge_pairs = {
            (edge.prerequisite_id, edge.dependent_id)
            for edge in self.dependencies
        }

        if len(edge_pairs) != len(self.dependencies):
            raise ValueError("Duplicate dependency edge.")

        for edge in self.dependencies:
            if edge.prerequisite_id not in item_ids:
                raise ValueError(
                    f"Unknown prerequisite item {edge.prerequisite_id}."
                )
            if edge.dependent_id not in item_ids:
                raise ValueError(
                    f"Unknown dependent item {edge.dependent_id}."
                )

        # Freeze caller-owned dictionaries so an algorithm cannot observe
        # external mutation after problem construction.
        object.__setattr__(
            self,
            "capacity_by_duration",
            MappingProxyType(dict(self.capacity_by_duration)),
        )

        item_by_id = {
            item.item_id: item
            for item in self.items
        }

        direct_prerequisites = {
            item_id: set()
            for item_id in item_ids
        }

        direct_dependents = {
            item_id: set()
            for item_id in item_ids
        }

        for edge in self.dependencies:
            direct_prerequisites[
                edge.dependent_id
            ].add(
                edge.prerequisite_id
            )

            direct_dependents[
                edge.prerequisite_id
            ].add(
                edge.dependent_id
            )

        object.__setattr__(
            self,
            "_item_by_id_cache",
            MappingProxyType(
                item_by_id
            ),
        )

        object.__setattr__(
            self,
            "_item_ids_cache",
            frozenset(
                item_ids
            ),
        )

        object.__setattr__(
            self,
            "_direct_prerequisites_cache",
            MappingProxyType({
                item_id:
                    frozenset(values)
                for item_id, values
                in direct_prerequisites.items()
            }),
        )

        object.__setattr__(
            self,
            "_direct_dependents_cache",
            MappingProxyType({
                item_id:
                    frozenset(values)
                for item_id, values
                in direct_dependents.items()
            }),
        )

        object.__setattr__(
            self,
            "_topological_order_cache",
            self._compute_topological_order(),
        )

    @property
    def item_by_id(self) -> Mapping[int, ScheduleItem]:
        return self._item_by_id_cache

    def direct_prerequisites(self, item_id: int) -> frozenset[int]:
        self._require_item(
            item_id
        )

        return self._direct_prerequisites_cache[
            item_id
        ]

    def direct_dependents(self, item_id: int) -> frozenset[int]:
        self._require_item(
            item_id
        )

        return self._direct_dependents_cache[
            item_id
        ]

    def transitive_prerequisites(self, item_id: int) -> frozenset[int]:
        """All upstream prerequisites implied by graph reachability."""

        self._require_item(item_id)

        result: set[int] = set()
        stack = list(self.direct_prerequisites(item_id))

        while stack:
            current = stack.pop()

            if current in result:
                continue

            result.add(current)
            stack.extend(self.direct_prerequisites(current))

        return frozenset(result)

    def transitive_dependents(self, item_id: int) -> frozenset[int]:
        """All downstream dependents implied by graph reachability."""

        self._require_item(item_id)

        result: set[int] = set()
        stack = list(self.direct_dependents(item_id))

        while stack:
            current = stack.pop()

            if current in result:
                continue

            result.add(current)
            stack.extend(self.direct_dependents(current))

        return frozenset(result)

    def topological_order(self) -> tuple[int, ...]:
        """Deterministic topological ordering of the explicit DAG."""

        return self._topological_order_cache

    def _compute_topological_order(self) -> tuple[int, ...]:
        indegree = {
            item.item_id: 0
            for item in self.items
        }

        outgoing = {
            item.item_id: []
            for item in self.items
        }

        for edge in self.dependencies:
            indegree[
                edge.dependent_id
            ] += 1

            outgoing[
                edge.prerequisite_id
            ].append(
                edge.dependent_id
            )

        ready = sorted(
            item_id
            for item_id, degree
            in indegree.items()
            if degree == 0
        )

        order: list[int] = []

        while ready:
            current = ready.pop(0)

            order.append(
                current
            )

            for dependent in sorted(
                outgoing[current]
            ):
                indegree[
                    dependent
                ] -= 1

                if (
                    indegree[
                        dependent
                    ]
                    == 0
                ):
                    ready.append(
                        dependent
                    )

                    ready.sort()

        if len(order) != len(self.items):
            raise ValueError(
                "Dependency graph contains a cycle."
            )

        return tuple(order)

    def _assert_acyclic(self) -> None:
        self._compute_topological_order()

    def _require_item(self, item_id: int) -> None:
        if item_id not in self._item_ids_cache:
            raise KeyError(
                item_id
            )


@dataclass(frozen=True, slots=True)
class Allocation:
    """One disposable future scheduling proposal.

    Percentage is percentage of the item's TOTAL work, matching ARC's
    SchedulerAllocation representation.
    """

    item_id: int
    scheduled_date: date
    percentage: Decimal
    execution_rank: int

    def __post_init__(self) -> None:
        if not Decimal("0") < self.percentage <= Decimal("100"):
            raise ValueError(
                "Allocation percentage must be in (0, 100]."
            )

        if self.execution_rank < 1:
            raise ValueError(
                "execution_rank must be positive."
            )


@dataclass(frozen=True, slots=True)
class SchedulePlan:
    """Pure algorithm proposal.

    Algorithms may return conflicts/diagnostics, but those declarations do
    not make an invalid plan valid. The shared validator is authoritative.
    """

    allocations: tuple[Allocation, ...]
    conflicts: tuple[str, ...] = ()
    diagnostics: tuple[tuple[str, str], ...] = ()

    def allocations_for(
        self,
        item_id: int,
    ) -> tuple[Allocation, ...]:
        return tuple(
            row
            for row in self.allocations
            if row.item_id == item_id
        )
