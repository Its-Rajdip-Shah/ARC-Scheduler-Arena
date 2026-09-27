from arena.production.flavour_planner import (
    generate_flavour_schedule,
)
from arena.production.validation_suite import (
    validation_scenarios,
)
from arena.production.work_mass import (
    validate_dynamic_plan,
)


def test_validation_suite_has_expected_scenario_diversity():
    scenarios = validation_scenarios()

    assert len(scenarios) == 7

    assert {
        row.scenario_id
        for row in scenarios
    } == {
        "open_parallel_work",
        "anchor_pressure",
        "dependency_chain",
        "deadline_compression",
        "staggered_releases",
        "partial_progress",
        "single_large_task",
    }


def test_both_flavours_are_hard_valid_on_all_validation_scenarios():
    for scenario in validation_scenarios():
        for flavour in (
            "lock-in",
            "monk",
        ):
            generated = (
                generate_flavour_schedule(
                    scenario.problem,
                    flavour,
                    explicit_total_hours=
                        scenario.explicit_total_hours,
                )
            )

            validation = (
                validate_dynamic_plan(
                    scenario.problem,
                    generated.plan,
                )
            )

            assert (
                validation.violations
                == ()
            ), (
                scenario.scenario_id,
                flavour,
                validation.violations,
            )


def test_single_large_task_preserves_expected_flavour_shape():
    scenario = next(
        row
        for row in validation_scenarios()
        if row.scenario_id
        == "single_large_task"
    )

    lock_in = generate_flavour_schedule(
        scenario.problem,
        "lock-in",
        explicit_total_hours=
            scenario.explicit_total_hours,
    )

    monk = generate_flavour_schedule(
        scenario.problem,
        "monk",
        explicit_total_hours=
            scenario.explicit_total_hours,
    )

    assert max(
        row.hours
        for row in lock_in.work_allocations
    ) <= 6

    assert max(
        row.hours
        for row in monk.work_allocations
    ) <= 5

    assert max(
        row.scheduled_date
        for row in lock_in.work_allocations
    ) <= max(
        row.scheduled_date
        for row in monk.work_allocations
    )
