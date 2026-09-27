from pathlib import Path
from types import MappingProxyType

import pytest

from arena.tuning.execution import (
    TuningCandidateSummary,
    TuningStudyResults,
    TuningTrialObservation,
)
from arena.tuning.selection import (
    MetricDirection,
    SelectionMetric,
    SelectionPolicy,
    select_pareto_candidates,
)


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
        performance_means=MappingProxyType({}),
        performance_observation_counts=MappingProxyType({}),
    )


def _observation(
    candidate_id,
    scenario_id,
    *,
    status='ok',
    deadline=None,
    priority=None,
):
    performance = None

    if status == 'ok':
        values = {
            'hard_violation_count': 0.0,
            'canonical_infeasibility_count': 0.0,
        }

        if deadline is not None:
            values['deadline_miss_rate'] = deadline

        if priority is not None:
            values['priority_inversion_rate'] = priority

        performance = MappingProxyType(values)

    return TuningTrialObservation(
        candidate_id=candidate_id,
        scenario_id=scenario_id,
        run_seed=1,
        status=status,
        worker_wall_seconds=1.0,
        performance=performance,
    )


def _results(observations, scenarios=('S1', 'S2')):
    ids = []
    for observation in observations:
        if observation.candidate_id not in ids:
            ids.append(observation.candidate_id)

    return TuningStudyResults(
        output_root=Path('study'),
        benchmark_manifest_sha256='a' * 64,
        development_scenario_ids=scenarios,
        holdout_scenario_ids=('H',),
        seeds=(1,),
        candidate_summaries=tuple(
            _summary(candidate_id, len(scenarios))
            for candidate_id in ids
        ),
        trial_observations=tuple(observations),
        expected_trials=len(observations),
        completed_trials=len(observations),
    )


def _policy(**kwargs):
    return SelectionPolicy(
        metrics=(
            SelectionMetric(
                'deadline_miss_rate',
                MetricDirection.MINIMIZE,
            ),
            SelectionMetric(
                'priority_inversion_rate',
                MetricDirection.MINIMIZE,
            ),
        ),
        **kwargs,
    )


def test_structural_cell_is_reported_not_used_to_eliminate_everyone():
    results = _results((
        _observation(
            'a',
            'S1',
            deadline=0.1,
            priority=0.2,
        ),
        _observation(
            'b',
            'S1',
            deadline=0.2,
            priority=0.3,
        ),
        _observation(
            'a',
            'S2',
            status='constructor_invalid',
        ),
        _observation(
            'b',
            'S2',
            status='constructor_invalid',
        ),
    ))

    selection = select_pareto_candidates(
        results,
        _policy(),
    )

    assert selection.structurally_unscorable_cells == (
        ('S2', 1),
    )
    assert selection.unresolved_cells == ()
    assert selection.paired_quality_cells == (
        ('S1', 1),
    )
    assert selection.eligible_candidate_ids == (
        'a',
        'b',
    )
    assert selection.pareto_candidate_ids == ('a',)


def test_all_timeout_cell_is_unresolved_and_selection_refuses_to_clip():
    results = _results((
        _observation(
            'a',
            'S1',
            deadline=0.1,
            priority=0.2,
        ),
        _observation(
            'b',
            'S1',
            deadline=0.2,
            priority=0.3,
        ),
        _observation(
            'a',
            'S2',
            status='wall_timeout',
        ),
        _observation(
            'b',
            'S2',
            status='wall_timeout',
        ),
    ))

    with pytest.raises(
        ValueError,
        match='unresolved cells',
    ):
        select_pareto_candidates(
            results,
            _policy(),
        )


def test_candidate_specific_timeout_on_scorable_cell_excludes_candidate():
    results = _results((
        _observation(
            'a',
            'S1',
            deadline=0.1,
            priority=0.2,
        ),
        _observation(
            'b',
            'S1',
            status='wall_timeout',
        ),
        _observation(
            'a',
            'S2',
            deadline=0.2,
            priority=0.2,
        ),
        _observation(
            'b',
            'S2',
            deadline=0.1,
            priority=0.1,
        ),
    ))

    selection = select_pareto_candidates(
        results,
        _policy(),
    )

    assert selection.eligible_candidate_ids == ('a',)
    assert (
        selection.excluded_candidates['b']
        == 'timeout_rate'
    )
    assert selection.pareto_candidate_ids == ('a',)


def test_metric_coverage_is_paired_and_missing_values_are_not_imputed():
    results = _results((
        _observation(
            'a',
            'S1',
            deadline=0.1,
            priority=0.2,
        ),
        _observation(
            'b',
            'S1',
            deadline=0.2,
            priority=0.1,
        ),
        _observation(
            'a',
            'S2',
            deadline=0.2,
            priority=None,
        ),
        _observation(
            'b',
            'S2',
            deadline=0.3,
            priority=None,
        ),
    ))

    selection = select_pareto_candidates(
        results,
        _policy(),
    )

    assert (
        selection.metric_observation_counts[
            'deadline_miss_rate'
        ]
        == 2
    )

    assert (
        selection.metric_observation_counts[
            'priority_inversion_rate'
        ]
        == 1
    )

    assert selection.pareto_candidate_ids == (
        'a',
        'b',
    )
