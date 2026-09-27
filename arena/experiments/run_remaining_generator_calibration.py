"""Calibration sweep for Priority, Temporal, Anchor and Lifecycle generation."""

from __future__ import annotations

import os
from collections import defaultdict
from statistics import mean
from time import perf_counter

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "arc_backend.settings")

import django
django.setup()

from arena.generation.blueprint import (
    DURATION_CATEGORIES,
    GENERATOR_TODAY,
    build_blueprint,
)
from arena.generation.spec import (
    AnchorRelation,
    DependencyLoad,
    DependencyTopology,
    GenerationSpec,
    Heterogeneity,
    LifecycleProfile,
    PriorityAlignment,
    TemporalPressure,
)


SIZE = 128
SEEDS = range(50)

PRIORITY_COVERAGES = (0.0, 0.25, 0.5, 0.75, 1.0)
TEMPORAL_COVERAGES = (0.0, 0.25, 0.5, 0.75, 1.0)
ANCHOR_COVERAGES = (0.0, 0.25, 0.5, 0.75, 1.0)

PRIORITY_ALIGNMENTS = [
    PriorityAlignment.RANDOM,
    PriorityAlignment.DURATION_ALIGNED,
    PriorityAlignment.DURATION_OPPOSED,
    PriorityAlignment.URGENCY_ALIGNED,
    PriorityAlignment.URGENCY_OPPOSED,
]

TEMPORAL_PRESSURES = [
    TemporalPressure.RELAXED,
    TemporalPressure.MIXED,
    TemporalPressure.COMPRESSED,
    TemporalPressure.URGENT,
    TemporalPressure.OVERDUE_MIXED,
]

ANCHOR_RELATIONS = [
    AnchorRelation.BEFORE,
    AnchorRelation.SAME,
    AnchorRelation.AFTER,
    AnchorRelation.MIXED,
]

LIFECYCLE_PROFILES = list(LifecycleProfile)
HETEROGENEITIES = list(Heterogeneity)

DURATION_RANK = {
    str(category).split(".")[-1]: rank
    for rank, category in enumerate(DURATION_CATEGORIES)
}


def base_spec(**overrides):
    values = dict(
        seed=0,
        size=SIZE,
        priority_coverage=0.0,
        priority_alignment=PriorityAlignment.NONE,
        temporal_coverage=0.0,
        temporal_pressure=TemporalPressure.MIXED,
        anchor_coverage=0.0,
        anchor_relation=AnchorRelation.NONE,
        lifecycle=LifecycleProfile.FRESH,
        heterogeneity=Heterogeneity.HOMOGENEOUS,
        dependency_load=DependencyLoad.MODERATE,
        dependency_topology=DependencyTopology.RANDOM_DAG,
    )
    values.update(overrides)
    return GenerationSpec(**values)


def frozen_signature(bp):
    """Everything already frozen before Pass 1D."""
    return (
        tuple(
            (
                item.key,
                item.parent_key,
                item.depth,
                item.duration_category,
            )
            for item in bp.items
        ),
        tuple(
            (
                edge.prerequisite_key,
                edge.dependent_key,
            )
            for edge in bp.dependencies
        ),
    )


def ranks(values):
    """Average ranks; only used for calibration diagnostics."""
    n = len(values)
    order = sorted(range(n), key=lambda i: values[i])
    result = [0.0] * n

    i = 0
    while i < n:
        j = i + 1
        while j < n and values[order[j]] == values[order[i]]:
            j += 1

        average_rank = (i + 1 + j) / 2.0

        for k in range(i, j):
            result[order[k]] = average_rank

        i = j

    return result


def pearson(xs, ys):
    if len(xs) < 2:
        return None

    mx = mean(xs)
    my = mean(ys)

    dx = [x - mx for x in xs]
    dy = [y - my for y in ys]

    denominator = (
        sum(x * x for x in dx) * sum(y * y for y in dy)
    ) ** 0.5

    if denominator == 0:
        return None

    return sum(x * y for x, y in zip(dx, dy)) / denominator


def spearman(xs, ys):
    if len(xs) < 2:
        return None
    return pearson(ranks(xs), ranks(ys))


