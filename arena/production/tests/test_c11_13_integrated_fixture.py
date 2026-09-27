from decimal import Decimal

import pytest

from arena.production.flavour_planner import (
    generate_flavour_schedule,
)
from arena.production.integrated_fixture import (
    build_c11_13_base_world,
)
from arena.production.production_improver import (
    ProductionImproveConfig,
    improve_production_schedule,
)
from arena.production.work_mass import (
    validate_dynamic_plan,
)


D = Decimal


@pytest.mark.parametrize(
    "flavour",
    ["lock-in", "monk"],
)
def test_c11_13_integrated_world_remains_hard_legal(
    flavour,
):
    world = build_c11_13_base_world()

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
            max_iterations=30,
            max_evaluations=3000,
        ),
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

    assert result.final_objective.late_hours == D("0")


@pytest.mark.parametrize(
    "flavour",
    ["lock-in", "monk"],
)
def test_c11_13_dependency_chains_preserve_completion_precedence(
    flavour,
):
    world = build_c11_13_base_world()

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
            max_iterations=20,
            max_evaluations=2000,
        ),
    )

    by_item = {}

    for row in result.final_schedule.work_allocations:
        by_item.setdefault(
            row.item_id,
            [],
        ).append(row)

    for prerequisite, dependent in (
        (1, 2),
        (2, 3),
        (4, 5),
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
def test_c11_13_release_and_anchor_semantics_survive_improvement(
    flavour,
):
    world = build_c11_13_base_world()

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
            max_iterations=20,
            max_evaluations=2000,
        ),
    )

    by_item = {}

    for row in result.final_schedule.work_allocations:
        by_item.setdefault(
            row.item_id,
            [],
        ).append(row)

    for item_id in (8, 9):
        item = world.problem.item_by_id[
            item_id
        ]

        assert all(
            row.scheduled_date
            >= item.release_date
            for row in by_item[item_id]
        )

    for item_id in (
        10,
        11,
        12,
        13,
    ):
        item = world.problem.item_by_id[
            item_id
        ]

        assert min(
            row.scheduled_date
            for row in by_item[item_id]
        ) == item.anchor_date


def test_c11_13_partial_progress_conserves_only_remaining_work():
    world = build_c11_13_base_world()

    schedule = generate_flavour_schedule(
        world.problem,
        "lock-in",
        explicit_total_hours=
            world.explicit_total_hours,
    )

    hours = sum(
        row.hours
        for row in schedule.work_allocations
        if row.item_id == 7
    )

    # 40% complete of a 20h task leaves 12h.
    assert hours == D("12")


def test_c11_13_world_contains_the_intended_scenario_mix():
    world = build_c11_13_base_world()

    assert len(world.problem.items) == 22
    assert len(world.problem.dependencies) == 3

    assert world.explicit_total_hours[16] == D("0.25")

    assert (
        world.problem.item_by_id[7].percent_completed
        == D("40")
    )

    assert (
        world.problem.item_by_id[20].percent_completed
        == D("50")
    )

    assert (
        world.problem.item_by_id[8].release_date
        is not None
    )

    assert (
        world.problem.item_by_id[10].anchor_date
        is not None
    )
