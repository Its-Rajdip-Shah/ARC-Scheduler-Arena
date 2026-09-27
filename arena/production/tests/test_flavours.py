from arena.production.flavours import (
    LOCK_IN,
    MONK,
    ProductionFlavour,
    flavour_contract_artifact,
    frozen_flavour_contracts,
)


def test_exactly_two_frozen_production_flavours():
    contracts = (
        frozen_flavour_contracts()
    )

    assert tuple(
        contract.flavour
        for contract in contracts
    ) == (
        ProductionFlavour.LOCK_IN,
        ProductionFlavour.MONK,
    )


def test_both_flavours_share_task_continuity():
    assert (
        LOCK_IN
        .task_continuity_required
        is True
    )

    assert (
        MONK
        .task_continuity_required
        is True
    )

    assert (
        LOCK_IN
        .task_continuity_definition
        ==
        MONK
        .task_continuity_definition
    )


def test_lock_in_and_monk_have_distinct_load_semantics():
    assert (
        LOCK_IN.load_policy
        != MONK.load_policy
    )

    assert (
        LOCK_IN.idle_day_policy
        != MONK.idle_day_policy
    )

    assert (
        LOCK_IN.overload_policy
        != MONK.overload_policy
    )


def test_flavour_preferences_are_below_hard_invariants():
    for contract in (
        LOCK_IN,
        MONK,
    ):
        assert (
            contract
            .invariant_precedence[-1]
            == "flavour_preferences"
        )

        assert (
            contract
            .invariant_precedence[0]
            ==
            "canonical_arc_state_is_authoritative"
        )


def test_artifact_is_plan_only():
    artifact = (
        flavour_contract_artifact()
    )

    assert (
        artifact["stage"]
        == "C11.1"
    )

    assert (
        artifact["flavour_count"]
        == 2
    )

    assert (
        artifact[
            "scheduler_trials_executed"
        ]
        == 0
    )

    assert (
        artifact[
            "objective_status"
        ]
        ==
        "not_yet_parameterized"
    )

    assert (
        artifact[
            "common_requirements"
        ][
            "c7_c8_c9_retuning_allowed"
        ]
        is False
    )