def duration_rank(item):
    raw = str(item.duration_category)
    name = raw.split(".")[-1]

    if name in DURATION_RANK:
        return DURATION_RANK[name]

    # Calibration should fail loudly rather than silently inventing an order.
    raise AssertionError(f"Unknown duration category: {raw!r}")


def priority_duration_corr(bp):
    items = [
        item
        for item in bp.frontier
        if item.priority_position is not None
    ]

    return spearman(
        [item.priority_position for item in items],
        [duration_rank(item) for item in items],
    )


def priority_urgency_corr(bp):
    items = [
        item
        for item in bp.frontier
        if item.priority_position is not None
        and item.due_date is not None
    ]

    return spearman(
        [item.priority_position for item in items],
        [(item.due_date - GENERATOR_TODAY).days for item in items],
    )


def priority_metrics(bp):
    frontier = bp.frontier
    by_key = {item.key: item for item in bp.items}

    blocked = {
        edge.dependent_key
        for edge in bp.dependencies
        if not by_key[edge.prerequisite_key].is_completed
    }

    eligible = [
        item
        for item in frontier
        if not item.is_completed
        and item.key not in blocked
    ]

    prioritized = [
        item
        for item in frontier
        if item.priority_position is not None
    ]

    positions = sorted(
        item.priority_position for item in prioritized
    )

    eligible_keys = {item.key for item in eligible}

    return {
        "coverage": (
            len(prioritized) / len(eligible)
            if eligible else 0.0
        ),
        "dense": positions == list(range(1, len(positions) + 1)),
        "eligible_only": all(
            item.key in eligible_keys
            for item in prioritized
        ),
        "duration_corr": priority_duration_corr(bp),
        "urgency_corr": priority_urgency_corr(bp),
    }


def temporal_metrics(bp):
    frontier = bp.frontier
    constrained = [
        item for item in frontier
        if item.due_date is not None
    ]

    offsets = [
        (item.due_date - GENERATOR_TODAY).days
        for item in constrained
    ]

    overdue = sum(offset < 0 for offset in offsets)
    urgent = sum(0 <= offset <= 3 for offset in offsets)

    return {
        "coverage": len(constrained) / len(frontier) if frontier else 0.0,
        "mean_due": mean(offsets) if offsets else None,
        "min_due": min(offsets) if offsets else None,
        "max_due": max(offsets) if offsets else None,
        "overdue": overdue / len(offsets) if offsets else 0.0,
        "urgent": urgent / len(offsets) if offsets else 0.0,
    }


def anchor_metrics(bp):
    anchored = [
        item for item in bp.frontier
        if item.manual_requested_date is not None
    ]

    before = same = after = no_due = 0

    for item in anchored:
        if item.due_date is None:
            no_due += 1
        elif item.manual_requested_date < item.due_date:
            before += 1
        elif item.manual_requested_date == item.due_date:
            same += 1
        else:
            after += 1

    n = len(anchored)

    return {
        "coverage": n / len(bp.frontier) if bp.frontier else 0.0,
        "before": before / n if n else 0.0,
        "same": same / n if n else 0.0,
        "after": after / n if n else 0.0,
        "no_due": no_due / n if n else 0.0,
    }


def lifecycle_metrics(bp):
    frontier = bp.frontier

    progress = [item.percent_completed for item in frontier]
    completed = [item.is_completed for item in frontier]

    return {
        "mean_progress": mean(progress) if progress else 0.0,
        "completed": (
            sum(completed) / len(completed)
            if completed else 0.0
        ),
        "progress_states": len(set(progress)),
    }


def avg_defined(values):
    values = [value for value in values if value is not None]
    return mean(values) if values else None


def fmt(value, width=7, precision=3):
    if value is None:
        return f"{'None':>{width}}"
    return f"{value:>{width}.{precision}f}"


