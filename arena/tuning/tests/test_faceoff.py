from dataclasses import replace

import pytest

from arena.tuning.contestants import (
    _semantic_fingerprint,
)
from arena.tuning.design import (
    build_c7_calibration_spec,
)
from arena.tuning.faceoff import (
    C8_FACE_OFF_SEEDS,
    C8_TRIAL_WALL_SECONDS,
    build_c8_faceoff_plan,
)
from arena.tuning.study import (
    plan_tuning_study,
)


def _plans(tmp_path):
    source = plan_tuning_study(
        build_c7_calibration_spec(
            tmp_path / 'source'
        )
    )

    fresh_spec = replace(
        source.spec,
        seeds=C8_FACE_OFF_SEEDS,
        output_root=
            tmp_path / 'fresh',
        max_trials=(
            len(source.candidates)
            * len(
                source
                .development_scenario_ids
            )
            * len(
                C8_FACE_OFF_SEEDS
            )
        ),
    )

    fresh = plan_tuning_study(
        fresh_spec
    )

    return source, fresh


def _artifact(source, candidate):
    return {
        'stage': 'C7.6',
        'purpose':
            'freeze_C8_contestant_field',
        'contestant_count': 6,
        'holdout_accessed': False,
        'holdout_scenario_ids':
            list(
                source
                .holdout_scenario_ids
            ),
        'contestants': [
            {
                'source_candidate_id':
                    candidate.candidate_id,
                'label': f'C{i}',
                'witness_metrics': ['m'],
                'semantic_fingerprint':
                    _semantic_fingerprint(
                        candidate
                    ),
            }
            for i in range(6)
        ],
    }


def test_c8_plan_uses_only_fresh_holdout_cells(
    tmp_path,
):
    source, fresh = _plans(
        tmp_path
    )

    candidates = (
        source.candidates[:6]
    )

    artifact = {
        'stage': 'C7.6',
        'purpose':
            'freeze_C8_contestant_field',
        'contestant_count': 6,
        'holdout_accessed': False,
        'holdout_scenario_ids':
            list(
                source
                .holdout_scenario_ids
            ),
        'contestants': [
            {
                'source_candidate_id':
                    candidate.candidate_id,
                'label': f'C{i}',
                'witness_metrics': ['m'],
                'semantic_fingerprint':
                    _semantic_fingerprint(
                        candidate
                    ),
            }
            for i, candidate
            in enumerate(candidates)
        ],
    }

    plan = build_c8_faceoff_plan(
        source,
        fresh,
        artifact,
        output_root=
            tmp_path / 'c8',
    )

    assert plan.seeds == (
        1801,
        1802,
        1803,
    )

    assert (
        plan.trial_wall_seconds
        == 45.0
    )

    assert (
        plan.holdout_scenario_ids
        == source
        .holdout_scenario_ids
    )

    assert all(
        run.scenario_ids
        == source
        .holdout_scenario_ids
        for run in plan.run_configs
    )

    assert (
        plan.expected_trials
        == (
            6
            * len(
                source
                .holdout_scenario_ids
            )
            * 3
        )
    )


def test_c8_rejects_frozen_semantic_drift(
    tmp_path,
):
    source, fresh = _plans(
        tmp_path
    )

    candidates = (
        source.candidates[:6]
    )

    artifact = {
        'stage': 'C7.6',
        'purpose':
            'freeze_C8_contestant_field',
        'contestant_count': 6,
        'holdout_accessed': False,
        'holdout_scenario_ids':
            list(
                source
                .holdout_scenario_ids
            ),
        'contestants': [
            {
                'source_candidate_id':
                    candidate.candidate_id,
                'label': f'C{i}',
                'witness_metrics': ['m'],
                'semantic_fingerprint': (
                    '0' * 64
                    if i == 0
                    else _semantic_fingerprint(
                        candidate
                    )
                ),
            }
            for i, candidate
            in enumerate(candidates)
        ],
    }

    with pytest.raises(
        ValueError,
        match='fingerprint',
    ):
        build_c8_faceoff_plan(
            source,
            fresh,
            artifact,
            output_root=
                tmp_path / 'c8',
        )
