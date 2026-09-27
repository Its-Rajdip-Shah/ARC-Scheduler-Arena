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
from arena.scheduling.domain import (
    DependencyEdge,
    ScheduleItem,
    ScheduleProblem,
)
from arena.scheduling.validation import (
    validate_plan,
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
    completed="0",
):
    completed_d = D(completed)

    return ScheduleItem(
        item_id=item_id,
        duration_category=duration,
        priority_position=priority,
        release_date=release,
        due_date=due,
        anchor_date=anchor,
        percent_completed=completed_d,
        remaining_fraction=(
            D("1")
            - completed_d / D("100")
        ),
    )


def problem(
    items,
    dependencies=(),
):
    return ScheduleProblem(
        today=TODAY,
        items=tuple(items),
        dependencies=tuple(dependencies),
        capacity_by_duration={
            "UNDER_20_MINUTES": 10,
            "UNDER_1_HOUR": 10,
            "UNDER_4_HOURS": 10,
            "UNDER_8_HOURS": 10,
            "UNDER_16_HOURS": 10,
            "OVER_16_HOURS": 10,
        },
    )


def show(
    scenario_name,
    flavour,
    generated,
    p,
):
    print()
    print("=" * 78)
    print(
        f"{scenario_name} — {flavour.upper()}"
    )
    print("=" * 78)

    rows_by_day = {}

    for row in generated.work_allocations:
        rows_by_day.setdefault(
            row.scheduled_date,
            [],
        ).append(row)

    first = min(
        rows_by_day
    )
    last = max(
        rows_by_day
    )

    day = first

    while day <= last:
        rows = rows_by_day.get(
            day,
            [],
        )

        hours = generated.daily_hours.get(
            day,
            D("0"),
        )

        status = generated.daily_status.get(
            day,
        )

        status_text = (
            "empty"
            if status is None
            else status.value
        )

        print(
            f"{day.isoformat()}  "
            f"{hours:.2f}h  "
            f"[{status_text}]"
        )

        if not rows:
            print("  — empty —")

        for row in sorted(
            rows,
            key=lambda r: r.item_id,
        ):
            source = p.item_by_id[
                row.item_id
            ]

            bits = []

            if source.release_date:
                bits.append(
                    "release="
                    + source.release_date.isoformat()
                )

            if source.due_date:
                bits.append(
                    "due="
                    + source.due_date.isoformat()
                )

            if source.anchor_date:
                bits.append(
                    "anchor="
                    + source.anchor_date.isoformat()
                )

            suffix = (
                ""
                if not bits
                else " | " + ", ".join(bits)
            )

            print(
                f"  task {row.item_id}: "
                f"{row.hours:.2f}h "
                f"({row.percentage}%)"
                f"{suffix}"
            )

        day += DAY

    validation = validate_plan(
        p,
        generated.plan,
    )

    print()
    print(
        "hard_violations="
        f"{len(validation.violations)}"
    )

    print(
        "soft_violations="
        f"{len(validation.soft_violations)}"
    )


def run_scenario(
    name,
    p,
    estimates,
):
    for flavour in (
        "lock-in",
        "monk",
    ):
        generated = (
            generate_flavour_schedule(
                p,
                flavour,
                explicit_total_hours=
                    estimates,
            )
        )

        show(
            name,
            flavour,
            generated,
            p,
        )


def main():
    print()
    print("#" * 78)
    print("C11.11 WONKY LOOK-AHEAD / ADAPTIVENESS REVIEW")
    print("#" * 78)

    # ------------------------------------------------------------------
    # 1. Future anchor wall
    #
    # Big 30h task is available now and due after two future days that are
    # already known to contain 10h of anchored work each.
    #
    # Question:
    # Does the planner anticipate that future congestion, or leave a huge
    # deadline-day remainder?
    # ------------------------------------------------------------------

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

    run_scenario(
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

    # ------------------------------------------------------------------
    # 2. Known future urgent release
    #
    # A large task is available now. Tomorrow another large urgent body of
    # work will release and shortly become due.
    #
    # Release dates are known metadata, even though those tasks are not yet
    # executable.
    #
    # Question:
    # Does today's allocation make sensible use of today's freedom?
    # ------------------------------------------------------------------

    future_release_collision = problem([
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

    run_scenario(
        "KNOWN FUTURE RELEASE COLLISION",
        future_release_collision,
        {
            1: D("20"),
            2: D("10"),
            3: D("10"),
        },
    )

    # ------------------------------------------------------------------
    # 3. Downstream deadline dependency
    #
    # Task 1 itself has no deadline.
    # Task 2 cannot begin until task 1 completes and task 2 is due soon.
    #
    # Question:
    # Does urgency propagate backward through the dependency?
    # ------------------------------------------------------------------

    downstream_dependency = problem(
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

    run_scenario(
        "DOWNSTREAM DEADLINE DEPENDENCY",
        downstream_dependency,
        {
            1: D("12"),
            2: D("10"),
            3: D("6"),
        },
    )

    # ------------------------------------------------------------------
    # 4. Two competing large tasks
    #
    # Both are large and due close together.
    # One gets started first.
    #
    # Question:
    # Does continuity become starvation of the second task?
    # ------------------------------------------------------------------

    competing_large = problem([
        item(
            1,
            "OVER_16_HOURS",
            due=TODAY + 5 * DAY,
            priority=1,
        ),
        item(
            2,
            "OVER_16_HOURS",
            due=TODAY + 5 * DAY,
            priority=2,
        ),
    ])

    run_scenario(
        "COMPETING LARGE TASKS",
        competing_large,
        {
            1: D("20"),
            2: D("20"),
        },
    )

    # ------------------------------------------------------------------
    # 5. Partial progress + future anchored congestion
    #
    # Task already has momentum and only part remains.
    #
    # Question:
    # Is remaining work treated adaptively rather than as original size?
    # ------------------------------------------------------------------

    partial_future_pressure = problem([
        item(
            1,
            "OVER_16_HOURS",
            due=TODAY + 4 * DAY,
            completed="50",
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
    ])

    run_scenario(
        "PARTIAL PROGRESS + FUTURE PRESSURE",
        partial_future_pressure,
        {
            1: D("30"),
            2: D("4"),
            3: D("4"),
            4: D("1"),
        },
    )

    print()
    print("#" * 78)
    print("END C11.11 REVIEW")
    print("#" * 78)


if __name__ == "__main__":
    main()
