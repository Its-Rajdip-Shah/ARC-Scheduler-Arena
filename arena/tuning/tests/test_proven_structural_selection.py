from pathlib import Path
from types import MappingProxyType

import pytest

from arena.tuning.execution import (
    TuningCandidateSummary,
    TuningStudyResults,
    TuningTrialObservation,
)
from arena.tuning.racing import (
    RacingRoundSpec,
    decide_racing_round,
)
from arena.tuning.selection import (
    C7_V1_SELECTION_POLICY,
    select_pareto_candidates,
)


def _summary(candidate_id):
    return TuningCandidateSummary(
        candidate_id=candidate_id,
        objective_id="objective",
        constructor_id="constructor",
        improver_id=candidate_id,
        intended_trials=2,
        ok_trials=1,
        timed_out_trials=1,
        failed_trials=0,
        ok_rate=0.5,
        timeout_rate=0.5,
        mean_worker_wall_seconds=1.0,
        performance_means=MappingProxyType({}),
        performance_observation_counts=MappingProxyType({}),
    )


def _ok(candidate_id):
    return TuningTrialObservation(
        candidate_id=candidate_id,
        scenario_id="FEASIBLE",
        run_seed=1701,
        status="ok",
        worker_wall_seconds=1.0,
        performance=MappingProxyType({
            "hard_violation_count": 0.0,
            "canonical_infeasibility_count": 0.0,
            "deadline_miss_rate": 0.0,
            "mean_lateness_days": 0.0,
            "priority_inversion_rate": 0.0,
            "unapproved_excess_session_count": 0.0,
            "fragmented_item_rate": 0.0,
            "mean_dependency_wait_days": 0.0,
            "mean_start_delay_days": 0.0,
        }),
    )


def _results(structural_statuses):
    candidate_ids = ("a", "b")

    observations = [
        _ok("a"),
        _ok("b"),
    ]

    for candidate_id, status in zip(
        candidate_ids,
        structural_statuses,
    ):
        observations.append(
            TuningTrialObservation(
                candidate_id=candidate_id,
                scenario_id="INFEASIBLE",
                run_seed=1701,
                status=status,
                worker_wall_seconds=45.0,
                performance=None,
            )
        )

    return TuningStudyResults(
        output_root=Path("study"),
        benchmark_manifest_sha256="a" * 64,
        development_scenario_ids=(
            "FEASIBLE",
            "INFEASIBLE",
        ),
        holdout_scenario_ids=("H1",),
        seeds=(1701,),
        candidate_summaries=tuple(
            _summary(candidate_id)
            for candidate_id in candidate_ids
        ),
        trial_observations=tuple(observations),
        expected_trials=4,
        completed_trials=4,
    )


def test_independent_proof_resolves_all_timeout_cell():
    results = _results((
        "wall_timeout",
        "wall_timeout",
    ))

    selection = select_pareto_candidates(
        results,
        C7_V1_SELECTION_POLICY,
        externally_proven_structural_cells=(
            ("INFEASIBLE", 1701),
        ),
    )

    assert selection.unresolved_cells == ()
    assert (
        selection.externally_proven_structural_cells
        == (("INFEASIBLE", 1701),)
    )


def test_independent_proof_resolves_mixed_invalid_timeout_cell():
    results = _results((
        "constructor_invalid",
        "wall_timeout",
    ))

    spec = RacingRoundSpec(
        round_index=1,
        expected_candidate_ids=("a", "b"),
        target_survivor_count=2,
        selection_policy=C7_V1_SELECTION_POLICY,
        proven_infeasible_scenario_ids=(
            "INFEASIBLE",
        ),
    )

    decision = decide_racing_round(
        results,
        spec,
    )

    assert decision.selection.unresolved_cells == ()
    assert (
        decision.selection.externally_proven_structural_cells
        == (("INFEASIBLE", 1701),)
    )


def test_independent_proof_cannot_hide_success():
    results = _results((
        "wall_timeout",
        "wall_timeout",
    ))

    observations = list(
        results.trial_observations
    )

    observations[-1] = TuningTrialObservation(
        candidate_id="b",
        scenario_id="INFEASIBLE",
        run_seed=1701,
        status="ok",
        worker_wall_seconds=1.0,
        performance=MappingProxyType({
            "hard_violation_count": 0.0,
            "canonical_infeasibility_count": 0.0,
            "deadline_miss_rate": 0.0,
            "mean_lateness_days": 0.0,
            "priority_inversion_rate": 0.0,
            "unapproved_excess_session_count": 0.0,
            "fragmented_item_rate": 0.0,
            "mean_dependency_wait_days": 0.0,
            "mean_start_delay_days": 0.0,
        }),
    )

    contradictory = TuningStudyResults(
        output_root=results.output_root,
        benchmark_manifest_sha256=
            results.benchmark_manifest_sha256,
        development_scenario_ids=
            results.development_scenario_ids,
        holdout_scenario_ids=
            results.holdout_scenario_ids,
        seeds=results.seeds,
        candidate_summaries=
            results.candidate_summaries,
        trial_observations=tuple(observations),
        expected_trials=4,
        completed_trials=4,
    )

    with pytest.raises(
        ValueError,
        match="contradicts",
    ):
        select_pareto_candidates(
            contradictory,
            C7_V1_SELECTION_POLICY,
            externally_proven_structural_cells=(
                ("INFEASIBLE", 1701),
            ),
        )
