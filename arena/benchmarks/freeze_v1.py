"""Freeze the validated Phase-2B screening corpus as ARC Benchmark V1."""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
from datetime import date, datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

SOURCE = ROOT / "arena" / "reports" / "generated_phi89_phase2b"
DEST = ROOT / "arena" / "benchmarks" / "v1"

SOURCE_FEATURES = SOURCE / "generated_workload_features.json"
SOURCE_PHI89 = SOURCE / "generated_workload_features.csv"
SOURCE_DESIGNS = SOURCE / "generated_designs.csv"
SOURCE_VARIATION = SOURCE / "feature_variation.csv"
SOURCE_SUMMARY = SOURCE / "summary.json"

EXPECTED_SCENARIOS = 118
EXPECTED_DESIGNS = 59
EXPECTED_DIMENSIONS = 89
EXPECTED_PAIR_TOKENS = 2602

GENERATOR_TODAY = "2026-01-15"

FROZEN_FILES = (
    "designs.csv",
    "workloads.json",
    "phi89.csv",
    "feature_variation.csv",
    "manifest.json",
    "README.md",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)

    return digest.hexdigest()


def load_json(path: Path):
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def validate_source():
    required = (
        SOURCE_FEATURES,
        SOURCE_PHI89,
        SOURCE_DESIGNS,
        SOURCE_VARIATION,
        SOURCE_SUMMARY,
    )

    missing = [str(path) for path in required if not path.is_file()]

    if missing:
        raise SystemExit(
            "Missing Phase-2B source artifact(s):\n  "
            + "\n  ".join(missing)
        )

    summary = load_json(SOURCE_SUMMARY)
    workloads = load_json(SOURCE_FEATURES)

    if len(workloads) != EXPECTED_SCENARIOS:
        raise AssertionError(
            f"Expected {EXPECTED_SCENARIOS} workloads, "
            f"found {len(workloads)}"
        )

    scenario_ids = [
        row["metadata"]["scenario_id"]
        for row in workloads
    ]

    if len(scenario_ids) != len(set(scenario_ids)):
        raise AssertionError("Scenario IDs are not unique.")

    if any(
        row["metadata"]["today"] != GENERATOR_TODAY
        for row in workloads
    ):
        raise AssertionError(
            "Corpus contains unexpected characterization date."
        )

    feature_schemas = {
        tuple(row["features"].keys())
        for row in workloads
    }

    if len(feature_schemas) != 1:
        raise AssertionError("Φ89 schema differs across workloads.")

    feature_schema = next(iter(feature_schemas))

    if len(feature_schema) != EXPECTED_DIMENSIONS:
        raise AssertionError(
            f"Expected Φ{EXPECTED_DIMENSIONS}, "
            f"found {len(feature_schema)} dimensions."
        )

    with SOURCE_DESIGNS.open(
        newline="",
        encoding="utf-8",
    ) as stream:
        designs = list(csv.DictReader(stream))

    if len(designs) != EXPECTED_DESIGNS:
        raise AssertionError(
            f"Expected {EXPECTED_DESIGNS} designs, "
            f"found {len(designs)}."
        )

    with SOURCE_PHI89.open(
        newline="",
        encoding="utf-8",
    ) as stream:
        phi_rows = list(csv.DictReader(stream))

    if len(phi_rows) != EXPECTED_SCENARIOS:
        raise AssertionError(
            f"Expected {EXPECTED_SCENARIOS} Φ89 rows, "
            f"found {len(phi_rows)}."
        )

    csv_ids = [row["scenario_id"] for row in phi_rows]

    if csv_ids != scenario_ids:
        raise AssertionError(
            "JSON/CSV scenario ordering differs."
        )

    if summary.get("scenario_count") != EXPECTED_SCENARIOS:
        raise AssertionError("Summary scenario count drifted.")

    if summary.get("selected_designs") != EXPECTED_DESIGNS:
        raise AssertionError("Summary design count drifted.")

    if summary.get("feature_dimensions") != EXPECTED_DIMENSIONS:
        raise AssertionError("Summary Φ dimension count drifted.")

    if (
        summary.get("pair_tokens_covered")
        != EXPECTED_PAIR_TOKENS
        or summary.get("pair_tokens_total_candidate_supported")
        != EXPECTED_PAIR_TOKENS
    ):
        raise AssertionError("Pairwise control coverage drifted.")

    if summary.get("constant_features"):
        raise AssertionError(
            "Benchmark source contains constant Φ89 dimensions."
        )

    return summary, workloads, designs, feature_schema


