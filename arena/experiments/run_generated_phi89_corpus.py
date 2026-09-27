"""Generate the first controlled ARC workload corpus and characterize it in Φ89.

Phase 2A goals:
* deterministic labelled experimental designs;
* broad pairwise coverage of generator-control levels;
* two stochastic replicates per selected design;
* blueprint -> canonical ARC DB -> Φ89;
* no scheduler invocation;
* stable 89-dimensional schema;
* JSON + CSV reports;
* initial feature-variation / degeneracy diagnostics.

This is a SCREENING corpus, not the frozen benchmark.
"""

from __future__ import annotations

import csv
from dataclasses import asdict, replace
from enum import Enum
import itertools
import math
from pathlib import Path
import random
from statistics import mean, pstdev
from time import perf_counter

import django

django.setup()

from django.db import transaction

from arena.evaluation.features import (
    CORRELATION_NAMES,
    canonical_json,
    characterize_workload,
)
from arena.generation.blueprint import GENERATOR_TODAY, build_blueprint
from arena.generation.materialize import materialize_blueprint
from arena.generation.spec import (
    ActionableParentCoverage,
    AnchorRelation,
    COVERAGE_LEVELS,
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
    SCALES,
    TemporalPressure,
    TemporalShape,
)


REPORT_DIR = (
    Path(__file__).resolve().parents[1]
    / "reports"
    / "generated_phi89_phase2b"
)

DESIGN_SEED = 3609
CANDIDATE_POOL_SIZE = 6000
TARGET_DESIGNS = 128
REPLICATES = 2

CONTROL_NAMES = (
    "size",
    "hierarchy_depth",
    "hierarchy_branching",
    "dependency_load",
    "dependency_topology",
    "duration_profile",
    "priority_coverage",
    "priority_alignment",
    "temporal_coverage",
    "temporal_pressure",
    "temporal_shape",
    "anchor_coverage",
    "anchor_relation",
    "expired_anchor_history",
    "actionable_parent_coverage",
    "lifecycle",
    "heterogeneity",
)


def value(x):
    return x.value if isinstance(x, Enum) else x


def design_mapping(spec: GenerationSpec) -> dict:
    raw = asdict(spec)
    raw.pop("seed")

    return {
        key: value(raw[key])
        for key in CONTROL_NAMES
    }


def random_valid_spec(rng: random.Random, *, seed: int = 0) -> GenerationSpec:
    """Sample one valid V1 control configuration."""

    size = rng.choice(sorted(SCALES))

    hierarchy_depth = rng.choice(list(HierarchyDepth))
    hierarchy_branching = (
        HierarchyBranching.BALANCED
        if hierarchy_depth is HierarchyDepth.FLAT
        else rng.choice(list(HierarchyBranching))
    )

    dependency_load = rng.choice(list(DependencyLoad))

    if dependency_load is DependencyLoad.NONE:
        dependency_topology = DependencyTopology.NONE
    else:
        dependency_topology = rng.choice([
            DependencyTopology.RANDOM_DAG,
            DependencyTopology.CHAIN,
            DependencyTopology.LAYERED,
            DependencyTopology.FAN_IN,
            DependencyTopology.FAN_OUT,
        ])

    duration_profile = rng.choice(list(DurationProfile))

    temporal_coverage = rng.choice(sorted(COVERAGE_LEVELS))
    temporal_pressure = rng.choice(list(TemporalPressure))

    # Preserve V1 semantics when there is no temporal population.
    # Otherwise deliberately expose all Phase-2B temporal shapes.
    temporal_shape = (
        TemporalShape.BOTH
        if temporal_coverage == 0
        else rng.choice(list(TemporalShape))
    )

    priority_coverage = rng.choice(sorted(COVERAGE_LEVELS))

    if priority_coverage == 0:
        priority_alignment = PriorityAlignment.NONE
    else:
        allowed_priority = [
            PriorityAlignment.RANDOM,
            PriorityAlignment.DURATION_ALIGNED,
            PriorityAlignment.DURATION_OPPOSED,
        ]

        if temporal_coverage > 0:
            allowed_priority += [
                PriorityAlignment.URGENCY_ALIGNED,
                PriorityAlignment.URGENCY_OPPOSED,
            ]

        priority_alignment = rng.choice(allowed_priority)

    anchor_coverage = rng.choice(sorted(COVERAGE_LEVELS))

    if anchor_coverage == 0:
        anchor_relation = AnchorRelation.NONE
    else:
        allowed_anchor = [AnchorRelation.MIXED]

        if temporal_coverage > 0:
            allowed_anchor += [
                AnchorRelation.BEFORE,
                AnchorRelation.SAME,
                AnchorRelation.AFTER,
            ]

        anchor_relation = rng.choice(allowed_anchor)

    expired_anchor_history = rng.choice(
        list(ExpiredAnchorHistory)
    )

    actionable_parent_coverage = rng.choice(
        list(ActionableParentCoverage)
    )

    spec = GenerationSpec(
        seed=seed,
        size=size,
        hierarchy_depth=hierarchy_depth,
        hierarchy_branching=hierarchy_branching,
        dependency_load=dependency_load,
        dependency_topology=dependency_topology,
        duration_profile=duration_profile,
        priority_coverage=priority_coverage,
        priority_alignment=priority_alignment,
        temporal_coverage=temporal_coverage,
        temporal_pressure=temporal_pressure,
        temporal_shape=temporal_shape,
        anchor_coverage=anchor_coverage,
        anchor_relation=anchor_relation,
        expired_anchor_history=expired_anchor_history,
        actionable_parent_coverage=actionable_parent_coverage,
        lifecycle=rng.choice(list(LifecycleProfile)),
        heterogeneity=rng.choice(list(Heterogeneity)),
    )

    spec.validate()
    return spec


