from __future__ import annotations

from dataclasses import replace

import pytest

from arena.benchmarks.reconstruct import (
    BenchmarkDriftError,
    assert_phi89_matches,
    load_v1_scenarios,
    reconstruct_scenario,
)
from arena.generation.spec import GenerationSpec


def test_v1_loads_118_typed_scenarios():
    scenarios = load_v1_scenarios()

    assert len(scenarios) == 118
    assert len({
        scenario.scenario_id
        for scenario in scenarios
    }) == 118

    assert all(
        isinstance(scenario.spec, GenerationSpec)
        for scenario in scenarios
    )

    assert all(
        scenario.spec.seed == scenario.seed
        for scenario in scenarios
    )

    assert all(
        len(scenario.frozen_features) == 89
        for scenario in scenarios
    )


def test_phi89_guard_accepts_identical_mapping():
    scenario = load_v1_scenarios()[0]

    assert_phi89_matches(
        scenario.frozen_features,
        dict(scenario.frozen_features),
        scenario_id=scenario.scenario_id,
    )


def test_phi89_guard_rejects_schema_drift():
    scenario = load_v1_scenarios()[0]
    regenerated = dict(scenario.frozen_features)
    regenerated.pop(next(iter(regenerated)))

    with pytest.raises(
        BenchmarkDriftError,
        match="schema drift",
    ):
        assert_phi89_matches(
            scenario.frozen_features,
            regenerated,
            scenario_id=scenario.scenario_id,
        )


def test_phi89_guard_rejects_semantic_drift():
    scenario = load_v1_scenarios()[0]
    regenerated = dict(scenario.frozen_features)

    name = next(
        key
        for key, value in regenerated.items()
        if isinstance(value, (int, float))
        and not isinstance(value, bool)
    )

    regenerated[name] = regenerated[name] + 1

    with pytest.raises(
        BenchmarkDriftError,
        match="semantic drift",
    ):
        assert_phi89_matches(
            scenario.frozen_features,
            regenerated,
            scenario_id=scenario.scenario_id,
        )


@pytest.mark.django_db
def test_real_v1_scenario_reconstructs_and_matches_phi89():
    scenario = load_v1_scenarios()[0]

    reconstructed = reconstruct_scenario(
        scenario,
        email="arena-v1-c02-first@local.test",
    )

    assert reconstructed.frozen == scenario
    assert (
        reconstructed.regenerated_features
        == scenario.frozen_features
    )

    assert reconstructed.problem.items


@pytest.mark.django_db
def test_modified_seed_is_caught_by_phi89_guard():
    scenario = load_v1_scenarios()[0]

    drifted = replace(
        scenario,
        spec=replace(
            scenario.spec,
            seed=scenario.seed + 987654,
        ),
    )

    with pytest.raises(
        BenchmarkDriftError,
        match="semantic drift",
    ):
        reconstruct_scenario(
            drifted,
            email="arena-v1-c02-drift@local.test",
        )


def test_v1_replicate_and_seed_provenance():
    scenarios = load_v1_scenarios()

    assert all(
        scenario.replicate_index in {0, 1}
        for scenario in scenarios
    )

    assert all(
        scenario.scenario_id
        == (
            f"G{scenario.design_index:03d}"
            f"-R{scenario.replicate_index}"
        )
        for scenario in scenarios
    )

    # Frozen V1 corpus seed contract:
    # design 0 -> 100000/100001,
    # design 1 -> 100100/100101, etc.
    assert all(
        scenario.seed
        == (
            100000
            + scenario.design_index * 100
            + scenario.replicate_index
        )
        for scenario in scenarios
    )

