from arena.production.acceptance import (
    FlavourParameters,
    evaluate_parameters,
    parameter_grid,
    satisfies_flavour,
)


def test_parameter_grid_is_small_and_deterministic():
    first = parameter_grid()
    second = parameter_grid()

    assert first == second

    assert len(first) == (
        4 * 4 * 4 * 4 * 5 * 3
    )


def test_common_contract_can_be_satisfied():
    parameters = FlavourParameters(
        timing_weight=0,
        continuity_weight=4,
        avoidable_idle_weight=1,
        same_day_repeat_weight=4,
        concentration_weight=2,
        concentration_free_sessions=3,
    )

    common = evaluate_parameters(
        "lock-in",
        parameters,
    )[:2]

    assert all(
        row.passes
        for row in common
    )


def test_grid_contains_lock_in_solutions():
    accepted = [
        row
        for row in parameter_grid()
        if satisfies_flavour(
            "lock-in",
            row,
        )
    ]

    assert accepted


def test_grid_contains_monk_solutions():
    accepted = [
        row
        for row in parameter_grid()
        if satisfies_flavour(
            "monk",
            row,
        )
    ]

    assert accepted


def test_one_parameterization_cannot_pass_opposite_tradeoff_when_identical():
    for row in parameter_grid():
        lock_results = {
            result.case_id:
                result
            for result
            in evaluate_parameters(
                "lock-in",
                row,
            )
        }

        monk_results = {
            result.case_id:
                result
            for result
            in evaluate_parameters(
                "monk",
                row,
            )
        }

        if (
            lock_results[
                "lock_in_prefers_earlier_progress"
            ].passes
        ):
            assert not (
                monk_results[
                    "monk_prefers_smooth_over_earliest"
                ].passes
            )
