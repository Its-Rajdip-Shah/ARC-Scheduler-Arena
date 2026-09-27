from pathlib import Path
from types import MappingProxyType
import json

import pytest

from arena.tuning.execution import (
    TuningCandidateSummary,
    TuningStudyResults,
    TuningTrialObservation,
)
from arena.tuning.racing import (
    RacingRoundSpec,
    decide_racing_round,
    racing_decision_artifact,
    tuning_results_fingerprint,
    write_racing_decision,
)
from arena.tuning.selection import (
    MetricDirection,
    SelectionMetric,
    SelectionPolicy,
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
        performance_observation_counts=
            MappingProxyType({}),
    )


def _observation(
    candidate_id,
    scenario_id,
    *,
    deadline,
    priority,
    status='ok',
):
    performance = None

    if status == 'ok':
        performance = MappingProxyType({
            'hard_violation_count': 0.0,
            'canonical_infeasibility_count': 0.0,
            'deadline_miss_rate': deadline,
            'priority_inversion_rate': priority,
        })

    return TuningTrialObservation(
        candidate_id=candidate_id,
        scenario_id=scenario_id,
        run_seed=1,
        status=status,
        worker_wall_seconds=1.0,
        performance=performance,
    )


def _results(rows, scenarios=('S1', 'S2')):
    candidate_ids = []

    for row in rows:
        if row.candidate_id not in candidate_ids:
            candidate_ids.append(row.candidate_id)

    return TuningStudyResults(
        output_root=Path('study'),
        benchmark_manifest_sha256='a' * 64,
        development_scenario_ids=scenarios,
        holdout_scenario_ids=('H1',),
        seeds=(1,),
        candidate_summaries=tuple(
            _summary(
                candidate_id,
                len(scenarios),
            )
            for candidate_id in candidate_ids
        ),
        trial_observations=tuple(rows),
        expected_trials=len(rows),
        completed_trials=len(rows),
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


def _spec(candidate_ids, target=2, **policy_kwargs):
    return RacingRoundSpec(
        round_index=1,
        expected_candidate_ids=tuple(candidate_ids),
        target_survivor_count=target,
        selection_policy=_policy(**policy_kwargs),
    )


def test_round_eliminates_only_strictly_dominated_candidates():
    results = _results((
        _observation(
            'a', 'S1',
            deadline=0.1,
            priority=0.1,
        ),
        _observation(
            'b', 'S1',
            deadline=0.2,
            priority=0.2,
        ),
        _observation(
            'c', 'S1',
            deadline=0.0,
            priority=0.5,
        ),
        _observation(
            'a', 'S2',
            deadline=0.1,
            priority=0.1,
        ),
        _observation(
            'b', 'S2',
            deadline=0.3,
            priority=0.3,
        ),
        _observation(
            'c', 'S2',
            deadline=0.0,
            priority=0.5,
        ),
    ))

    decision = decide_racing_round(
        results,
        _spec(('a', 'b', 'c')),
    )

    assert decision.survivor_candidate_ids == (
        'a',
        'c',
    )
    assert dict(decision.eliminated_candidates) == {
        'b': 'strict_pareto_dominated',
    }
    assert decision.target_reached is True
    assert (
        decision.stop_reason
        == 'target_reached_without_scalar_ranking'
    )


def test_round_refuses_to_force_large_pareto_front_to_target():
    results = _results((
        _observation(
            'a', 'S1',
            deadline=0.0,
            priority=0.8,
        ),
        _observation(
            'b', 'S1',
            deadline=0.4,
            priority=0.4,
        ),
        _observation(
            'c', 'S1',
            deadline=0.8,
            priority=0.0,
        ),
        _observation(
            'a', 'S2',
            deadline=0.0,
            priority=0.8,
        ),
        _observation(
            'b', 'S2',
            deadline=0.4,
            priority=0.4,
        ),
        _observation(
            'c', 'S2',
            deadline=0.8,
            priority=0.0,
        ),
    ))

    decision = decide_racing_round(
        results,
        _spec(('a', 'b', 'c'), target=2),
    )

    assert decision.survivor_candidate_ids == (
        'a',
        'b',
        'c',
    )
    assert dict(decision.eliminated_candidates) == {}
    assert decision.target_reached is False
    assert (
        decision.stop_reason
        == 'pareto_front_exceeds_target_no_forced_ranking'
    )


def test_explicit_timeout_gate_is_an_auditable_elimination():
    results = _results((
        _observation(
            'a', 'S1',
            deadline=0.1,
            priority=0.1,
        ),
        _observation(
            'b', 'S1',
            deadline=0.0,
            priority=0.0,
            status='wall_timeout',
        ),
        _observation(
            'a', 'S2',
            deadline=0.2,
            priority=0.2,
        ),
        _observation(
            'b', 'S2',
            deadline=0.1,
            priority=0.1,
        ),
    ))

    decision = decide_racing_round(
        results,
        _spec(
            ('a', 'b'),
            target=1,
            max_timeout_rate=0.0,
        ),
    )

    assert decision.survivor_candidate_ids == ('a',)
    assert dict(decision.eliminated_candidates) == {
        'b': 'selection_excluded:timeout_rate',
    }


def test_structural_cell_does_not_penalise_every_candidate():
    rows = (
        _observation(
            'a', 'S1',
            deadline=0.1,
            priority=0.1,
        ),
        _observation(
            'b', 'S1',
            deadline=0.2,
            priority=0.2,
        ),
        TuningTrialObservation(
            candidate_id='a',
            scenario_id='S2',
            run_seed=1,
            status='constructor_invalid',
            worker_wall_seconds=0.1,
            performance=None,
        ),
        TuningTrialObservation(
            candidate_id='b',
            scenario_id='S2',
            run_seed=1,
            status='constructor_invalid',
            worker_wall_seconds=0.1,
            performance=None,
        ),
    )

    decision = decide_racing_round(
        _results(rows),
        _spec(('a', 'b'), target=1),
    )

    assert (
        decision.selection.structurally_unscorable_cells
        == (('S2', 1),)
    )
    assert decision.survivor_candidate_ids == ('a',)


def test_candidate_set_must_exactly_match_incoming_survivors():
    results = _results((
        _observation(
            'a', 'S1',
            deadline=0.1,
            priority=0.1,
        ),
        _observation(
            'b', 'S1',
            deadline=0.2,
            priority=0.2,
        ),
        _observation(
            'a', 'S2',
            deadline=0.1,
            priority=0.1,
        ),
        _observation(
            'b', 'S2',
            deadline=0.2,
            priority=0.2,
        ),
    ))

    with pytest.raises(
        ValueError,
        match='candidate set',
    ):
        decide_racing_round(
            results,
            _spec(('b', 'a'), target=1),
        )


def test_fingerprint_is_deterministic_and_binds_trial_evidence():
    first = _results((
        _observation(
            'a', 'S1',
            deadline=0.1,
            priority=0.1,
        ),
        _observation(
            'a', 'S2',
            deadline=0.2,
            priority=0.2,
        ),
    ))

    equivalent = _results((
        _observation(
            'a', 'S1',
            deadline=0.1,
            priority=0.1,
        ),
        _observation(
            'a', 'S2',
            deadline=0.2,
            priority=0.2,
        ),
    ))

    changed = _results((
        _observation(
            'a', 'S1',
            deadline=0.1,
            priority=0.1,
        ),
        _observation(
            'a', 'S2',
            deadline=0.25,
            priority=0.2,
        ),
    ))

    assert (
        tuning_results_fingerprint(first)
        == tuning_results_fingerprint(equivalent)
    )
    assert (
        tuning_results_fingerprint(first)
        != tuning_results_fingerprint(changed)
    )


def test_decision_artifact_is_complete_and_exclusive(tmp_path):
    results = _results((
        _observation(
            'a', 'S1',
            deadline=0.1,
            priority=0.1,
        ),
        _observation(
            'b', 'S1',
            deadline=0.2,
            priority=0.2,
        ),
        _observation(
            'a', 'S2',
            deadline=0.1,
            priority=0.1,
        ),
        _observation(
            'b', 'S2',
            deadline=0.2,
            priority=0.2,
        ),
    ))

    decision = decide_racing_round(
        results,
        _spec(('a', 'b'), target=1),
    )

    artifact = racing_decision_artifact(decision)

    assert artifact['schema_version'] == 1
    assert artifact['stage'] == 'C7.4b'
    assert artifact['survivor_candidate_ids'] == ['a']
    assert (
        artifact['eliminated_candidates']['b']
        == 'strict_pareto_dominated'
    )
    assert (
        artifact['source_evidence_sha256']
        == tuning_results_fingerprint(results)
    )

    path = tmp_path / 'round_01_decision.json'

    assert write_racing_decision(
        decision,
        path,
    ) == path

    loaded = json.loads(
        path.read_text(encoding='utf-8')
    )

    assert loaded == artifact

    with pytest.raises(FileExistsError):
        write_racing_decision(
            decision,
            path,
        )


def test_all_candidate_timeouts_are_recorded_as_common_mode_coverage_gap():
    results = _results((
        _observation(
            'a', 'S1',
            deadline=0.1,
            priority=0.1,
        ),
        _observation(
            'b', 'S1',
            deadline=0.2,
            priority=0.2,
        ),
        _observation(
            'a', 'S2',
            deadline=0.0,
            priority=0.0,
            status='wall_timeout',
        ),
        _observation(
            'b', 'S2',
            deadline=0.0,
            priority=0.0,
            status='wall_timeout',
        ),
    ))

    decision = decide_racing_round(
        results,
        _spec(
            ('a', 'b'),
            target=1,
            max_timeout_rate=0.0,
            reject_unresolved_cells=True,
        ),
    )

    assert decision.common_mode_timeout_cells == (
        ('S2', 1),
    )

    assert (
        decision.selection.unresolved_cells
        == ()
    )

    assert (
        decision.selection.paired_quality_cells
        == (('S1', 1),)
    )

    assert decision.survivor_candidate_ids == (
        'a',
    )

    artifact = racing_decision_artifact(
        decision
    )

    assert artifact[
        'common_mode_timeout_cells'
    ] == [['S2', 1]]


def test_mixed_common_failure_is_not_silently_dropped():
    results = _results((
        _observation(
            'a', 'S1',
            deadline=0.1,
            priority=0.1,
        ),
        _observation(
            'b', 'S1',
            deadline=0.2,
            priority=0.2,
        ),
        _observation(
            'a', 'S2',
            deadline=0.0,
            priority=0.0,
            status='wall_timeout',
        ),
        _observation(
            'b', 'S2',
            deadline=0.0,
            priority=0.0,
            status='error',
        ),
    ))

    with pytest.raises(
        ValueError,
        match='unresolved cells',
    ):
        decide_racing_round(
            results,
            _spec(
                ('a', 'b'),
                target=1,
                max_timeout_rate=0.0,
                reject_unresolved_cells=True,
            ),
        )
