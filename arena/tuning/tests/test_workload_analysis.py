from pathlib import Path
from types import MappingProxyType

from arena.tuning.execution import (
    TuningCandidateSummary,
    TuningStudyResults,
    TuningTrialObservation,
)
from arena.tuning.workload_analysis import (
    analyze_workload_responses,
    summarize_workload_responses,
)


def _summary(candidate_id):
    return TuningCandidateSummary(
        candidate_id=candidate_id,
        objective_id='o',
        constructor_id='c',
        improver_id=candidate_id,
        intended_trials=2,
        ok_trials=2,
        timed_out_trials=0,
        failed_trials=0,
        ok_rate=1.0,
        timeout_rate=0.0,
        mean_worker_wall_seconds=1.0,
        performance_means=
            MappingProxyType({}),
        performance_observation_counts=
            MappingProxyType({}),
    )


def _obs(
    candidate_id,
    scenario_id,
    seed,
    a,
    b,
):
    return TuningTrialObservation(
        candidate_id=candidate_id,
        scenario_id=scenario_id,
        run_seed=seed,
        status='ok',
        worker_wall_seconds=1.0,
        performance=
            MappingProxyType({
                'a': a,
                'b': b,
            }),
    )


def test_scenario_local_pareto_and_summary():
    candidates = ('x', 'y', 'z')

    observations = []

    for seed in (1, 2):
        observations.extend([
            _obs(
                'x',
                'G001-R0',
                seed,
                0.0,
                3.0,
            ),
            _obs(
                'y',
                'G001-R0',
                seed,
                1.0,
                1.0,
            ),
            _obs(
                'z',
                'G001-R0',
                seed,
                3.0,
                3.0,
            ),
        ])

    results = TuningStudyResults(
        output_root=Path('x'),
        benchmark_manifest_sha256=
            'a' * 64,
        development_scenario_ids=(
            'G001-R0',
        ),
        holdout_scenario_ids=(
            'H',
        ),
        seeds=(1, 2),
        candidate_summaries=tuple(
            _summary(candidate_id)
            for candidate_id
            in candidates
        ),
        trial_observations=
            tuple(observations),
        expected_trials=6,
        completed_trials=6,
    )

    responses = analyze_workload_responses(
        results,
        candidate_ids=candidates,
        active_metrics=('a', 'b'),
    )

    assert (
        responses[0]
        .pareto_candidate_ids
        == ('x', 'y')
    )

    summary = summarize_workload_responses(
        responses,
        candidate_ids=candidates,
        labels={
            'x': 'X',
            'y': 'Y',
            'z': 'Z',
        },
        features_by_scenario={
            'G001-R0': {
                'size': 10,
            },
        },
        metadata_by_scenario={
            'G001-R0': {
                'design': 'one',
            },
        },
        active_metrics=('a', 'b'),
    )

    assert (
        summary[
            'scorable_scenario_count'
        ]
        == 1
    )

    counts = {
        row['candidate_id']:
            row[
                'pareto_scenario_count'
            ]
        for row in summary[
            'candidates'
        ]
    }

    assert counts == {
        'x': 1,
        'y': 1,
        'z': 0,
    }


def test_common_mode_timeout_is_coverage_gap():
    candidates = ('x', 'y')

    observations = tuple(
        TuningTrialObservation(
            candidate_id=candidate_id,
            scenario_id='G016-R0',
            run_seed=seed,
            status='wall_timeout',
            worker_wall_seconds=45.0,
            performance=None,
        )
        for candidate_id in candidates
        for seed in (1, 2)
    )

    results = TuningStudyResults(
        output_root=Path('x'),
        benchmark_manifest_sha256=
            'a' * 64,
        development_scenario_ids=(
            'G016-R0',
        ),
        holdout_scenario_ids=('H',),
        seeds=(1, 2),
        candidate_summaries=(
            _summary('x'),
            _summary('y'),
        ),
        trial_observations=observations,
        expected_trials=4,
        completed_trials=4,
    )

    responses = analyze_workload_responses(
        results,
        candidate_ids=candidates,
        active_metrics=('a',),
    )

    assert (
        responses[0].status
        == 'common_mode_timeout'
    )


