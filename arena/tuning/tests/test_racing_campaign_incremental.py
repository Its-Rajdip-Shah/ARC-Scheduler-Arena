from arena.tuning.racing_campaign import (
    RacingCampaignSpec,
    RacingFidelityStage,
    build_racing_round_plan,
)
from arena.tuning.selection import C7_V1_SELECTION_POLICY


def _campaign():
    return RacingCampaignSpec(
        campaign_id="incremental-test",
        benchmark_manifest_sha256="a" * 64,
        development_scenario_ids=tuple(
            f"D{i:02d}" for i in range(1, 95)
        ),
        holdout_scenario_ids=tuple(
            f"H{i:02d}" for i in range(1, 25)
        ),
        seeds=(1701,),
        initial_candidate_ids=tuple(
            f"c{i:02d}" for i in range(1, 61)
        ),
        stages=(
            RacingFidelityStage(1, 24, 30),
            RacingFidelityStage(2, 48, 15),
            RacingFidelityStage(3, 72, 8),
            RacingFidelityStage(4, 94, 4),
        ),
        selection_policy=C7_V1_SELECTION_POLICY,
    )


def test_round_one_executes_entire_first_fidelity():
    campaign = _campaign()

    plan = build_racing_round_plan(
        campaign,
        1,
        campaign.initial_candidate_ids,
    )

    assert len(plan.scenario_ids) == 24
    assert len(plan.incremental_scenario_ids) == 24
    assert plan.expected_trials == 1440
    assert plan.incremental_expected_trials == 1440


def test_round_two_executes_only_new_scenario_suffix():
    campaign = _campaign()

    survivors = campaign.initial_candidate_ids[:30]

    plan = build_racing_round_plan(
        campaign,
        2,
        survivors,
    )

    assert plan.scenario_ids == (
        campaign.development_scenario_ids[:48]
    )

    assert plan.incremental_scenario_ids == (
        campaign.development_scenario_ids[24:48]
    )

    assert plan.expected_trials == 1440
    assert plan.incremental_expected_trials == 720


def test_round_three_executes_only_24_new_scenarios():
    campaign = _campaign()

    survivors = campaign.initial_candidate_ids[:15]

    plan = build_racing_round_plan(
        campaign,
        3,
        survivors,
    )

    assert len(plan.scenario_ids) == 72
    assert len(plan.incremental_scenario_ids) == 24
    assert plan.expected_trials == 1080
    assert plan.incremental_expected_trials == 360


def test_final_round_executes_only_remaining_22_scenarios():
    campaign = _campaign()

    survivors = campaign.initial_candidate_ids[:8]

    plan = build_racing_round_plan(
        campaign,
        4,
        survivors,
    )

    assert len(plan.scenario_ids) == 94
    assert len(plan.incremental_scenario_ids) == 22
    assert plan.expected_trials == 752
    assert plan.incremental_expected_trials == 176


def test_nominal_incremental_campaign_is_2696_trials():
    campaign = _campaign()

    incoming_counts = (60, 30, 15, 8)

    total = 0

    for stage, incoming_count in zip(
        campaign.stages,
        incoming_counts,
    ):
        incoming = campaign.initial_candidate_ids[
            :incoming_count
        ]

        plan = build_racing_round_plan(
            campaign,
            stage.round_index,
            incoming,
        )

        total += plan.incremental_expected_trials

    assert total == 2696


def test_incremental_sets_never_touch_holdout():
    campaign = _campaign()

    incoming_counts = (60, 30, 15, 8)

    for stage, incoming_count in zip(
        campaign.stages,
        incoming_counts,
    ):
        plan = build_racing_round_plan(
            campaign,
            stage.round_index,
            campaign.initial_candidate_ids[
                :incoming_count
            ],
        )

        assert not (
            set(plan.incremental_scenario_ids)
            & set(campaign.holdout_scenario_ids)
        )
