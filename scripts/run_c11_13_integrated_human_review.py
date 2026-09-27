from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


from arena.production.flavour_planner import (
    generate_flavour_schedule,
)
from arena.production.integrated_fixture import (
    build_c11_13_base_world,
)
from arena.production.production_improver import (
    ProductionImproveConfig,
    improve_production_schedule,
)
from arena.production.work_mass import (
    validate_dynamic_plan,
)


D = Decimal


def metadata_text(
    item,
) -> str:
    bits = []

    if item.release_date is not None:
        bits.append(
            "release="
            + item.release_date.isoformat()
        )

    if item.due_date is not None:
        bits.append(
            "due="
            + item.due_date.isoformat()
        )

    if item.anchor_date is not None:
        bits.append(
            "anchor="
            + item.anchor_date.isoformat()
        )

    if item.priority_position is not None:
        bits.append(
            "priority="
            + str(item.priority_position)
        )

    if item.percent_completed > 0:
        bits.append(
            "already_done="
            + str(item.percent_completed)
            + "%"
        )

    if not bits:
        return ""

    return " | " + ", ".join(bits)


def print_legend(
    world,
) -> None:
    print()
    print("=" * 96)
    print("TASK LEGEND")
    print("=" * 96)

    for item in world.problem.items:
        total = world.explicit_total_hours[
            item.item_id
        ]

        remaining = (
            total
            * item.remaining_fraction
        )

        print(
            f"{item.item_id:>2}. "
            f"{world.labels[item.item_id]}"
        )

        print(
            "    "
            f"total estimate={total}h"
            f" | remaining={remaining}h"
            f" | bucket={item.duration_category}"
            f"{metadata_text(item)}"
        )

    print()
    print("DEPENDENCIES")

    for edge in world.problem.dependencies:
        print(
            "  "
            f"{edge.prerequisite_id} "
            f"({world.labels[edge.prerequisite_id]})"
            "  ->  "
            f"{edge.dependent_id} "
            f"({world.labels[edge.dependent_id]})"
        )


def print_calendar(
    flavour,
    schedule,
    world,
) -> None:
    rows_by_day = defaultdict(list)

    for row in schedule.work_allocations:
        rows_by_day[
            row.scheduled_date
        ].append(row)

    print()
    print("=" * 96)
    print(
        f"{flavour.upper()} — FINAL IMPROVED HUMAN CALENDAR"
    )
    print("=" * 96)

    for day in sorted(
        schedule.daily_hours
    ):
        hours = schedule.daily_hours[
            day
        ]

        status = schedule.daily_status[
            day
        ].value

        print()
        print(
            f"{day.strftime('%a %d %b %Y').upper()}"
            f"   {hours:.2f}h"
            f"   [{status.upper()}]"
        )

        print("-" * 96)

        rows = rows_by_day.get(
            day,
            (),
        )

        if not rows:
            print("  — EMPTY —")
            continue

        for row in sorted(
            rows,
            key=lambda row: (
                row.item_id,
                row.hours,
            ),
        ):
            item = world.problem.item_by_id[
                row.item_id
            ]

            print(
                f"  #{row.item_id:02d} "
                f"{world.labels[row.item_id]}"
            )

            print(
                "       "
                f"{row.hours:.2f}h"
                f" | {row.percentage}%"
                f"{metadata_text(item)}"
            )


