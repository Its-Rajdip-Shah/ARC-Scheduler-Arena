from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
V1 = ROOT / "arena" / "benchmarks" / "v1"

EXPECTED_SCENARIOS = 118
EXPECTED_DESIGNS = 59
EXPECTED_DIMENSIONS = 89
EXPECTED_PAIR_TOKENS = 2602
EXPECTED_TODAY = "2026-01-15"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def test_v1_manifest_contract():
    manifest = json.loads(
        (V1 / "manifest.json").read_text(
            encoding="utf-8"
        )
    )

    assert manifest["benchmark_version"] == "v1"
    assert manifest["status"] == "frozen"

    generation = manifest["generation_contract"]
    characterization = manifest["characterization_contract"]

    assert generation["selected_designs"] == EXPECTED_DESIGNS
    assert generation["scenario_count"] == EXPECTED_SCENARIOS
    assert generation["generator_today"] == EXPECTED_TODAY
    assert (
        generation["pairwise_control_tokens"]
        == EXPECTED_PAIR_TOKENS
    )
    assert generation["pairwise_control_coverage"] == 1.0

    assert characterization["name"] == "Phi89"
    assert characterization["dimensions"] == EXPECTED_DIMENSIONS
    assert (
        len(characterization["feature_names"])
        == EXPECTED_DIMENSIONS
    )
    assert characterization["all_dimensions_vary_in_v1"] is True

    assert len(manifest["scenario_ids"]) == EXPECTED_SCENARIOS
    assert (
        len(set(manifest["scenario_ids"]))
        == EXPECTED_SCENARIOS
    )


def test_v1_artifact_shapes_and_scenario_alignment():
    workloads = json.loads(
        (V1 / "workloads.json").read_text(
            encoding="utf-8"
        )
    )

    with (V1 / "designs.csv").open(
        newline="",
        encoding="utf-8",
    ) as stream:
        designs = list(csv.DictReader(stream))

    with (V1 / "phi89.csv").open(
        newline="",
        encoding="utf-8",
    ) as stream:
        phi = list(csv.DictReader(stream))

    assert len(workloads) == EXPECTED_SCENARIOS
    assert len(designs) == EXPECTED_DESIGNS
    assert len(phi) == EXPECTED_SCENARIOS

    json_ids = [
        row["metadata"]["scenario_id"]
        for row in workloads
    ]
    csv_ids = [row["scenario_id"] for row in phi]

    assert json_ids == csv_ids

    schemas = {
        tuple(row["features"].keys())
        for row in workloads
    }

    assert len(schemas) == 1
    assert len(next(iter(schemas))) == EXPECTED_DIMENSIONS

    assert all(
        row["metadata"]["today"] == EXPECTED_TODAY
        for row in workloads
    )


def test_v1_sha256_integrity():
    checksum_file = V1 / "SHA256SUMS"

    expected = {}

    for line in checksum_file.read_text(
        encoding="utf-8"
    ).splitlines():
        digest, name = line.split("  ", 1)
        expected[name] = digest

    assert expected

    for name, digest in expected.items():
        path = V1 / name

        assert path.is_file(), name
        assert sha256(path) == digest, (
            f"Frozen benchmark artifact drifted: {name}"
        )
