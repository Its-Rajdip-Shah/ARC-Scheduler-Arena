import math

import pytest

from planning.models import DurationCategory

from arena.generation.blueprint import (
    DURATION_CATEGORIES,
    DURATION_PROFILE_WEIGHTS,
    _largest_remainder_counts,
    _minimum_frontier,
    build_blueprint,
)
from arena.generation.spec import (
    DurationProfile,
    ExpiredAnchorHistory,
    GenerationSpec,
    HierarchyBranching,
    HierarchyDepth,
    PriorityAlignment,
)


def spec_for(**changes):
    base = dict(seed=123, priority_coverage=0, priority_alignment=PriorityAlignment.NONE)
    base.update(changes)
    return GenerationSpec(**base)


@pytest.mark.parametrize("size", [16, 32, 64, 128, 256])
def test_blueprint_has_exact_requested_size(size):
    bp = build_blueprint(spec_for(size=size))
    assert len(bp.items) == size


def test_same_spec_is_exactly_deterministic():
    spec = spec_for(seed=987654, size=64)
    assert build_blueprint(spec) == build_blueprint(spec)


def test_different_hierarchy_seed_changes_structure():
    a = build_blueprint(spec_for(seed=1, size=64))
    b = build_blueprint(spec_for(seed=2, size=64))
    assert [x.parent_key for x in a.items] != [x.parent_key for x in b.items]


def test_keys_are_stable_and_unique():
    bp = build_blueprint(spec_for(size=32))
    assert [x.key for x in bp.items] == [
        f"item-{i:04d}" for i in range(32)
    ]


def test_all_parent_references_point_backward():
    bp = build_blueprint(spec_for(size=128))
    index = {item.key: i for i, item in enumerate(bp.items)}

    for i, item in enumerate(bp.items):
        if item.parent_key is not None:
            assert index[item.parent_key] < i


def test_recorded_depth_matches_parent_chain():
    bp = build_blueprint(spec_for(size=128))
    by_key = {item.key: item for item in bp.items}

    for item in bp.items:
        depth = 0
        current = item
        while current.parent_key is not None:
            depth += 1
            current = by_key[current.parent_key]
        assert depth == item.depth


def test_flat_hierarchy_is_entirely_frontier():
    bp = build_blueprint(
        spec_for(
            size=64,
            hierarchy_depth=HierarchyDepth.FLAT,
            hierarchy_branching=HierarchyBranching.BALANCED,
        )
    )
    assert bp.max_depth == 0
    assert all(item.parent_key is None for item in bp.items)
    assert len(bp.frontier) == 64


@pytest.mark.parametrize("size", [16, 32, 64, 128, 256])
@pytest.mark.parametrize(
    "depth",
    [
        HierarchyDepth.SHALLOW,
        HierarchyDepth.MEDIUM,
        HierarchyDepth.DEEP,
    ],
)
@pytest.mark.parametrize(
    "branching",
    [
        HierarchyBranching.NARROW,
        HierarchyBranching.BALANCED,
        HierarchyBranching.BROAD,
    ],
)
def test_frontier_floor_is_always_preserved(size, depth, branching):
    bp = build_blueprint(
        spec_for(
            size=size,
            hierarchy_depth=depth,
            hierarchy_branching=branching,
        )
    )
    assert len(bp.frontier) >= _minimum_frontier(size)


