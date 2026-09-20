"""Run A0 through every micro hard-invariant benchmark."""

from __future__ import annotations

import os
import sys
from collections import Counter
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"

sys.path.insert(0, str(BACKEND))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "arc_backend.settings")

import django

django.setup()

from accounts.models import User
from planning.models import PlanningItem

from arena.algorithms.arc_baseline import NAME, run
from arena.datasets.importer import _rows, load_scenario
from arena.evaluation.invariants import (
    execution_frontier,
    validate_schedule,
)


def main():
    scenario_rows = [
        row
        for row in _rows("scenarios.csv")
        if row["family"] == "micro"
    ]

    print("=" * 78)
    print("A0 HARD-INVARIANT GAUNTLET")
    print(f"Algorithm: {NAME}")
    print("=" * 78)

    results = []

    for meta in scenario_rows:
        scenario = meta["scenario"]
        benchmark_today = date.fromisoformat(meta["today"])

        try:
            # Fresh DB state for every scenario.
            load_scenario(scenario)

            user = User.objects.get(email="arena@local.test")

            frontier_before = len(execution_frontier(user))

            result = run(user, benchmark_today)

            violations = validate_schedule(
                user,
                benchmark_today=benchmark_today,
                anchored_before=result["anchored_before"],
                completed_before=result["completed_before"],
            )

            scheduled = PlanningItem.objects.filter(
                user=user,
                is_deleted=False,
                is_completed=False,
                scheduled_date__isnull=False,
            ).count()

            results.append(
                {
                    "scenario": scenario,
                    "passed": not violations,
                    "violations": violations,
                    "frontier": frontier_before,
                    "scheduled": scheduled,
                    "error": None,
                }
            )

        except Exception as exc:
            results.append(
                {
                    "scenario": scenario,
                    "passed": False,
                    "violations": [],
                    "frontier": None,
                    "scheduled": None,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )

    print()
    print(f"{'SCENARIO':<38} {'RESULT':<8} {'FRONTIER':>8} {'SCHEDULED':>10}")
    print("-" * 78)

    for result in results:
        status = "PASS" if result["passed"] else "FAIL"

        frontier = (
            str(result["frontier"])
            if result["frontier"] is not None
            else "-"
        )
        scheduled = (
            str(result["scheduled"])
            if result["scheduled"] is not None
            else "-"
        )

        print(
            f"{result['scenario']:<38} "
            f"{status:<8} "
            f"{frontier:>8} "
            f"{scheduled:>10}"
        )

    failures = [r for r in results if not r["passed"]]

    if failures:
        print()
        print("=" * 78)
        print("FAILURE DETAILS")
        print("=" * 78)

        for result in failures:
            print()
            print(result["scenario"])
            print("-" * len(result["scenario"]))

            if result["error"]:
                print(f"ERROR: {result['error']}")
                continue

            counts = Counter(v.kind for v in result["violations"])

            for kind, count in sorted(counts.items()):
                print(f"{kind:<30} {count}")

            for violation in result["violations"]:
                print(
                    f"  [{violation.kind}] "
                    f"{violation.title}: {violation.detail}"
                )

    passed = sum(r["passed"] for r in results)
    total = len(results)

    print()
    print("=" * 78)
    print(f"RESULT: {passed}/{total} micro scenarios passed")
    print("=" * 78)

    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
