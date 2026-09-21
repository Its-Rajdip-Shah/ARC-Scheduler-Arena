"""Materialise ARC Scheduler Arena CSV scenarios into ARC's Django models."""

from __future__ import annotations

import csv
import os
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
RAW_DIR = Path(__file__).resolve().parent / "raw_Datas"

sys.path.insert(0, str(BACKEND_ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "arc_backend.settings")

import django

django.setup()

from accounts.models import User
from planning.models import PlanningItem


DURATION_MAP = {
    "UNDER_20_MIN": "UNDER_20_MIN",
    "MIN_20_TO_60": "MIN_20_TO_60",
    "OVER_60_MIN": "OVER_60_MIN",

    # Experimental buckets collapse into ARC's current largest bucket
    # when benchmarking algorithms against the native ARC schema.
    "HOURS_1_TO_4": "OVER_60_MIN",
    "HOURS_4_TO_12": "OVER_60_MIN",
    "OVER_12_HOURS": "OVER_60_MIN",
}


def _rows(filename: str) -> list[dict[str, str]]:
    with (RAW_DIR / filename).open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def available_scenarios() -> list[str]:
    return [row["scenario"] for row in _rows("scenarios.csv")]


def load_scenario(name: str) -> None:
    scenario_rows = _rows("scenarios.csv")
    item_rows = _rows("items.csv")

    scenario = next(
        (row for row in scenario_rows if row["scenario"] == name),
        None,
    )

    if scenario is None:
        raise ValueError(
            f"Unknown scenario {name!r}. "
            f"Available: {', '.join(available_scenarios())}"
        )

    rows = [row for row in item_rows if row["scenario"] == name]

    if not rows:
        raise ValueError(f"Scenario {name!r} contains no items.")

    # Arena DB is disposable. Keep exactly one benchmark user/state loaded.
    PlanningItem.objects.all().delete()
    User.objects.filter(email="arena@local.test").delete()

    user = User.objects.create_user(
        email="arena@local.test",
        password="arena-local-only",
    )

    by_key: dict[str, PlanningItem] = {}
    remaining = rows[:]

    while remaining:
        progressed = False

        for row in remaining[:]:
            parent_key = row["parent_key"].strip()

            if parent_key and parent_key not in by_key:
                continue

            kwargs = {
                "user": user,
                "title": row["title"],
                "item_type": row["item_type"],
                "parent": by_key.get(parent_key),
                "duration_category": DURATION_MAP[row["duration_class"]],
                "is_completed": row["completed"].lower() == "true",
                "manual_requested_date": (row["scheduled_date"] or None) if row["anchored"].lower() == "true" else None,
            }

            if row["release_date"]:
                kwargs["start_date"] = row["release_date"]

            if row["due_date"]:
                kwargs["due_date"] = row["due_date"]

            if row["scheduled_date"]:
                kwargs["scheduled_date"] = row["scheduled_date"]

            if row["priority"]:
                kwargs["priority_position"] = int(row["priority"])

            item = PlanningItem.objects.create(**kwargs)
            by_key[row["key"]] = item

            remaining.remove(row)
            progressed = True

        if not progressed:
            unresolved = [
                (row["key"], row["parent_key"])
                for row in remaining
            ]
            raise ValueError(
                "Could not resolve hierarchy. Missing/cyclic parents: "
                f"{unresolved}"
            )

    print()
    print(f"Loaded: {name}")
    print(f"Family: {scenario['family']}")
    print(f"Items:  {len(by_key)}")
    print(f"Today:  {scenario['today']}")
    print()


def print_hierarchy() -> None:
    roots = PlanningItem.objects.filter(parent__isnull=True).order_by("id")

    def walk(item: PlanningItem, depth: int = 0) -> None:
        marker = "✓" if item.is_completed else "•"
        anchor = " ⚓" if item.manual_requested_date is not None else ""

        print(
            f"{'    ' * depth}{marker} "
            f"{item.title} [{item.item_type}]{anchor}"
        )

        for child in item.children.order_by("id"):
            walk(child, depth + 1)

    for root in roots:
        walk(root)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python -m arena.datasets.importer <scenario>")
        print()
        print("Available scenarios:")
        for scenario in available_scenarios():
            print(f"  {scenario}")
        raise SystemExit(1)

    load_scenario(sys.argv[1])
    print_hierarchy()
