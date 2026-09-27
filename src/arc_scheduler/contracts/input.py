"""Version 1 scheduler input contract.

This module contains no Django or ARC database dependency.

Only algorithm-visible scheduling facts belong here. Canonical ARC state that
does not affect scheduling remains outside this contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from types import MappingProxyType
from typing import Mapping

from .enums import SchedulerFlavourV1


def _decimal(value: Decimal | int | float | str) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


@dataclass(frozen=True, slots=True)
class SchedulerTaskInputV1:
    item_id: int
    duration_category: str
    priority_position: int | None

    release_date: date | None
    due_date: date | None
    anchor_date: date | None

    percent_completed: Decimal
    remaining_fraction: Decimal

    is_residual: bool = False

    # Observational scheduler state only. Never canonical authority.
    existing_scheduled_date: date | None = None

    def __post_init__(self) -> None:
        percent = _decimal(self.percent_completed)
        remaining = _decimal(self.remaining_fraction)

        if not Decimal("0") <= percent <= Decimal("100"):
            raise ValueError("percent_completed must be in [0, 100].")

        if not Decimal("0") <= remaining <= Decimal("1"):
            raise ValueError("remaining_fraction must be in [0, 1].")

        object.__setattr__(self, "percent_completed", percent)
        object.__setattr__(self, "remaining_fraction", remaining)


@dataclass(frozen=True, slots=True, order=True)
class SchedulerDependencyInputV1:
    prerequisite_id: int
    dependent_id: int

    def __post_init__(self) -> None:
        if self.prerequisite_id == self.dependent_id:
            raise ValueError("Dependency cannot be a self-edge.")


@dataclass(frozen=True, slots=True)
class SchedulerInputV1:
    today: date
    flavour: SchedulerFlavourV1 | str

    tasks: tuple[SchedulerTaskInputV1, ...]
    dependencies: tuple[SchedulerDependencyInputV1, ...]

    # Existing engine input. This is not yet ARC user-availability semantics.
    capacity_by_duration: Mapping[str, int]

    # Existing explicit permission signal from the current scheduler domain.
    overload_dates: frozenset[date] = frozenset()

    # Optional total work estimates for 100% of an item.
    # Missing rows use the frozen duration-category fallback priors.
    explicit_total_hours: Mapping[int, Decimal] | None = None

    def __post_init__(self) -> None:
        flavour = SchedulerFlavourV1(self.flavour)

        ids = tuple(task.item_id for task in self.tasks)
        if len(ids) != len(set(ids)):
            raise ValueError("Scheduler task IDs must be unique.")

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

        capacities = {
            str(key): int(value)
            for key, value in self.capacity_by_duration.items()
        }

        if any(value < 0 for value in capacities.values()):
            raise ValueError("capacity_by_duration values cannot be negative.")

        explicit = {
            int(item_id): _decimal(hours)
            for item_id, hours in (self.explicit_total_hours or {}).items()
        }

        unknown_estimates = set(explicit) - item_ids
        if unknown_estimates:
            raise ValueError(
                "Explicit estimates reference unknown items: "
                f"{sorted(unknown_estimates)}"
            )

        if any(hours <= 0 for hours in explicit.values()):
            raise ValueError("Explicit total hours must be positive.")

        object.__setattr__(self, "flavour", flavour)
        object.__setattr__(
            self,
            "capacity_by_duration",
            MappingProxyType(capacities),
        )
        object.__setattr__(
            self,
            "explicit_total_hours",
            MappingProxyType(explicit),
        )
        object.__setattr__(
            self,
            "overload_dates",
            frozenset(self.overload_dates),
        )