def design_key(spec: GenerationSpec) -> tuple:
    mapping = design_mapping(spec)
    return tuple(mapping[name] for name in CONTROL_NAMES)


def pair_tokens(spec: GenerationSpec) -> frozenset:
    mapping = design_mapping(spec)

    return frozenset(
        (
            left,
            str(mapping[left]),
            right,
            str(mapping[right]),
        )
        for left, right in itertools.combinations(CONTROL_NAMES, 2)
    )


def build_candidate_pool() -> list[GenerationSpec]:
    rng = random.Random(DESIGN_SEED)

    unique = {}

    while len(unique) < CANDIDATE_POOL_SIZE:
        spec = random_valid_spec(rng)
        unique.setdefault(design_key(spec), spec)

    return list(unique.values())


def select_pairwise_designs(
    candidates: list[GenerationSpec],
) -> tuple[list[GenerationSpec], int, int]:
    """Greedily maximize pairwise control-level coverage.

    The universe is the set of valid pair tokens observed in the large,
    deterministic candidate pool. This avoids claiming coverage for logically
    impossible control combinations.
    """

    token_sets = [pair_tokens(spec) for spec in candidates]

    universe = set().union(*token_sets)
    uncovered = set(universe)

    selected = []
    remaining = set(range(len(candidates)))

    while remaining and len(selected) < TARGET_DESIGNS:
        best_index = None
        best_gain = -1

        for index in remaining:
            gain = len(token_sets[index] & uncovered)

            if gain > best_gain:
                best_gain = gain
                best_index = index

        if best_index is None:
            break

        selected.append(candidates[best_index])
        uncovered.difference_update(token_sets[best_index])
        remaining.remove(best_index)

        if not uncovered:
            break

    covered = len(universe) - len(uncovered)

    return selected, covered, len(universe)


def replicated_specs(designs: list[GenerationSpec]):
    """Assign deterministic independent generator seeds.

    Preserve typed GenerationSpec values. design_mapping() is strictly
    serialization/reporting-only and must never reconstruct executable specs.
    """
    for design_index, design in enumerate(designs):
        for replicate in range(REPLICATES):
            seed = (
                100_000
                + design_index * 100
                + replicate
            )

            spec = replace(
                design,
                seed=seed,
            )
            spec.validate()

            yield (
                design_index,
                replicate,
                spec,
            )


