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
):
    return ScheduleItem(
        item_id=item_id,
        duration_category=duration,
        priority_position=None,
        release_date=release,
        due_date=due,
        anchor_date=anchor,
        percent_completed=D("0"),
        remaining_fraction=D("1"),
    )


def problem(items):
    return ScheduleProblem(
        today=TODAY,
        items=tuple(items),
        dependencies=(),
        capacity_by_duration={
            "UNDER_20_MINUTES": 10,
            "UNDER_1_HOUR": 10,
            "UNDER_4_HOURS": 10,
            "UNDER_8_HOURS": 10,
            "UNDER_16_HOURS": 10,
            "OVER_16_HOURS": 10,
        },
    )


def show(title, generated):
    print()
    print(title)
    print("-" * len(title))

    by_day = {}

    for row in generated.work_allocations:
        by_day.setdefault(
            row.scheduled_date,
            [],
        ).append(row)

    for day in sorted(by_day):
        print(
            f"{day.isoformat()}  "
            f"{generated.daily_hours[day]:.2f}h total  "
            f"[{generated.daily_status[day].value}]"
        )

        for row in sorted(
            by_day[day],
            key=lambda r: r.item_id,
        ):
            print(
                f"  task {row.item_id}: "
                f"{row.hours:.2f}h "
                f"({row.percentage}%)"
            )


def main():
    anchored = problem([
        item(
            1,
            "OVER_16_HOURS",
            due=TODAY + 14 * DAY,
        ),
        item(
            2,
            "UNDER_4_HOURS",
            anchor=TODAY + DAY,
        ),
        item(
            3,
            "UNDER_4_HOURS",
            anchor=TODAY + DAY,
        ),
        item(
            4,
            "UNDER_1_HOUR",
            anchor=TODAY + DAY,
        ),
        item(
            5,
            "UNDER_1_HOUR",
            anchor=TODAY + DAY,
        ),
    ])

    urgent = problem([
        item(
            1,
            "OVER_16_HOURS",
            due=TODAY + 14 * DAY,
        ),
        item(
            2,
            "UNDER_4_HOURS",
            release=TODAY + DAY,
            due=TODAY + DAY,
        ),
        item(
            3,
            "UNDER_4_HOURS",
            release=TODAY + DAY,
            due=TODAY + DAY,
        ),
        item(
            4,
            "UNDER_1_HOUR",
            release=TODAY + DAY,
            due=TODAY + DAY,
        ),
        item(
            5,
            "UNDER_1_HOUR",
            release=TODAY + DAY,
            due=TODAY + DAY,
        ),
    ])

    estimates = {
        1: D("24"),
        2: D("4"),
        3: D("4"),
        4: D("1"),
        5: D("1"),
    }

    print("=" * 72)
    print("C11.9 ADAPTIVE INTERRUPTION HUMAN REVIEW")
    print("Task 1 is the 24h large task.")
    print("=" * 72)

    for flavour in (
        "lock-in",
        "monk",
    ):
        generated = generate_flavour_schedule(
            anchored,
            flavour,
            explicit_total_hours=estimates,
        )

        show(
            f"{flavour.upper()} — ANCHORED INTERRUPTION",
            generated,
        )

    for flavour in (
        "lock-in",
        "monk",
    ):
        generated = generate_flavour_schedule(
            urgent,
            flavour,
            explicit_total_hours=estimates,
        )

        show(
            f"{flavour.upper()} — URGENT RELEASE INTERRUPTION",
            generated,
        )

    print()
    print(
        "EXPECTED SHAPE FOR TASK 1: "
        "Oct 12 progress -> Oct 13 absent -> Oct 14 resume"
    )


if __name__ == "__main__":
    main()
