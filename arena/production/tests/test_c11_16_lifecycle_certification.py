from arena.production.decision_world import (
    build_c11_15_saturated_world,
)
from arena.production.lifecycle_certification import (
    build_lifecycle_world,
    lifecycle_steps,
    run_lifecycle_step,
)


def test_c11_16_lifecycle_grows_to_exact_frozen_c11_15_world_then_shrinks():
    steps = lifecycle_steps()

    grow = tuple(
        step
        for step in steps
        if step.phase == "grow"
    )

    shrink = tuple(
        step
        for step in steps
        if step.phase == "shrink"
    )

    assert grow[0].code == "G00"
    assert grow[-1].code == "G13"

    assert shrink[0].code == "S01"
    assert shrink[-1].code == "S13"

    for previous, current in zip(
        grow,
        grow[1:],
    ):
        assert (
            previous.item_ids
            < current.item_ids
        )

    for previous, current in zip(
        shrink,
        shrink[1:],
    ):
        assert (
            current.item_ids
            < previous.item_ids
        )

    master = (
        build_c11_15_saturated_world()
    )

    assert grow[-1].item_ids == {
        item.item_id
        for item
        in master.problem.items
    }

    assert shrink[-1].item_ids == (
        grow[0].item_ids
    )


def test_c11_16_every_step_is_a_valid_subset_of_frozen_master_world():
    master = (
        build_c11_15_saturated_world()
    )

    master_dependencies = set(
        master.problem.dependencies
    )

    for step in lifecycle_steps():
        world = build_lifecycle_world(
            step,
            master=master,
        )

        item_ids = {
            item.item_id
            for item
            in world.problem.items
        }

        assert item_ids == set(
            step.item_ids
        )

        assert set(
            world.explicit_total_hours
        ) == item_ids

        assert set(
            world.labels
        ) == item_ids

        assert set(
            world.problem.dependencies
        ) <= master_dependencies

        for edge in (
            world.problem.dependencies
        ):
            assert (
                edge.prerequisite_id
                in item_ids
            )

            assert (
                edge.dependent_id
                in item_ids
            )


def test_c11_16_maximum_complexity_step_matches_master_dependencies_and_hours():
    master = (
        build_c11_15_saturated_world()
    )

    max_step = tuple(
        step
        for step in lifecycle_steps()
        if step.phase == "grow"
    )[-1]

    world = build_lifecycle_world(
        max_step,
        master=master,
    )

    assert (
        world.problem.items
        == master.problem.items
    )

    assert (
        world.problem.dependencies
        == master.problem.dependencies
    )

    assert (
        world.explicit_total_hours
        == master.explicit_total_hours
    )

    assert (
        world.labels
        == master.labels
    )


def test_c11_16_first_grow_and_last_shrink_are_same_canonical_world():
    steps = lifecycle_steps()

    first = steps[0]
    last = steps[-1]

    first_world = build_lifecycle_world(
        first
    )

    last_world = build_lifecycle_world(
        last
    )

    assert (
        first_world.problem.items
        == last_world.problem.items
    )

    assert (
        first_world.problem.dependencies
        == last_world.problem.dependencies
    )

    assert (
        first_world.explicit_total_hours
        == last_world.explicit_total_hours
    )


def test_c11_16_small_baseline_executes_validly_for_both_flavours():
    first_step = lifecycle_steps()[0]

    for flavour in (
        "lock-in",
        "monk",
    ):
        run = run_lifecycle_step(
            first_step,
            flavour,
            max_iterations=5,
            max_evaluations=100,
        )

        assert (
            run.validation_violations
            == ()
        )

        assert (
            run.result.final_objective.key
            <= run.result.initial_objective.key
        )

        assert (
            run.delta.previous_step
            is None
        )

        assert (
            run.delta.added_item_ids
            == (18,)
        )



def test_c11_16_recreated_intermediate_world_returns_exact_same_schedule():
    steps = lifecycle_steps()

    grow = tuple(
        step
        for step in steps
        if step.phase == "grow"
    )

    shrink = tuple(
        step
        for step in steps
        if step.phase == "shrink"
    )

    # G04 and S09 represent the exact same canonical world:
    # anchors + releases + dependency chain + relaxed baseline pressure.
    original_step = grow[4]
    reverted_step = shrink[8]

    assert (
        original_step.item_ids
        == reverted_step.item_ids
    )

    for flavour in (
        "lock-in",
        "monk",
    ):
        original = run_lifecycle_step(
            original_step,
            flavour,
            max_iterations=15,
            max_evaluations=1000,
        )

        reverted = run_lifecycle_step(
            reverted_step,
            flavour,
            max_iterations=15,
            max_evaluations=1000,
        )

        assert (
            original.validation_violations
            == ()
        )

        assert (
            reverted.validation_violations
            == ()
        )

        assert (
            original.world.problem
            == reverted.world.problem
        )

        assert (
            original.world.explicit_total_hours
            == reverted.world.explicit_total_hours
        )

        assert (
            original.result.final_schedule
            == reverted.result.final_schedule
        )

        assert (
            original.result.final_objective
            == reverted.result.final_objective
        )
