from arena.tuning.design import (
    C7_CALIBRATION_CANDIDATE_COUNT,
    C7_CALIBRATION_EXPECTED_TRIALS,
    C7_V1_DEVELOPMENT_DESIGN_COUNT,
    build_c7_calibration_spec,
)
from arena.tuning.study import plan_tuning_study


def test_calibration_design_has_fixed_bounded_full_development_matrix(
    tmp_path,
):
    plan = plan_tuning_study(
        build_c7_calibration_spec(
            tmp_path / 'calibration',
        )
    )

    assert C7_V1_DEVELOPMENT_DESIGN_COUNT == 47
    assert len(plan.development_scenario_ids) == 94
    assert len(plan.holdout_scenario_ids) == 24

    assert set(plan.development_scenario_ids).isdisjoint(
        plan.holdout_scenario_ids
    )

    assert len(plan.candidates) == C7_CALIBRATION_CANDIDATE_COUNT
    assert len(plan.candidates) == 32

    assert plan.expected_trials == C7_CALIBRATION_EXPECTED_TRIALS
    assert plan.expected_trials == 3008

    assert len(plan.run_configs) == 1

    run = plan.run_configs[0]
    assert len(run.constructors) == 4
    assert len(run.improvers) == 8
    assert len(run.seeds) == 1
    assert run.scenario_ids == plan.development_scenario_ids


def test_calibration_candidate_identity_is_output_path_independent(
    tmp_path,
):
    first = plan_tuning_study(
        build_c7_calibration_spec(
            tmp_path / 'first',
        )
    )

    second = plan_tuning_study(
        build_c7_calibration_spec(
            tmp_path / 'second',
        )
    )

    assert tuple(
        candidate.candidate_id
        for candidate in first.candidates
    ) == tuple(
        candidate.candidate_id
        for candidate in second.candidates
    )


def test_budget_probe_expands_wall_budget_without_using_holdout(
    tmp_path,
):
    from arena.tuning.design import (
        C7_BUDGET_PROBE_CANDIDATE_COUNT,
        C7_BUDGET_PROBE_EXPECTED_TRIALS,
        C7_BUDGET_PROBE_TRIAL_WALL_SECONDS,
        build_c7_budget_probe_spec,
    )

    plan = plan_tuning_study(
        build_c7_budget_probe_spec(
            tmp_path / 'budget_probe',
        )
    )

    assert C7_BUDGET_PROBE_TRIAL_WALL_SECONDS == 15.0
    assert len(plan.development_scenario_ids) == 94
    assert len(plan.holdout_scenario_ids) == 24
    assert set(plan.development_scenario_ids).isdisjoint(
        plan.holdout_scenario_ids
    )

    assert len(plan.candidates) == C7_BUDGET_PROBE_CANDIDATE_COUNT
    assert len(plan.candidates) == 12

    assert plan.expected_trials == C7_BUDGET_PROBE_EXPECTED_TRIALS
    assert plan.expected_trials == 1128

    run = plan.run_configs[0]

    assert len(run.constructors) == 4
    assert tuple(
        arm.arm_id.split('_', 1)[0]
        for arm in run.improvers
    ) == (
        'none',
        'sa80',
        'sa160',
    )
