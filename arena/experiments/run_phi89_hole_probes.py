"""Phase 2B.1 — targeted Φ89 reachability probes.

Do NOT modify the frozen generator.

Instead:
1. generate/materialize a known-valid baseline;
2. mutate only canonical workload INPUT state inside a rollback transaction;
3. characterize again through frozen Φ89;
4. determine whether Phase-2A constants/couplings are genuine reachable
   workload dimensions or structural identities.

No scheduler is invoked and no database state survives.
"""

from __future__ import annotations

import django
django.setup()

import csv
from pathlib import Path
from statistics import mean

from django.db import transaction

from arena.evaluation.features import characterize_workload
from arena.generation.blueprint import GENERATOR_TODAY, build_blueprint
from arena.generation.materialize import materialize_blueprint
from arena.generation.spec import (
    AnchorRelation,
    DependencyLoad,
    DependencyTopology,
    GenerationSpec,
    Heterogeneity,
    HierarchyBranching,
    HierarchyDepth,
    LifecycleProfile,
    PriorityAlignment,
    TemporalPressure,
)
from planning.models import ItemType, PlanningItem


REPORT_DIR = (
    Path(__file__).resolve().parents[1]
    / "reports"
    / "generated_phi89"
)

SEEDS = tuple(range(20_000, 20_010))


def baseline_spec(seed: int) -> GenerationSpec:
    return GenerationSpec(
        seed=seed,
        size=128,

        hierarchy_depth=HierarchyDepth.MEDIUM,
        hierarchy_branching=HierarchyBranching.BALANCED,

        dependency_load=DependencyLoad.MODERATE,
        dependency_topology=DependencyTopology.LAYERED,

        priority_coverage=0.5,
        priority_alignment=PriorityAlignment.RANDOM,

        temporal_coverage=0.75,
        temporal_pressure=TemporalPressure.MIXED,

        anchor_coverage=0.5,
        anchor_relation=AnchorRelation.MIXED,

        lifecycle=LifecycleProfile.MIXED,
        heterogeneity=Heterogeneity.MIXED,
    )


def features(user):
    return characterize_workload(
        user,
        GENERATOR_TODAY,
    ).to_mapping()


def frontier_queryset(user):
    """Mirror canonical incomplete-child frontier predicate."""
    from django.db.models import Count, Q

    return (
        PlanningItem.objects
        .for_user(user)
        .filter(item_type__in=("TASK", "ASSIGNMENT"))
        .annotate(
            incomplete_child_count=Count(
                "children",
                filter=Q(
                    children__is_completed=False,
                    children__is_deleted=False,
                ),
            )
        )
        .filter(incomplete_child_count=0)
    )


