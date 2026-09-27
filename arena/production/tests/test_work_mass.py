from datetime import (
    date,
    timedelta,
)
from decimal import Decimal

import pytest

from arena.production.work_mass import (
    DayHeadroom,
    WorkEstimate,
    allocate_work_mass,
    allocation_hours,
    hours_for_percentage,
    percentage_for_hours,
    remaining_work_hours,
    validate_dynamic_plan,
    work_allocations_to_plan,
)
from arena.scheduling.domain import (
    ScheduleItem,
    ScheduleProblem,
)


TODAY = date(
    2026,
    10,
    7,
)

DAY = timedelta(
    days=1,
)


def item(
    *,
    duration_category=
        "UNDER_16_HOURS",
    percent_completed=
        "0",
) -> ScheduleItem:
    completed = Decimal(
        percent_completed
    )

    return ScheduleItem(
        item_id=1,
        duration_category=
            duration_category,
        priority_position=None,
        release_date=None,
        due_date=
            TODAY + 12 * DAY,
        anchor_date=None,
        percent_completed=
            completed,
        remaining_fraction=(
            Decimal("1")
            - completed
            / Decimal("100")
        ),
    )


def problem(
    obj: ScheduleItem,
) -> ScheduleProblem:
    return ScheduleProblem(
        today=TODAY,
        items=(obj,),
        dependencies=(),
        capacity_by_duration={
            "UNDER_20_MINUTES": 10,
            "UNDER_1_HOUR": 10,
            "UNDER_4_HOURS": 10,
            "UNDER_8_HOURS": 10,
            "UNDER_16_HOURS": 10,
            "OVER_16_HOURS": 10,
        },
    )


def test_percentage_is_derived_from_task_work_mass():
    estimate = WorkEstimate(
        item_id=1,
        total_hours=
            Decimal("16"),
        source=
            "duration_category_upper_bound",
    )

    assert (
        percentage_for_hours(
            Decimal("3.2"),
            estimate,
        )
        == Decimal("20")
    )

    assert (
        hours_for_percentage(
            Decimal("20"),
            estimate,
        )
        == Decimal("3.2")
    )


def test_dynamic_headroom_produces_30_25_45_not_equal_fixed_pieces():
    obj = item()

    estimate = WorkEstimate(
        item_id=1,
        total_hours=
            Decimal("16"),
        source=
            "duration_category_upper_bound",
    )

    allocations = (
        allocate_work_mass(
            obj,
            estimate,
            (
                DayHeadroom(
                    TODAY,
                    Decimal("4.8"),
                ),
                DayHeadroom(
                    TODAY + DAY,
                    Decimal("4"),
                ),
                DayHeadroom(
                    TODAY + 3 * DAY,
                    Decimal("7.2"),
                ),
            ),
        )
    )

    assert tuple(
        row.percentage
        for row in allocations
    ) == (
        Decimal("30.00"),
        Decimal("25.00"),
        Decimal("45.00"),
    )

    assert tuple(
        row.hours
        for row in allocations
    ) == (
        Decimal("4.8"),
        Decimal("4"),
        Decimal("7.2"),
    )


def test_dynamic_30_25_45_plan_is_valid_under_existing_arc_contract():
    obj = item()

    estimate = WorkEstimate(
        1,
        Decimal("16"),
        "test",
    )

    allocations = (
        allocate_work_mass(
            obj,
            estimate,
            (
                DayHeadroom(
                    TODAY,
                    Decimal("4.8"),
                ),
                DayHeadroom(
                    TODAY + DAY,
                    Decimal("4"),
                ),
                DayHeadroom(
                    TODAY + 3 * DAY,
                    Decimal("7.2"),
                ),
            ),
        )
    )

    plan = (
        work_allocations_to_plan(
            allocations
        )
    )

    validation = (
        validate_dynamic_plan(
            problem(obj),
            plan,
        )
    )

    assert (
        validation.violations
        == ()
    )

    assert (
        validation.infeasibilities
        == ()
    )


def test_partial_task_allocates_only_remaining_work_mass():
    obj = item(
        percent_completed="25",
    )

    estimate = WorkEstimate(
        1,
        Decimal("16"),
        "test",
    )

    assert (
        remaining_work_hours(
            obj,
            estimate,
        )
        == Decimal("12")
    )

    allocations = (
        allocate_work_mass(
            obj,
            estimate,
            (
                DayHeadroom(
                    TODAY,
                    Decimal("4"),
                ),
                DayHeadroom(
                    TODAY + DAY,
                    Decimal("5"),
                ),
                DayHeadroom(
                    TODAY + 2 * DAY,
                    Decimal("3"),
                ),
            ),
        )
    )

    assert sum(
        (
            row.percentage
            for row in allocations
        ),
        Decimal("0"),
    ) == Decimal("75")

    assert sum(
        (
            row.hours
            for row in allocations
        ),
        Decimal("0"),
    ) == Decimal("12")


def test_rounding_conserves_exact_remaining_percentage():
    obj = item()

    estimate = WorkEstimate(
        1,
        Decimal("7"),
        "test",
    )

    allocations = (
        allocate_work_mass(
            obj,
            estimate,
            (
                DayHeadroom(
                    TODAY,
                    Decimal("2"),
                ),
                DayHeadroom(
                    TODAY + DAY,
                    Decimal("2"),
                ),
                DayHeadroom(
                    TODAY + 2 * DAY,
                    Decimal("3"),
                ),
            ),
        )
    )

    assert sum(
        (
            row.percentage
            for row in allocations
        ),
        Decimal("0"),
    ) == Decimal("100")

    assert tuple(
        row.percentage
        for row in allocations
    ) == (
        Decimal("28.57"),
        Decimal("28.57"),
        Decimal("42.86"),
    )


def test_atomic_task_is_not_split_even_if_multiple_days_are_supplied():
    obj = item(
        duration_category=
            "UNDER_4_HOURS",
    )

    estimate = WorkEstimate(
        1,
        Decimal("4"),
        "test",
    )

    allocations = (
        allocate_work_mass(
            obj,
            estimate,
            (
                DayHeadroom(
                    TODAY,
                    Decimal("4"),
                ),
                DayHeadroom(
                    TODAY + DAY,
                    Decimal("4"),
                ),
            ),
        )
    )

    assert len(
        allocations
    ) == 1

    assert (
        allocations[0]
        .percentage
        == Decimal("100")
    )


def test_atomic_task_requires_enough_single_day_headroom():
    obj = item(
        duration_category=
            "UNDER_4_HOURS",
    )

    estimate = WorkEstimate(
        1,
        Decimal("4"),
        "test",
    )

    with pytest.raises(
        ValueError,
        match="atomic task requires",
    ):
        allocate_work_mass(
            obj,
            estimate,
            (
                DayHeadroom(
                    TODAY,
                    Decimal("2"),
                ),
                DayHeadroom(
                    TODAY + DAY,
                    Decimal("2"),
                ),
            ),
        )


def test_allocation_hours_round_trip():
    obj = item()

    estimate = WorkEstimate(
        1,
        Decimal("16"),
        "test",
    )

    dynamic = (
        allocate_work_mass(
            obj,
            estimate,
            (
                DayHeadroom(
                    TODAY,
                    Decimal("4"),
                ),
                DayHeadroom(
                    TODAY + DAY,
                    Decimal("12"),
                ),
            ),
        )
    )

    plan = (
        work_allocations_to_plan(
            dynamic
        )
    )

    assert (
        allocation_hours(
            plan.allocations[0],
            estimate,
        )
        == Decimal("4.00")
    )
