from __future__ import annotations

import csv
import json
import os
import sys
import tarfile
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BACKEND))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "arc_backend.settings")

import django
django.setup()

from arena.benchmarks.reconstruct import reconstruct_v1_scenario
from arena.oracle import ExactOracle, ExactOracleConfig
from arena.scheduling.mechanics import session_pieces
from arena.tuning.design import calibration_objective


def find_archive() -> Path:
    candidates = [
        Path.home()
        / "Desktop"
        / "ARC_CLOUD_RESULTS"
        / "ARC_C7_4A_R1_20260925_160029.tar.gz",

        Path.home()
        / "Desktop"
        / "ARC_C7_4A_R1_20260925_160029.tar.gz",
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate

    found = sorted(
        (Path.home() / "Desktop").rglob(
            "ARC_C7_4A_R1_*.tar.gz"
        ),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    if found:
        return found[0]

    raise FileNotFoundError(
        "Could not find an ARC_C7_4A_R1_*.tar.gz result archive."
    )


def main() -> int:
    archive = find_archive()
    desktop = Path.home() / "Desktop"

    print("=" * 78)
    print("ARC C7 EXACT-FEASIBILITY DIAGNOSTIC")
    print("=" * 78)
    print(f"archive={archive}")
    print()

    with tempfile.TemporaryDirectory(
        prefix="arc-c7-feasibility-"
    ) as tmpdir:
        tmp = Path(tmpdir)

        with tarfile.open(archive, "r:gz") as tf:
            tf.extractall(tmp)

        roots = [
            p for p in tmp.iterdir()
            if p.is_dir()
            and p.name.startswith("ARC_C7_4A_R1_")
        ]

        if len(roots) != 1:
            raise RuntimeError(
                f"Unexpected archive structure: {roots}"
            )

        record_files = list(
            roots[0].glob("objective_*/records.jsonl")
        )

        if len(record_files) != 1:
            raise RuntimeError(
                "Expected exactly one records.jsonl; "
                f"found {len(record_files)}"
            )

        by_scenario: dict[str, list[dict]] = defaultdict(list)

        with record_files[0].open(
            encoding="utf-8"
        ) as stream:
            for line in stream:
                record = json.loads(line)
                by_scenario[
                    record["scenario_id"]
                ].append(record)

        all_invalid = []

        for scenario_id, records in sorted(
            by_scenario.items()
        ):
            if (
                len(records) == 60
                and all(
                    r["status"] == "constructor_invalid"
                    for r in records
                )
            ):
                all_invalid.append(scenario_id)

        print(f"scenarios={len(by_scenario)}")
        print(
            "all_60_constructor_invalid="
            f"{len(all_invalid)}"
        )
        print()

        # Intentionally conservative.
        # The exact oracle is exponential.
        MAX_SESSIONS = 10
        MAX_NODES = 1_000_000
        HORIZON_DAYS = 30

        config = ExactOracleConfig(
            objective=calibration_objective(),
            horizon_days=HORIZON_DAYS,
            max_sessions=MAX_SESSIONS,
            max_nodes=MAX_NODES,
        )

        rows = []

        for i, scenario_id in enumerate(
            all_invalid,
            start=1,
        ):
            print(
                f"[{i:02d}/{len(all_invalid):02d}] "
                f"{scenario_id}",
                flush=True,
            )

            reconstructed = reconstruct_v1_scenario(
                scenario_id
            )

            problem = reconstructed.problem
            features = reconstructed.regenerated_features

            sessions = sum(
                len(session_pieces(item))
                for item in problem.items
            )

            row = {
                "scenario_id": scenario_id,
                "item_count": len(problem.items),
                "session_count": sessions,

                "anchor_count": features.get(
                    "anchor_count"
                ),
                "anchor_fraction": features.get(
                    "anchor_fraction"
                ),
                "dependency_edge_count": features.get(
                    "dependency_edge_count"
                ),
                "dependency_blocked_fraction": features.get(
                    "dependency_blocked_fraction"
                ),
                "temporal_span_days": features.get(
                    "temporal_span_days"
                ),
                "pressure_due_14d_count": features.get(
                    "pressure_due_14d_count"
                ),
                "overdue_fraction": features.get(
                    "overdue_fraction"
                ),

                "exact_status": None,
                "nodes_visited": None,
                "leaves_evaluated": None,
                "elapsed_seconds": None,
                "optimal_objective": None,
            }

            if sessions > MAX_SESSIONS:
                row["exact_status"] = "too_large"

                print(
                    f"    items={len(problem.items)} "
                    f"sessions={sessions} "
                    f"-> skipped (> {MAX_SESSIONS})"
                )

                rows.append(row)
                continue

            print(
                f"    items={len(problem.items)} "
                f"sessions={sessions} "
                "-> exact oracle",
                flush=True,
            )

            result = ExactOracle(config).solve(problem)

            row.update(
                exact_status=result.status,
                nodes_visited=result.nodes_visited,
                leaves_evaluated=result.leaves_evaluated,
                elapsed_seconds=result.elapsed_seconds,
                optimal_objective=(
                    result.objective.total
                    if result.objective is not None
                    else None
                ),
            )

            print(
                f"    status={result.status} "
                f"nodes={result.nodes_visited:,} "
                f"leaves={result.leaves_evaluated:,} "
                f"time={result.elapsed_seconds:.3f}s"
            )

            rows.append(row)

    out_json = (
        desktop
        / "ARC_C7_EXACT_FEASIBILITY_DIAGNOSTIC.json"
    )

    out_csv = (
        desktop
        / "ARC_C7_EXACT_FEASIBILITY_DIAGNOSTIC.csv"
    )

    counts = Counter(
        row["exact_status"]
        for row in rows
    )

    payload = {
        "source_archive": str(archive),
        "all_constructor_invalid_scenario_count": len(
            all_invalid
        ),
        "oracle_policy": {
            "horizon_days": HORIZON_DAYS,
            "max_sessions": MAX_SESSIONS,
            "max_nodes": MAX_NODES,
        },
        "status_counts": dict(counts),
        "results": rows,
    }

    out_json.write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        ) + "\n",
        encoding="utf-8",
    )

    with out_csv.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=list(rows[0]),
        )
        writer.writeheader()
        writer.writerows(rows)

    print()
    print("=" * 78)
    print("SUMMARY")
    print("=" * 78)

    for status in (
        "optimal",
        "infeasible",
        "node_limit",
        "too_large",
    ):
        print(
            f"{status:12s}: "
            f"{counts.get(status, 0)}"
        )

    print()
    print("PROVEN FEASIBLE DESPITE CONSTRUCTOR FAILURE")
    for row in rows:
        if row["exact_status"] == "optimal":
            print(
                f"  {row['scenario_id']} | "
                f"sessions={row['session_count']} | "
                f"nodes={row['nodes_visited']:,} | "
                f"optimum={row['optimal_objective']}"
            )

    print()
    print("PROVEN INFEASIBLE")
    for row in rows:
        if row["exact_status"] == "infeasible":
            print(
                f"  {row['scenario_id']} | "
                f"sessions={row['session_count']} | "
                f"nodes={row['nodes_visited']:,}"
            )

    print()
    print("UNRESOLVED NODE LIMIT")
    for row in rows:
        if row["exact_status"] == "node_limit":
            print(
                f"  {row['scenario_id']} | "
                f"sessions={row['session_count']} | "
                f"nodes={row['nodes_visited']:,}"
            )

    print()
    print("OUTPUTS")
    print(out_json)
    print(out_csv)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
