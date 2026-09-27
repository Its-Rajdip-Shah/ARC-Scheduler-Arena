from datetime import (
    date,
    timedelta,
)
from decimal import Decimal

from arena.production.flavour_planner import (
    generate_flavour_schedule,
)
from arena.scheduling.domain import (
    DependencyEdge,
    ScheduleItem,
    ScheduleProblem,
)
from arena.scheduling.validation import (
    validate_plan,
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
    item_id: int,
    duration: str,
    *,
    release=None,
    due=None,
    anchor=None,
    priority=None,
):
    return ScheduleItem(
        item_id=item_id,
        duration_category=duration,
        priority_position=priority,
        release_date=release,
        due_date=due,
        anchor_date=anchor,
        percent_completed=
            Decimal("0"),
        remaining_fraction=
            Decimal("1"),
    )


def problem(
    items,
    dependencies=(),
):
    return ScheduleProblem(
        today=TODAY,
        items=tuple(items),
        dependencies=tuple(
            dependencies
        ),
        capacity_by_duration={
            "UNDER_20_MINUTES": 10,
            "UNDER_1_HOUR": 10,
            "UNDER_4_HOURS": 10,
            "UNDER_8_HOURS": 10,
            "UNDER_16_HOURS": 10,
            "OVER_16_HOURS": 10,
        },
    )


def test_both_flavours_generate_valid_complete_plans():
    p = problem([
        item(
            1,
            "UNDER_16_HOURS",
            due=TODAY + 7 * DAY,
        ),
        item(
            2,
            "UNDER_8_HOURS",
            due=TODAY + 5 * DAY,
        ),
        item(
            3,
            "UNDER_1_HOUR",
            anchor=TODAY + DAY,
        ),
    ])

    for flavour in (
        "lock-in",
        "monk",
    ):
        generated = (
            generate_flavour_schedule(
                p,
                flavour,
            )
        )

        result = validate_plan(
            p,
            generated.plan,
        )

        assert (
            result.violations
            == ()
        )


def test_lock_in_finishes_same_work_no_later_than_monk_in_simple_open_window():
    p = problem([
        item(
            1,
            "UNDER_16_HOURS",
            due=TODAY + 10 * DAY,
        ),
        item(
            2,
            "UNDER_16_HOURS",
            due=TODAY + 10 * DAY,
        ),
    ])

    lock_in = (
        generate_flavour_schedule(
            p,
            "lock-in",
        )
    )

    monk = (
        generate_flavour_schedule(
            p,
            "monk",
        )
    )

    lock_finish = max(
        row.scheduled_date
        for row
        in lock_in.plan.allocations
    )

    monk_finish = max(
        row.scheduled_date
        for row
        in monk.plan.allocations
    )

    assert (
        lock_finish
        <= monk_finish
    )


def test_monk_has_no_higher_peak_hours_than_lock_in():
    p = problem([
        item(
            1,
            "UNDER_16_HOURS",
            due=TODAY + 12 * DAY,
        ),
        item(
            2,
            "UNDER_8_HOURS",
            due=TODAY + 12 * DAY,
        ),
        item(
            3,
            "UNDER_8_HOURS",
            due=TODAY + 12 * DAY,
        ),
    ])

    lock_in = (
        generate_flavour_schedule(
            p,
            "lock-in",
        )
    )

    monk = (
        generate_flavour_schedule(
            p,
            "monk",
        )
    )

    assert max(
        monk.daily_hours.values()
    ) <= max(
        lock_in.daily_hours.values()
    )


def test_dependency_waits_until_prerequisite_completion():
    p = problem(
        [
            item(
                1,
                "UNDER_16_HOURS",
            ),
            item(
                2,
                "UNDER_8_HOURS",
            ),
        ],
        dependencies=(
            DependencyEdge(
                1,
                2,
            ),
        ),
    )

    generated = (
        generate_flavour_schedule(
            p,
            "lock-in",
        )
    )

    prerequisite = (
        generated.plan
        .allocations_for(1)
    )

    dependent = (
        generated.plan
        .allocations_for(2)
    )

    assert min(
        row.scheduled_date
        for row in dependent
    ) > max(
        row.scheduled_date
        for row in prerequisite
    )


def test_anchor_controls_first_execution_date():
    anchor = TODAY + 3 * DAY

    p = problem([
        item(
            1,
            "UNDER_8_HOURS",
            anchor=anchor,
        ),
    ])

    generated = (
        generate_flavour_schedule(
            p,
            "monk",
        )
    )

    assert min(
        row.scheduled_date
        for row
        in generated.plan.allocations
    ) == anchor


def test_anchor_consumes_headroom_before_flexible_work():
    anchor = TODAY

    p = problem([
        item(
            1,
            "UNDER_4_HOURS",
            anchor=anchor,
        ),
        item(
            2,
            "UNDER_16_HOURS",
            due=TODAY + 10 * DAY,
        ),
        item(
            3,
            "UNDER_16_HOURS",
            due=TODAY + 10 * DAY,
        ),
    ])

    monk = generate_flavour_schedule(
        p,
        "monk",
    )

    today_rows = [
        row
        for row in monk.work_allocations
        if row.scheduled_date == TODAY
    ]

    assert any(
        row.item_id == 1
        and row.hours == Decimal("4")
        for row in today_rows
    )

    # The 4h anchor is scheduled before flexible work, so Monk should not
    # blindly allocate another full 6h of flexible work on top of it.
    assert (
        monk.daily_hours[TODAY]
        <= Decimal("8")
    )


def test_small_final_tail_is_absorbed_when_soft_headroom_allows():
    p = problem([
        item(
            1,
            "UNDER_16_HOURS",
            due=TODAY + 10 * DAY,
        ),
    ])

    lock_in = generate_flavour_schedule(
        p,
        "lock-in",
    )

    rows = [
        row
        for row in lock_in.work_allocations
        if row.item_id == 1
    ]

    assert all(
        row.hours >= Decimal("1")
        or row is rows[-1]
        for row in rows
    )

    # There should be no artificial sub-hour clean-up session if the previous
    # day had enough soft-max room to absorb it.
    assert not any(
        row.hours < Decimal("1")
        for row in rows
    )

def test_large_single_task_session_is_bounded_under_normal_conditions():

    p = problem([

        item(

            1,

            "OVER_16_HOURS",

            due=TODAY + 20 * DAY,

        ),

    ])

    lock_in = generate_flavour_schedule(

        p,

        "lock-in",

        explicit_total_hours={

            1: Decimal("24"),

        },

    )

    assert max(

        row.hours

        for row in lock_in.work_allocations

    ) <= Decimal("6")

def test_started_large_task_receives_meaningful_continuation_when_room_exists():

    p = problem([

        item(

            1,

            "UNDER_16_HOURS",

            due=TODAY + 10 * DAY,

        ),

        item(

            2,

            "UNDER_4_HOURS",

            anchor=TODAY,

        ),

    ])

    monk = generate_flavour_schedule(

        p,

        "monk",

        explicit_total_hours={

            1: Decimal("16"),

            2: Decimal("4"),

        },

    )

    rows = [

        row

        for row in monk.work_allocations

        if row.item_id == 1

    ]

    assert len(rows) >= 2

    # After the first constrained day, Monk should not repeatedly drip only

    # the absolute 1h minimum when ordinary headroom exists.

    assert any(

        row.hours >= Decimal("3")

        for row in rows[1:]

    )

