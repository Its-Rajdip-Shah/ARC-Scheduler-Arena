"""C7.6 durable freeze of the C8 contestant field."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from types import MappingProxyType

from arena.experiments.paired import (
    _config_json,
    _dump,
    _normalize,
)

from .study import TuningCandidate


@dataclass(frozen=True, slots=True)
class FrozenContestant:
    source_candidate_id: str
    label: str
    witness_metrics: tuple[str, ...]
    objective_id: str
    constructor_arm_id: str
    improver_arm_id: str
    comparison_objective: object
    constructor_config: object
    improver_config: object | None
    semantic_fingerprint: str


@dataclass(frozen=True, slots=True)
class C8ContestantField:
    contestants: tuple[FrozenContestant, ...]
    holdout_scenario_ids: tuple[str, ...]


def _semantic_payload(
    candidate: TuningCandidate,
) -> dict:
    return {
        'comparison_objective':
            _normalize(
                candidate.comparison_objective
            ),
        'constructor_config':
            _normalize(
                candidate
                .constructor
                .algorithm
            ),
        'improver_config': (
            None
            if candidate.improver.engine is None
            else _normalize(
                candidate.improver.engine
            )
        ),
    }


def _semantic_fingerprint(
    candidate: TuningCandidate,
) -> str:
    encoded = _dump(
        _semantic_payload(candidate)
    ).encode('utf-8')

    return sha256(encoded).hexdigest()


def freeze_c8_contestants(
    *,
    source_candidates: tuple[
        TuningCandidate,
        ...
    ],
    shortlisted_candidate_ids:
        tuple[str, ...],
    labels: dict[str, str],
    witness_metrics:
        dict[str, tuple[str, ...]],
    holdout_scenario_ids:
        tuple[str, ...],
) -> C8ContestantField:
    if (
        not isinstance(
            shortlisted_candidate_ids,
            tuple,
        )
        or not shortlisted_candidate_ids
        or len(
            set(shortlisted_candidate_ids)
        )
        != len(shortlisted_candidate_ids)
    ):
        raise ValueError(
            'shortlisted_candidate_ids must '
            'be a unique nonempty tuple'
        )

    if (
        not isinstance(
            holdout_scenario_ids,
            tuple,
        )
        or not holdout_scenario_ids
        or len(set(holdout_scenario_ids))
        != len(holdout_scenario_ids)
    ):
        raise ValueError(
            'holdout_scenario_ids must be '
            'a unique nonempty tuple'
        )

    by_id = {
        candidate.candidate_id:
            candidate
        for candidate
        in source_candidates
    }

    if len(by_id) != len(source_candidates):
        raise ValueError(
            'source candidate IDs are not unique'
        )

    missing = [
        candidate_id
        for candidate_id
        in shortlisted_candidate_ids
        if candidate_id not in by_id
    ]

    if missing:
        raise ValueError(
            'Shortlisted candidate not found '
            f'in frozen source plan: {missing}'
        )

    if (
        set(labels)
        != set(shortlisted_candidate_ids)
    ):
        raise ValueError(
            'labels must exactly cover '
            'the shortlisted field'
        )

    if (
        set(witness_metrics)
        != set(shortlisted_candidate_ids)
    ):
        raise ValueError(
            'witness_metrics must exactly cover '
            'the shortlisted field'
        )

    contestants = []

    for candidate_id in (
        shortlisted_candidate_ids
    ):
        candidate = by_id[candidate_id]

        metrics = witness_metrics[
            candidate_id
        ]

        if (
            not isinstance(metrics, tuple)
            or not metrics
            or len(set(metrics))
            != len(metrics)
        ):
            raise ValueError(
                'Every frozen contestant must '
                'have at least one unique '
                'C7.5 witness metric'
            )

        constructor_config = (
            _normalize(
                candidate
                .constructor
                .algorithm
            )
        )

        improver_config = (
            None
            if candidate.improver.engine
            is None
            else _normalize(
                candidate.improver.engine
            )
        )

        contestants.append(
            FrozenContestant(
                source_candidate_id=
                    candidate_id,
                label=labels[
                    candidate_id
                ],
                witness_metrics=
                    metrics,
                objective_id=
                    candidate.objective_id,
                constructor_arm_id=
                    candidate
                    .constructor
                    .arm_id,
                improver_arm_id=
                    candidate
                    .improver
                    .arm_id,
                comparison_objective=
                    _normalize(
                        candidate
                        .comparison_objective
                    ),
                constructor_config=
                    constructor_config,
                improver_config=
                    improver_config,
                semantic_fingerprint=
                    _semantic_fingerprint(
                        candidate
                    ),
            )
        )

    fingerprints = tuple(
        contestant.semantic_fingerprint
        for contestant in contestants
    )

    if (
        len(set(fingerprints))
        != len(fingerprints)
    ):
        raise ValueError(
            'Distinct C8 contestants have '
            'duplicate semantic configurations'
        )

    return C8ContestantField(
        contestants=tuple(contestants),
        holdout_scenario_ids=
            holdout_scenario_ids,
    )


def c8_contestant_artifact(
    field: C8ContestantField,
    *,
    c75_shortlist_sha256: str,
    c74c_evidence_sha256: str,
) -> dict:
    if not isinstance(
        field,
        C8ContestantField,
    ):
        raise TypeError(
            'field must be C8ContestantField'
        )

    for value, name in (
        (
            c75_shortlist_sha256,
            'c75_shortlist_sha256',
        ),
        (
            c74c_evidence_sha256,
            'c74c_evidence_sha256',
        ),
    ):
        if (
            not isinstance(value, str)
            or len(value) != 64
            or any(
                char not in '0123456789abcdef'
                for char in value
            )
        ):
            raise ValueError(
                f'{name} must be lowercase SHA-256'
            )

    return {
        'schema_version': 1,
        'stage': 'C7.6',
        'purpose':
            'freeze_C8_contestant_field',
        'source_stage': 'C7.5',
        'source_shortlist_sha256':
            c75_shortlist_sha256,
        'source_c74c_evidence_sha256':
            c74c_evidence_sha256,
        'contestant_count':
            len(field.contestants),
        'holdout_scenario_count':
            len(
                field.holdout_scenario_ids
            ),
        'holdout_scenario_ids':
            list(
                field.holdout_scenario_ids
            ),
        'holdout_accessed': False,
        'additional_development_selection':
            False,
        'scalar_ranking_used': False,
        'contestants': [
            {
                'source_candidate_id':
                    contestant
                    .source_candidate_id,
                'label':
                    contestant.label,
                'witness_metrics':
                    list(
                        contestant
                        .witness_metrics
                    ),
                'objective_id':
                    contestant.objective_id,
                'constructor_arm_id':
                    contestant
                    .constructor_arm_id,
                'improver_arm_id':
                    contestant
                    .improver_arm_id,
                'comparison_objective':
                    contestant
                    .comparison_objective,
                'constructor_config':
                    contestant
                    .constructor_config,
                'improver_config':
                    contestant
                    .improver_config,
                'semantic_fingerprint':
                    contestant
                    .semantic_fingerprint,
            }
            for contestant
            in field.contestants
        ],
    }
