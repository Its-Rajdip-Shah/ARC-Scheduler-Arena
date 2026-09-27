from pathlib import Path
from types import MappingProxyType

from arena.tuning.execution import (
    TuningCandidateSummary,
    TuningStudyResults,
    TuningTrialObservation,
)
from arena.tuning.selection import (
    MetricDirection,
    ParetoSelectionResult,
    SelectionMetric,
    SelectionPolicy,
)
from arena.tuning.shortlist import (
    build_metric_witness_shortlist,
    shortlist_artifact,
)


def _summary(candidate_id):
    return TuningCandidateSummary(
        candidate_id=candidate_id,
        objective_id='objective',
        constructor_id='constructor',
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


def _observation(
    candidate_id,
    scenario_id,
    deadline,
    lateness,
):
    return TuningTrialObservation(
        candidate_id=candidate_id,
        scenario_id=scenario_id,
        run_seed=1,
        status='ok',
        worker_wall_seconds=1.0,
        performance=MappingProxyType({
            'deadline_miss_rate':
                deadline,
            'mean_lateness_days':
                lateness,
        }),
    )


def _fixture():
    ids = ('a', 'b', 'c')

    results = TuningStudyResults(
        output_root=Path('evidence'),
        benchmark_manifest_sha256=
            'a' * 64,
        development_scenario_ids=(
            'S1',
            'S2',
        ),
        holdout_scenario_ids=('H1',),
        seeds=(1,),
        candidate_summaries=tuple(
            _summary(candidate_id)
            for candidate_id in ids
        ),
        trial_observations=(
            _observation(
                'a', 'S1',
                0.1, 5.0,
            ),
            _observation(
                'a', 'S2',
                0.1, 5.0,
            ),
            _observation(
                'b', 'S1',
                0.5, 1.0,
            ),
            _observation(
                'b', 'S2',
                0.5, 1.0,
            ),
            _observation(
                'c', 'S1',
                0.3, 3.0,
            ),
            _observation(
                'c', 'S2',
                0.3, 3.0,
            ),
        ),
        expected_trials=6,
        completed_trials=6,
    )

    policy = SelectionPolicy(
        metrics=(
            SelectionMetric(
                'deadline_miss_rate',
                MetricDirection.MINIMIZE,
            ),
            SelectionMetric(
                'mean_lateness_days',
                MetricDirection.MINIMIZE,
            ),
        )
    )

    selection = ParetoSelectionResult(
        policy=policy,
        eligible_candidate_ids=ids,
        excluded_candidates=
            MappingProxyType({}),
        structurally_unscorable_cells=(),
        externally_proven_structural_cells=(),
        unresolved_cells=(),
        paired_quality_cells=(
            ('S1', 1),
            ('S2', 1),
        ),
        active_metrics=policy.metrics,
        inactive_metrics=(),
        metric_observation_counts=
            MappingProxyType({
                'deadline_miss_rate': 2,
                'mean_lateness_days': 2,
            }),
        pareto_candidate_ids=ids,
    )

    return results, selection, ids


def test_metric_witness_shortlist_has_no_compromise_ranking():
    results, selection, ids = (
        _fixture()
    )

    shortlist = (
        build_metric_witness_shortlist(
            results,
            selection,
            expected_candidate_ids=ids,
        )
    )

    assert (
        shortlist
        .shortlisted_candidate_ids
        == ('a', 'b')
    )

    assert tuple(
        witness.metric_name
        for witness
        in shortlist.metric_witnesses
    ) == (
        'deadline_miss_rate',
        'mean_lateness_days',
    )

    assert (
        shortlist.metric_witnesses[
            0
        ].candidate_ids
        == ('a',)
    )

    assert (
        shortlist.metric_witnesses[
            1
        ].candidate_ids
        == ('b',)
    )


def test_metric_witness_shortlist_preserves_exact_ties():
    results, selection, ids = (
        _fixture()
    )

    observations = list(
        results.trial_observations
    )

    observations[4] = _observation(
        'c', 'S1',
        0.1, 3.0,
    )

    observations[5] = _observation(
        'c', 'S2',
        0.1, 3.0,
    )

    tied = TuningStudyResults(
        output_root=
            results.output_root,
        benchmark_manifest_sha256=
            results
            .benchmark_manifest_sha256,
        development_scenario_ids=
            results
            .development_scenario_ids,
        holdout_scenario_ids=
            results
            .holdout_scenario_ids,
        seeds=results.seeds,
        candidate_summaries=
            results.candidate_summaries,
        trial_observations=
            tuple(observations),
        expected_trials=
            results.expected_trials,
        completed_trials=
            results.completed_trials,
    )

    shortlist = (
        build_metric_witness_shortlist(
            tied,
            selection,
            expected_candidate_ids=ids,
        )
    )

    assert (
        shortlist.metric_witnesses[
            0
        ].candidate_ids
        == ('a', 'c')
    )

    assert (
        shortlist
        .shortlisted_candidate_ids
        == ('a', 'b', 'c')
    )


def test_shortlist_artifact_declares_no_scalar_rule():
    results, selection, ids = (
        _fixture()
    )

    shortlist = (
        build_metric_witness_shortlist(
            results,
            selection,
            expected_candidate_ids=ids,
        )
    )

    artifact = shortlist_artifact(
        shortlist,
        candidate_labels={
            'a': 'A',
            'b': 'B',
            'c': 'C',
        },
    )

    assert (
        artifact[
            'scalar_ranking_used'
        ]
        is False
    )

    assert (
        artifact['epsilon_used']
        is False
    )

    assert (
        artifact[
            'shortlist_candidate_count'
        ]
        == 2
    )
