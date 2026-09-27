from decimal import Decimal
from functools import lru_cache

import pytest

from arena.production.decision_world import (
    TODAY,
    build_c11_15_saturated_world,
)
from arena.production.flavour_planner import (
    generate_flavour_schedule,
)
from arena.production.load_status import (
    LoadStatus,
)
from arena.production.production_improver import (
    ProductionImproveConfig,
    improve_production_schedule,
)
from arena.production.work_mass import (
    validate_dynamic_plan,
)


D = Decimal


@lru_cache(maxsize=None)
def _result(
    flavour,
    *,
    iterations=120,
    evaluations=12000,
):
    """Return the deterministic saturated-world production result.

    C11.15.2 established 12,000 evaluations as the current saturated-world
    acceptance budget. The old 3,000-evaluation helper measured an unfinished
    intermediate search state and could therefore fail behavioural assertions
    that the accepted production run satisfies.

    Results are cached because every test for a given flavour/configuration
    evaluates the same deterministic world. Regression tests should inspect
    one production result repeatedly rather than rerunning the optimiser for
    every assertion.
    """

    world = build_c11_15_saturated_world()

    initial = generate_flavour_schedule(
        world.problem,
        flavour,
        explicit_total_hours=
            world.explicit_total_hours,
    )

    result = improve_production_schedule(
        world.problem,
        initial,
        ProductionImproveConfig(
            max_iterations=iterations,
            max_evaluations=evaluations,
        ),
    )

    return (
        world,
        result,
    )


def _rows_by_item(
    schedule,
):
    result = {}

    for row in schedule.work_allocations:
        result.setdefault(
            row.item_id,
            [],
        ).append(row)

    for rows in result.values():
        rows.sort(
            key=lambda row:
                row.scheduled_date
        )

    return result


@pytest.mark.parametrize(
    "flavour",
    ["lock-in", "monk"],
)
def test_c11_15_saturated_world_is_structurally_valid(
    flavour,
):
    world, result = _result(
        flavour,
    )

    validation = validate_dynamic_plan(
        world.problem,
        result.final_schedule.plan,
    )

    assert validation.violations == ()

    assert (
        result.final_objective.key
        <= result.initial_objective.key
    )


@pytest.mark.parametrize(
    "flavour",
    ["lock-in", "monk"],
)
def test_c11_15_dependency_structures_preserve_completion_precedence(
    flavour,
):
    world, result = _result(
        flavour,
    )

    by_item = _rows_by_item(
        result.final_schedule
    )

    for prerequisite, dependent in (
        (1, 2),
        (2, 3),
        (25, 27),
        (26, 27),
        (27, 28),
        (29, 30),
        (29, 31),
    ):
        prerequisite_completion = max(
            row.scheduled_date
            for row in by_item[
                prerequisite
            ]
        )

        dependent_start = min(
            row.scheduled_date
            for row in by_item[
                dependent
            ]
        )

        assert (
            prerequisite_completion
            < dependent_start
        )


@pytest.mark.parametrize(
    "flavour",
    ["lock-in", "monk"],
)
def test_c11_15_anchor_wall_and_future_release_semantics(
    flavour,
):
    world, result = _result(
        flavour,
    )

    by_item = _rows_by_item(
        result.final_schedule
    )

    for item_id in (
        32,
        33,
        34,
        35,
    ):
        assert (
            by_item[item_id][0].scheduled_date
            == TODAY + 8
            * __import__("datetime").timedelta(days=1)
        )

    for item_id in (
        36,
        37,
        38,
        39,
    ):
        assert (
            by_item[item_id][0].scheduled_date
            == TODAY + 9
            * __import__("datetime").timedelta(days=1)
        )

    item_40 = world.problem.item_by_id[
        40
    ]

    assert all(
        row.scheduled_date
        >= item_40.release_date
        for row in by_item[40]
    )


@pytest.mark.parametrize(
    "flavour",
    ["lock-in", "monk"],
)
def test_c11_15_partial_progress_conserves_remaining_hours(
    flavour,
):
    world, result = _result(
        flavour,
    )

    by_item = _rows_by_item(
        result.final_schedule
    )

    expected_remaining = {
        7: D("12"),
        20: D("12"),
        42: D("8"),
    }

    for item_id, expected in (
        expected_remaining.items()
    ):
        actual = sum(
            (
                row.hours
                for row
                in by_item[item_id]
            ),
            D("0"),
        )

        assert actual == expected


@pytest.mark.parametrize(
    "flavour",
    ["lock-in", "monk"],
)
def test_c11_15_comparable_priority_pairs_respect_higher_priority(
    flavour,
):
    _, result = _result(
        flavour,
    )

    by_item = _rows_by_item(
        result.final_schedule
    )

    high_start = min(
        row.scheduled_date
        for row in by_item[23]
    )

    low_start = min(
        row.scheduled_date
        for row in by_item[24]
    )

    assert high_start <= low_start

    equal_due_high = min(
        row.scheduled_date
        for row in by_item[44]
    )

    equal_due_low = min(
        row.scheduled_date
        for row in by_item[45]
    )

    assert (
        equal_due_high
        <= equal_due_low
    )


@pytest.mark.parametrize(
    "flavour",
    ["lock-in", "monk"],
)
def test_c11_15_impossible_due_today_work_is_not_hidden_as_lateness(
    flavour,
):
    _, result = _result(
        flavour,
        iterations=10,
        evaluations=1000,
    )

    by_item = _rows_by_item(
        result.final_schedule
    )

    assert all(
        row.scheduled_date == TODAY
        for row in by_item[46]
    )

    assert sum(
        (
            row.hours
            for row in by_item[46]
        ),
        D("0"),
    ) == D("25")

    assert (
        result.final_schedule.daily_status[
            TODAY
        ]
        == LoadStatus.INFEASIBLE
    )


@pytest.mark.parametrize(
    "flavour",
    ["lock-in", "monk"],
)
def test_c11_15_atomic_tasks_remain_single_allocations(
    flavour,
):
    _, result = _result(
        flavour,
    )

    by_item = _rows_by_item(
        result.final_schedule
    )

    for item_id in (
        14,
        16,
        17,
        32,
        33,
        34,
        35,
        36,
        37,
        38,
        39,
    ):
        assert len(
            by_item[item_id]
        ) == 1


def test_c11_15_world_declares_explicit_decision_coverage():
    world = build_c11_15_saturated_world()

    assert len(
        world.problem.items
    ) == 46

    assert len(
        world.cases
    ) == 18

    assert {
        case.code
        for case in world.cases
    } == {
        f"D{index:02d}"
        for index in range(
            1,
            19,
        )
    }

    assert (
        world.explicit_total_hours[46]
        == D("25")
    )