def test_scenario_uses_only_metrics_common_to_all_cells():
    candidates = ('x', 'y')

    observations = (
        TuningTrialObservation(
            candidate_id='x',
            scenario_id='G001-R0',
            run_seed=1,
            status='ok',
            worker_wall_seconds=1.0,
            performance=MappingProxyType({
                'a': 0.0,
                'b': 10.0,
            }),
        ),
        TuningTrialObservation(
            candidate_id='x',
            scenario_id='G001-R0',
            run_seed=2,
            status='ok',
            worker_wall_seconds=1.0,
            performance=MappingProxyType({
                'a': 0.0,
            }),
        ),
        TuningTrialObservation(
            candidate_id='y',
            scenario_id='G001-R0',
            run_seed=1,
            status='ok',
            worker_wall_seconds=1.0,
            performance=MappingProxyType({
                'a': 1.0,
                'b': 0.0,
            }),
        ),
        TuningTrialObservation(
            candidate_id='y',
            scenario_id='G001-R0',
            run_seed=2,
            status='ok',
            worker_wall_seconds=1.0,
            performance=MappingProxyType({
                'a': 1.0,
                'b': 0.0,
            }),
        ),
    )

    results = TuningStudyResults(
        output_root=Path('x'),
        benchmark_manifest_sha256='a' * 64,
        development_scenario_ids=('G001-R0',),
        holdout_scenario_ids=('H',),
        seeds=(1, 2),
        candidate_summaries=(
            _summary('x'),
            _summary('y'),
        ),
        trial_observations=observations,
        expected_trials=4,
        completed_trials=4,
    )

    responses = analyze_workload_responses(
        results,
        candidate_ids=candidates,
        active_metrics=('a', 'b'),
    )

    assert responses[0].active_metrics == ('a',)
    assert responses[0].pareto_candidate_ids == ('x',)
    assert set(
        responses[0].metric_leaders
    ) == {'a'}


def test_summary_uses_each_scenarios_local_metric_set():
    candidates = ('x', 'y')

    observations = (
        TuningTrialObservation(
            candidate_id='x',
            scenario_id='G001-R0',
            run_seed=1,
            status='ok',
            worker_wall_seconds=1.0,
            performance=MappingProxyType({
                'a': 0.0,
                'b': 10.0,
            }),
        ),
        TuningTrialObservation(
            candidate_id='x',
            scenario_id='G001-R0',
            run_seed=2,
            status='ok',
            worker_wall_seconds=1.0,
            performance=MappingProxyType({
                'a': 0.0,
            }),
        ),
        TuningTrialObservation(
            candidate_id='y',
            scenario_id='G001-R0',
            run_seed=1,
            status='ok',
            worker_wall_seconds=1.0,
            performance=MappingProxyType({
                'a': 1.0,
                'b': 0.0,
            }),
        ),
        TuningTrialObservation(
            candidate_id='y',
            scenario_id='G001-R0',
            run_seed=2,
            status='ok',
            worker_wall_seconds=1.0,
            performance=MappingProxyType({
                'a': 1.0,
                'b': 0.0,
            }),
        ),
    )

    results = TuningStudyResults(
        output_root=Path('x'),
        benchmark_manifest_sha256='a' * 64,
        development_scenario_ids=('G001-R0',),
        holdout_scenario_ids=('H',),
        seeds=(1, 2),
        candidate_summaries=(
            _summary('x'),
            _summary('y'),
        ),
        trial_observations=observations,
        expected_trials=4,
        completed_trials=4,
    )

    responses = analyze_workload_responses(
        results,
        candidate_ids=candidates,
        active_metrics=('a', 'b'),
    )

    summary = summarize_workload_responses(
        responses,
        candidate_ids=candidates,
        labels={
            'x': 'X',
            'y': 'Y',
        },
        features_by_scenario={
            'G001-R0': {
                'size': 10,
            },
        },
        metadata_by_scenario={
            'G001-R0': {},
        },
        active_metrics=('a', 'b'),
    )

    rows = {
        row['candidate_id']: row
        for row in summary['candidates']
    }

    assert (
        responses[0].active_metrics
        == ('a',)
    )

    assert (
        rows['x'][
            'pairwise_dominance_counts'
        ]['y']
        == 1
    )

    assert (
        rows['y'][
            'pairwise_dominance_counts'
        ]['x']
        == 0
    )