def freeze():
    summary, workloads, designs, feature_schema = validate_source()

    if DEST.exists():
        raise SystemExit(
            f"{DEST} already exists.\n"
            "Benchmark V1 is immutable. Delete it manually only if "
            "you intentionally want to abandon the existing freeze."
        )

    DEST.mkdir(parents=True)

    shutil.copy2(SOURCE_DESIGNS, DEST / "designs.csv")
    shutil.copy2(SOURCE_FEATURES, DEST / "workloads.json")
    shutil.copy2(SOURCE_PHI89, DEST / "phi89.csv")
    shutil.copy2(
        SOURCE_VARIATION,
        DEST / "feature_variation.csv",
    )

    control_names = [
        name
        for name in designs[0]
        if name != "design_index"
    ]

    manifest = {
        "benchmark": "ARC Scheduler Arena",
        "benchmark_version": "v1",
        "status": "frozen",
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_phase": "2B_expanded_screening",
        "generation_contract": {
            "design_seed": summary["design_seed"],
            "candidate_pool_size": summary["candidate_pool_size"],
            "selected_designs": EXPECTED_DESIGNS,
            "replicates_per_design": summary[
                "replicates_per_design"
            ],
            "scenario_count": EXPECTED_SCENARIOS,
            "generator_today": GENERATOR_TODAY,
            "pairwise_control_tokens": EXPECTED_PAIR_TOKENS,
            "pairwise_control_coverage": 1.0,
            "control_names": control_names,
        },
        "characterization_contract": {
            "name": "Phi89",
            "dimensions": EXPECTED_DIMENSIONS,
            "feature_names": list(feature_schema),
            "all_dimensions_vary_in_v1": True,
        },
        "scenario_ids": [
            row["metadata"]["scenario_id"]
            for row in workloads
        ],
        "immutability": {
            "policy": (
                "Algorithm development and evaluation must not alter "
                "Benchmark V1 workloads, designs, seeds, characterization "
                "date, or Phi89 schema. Any workload-space revision requires "
                "a new benchmark version."
            )
        },
    }

    with (DEST / "manifest.json").open(
        "w",
        encoding="utf-8",
    ) as stream:
        json.dump(
            manifest,
            stream,
            indent=2,
            sort_keys=True,
        )
        stream.write("\n")

    readme = f"""# ARC Scheduler Arena — Benchmark V1

**Status:** FROZEN

Benchmark V1 is the first fixed synthetic workload benchmark used for
algorithm evaluation in ARC Scheduler Arena.

## Corpus

- Designs: {EXPECTED_DESIGNS}
- Replicates per design: {summary["replicates_per_design"]}
- Workloads: {EXPECTED_SCENARIOS}
- Characterization: Φ{EXPECTED_DIMENSIONS}
- Candidate-supported pairwise control coverage: 100%
- Pairwise control tokens: {EXPECTED_PAIR_TOKENS}
- Characterization date: `{GENERATOR_TODAY}`
- Constant Φ89 dimensions: 0

## Provenance

V1 was frozen from the validated Phase-2B expanded screening corpus after:

1. freezing the Φ89 characterizer;
2. implementing the controlled workload generator;
3. canonical ARC materialization;
4. generator and planning-contract regression testing;
5. pairwise control-space screening;
6. Φ89 coverage analysis;
7. targeted reachability probes;
8. deliberate temporal, anchor-history, and actionable-parent hole filling;
9. re-characterization confirming variation in all 89 dimensions.

## Files

- `manifest.json` — benchmark contract and exact scenario IDs.
- `designs.csv` — the 59 frozen generator-control designs.
- `workloads.json` — metadata, Φ89 values, and correlation support for all scenarios.
- `phi89.csv` — flat workload × feature matrix.
- `feature_variation.csv` — V1 feature-range diagnostics.
- `SHA256SUMS` — integrity hashes for the frozen artifacts.

## Immutability rule

**Do not modify Benchmark V1 in response to algorithm performance.**

Algorithms are evaluated against this workload set. If future evidence shows
that the workload benchmark itself requires a semantic change, create a new
benchmark version (`v2`, etc.) and retain V1 unchanged.

Generated workload state is deterministic from the frozen design controls and
replicate seeds. Φ89 values in this directory are the frozen characterization
of those workloads under the V1 ruler.

## Experimental boundary

Benchmark V1 freezes the **workload side** of the experiment. It does not
freeze:

- scheduling algorithms;
- algorithm hyperparameters;
- performance metrics;
- performance maps;
- hybrid-selection models.

Those are subsequent experimental layers and must consume V1 without changing
it.
"""

    (DEST / "README.md").write_text(
        readme,
        encoding="utf-8",
    )

    checksum_path = DEST / "SHA256SUMS"

    with checksum_path.open(
        "w",
        encoding="utf-8",
    ) as stream:
        for name in FROZEN_FILES:
            stream.write(
                f"{sha256(DEST / name)}  {name}\n"
            )

    print("🔒 ARC BENCHMARK V1 FROZEN")
    print()
    print(f"Designs:      {EXPECTED_DESIGNS}")
    print(f"Workloads:    {EXPECTED_SCENARIOS}")
    print(f"Dimensions:   {EXPECTED_DIMENSIONS}")
    print(f"Pair tokens:  {EXPECTED_PAIR_TOKENS}/{EXPECTED_PAIR_TOKENS}")
    print(f"Today:        {GENERATOR_TODAY}")
    print()
    print(f"Location: {DEST}")
    print()
    print("SHA256:")
    print(checksum_path.read_text(), end="")


if __name__ == "__main__":
    freeze()
