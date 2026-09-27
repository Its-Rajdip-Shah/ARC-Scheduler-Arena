"""Dynamic production work-mass allocation mechanics.

C1-C10 research search states use frozen equal-sized session identities.
Production C11 deliberately does not.

A production allocation represents an amount of estimated task work assigned
to a calendar day. Percentage is derived from work mass; it is not a
pre-selected scheduler piece.

This module contains mechanics only. Lock-in and Monk decide which days and
how much usable headroom each day should contribute.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import (
    Decimal,
    ROUND_DOWN,
)

from arena.scheduling.domain import (
    Allocation,
    ScheduleItem,
    SchedulePlan,
    ScheduleProblem,
)
from arena.scheduling.mechanics import (
    effective_bucket,
)
from arena.scheduling.validation import (
    ValidationResult,
    validate_plan,
)


PERCENT_QUANTUM = Decimal("0.01")
HOUR_QUANTUM = Decimal("0.01")

ATOMIC_BUCKETS = frozenset({
    "UNDER_20_MINUTES",
    "UNDER_1_HOUR",
    "UNDER_4_HOURS",
})


def _decimal(
    value: Decimal | int | float | str,
) -> Decimal:
    if isinstance(
        value,
        Decimal,
    ):
        return value

    return Decimal(
        str(value)
    )


@dataclass(
    frozen=True,
    slots=True,
)
class WorkEstimate:
    """Estimated total work mass for one task.

    total_hours refers to the estimated work required for 100% of the item,
    not merely its currently remaining work.

    source is provenance only; examples include:
    - user_estimate
    - learned_estimate
    - duration_category_prior
    """

    item_id: int
    total_hours: Decimal
    source: str

    def __post_init__(self) -> None:
        hours = _decimal(
            self.total_hours
        )

        if hours <= 0:
            raise ValueError(
                "total_hours must be positive"
            )

        if not self.source:
            raise ValueError(
                "WorkEstimate source is required"
            )

        object.__setattr__(
            self,
            "total_hours",
            hours,
        )


@dataclass(
    frozen=True,
    slots=True,
)
class DayHeadroom:
    """Amount of task work reasonably assignable to one day.

    This is intentionally not hard capacity.

    A flavour/policy may derive this quantity from:
    - existing workload;
    - desired daily intensity;
    - task continuity;
    - deadlines;
    - user availability;
    - other future production signals.

    Work-mass mechanics merely consume the result.
    """

    scheduled_date: date
    hours: Decimal

    def __post_init__(self) -> None:
        hours = _decimal(
            self.hours
        )

        if hours < 0:
            raise ValueError(
                "headroom hours cannot be negative"
            )

        object.__setattr__(
            self,
            "hours",
            hours,
        )


@dataclass(
    frozen=True,
    slots=True,
)
class WorkAllocation:
    """Human-interpretable work allocation before conversion to SchedulePlan."""

    item_id: int
    scheduled_date: date
    hours: Decimal
    percentage: Decimal

    def __post_init__(self) -> None:
        if self.hours <= 0:
            raise ValueError(
                "allocation hours must be positive"
            )

        if (
            self.percentage <= 0
            or self.percentage
            > Decimal("100")
        ):
            raise ValueError(
                "allocation percentage "
                "must be in (0, 100]"
            )


def total_percentage(
    item: ScheduleItem,
) -> Decimal:
    return (
        item.remaining_fraction
        * Decimal("100")
    )


def remaining_work_hours(
    item: ScheduleItem,
    estimate: WorkEstimate,
) -> Decimal:
    if (
        estimate.item_id
        != item.item_id
    ):
        raise ValueError(
            "WorkEstimate belongs to "
            "a different item"
        )

    return (
        estimate.total_hours
        * item.remaining_fraction
    )


def hours_for_percentage(
    percentage: Decimal | int | float | str,
    estimate: WorkEstimate,
) -> Decimal:
    percentage = _decimal(
        percentage
    )

    if (
        percentage < 0
        or percentage > 100
    ):
        raise ValueError(
            "percentage must be in [0, 100]"
        )

    return (
        estimate.total_hours
        * percentage
        / Decimal("100")
    )


def percentage_for_hours(
    hours: Decimal | int | float | str,
    estimate: WorkEstimate,
) -> Decimal:
    hours = _decimal(
        hours
    )

    if hours < 0:
        raise ValueError(
            "hours cannot be negative"
        )

    return (
        hours
        / estimate.total_hours
        * Decimal("100")
    )


def _rounded_percentage_for_hours(
    hours: Decimal,
    estimate: WorkEstimate,
) -> Decimal:
    """Round down so intermediate allocations never manufacture work."""

    return (
        percentage_for_hours(
            hours,
            estimate,
        )
        .quantize(
            PERCENT_QUANTUM,
            rounding=ROUND_DOWN,
        )
    )


def allocate_work_mass(
    item: ScheduleItem,
    estimate: WorkEstimate,
    headroom: tuple[
        DayHeadroom,
        ...,
    ],
) -> tuple[
    WorkAllocation,
    ...,
]:
    """Allocate remaining work dynamically over supplied day headroom.

    The function does NOT decide the calendar strategy.

    It consumes an ordered sequence of days and the amount of this task that
    the caller considers reasonable to perform on each day.

    Intermediate percentages are derived from assigned hours. The final
    allocation absorbs decimal rounding so total percentage equals the exact
    remaining canonical percentage.

    Atomic ARC buckets remain a single allocation and therefore require one
    day with enough supplied headroom for the remaining work estimate.
    """

    if (
        estimate.item_id
        != item.item_id
    ):
        raise ValueError(
            "estimate item mismatch"
        )

    if any(
        left.scheduled_date
        >= right.scheduled_date
        for left, right
        in zip(
            headroom,
            headroom[1:],
        )
    ):
        raise ValueError(
            "headroom dates must be "
            "strictly increasing"
        )

    remaining_hours = (
        remaining_work_hours(
            item,
            estimate,
        )
    )

    remaining_percent = (
        total_percentage(
            item
        )
    )

    if (
        remaining_hours <= 0
        or remaining_percent <= 0
    ):
        return ()

    bucket = effective_bucket(
        item
    )

    usable = tuple(
        row
        for row in headroom
        if row.hours > 0
    )

    if not usable:
        raise ValueError(
            "insufficient headroom "
            "for remaining work"
        )

    if bucket in ATOMIC_BUCKETS:
        first = usable[0]

        if (
            first.hours
            < remaining_hours
        ):
            raise ValueError(
                "atomic task requires one day "
                "with enough headroom"
            )

        return (
            WorkAllocation(
                item_id=item.item_id,
                scheduled_date=
                    first.scheduled_date,
                hours=
                    remaining_hours,
                percentage=
                    remaining_percent,
            ),
        )

    rows: list[
        WorkAllocation
    ] = []

    hours_left = (
        remaining_hours
    )

    percent_left = (
        remaining_percent
    )

    for day in usable:
        if hours_left <= 0:
            break

        assigned_hours = min(
            day.hours,
            hours_left,
        )

        if (
            assigned_hours
            == hours_left
        ):
            percentage = (
                percent_left
            )
        else:
            percentage = (
                _rounded_percentage_for_hours(
                    assigned_hours,
                    estimate,
                )
            )

            if percentage <= 0:
                continue

            percentage = min(
                percentage,
                percent_left,
            )

        rows.append(
            WorkAllocation(
                item_id=item.item_id,
                scheduled_date=
                    day.scheduled_date,
                hours=
                    assigned_hours,
                percentage=
                    percentage,
            )
        )

        hours_left -= (
            assigned_hours
        )

        percent_left -= (
            percentage
        )

    if hours_left > 0:
        raise ValueError(
            "supplied headroom does not "
            "cover remaining work"
        )

    if percent_left != 0:
        # Decimal percentage quantisation can leave a tiny remainder after
        # hours have been fully allocated. Conserve canonical work exactly by
        # attaching it to the final work session.
        final = rows[-1]

        rows[-1] = (
            WorkAllocation(
                item_id=
                    final.item_id,
                scheduled_date=
                    final.scheduled_date,
                hours=
                    final.hours,
                percentage=(
                    final.percentage
                    + percent_left
                ),
            )
        )

    if (
        sum(
            (
                row.percentage
                for row in rows
            ),
            Decimal("0"),
        )
        != remaining_percent
    ):
        raise AssertionError(
            "dynamic allocations failed "
            "percentage conservation"
        )

    return tuple(
        rows
    )


def allocation_hours(
    allocation: Allocation,
    estimate: WorkEstimate,
) -> Decimal:
    if (
        allocation.item_id
        != estimate.item_id
    ):
        raise ValueError(
            "allocation/estimate mismatch"
        )

    return hours_for_percentage(
        allocation.percentage,
        estimate,
    )


def work_allocations_to_plan(
    allocations: tuple[
        WorkAllocation,
        ...,
    ],
) -> SchedulePlan:
    """Convert dynamic work allocations to disposable ARC plan rows."""

    ranks: dict[
        date,
        int,
    ] = {}

    rows = []

    for allocation in sorted(
        allocations,
        key=lambda row: (
            row.scheduled_date,
            row.item_id,
        ),
    ):
        ranks[
            allocation.scheduled_date
        ] = (
            ranks.get(
                allocation.scheduled_date,
                0,
            )
            + 1
        )

        rows.append(
            Allocation(
                item_id=
                    allocation.item_id,
                scheduled_date=
                    allocation.scheduled_date,
                percentage=
                    allocation.percentage,
                execution_rank=
                    ranks[
                        allocation
                        .scheduled_date
                    ],
            )
        )

    return SchedulePlan(
        tuple(rows)
    )


def validate_dynamic_plan(
    problem: ScheduleProblem,
    plan: SchedulePlan,
) -> ValidationResult:
    """Production dynamic plans use the same independent ARC validator."""

    return validate_plan(
        problem,
        plan,
    )
