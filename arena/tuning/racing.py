"""C7.4b: deterministic paired racing without a hidden scalar score.

A racing round consumes one complete development-only TuningStudyResults
matrix. Candidate quality is delegated to the frozen C7 paired Pareto
selector.

The racing layer is deliberately conservative:

* resource/feasibility gate failures may eliminate a candidate;
* strict paired Pareto domination may eliminate a candidate;
* a requested survivor target never authorises arbitrary ranking;
* when the Pareto front is larger than the requested target, the round
  explicitly stalls above target instead of inventing a scalar tie-break;
* every decision is bound to a deterministic fingerprint of the semantic
  evidence from which it was derived.

This module performs no scheduling and accesses no holdout workloads.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
from types import MappingProxyType

from .execution import TuningStudyResults
from .selection import (
    ParetoSelectionResult,
    SelectionPolicy,
    select_pareto_candidates,
)


@dataclass(frozen=True, slots=True)
class RacingRoundSpec:
    """Immutable contract for one C7.4b elimination round."""

    round_index: int
    expected_candidate_ids: tuple[str, ...]
    target_survivor_count: int
    selection_policy: SelectionPolicy
    proven_infeasible_scenario_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if type(self.round_index) is not int or self.round_index <= 0:
            raise ValueError('round_index must be a positive exact integer')

        if (
            not isinstance(self.expected_candidate_ids, tuple)
            or not self.expected_candidate_ids
            or any(
                not isinstance(candidate_id, str) or not candidate_id
                for candidate_id in self.expected_candidate_ids
            )
        ):
            raise ValueError(
                'expected_candidate_ids must be a nonempty tuple '
                'of nonempty strings'
            )

        if (
            len(set(self.expected_candidate_ids))
            != len(self.expected_candidate_ids)
        ):
            raise ValueError('Duplicate expected candidate ID')

        if (
            type(self.target_survivor_count) is not int
            or self.target_survivor_count <= 0
            or self.target_survivor_count
            > len(self.expected_candidate_ids)
        ):
            raise ValueError(
                'target_survivor_count must lie in '
                '[1, candidate_count]'
            )

        if not isinstance(
            self.selection_policy,
            SelectionPolicy,
        ):
            raise TypeError(
                'selection_policy must be a SelectionPolicy'
            )

        if not isinstance(
            self.proven_infeasible_scenario_ids,
            tuple,
        ):
            raise TypeError(
                'proven_infeasible_scenario_ids must be a tuple'
            )

        if any(
            not isinstance(scenario_id, str)
            or not scenario_id
            for scenario_id
            in self.proven_infeasible_scenario_ids
        ):
            raise ValueError(
                'proven_infeasible_scenario_ids must contain '
                'nonempty strings'
            )

        if (
            len(set(self.proven_infeasible_scenario_ids))
            != len(self.proven_infeasible_scenario_ids)
        ):
            raise ValueError(
                'Duplicate proven-infeasible scenario ID'
            )


@dataclass(frozen=True, slots=True)
class RacingRoundDecision:
    """Auditable outcome of a single paired racing round."""

    spec: RacingRoundSpec
    source_evidence_sha256: str
    benchmark_manifest_sha256: str
    development_scenario_ids: tuple[str, ...]
    seeds: tuple[int, ...]
    candidate_ids: tuple[str, ...]
    survivor_candidate_ids: tuple[str, ...]
    eliminated_candidates: MappingProxyType
    common_mode_timeout_cells: tuple[tuple[str, int], ...]
    target_reached: bool
    stop_reason: str
    selection: ParetoSelectionResult


def _canonical_json(value) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(',', ':'),
        ensure_ascii=True,
        allow_nan=False,
    )


def tuning_results_fingerprint(
    results: TuningStudyResults,
) -> str:
    """Hash the semantic evidence used by a racing decision.

    The fingerprint does not depend on an absolute filesystem path. It binds
    the benchmark identity, development/holdout split, seeds, declared
    candidates and every loaded trial observation including C1 values.
    """
    if not isinstance(results, TuningStudyResults):
        raise TypeError('Expected TuningStudyResults')

    payload = {
        'benchmark_manifest_sha256':
            results.benchmark_manifest_sha256,
        'development_scenario_ids':
            list(results.development_scenario_ids),
        'holdout_scenario_ids':
            list(results.holdout_scenario_ids),
        'seeds':
            list(results.seeds),
        'candidate_ids': [
            summary.candidate_id
            for summary in results.candidate_summaries
        ],
        'observations': [
            {
                'candidate_id': observation.candidate_id,
                'scenario_id': observation.scenario_id,
                'run_seed': observation.run_seed,
                'status': observation.status,
                'worker_wall_seconds':
                    observation.worker_wall_seconds,
                'performance': (
                    None
                    if observation.performance is None
                    else dict(observation.performance)
                ),
            }
            for observation in results.trial_observations
        ],
    }

    return sha256(
        _canonical_json(payload).encode('utf-8')
    ).hexdigest()


def _common_mode_timeout_cells(
    results: TuningStudyResults,
    *,
    excluded_cells: set[tuple[str, int]],
) -> tuple[tuple[str, int], ...]:
    candidate_ids = tuple(
        summary.candidate_id
        for summary in results.candidate_summaries
    )

    observation_map = {
        (
            observation.candidate_id,
            observation.scenario_id,
            observation.run_seed,
        ): observation
        for observation in results.trial_observations
    }

    common_mode = []

    for scenario_id in results.development_scenario_ids:
        for seed in results.seeds:
            cell_key = (scenario_id, seed)

            if cell_key in excluded_cells:
                continue

            statuses = tuple(
                observation_map[
                    (
                        candidate_id,
                        scenario_id,
                        seed,
                    )
                ].status
                for candidate_id in candidate_ids
            )

            if statuses and all(
                status == 'wall_timeout'
                for status in statuses
            ):
                common_mode.append(cell_key)

    return tuple(common_mode)


def _without_comparatively_unusable_cells(
    results: TuningStudyResults,
    cells: tuple[tuple[str, int], ...],
) -> TuningStudyResults:
    if not cells:
        return results

    blocked = set(cells)

    scenario_ids = tuple(
        scenario_id
        for scenario_id in results.development_scenario_ids
        if all(
            (scenario_id, seed) not in blocked
            for seed in results.seeds
        )
    )

    if not scenario_ids:
        raise ValueError(
            'No comparative development scenarios remain after '
            'common-mode timeout classification'
        )

    observations = tuple(
        observation
        for observation in results.trial_observations
        if (
            observation.scenario_id,
            observation.run_seed,
        ) not in blocked
    )

    expected = (
        len(results.candidate_summaries)
        * len(scenario_ids)
        * len(results.seeds)
    )

    if len(observations) != expected:
        raise ValueError(
            'Common-mode timeout filtering broke paired evidence'
        )

    return TuningStudyResults(
        output_root=results.output_root,
        benchmark_manifest_sha256=
            results.benchmark_manifest_sha256,
        development_scenario_ids=scenario_ids,
        holdout_scenario_ids=
            results.holdout_scenario_ids,
        seeds=results.seeds,
        candidate_summaries=
            results.candidate_summaries,
        trial_observations=observations,
        expected_trials=expected,
        completed_trials=expected,
    )


def decide_racing_round(
    results: TuningStudyResults,
    spec: RacingRoundSpec,
) -> RacingRoundDecision:
    """Apply the frozen paired selector and make only defensible eliminations.

    The target survivor count is an experiment-resource target, not a quality
    ranking instruction. If the strict Pareto front remains larger than the
    target, every member of that front survives.
    """
    if not isinstance(results, TuningStudyResults):
        raise TypeError('Expected TuningStudyResults')

    if not isinstance(spec, RacingRoundSpec):
        raise TypeError('Expected RacingRoundSpec')

    candidate_ids = tuple(
        summary.candidate_id
        for summary in results.candidate_summaries
    )

    if candidate_ids != spec.expected_candidate_ids:
        raise ValueError(
            'Racing round candidate set does not exactly match '
            'the registered incoming survivor set'
        )

    if (
        set(results.development_scenario_ids)
        & set(results.holdout_scenario_ids)
    ):
        raise ValueError(
            'Development and holdout scenarios must be disjoint'
        )

    unknown_proven = (
        set(spec.proven_infeasible_scenario_ids)
        - set(results.development_scenario_ids)
    )

    if unknown_proven:
        raise ValueError(
            'Proven-infeasible scenario is outside '
            'the current racing round'
        )

    externally_proven_cells = tuple(
        (scenario_id, seed)
        for scenario_id
        in spec.proven_infeasible_scenario_ids
        for seed in results.seeds
    )

    common_mode_timeout_cells = (
        _common_mode_timeout_cells(
            results,
            excluded_cells=set(
                externally_proven_cells
            ),
        )
    )

    comparative_results = (
        _without_comparatively_unusable_cells(
            results,
            common_mode_timeout_cells,
        )
    )

    comparative_proven_cells = tuple(
        cell
        for cell in externally_proven_cells
        if (
            cell[0]
            in comparative_results.development_scenario_ids
        )
    )

    selection = select_pareto_candidates(
        comparative_results,
        spec.selection_policy,
        externally_proven_structural_cells=
            comparative_proven_cells,
    )

    pareto_ids = selection.pareto_candidate_ids

    if not pareto_ids:
        raise ValueError(
            'Racing round eliminated every candidate; '
            'do not continue to a later fidelity'
        )

    pareto_set = set(pareto_ids)
    excluded = dict(selection.excluded_candidates)
    eliminated = {}

    for candidate_id in candidate_ids:
        if candidate_id in pareto_set:
            continue

        if candidate_id in excluded:
            eliminated[candidate_id] = (
                'selection_excluded:'
                + excluded[candidate_id]
            )
        else:
            eliminated[candidate_id] = (
                'strict_pareto_dominated'
            )

    target_reached = (
        len(pareto_ids)
        <= spec.target_survivor_count
    )

    if target_reached:
        stop_reason = 'target_reached_without_scalar_ranking'
    else:
        stop_reason = (
            'pareto_front_exceeds_target_no_forced_ranking'
        )

    return RacingRoundDecision(
        spec=spec,
        source_evidence_sha256=
            tuning_results_fingerprint(results),
        benchmark_manifest_sha256=
            results.benchmark_manifest_sha256,
        development_scenario_ids=
            results.development_scenario_ids,
        seeds=results.seeds,
        candidate_ids=candidate_ids,
        survivor_candidate_ids=pareto_ids,
        eliminated_candidates=MappingProxyType(
            eliminated
        ),
        common_mode_timeout_cells=
            common_mode_timeout_cells,
        target_reached=target_reached,
        stop_reason=stop_reason,
        selection=selection,
    )


def _metric_artifact(metric) -> dict:
    return {
        'name': metric.name,
        'direction': metric.direction.value,
    }


def racing_decision_artifact(
    decision: RacingRoundDecision,
) -> dict:
    """Return the stable JSON representation of a racing decision."""
    if not isinstance(decision, RacingRoundDecision):
        raise TypeError('Expected RacingRoundDecision')

    selection = decision.selection
    policy = decision.spec.selection_policy

    return {
        'schema_version': 1,
        'stage': 'C7.4b',
        'round_index': decision.spec.round_index,
        'source_evidence_sha256':
            decision.source_evidence_sha256,
        'benchmark_manifest_sha256':
            decision.benchmark_manifest_sha256,
        'development_scenario_ids':
            list(decision.development_scenario_ids),
        'seeds': list(decision.seeds),
        'candidate_ids':
            list(decision.candidate_ids),
        'target_survivor_count':
            decision.spec.target_survivor_count,
        'proven_infeasible_scenario_ids':
            list(
                decision.spec.proven_infeasible_scenario_ids
            ),
        'selection_policy': {
            'metrics': [
                _metric_artifact(metric)
                for metric in policy.metrics
            ],
            'max_timeout_rate':
                policy.max_timeout_rate,
            'max_failure_rate':
                policy.max_failure_rate,
            'require_zero_hard_violations':
                policy.require_zero_hard_violations,
            'require_zero_canonical_infeasibilities':
                policy.require_zero_canonical_infeasibilities,
            'reject_unresolved_cells':
                policy.reject_unresolved_cells,
        },
        'common_mode_timeout_cells': [
            [scenario_id, seed]
            for scenario_id, seed
            in decision.common_mode_timeout_cells
        ],
        'selection_evidence': {
            'eligible_candidate_ids':
                list(selection.eligible_candidate_ids),
            'excluded_candidates':
                dict(selection.excluded_candidates),
            'structurally_unscorable_cells': [
                [scenario_id, seed]
                for scenario_id, seed
                in selection.structurally_unscorable_cells
            ],
            'externally_proven_structural_cells': [
                [scenario_id, seed]
                for scenario_id, seed
                in selection.externally_proven_structural_cells
            ],
            'unresolved_cells': [
                [scenario_id, seed]
                for scenario_id, seed
                in selection.unresolved_cells
            ],
            'paired_quality_cells': [
                [scenario_id, seed]
                for scenario_id, seed
                in selection.paired_quality_cells
            ],
            'active_metrics': [
                _metric_artifact(metric)
                for metric in selection.active_metrics
            ],
            'inactive_metrics': [
                _metric_artifact(metric)
                for metric in selection.inactive_metrics
            ],
            'metric_observation_counts':
                dict(selection.metric_observation_counts),
            'pareto_candidate_ids':
                list(selection.pareto_candidate_ids),
        },
        'survivor_candidate_ids':
            list(decision.survivor_candidate_ids),
        'eliminated_candidates':
            dict(decision.eliminated_candidates),
        'target_reached':
            decision.target_reached,
        'stop_reason':
            decision.stop_reason,
    }


def write_racing_decision(
    decision: RacingRoundDecision,
    path: Path,
) -> Path:
    """Exclusively write one immutable C7.4b decision artifact."""
    if not isinstance(path, Path):
        raise TypeError('path must be a Path')

    if path.name in ('', '.', '..'):
        raise ValueError('Invalid decision artifact path')

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    payload = (
        _canonical_json(
            racing_decision_artifact(decision)
        )
        + '\n'
    ).encode('utf-8')

    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL

    try:
        descriptor = os.open(
            path,
            flags,
            0o644,
        )
    except FileExistsError:
        raise

    try:
        with os.fdopen(
            descriptor,
            'wb',
        ) as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        try:
            path.unlink()
        except OSError:
            pass
        raise

    return path
