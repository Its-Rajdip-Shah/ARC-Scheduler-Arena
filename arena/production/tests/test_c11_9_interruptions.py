from datetime import date, timedelta
from decimal import Decimal

import pytest

from arena.production.flavour_planner import (
    generate_flavour_schedule,
)
from arena.scheduling.domain import (
    ScheduleItem,
    ScheduleProblem,
)
from arena.scheduling.validation import (
    validate_plan,
)


D = Decimal
TODAY = date(2026, 10, 12)
DAY = timedelta(days=1)


def item(
    item_id,
    duration,
    *,
    release=None,
    due=None,
    anchor=None,
):
    return ScheduleItem(
        item_id=item_id,
        duration_category=duration,
        priority_position=None,
        release_date=release,
        due_date=due,
        anchor_date=anchor,
        percent_completed=D("0"),
        remaining_fraction=D("1"),
    )


def problem(items):
    return ScheduleProblem(
        today=TODAY,
        items=tuple(items),
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


@pytest.mark.parametrize(
    "flavour",
    ["lock-in", "monk"],
)
def test_full_anchor_pressure_can_interrupt_then_large_task_resumes(
    flavour,
):
    big = item(
        1,
        "OVER_16_HOURS",
        due=TODAY + 14 * DAY,
    )

    # Four actual TASKS anchored to day 13.
    # Together they consume 10 hours, leaving no production headroom.
    anchored_a = item(
        2,
        "UNDER_4_HOURS",
        anchor=TODAY + DAY,
    )
    anchored_b = item(
        3,
        "UNDER_4_HOURS",
        anchor=TODAY + DAY,
    )
    anchored_c = item(
        4,
        "UNDER_1_HOUR",
        anchor=TODAY + DAY,
    )
    anchored_d = item(
        5,
        "UNDER_1_HOUR",
        anchor=TODAY + DAY,
    )

    p = problem([
        big,
        anchored_a,
        anchored_b,
        anchored_c,
        anchored_d,
    ])

    generated = generate_flavour_schedule(
        p,
        flavour,
        explicit_total_hours={
            1: D("24"),
            2: D("4"),
            3: D("4"),
            4: D("1"),
            5: D("1"),
        },
    )

    big_rows = [
        row
        for row in generated.work_allocations
        if row.item_id == 1
    ]

    big_dates = {
        row.scheduled_date
        for row in big_rows
    }

    assert TODAY in big_dates
    assert TODAY + DAY not in big_dates
    assert TODAY + 2 * DAY in big_dates

    validation = validate_plan(
        p,
        generated.plan,
    )

    assert validation.violations == ()


@pytest.mark.parametrize(
    "flavour",
    ["lock-in", "monk"],
)
def test_urgent_release_can_interrupt_relaxed_started_task_then_it_resumes(
    flavour,
):
    big = item(
        1,
        "OVER_16_HOURS",
        due=TODAY + 14 * DAY,
    )

    # These tasks do not exist for scheduling purposes until day 13.
    # Once released they are due immediately and collectively consume the day.
    urgent_a = item(
        2,
        "UNDER_4_HOURS",
        release=TODAY + DAY,
        due=TODAY + DAY,
    )
    urgent_b = item(
        3,
        "UNDER_4_HOURS",
        release=TODAY + DAY,
        due=TODAY + DAY,
    )
    urgent_c = item(
        4,
        "UNDER_1_HOUR",
        release=TODAY + DAY,
        due=TODAY + DAY,
    )
    urgent_d = item(
        5,
        "UNDER_1_HOUR",
        release=TODAY + DAY,
        due=TODAY + DAY,
    )

    p = problem([
        big,
        urgent_a,
        urgent_b,
        urgent_c,
        urgent_d,
    ])

    generated = generate_flavour_schedule(
        p,
        flavour,
        explicit_total_hours={
            1: D("24"),
            2: D("4"),
            3: D("4"),
            4: D("1"),
            5: D("1"),
        },
    )

    big_dates = {
        row.scheduled_date
        for row in generated.work_allocations
        if row.item_id == 1
    }

    assert TODAY in big_dates
    assert TODAY + DAY not in big_dates
    assert TODAY + 2 * DAY in big_dates

    urgent_day_rows = [
        row
        for row in generated.work_allocations
        if (
            row.item_id in {2, 3, 4, 5}
            and row.scheduled_date
            == TODAY + DAY
        )
    ]

    assert sum(
        (
            row.hours
            for row in urgent_day_rows
        ),
        D("0"),
    ) == D("10")


@pytest.mark.parametrize(
    "flavour",
    ["lock-in", "monk"],
)
def test_relaxed_new_release_does_not_unnecessarily_break_continuity(
    flavour,
):
    big = item(
        1,
        "OVER_16_HOURS",
        due=TODAY + 14 * DAY,
    )

    relaxed = item(
        2,
        "UNDER_8_HOURS",
        release=TODAY + DAY,
        due=TODAY + 14 * DAY,
    )

    p = problem([
        big,
        relaxed,
    ])

    generated = generate_flavour_schedule(
        p,
        flavour,
        explicit_total_hours={
            1: D("24"),
            2: D("6"),
        },
    )

    big_dates = {
        row.scheduled_date
        for row in generated.work_allocations
        if row.item_id == 1
    }

    assert TODAY in big_dates
    assert TODAY + DAY in big_dates


@pytest.mark.parametrize(
    "flavour",
    ["lock-in", "monk"],
)
def test_interruption_does_not_create_illegal_percentage_or_dependency_state(
    flavour,
):
    big = item(
        1,
        "OVER_16_HOURS",
        due=TODAY + 10 * DAY,
    )

    blocker = item(
        2,
        "UNDER_4_HOURS",
        anchor=TODAY + DAY,
    )

    p = problem([
        big,
        blocker,
    ])

    generated = generate_flavour_schedule(
        p,
        flavour,
        explicit_total_hours={
            1: D("18"),
            2: D("4"),
        },
    )

    big_percent = sum(
        (
            row.percentage
            for row in generated.work_allocations
            if row.item_id == 1
        ),
        D("0"),
    )

    assert big_percent == D("100")

    result = validate_plan(
        p,
        generated.plan,
    )

    assert result.violations == ()


@pytest.mark.parametrize(
    "flavour",
    ["lock-in", "monk"],
)
def test_due_today_work_can_exceed_soft_max_instead_of_becoming_late(
    flavour,
):
    urgent = [
        item(
            1,
            "UNDER_4_HOURS",
            release=TODAY,
            due=TODAY,
        ),
        item(
            2,
            "UNDER_4_HOURS",
            release=TODAY,
            due=TODAY,
        ),
        item(
            3,
            "UNDER_1_HOUR",
            release=TODAY,
            due=TODAY,
        ),
        item(
            4,
            "UNDER_1_HOUR",
            release=TODAY,
            due=TODAY,
        ),
    ]

    p = problem(urgent)

    generated = generate_flavour_schedule(
        p,
        flavour,
        explicit_total_hours={
            1: D("4"),
            2: D("4"),
            3: D("1"),
            4: D("1"),
        },
    )

    assert (
        generated.daily_hours[TODAY]
        == D("10")
    )

    assert (
        generated.daily_status[TODAY].value
        == "locked-in"
        if flavour == "lock-in"
        else generated.daily_status[TODAY].value
        == "overloaded"
    )


@pytest.mark.parametrize(
    "flavour",
    ["lock-in", "monk"],
)
def test_physically_impossible_due_today_load_is_scheduled_and_marked_infeasible(
    flavour,
):
    p = problem([
        item(
            1,
            "OVER_16_HOURS",
            release=TODAY,
            due=TODAY,
        ),
    ])

    generated = generate_flavour_schedule(
        p,
        flavour,
        explicit_total_hours={
            1: D("30"),
        },
    )

    assert (
        generated.daily_hours[TODAY]
        == D("30")
    )

    assert (
        generated.daily_status[TODAY].value
        == "infeasible"
    )
