import pytest

from arena.generation.randomness import (
    SUBSEED_NAMES,
    derive_subseed,
    rng_for,
)
from arena.generation.spec import (
    AnchorRelation,
    DependencyLoad,
    DependencyTopology,
    GenerationSpec,
    HierarchyBranching,
    HierarchyDepth,
    PriorityAlignment,
)


def test_default_spec_is_valid():
    GenerationSpec(seed=1).validate()


@pytest.mark.parametrize("size", [16, 32, 64, 128, 256])
def test_supported_scales(size):
    GenerationSpec(seed=1, size=size).validate()


@pytest.mark.parametrize("size", [0, 1, 15, 17, 100, 512])
def test_other_scales_are_rejected(size):
    with pytest.raises(ValueError, match="workload size"):
        GenerationSpec(seed=1, size=size).validate()


@pytest.mark.parametrize("field", [
    "priority_coverage",
    "temporal_coverage",
    "anchor_coverage",
])
def test_invalid_coverage_is_rejected(field):
    kwargs = {field: 0.33}
    with pytest.raises(ValueError, match=field):
        GenerationSpec(seed=1, **kwargs).validate()


def test_flat_hierarchy_uses_neutral_branching():
    GenerationSpec(
        seed=1,
        hierarchy_depth=HierarchyDepth.FLAT,
    ).validate()

    with pytest.raises(ValueError, match="flat hierarchy"):
        GenerationSpec(
            seed=1,
            hierarchy_depth=HierarchyDepth.FLAT,
            hierarchy_branching=HierarchyBranching.NARROW,
        ).validate()


def test_dependency_none_pair_is_consistent():
    GenerationSpec(seed=1).validate()

    with pytest.raises(ValueError, match="dependency_topology"):
        GenerationSpec(
            seed=1,
            dependency_load=DependencyLoad.NONE,
            dependency_topology=DependencyTopology.CHAIN,
        ).validate()

    with pytest.raises(ValueError, match="dependency topology"):
        GenerationSpec(
            seed=1,
            dependency_load=DependencyLoad.SPARSE,
            dependency_topology=DependencyTopology.NONE,
        ).validate()


def test_zero_priority_requires_none_alignment():
    GenerationSpec(
        seed=1,
        priority_coverage=0,
        priority_alignment=PriorityAlignment.NONE,
    ).validate()

    with pytest.raises(ValueError, match="priority_alignment"):
        GenerationSpec(
            seed=1,
            priority_coverage=0,
            priority_alignment=PriorityAlignment.RANDOM,
        ).validate()


def test_positive_priority_requires_alignment():
    with pytest.raises(ValueError, match="priority alignment"):
        GenerationSpec(
            seed=1,
            priority_coverage=0.5,
            priority_alignment=PriorityAlignment.NONE,
        ).validate()


def test_urgency_alignment_requires_temporal_support():
    with pytest.raises(ValueError, match="temporal coverage"):
        GenerationSpec(
            seed=1,
            temporal_coverage=0,
            priority_alignment=PriorityAlignment.URGENCY_ALIGNED,
        ).validate()


def test_anchor_pair_is_consistent():
    GenerationSpec(seed=1).validate()

    with pytest.raises(ValueError, match="anchor_relation"):
        GenerationSpec(
            seed=1,
            anchor_coverage=0,
            anchor_relation=AnchorRelation.MIXED,
        ).validate()

    with pytest.raises(ValueError, match="anchor relation"):
        GenerationSpec(
            seed=1,
            anchor_coverage=0.5,
            anchor_relation=AnchorRelation.NONE,
        ).validate()


def test_deadline_relative_anchor_requires_temporal_support():
    with pytest.raises(ValueError, match="temporal coverage"):
        GenerationSpec(
            seed=1,
            temporal_coverage=0,
            anchor_coverage=0.5,
            anchor_relation=AnchorRelation.BEFORE,
        ).validate()


def test_subseeds_are_repeatable_and_independent():
    first = {name: derive_subseed(12345, name) for name in SUBSEED_NAMES}
    second = {name: derive_subseed(12345, name) for name in SUBSEED_NAMES}

    assert first == second
    assert len(set(first.values())) == len(SUBSEED_NAMES)


def test_different_master_seeds_change_subseeds():
    assert derive_subseed(1, "duration") != derive_subseed(2, "duration")


def test_rng_stream_is_repeatable():
    a = rng_for(999, "hierarchy")
    b = rng_for(999, "hierarchy")

    assert [a.random() for _ in range(10)] == [b.random() for _ in range(10)]


def test_unknown_rng_namespace_is_rejected():
    with pytest.raises(ValueError, match="unknown generator RNG namespace"):
        derive_subseed(1, "lol-nope")