def print_task_summary(
    schedule,
    world,
) -> None:
    rows_by_item = defaultdict(list)

    for row in schedule.work_allocations:
        rows_by_item[
            row.item_id
        ].append(row)

    print()
    print("=" * 96)
    print("TASK-BY-TASK SUMMARY")
    print("=" * 96)

    for item in world.problem.items:
        rows = sorted(
            rows_by_item[item.item_id],
            key=lambda row:
                row.scheduled_date,
        )

        start = min(
            row.scheduled_date
            for row in rows
        )

        finish = max(
            row.scheduled_date
            for row in rows
        )

        hours = sum(
            row.hours
            for row in rows
        )

        dates = ", ".join(
            (
                row.scheduled_date
                .strftime("%d %b")
                + f"({row.hours:.2f}h)"
            )
            for row in rows
        )

        print(
            f"#{item.item_id:02d} "
            f"{world.labels[item.item_id]}"
        )

        print(
            "    "
            f"{hours:.2f}h across "
            f"{len(rows)} allocation(s)"
            f" | {start} -> {finish}"
        )

        print(
            "    "
            + dates
        )


def main() -> int:
    world = build_c11_13_base_world()

    print()
    print("#" * 96)
    print(
        "C11.13 INTEGRATED ADVERSARIAL HUMAN REVIEW"
    )
    print("#" * 96)

    print()
    print(
        "This is intentionally ONE shared world."
    )

    print(
        "Judge each allocation in relation to every "
        "other task already competing for the calendar."
    )

    print_legend(
        world
    )

    overall_rc = 0

    for flavour in (
        "lock-in",
        "monk",
    ):
        initial = generate_flavour_schedule(
            world.problem,
            flavour,
            explicit_total_hours=
                world.explicit_total_hours,
        )

        result = improve_production_schedule(
            world.problem,
            initial,
            ProductionImproveConfig(
                max_iterations=60,
                max_evaluations=8000,
            ),
        )

        final = result.final_schedule

        validation = validate_dynamic_plan(
            world.problem,
            final.plan,
        )

        print_calendar(
            flavour,
            final,
            world,
        )

        print_task_summary(
            final,
            world,
        )

        print()
        print("=" * 96)
        print(
            f"{flavour.upper()} — SEARCH / VALIDATION SUMMARY"
        )
        print("=" * 96)

        print(
            "objective_before="
            f"{result.initial_objective.key}"
        )

        print(
            "objective_after ="
            f"{result.final_objective.key}"
        )

        print(
            "improved="
            f"{result.improved}"
        )

        print(
            "accepted_moves="
            f"{len(result.accepted_moves)}"
        )

        print(
            "evaluations="
            f"{result.evaluations}"
        )

        print(
            "termination="
            f"{result.termination_reason}"
        )

        print(
            "hard_violations="
            f"{len(validation.violations)}"
        )

        print(
            "infeasibilities="
            f"{len(validation.infeasibilities)}"
        )

        print(
            "soft_violations="
            f"{len(validation.soft_violations)}"
        )

        print(
            "late_hours="
            f"{result.final_objective.late_hours}"
        )

        print(
            "peak_day_hours="
            f"{result.final_objective.max_daily_hours}"
        )

        if validation.violations:
            overall_rc = 1

            print(
                "HARD VIOLATION DETAILS:"
            )

            for violation in validation.violations:
                print(
                    "  ",
                    violation,
                )

    print()
    print("#" * 96)
    print("HUMAN PASS QUESTIONS")
    print("#" * 96)

    print(
        """
1. Which individual days feel too heavy even if ARC calls them legal?
2. Which tasks are split too much or too little?
3. Is anything happening too early?
4. Is anything happening too late?
5. Does the 3-stage dependency chain feel natural?
6. Do future-release tasks displace existing work sensibly?
7. Are the anchored jobs handled sensibly around surrounding work?
8. Does partially-completed work resume naturally?
9. Does the 15-minute laundry/admin-scale work land somewhere sensible?
10. Does low-priority urgent work correctly beat high-priority relaxed work?
11. Does Lock-in feel meaningfully more aggressive than Monk?
12. Does Monk actually feel calmer, or merely longer?
13. Any day where you would personally rearrange the order/tasks?
14. Any schedule that is mathematically valid but just feels stupid?
"""
    )

    print(
        "C11_13_BASE_WORLD_HUMAN_REVIEW_READY=1"
    )

    return overall_rc


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