def main():
    started = perf_counter()
    violations = []
    builds = 0

    print("🔥 PASS 1D CALIBRATION")
    print(f"   N={SIZE}, seeds={len(SEEDS)}")

    # ========================================================
    # 1. Priority coverage
    # ========================================================

    print("\n=== PRIORITY COVERAGE ===")

    for coverage in PRIORITY_COVERAGES:
        values = []

        for seed in SEEDS:
            spec = base_spec(
                seed=seed,
                priority_coverage=coverage,
                priority_alignment=(
                    PriorityAlignment.NONE
                    if coverage == 0
                    else PriorityAlignment.RANDOM
                ),
            )

            a = build_blueprint(spec)
            b = build_blueprint(spec)
            builds += 2

            if a != b:
                violations.append(
                    ("priority_nondeterminism", coverage, seed)
                )

            result = priority_metrics(a)
            values.append(result)

            if not result["dense"]:
                violations.append(
                    ("priority_not_dense", coverage, seed)
                )

            if not result["eligible_only"]:
                violations.append(
                    ("priority_assigned_outside_eligible_population",
                     coverage, seed)
                )

        print(
            f"coverage={coverage:>4.2f} | "
            f"observed={mean(x['coverage'] for x in values):.3f}"
        )

    # ========================================================
    # 2. Priority alignment
    # ========================================================

    print("\n=== PRIORITY ALIGNMENT ===")

    for alignment in PRIORITY_ALIGNMENTS:
        duration_corrs = []
        urgency_corrs = []

        for seed in SEEDS:
            kwargs = dict(
                seed=seed,
                priority_coverage=1.0,
                priority_alignment=alignment,
            )

            if alignment in {
                PriorityAlignment.URGENCY_ALIGNED,
                PriorityAlignment.URGENCY_OPPOSED,
            }:
                kwargs.update(
                    temporal_coverage=1.0,
                    temporal_pressure=TemporalPressure.MIXED,
                )

            bp = build_blueprint(base_spec(**kwargs))
            builds += 1

            result = priority_metrics(bp)
            duration_corrs.append(result["duration_corr"])
            urgency_corrs.append(result["urgency_corr"])

        print(
            f"{alignment.value:<20} | "
            f"duration rho={fmt(avg_defined(duration_corrs))} | "
            f"urgency rho={fmt(avg_defined(urgency_corrs))}"
        )

    # ========================================================
    # 3. Temporal coverage
    # ========================================================

    print("\n=== TEMPORAL COVERAGE ===")

    for coverage in TEMPORAL_COVERAGES:
        values = []

        for seed in SEEDS:
            bp = build_blueprint(base_spec(
                seed=seed,
                temporal_coverage=coverage,
                temporal_pressure=TemporalPressure.MIXED,
            ))
            builds += 1
            values.append(temporal_metrics(bp))

        print(
            f"coverage={coverage:>4.2f} | "
            f"observed={mean(x['coverage'] for x in values):.3f}"
        )

    # ========================================================
    # 4. Temporal pressure
    # ========================================================

    print("\n=== TEMPORAL PRESSURE ===")

    for pressure in TEMPORAL_PRESSURES:
        values = []

        for seed in SEEDS:
            bp = build_blueprint(base_spec(
                seed=seed,
                temporal_coverage=1.0,
                temporal_pressure=pressure,
            ))
            builds += 1
            values.append(temporal_metrics(bp))

        print(
            f"{pressure.value:<16} | "
            f"meanDue={fmt(mean(x['mean_due'] for x in values))} | "
            f"min={fmt(mean(x['min_due'] for x in values))} | "
            f"max={fmt(mean(x['max_due'] for x in values))} | "
            f"overdue={mean(x['overdue'] for x in values):.3f} | "
            f"urgent={mean(x['urgent'] for x in values):.3f}"
        )

    # ========================================================
    # 5. Anchor coverage
    # ========================================================

    print("\n=== ANCHOR COVERAGE ===")

    for coverage in ANCHOR_COVERAGES:
        values = []

        for seed in SEEDS:
            bp = build_blueprint(base_spec(
                seed=seed,
                temporal_coverage=1.0,
                temporal_pressure=TemporalPressure.MIXED,
                anchor_coverage=coverage,
                anchor_relation=(
                    AnchorRelation.NONE
                    if coverage == 0
                    else AnchorRelation.MIXED
                ),
            ))
            builds += 1
            values.append(anchor_metrics(bp))

        print(
            f"coverage={coverage:>4.2f} | "
            f"observed={mean(x['coverage'] for x in values):.3f}"
        )

    # ========================================================
    # 6. Anchor relation
    # ========================================================

    print("\n=== ANCHOR RELATION ===")

    for relation in ANCHOR_RELATIONS:
        values = []

        for seed in SEEDS:
            bp = build_blueprint(base_spec(
                seed=seed,
                temporal_coverage=1.0,
                temporal_pressure=TemporalPressure.MIXED,
                anchor_coverage=1.0,
                anchor_relation=relation,
            ))
            builds += 1
            values.append(anchor_metrics(bp))

        print(
            f"{relation.value:<10} | "
            f"before={mean(x['before'] for x in values):.3f} | "
            f"same={mean(x['same'] for x in values):.3f} | "
            f"after={mean(x['after'] for x in values):.3f} | "
            f"noDue={mean(x['no_due'] for x in values):.3f}"
        )

    # ========================================================
    # 7. Lifecycle
    # ========================================================

    print("\n=== LIFECYCLE × HETEROGENEITY ===")

    for profile in LIFECYCLE_PROFILES:
        for heterogeneity in HETEROGENEITIES:
            values = []

            for seed in SEEDS:
                bp = build_blueprint(base_spec(
                    seed=seed,
                    lifecycle=profile,
                    heterogeneity=heterogeneity,
                ))
                builds += 1
                values.append(lifecycle_metrics(bp))

            print(
                f"{profile.value:<18} "
                f"{heterogeneity.value:<12} | "
                f"progress={mean(x['mean_progress'] for x in values):6.2f} | "
                f"completed={mean(x['completed'] for x in values):.3f} | "
                f"states={mean(x['progress_states'] for x in values):.2f}"
            )

    # ========================================================
    # 8. Frozen-axis isolation torture
    # ========================================================

    print("\n=== FROZEN AXIS ISOLATION ===")

    for seed in SEEDS:
        baseline = build_blueprint(base_spec(
            seed=seed,
            dependency_load=DependencyLoad.HEAVY,
            dependency_topology=DependencyTopology.LAYERED,
        ))
        builds += 1

        variants = [
            base_spec(
                seed=seed,
                priority_coverage=1.0,
                priority_alignment=PriorityAlignment.DURATION_ALIGNED,
                dependency_load=DependencyLoad.HEAVY,
                dependency_topology=DependencyTopology.LAYERED,
            ),
            base_spec(
                seed=seed,
                temporal_coverage=1.0,
                temporal_pressure=TemporalPressure.OVERDUE_MIXED,
                dependency_load=DependencyLoad.HEAVY,
                dependency_topology=DependencyTopology.LAYERED,
            ),
            base_spec(
                seed=seed,
                temporal_coverage=1.0,
                anchor_coverage=1.0,
                anchor_relation=AnchorRelation.MIXED,
                dependency_load=DependencyLoad.HEAVY,
                dependency_topology=DependencyTopology.LAYERED,
            ),
            base_spec(
                seed=seed,
                lifecycle=LifecycleProfile.COMPLETION_HEAVY,
                heterogeneity=Heterogeneity.MIXED,
                dependency_load=DependencyLoad.HEAVY,
                dependency_topology=DependencyTopology.LAYERED,
            ),
            base_spec(
                seed=seed,
                priority_coverage=1.0,
                priority_alignment=PriorityAlignment.URGENCY_ALIGNED,
                temporal_coverage=1.0,
                temporal_pressure=TemporalPressure.URGENT,
                anchor_coverage=1.0,
                anchor_relation=AnchorRelation.MIXED,
                lifecycle=LifecycleProfile.MIXED,
                heterogeneity=Heterogeneity.MIXED,
                dependency_load=DependencyLoad.HEAVY,
                dependency_topology=DependencyTopology.LAYERED,
            ),
        ]

        signature = frozen_signature(baseline)

        for index, spec in enumerate(variants):
            candidate = build_blueprint(spec)
            builds += 1

            if frozen_signature(candidate) != signature:
                violations.append(
                    ("frozen_axis_changed", seed, index)
                )

    elapsed = perf_counter() - started

    print()
    print(f"⚙️  Blueprint builds: {builds:,}")
    print(f"⏱️  Runtime: {elapsed:.2f}s")

    if violations:
        print(f"\n❌ {len(violations)} violation(s)")
        for violation in violations[:30]:
            print("   ", violation)
        raise SystemExit(1)

    print("\n✅ Determinism checks clean")
    print("✅ Canonical priority positions remain dense/unique")
    print("✅ Frozen duration/hierarchy/dependency state unchanged")
    print()
    print("🧪 PASS 1D CALIBRATION COMPLETE")


if __name__ == "__main__":
    main()
