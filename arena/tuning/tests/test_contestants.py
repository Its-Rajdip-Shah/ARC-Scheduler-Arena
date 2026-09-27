from dataclasses import dataclass

import pytest

from arena.tuning.contestants import (
    c8_contestant_artifact,
    freeze_c8_contestants,
)
from arena.tuning.design import (
    build_c7_calibration_spec,
)
from arena.tuning.study import (
    plan_tuning_study,
)


def _plan(tmp_path):
    return plan_tuning_study(
        build_c7_calibration_spec(
            tmp_path / 'plan'
        )
    )


def test_freeze_preserves_requested_order_and_identity(
    tmp_path,
):
    plan = _plan(tmp_path)

    selected = tuple(
        candidate.candidate_id
        for candidate
        in plan.candidates[:2]
    )

    field = freeze_c8_contestants(
        source_candidates=
            plan.candidates,
        shortlisted_candidate_ids=
            selected,
        labels={
            selected[0]: 'A',
            selected[1]: 'B',
        },
        witness_metrics={
            selected[0]: ('m1',),
            selected[1]: ('m2',),
        },
        holdout_scenario_ids=
            plan.holdout_scenario_ids,
    )

    assert tuple(
        contestant.source_candidate_id
        for contestant
        in field.contestants
    ) == selected

    assert len({
        contestant.semantic_fingerprint
        for contestant
        in field.contestants
    }) == 2


def test_every_contestant_requires_witness(
    tmp_path,
):
    plan = _plan(tmp_path)

    candidate_id = (
        plan.candidates[0].candidate_id
    )

    with pytest.raises(
        ValueError,
        match='witness',
    ):
        freeze_c8_contestants(
            source_candidates=
                plan.candidates,
            shortlisted_candidate_ids=(
                candidate_id,
            ),
            labels={
                candidate_id: 'A',
            },
            witness_metrics={
                candidate_id: (),
            },
            holdout_scenario_ids=
                plan.holdout_scenario_ids,
        )


def test_artifact_declares_no_new_selection(
    tmp_path,
):
    plan = _plan(tmp_path)

    candidate_id = (
        plan.candidates[0].candidate_id
    )

    field = freeze_c8_contestants(
        source_candidates=
            plan.candidates,
        shortlisted_candidate_ids=(
            candidate_id,
        ),
        labels={
            candidate_id: 'A',
        },
        witness_metrics={
            candidate_id: ('m1',),
        },
        holdout_scenario_ids=
            plan.holdout_scenario_ids,
    )

    artifact = c8_contestant_artifact(
        field,
        c75_shortlist_sha256=
            'a' * 64,
        c74c_evidence_sha256=
            'b' * 64,
    )

    assert (
        artifact[
            'additional_development_selection'
        ]
        is False
    )

    assert (
        artifact[
            'scalar_ranking_used'
        ]
        is False
    )

    assert (
        artifact[
            'holdout_accessed'
        ]
        is False
    )
