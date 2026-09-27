"""C7.4b multi-fidelity racing campaign planning.

This module plans successive development-only fidelity stages. It does not
execute schedulers and does not select winners.

The campaign contract keeps:
- holdout workloads inaccessible to racing rounds;
- scenario fidelity cumulative and deterministic;
- candidate identity unchanged across rounds;
- survivor carry-forward explicit;
- requested survivor counts advisory only;
- every round auditable before execution.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path

from .racing import RacingRoundSpec
from .selection import SelectionPolicy


@dataclass(frozen=True, slots=True)
class RacingFidelityStage:
    round_index: int
    scenario_count: int
    target_survivor_count: int

    def __post_init__(self) -> None:
        if type(self.round_index) is not int or self.round_index <= 0:
            raise ValueError('round_index must be a positive exact integer')

        if type(self.scenario_count) is not int or self.scenario_count <= 0:
            raise ValueError('scenario_count must be a positive exact integer')

        if (
            type(self.target_survivor_count) is not int
            or self.target_survivor_count <= 0
        ):
            raise ValueError(
                'target_survivor_count must be a positive exact integer'
            )


@dataclass(frozen=True, slots=True)
class RacingCampaignSpec:
    campaign_id: str
    benchmark_manifest_sha256: str
    development_scenario_ids: tuple[str, ...]
    holdout_scenario_ids: tuple[str, ...]
    seeds: tuple[int, ...]
    initial_candidate_ids: tuple[str, ...]
    stages: tuple[RacingFidelityStage, ...]
    selection_policy: SelectionPolicy
    proven_infeasible_scenario_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.campaign_id, str) or not self.campaign_id:
            raise ValueError('campaign_id must be a nonempty string')

        if (
            not isinstance(self.benchmark_manifest_sha256, str)
            or len(self.benchmark_manifest_sha256) != 64
            or any(
                char not in '0123456789abcdef'
                for char in self.benchmark_manifest_sha256
            )
        ):
            raise ValueError(
                'benchmark_manifest_sha256 must be lowercase SHA-256'
            )

        for name in (
            'development_scenario_ids',
            'holdout_scenario_ids',
            'initial_candidate_ids',
            'seeds',
            'stages',
        ):
            if not isinstance(getattr(self, name), tuple):
                raise TypeError(f'{name} must be a tuple')

        if not self.development_scenario_ids:
            raise ValueError('development_scenario_ids must be nonempty')

        if not self.holdout_scenario_ids:
            raise ValueError('holdout_scenario_ids must be nonempty')

        if (
            len(set(self.development_scenario_ids))
            != len(self.development_scenario_ids)
        ):
            raise ValueError('Duplicate development scenario ID')

        if (
            len(set(self.holdout_scenario_ids))
            != len(self.holdout_scenario_ids)
        ):
            raise ValueError('Duplicate holdout scenario ID')

        if (
            set(self.development_scenario_ids)
            & set(self.holdout_scenario_ids)
        ):
            raise ValueError(
                'Development and holdout scenarios must be disjoint'
            )

        if (
            not self.initial_candidate_ids
            or any(
                not isinstance(candidate_id, str) or not candidate_id
                for candidate_id in self.initial_candidate_ids
            )
        ):
            raise ValueError(
                'initial_candidate_ids must contain nonempty strings'
            )

        if (
            len(set(self.initial_candidate_ids))
            != len(self.initial_candidate_ids)
        ):
            raise ValueError('Duplicate initial candidate ID')

        if (
            not self.seeds
            or any(type(seed) is not int for seed in self.seeds)
            or len(set(self.seeds)) != len(self.seeds)
        ):
            raise ValueError('Seeds must be unique exact integers')

        if (
            not self.stages
            or any(
                not isinstance(stage, RacingFidelityStage)
                for stage in self.stages
            )
        ):
            raise ValueError(
                'stages must contain RacingFidelityStage values'
            )

        if not isinstance(self.selection_policy, SelectionPolicy):
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

        if (
            set(self.proven_infeasible_scenario_ids)
            - set(self.development_scenario_ids)
        ):
            raise ValueError(
                'Proven-infeasible scenarios must belong '
                'to the development partition'
            )

        expected_rounds = tuple(
            range(1, len(self.stages) + 1)
        )

        actual_rounds = tuple(
            stage.round_index
            for stage in self.stages
        )

        if actual_rounds != expected_rounds:
            raise ValueError(
                'Racing rounds must be contiguous and one-indexed'
            )

        previous_scenarios = 0
        previous_target = len(self.initial_candidate_ids)

        for stage in self.stages:
            if stage.scenario_count > len(
                self.development_scenario_ids
            ):
                raise ValueError(
                    'A fidelity stage exceeds development scenario count'
                )

            if stage.scenario_count <= previous_scenarios:
                raise ValueError(
                    'Scenario fidelity must strictly increase each round'
                )

            if stage.target_survivor_count > previous_target:
                raise ValueError(
                    'Target survivor counts must be nonincreasing'
                )

            previous_scenarios = stage.scenario_count
            previous_target = stage.target_survivor_count


@dataclass(frozen=True, slots=True)
class RacingRoundPlan:
    campaign_id: str
    round_index: int
    scenario_ids: tuple[str, ...]
    incremental_scenario_ids: tuple[str, ...]
    seeds: tuple[int, ...]
    incoming_candidate_ids: tuple[str, ...]
    target_survivor_count: int
    expected_trials: int
    incremental_expected_trials: int
    decision_spec: RacingRoundSpec


def campaign_fingerprint(spec: RacingCampaignSpec) -> str:
    if not isinstance(spec, RacingCampaignSpec):
        raise TypeError('Expected RacingCampaignSpec')

    payload = racing_campaign_artifact(spec)

    return sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(',', ':'),
            ensure_ascii=True,
            allow_nan=False,
        ).encode('utf-8')
    ).hexdigest()


def build_racing_round_plan(
    campaign: RacingCampaignSpec,
    round_index: int,
    incoming_candidate_ids: tuple[str, ...],
) -> RacingRoundPlan:
    if not isinstance(campaign, RacingCampaignSpec):
        raise TypeError('Expected RacingCampaignSpec')

    if (
        type(round_index) is not int
        or round_index < 1
        or round_index > len(campaign.stages)
    ):
        raise ValueError('Invalid racing round index')

    if (
        not isinstance(incoming_candidate_ids, tuple)
        or not incoming_candidate_ids
        or any(
            not isinstance(candidate_id, str) or not candidate_id
            for candidate_id in incoming_candidate_ids
        )
    ):
        raise ValueError(
            'incoming_candidate_ids must be a nonempty tuple'
        )

    if len(set(incoming_candidate_ids)) != len(
        incoming_candidate_ids
    ):
        raise ValueError('Duplicate incoming candidate ID')

    initial_set = set(campaign.initial_candidate_ids)

    if any(
        candidate_id not in initial_set
        for candidate_id in incoming_candidate_ids
    ):
        raise ValueError(
            'Incoming survivors must belong to initial candidate set'
        )

    initial_order = {
        candidate_id: index
        for index, candidate_id
        in enumerate(campaign.initial_candidate_ids)
    }

    if tuple(
        sorted(
            incoming_candidate_ids,
            key=initial_order.__getitem__,
        )
    ) != incoming_candidate_ids:
        raise ValueError(
            'Incoming survivor order must preserve frozen candidate order'
        )

    stage = campaign.stages[round_index - 1]

    scenario_ids = campaign.development_scenario_ids[
        :stage.scenario_count
    ]

    previous_scenario_count = (
        0
        if round_index == 1
        else campaign.stages[
            round_index - 2
        ].scenario_count
    )

    incremental_scenario_ids = (
        campaign.development_scenario_ids[
            previous_scenario_count:
            stage.scenario_count
        ]
    )

    if (
        set(scenario_ids)
        & set(campaign.holdout_scenario_ids)
    ):
        raise ValueError(
            'Racing round attempted to access holdout scenarios'
        )

    if (
        set(incremental_scenario_ids)
        & set(campaign.holdout_scenario_ids)
    ):
        raise ValueError(
            'Incremental racing work attempted to access holdout scenarios'
        )

    if not incremental_scenario_ids:
        raise ValueError(
            'Racing round must add at least one development scenario'
        )

    target = min(
        stage.target_survivor_count,
        len(incoming_candidate_ids),
    )

    proven_in_round = tuple(
        scenario_id
        for scenario_id
        in campaign.proven_infeasible_scenario_ids
        if scenario_id in set(scenario_ids)
    )

    decision_spec = RacingRoundSpec(
        round_index=round_index,
        expected_candidate_ids=incoming_candidate_ids,
        target_survivor_count=target,
        selection_policy=campaign.selection_policy,
        proven_infeasible_scenario_ids=
            proven_in_round,
    )

    expected_trials = (
        len(incoming_candidate_ids)
        * len(scenario_ids)
        * len(campaign.seeds)
    )

    incremental_expected_trials = (
        len(incoming_candidate_ids)
        * len(incremental_scenario_ids)
        * len(campaign.seeds)
    )

    return RacingRoundPlan(
        campaign_id=campaign.campaign_id,
        round_index=round_index,
        scenario_ids=scenario_ids,
        incremental_scenario_ids=incremental_scenario_ids,
        seeds=campaign.seeds,
        incoming_candidate_ids=incoming_candidate_ids,
        target_survivor_count=target,
        expected_trials=expected_trials,
        incremental_expected_trials=incremental_expected_trials,
        decision_spec=decision_spec,
    )


def next_round_plan(
    campaign: RacingCampaignSpec,
    completed_round,
) -> RacingRoundPlan | None:
    """Build the next fidelity plan directly from a completed decision."""
    from .racing import RacingRoundDecision

    if not isinstance(completed_round, RacingRoundDecision):
        raise TypeError('Expected RacingRoundDecision')

    if completed_round.spec.round_index >= len(campaign.stages):
        return None

    return build_racing_round_plan(
        campaign,
        completed_round.spec.round_index + 1,
        completed_round.survivor_candidate_ids,
    )


def racing_campaign_artifact(
    spec: RacingCampaignSpec,
) -> dict:
    if not isinstance(spec, RacingCampaignSpec):
        raise TypeError('Expected RacingCampaignSpec')

    return {
        'schema_version': 1,
        'stage': 'C7.4b',
        'campaign_id': spec.campaign_id,
        'benchmark_manifest_sha256':
            spec.benchmark_manifest_sha256,
        'development_scenario_ids':
            list(spec.development_scenario_ids),
        'holdout_scenario_ids':
            list(spec.holdout_scenario_ids),
        'seeds': list(spec.seeds),
        'initial_candidate_ids':
            list(spec.initial_candidate_ids),
        'proven_infeasible_scenario_ids':
            list(spec.proven_infeasible_scenario_ids),
        'stages': [
            {
                'round_index': stage.round_index,
                'scenario_count': stage.scenario_count,
                'target_survivor_count':
                    stage.target_survivor_count,
            }
            for stage in spec.stages
        ],
        'selection_policy': {
            'metrics': [
                {
                    'name': metric.name,
                    'direction': metric.direction.value,
                }
                for metric in spec.selection_policy.metrics
            ],
            'max_timeout_rate':
                spec.selection_policy.max_timeout_rate,
            'max_failure_rate':
                spec.selection_policy.max_failure_rate,
            'require_zero_hard_violations':
                spec.selection_policy.require_zero_hard_violations,
            'require_zero_canonical_infeasibilities':
                spec.selection_policy
                .require_zero_canonical_infeasibilities,
            'reject_unresolved_cells':
                spec.selection_policy.reject_unresolved_cells,
        },
    }


def racing_round_plan_artifact(
    plan: RacingRoundPlan,
) -> dict:
    if not isinstance(plan, RacingRoundPlan):
        raise TypeError('Expected RacingRoundPlan')

    return {
        'schema_version': 1,
        'stage': 'C7.4b',
        'campaign_id': plan.campaign_id,
        'round_index': plan.round_index,
        'scenario_ids': list(plan.scenario_ids),
        'incremental_scenario_ids':
            list(plan.incremental_scenario_ids),
        'seeds': list(plan.seeds),
        'incoming_candidate_ids':
            list(plan.incoming_candidate_ids),
        'target_survivor_count':
            plan.target_survivor_count,
        'expected_trials':
            plan.expected_trials,
        'incremental_expected_trials':
            plan.incremental_expected_trials,
    }


def _write_exclusive_json(payload: dict, path: Path) -> Path:
    if not isinstance(path, Path):
        raise TypeError('path must be a Path')

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    data = (
        json.dumps(
            payload,
            sort_keys=True,
            separators=(',', ':'),
            ensure_ascii=True,
            allow_nan=False,
        )
        + '\n'
    ).encode('utf-8')

    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        0o644,
    )

    try:
        with os.fdopen(descriptor, 'wb') as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        try:
            path.unlink()
        except OSError:
            pass
        raise

    return path


def write_racing_campaign(
    spec: RacingCampaignSpec,
    path: Path,
) -> Path:
    return _write_exclusive_json(
        racing_campaign_artifact(spec),
        path,
    )


def write_racing_round_plan(
    plan: RacingRoundPlan,
    path: Path,
) -> Path:
    return _write_exclusive_json(
        racing_round_plan_artifact(plan),
        path,
    )
