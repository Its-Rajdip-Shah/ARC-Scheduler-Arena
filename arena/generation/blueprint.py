"""Pure in-memory workload construction for ARC Arena Generator V1.

Pass 1B deliberately performs no database writes, scheduling, feature
extraction, temporal generation, dependencies, priority, or lifecycle changes.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, timedelta

from planning.models import DurationCategory, ItemType

from arena.generation.randomness import rng_for
from planning.models import ATOMIC_DURATION_CATEGORIES

from arena.generation.spec import (
    ActionableParentCoverage,
    AnchorRelation,
    DependencyLoad,
    DependencyTopology,
    DurationProfile,
    ExpiredAnchorHistory,
    GenerationSpec,
    Heterogeneity,
    HierarchyBranching,
    HierarchyDepth,
    LifecycleProfile,
    PriorityAlignment,
    TemporalPressure,
    TemporalShape,
)


DURATION_CATEGORIES = (
    DurationCategory.UNDER_20_MINUTES,
    DurationCategory.UNDER_1_HOUR,
    DurationCategory.UNDER_4_HOURS,
    DurationCategory.UNDER_8_HOURS,
    DurationCategory.UNDER_16_HOURS,
    DurationCategory.OVER_16_HOURS,
)

DURATION_PROFILE_WEIGHTS = {
    DurationProfile.SHORT: (0.40, 0.35, 0.15, 0.06, 0.03, 0.01),
    DurationProfile.BALANCED: (0.10, 0.20, 0.25, 0.20, 0.15, 0.10),
    DurationProfile.LONG: (0.02, 0.05, 0.13, 0.25, 0.30, 0.25),
    DurationProfile.BIMODAL: (0.30, 0.15, 0.05, 0.05, 0.15, 0.30),
    DurationProfile.UNIFORM: (1 / 6,) * 6,
}


@dataclass(frozen=True, slots=True)
class BlueprintItem:
    """One generated item before persistence into the ARC domain."""

    key: str
    parent_key: str | None
    depth: int
    duration_category: str
    item_type: str = ItemType.TASK

    # Remaining pure workload-state dimensions. These deliberately mirror
    # canonical ARC fields without persisting anything yet.
    priority_position: int | None = None
    start_date: date | None = None
    due_date: date | None = None
    manual_requested_date: date | None = None
    expired_manual_requested_date: date | None = None
    percent_completed: int = 0
    is_completed: bool = False


@dataclass(frozen=True, slots=True)
class BlueprintDependency:
    """One canonical prerequisite -> dependent edge before persistence."""

    prerequisite_key: str
    dependent_key: str


@dataclass(frozen=True, slots=True)
class WorkloadBlueprint:
    """Pure deterministic output of the controlled in-memory generator."""

    seed: int
    items: tuple[BlueprintItem, ...]
    dependencies: tuple[BlueprintDependency, ...] = ()

    @property
    def frontier(self) -> tuple[BlueprintItem, ...]:
        parent_keys = {
            item.parent_key
            for item in self.items
            if item.parent_key is not None
        }
        return tuple(item for item in self.items if item.key not in parent_keys)

    @property
    def max_depth(self) -> int:
        return max((item.depth for item in self.items), default=0)


def _target_max_depth(spec: GenerationSpec) -> int:
    if spec.hierarchy_depth is HierarchyDepth.FLAT:
        return 0
    if spec.hierarchy_depth is HierarchyDepth.SHALLOW:
        return 2
    if spec.hierarchy_depth is HierarchyDepth.MEDIUM:
        return math.ceil(math.log2(spec.size))
    if spec.hierarchy_depth is HierarchyDepth.DEEP:
        return min(12, spec.size // 4)
    raise AssertionError(f"unhandled hierarchy depth: {spec.hierarchy_depth}")


def _minimum_frontier(size: int) -> int:
    return max(8, math.ceil(0.35 * size))


def _parent_indices(
    *,
    size: int,
    target_depth: int,
    branching: HierarchyBranching,
    seed: int,
) -> list[int | None]:
    """Construct deterministic hierarchy with controlled depth and width.

    Depth is guaranteed by a backbone. Branching controls how the remaining
    population is distributed around that backbone.

    Distinct-parent usage is bounded so the V1 frontier floor is preserved.
    Per-parent soft capacities prevent pathological O(N) fan-out.
    """
    if target_depth == 0:
        return [None] * size

    rng = rng_for(seed, "hierarchy")

    minimum_frontier = _minimum_frontier(size)
    max_parent_nodes = size - minimum_frontier

    if target_depth > max_parent_nodes:
        raise ValueError(
            "requested hierarchy depth is incompatible with the frontier floor"
        )

    parents: list[int | None] = [None] * size
    depths: list[int] = [0] * size
    child_counts: list[int] = [0] * size

    # --------------------------------------------------------------
    # Stage 1: mandatory backbone.
    # --------------------------------------------------------------
    for index in range(1, target_depth + 1):
        parent = index - 1
        parents[index] = parent
        depths[index] = depths[parent] + 1
        child_counts[parent] += 1

    used_as_parent = set(range(target_depth))

    # --------------------------------------------------------------
    # Regime semantics.
    #
    # NARROW:
    #   modest structural-parent population, deep attachment preference,
    #   low fan-out.
    #
    # BALANCED:
    #   larger structural-parent population, distributed attachment,
    #   moderate fan-out.
    #
    # BROAD:
    #   shallow attachment preference and higher fan-out, but still
    #   bounded so no parent becomes an O(N) mega-star.
    # --------------------------------------------------------------
    if branching is HierarchyBranching.NARROW:
        parent_fraction = 0.30
        soft_child_cap = 3
    elif branching is HierarchyBranching.BALANCED:
        parent_fraction = 0.50
        soft_child_cap = 4
    else:
        parent_fraction = 0.40
        soft_child_cap = max(6, math.ceil(math.sqrt(size)))

    desired_parent_nodes = max(
        target_depth,
        min(max_parent_nodes, math.ceil(parent_fraction * size)),
    )

    for index in range(target_depth + 1, size):
        existing = [
            candidate
            for candidate in used_as_parent
            if candidate < index
            and depths[candidate] < target_depth
            and child_counts[candidate] < soft_child_cap
        ]

        unopened = [
            candidate
            for candidate in range(index)
            if candidate not in used_as_parent
            and depths[candidate] < target_depth
        ]

        can_open = (
            len(used_as_parent) < desired_parent_nodes
            and bool(unopened)
        )

        # Open structural parents gradually. This avoids both one giant star
        # and turning every possible item into a parent immediately.
        if can_open:
            remaining_items = size - index
            parents_needed = desired_parent_nodes - len(used_as_parent)

            # Force expansion when postponing it would make the requested
            # structural-parent budget unreachable.
            force_open = parents_needed >= remaining_items

            if branching is HierarchyBranching.NARROW:
                open_probability = 0.22
            elif branching is HierarchyBranching.BALANCED:
                open_probability = 0.55
            else:
                open_probability = 0.38

            should_open = force_open or rng.random() < open_probability
        else:
            should_open = False

        pool = unopened if should_open else existing

        # Capacity is part of branching geometry. If no legal parent remains
        # under the regime's fan-out budget, leave this item independent
        # rather than forcing pathological fan-out onto an existing parent.
        #
        # The mandatory backbone already guarantees target_depth, so an
        # independent root here does not weaken the requested depth regime.
        if not pool:
            parents[index] = None
            depths[index] = 0
            continue

        if branching is HierarchyBranching.NARROW:
            deepest = max(depths[c] for c in pool)
            depth_pool = [c for c in pool if depths[c] == deepest]
            minimum_children = min(child_counts[c] for c in depth_pool)
            preferred = [
                c for c in depth_pool
                if child_counts[c] == minimum_children
            ]

        elif branching is HierarchyBranching.BROAD:
            shallowest = min(depths[c] for c in pool)
            depth_pool = [c for c in pool if depths[c] == shallowest]
            minimum_children = min(child_counts[c] for c in depth_pool)
            preferred = [
                c for c in depth_pool
                if child_counts[c] == minimum_children
            ]

        else:
            minimum_children = min(child_counts[c] for c in pool)
            load_pool = [
                c for c in pool
                if child_counts[c] == minimum_children
            ]

            # Prefer middle-depth candidates when loads are equivalent.
            midpoint = target_depth / 2
            distance = min(abs(depths[c] - midpoint) for c in load_pool)
            preferred = [
                c for c in load_pool
                if abs(depths[c] - midpoint) == distance
            ]

        parent = rng.choice(preferred)

        parents[index] = parent
        depths[index] = depths[parent] + 1
        child_counts[parent] += 1
        used_as_parent.add(parent)

    return parents

def _depths_from_parents(parents: list[int | None]) -> list[int]:
    depths: list[int] = []
    for index, parent in enumerate(parents):
        if parent is None:
            depths.append(0)
        else:
            assert 0 <= parent < index
            depths.append(depths[parent] + 1)
    return depths



DEPENDENCY_LOAD_FRACTIONS = {
    DependencyLoad.SPARSE: 0.25,
    DependencyLoad.MODERATE: 0.50,
    DependencyLoad.HEAVY: 0.75,
}


def _dependency_target_edges(frontier_count: int, load: DependencyLoad) -> int:
    """Return a scale-linear edge budget for the frontier dependency DAG.

    The frozen Φ89 density denominator is n*(n-1), so an O(n) edge budget
    intentionally spans sparse realistic precedence graphs rather than
    near-complete DAGs. Load controls quantity; topology controls geometry.
    """
    if load is DependencyLoad.NONE or frontier_count < 2:
        return 0

    fraction = DEPENDENCY_LOAD_FRACTIONS[load]
    return max(1, round(fraction * frontier_count))


def _dependency_edges(
    frontier_keys: tuple[str, ...],
    *,
    load: DependencyLoad,
    topology: DependencyTopology,
    seed: int,
) -> tuple[BlueprintDependency, ...]:
    """Generate a deterministic acyclic dependency graph over frontier work.

    A seeded hidden topological order is fixed first. Every generated edge
    points forward in that order, making cycles impossible by construction.

    Load controls edge budget independently from topology. Topology controls
    where those edges are concentrated.
    """
    if load is DependencyLoad.NONE:
        return ()

    n = len(frontier_keys)
    if n < 2:
        return ()

    rng = rng_for(seed, "dependencies")
    order = list(frontier_keys)
    rng.shuffle(order)

    target = min(
        _dependency_target_edges(n, load),
        n * (n - 1) // 2,
    )

    if target == 0:
        return ()

    candidates: list[tuple[str, str]] = []

    if topology is DependencyTopology.CHAIN:
        # Prefer consecutive edges first, guaranteeing the longest possible
        # chain for the available budget. Additional edges remain forward.
        candidates.extend(
            (order[i], order[i + 1])
            for i in range(n - 1)
        )
        candidates.extend(
            (order[i], order[j])
            for gap in range(2, n)
            for i in range(n - gap)
            for j in (i + gap,)
        )

    elif topology is DependencyTopology.FAN_IN:
        # Many prerequisites converge onto late sinks.
        for sink_index in range(n - 1, 0, -1):
            candidates.extend(
                (order[source_index], order[sink_index])
                for source_index in range(sink_index)
            )

    elif topology is DependencyTopology.FAN_OUT:
        # Early sources block many later dependants.
        for source_index in range(n - 1):
            candidates.extend(
                (order[source_index], order[target_index])
                for target_index in range(source_index + 1, n)
            )

    elif topology is DependencyTopology.LAYERED:
        # Split the hidden topological order into up to four deterministic
        # stages. Adjacent-stage edges are interleaved across transitions so
        # the edge budget cannot be exhausted entirely by layer 0 -> layer 1.
        #
        # This preserves load as the edge-count control while making LAYERED
        # express genuine multi-stage precedence geometry.
        layer_count = min(4, n)
        layers: list[list[str]] = [[] for _ in range(layer_count)]

        for index, key in enumerate(order):
            layers[index * layer_count // n].append(key)

        transition_edges: list[list[tuple[str, str]]] = []

        for layer_index in range(layer_count - 1):
            left = layers[layer_index]
            right = layers[layer_index + 1]

            edges = [
                (left[i % len(left)], right[i % len(right)])
                for i in range(max(len(left), len(right)))
            ]

            # Add the remaining adjacent-layer possibilities after the
            # distributed backbone. Their deterministic ordering is retained.
            backbone = set(edges)
            edges.extend(
                (source, target)
                for source in left
                for target in right
                if (source, target) not in backbone
            )

            transition_edges.append(edges)

        # Round-robin the adjacent-layer candidate streams. Therefore early
        # budgets populate every layer transition instead of creating a
        # one-hop bipartite fan-out.
        cursor = 0
        while True:
            added = False

            for edges in transition_edges:
                if cursor < len(edges):
                    candidates.append(edges[cursor])
                    added = True

            if not added:
                break

            cursor += 1

        # Only after all adjacent-layer candidates do we expose longer-range
        # forward edges as deterministic overflow candidates.
        layered_edges = set(candidates)
        candidates.extend(
            (order[i], order[j])
            for i in range(n)
            for j in range(i + 1, n)
            if (order[i], order[j]) not in layered_edges
        )

    elif topology is DependencyTopology.RANDOM_DAG:
        candidates = [
            (order[i], order[j])
            for i in range(n)
            for j in range(i + 1, n)
        ]
        rng.shuffle(candidates)

    else:
        raise AssertionError(f"unhandled dependency topology: {topology}")

    # Preserve topology preference while removing any accidental duplicates.
    seen: set[tuple[str, str]] = set()
    chosen: list[tuple[str, str]] = []

    for edge in candidates:
        if edge in seen:
            continue
        seen.add(edge)
        chosen.append(edge)
        if len(chosen) == target:
            break

    if len(chosen) != target:
        raise AssertionError(
            f"dependency generator produced {len(chosen)} edges; expected {target}"
        )

    return tuple(
        BlueprintDependency(prerequisite_key=source, dependent_key=target)
        for source, target in chosen
    )

def _largest_remainder_counts(
    total: int,
    weights: tuple[float, ...],
) -> list[int]:
    """Allocate exactly total observations according to categorical weights."""
    raw = [total * weight for weight in weights]
    counts = [math.floor(value) for value in raw]
    remaining = total - sum(counts)

    order = sorted(
        range(len(weights)),
        key=lambda i: (-(raw[i] - counts[i]), i),
    )
    for index in order[:remaining]:
        counts[index] += 1

    assert sum(counts) == total
    return counts


def _duration_assignments(spec: GenerationSpec) -> list[str]:
    weights = DURATION_PROFILE_WEIGHTS[spec.duration_profile]
    counts = _largest_remainder_counts(spec.size, weights)

    values: list[str] = []
    for category, count in zip(DURATION_CATEGORIES, counts):
        values.extend([str(category)] * count)

    rng_for(spec.seed, "duration").shuffle(values)
    return values



# ---------------------------------------------------------------------------
# PASS 1D — remaining pure workload-state dimensions
# ---------------------------------------------------------------------------

GENERATOR_TODAY = date(2026, 1, 15)

_DURATION_RANK = {
    str(category): rank
    for rank, category in enumerate(DURATION_CATEGORIES)
}


def _coverage_count(count: int, coverage: float) -> int:
    if count <= 0 or coverage <= 0:
        return 0
    return min(count, round(count * coverage))


def _temporal_assignments(
    frontier: tuple[BlueprintItem, ...],
    spec: GenerationSpec,
) -> dict[str, tuple[date | None, date | None]]:
    """Generate deterministic temporal state over the frontier."""
    count = _coverage_count(len(frontier), spec.temporal_coverage)
    if count == 0:
        return {}

    rng = rng_for(spec.seed, "temporal")
    chosen = list(frontier)
    rng.shuffle(chosen)
    chosen = chosen[:count]

    pressure_offsets = {
        TemporalPressure.RELAXED: (14, 21, 30, 45, 60),
        TemporalPressure.MIXED: (1, 3, 7, 14, 30),
        TemporalPressure.COMPRESSED: (1, 2, 3, 5, 7),
        TemporalPressure.URGENT: (0, 1, 1, 2, 3),
        TemporalPressure.OVERDUE_MIXED: (-14, -7, -3, 1, 3, 7),
    }
    offsets = pressure_offsets[spec.temporal_pressure]

    result = {}

    for index, item in enumerate(chosen):
        due_offset = offsets[index % len(offsets)]

        if spec.temporal_pressure is TemporalPressure.RELAXED:
            due_offset += rng.randint(0, 10)
        elif spec.temporal_pressure is TemporalPressure.MIXED:
            due_offset += rng.randint(0, 3)
        elif spec.temporal_pressure is TemporalPressure.COMPRESSED:
            due_offset += rng.randint(0, 1)
        elif spec.temporal_pressure is TemporalPressure.URGENT:
            due_offset += rng.randint(0, 1)
        else:
            due_offset += rng.randint(0, 2)

        due = GENERATOR_TODAY + timedelta(days=due_offset)

        if due_offset < 0:
            release = due - timedelta(days=7)
        else:
            window = {
                TemporalPressure.RELAXED: 14,
                TemporalPressure.MIXED: 7,
                TemporalPressure.COMPRESSED: 3,
                TemporalPressure.URGENT: 1,
                TemporalPressure.OVERDUE_MIXED: 5,
            }[spec.temporal_pressure]
            release = min(
                GENERATOR_TODAY,
                due - timedelta(days=window),
            )

        shape = spec.temporal_shape

        if shape is TemporalShape.MIXED:
            shape = (
                TemporalShape.DEADLINE_ONLY,
                TemporalShape.RELEASE_ONLY,
                TemporalShape.BOTH,
            )[index % 3]

        if shape is TemporalShape.DEADLINE_ONLY:
            start_date, due_date = None, due
        elif shape is TemporalShape.RELEASE_ONLY:
            start_date, due_date = release, None
        elif shape is TemporalShape.BOTH:
            start_date, due_date = release, due
        else:
            raise AssertionError(
                f"unhandled temporal shape: {shape}"
            )

        result[item.key] = (start_date, due_date)

    return result


def _priority_assignments(
    frontier: tuple[BlueprintItem, ...],
    spec: GenerationSpec,
    temporal: dict[str, tuple[date | None, date | None]],
) -> dict[str, int]:
    """Assign unique dense canonical priority positions over covered frontier."""
    count = _coverage_count(len(frontier), spec.priority_coverage)
    if count == 0:
        return {}

    rng = rng_for(spec.seed, "priority")
    candidates = list(frontier)

    if spec.priority_alignment is PriorityAlignment.RANDOM:
        rng.shuffle(candidates)

    elif spec.priority_alignment in {
        PriorityAlignment.DURATION_ALIGNED,
        PriorityAlignment.DURATION_OPPOSED,
    }:
        # Lower canonical position means higher priority.
        reverse = spec.priority_alignment is PriorityAlignment.DURATION_OPPOSED
        candidates.sort(
            key=lambda item: (_DURATION_RANK[item.duration_category], item.key),
            reverse=reverse,
        )

    elif spec.priority_alignment in {
        PriorityAlignment.URGENCY_ALIGNED,
        PriorityAlignment.URGENCY_OPPOSED,
    }:
        def urgency_key(item):
            _, due = temporal.get(item.key, (None, None))
            # Unconstrained work is least urgent.
            return (due is None, due or date.max, item.key)

        candidates.sort(key=urgency_key)
        if spec.priority_alignment is PriorityAlignment.URGENCY_OPPOSED:
            candidates.reverse()

    else:
        raise AssertionError(
            f"unhandled priority alignment: {spec.priority_alignment}"
        )

    selected = candidates[:count]
    return {
        item.key: position
        for position, item in enumerate(selected, start=1)
    }


def _anchor_assignments(
    frontier: tuple[BlueprintItem, ...],
    spec: GenerationSpec,
    temporal: dict[str, tuple[date | None, date | None]],
) -> dict[str, date]:
    """Generate explicit manual date intent over covered frontier."""
    count = _coverage_count(len(frontier), spec.anchor_coverage)
    if count == 0:
        return {}

    rng = rng_for(spec.seed, "anchors")

    if spec.anchor_relation in {
        AnchorRelation.BEFORE,
        AnchorRelation.SAME,
        AnchorRelation.AFTER,
    }:
        eligible = [
            item for item in frontier
            if temporal.get(item.key, (None, None))[1] is not None
        ]
    else:
        eligible = list(frontier)

    rng.shuffle(eligible)
    chosen = eligible[: min(count, len(eligible))]

    result = {}
    for index, item in enumerate(chosen):
        due = temporal.get(item.key, (None, None))[1]

        relation = spec.anchor_relation
        if relation is AnchorRelation.MIXED:
            relation = (
                AnchorRelation.BEFORE,
                AnchorRelation.SAME,
                AnchorRelation.AFTER,
            )[index % 3]

        if due is None:
            anchor = GENERATOR_TODAY + timedelta(
                days=(-3, 0, 3, 7)[index % 4]
            )
        elif relation is AnchorRelation.BEFORE:
            anchor = due - timedelta(days=2)
        elif relation is AnchorRelation.SAME:
            anchor = due
        elif relation is AnchorRelation.AFTER:
            anchor = due + timedelta(days=2)
        else:
            raise AssertionError(f"unhandled anchor relation: {relation}")

        result[item.key] = anchor

    return result


def _expired_anchor_assignments(
    frontier: tuple[BlueprintItem, ...],
    spec: GenerationSpec,
    anchors: dict[str, date],
) -> dict[str, date]:
    """Generate historical manual-anchor state independently of current intent."""
    if spec.expired_anchor_history is ExpiredAnchorHistory.NONE:
        return {}

    fraction = {
        ExpiredAnchorHistory.SPARSE: 0.25,
        ExpiredAnchorHistory.DENSE: 0.75,
    }[spec.expired_anchor_history]

    count = _coverage_count(len(frontier), fraction)
    if count == 0:
        return {}

    rng = rng_for(spec.seed, "expired-anchor-history")
    chosen = list(frontier)
    rng.shuffle(chosen)
    chosen = chosen[:count]

    result = {}

    for index, item in enumerate(chosen):
        current = anchors.get(item.key)

        if current is not None:
            historical = current - timedelta(days=7)
        else:
            historical = GENERATOR_TODAY - timedelta(
                days=7 + (index % 7)
            )

        result[item.key] = historical

    return result


def _actionable_parent_keys(
    structural_items: tuple[BlueprintItem, ...],
    spec: GenerationSpec,
) -> frozenset[str]:
    """Select structural parents that remain actionable TASK hierarchy nodes."""
    if spec.actionable_parent_coverage is ActionableParentCoverage.NONE:
        return frozenset()

    parent_keys = sorted({
        item.parent_key
        for item in structural_items
        if item.parent_key is not None
    })

    if not parent_keys:
        return frozenset()

    fraction = {
        ActionableParentCoverage.SOME: 0.50,
        ActionableParentCoverage.MANY: 1.00,
    }[spec.actionable_parent_coverage]

    count = _coverage_count(len(parent_keys), fraction)

    rng = rng_for(spec.seed, "actionable-parents")
    rng.shuffle(parent_keys)

    return frozenset(parent_keys[:count])



def _lifecycle_assignments(
    frontier: tuple[BlueprintItem, ...],
    spec: GenerationSpec,
) -> dict[str, tuple[int, bool]]:
    """Generate deterministic lifecycle state before cross-domain repair."""
    if not frontier:
        return {}

    rng = rng_for(spec.seed, "lifecycle")

    base_progress = {
        LifecycleProfile.FRESH: (0,),
        LifecycleProfile.EARLY: (0, 10, 20, 25),
        LifecycleProfile.MIXED: (0, 20, 40, 60, 80, 100),
        LifecycleProfile.ADVANCED: (60, 70, 80, 90, 100),
        LifecycleProfile.COMPLETION_HEAVY: (80, 100, 100, 100),
    }[spec.lifecycle]

    result = {}

    if spec.heterogeneity is Heterogeneity.HOMOGENEOUS:
        progress = base_progress[len(base_progress) // 2]
        for item in frontier:
            completed = progress == 100
            result[item.key] = (
                100 if completed else progress,
                completed,
            )
        return result

    values = list(base_progress)

    for item in frontier:
        progress = rng.choice(values)
        completed = progress == 100
        result[item.key] = (
            100 if completed else progress,
            completed,
        )

    return result


_ATOMIC_DURATION_VALUES = {
    value.value if hasattr(value, "value") else str(value)
    for value in ATOMIC_DURATION_CATEGORIES
}


def _canonicalize_lifecycle(
    frontier: tuple[BlueprintItem, ...],
    lifecycle: dict[str, tuple[int, bool]],
    dependencies: tuple[BlueprintDependency, ...],
) -> dict[str, tuple[int, bool]]:
    """Compose lifecycle with frozen ARC duration/dependency invariants.

    Frozen ARC semantics require:

    * unfinished atomic work has zero partial progress;
    * a completed dependent cannot have an unfinished prerequisite.

    Dependency repair is deliberately completion-demoting rather than
    prerequisite-completing: lifecycle generation owns the completion
    distribution, so dependency consistency may remove contradictory
    completion but must not invent additional completed work.
    """
    by_key = {item.key: item for item in frontier}

    result = {
        key: (progress, completed)
        for key, (progress, completed) in lifecycle.items()
    }

    # Atomic unfinished work cannot represent partial progress.
    for key, item in by_key.items():
        progress, completed = result.get(key, (0, False))

        if (
            item.duration_category in _ATOMIC_DURATION_VALUES
            and not completed
        ):
            progress = 0

        result[key] = (
            100 if completed else progress,
            completed,
        )

    # Because the dependency graph is a DAG, repeatedly demoting
    # contradictory completed dependents converges monotonically.
    changed = True

    while changed:
        changed = False

        for edge in dependencies:
            prerequisite_progress, prerequisite_completed = result.get(
                edge.prerequisite_key,
                (0, False),
            )
            dependent_progress, dependent_completed = result.get(
                edge.dependent_key,
                (0, False),
            )

            if dependent_completed and not prerequisite_completed:
                dependent_item = by_key[edge.dependent_key]

                # Reopening completed work leaves it unfinished. Atomic work
                # has no partial-progress semantics; splittable work is also
                # reset here because the generated 100% was completion state,
                # not durable ProgressSegment history.
                result[edge.dependent_key] = (0, False)
                changed = True

    return result


def _priority_eligible_frontier(
    frontier: tuple[BlueprintItem, ...],
    lifecycle: dict[str, tuple[int, bool]],
    dependencies: tuple[BlueprintDependency, ...],
) -> tuple[BlueprintItem, ...]:
    """Mirror ARC's canonical priority_eligible() population.

    Generated frontier items are already actionable leaves. Eligibility
    therefore requires that an item is:

    * unfinished; and
    * not blocked by any unfinished prerequisite.

    Priority coverage is measured over this canonical eligible population,
    not over all unfinished frontier work.
    """
    unfinished = {
        item.key
        for item in frontier
        if not lifecycle.get(item.key, (0, False))[1]
    }

    blocked = {
        edge.dependent_key
        for edge in dependencies
        if not lifecycle.get(
            edge.prerequisite_key,
            (0, False),
        )[1]
    }

    return tuple(
        item
        for item in frontier
        if item.key in unfinished
        and item.key not in blocked
    )


def build_blueprint(spec: GenerationSpec) -> WorkloadBlueprint:
    """Generate one pure deterministic controlled workload blueprint."""
    spec.validate()

    target_depth = _target_max_depth(spec)
    parents = _parent_indices(
        size=spec.size,
        target_depth=target_depth,
        branching=spec.hierarchy_branching,
        seed=spec.seed,
    )
    depths = _depths_from_parents(parents)
    durations = _duration_assignments(spec)

    structural_items = tuple(
        BlueprintItem(
            key=f"item-{index:04d}",
            parent_key=None if parent is None else f"item-{parent:04d}",
            depth=depths[index],
            duration_category=durations[index],
        )
        for index, parent in enumerate(parents)
    )

    structural = WorkloadBlueprint(
        seed=spec.seed,
        items=structural_items,
    )
    frontier = structural.frontier

    # Frozen structural/dependency geometry is generated independently of
    # lifecycle, priority, temporal and anchor state.
    dependencies = _dependency_edges(
        tuple(item.key for item in frontier),
        load=spec.dependency_load,
        topology=spec.dependency_topology,
        seed=spec.seed,
    )

    temporal = _temporal_assignments(frontier, spec)
    anchors = _anchor_assignments(frontier, spec, temporal)
    expired_anchors = _expired_anchor_assignments(
        frontier,
        spec,
        anchors,
    )
    actionable_parent_keys = _actionable_parent_keys(
        structural_items,
        spec,
    )

    raw_lifecycle = _lifecycle_assignments(frontier, spec)
    lifecycle = _canonicalize_lifecycle(
        frontier,
        raw_lifecycle,
        dependencies,
    )

    # Priority is defined over ARC's canonical priority-eligible frontier.
    # Lifecycle repair happens first so completed items are excluded, and
    # dependency state then excludes items blocked by unfinished prerequisites.
    priority_eligible_frontier = _priority_eligible_frontier(
        frontier,
        lifecycle,
        dependencies,
    )
    priorities = _priority_assignments(
        priority_eligible_frontier,
        spec,
        temporal,
    )

    items = tuple(
        BlueprintItem(
            key=item.key,
            parent_key=item.parent_key,
            depth=item.depth,
            duration_category=item.duration_category,
            item_type=(
                ItemType.TASK
                if (
                    item.key in actionable_parent_keys
                    or item.key not in {
                        candidate.parent_key
                        for candidate in structural_items
                        if candidate.parent_key is not None
                    }
                )
                else ItemType.GOAL
            ),
            priority_position=priorities.get(item.key),
            start_date=temporal.get(item.key, (None, None))[0],
            due_date=temporal.get(item.key, (None, None))[1],
            manual_requested_date=anchors.get(item.key),
            expired_manual_requested_date=expired_anchors.get(item.key),
            percent_completed=lifecycle.get(item.key, (0, False))[0],
            is_completed=lifecycle.get(item.key, (0, False))[1],
        )
        for item in structural_items
    )

    blueprint = WorkloadBlueprint(
        seed=spec.seed,
        items=items,
        dependencies=dependencies,
    )

    assert len(blueprint.items) == spec.size
    assert len(blueprint.frontier) >= _minimum_frontier(spec.size)
    assert blueprint.max_depth <= target_depth

    frontier_keys = {item.key for item in blueprint.frontier}

    assert all(
        edge.prerequisite_key in frontier_keys
        and edge.dependent_key in frontier_keys
        and edge.prerequisite_key != edge.dependent_key
        for edge in blueprint.dependencies
    )

    # Canonical lifecycle composition.
    by_key = {item.key: item for item in blueprint.items}

    for item in blueprint.frontier:
        if (
            item.duration_category in _ATOMIC_DURATION_VALUES
            and not item.is_completed
        ):
            assert item.percent_completed == 0

        if item.is_completed:
            assert item.percent_completed == 100
            assert item.priority_position is None

    for edge in blueprint.dependencies:
        prerequisite = by_key[edge.prerequisite_key]
        dependent = by_key[edge.dependent_key]

        assert not (
            dependent.is_completed
            and not prerequisite.is_completed
        )

    # Priority positions are dense over exactly the covered canonical
    # priority-eligible population.
    priority_eligible = _priority_eligible_frontier(
        blueprint.frontier,
        lifecycle,
        dependencies,
    )
    priority_eligible_keys = {
        item.key
        for item in priority_eligible
    }

    positions = [
        item.priority_position
        for item in blueprint.frontier
        if item.priority_position is not None
    ]

    assert all(
        item.key in priority_eligible_keys
        for item in blueprint.frontier
        if item.priority_position is not None
    )

    assert len(positions) == len(set(positions))
    assert sorted(positions) == list(range(1, len(positions) + 1))

    expected_priority_count = _coverage_count(
        len(priority_eligible),
        spec.priority_coverage,
    )
    assert len(positions) == expected_priority_count

    return blueprint

