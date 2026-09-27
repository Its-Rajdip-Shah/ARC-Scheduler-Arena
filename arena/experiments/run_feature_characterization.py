"""Characterize all 49 legacy scenarios without invoking any algorithm.

Uses the importer/bootstrap shared with the Arena baseline runner. Each scenario
is materialized inside a rolled-back transaction, preserving pre-existing DB
rows even though the legacy importer treats its database as disposable.
"""
from __future__ import annotations

from contextlib import redirect_stdout
import csv
from datetime import date
import io
import json
from pathlib import Path

# Importer establishes the existing Arena Django environment before model use.
from arena.datasets.importer import RAW_DIR, _rows, load_scenario, map_legacy_duration
from accounts.models import User
from django.db import transaction
from arena.evaluation.features import CORRELATION_NAMES, canonical_json, characterize_workload

REPORT_DIR = Path(__file__).resolve().parents[1] / "reports"
SCENARIO_COLUMNS = ("scenario", "family", "seed", "today")
METADATA_COLUMNS = (*SCENARIO_COLUMNS, "legacy_priority_linearized", "legacy_priority_tie_count")


def characterize_corpus() -> list[dict]:
    scenarios = sorted(_rows("scenarios.csv"), key=lambda row: row["scenario"])
    manifest = json.loads((RAW_DIR / "manifest.json").read_text(encoding="utf-8"))
    if manifest["scenario_count"] != 49 or len(scenarios) != 49 or len({row["scenario"] for row in scenarios}) != 49:
        raise ValueError("Expected exactly 49 distinct scenarios and manifest scenario_count=49")
    # Validate every raw duration before any materialization; never skip failures.
    for row in _rows("items.csv"):
        map_legacy_duration(row["duration_class"])
    records = []
    schema = None
    for scenario in scenarios:
        today = date.fromisoformat(scenario["today"])
        with transaction.atomic():
            with redirect_stdout(io.StringIO()):
                compatibility = load_scenario(scenario["scenario"])
            user = User.objects.get(email="arena@local.test")
            result = characterize_workload(user, today)
            transaction.set_rollback(True)
        current_schema = tuple(result.to_mapping())
        if schema is not None and current_schema != schema:
            raise ValueError(f"Feature schema mismatch for {scenario['scenario']}")
        schema = current_schema
        if tuple(result.corr_support) != CORRELATION_NAMES:
            raise ValueError(f"Correlation support mismatch for {scenario['scenario']}")
        records.append({
            "metadata": {**{key: scenario[key] for key in SCENARIO_COLUMNS}, **compatibility},
            **result.to_serializable(),
        })
    return records


def write_reports(records: list[dict], output_dir: Path = REPORT_DIR) -> None:
    """Metadata first, stable raw schema, CSV nulls empty; support only in JSON."""
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "workload_features.json").write_text(canonical_json(records) + "\n", encoding="utf-8")
    with (output_dir / "workload_features.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=[*METADATA_COLUMNS, *records[0]["features"]], lineterminator="\n")
        writer.writeheader()
        for record in records:
            writer.writerow({**record["metadata"], **record["features"]})


def main():
    records = characterize_corpus()
    write_reports(records)
    print(f"Characterized {len(records)} scenarios; {len(records[0]['features'])} raw features each. No scheduler invoked.")


if __name__ == "__main__":
    main()