def characterize_specs(spec_rows):
    records = []
    schema = None
    support_schema = None

    total = len(spec_rows)
    started = perf_counter()

    for ordinal, (design_index, replicate, spec) in enumerate(
        spec_rows,
        start=1,
    ):
        blueprint = build_blueprint(spec)

        # Each workload exists only long enough to characterize it.
        # The transaction is rolled back so the experiment leaves no DB state.
        with transaction.atomic():
            materialized = materialize_blueprint(blueprint)

            result = characterize_workload(
                materialized.user,
                GENERATOR_TODAY,
            )

            transaction.set_rollback(True)

        current_schema = tuple(result.to_mapping())
        current_support = tuple(result.corr_support)

        if schema is None:
            schema = current_schema
        elif current_schema != schema:
            raise AssertionError(
                f"Φ89 schema changed at scenario {ordinal}"
            )

        if support_schema is None:
            support_schema = current_support
        elif current_support != support_schema:
            raise AssertionError(
                f"Correlation-support schema changed at scenario {ordinal}"
            )

        if len(current_schema) != 89:
            raise AssertionError(
                f"Expected Φ89, got {len(current_schema)} features"
            )

        if current_support != CORRELATION_NAMES:
            raise AssertionError(
                "Correlation-support schema differs from frozen ruler"
            )

        metadata = {
            "scenario_id": f"G{design_index:03d}-R{replicate}",
            "design_index": design_index,
            "replicate": replicate,
            "seed": spec.seed,
            "today": GENERATOR_TODAY.isoformat(),
            **design_mapping(spec),
        }

        records.append({
            "metadata": metadata,
            **result.to_serializable(),
        })

        if ordinal == 1 or ordinal % 25 == 0 or ordinal == total:
            elapsed = perf_counter() - started
            print(
                f"  [{ordinal:>3}/{total}] "
                f"{metadata['scenario_id']} "
                f"elapsed={elapsed:.1f}s",
                flush=True,
            )

    return records


