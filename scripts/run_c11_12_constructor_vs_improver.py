from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


from arena.production.flavour_planner import (
    generate_flavour_schedule,
)
from arena.production.production_improver import (
    ProductionImproveConfig,
    improve_production_schedule,
)
from arena.scheduling.domain import (
    DependencyEdge,
    ScheduleItem,
    ScheduleProblem,
)


D = Decimal
TODAY = date(2026, 10, 12)
DAY = timedelta(days=1)


def item(
    item_id,
    duration,
    *,
    release=None,
    due=None,
    anchor=None,
    priority=None,
):
    return ScheduleItem(
        item_id=item_id,
        duration_category=duration,
        priority_position=priority,
        release_date=release,
        due_date=due,
        anchor_date=anchor,
        percent_completed=D("0"),
        remaining_fraction=D("1"),
    )


def problem(
    items,
    dependencies=(),
):
    return ScheduleProblem(
        today=TODAY,
        items=tuple(items),
        dependencies=tuple(
            dependencies
        ),
        capacity_by_duration={
            "UNDER_20_MINUTES": 10,
            "UNDER_1_HOUR": 10,
            "UNDER_4_HOURS": 10,
            "UNDER_8_HOURS": 10,
            "UNDER_16_HOURS": 10,
            "OVER_16_HOURS": 10,
        },
    )


def print_schedule(
    label,
    schedule,
):
    print()
    print(label)
    print("-" * len(label))

    rows = {}

    for allocation in (
        schedule.work_allocations
    ):
        rows.setdefault(
            allocation.scheduled_date,
            [],
        ).append(allocation)

    for day in sorted(
        schedule.daily_hours
    ):
        hours = (
            schedule.daily_hours[
                day
            ]
        )

        status = (
            schedule.daily_status[
                day
            ].value
        )

        print(
            f"{day}  "
            f"{hours:.2f}h  "
            f"[{status}]"
        )

        for row in sorted(
            rows.get(
                day,
                [],
            ),
            key=lambda row:
                row.item_id,
        ):
            print(
                "  "
                f"task {row.item_id}: "
                f"{row.hours:.2f}h "
                f"({row.percentage}%)"
            )


def run(
    name,
    p,
    estimates,
):
    print()
    print("=" * 78)
    print(name)
    print("=" * 78)

    for flavour in (
        "lock-in",
        "monk",
    ):
        initial = (
            generate_flavour_schedule(
                p,
                flavour,
                explicit_total_hours=
                    estimates,
            )
        )

        result = (
            improve_production_schedule(
                p,
                initial,
                ProductionImproveConfig(
                    max_iterations=40,
                    max_evaluations=4000,
                ),
            )
        )

        print_schedule(
            f"{flavour.upper()} — CONSTRUCTOR",
            initial,
        )

        print_schedule(
            f"{flavour.upper()} — AFTER PRODUCTION IMPROVER",
            result.final_schedule,
        )

        print()
        print(
            "objective_before="
            f"{result.initial_objective.key}"
        )
        print(
            "objective_after ="
            f"{result.final_objective.key}"
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


def main():
    future_anchor_wall = problem([
        item(
            1,
            "OVER_16_HOURS",
            due=TODAY + 4 * DAY,
        ),
        item(
            2,
            "UNDER_4_HOURS",
            anchor=TODAY + 2 * DAY,
        ),
        item(
            3,
            "UNDER_4_HOURS",
            anchor=TODAY + 2 * DAY,
        ),
        item(
            4,
            "UNDER_1_HOUR",
            anchor=TODAY + 2 * DAY,
        ),
        item(
            5,
            "UNDER_1_HOUR",
            anchor=TODAY + 2 * DAY,
        ),
        item(
            6,
            "UNDER_4_HOURS",
            anchor=TODAY + 3 * DAY,
        ),
        item(
            7,
            "UNDER_4_HOURS",
            anchor=TODAY + 3 * DAY,
        ),
        item(
            8,
            "UNDER_1_HOUR",
            anchor=TODAY + 3 * DAY,
        ),
        item(
            9,
            "UNDER_1_HOUR",
            anchor=TODAY + 3 * DAY,
        ),
    ])

    run(
        "FUTURE ANCHOR WALL",
        future_anchor_wall,
        {
            1: D("30"),
            2: D("4"),
            3: D("4"),
            4: D("1"),
            5: D("1"),
            6: D("4"),
            7: D("4"),
            8: D("1"),
            9: D("1"),
        },
    )

    dependency = problem(
        [
            item(
                1,
                "UNDER_16_HOURS",
            ),
            item(
                2,
                "UNDER_16_HOURS",
                due=TODAY + 3 * DAY,
            ),
            item(
                3,
                "UNDER_8_HOURS",
                due=TODAY + 10 * DAY,
            ),
        ],
        dependencies=(
            DependencyEdge(
                1,
                2,
            ),
        ),
    )

    run(
        "DOWNSTREAM DEADLINE DEPENDENCY",
        dependency,
        {
            1: D("12"),
            2: D("10"),
            3: D("6"),
        },
    )

    release_collision = problem([
        item(
            1,
            "OVER_16_HOURS",
            due=TODAY + 5 * DAY,
        ),
        item(
            2,
            "UNDER_16_HOURS",
            release=TODAY + DAY,
            due=TODAY + 2 * DAY,
        ),
        item(
            3,
            "UNDER_16_HOURS",
            release=TODAY + DAY,
            due=TODAY + 2 * DAY,
        ),
    ])

    run(
        "KNOWN FUTURE RELEASE COLLISION",
        release_collision,
        {
            1: D("20"),
            2: D("10"),
            3: D("10"),
        },
    )


if __name__ == "__main__":
    main()