def probe_release_only(user):
    """Create legitimate release-only frontier work.

    Convert a deterministic subset of frontier items that currently have both
    start+due into start-only items.
    """
    candidates = list(
        frontier_queryset(user)
        .filter(
            start_date__isnull=False,
            due_date__isnull=False,
        )
        .order_by("id")
    )

    chosen = candidates[: max(1, len(candidates) // 2)]

    PlanningItem.objects.filter(
        id__in=[row.id for row in chosen]
    ).update(
        due_date=None,
        manual_requested_date=None,
    )


def probe_expired_anchor_history(user):
    """Populate legitimate historical-anchor input state.

    Preserve current anchor intent while recording a previous anchor value.
    """
    candidates = list(
        frontier_queryset(user)
        .filter(manual_requested_date__isnull=False)
        .order_by("id")
    )

    if not candidates:
        candidates = list(
            frontier_queryset(user)
            .order_by("id")[:16]
        )

    chosen = candidates[: max(1, len(candidates) // 2)]

    for row in chosen:
        old = (
            row.manual_requested_date
            or GENERATOR_TODAY
        )

        row.expired_manual_requested_date = old
        row.save(
            update_fields=[
                "expired_manual_requested_date",
            ]
        )


def probe_actionable_parents(user):
    """Make a deterministic subset of hierarchy parents actionable.

    ARC explicitly permits TASK/ASSIGNMENT hierarchy nodes; its canonical
    priority frontier then excludes actionable parents while they retain
    incomplete children.

    This probes the lifecycle residual/decomposition dimensions without
    changing hierarchy geometry.
    """
    parent_ids = list(
        PlanningItem.objects
        .for_user(user)
        .filter(children__is_deleted=False)
        .values_list("id", flat=True)
        .distinct()
        .order_by("id")
    )

    chosen = parent_ids[: max(1, len(parent_ids) // 2)]

    PlanningItem.objects.filter(
        id__in=chosen
    ).update(
        item_type=ItemType.TASK,
    )


def probe_all_three(user):
    probe_release_only(user)
    probe_expired_anchor_history(user)
    probe_actionable_parents(user)


PROBES = {
    "baseline": None,
    "release_only": probe_release_only,
    "expired_anchor_history": probe_expired_anchor_history,
    "actionable_parents": probe_actionable_parents,
    "combined": probe_all_three,
}

WATCH = (
    "temporal_release_fraction",
    "temporal_deadline_fraction",
    "temporal_both_fraction",
    "temporal_unconstrained_fraction",

    "expired_anchor_history_fraction",

    "lifecycle_residual_fraction",
    "lifecycle_decomposed_parent_fraction",

    "hierarchy_frontier_fraction",
    "item_count_actionable",
    "item_count_frontier",
)


def run():
    rows = []

    print("🔬 PHASE 2B.1 — Φ89 HOLE REACHABILITY PROBES")
    print()

    for seed in SEEDS:
        print(f"seed={seed}", end=" ", flush=True)

        blueprint = build_blueprint(
            baseline_spec(seed)
        )

        for probe_name, mutation in PROBES.items():
            with transaction.atomic():
                result = materialize_blueprint(
                    blueprint,
                    email=(
                        f"arena-hole-probe-"
                        f"{seed}-{probe_name}@local.test"
                    ),
                )

                if mutation is not None:
                    mutation(result.user)

                measured = features(result.user)

                rows.append({
                    "seed": seed,
                    "probe": probe_name,
                    **{
                        name: measured[name]
                        for name in WATCH
                    },
                })

                transaction.set_rollback(True)

            print(".", end="", flush=True)

        print(" done", flush=True)

    return rows


def summarize(rows):
    by_probe = {}

    for probe in PROBES:
        subset = [
            row
            for row in rows
            if row["probe"] == probe
        ]

        by_probe[probe] = {
            name: mean(
                row[name]
                for row in subset
                if row[name] is not None
            )
            for name in WATCH
        }

    print()
    print("=== MEAN Φ89 RESPONSE ACROSS 10 SEEDS ===")
    print()

    for probe, values in by_probe.items():
        print(probe)

        for name in WATCH:
            print(
                f"  {name:<40} "
                f"{values[name]:.4f}"
            )

        print()

    baseline = by_probe["baseline"]

    print("=== TARGETED DELTAS FROM BASELINE ===")
    print()

    for probe in (
        "release_only",
        "expired_anchor_history",
        "actionable_parents",
        "combined",
    ):
        print(probe)

        for name in WATCH:
            delta = (
                by_probe[probe][name]
                - baseline[name]
            )

            if abs(delta) > 1e-12:
                print(
                    f"  {name:<40} "
                    f"{delta:+.4f}"
                )

        print()

    return by_probe


def validate(summary):
    base = summary["baseline"]
    release = summary["release_only"]
    expired = summary["expired_anchor_history"]
    parents = summary["actionable_parents"]

    # Phase 2A generator coupling:
    assert abs(
        base["temporal_release_fraction"]
        - base["temporal_both_fraction"]
    ) < 1e-12

    # Release-only state must break that coupling.
    assert (
        release["temporal_release_fraction"]
        >
        release["temporal_both_fraction"]
    )

    # Historical anchor dimension must be canonically reachable.
    assert (
        base["expired_anchor_history_fraction"] == 0
    )
    assert (
        expired["expired_anchor_history_fraction"] > 0
    )

    # Actionable hierarchy parents must activate both lifecycle dimensions.
    assert base["lifecycle_residual_fraction"] == 0
    assert (
        base["lifecycle_decomposed_parent_fraction"] == 0
    )

    assert parents["lifecycle_residual_fraction"] > 0
    assert (
        parents["lifecycle_decomposed_parent_fraction"] > 0
    )

    print("✅ Release-only temporal state is Φ89-reachable")
    print("✅ Expired-anchor history is Φ89-reachable")
    print("✅ Actionable/decomposed parent state is Φ89-reachable")
    print()
    print(
        "🎯 Phase-2A constants/coupling are generator-coverage holes, "
        "not Φ89 structural impossibilities."
    )


def write_csv(rows):
    REPORT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    path = REPORT_DIR / "phase2b_hole_probes.csv"

    with path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=tuple(rows[0]),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)

    print()
    print(f"Report: {path}")


def main():
    rows = run()
    summary = summarize(rows)
    validate(summary)
    write_csv(rows)

    print()
    print("✅ All probe transactions rolled back")
    print("🔬 PHASE 2B.1 REACHABILITY COMPLETE")


if __name__ == "__main__":
    main()
