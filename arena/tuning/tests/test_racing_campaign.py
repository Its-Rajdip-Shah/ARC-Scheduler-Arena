import json

import pytest

from arena.tuning.racing_campaign import (
    RacingCampaignSpec,
    RacingFidelityStage,
    build_racing_round_plan,
    campaign_fingerprint,
    racing_campaign_artifact,
    racing_round_plan_artifact,
    write_racing_campaign,
    write_racing_round_plan,
)
from arena.tuning.selection import C7_V1_SELECTION_POLICY


def _campaign():
    return RacingCampaignSpec(
        campaign_id='c7.4b-test',
        benchmark_manifest_sha256='a' * 64,
        development_scenario_ids=tuple(
            f'D{i:02d}'
            for i in range(1, 11)
        ),
        holdout_scenario_ids=('H1', 'H2'),
        seeds=(1701, 1702),
        initial_candidate_ids=(
            'c1',
            'c2',
            'c3',
            'c4',
        ),
        stages=(
            RacingFidelityStage(
                round_index=1,
                scenario_count=3,
                target_survivor_count=2,
            ),
            RacingFidelityStage(
                round_index=2,
                scenario_count=7,
                target_survivor_count=1,
            ),
            RacingFidelityStage(
                round_index=3,
                scenario_count=10,
                target_survivor_count=1,
            ),
        ),
        selection_policy=C7_V1_SELECTION_POLICY,
    )


def test_round_plan_uses_only_cumulative_development_prefix():
    campaign = _campaign()

    first = build_racing_round_plan(
        campaign,
        1,
        campaign.initial_candidate_ids,
    )

    assert first.scenario_ids == (
        'D01',
        'D02',
        'D03',
    )
    assert not (
        set(first.scenario_ids)
        & set(campaign.holdout_scenario_ids)
    )
    assert first.expected_trials == 4 * 3 * 2


def test_later_round_preserves_survivor_identity_and_order():
    campaign = _campaign()

    plan = build_racing_round_plan(
        campaign,
        2,
        ('c1', 'c3'),
    )

    assert plan.incoming_candidate_ids == (
        'c1',
        'c3',
    )
    assert plan.target_survivor_count == 1
    assert plan.expected_trials == 2 * 7 * 2
    assert (
        plan.decision_spec.expected_candidate_ids
        == ('c1', 'c3')
    )


def test_survivor_reordering_is_rejected():
    campaign = _campaign()

    with pytest.raises(
        ValueError,
        match='frozen candidate order',
    ):
        build_racing_round_plan(
            campaign,
            2,
            ('c3', 'c1'),
        )


def test_unknown_candidate_is_rejected():
    campaign = _campaign()

    with pytest.raises(
        ValueError,
        match='initial candidate set',
    ):
        build_racing_round_plan(
            campaign,
            2,
            ('c1', 'unknown'),
        )


def test_fidelity_must_strictly_increase():
    with pytest.raises(
        ValueError,
        match='strictly increase',
    ):
        RacingCampaignSpec(
            campaign_id='bad',
            benchmark_manifest_sha256='a' * 64,
            development_scenario_ids=(
                'D1',
                'D2',
            ),
            holdout_scenario_ids=('H1',),
            seeds=(1,),
            initial_candidate_ids=('c1', 'c2'),
            stages=(
                RacingFidelityStage(1, 1, 2),
                RacingFidelityStage(2, 1, 1),
            ),
            selection_policy=C7_V1_SELECTION_POLICY,
        )


def test_stage_cannot_reach_holdout_by_count():
    with pytest.raises(
        ValueError,
        match='development scenario count',
    ):
        RacingCampaignSpec(
            campaign_id='bad',
            benchmark_manifest_sha256='a' * 64,
            development_scenario_ids=('D1',),
            holdout_scenario_ids=('H1',),
            seeds=(1,),
            initial_candidate_ids=('c1',),
            stages=(
                RacingFidelityStage(1, 2, 1),
            ),
            selection_policy=C7_V1_SELECTION_POLICY,
        )


def test_target_is_advisory_when_incoming_field_is_smaller():
    campaign = _campaign()

    plan = build_racing_round_plan(
        campaign,
        1,
        ('c1',),
    )

    assert plan.target_survivor_count == 1


def test_campaign_fingerprint_is_deterministic():
    first = _campaign()
    second = _campaign()

    assert campaign_fingerprint(first) == campaign_fingerprint(second)

    artifact = racing_campaign_artifact(first)

    assert artifact['stage'] == 'C7.4b'
    assert artifact['initial_candidate_ids'] == [
        'c1',
        'c2',
        'c3',
        'c4',
    ]


def test_artifacts_are_written_exclusively(tmp_path):
    campaign = _campaign()

    campaign_path = tmp_path / 'campaign.json'

    write_racing_campaign(
        campaign,
        campaign_path,
    )

    loaded = json.loads(
        campaign_path.read_text(encoding='utf-8')
    )

    assert loaded == racing_campaign_artifact(campaign)

    with pytest.raises(FileExistsError):
        write_racing_campaign(
            campaign,
            campaign_path,
        )

    plan = build_racing_round_plan(
        campaign,
        1,
        campaign.initial_candidate_ids,
    )

    plan_path = tmp_path / 'round_01_plan.json'

    write_racing_round_plan(
        plan,
        plan_path,
    )

    loaded_plan = json.loads(
        plan_path.read_text(encoding='utf-8')
    )

    assert loaded_plan == racing_round_plan_artifact(plan)

    with pytest.raises(FileExistsError):
        write_racing_round_plan(
            plan,
            plan_path,
        )
