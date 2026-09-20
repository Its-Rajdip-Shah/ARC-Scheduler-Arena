"""Run the current ARC scheduler against an Arena benchmark scenario."""

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
from arena.datasets.importer import load_scenario, _rows
from arena.evaluation.invariants import execution_frontier, validate_schedule


def full_title(item):
    parts = [item.title]
    parent = item.parent

    while parent is not None:
        parts.append(parent.title)
        parent = parent.parent

    return " | ".join(reversed(parts))


def main():
    scenario = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "realistic_normal_semester"
    )

    print("=" * 72)
    print("ARC SCHEDULER ARENA")
    print("=" * 72)
    print(f"Scenario:  {scenario}")
    print(f"Algorithm: {NAME}")
    print()

    scenario_meta = next(
        row for row in _rows("scenarios.csv")
        if row["scenario"] == scenario
    )
    benchmark_today = date.fromisoformat(scenario_meta["today"])

    load_scenario(scenario)

    user = User.objects.get(email="arena@local.test")

    all_items = PlanningItem.objects.filter(
        user=user,
        is_deleted=False,
    )

    frontier_before = execution_frontier(user)

    print("PRE-RUN")
    print("-" * 72)
    print(f"Planning items:      {all_items.count()}")
    print(f"Execution frontier: {len(frontier_before)}")
    print()

    result = run(user, benchmark_today)

    violations = validate_schedule(
        user,
        benchmark_today=benchmark_today,
        anchored_before=result["anchored_before"],
        completed_before=result["completed_before"],
    )

    scheduled = (
        PlanningItem.objects
        .filter(
            user=user,
            is_deleted=False,
            is_completed=False,
            scheduled_date__isnull=False,
        )
        .select_related("parent")
        .order_by("scheduled_date", "priority_position", "id")
    )

    print("SCHEDULE")
    print("-" * 72)

    current_date = None

    for item in scheduled:
        if item.scheduled_date != current_date:
            current_date = item.scheduled_date
            print()
            print(current_date)

        anchor = " ⚓" if item.schedule_is_manual else ""
        priority = (
            f"P{item.priority_position}"
            if item.priority_position is not None
            else "P-"
        )

        print(
            f"  {priority:<5} "
            f"{full_title(item)}{anchor}"
        )

    print()
    print("=" * 72)
    print("VALIDATION")
    print("=" * 72)

    if not violations:
        print("PASS — no hard-invariant violations")
    else:
        counts = Counter(v.kind for v in violations)

        print(f"FAIL — {len(violations)} violation(s)")
        print()

        for kind, count in sorted(counts.items()):
            print(f"  {kind:<28} {count}")

        print()
        print("DETAILS")
        print("-" * 72)

        for violation in violations:
            print(
                f"[{violation.kind}] "
                f"{violation.title}: "
                f"{violation.detail}"
            )

    print()
    print("=" * 72)
    print(
        f"Scheduled: {scheduled.count()} | "
        f"Frontier before run: {len(frontier_before)} | "
        f"Violations: {len(violations)}"
    )
    print("=" * 72)


if __name__ == "__main__":
    main()