def write_reports(records, selected_count, covered_pairs, total_pairs):
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    json_path = REPORT_DIR / "generated_workload_features.json"
    csv_path = REPORT_DIR / "generated_workload_features.csv"
    design_path = REPORT_DIR / "generated_designs.csv"
    diagnostic_path = REPORT_DIR / "feature_variation.csv"
    summary_path = REPORT_DIR / "summary.json"

    json_path.write_text(
        canonical_json(records) + "\n",
        encoding="utf-8",
    )

    metadata_columns = tuple(records[0]["metadata"])
    feature_columns = tuple(records[0]["features"])

    with csv_path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=[
                *metadata_columns,
                *feature_columns,
            ],
            lineterminator="\n",
        )
        writer.writeheader()

        for record in records:
            writer.writerow({
                **record["metadata"],
                **record["features"],
            })

    # One row per selected control design.
    seen_designs = {}

    for record in records:
        metadata = record["metadata"]
        seen_designs.setdefault(
            metadata["design_index"],
            {
                key: metadata[key]
                for key in (
                    "design_index",
                    *CONTROL_NAMES,
                )
            },
        )

    with design_path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as stream:
        fields = ("design_index", *CONTROL_NAMES)

        writer = csv.DictWriter(
            stream,
            fieldnames=fields,
            lineterminator="\n",
        )
        writer.writeheader()

        for index in sorted(seen_designs):
            writer.writerow(seen_designs[index])

    # Initial degeneracy/variation diagnostics.
    diagnostics = []

    for feature in feature_columns:
        values = [
            record["features"][feature]
            for record in records
        ]

        defined = [x for x in values if x is not None]
        unique = set(defined)

        diagnostics.append({
            "feature": feature,
            "defined_count": len(defined),
            "null_count": len(values) - len(defined),
            "unique_defined": len(unique),
            "minimum": min(defined) if defined else None,
            "maximum": max(defined) if defined else None,
            "mean": mean(defined) if defined else None,
            "std": (
                pstdev(defined)
                if defined
                else None
            ),
            "constant_when_defined": (
                len(unique) <= 1
            ),
        })

    with diagnostic_path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as stream:
        fields = tuple(diagnostics[0])

        writer = csv.DictWriter(
            stream,
            fieldnames=fields,
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(diagnostics)

    summary = {
        "phase": "2B_expanded_screening",
        "design_seed": DESIGN_SEED,
        "candidate_pool_size": CANDIDATE_POOL_SIZE,
        "selected_designs": selected_count,
        "replicates_per_design": REPLICATES,
        "scenario_count": len(records),
        "feature_dimensions": len(feature_columns),
        "pair_tokens_covered": covered_pairs,
        "pair_tokens_total_candidate_supported": total_pairs,
        "pair_coverage_fraction": (
            covered_pairs / total_pairs
            if total_pairs
            else 0.0
        ),
        "constant_features": [
            row["feature"]
            for row in diagnostics
            if row["constant_when_defined"]
        ],
        "features_with_nulls": [
            row["feature"]
            for row in diagnostics
            if row["null_count"] > 0
        ],
    }

    summary_path.write_text(
        canonical_json(summary) + "\n",
        encoding="utf-8",
    )

    return summary, diagnostics


def main():
    started = perf_counter()

    print("🔥 PHASE 2B — EXPANDED Φ89 SCREENING CORPUS")
    print()
    print(
        f"Building deterministic candidate pool "
        f"({CANDIDATE_POOL_SIZE:,} unique designs)...",
        flush=True,
    )

    candidates = build_candidate_pool()

    print("Selecting pairwise-maximizing designs...", flush=True)

    designs, covered_pairs, total_pairs = (
        select_pairwise_designs(candidates)
    )

    pair_fraction = (
        covered_pairs / total_pairs
        if total_pairs
        else 0.0
    )

    print(
        f"Selected designs: {len(designs)} / {TARGET_DESIGNS}"
    )
    print(
        f"Candidate-supported pair coverage: "
        f"{covered_pairs}/{total_pairs} "
        f"({pair_fraction:.2%})"
    )

    spec_rows = list(replicated_specs(designs))

    print(
        f"Materializing + characterizing "
        f"{len(spec_rows)} workloads through Φ89...",
        flush=True,
    )

    records = characterize_specs(spec_rows)

    summary, diagnostics = write_reports(
        records,
        len(designs),
        covered_pairs,
        total_pairs,
    )

    constant = [
        row["feature"]
        for row in diagnostics
        if row["constant_when_defined"]
    ]

    varying = [
        row
        for row in diagnostics
        if not row["constant_when_defined"]
    ]

    elapsed = perf_counter() - started

    print()
    print("=== Φ89 SCREENING RESULT ===")
    print(f"Scenarios:          {len(records)}")
    print(f"Dimensions:         {len(records[0]['features'])}")
    print(f"Varying features:   {len(varying)}")
    print(f"Constant features:  {len(constant)}")
    print(
        f"Pairwise coverage:  "
        f"{summary['pair_coverage_fraction']:.2%}"
    )
    print(f"Runtime:            {elapsed:.1f}s")
    print()

    if constant:
        print("Constant/degenerate features:")
        for name in constant:
            print(f"  • {name}")
    else:
        print("✅ Every Φ89 dimension varies somewhere in the screening corpus")

    print()
    print("Reports:")
    print(f"  {REPORT_DIR / 'generated_workload_features.json'}")
    print(f"  {REPORT_DIR / 'generated_workload_features.csv'}")
    print(f"  {REPORT_DIR / 'generated_designs.csv'}")
    print(f"  {REPORT_DIR / 'feature_variation.csv'}")
    print(f"  {REPORT_DIR / 'summary.json'}")
    print()
    print("✅ Identical 89-D schema across every generated scenario")
    print("✅ Frozen correlation-support schema preserved")
    print("✅ Every workload passed blueprint → ARC DB → Φ89")
    print("✅ Experiment transactions rolled back")
    print()
    print("🔬 PHASE 2B EXPANDED SCREENING CORPUS COMPLETE")


if __name__ == "__main__":
    main()
