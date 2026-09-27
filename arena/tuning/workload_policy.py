"""C9.2 frozen workload policy.

C9.2 deliberately does not train or fit an automatic workload router.
It converts frozen C9.1 development-only evidence into an explicit,
human-readable policy for C10 real-ARC validation.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WorkloadPolicyRole:
    candidate_id: str
    label: str
    role: str
    pareto_scenario_count: int
    scorable_scenario_count: int
    rationale: str


@dataclass(frozen=True, slots=True)
class FrozenWorkloadPolicy:
    roles: tuple[
        WorkloadPolicyRole,
        ...
    ]
    automatic_router_enabled: bool
    learned_classifier_used: bool
    c8_evidence_used_for_policy: bool


def freeze_workload_policy(
    c91_artifact: dict,
    *,
    expected_candidate_labels:
        tuple[str, ...],
) -> FrozenWorkloadPolicy:
    if not isinstance(
        c91_artifact,
        dict,
    ):
        raise TypeError(
            'c91_artifact must be dict'
        )

    if (
        c91_artifact.get('stage')
        != 'C9.1'
    ):
        raise ValueError(
            'Expected C9.1 artifact'
        )

    if (
        c91_artifact.get(
            'holdout_used_for_training'
        )
        is not False
    ):
        raise ValueError(
            'C9.2 policy cannot consume '
            'holdout-trained evidence'
        )

    if (
        c91_artifact.get(
            'c8_evidence_consumed'
        )
        is not False
    ):
        raise ValueError(
            'C9.2 policy cannot consume '
            'C8 results'
        )

    if (
        c91_artifact.get(
            'scalar_candidate_score_used'
        )
        is not False
    ):
        raise ValueError(
            'C9.2 policy source must not '
            'contain scalar ranking'
        )

    candidates = (
        c91_artifact.get(
            'candidates'
        )
    )

    if not isinstance(
        candidates,
        list,
    ):
        raise ValueError(
            'C9.1 candidates missing'
        )

    if len(candidates) != 6:
        raise ValueError(
            'Expected six frozen finalists'
        )

    labels = tuple(
        row['label']
        for row in candidates
    )

    if labels != expected_candidate_labels:
        raise ValueError(
            'Frozen finalist order/identity changed'
        )

    scorable = c91_artifact.get(
        'scorable_scenario_count'
    )

    if scorable != 51:
        raise ValueError(
            'Expected 51 scorable '
            'development workloads'
        )

    counts = {
        row['label']:
            row[
                'pareto_scenario_count'
            ]
        for row in candidates
    }

    expected_counts = {
        'pressure+lns60': 46,
        'aggressive+none': 48,
        'aggressive+lns60': 51,
        'aggressive+alns80': 49,
        'stable+none': 51,
        'stable+alns80': 50,
    }

    if counts != expected_counts:
        raise ValueError(
            'Frozen C9.1 Pareto '
            'coverage changed'
        )

    replicate = (
        c91_artifact[
            'replicate_consistency'
        ][
            'mean_pareto_jaccard'
        ]
    )

    if replicate is None:
        raise ValueError(
            'Missing replicate consistency'
        )

    if replicate < 0.90:
        raise ValueError(
            'Replicate consistency is '
            'too weak to freeze C9.2 policy'
        )

    rows_by_label = {
        row['label']: row
        for row in candidates
    }

    roles = (
        WorkloadPolicyRole(
            candidate_id=
                rows_by_label[
                    'aggressive+lns60'
                ][
                    'candidate_id'
                ],
            label=
                'aggressive+lns60',
            role=
                'robust_core',
            pareto_scenario_count=51,
            scorable_scenario_count=51,
            rationale=(
                'Pareto on every scorable '
                'development workload; strong '
                'start-delay and dependency-wait '
                'behaviour; retain as robust '
                'general-purpose core.'
            ),
        ),
        WorkloadPolicyRole(
            candidate_id=
                rows_by_label[
                    'stable+none'
                ][
                    'candidate_id'
                ],
            label=
                'stable+none',
            role=
                'robust_core',
            pareto_scenario_count=51,
            scorable_scenario_count=51,
            rationale=(
                'Pareto on every scorable '
                'development workload; simple '
                'constructor-only candidate with '
                'strong excess-session behaviour; '
                'retain as robust low-complexity core.'
            ),
        ),
        WorkloadPolicyRole(
            candidate_id=
                rows_by_label[
                    'pressure+lns60'
                ][
                    'candidate_id'
                ],
            label=
                'pressure+lns60',
            role=
                'specialist',
            pareto_scenario_count=46,
            scorable_scenario_count=51,
            rationale=(
                'Strong fragmentation and '
                'dependency-wait specialist; '
                'occasionally leaves the local '
                'Pareto frontier, so do not use '
                'as unconditional default.'
            ),
        ),
        WorkloadPolicyRole(
            candidate_id=
                rows_by_label[
                    'aggressive+alns80'
                ][
                    'candidate_id'
                ],
            label=
                'aggressive+alns80',
            role=
                'specialist',
            pareto_scenario_count=49,
            scorable_scenario_count=51,
            rationale=(
                'Strong latency/start-delay '
                'specialist; nearly universal '
                'development Pareto coverage but '
                'not sufficiently distinct to '
                'justify an automatic router.'
            ),
        ),
        WorkloadPolicyRole(
            candidate_id=
                rows_by_label[
                    'stable+alns80'
                ][
                    'candidate_id'
                ],
            label=
                'stable+alns80',
            role=
                'specialist',
            pareto_scenario_count=50,
            scorable_scenario_count=51,
            rationale=(
                'Strong deadline/excess-session '
                'specialist; misses the local '
                'frontier only rarely and remains '
                'a C10 flavour candidate.'
            ),
        ),
        WorkloadPolicyRole(
            candidate_id=
                rows_by_label[
                    'aggressive+none'
                ][
                    'candidate_id'
                ],
            label=
                'aggressive+none',
            role=
                'baseline_fallback',
            pareto_scenario_count=48,
            scorable_scenario_count=51,
            rationale=(
                'Simple aggressive constructor '
                'retained as low-complexity '
                'baseline/fallback and for '
                'measuring whether neighbourhood '
                'search adds meaningful value on '
                'real ARC workloads.'
            ),
        ),
    )

    ids = tuple(
        role.candidate_id
        for role in roles
    )

    if len(set(ids)) != 6:
        raise ValueError(
            'C9.2 role assignment must '
            'cover six unique candidates'
        )

    return FrozenWorkloadPolicy(
        roles=roles,
        automatic_router_enabled=False,
        learned_classifier_used=False,
        c8_evidence_used_for_policy=False,
    )


def workload_policy_artifact(
    policy: FrozenWorkloadPolicy,
    *,
    c91_sha256: str,
    c76_sha256: str,
) -> dict:
    if not isinstance(
        policy,
        FrozenWorkloadPolicy,
    ):
        raise TypeError(
            'policy must be FrozenWorkloadPolicy'
        )

    for value, name in (
        (
            c91_sha256,
            'c91_sha256',
        ),
        (
            c76_sha256,
            'c76_sha256',
        ),
    ):
        if (
            not isinstance(value, str)
            or len(value) != 64
            or any(
                char
                not in '0123456789abcdef'
                for char in value
            )
        ):
            raise ValueError(
                f'{name} must be lowercase SHA-256'
            )

    role_counts = {}

    for role in policy.roles:
        role_counts[
            role.role
        ] = (
            role_counts.get(
                role.role,
                0,
            )
            + 1
        )

    return {
        'schema_version': 1,
        'stage': 'C9.2',
        'purpose':
            'freeze_workload_policy_decision',
        'source_stage': 'C9.1',
        'source_c9_1_sha256':
            c91_sha256,
        'source_c7_6_sha256':
            c76_sha256,
        'candidate_count':
            len(policy.roles),
        'automatic_router_enabled':
            policy
            .automatic_router_enabled,
        'learned_classifier_used':
            policy
            .learned_classifier_used,
        'c8_evidence_used_for_policy':
            policy
            .c8_evidence_used_for_policy,
        'scalar_candidate_score_used':
            False,
        'development_only_policy':
            True,
        'role_counts':
            role_counts,
        'roles': [
            {
                'candidate_id':
                    role.candidate_id,
                'label':
                    role.label,
                'role':
                    role.role,
                'pareto_scenario_count':
                    role
                    .pareto_scenario_count,
                'scorable_scenario_count':
                    role
                    .scorable_scenario_count,
                'rationale':
                    role.rationale,
            }
            for role in policy.roles
        ],
        'c10_instruction': (
            'Carry all six frozen candidates '
            'into real-ARC/human-friendliness '
            'validation. Treat the two robust-core '
            'candidates as default candidates, '
            'specialists as explicit alternatives, '
            'and aggressive+none as baseline/fallback. '
            'Do not train an automatic workload router '
            'from C8 or C9.1.'
        ),
    }
