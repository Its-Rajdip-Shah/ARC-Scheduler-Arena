from datetime import date, timedelta
from decimal import Decimal

from arena.algorithms.earliest_feasible import (
    EarliestFeasible,
)
from arena.scheduling.domain import (
    DependencyEdge,
    ScheduleItem,
    ScheduleProblem,
)
from arena.scheduling.validation import validate_plan


TODAY = date(2026, 1, 15)


CAPACITY = {
    "UNDER_20_MINUTES": 5,
    "UNDER_1_HOUR": 4,
    "UNDER_4_HOURS": 3,
    "UNDER_8_HOURS": 3,
    "UNDER_16_HOURS": 3,
    "OVER_16_HOURS": 3,
}


def item(
    item_id,
    *,
    duration="UNDER_1_HOUR",
    release=None,
    due=None,
    anchor=None,
    remaining="1",
    residual=False,
):
    return ScheduleItem(
        item_id=item_id,
        duration_category=duration,
        priority_position=None,
        release_date=release,
        due_date=due,
        anchor_date=anchor,
        percent_completed=(
            Decimal("100")
            - Decimal(remaining) * Decimal("100")
        ),
        remaining_fraction=Decimal(remaining),
        is_residual=residual,
    )


def problem(
    items,
    edges=(),
    *,
    capacity=None,
    overload_dates=frozenset(),
):
    return ScheduleProblem(
        today=TODAY,
        items=tuple(items),
        dependencies=tuple(
            DependencyEdge(a, b)
            for a, b in edges
        ),
        capacity_by_duration=(
            capacity or CAPACITY
        ),
        overload_dates=overload_dates,
    )


def solve(p):
    plan = EarliestFeasible().solve(p)
    return plan, validate_plan(p, plan)


def test_atomic_item_goes_today():
    p = problem([item(1)])

    plan, result = solve(p)

    assert result.is_valid
    assert len(plan.allocations) == 1
    assert plan.allocations[0].scheduled_date == TODAY
    assert plan.allocations[0].percentage == Decimal("100")


def test_release_date_is_hard_lower_bound():
    release = TODAY + timedelta(days=5)

    p = problem([
        item(
            1,
            release=release,
        )
    ])

    plan, result = solve(p)

    assert result.is_valid
    assert plan.allocations[0].scheduled_date == release


def test_dependency_chain_is_planned_across_future():
    p = problem(
        [
            item(1),
            item(2),
            item(3),
        ],
        [
            (1, 2),
            (2, 3),
        ],
    )

    plan, result = solve(p)

    assert result.is_valid

    dates = {
        allocation.item_id: allocation.scheduled_date
        for allocation in plan.allocations
    }

    assert dates[1] == TODAY
    assert dates[2] == TODAY + timedelta(days=1)
    assert dates[3] == TODAY + timedelta(days=2)


def test_fan_in_waits_for_every_prerequisite():
    p = problem(
        [
            item(1),
            item(
                2,
                release=TODAY + timedelta(days=3),
            ),
            item(3),
        ],
        [
            (1, 3),
            (2, 3),
        ],
    )

    plan, result = solve(p)

    assert result.is_valid

    dates = {
        allocation.item_id: allocation.scheduled_date
        for allocation in plan.allocations
    }

    assert dates[3] == TODAY + timedelta(days=4)


def test_capacity_pushes_atomic_work_forward():
    capacity = dict(CAPACITY)
    capacity["UNDER_1_HOUR"] = 1

    p = problem(
        [
            item(1),
            item(2),
            item(3),
        ],
        capacity=capacity,
    )

    plan, result = solve(p)

    assert result.is_valid

    assert [
        allocation.scheduled_date
        for allocation in plan.allocations
    ] == [
        TODAY,
        TODAY + timedelta(days=1),
        TODAY + timedelta(days=2),
    ]


def test_under_8_hour_item_uses_two_sessions():
    p = problem([
        item(
            1,
            duration="UNDER_8_HOURS",
        )
    ])

    plan, result = solve(p)

    assert result.is_valid

    rows = plan.allocations_for(1)

    assert len(rows) == 2
    assert sum(
        row.percentage
        for row in rows
    ) == Decimal("100")

    assert rows[0].scheduled_date == TODAY
    assert rows[1].scheduled_date == TODAY + timedelta(days=1)


def test_over_16_hour_item_uses_three_sessions():
    p = problem([
        item(
            1,
            duration="OVER_16_HOURS",
        )
    ])

    plan, result = solve(p)

    assert result.is_valid

    rows = plan.allocations_for(1)

    assert len(rows) == 3
    assert sum(
        row.percentage
        for row in rows
    ) == Decimal("100")


def test_partial_splittable_item_allocates_only_remaining_work():
    p = problem([
        item(
            1,
            duration="UNDER_16_HOURS",
            remaining="0.4",
        )
    ])

    plan, result = solve(p)

    assert result.is_valid

    assert sum(
        row.percentage
        for row in plan.allocations_for(1)
    ) == Decimal("40.0")


def test_dependent_waits_until_split_prerequisite_finishes():
    p = problem(
        [
            item(
                1,
                duration="UNDER_16_HOURS",
            ),
            item(2),
        ],
        [(1, 2)],
    )

    plan, result = solve(p)

    assert result.is_valid

    prerequisite = plan.allocations_for(1)
    dependent = plan.allocations_for(2)

    assert max(
        row.scheduled_date
        for row in prerequisite
    ) < min(
        row.scheduled_date
        for row in dependent
    )


def test_anchor_is_preserved():
    anchor = TODAY + timedelta(days=5)

    p = problem([
        item(
            1,
            anchor=anchor,
        )
    ])

    plan, result = solve(p)

    assert result.is_valid
    assert plan.allocations[0].scheduled_date == anchor


def test_no_capacity_before_deadline_uses_soft_overload():
    capacity = dict(CAPACITY)
    capacity["UNDER_1_HOUR"] = 1

    p = problem(
        [
            item(
                1,
                due=TODAY,
            ),
            item(
                2,
                due=TODAY,
            ),
        ],
        capacity=capacity,
    )

    plan = EarliestFeasible().solve(p)

    assert all(
        row.scheduled_date == TODAY
        for row in plan.allocations
    )

    assert any(
        "no_capacity_before_deadline"
        in conflict
        for conflict in plan.conflicts
    )


def test_deterministic():
    p = problem(
        [
            item(4),
            item(1),
            item(3),
            item(2),
        ],
        [
            (1, 3),
            (2, 4),
        ],
    )

    algorithm = EarliestFeasible()

    assert algorithm.solve(p) == algorithm.solve(p)


def test_tiny_fraction_historical_rounding_is_frozen():
    p = problem([item(1, duration="OVER_16_HOURS", remaining=".00016")])
    plan = EarliestFeasible().solve(p)
    assert tuple(row.percentage for row in plan.allocations) == (Decimal('.01'), Decimal('.01'))
    assert tuple(row.scheduled_date for row in plan.allocations) == (TODAY, TODAY + timedelta(days=1))
    assert plan.conflicts == ()
    assert plan.diagnostics == (("policy", "earliest-feasible"),)