@pytest.mark.parametrize(
    "depth,limit",
    [
        (HierarchyDepth.FLAT, lambda n: 0),
        (HierarchyDepth.SHALLOW, lambda n: 2),
        (HierarchyDepth.MEDIUM, lambda n: math.ceil(math.log2(n))),
        (HierarchyDepth.DEEP, lambda n: min(12, n // 4)),
    ],
)
def test_hierarchy_never_exceeds_regime_depth(depth, limit):
    bp = build_blueprint(
        spec_for(
            size=64,
            hierarchy_depth=depth,
            hierarchy_branching=HierarchyBranching.BALANCED,
        )
    )
    assert bp.max_depth <= limit(64)


def test_narrow_and_broad_preserve_depth_but_change_geometry():
    narrow = build_blueprint(
        spec_for(
            size=128,
            seed=77,
            hierarchy_depth=HierarchyDepth.DEEP,
            hierarchy_branching=HierarchyBranching.NARROW,
        )
    )
    broad = build_blueprint(
        spec_for(
            size=128,
            seed=77,
            hierarchy_depth=HierarchyDepth.DEEP,
            hierarchy_branching=HierarchyBranching.BROAD,
        )
    )

    # Depth and branching are intentionally independent controls.
    assert narrow.max_depth == broad.max_depth == 12

    narrow_parents = tuple(item.parent_key for item in narrow.items)
    broad_parents = tuple(item.parent_key for item in broad.items)

    # Branching still changes the hierarchy's actual geometry.
    assert narrow_parents != broad_parents


def test_duration_vocabulary_is_exactly_frozen_arc_vocabulary():
    assert DURATION_CATEGORIES == (
        DurationCategory.UNDER_20_MINUTES,
        DurationCategory.UNDER_1_HOUR,
        DurationCategory.UNDER_4_HOURS,
        DurationCategory.UNDER_8_HOURS,
        DurationCategory.UNDER_16_HOURS,
        DurationCategory.OVER_16_HOURS,
    )


@pytest.mark.parametrize("profile", list(DurationProfile))
@pytest.mark.parametrize("size", [16, 32, 64, 128, 256])
def test_duration_allocation_matches_largest_remainder(profile, size):
    spec = spec_for(
        seed=42,
        size=size,
        duration_profile=profile,
    )
    bp = build_blueprint(spec)

    expected = _largest_remainder_counts(
        size,
        DURATION_PROFILE_WEIGHTS[profile],
    )

    actual = [
        sum(item.duration_category == str(category) for item in bp.items)
        for category in DURATION_CATEGORIES
    ]

    assert actual == expected
    assert sum(actual) == size


def test_duration_shuffle_is_repeatable():
    spec = spec_for(seed=1234, size=128, duration_profile=DurationProfile.BIMODAL)
    a = build_blueprint(spec)
    b = build_blueprint(spec)

    assert [x.duration_category for x in a.items] == [
        x.duration_category for x in b.items
    ]


def test_duration_rng_is_independent_of_hierarchy_choice():
    a = build_blueprint(
        spec_for(
            seed=555,
            size=128,
            hierarchy_depth=HierarchyDepth.SHALLOW,
            hierarchy_branching=HierarchyBranching.NARROW,
        )
    )
    b = build_blueprint(
        spec_for(
            seed=555,
            size=128,
            hierarchy_depth=HierarchyDepth.DEEP,
            hierarchy_branching=HierarchyBranching.BROAD,
        )
    )

    assert [x.duration_category for x in a.items] == [
        x.duration_category for x in b.items
    ]


def test_largest_remainder_is_exact_and_deterministic():
    weights = (0.40, 0.35, 0.15, 0.06, 0.03, 0.01)
    assert _largest_remainder_counts(16, weights) == [6, 6, 2, 1, 1, 0]
    assert sum(_largest_remainder_counts(257, weights)) == 257


@pytest.mark.django_db
def test_blueprint_construction_does_not_touch_database(django_assert_num_queries):
    with django_assert_num_queries(0):
        build_blueprint(spec_for(size=256, seed=999))


@pytest.mark.parametrize("size", [16, 32, 64, 128, 256])
@pytest.mark.parametrize(
    "depth",
    [
        HierarchyDepth.SHALLOW,
        HierarchyDepth.MEDIUM,
        HierarchyDepth.DEEP,
    ],
)
@pytest.mark.parametrize(
    "branching",
    [
        HierarchyBranching.NARROW,
        HierarchyBranching.BALANCED,
        HierarchyBranching.BROAD,
    ],
)
def test_nonflat_regimes_reach_their_exact_target_depth(size, depth, branching):
    spec = spec_for(
        size=size,
        hierarchy_depth=depth,
        hierarchy_branching=branching,
    )
    bp = build_blueprint(spec)

    if depth is HierarchyDepth.SHALLOW:
        expected = 2
    elif depth is HierarchyDepth.MEDIUM:
        expected = math.ceil(math.log2(size))
    else:
        expected = min(12, size // 4)

    assert bp.max_depth == expected


@pytest.mark.parametrize(
    "branching",
    [
        HierarchyBranching.NARROW,
        HierarchyBranching.BALANCED,
        HierarchyBranching.BROAD,
    ],
)
def test_every_branching_regime_has_real_hierarchy(branching):
    bp = build_blueprint(
        spec_for(
            size=128,
            hierarchy_depth=HierarchyDepth.DEEP,
            hierarchy_branching=branching,
        )
    )

    assert bp.max_depth == 12
    assert len(bp.frontier) < len(bp.items)


def test_branching_regimes_produce_distinct_parent_geometries():
    blueprints = {
        branching: build_blueprint(
            spec_for(
                size=128,
                seed=2026,
                hierarchy_depth=HierarchyDepth.DEEP,
                hierarchy_branching=branching,
            )
        )
        for branching in (
            HierarchyBranching.NARROW,
            HierarchyBranching.BALANCED,
            HierarchyBranching.BROAD,
        )
    }

    signatures = {
        branching: tuple(item.parent_key for item in bp.items)
        for branching, bp in blueprints.items()
    }

    assert len(set(signatures.values())) == 3


def test_branching_change_does_not_change_duration_assignment():
    blueprints = [
        build_blueprint(
            spec_for(
                size=128,
                seed=2026,
                hierarchy_depth=HierarchyDepth.DEEP,
                hierarchy_branching=branching,
                duration_profile=DurationProfile.BIMODAL,
            )
        )
        for branching in (
            HierarchyBranching.NARROW,
            HierarchyBranching.BALANCED,
            HierarchyBranching.BROAD,
        )
    ]

    duration_vectors = [
        tuple(item.duration_category for item in bp.items)
        for bp in blueprints
    ]

    assert duration_vectors[0] == duration_vectors[1] == duration_vectors[2]


# ---------------------------------------------------------------------------
# PASS 1C — dependency DAG generation
# ---------------------------------------------------------------------------

from arena.generation.spec import DependencyLoad, DependencyTopology


def dependency_spec(**changes):
    base = dict(
        size=128,
        seed=2026,
        dependency_load=DependencyLoad.MODERATE,
        dependency_topology=DependencyTopology.RANDOM_DAG,
    )
    base.update(changes)
    return spec_for(**base)


def _assert_dependency_dag(bp):
    frontier = {item.key for item in bp.frontier}

    assert all(
        edge.prerequisite_key in frontier
        and edge.dependent_key in frontier
        and edge.prerequisite_key != edge.dependent_key
        for edge in bp.dependencies
    )

    assert len({
        (edge.prerequisite_key, edge.dependent_key)
        for edge in bp.dependencies
    }) == len(bp.dependencies)

    incoming = {key: 0 for key in frontier}
    outgoing = {key: [] for key in frontier}

    for edge in bp.dependencies:
        incoming[edge.dependent_key] += 1
        outgoing[edge.prerequisite_key].append(edge.dependent_key)

    ready = [key for key, degree in incoming.items() if degree == 0]
    visited = 0

    while ready:
        node = ready.pop()
        visited += 1
        for target in outgoing[node]:
            incoming[target] -= 1
            if incoming[target] == 0:
                ready.append(target)

    assert visited == len(frontier)


def test_none_dependency_regime_produces_no_edges():
    bp = build_blueprint(spec_for())
    assert bp.dependencies == ()


@pytest.mark.parametrize(
    "load",
    [
        DependencyLoad.SPARSE,
        DependencyLoad.MODERATE,
        DependencyLoad.HEAVY,
    ],
)
@pytest.mark.parametrize(
    "topology",
    [
        DependencyTopology.RANDOM_DAG,
        DependencyTopology.CHAIN,
        DependencyTopology.LAYERED,
        DependencyTopology.FAN_IN,
        DependencyTopology.FAN_OUT,
    ],
)
def test_every_dependency_regime_is_a_valid_frontier_dag(load, topology):
    bp = build_blueprint(
        dependency_spec(
            dependency_load=load,
            dependency_topology=topology,
        )
    )
    assert bp.dependencies
    _assert_dependency_dag(bp)


@pytest.mark.parametrize(
    "topology",
    [
        DependencyTopology.RANDOM_DAG,
        DependencyTopology.CHAIN,
        DependencyTopology.LAYERED,
        DependencyTopology.FAN_IN,
        DependencyTopology.FAN_OUT,
    ],
)
def test_dependency_load_monotonically_controls_edge_count(topology):
    counts = []

    for load in (
        DependencyLoad.SPARSE,
        DependencyLoad.MODERATE,
        DependencyLoad.HEAVY,
    ):
        bp = build_blueprint(
            dependency_spec(
                dependency_load=load,
                dependency_topology=topology,
            )
        )
        counts.append(len(bp.dependencies))

    assert counts[0] < counts[1] < counts[2]


def test_same_dependency_spec_is_exactly_deterministic():
    spec = dependency_spec(
        seed=998877,
        dependency_load=DependencyLoad.HEAVY,
        dependency_topology=DependencyTopology.LAYERED,
    )
    assert build_blueprint(spec) == build_blueprint(spec)


def test_dependency_seed_changes_dependency_graph():
    a = build_blueprint(dependency_spec(seed=1))
    b = build_blueprint(dependency_spec(seed=2))

    assert a.dependencies != b.dependencies


def test_dependency_settings_do_not_change_hierarchy_or_duration():
    baseline = build_blueprint(spec_for(size=128, seed=55))

    dependent = build_blueprint(
        dependency_spec(
            size=128,
            seed=55,
            dependency_load=DependencyLoad.HEAVY,
            dependency_topology=DependencyTopology.FAN_IN,
        )
    )

    assert [
        (item.key, item.parent_key, item.depth, item.duration_category)
        for item in baseline.items
    ] == [
        (item.key, item.parent_key, item.depth, item.duration_category)
        for item in dependent.items
    ]


def test_topology_changes_graph_without_changing_edge_budget():
    graphs = {}

    for topology in (
        DependencyTopology.RANDOM_DAG,
        DependencyTopology.CHAIN,
        DependencyTopology.LAYERED,
        DependencyTopology.FAN_IN,
        DependencyTopology.FAN_OUT,
    ):
        bp = build_blueprint(
            dependency_spec(
                dependency_load=DependencyLoad.MODERATE,
                dependency_topology=topology,
            )
        )
        graphs[topology] = {
            (edge.prerequisite_key, edge.dependent_key)
            for edge in bp.dependencies
        }

    assert len({len(graph) for graph in graphs.values()}) == 1
    assert len({frozenset(graph) for graph in graphs.values()}) > 1


def test_chain_topology_creates_long_dependency_path():
    bp = build_blueprint(
        dependency_spec(
            size=128,
            dependency_load=DependencyLoad.HEAVY,
            dependency_topology=DependencyTopology.CHAIN,
        )
    )

    outgoing = {}
    for edge in bp.dependencies:
        outgoing.setdefault(edge.prerequisite_key, []).append(edge.dependent_key)

    memo = {}

    def longest(node):
        if node not in memo:
            memo[node] = max(
                (1 + longest(target) for target in outgoing.get(node, [])),
                default=0,
            )
        return memo[node]

    assert max((longest(item.key) for item in bp.frontier), default=0) >= 2


@pytest.mark.django_db
def test_dependency_blueprint_construction_still_does_not_touch_database(
    django_assert_num_queries,
):
    spec = dependency_spec(
        size=256,
        dependency_load=DependencyLoad.HEAVY,
        dependency_topology=DependencyTopology.LAYERED,
    )

    with django_assert_num_queries(0):
        build_blueprint(spec)


# ---------------------------------------------------------------------------
# PASS 1D — priority / temporal / anchor / lifecycle
# ---------------------------------------------------------------------------

from arena.generation.spec import (
    ActionableParentCoverage,
    AnchorRelation,
    Heterogeneity,
    LifecycleProfile,
    PriorityAlignment,
    TemporalPressure,
    TemporalShape,
)


def test_priority_coverage_is_frontier_based_and_dense():
    bp = build_blueprint(spec_for(
        size=128,
        priority_coverage=0.5,
        priority_alignment=PriorityAlignment.RANDOM,
    ))

    prioritized = [
        item for item in bp.frontier
        if item.priority_position is not None
    ]

    assert len(prioritized) == round(len(bp.frontier) * 0.5)
    assert sorted(item.priority_position for item in prioritized) == list(
        range(1, len(prioritized) + 1)
    )


def test_zero_priority_coverage_produces_no_priority():
    bp = build_blueprint(spec_for(
        priority_coverage=0,
        priority_alignment=PriorityAlignment.NONE,
    ))
    assert all(item.priority_position is None for item in bp.items)


def test_temporal_coverage_is_frontier_only():
    bp = build_blueprint(spec_for(
        size=128,
        temporal_coverage=0.5,
        temporal_pressure=TemporalPressure.MIXED,
    ))

    frontier_keys = {item.key for item in bp.frontier}
    constrained = [
        item for item in bp.items
        if item.start_date is not None or item.due_date is not None
    ]

    assert all(item.key in frontier_keys for item in constrained)
    assert sum(item.due_date is not None for item in bp.frontier) == round(
        len(bp.frontier) * 0.5
    )


def test_temporal_pressure_changes_dates_not_structure():
    relaxed = build_blueprint(spec_for(
        seed=88,
        temporal_coverage=1.0,
        temporal_pressure=TemporalPressure.RELAXED,
    ))
    urgent = build_blueprint(spec_for(
        seed=88,
        temporal_coverage=1.0,
        temporal_pressure=TemporalPressure.URGENT,
    ))

    assert [
        (x.key, x.parent_key, x.depth, x.duration_category)
        for x in relaxed.items
    ] == [
        (x.key, x.parent_key, x.depth, x.duration_category)
        for x in urgent.items
    ]

    assert [x.due_date for x in relaxed.frontier] != [
        x.due_date for x in urgent.frontier
    ]


@pytest.mark.parametrize(
    "relation",
    [
        AnchorRelation.BEFORE,
        AnchorRelation.SAME,
        AnchorRelation.AFTER,
        AnchorRelation.MIXED,
    ],
)
def test_anchor_generation_is_frontier_only(relation):
    bp = build_blueprint(spec_for(
        size=128,
        temporal_coverage=1.0,
        temporal_pressure=TemporalPressure.MIXED,
        anchor_coverage=0.5,
        anchor_relation=relation,
    ))

    frontier_keys = {item.key for item in bp.frontier}
    anchored = [
        item for item in bp.items
        if item.manual_requested_date is not None
    ]

    assert anchored
    assert all(item.key in frontier_keys for item in anchored)


def test_anchor_relations_have_exact_direction():
    for relation in (
        AnchorRelation.BEFORE,
        AnchorRelation.SAME,
        AnchorRelation.AFTER,
    ):
        bp = build_blueprint(spec_for(
            size=64,
            temporal_coverage=1.0,
            anchor_coverage=1.0,
            anchor_relation=relation,
        ))

        anchored = [
            item for item in bp.frontier
            if item.manual_requested_date is not None
        ]
        assert anchored

        for item in anchored:
            assert item.due_date is not None
            if relation is AnchorRelation.BEFORE:
                assert item.manual_requested_date < item.due_date
            elif relation is AnchorRelation.SAME:
                assert item.manual_requested_date == item.due_date
            else:
                assert item.manual_requested_date > item.due_date


@pytest.mark.parametrize("profile", list(LifecycleProfile))
@pytest.mark.parametrize("heterogeneity", list(Heterogeneity))
def test_lifecycle_state_is_canonical_and_frontier_only(profile, heterogeneity):
    bp = build_blueprint(spec_for(
        lifecycle=profile,
        heterogeneity=heterogeneity,
    ))

    frontier_keys = {item.key for item in bp.frontier}

    for item in bp.items:
        assert 0 <= item.percent_completed <= 100

        if item.is_completed:
            assert item.percent_completed == 100

        if item.key not in frontier_keys:
            assert item.percent_completed == 0
            assert item.is_completed is False


def test_remaining_dimensions_are_deterministic():
    spec = spec_for(
        seed=123456,
        size=128,
        priority_coverage=0.75,
        priority_alignment=PriorityAlignment.URGENCY_ALIGNED,
        temporal_coverage=1.0,
        temporal_pressure=TemporalPressure.COMPRESSED,
        anchor_coverage=0.5,
        anchor_relation=AnchorRelation.MIXED,
        lifecycle=LifecycleProfile.MIXED,
        heterogeneity=Heterogeneity.MIXED,
    )

    assert build_blueprint(spec) == build_blueprint(spec)


def test_remaining_dimensions_do_not_change_frozen_structure_duration_dependencies():
    baseline = build_blueprint(spec_for(
        seed=31415,
        size=128,
        priority_coverage=0,
        priority_alignment=PriorityAlignment.NONE,
        temporal_coverage=0,
        anchor_coverage=0,
        anchor_relation=AnchorRelation.NONE,
        lifecycle=LifecycleProfile.FRESH,
        heterogeneity=Heterogeneity.HOMOGENEOUS,
        dependency_load=DependencyLoad.MODERATE,
        dependency_topology=DependencyTopology.RANDOM_DAG,
    ))

    varied = build_blueprint(spec_for(
        seed=31415,
        size=128,
        priority_coverage=1.0,
        priority_alignment=PriorityAlignment.URGENCY_ALIGNED,
        temporal_coverage=1.0,
        temporal_pressure=TemporalPressure.URGENT,
        anchor_coverage=1.0,
        anchor_relation=AnchorRelation.MIXED,
        lifecycle=LifecycleProfile.MIXED,
        heterogeneity=Heterogeneity.MIXED,
        dependency_load=DependencyLoad.MODERATE,
        dependency_topology=DependencyTopology.RANDOM_DAG,
    ))

    frozen_a = [
        (x.key, x.parent_key, x.depth, x.duration_category)
        for x in baseline.items
    ]
    frozen_b = [
        (x.key, x.parent_key, x.depth, x.duration_category)
        for x in varied.items
    ]

    assert frozen_a == frozen_b
    assert baseline.dependencies == varied.dependencies


@pytest.mark.django_db
def test_remaining_pure_generation_does_not_touch_database(
    django_assert_num_queries,
):
    spec = spec_for(
        size=256,
        priority_coverage=1.0,
        priority_alignment=PriorityAlignment.URGENCY_ALIGNED,
        temporal_coverage=1.0,
        temporal_pressure=TemporalPressure.OVERDUE_MIXED,
        anchor_coverage=1.0,
        anchor_relation=AnchorRelation.MIXED,
        lifecycle=LifecycleProfile.COMPLETION_HEAVY,
        heterogeneity=Heterogeneity.MIXED,
        dependency_load=DependencyLoad.HEAVY,
        dependency_topology=DependencyTopology.LAYERED,
    )

    with django_assert_num_queries(0):
        build_blueprint(spec)


# ---------------------------------------------------------------------------
# PASS 1D.1 — cross-domain canonical composition
# ---------------------------------------------------------------------------

from planning.models import ATOMIC_DURATION_CATEGORIES


def _atomic_duration_values():
    return {
        value.value if hasattr(value, "value") else str(value)
        for value in ATOMIC_DURATION_CATEGORIES
    }


@pytest.mark.parametrize(
    "profile",
    [
        LifecycleProfile.EARLY,
        LifecycleProfile.MIXED,
        LifecycleProfile.ADVANCED,
        LifecycleProfile.COMPLETION_HEAVY,
    ],
)
@pytest.mark.parametrize(
    "heterogeneity",
    list(Heterogeneity),
)
def test_atomic_unfinished_work_has_zero_partial_progress(
    profile,
    heterogeneity,
):
    bp = build_blueprint(spec_for(
        seed=917,
        size=128,
        lifecycle=profile,
        heterogeneity=heterogeneity,
    ))

    atomic = _atomic_duration_values()

    for item in bp.frontier:
        if item.duration_category in atomic and not item.is_completed:
            assert item.percent_completed == 0


@pytest.mark.parametrize(
    "topology",
    [
        DependencyTopology.RANDOM_DAG,
        DependencyTopology.LAYERED,
        DependencyTopology.CHAIN,
        DependencyTopology.FAN_IN,
        DependencyTopology.FAN_OUT,
    ],
)
def test_completed_dependents_never_have_unfinished_prerequisites(topology):
    bp = build_blueprint(spec_for(
        seed=8128,
        size=128,
        dependency_load=DependencyLoad.HEAVY,
        dependency_topology=topology,
        lifecycle=LifecycleProfile.COMPLETION_HEAVY,
        heterogeneity=Heterogeneity.MIXED,
    ))

    by_key = {item.key: item for item in bp.items}

    for edge in bp.dependencies:
        prerequisite = by_key[edge.prerequisite_key]
        dependent = by_key[edge.dependent_key]

        assert not (
            dependent.is_completed
            and not prerequisite.is_completed
        )


def test_completed_frontier_items_never_hold_priority():
    bp = build_blueprint(spec_for(
        seed=2026,
        size=128,
        priority_coverage=1.0,
        priority_alignment=PriorityAlignment.RANDOM,
        lifecycle=LifecycleProfile.COMPLETION_HEAVY,
        heterogeneity=Heterogeneity.MIXED,
    ))

    assert all(
        item.priority_position is None
        for item in bp.frontier
        if item.is_completed
    )


def test_priority_coverage_is_measured_over_priority_eligible_frontier():
    bp = build_blueprint(spec_for(
        seed=3609,
        size=128,
        priority_coverage=0.5,
        priority_alignment=PriorityAlignment.RANDOM,
        lifecycle=LifecycleProfile.COMPLETION_HEAVY,
        heterogeneity=Heterogeneity.MIXED,
        dependency_load=DependencyLoad.HEAVY,
        dependency_topology=DependencyTopology.LAYERED,
    ))

    by_key = {item.key: item for item in bp.items}

    blocked = {
        edge.dependent_key
        for edge in bp.dependencies
        if not by_key[edge.prerequisite_key].is_completed
    }

    eligible = [
        item
        for item in bp.frontier
        if not item.is_completed
        and item.key not in blocked
    ]

    prioritized = [
        item
        for item in bp.frontier
        if item.priority_position is not None
    ]

    assert len(prioritized) == round(len(eligible) * 0.5)

    assert all(
        item.key not in blocked
        and not item.is_completed
        for item in prioritized
    )

    assert sorted(
        item.priority_position
        for item in prioritized
    ) == list(range(1, len(prioritized) + 1))


def test_canonical_composition_preserves_frozen_geometry():
    common = dict(
        seed=14159,
        size=128,
        dependency_load=DependencyLoad.HEAVY,
        dependency_topology=DependencyTopology.LAYERED,
    )

    fresh = build_blueprint(spec_for(
        **common,
        lifecycle=LifecycleProfile.FRESH,
        heterogeneity=Heterogeneity.HOMOGENEOUS,
    ))

    lifecycle_heavy = build_blueprint(spec_for(
        **common,
        priority_coverage=1.0,
        priority_alignment=PriorityAlignment.URGENCY_ALIGNED,
        temporal_coverage=1.0,
        temporal_pressure=TemporalPressure.OVERDUE_MIXED,
        anchor_coverage=1.0,
        anchor_relation=AnchorRelation.MIXED,
        lifecycle=LifecycleProfile.COMPLETION_HEAVY,
        heterogeneity=Heterogeneity.MIXED,
    ))

    assert [
        (
            item.key,
            item.parent_key,
            item.depth,
            item.duration_category,
        )
        for item in fresh.items
    ] == [
        (
            item.key,
            item.parent_key,
            item.depth,
            item.duration_category,
        )
        for item in lifecycle_heavy.items
    ]

    assert fresh.dependencies == lifecycle_heavy.dependencies


# ---------------------------------------------------------------------------
# PASS 1D.2 — canonical priority eligibility
# ---------------------------------------------------------------------------

def test_blocked_frontier_items_never_receive_priority():
    bp = build_blueprint(spec_for(
        seed=424242,
        size=128,
        priority_coverage=1.0,
        priority_alignment=PriorityAlignment.RANDOM,
        dependency_load=DependencyLoad.HEAVY,
        dependency_topology=DependencyTopology.LAYERED,
        lifecycle=LifecycleProfile.FRESH,
        heterogeneity=Heterogeneity.HOMOGENEOUS,
    ))

    by_key = {item.key: item for item in bp.items}

    blocked = {
        edge.dependent_key
        for edge in bp.dependencies
        if not by_key[edge.prerequisite_key].is_completed
    }

    assert blocked

    assert all(
        by_key[key].priority_position is None
        for key in blocked
    )

    eligible = [
        item
        for item in bp.frontier
        if not item.is_completed
        and item.key not in blocked
    ]

    assert all(
        item.priority_position is not None
        for item in eligible
    )

    assert sorted(
        item.priority_position
        for item in eligible
    ) == list(range(1, len(eligible) + 1))


def test_priority_eligibility_change_does_not_change_dependency_geometry():
    common = dict(
        seed=99173,
        size=128,
        dependency_load=DependencyLoad.HEAVY,
        dependency_topology=DependencyTopology.RANDOM_DAG,
        lifecycle=LifecycleProfile.FRESH,
        heterogeneity=Heterogeneity.HOMOGENEOUS,
    )

    unprioritized = build_blueprint(spec_for(
        **common,
        priority_coverage=0.0,
        priority_alignment=PriorityAlignment.NONE,
    ))

    prioritized = build_blueprint(spec_for(
        **common,
        priority_coverage=1.0,
        priority_alignment=PriorityAlignment.RANDOM,
    ))

    assert unprioritized.dependencies == prioritized.dependencies

    assert [
        (
            item.key,
            item.parent_key,
            item.depth,
            item.duration_category,
        )
        for item in unprioritized.items
    ] == [
        (
            item.key,
            item.parent_key,
            item.depth,
            item.duration_category,
        )
        for item in prioritized.items
    ]


# ---------------------------------------------------------------------------
# PHASE 2B — deliberate Φ89 hole filling
# ---------------------------------------------------------------------------

def test_temporal_shape_release_only_is_representable():
    bp = build_blueprint(spec_for(
        seed=81001,
        size=128,
        temporal_coverage=1.0,
        temporal_pressure=TemporalPressure.MIXED,
        temporal_shape=TemporalShape.RELEASE_ONLY,
    ))

    assert bp.frontier
    assert all(
        item.start_date is not None
        and item.due_date is None
        for item in bp.frontier
    )


def test_temporal_shape_deadline_only_is_representable():
    bp = build_blueprint(spec_for(
        seed=81002,
        size=128,
        temporal_coverage=1.0,
        temporal_pressure=TemporalPressure.MIXED,
        temporal_shape=TemporalShape.DEADLINE_ONLY,
    ))

    assert all(
        item.start_date is None
        and item.due_date is not None
        for item in bp.frontier
    )


def test_temporal_shape_both_is_representable():
    bp = build_blueprint(spec_for(
        seed=81003,
        size=128,
        temporal_coverage=1.0,
        temporal_pressure=TemporalPressure.MIXED,
        temporal_shape=TemporalShape.BOTH,
    ))

    assert all(
        item.start_date is not None
        and item.due_date is not None
        for item in bp.frontier
    )


def test_temporal_shape_mixed_spans_all_three_constrained_shapes():
    bp = build_blueprint(spec_for(
        seed=81004,
        size=128,
        temporal_coverage=1.0,
        temporal_pressure=TemporalPressure.MIXED,
        temporal_shape=TemporalShape.MIXED,
    ))

    shapes = {
        (
            item.start_date is not None,
            item.due_date is not None,
        )
        for item in bp.frontier
    }

    assert shapes == {
        (False, True),
        (True, False),
        (True, True),
    }


def test_expired_anchor_history_moves_independently_of_current_anchor_coverage():
    none = build_blueprint(spec_for(
        seed=82001,
        size=128,
        anchor_coverage=0.0,
        anchor_relation=AnchorRelation.NONE,
        expired_anchor_history=ExpiredAnchorHistory.NONE,
    ))

    dense = build_blueprint(spec_for(
        seed=82001,
        size=128,
        anchor_coverage=0.0,
        anchor_relation=AnchorRelation.NONE,
        expired_anchor_history=ExpiredAnchorHistory.DENSE,
    ))

    assert all(
        item.expired_manual_requested_date is None
        for item in none.frontier
    )

    historical = [
        item
        for item in dense.frontier
        if item.expired_manual_requested_date is not None
    ]

    assert len(historical) == round(len(dense.frontier) * 0.75)

    # This axis must not silently manufacture current anchor intent.
    assert all(
        item.manual_requested_date is None
        for item in dense.frontier
    )


def test_actionable_parent_coverage_changes_type_not_hierarchy_geometry():
    common = dict(
        seed=83001,
        size=128,
        hierarchy_depth=HierarchyDepth.MEDIUM,
        hierarchy_branching=HierarchyBranching.BALANCED,
    )

    none = build_blueprint(spec_for(
        **common,
        actionable_parent_coverage=ActionableParentCoverage.NONE,
    ))

    many = build_blueprint(spec_for(
        **common,
        actionable_parent_coverage=ActionableParentCoverage.MANY,
    ))

    assert [
        (item.key, item.parent_key, item.depth)
        for item in none.items
    ] == [
        (item.key, item.parent_key, item.depth)
        for item in many.items
    ]

    parent_keys = {
        item.parent_key
        for item in many.items
        if item.parent_key is not None
    }

    assert parent_keys

    assert all(
        item.item_type == "TASK"
        for item in many.items
        if item.key in parent_keys
    )

    assert all(
        item.item_type == "GOAL"
        for item in none.items
        if item.key in parent_keys
    )


def test_new_hole_filling_controls_do_not_change_dependency_geometry():
    common = dict(
        seed=84001,
        size=128,
        hierarchy_depth=HierarchyDepth.MEDIUM,
        hierarchy_branching=HierarchyBranching.BALANCED,
        dependency_load=DependencyLoad.HEAVY,
        dependency_topology=DependencyTopology.LAYERED,
    )

    baseline = build_blueprint(spec_for(**common))

    expanded = build_blueprint(spec_for(
        **common,
        temporal_shape=TemporalShape.RELEASE_ONLY,
        expired_anchor_history=ExpiredAnchorHistory.DENSE,
        actionable_parent_coverage=ActionableParentCoverage.MANY,
    ))

    assert baseline.dependencies == expanded.dependencies

    assert [
        (
            item.key,
            item.parent_key,
            item.depth,
            item.duration_category,
        )
        for item in baseline.items
    ] == [
        (
            item.key,
            item.parent_key,
            item.depth,
            item.duration_category,
        )
        for item in expanded.items
    ]
