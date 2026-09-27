from __future__ import annotations

import csv
import json
import os
import sys
import tarfile
import tempfile
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BACKEND))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "arc_backend.settings")

import django
django.setup()

from arena.benchmarks.reconstruct import reconstruct_v1_scenario
from arena.scheduling.mechanics import session_pieces
from arena.scheduling.validation import validate_plan
from arena.search.state import SearchState, SessionPlacement


HORIZON_DAYS = 30


def find_round_archive() -> Path:
    candidates = [
        Path.home()
        / "Desktop"
        / "ARC_CLOUD_RESULTS"
        / "ARC_C7_4A_R1_20260925_160029.tar.gz",

        Path.home()
        / "Desktop"
        / "ARC_C7_4A_R1_20260925_160029.tar.gz",
    ]

    for p in candidates:
        if p.exists():
            return p

    found = sorted(
        (Path.home() / "Desktop").rglob("ARC_C7_4A_R1_*.tar.gz"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    if found:
        return found[0]

    raise FileNotFoundError("Round-1 archive not found.")


def observed_category(records: list[dict]) -> str:
    counts = Counter(r["status"] for r in records)

    if len(records) == 60 and counts == {"ok": 60}:
        return "all_ok"

    if len(records) == 60 and counts == {"constructor_invalid": 60}:
        return "all_constructor_invalid"

    if len(records) == 60 and counts == {"timeout": 60}:
        return "all_timeout"

    return "mixed"


def classify(problem):
    """
    Complete feasibility proof for the CURRENT frozen hard semantics.

    Why this works:
      - release/today/dependency constraints only impose lower bounds;
      - an anchor fixes the first session to one exact day;
      - later sessions may occur on the same day;
      - capacity and deadlines are soft;
      - therefore choosing every item's earliest hard-legal day minimizes
        all downstream readiness dates.

    If this earliest schedule violates an anchor or horizon, no later
    schedule can repair it.
    """

    upper = problem.today + timedelta(days=HORIZON_DAYS)

    pieces_by_id = {
        item.item_id: session_pieces(item)
        for item in problem.items
    }

    item_by_id = problem.item_by_id
    completion: dict[int, date] = {}
    placements: list[SessionPlacement] = []

    for item_id in problem.topological_order():
        item = item_by_id[item_id]
        pieces = pieces_by_id[item_id]

        # Zero-work items require no placement and do not constrain
        # dependents under the frozen SearchState/ExactOracle semantics.
        if not pieces:
            continue

        lower = max(
            problem.today,
            item.release_date or problem.today,
        )

        blocking = []

        for prerequisite_id in sorted(
            problem.direct_prerequisites(item_id)
        ):
            if not pieces_by_id[prerequisite_id]:
                continue

            prerequisite_completion = completion[prerequisite_id]

            try:
                readiness = prerequisite_completion + timedelta(days=1)
            except OverflowError:
                return {
                    "proof_status": "PROVEN_INFEASIBLE",
                    "reason": "dependency_after_calendar_end",
                    "blocking_item_id": item_id,
                    "blocking_prerequisites": [prerequisite_id],
                    "earliest_start": None,
                    "anchor_date": (
                        None
                        if item.anchor_date is None
                        else item.anchor_date.isoformat()
                    ),
                    "horizon_upper": upper.isoformat(),
                    "plan": None,
                }

            if readiness > lower:
                lower = readiness
                blocking = [prerequisite_id]
            elif readiness == lower:
                blocking.append(prerequisite_id)

        if item.anchor_date is not None:
            if item.anchor_date < lower:
                return {
                    "proof_status": "PROVEN_INFEASIBLE",
                    "reason": "anchor_before_readiness",
                    "blocking_item_id": item_id,
                    "blocking_prerequisites": blocking,
                    "earliest_start": lower.isoformat(),
                    "anchor_date": item.anchor_date.isoformat(),
                    "horizon_upper": upper.isoformat(),
                    "plan": None,
                }

            if item.anchor_date > upper:
                return {
                    "proof_status": "PROVEN_INFEASIBLE",
                    "reason": "anchor_after_horizon",
                    "blocking_item_id": item_id,
                    "blocking_prerequisites": blocking,
                    "earliest_start": lower.isoformat(),
                    "anchor_date": item.anchor_date.isoformat(),
                    "horizon_upper": upper.isoformat(),
                    "plan": None,
                }

            start = item.anchor_date

        else:
            if lower > upper:
                return {
                    "proof_status": "PROVEN_INFEASIBLE",
                    "reason": "earliest_start_after_horizon",
                    "blocking_item_id": item_id,
                    "blocking_prerequisites": blocking,
                    "earliest_start": lower.isoformat(),
                    "anchor_date": None,
                    "horizon_upper": upper.isoformat(),
                    "plan": None,
                }

            start = lower

        # Same-day placement of all canonical pieces is hard-legal.
        for session_index in range(len(pieces)):
            placements.append(
                SessionPlacement(
                    item_id=item_id,
                    session_index=session_index,
                    scheduled_date=start,
                )
            )

        completion[item_id] = start

    state = SearchState(
        problem=problem,
        placements=tuple(placements),
    )

    plan = state.to_plan()
    validation = validate_plan(problem, plan)

    if validation.violations or validation.infeasibilities:
        raise AssertionError(
            "Constructed feasibility witness failed frozen validation: "
            f"violations={validation.violations}, "
            f"infeasibilities={validation.infeasibilities}"
        )

    return {
        "proof_status": "PROVEN_FEASIBLE",
        "reason": "earliest_hard_legal_witness",
        "blocking_item_id": None,
        "blocking_prerequisites": [],
        "earliest_start": None,
        "anchor_date": None,
        "horizon_upper": upper.isoformat(),
        "plan": plan,
    }


def load_round_records(archive: Path):
    tmp = tempfile.TemporaryDirectory(prefix="arc-c7-hard-feas-")
    root = Path(tmp.name)

    with tarfile.open(archive, "r:gz") as tf:
        tf.extractall(root)

    run_roots = [
        p
        for p in root.iterdir()
        if p.is_dir() and p.name.startswith("ARC_C7_4A_R1_")
    ]

    if len(run_roots) != 1:
        tmp.cleanup()
        raise RuntimeError(
            f"Unexpected Round-1 archive structure: {run_roots}"
        )

    records_files = list(
        run_roots[0].glob("objective_*/records.jsonl")
    )

    if len(records_files) != 1:
        tmp.cleanup()
        raise RuntimeError(
            f"Expected one records.jsonl, found {len(records_files)}"
        )

    by_scenario = defaultdict(list)

    with records_files[0].open(encoding="utf-8") as stream:
        for line in stream:
            record = json.loads(line)
            by_scenario[record["scenario_id"]].append(record)

    return tmp, by_scenario


def main():
    archive = find_round_archive()
    tmp, by_scenario = load_round_records(archive)

    try:
        rows = []

        print("=" * 90)
        print("ARC C7 HARD-FEASIBILITY CLASSIFIER")
        print("=" * 90)
        print(f"archive={archive}")
        print(f"horizon_days={HORIZON_DAYS}")
        print(f"development_scenarios={len(by_scenario)}")
        print()

        for index, scenario_id in enumerate(
            sorted(by_scenario),
            start=1,
        ):
            records = by_scenario[scenario_id]
            observed = observed_category(records)

            reconstructed = reconstruct_v1_scenario(scenario_id)
            problem = reconstructed.problem
            features = reconstructed.regenerated_features

            proof = classify(problem)

            row = {
                "scenario_id": scenario_id,
                "observed_category": observed,
                "proof_status": proof["proof_status"],
                "reason": proof["reason"],
                "blocking_item_id": proof["blocking_item_id"],
                "blocking_prerequisites": ",".join(
                    map(str, proof["blocking_prerequisites"])
                ),
                "earliest_start": proof["earliest_start"],
                "anchor_date": proof["anchor_date"],
                "horizon_upper": proof["horizon_upper"],
                "item_count": len(problem.items),
                "session_count": sum(
                    len(session_pieces(item))
                    for item in problem.items
                ),
                "anchor_count": features.get("anchor_count"),
                "anchor_fraction": features.get("anchor_fraction"),
                "dependency_edge_count": features.get(
                    "dependency_edge_count"
                ),
                "dependency_blocked_fraction": features.get(
                    "dependency_blocked_fraction"
                ),
                "pressure_due_14d_count": features.get(
                    "pressure_due_14d_count"
                ),
                "overdue_fraction": features.get("overdue_fraction"),
                "temporal_span_days": features.get(
                    "temporal_span_days"
                ),
            }

            rows.append(row)

            marker = (
                "!!!"
                if (
                    observed == "all_constructor_invalid"
                    and proof["proof_status"] == "PROVEN_FEASIBLE"
                )
                else "   "
            )

            print(
                f"{marker} "
                f"[{index:02d}/{len(by_scenario):02d}] "
                f"{scenario_id:9s} | "
                f"{observed:23s} | "
                f"{proof['proof_status']:17s} | "
                f"{proof['reason']}"
            )

        desktop = Path.home() / "Desktop"

        out_json = (
            desktop
            / "ARC_C7_HARD_FEASIBILITY_CLASSIFICATION.json"
        )

        out_csv = (
            desktop
            / "ARC_C7_HARD_FEASIBILITY_CLASSIFICATION.csv"
        )

        summary = {
            "overall_proof_status": dict(
                Counter(row["proof_status"] for row in rows)
            ),
            "observed_category": dict(
                Counter(row["observed_category"] for row in rows)
            ),
            "all_invalid_proof_status": dict(
                Counter(
                    row["proof_status"]
                    for row in rows
                    if row["observed_category"]
                    == "all_constructor_invalid"
                )
            ),
            "all_timeout_proof_status": dict(
                Counter(
                    row["proof_status"]
                    for row in rows
                    if row["observed_category"]
                    == "all_timeout"
                )
            ),
            "constructor_failure_but_proven_feasible": [
                row["scenario_id"]
                for row in rows
                if (
                    row["observed_category"]
                    == "all_constructor_invalid"
                    and row["proof_status"] == "PROVEN_FEASIBLE"
                )
            ],
            "timeout_but_proven_feasible": [
                row["scenario_id"]
                for row in rows
                if (
                    row["observed_category"] == "all_timeout"
                    and row["proof_status"] == "PROVEN_FEASIBLE"
                )
            ],
            "infeasibility_reasons": dict(
                Counter(
                    row["reason"]
                    for row in rows
                    if row["proof_status"]
                    == "PROVEN_INFEASIBLE"
                )
            ),
        }

        payload = {
            "source_archive": str(archive),
            "horizon_days": HORIZON_DAYS,
            "proof_basis": (
                "Frozen hard constraints are monotone lower-bound "
                "temporal constraints plus exact first-session anchors. "
                "Deadlines/capacity/overload are soft. Therefore the "
                "earliest hard-legal schedule is a complete feasibility "
                "witness; failure of that earliest schedule at an anchor "
                "or finite horizon proves infeasibility."
            ),
            "summary": summary,
            "rows": rows,
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
        print("=" * 90)
        print("SUMMARY")
        print("=" * 90)

        print(
            "overall_proof_status="
            + json.dumps(
                summary["overall_proof_status"],
                sort_keys=True,
            )
        )

        print(
            "observed_category="
            + json.dumps(
                summary["observed_category"],
                sort_keys=True,
            )
        )

        print(
            "all_invalid_proof_status="
            + json.dumps(
                summary["all_invalid_proof_status"],
                sort_keys=True,
            )
        )

        print(
            "all_timeout_proof_status="
            + json.dumps(
                summary["all_timeout_proof_status"],
                sort_keys=True,
            )
        )

        print(
            "infeasibility_reasons="
            + json.dumps(
                summary["infeasibility_reasons"],
                sort_keys=True,
            )
        )

        print()
        print(
            "ALL-CONSTRUCTOR-INVALID BUT PROVEN FEASIBLE:"
        )

        failures = (
            summary["constructor_failure_but_proven_feasible"]
        )

        if failures:
            for scenario_id in failures:
                print(f"  {scenario_id}")
        else:
            print("  NONE")

        print()
        print("ALL-TIMEOUT BUT PROVEN FEASIBLE:")

        timeout_feasible = (
            summary["timeout_but_proven_feasible"]
        )

        if timeout_feasible:
            for scenario_id in timeout_feasible:
                print(f"  {scenario_id}")
        else:
            print("  NONE")

        print()
        print("OUTPUTS")
        print(out_json)
        print(out_csv)

        # -------------------------------------------------------------
        # Cross-check against the exact-oracle probe if it exists.
        # This does NOT make the analytical proof depend on C5.
        # It simply checks agreement with the certificates we already ran.
        # -------------------------------------------------------------
        probe = (
            desktop
            / "ARC_C7_EXACT_SMALL_PROBE.json"
        )

        if probe.exists():
            exact = json.loads(
                probe.read_text(encoding="utf-8")
            )

            row_by_id = {
                row["scenario_id"]: row
                for row in rows
            }

            print()
            print("=" * 90)
            print("C5 CROSS-CHECK")
            print("=" * 90)

            mismatches = []

            for exact_row in exact["results"]:
                scenario_id = exact_row["scenario_id"]
                exact_status = exact_row["status"]

                if exact_status not in {
                    "optimal",
                    "infeasible",
                }:
                    continue

                analytical = row_by_id[
                    scenario_id
                ]["proof_status"]

                expected = (
                    "PROVEN_FEASIBLE"
                    if exact_status == "optimal"
                    else "PROVEN_INFEASIBLE"
                )

                ok = analytical == expected

                print(
                    f"{scenario_id}: "
                    f"C5={exact_status} | "
                    f"analytical={analytical} | "
                    f"{'MATCH' if ok else 'MISMATCH'}"
                )

                if not ok:
                    mismatches.append(
                        (
                            scenario_id,
                            exact_status,
                            analytical,
                        )
                    )

            if mismatches:
                raise AssertionError(
                    "Analytical/C5 feasibility mismatch: "
                    f"{mismatches}"
                )

            print("C5 cross-check: PASS")

    finally:
        tmp.cleanup()


if __name__ == "__main__":
    main()
