from pathlib import Path
from types import MappingProxyType

from arena.tuning.design import build_c7_calibration_spec
from arena.tuning.execution import (
    TuningCandidateSummary,
    TuningStudyResults,
    TuningTrialObservation,
)
from arena.tuning.racing import RacingRoundSpec
from arena.tuning.racing_campaign import RacingRoundPlan
from arena.tuning.racing_execution import (
    build_incremental_tuning_plan,
    merge_cumulative_tuning_results,
)
from arena.tuning.selection import C7_V1_SELECTION_POLICY
from arena.tuning.study import plan_tuning_study


def _summary(candidate_id, intended):
    return TuningCandidateSummary(
        candidate_id=candidate_id,
        objective_id='objective',
        constructor_id='constructor',
        improver_id=candidate_id,
        intended_trials=intended,
        ok_trials=intended,
        timed_out_trials=0,
        failed_trials=0,
        ok_rate=1.0,
        timeout_rate=0.0,
        mean_worker_wall_seconds=1.0,
        performance_means=MappingProxyType({
            'deadline_miss_rate': 0.1,
        }),
        performance_observation_counts=
            MappingProxyType({
                'deadline_miss_rate': intended,
            }),
    )


def _observation(candidate_id, scenario_id, value):
    return TuningTrialObservation(
        candidate_id=candidate_id,
        scenario_id=scenario_id,
        run_seed=1701,
        status='ok',
        worker_wall_seconds=1.0,
        performance=MappingProxyType({
            'hard_violation_count': 0.0,
            'canonical_infeasibility_count': 0.0,
            'deadline_miss_rate': value,
        }),
    )


def _results(candidate_ids, scenarios, base):
    observations = tuple(
        _observation(
            candidate_id,
            scenario_id,
            base + candidate_index / 100,
        )
        for candidate_index, candidate_id
        in enumerate(candidate_ids)
        for scenario_id in scenarios
    )

    return TuningStudyResults(
        output_root=Path('evidence'),
        benchmark_manifest_sha256='a' * 64,
        development_scenario_ids=scenarios,
        holdout_scenario_ids=('H1',),
        seeds=(1701,),
        candidate_summaries=tuple(
            _summary(
                candidate_id,
                len(scenarios),
            )
            for candidate_id in candidate_ids
        ),
        trial_observations=observations,
        expected_trials=len(observations),
        completed_trials=len(observations),
    )


def test_incremental_plan_covers_exact_survivor_cells(tmp_path):
    full = plan_tuning_study(
        build_c7_calibration_spec(
            tmp_path / 'unused-full-plan'
        )
    )

    incoming = tuple(
        candidate.candidate_id
        for candidate in full.candidates[:10]
    )

    decision_spec = RacingRoundSpec(
        round_index=1,
        expected_candidate_ids=incoming,
        target_survivor_count=5,
        selection_policy=C7_V1_SELECTION_POLICY,
    )

    round_plan = RacingRoundPlan(
        campaign_id='test',
        round_index=1,
        scenario_ids=full.development_scenario_ids[:4],
        incremental_scenario_ids=
            full.development_scenario_ids[:4],
        seeds=full.spec.seeds,
        incoming_candidate_ids=incoming,
        target_survivor_count=5,
        expected_trials=40,
        incremental_expected_trials=40,
        decision_spec=decision_spec,
    )

    executable = build_incremental_tuning_plan(
        full,
        round_plan,
        tmp_path / 'round1',
    )

    assert tuple(
        candidate.candidate_id
        for candidate in executable.candidates
    ) == incoming

    assert executable.development_scenario_ids == (
        full.development_scenario_ids[:4]
    )

    assert executable.expected_trials == 40

    represented = sum(
        len(run.scenario_ids)
        * len(run.constructors)
        * len(run.improvers)
        * len(run.seeds)
        for run in executable.run_configs
    )

    assert represented == 40

    assert all(
        len(run.constructors) == 1
        for run in executable.run_configs
    )


def test_cumulative_merge_filters_eliminated_candidates():
    previous = _results(
        ('a', 'b', 'c'),
        ('S1', 'S2'),
        0.1,
    )

    incremental = _results(
        ('a', 'c'),
        ('S3', 'S4'),
        0.2,
    )

    merged = merge_cumulative_tuning_results(
        previous,
        incremental,
        incoming_candidate_ids=('a', 'c'),
        cumulative_scenario_ids=(
            'S1',
            'S2',
            'S3',
            'S4',
        ),
    )

    assert tuple(
        summary.candidate_id
        for summary in merged.candidate_summaries
    ) == ('a', 'c')

    assert merged.development_scenario_ids == (
        'S1',
        'S2',
        'S3',
        'S4',
    )

    assert merged.expected_trials == 8
    assert merged.completed_trials == 8

    assert {
        observation.candidate_id
        for observation in merged.trial_observations
    } == {'a', 'c'}

    assert all(
        summary.intended_trials == 4
        for summary in merged.candidate_summaries
    )


def test_first_round_merge_is_incremental_matrix_itself():
    incremental = _results(
        ('a', 'b'),
        ('S1', 'S2'),
        0.1,
    )

    merged = merge_cumulative_tuning_results(
        None,
        incremental,
        incoming_candidate_ids=('a', 'b'),
        cumulative_scenario_ids=('S1', 'S2'),
    )

    assert merged.expected_trials == 4
    assert merged.development_scenario_ids == (
        'S1',
        'S2',
    )

    assert tuple(
        summary.candidate_id
        for summary in merged.candidate_summaries
    ) == ('a', 'b')


def test_subset_tuning_results_reuses_complete_quality_matrix():
    source = _results(
        ('a', 'b', 'c'),
        ('S1', 'S2', 'S3', 'S4'),
        0.1,
    )

    from arena.tuning.racing_execution import subset_tuning_results

    subset = subset_tuning_results(
        source,
        candidate_ids=('a', 'c'),
        scenario_ids=('S1', 'S2'),
    )

    assert subset.development_scenario_ids == ('S1', 'S2')

    assert tuple(
        summary.candidate_id
        for summary in subset.candidate_summaries
    ) == ('a', 'c')

    assert subset.expected_trials == 4
    assert subset.completed_trials == 4

    assert {
        observation.candidate_id
        for observation in subset.trial_observations
    } == {'a', 'c'}

    assert {
        observation.scenario_id
        for observation in subset.trial_observations
    } == {'S1', 'S2'}

    assert all(
        summary.intended_trials == 2
        for summary in subset.candidate_summaries
    )
