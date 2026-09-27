import pytest

from arena.tuning.workload_policy import (
    freeze_workload_policy,
    workload_policy_artifact,
)


LABELS = (
    'pressure+lns60',
    'aggressive+none',
    'aggressive+lns60',
    'aggressive+alns80',
    'stable+none',
    'stable+alns80',
)


COUNTS = {
    'pressure+lns60': 46,
    'aggressive+none': 48,
    'aggressive+lns60': 51,
    'aggressive+alns80': 49,
    'stable+none': 51,
    'stable+alns80': 50,
}


def _artifact():
    return {
        'stage': 'C9.1',
        'holdout_used_for_training':
            False,
        'c8_evidence_consumed':
            False,
        'scalar_candidate_score_used':
            False,
        'scorable_scenario_count':
            51,
        'replicate_consistency': {
            'mean_pareto_jaccard':
                0.94,
        },
        'candidates': [
            {
                'candidate_id':
                    f'id-{index}',
                'label':
                    label,
                'pareto_scenario_count':
                    COUNTS[label],
            }
            for index, label
            in enumerate(LABELS)
        ],
    }


def test_policy_disables_learned_router():
    policy = freeze_workload_policy(
        _artifact(),
        expected_candidate_labels=
            LABELS,
    )

    assert (
        policy
        .automatic_router_enabled
        is False
    )

    assert (
        policy
        .learned_classifier_used
        is False
    )

    assert (
        policy
        .c8_evidence_used_for_policy
        is False
    )


def test_policy_roles_are_exact():
    policy = freeze_workload_policy(
        _artifact(),
        expected_candidate_labels=
            LABELS,
    )

    roles = {
        role.label:
            role.role
        for role in policy.roles
    }

    assert roles == {
        'aggressive+lns60':
            'robust_core',
        'stable+none':
            'robust_core',
        'pressure+lns60':
            'specialist',
        'aggressive+alns80':
            'specialist',
        'stable+alns80':
            'specialist',
        'aggressive+none':
            'baseline_fallback',
    }


def test_policy_rejects_c8_consumption():
    artifact = _artifact()

    artifact[
        'c8_evidence_consumed'
    ] = True

    with pytest.raises(
        ValueError,
        match='C8',
    ):
        freeze_workload_policy(
            artifact,
            expected_candidate_labels=
                LABELS,
        )


def test_policy_artifact_declares_no_classifier():
    policy = freeze_workload_policy(
        _artifact(),
        expected_candidate_labels=
            LABELS,
    )

    artifact = (
        workload_policy_artifact(
            policy,
            c91_sha256='a' * 64,
            c76_sha256='b' * 64,
        )
    )

    assert (
        artifact[
            'automatic_router_enabled'
        ]
        is False
    )

    assert (
        artifact[
            'learned_classifier_used'
        ]
        is False
    )

    assert (
        artifact[
            'scalar_candidate_score_used'
        ]
        is False
    )

    assert (
        artifact[
            'c8_evidence_used_for_policy'
        ]
        is False
    )
