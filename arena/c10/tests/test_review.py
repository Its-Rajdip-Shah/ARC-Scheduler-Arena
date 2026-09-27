from datetime import date
from decimal import Decimal

from arena.c10.review import (
    calendar_rows,
    render_review_markdown,
)
from arena.scheduling.domain import (
    Allocation,
    ScheduleItem,
    SchedulePlan,
    ScheduleProblem,
)


def _problem():
    return ScheduleProblem(
        today=date(2026, 9, 28),
        items=(
            ScheduleItem(
                item_id=1,
                duration_category=
                    "UNDER_4_HOURS",
                priority_position=1,
                release_date=None,
                due_date=date(
                    2026,
                    10,
                    1,
                ),
                anchor_date=None,
                percent_completed=
                    Decimal("0"),
                remaining_fraction=
                    Decimal("1"),
            ),
        ),
        dependencies=(),
        capacity_by_duration={
            "UNDER_4_HOURS": 3,
        },
    )


def test_calendar_rows_are_human_readable():
    problem = _problem()

    plan = SchedulePlan(
        allocations=(
            Allocation(
                item_id=1,
                scheduled_date=date(
                    2026,
                    9,
                    29,
                ),
                percentage=
                    Decimal("100"),
                execution_rank=1,
            ),
        )
    )

    rows = calendar_rows(
        problem,
        plan,
        key_by_id={
            1: "task",
        },
        display_names={
            "task": "Important task",
        },
        groups={
            "task": "Course",
        },
    )

    assert rows == [{
        "scheduled_date":
            "2026-09-29",
        "weekday":
            "Tuesday",
        "execution_rank":
            1,
        "percentage":
            "100",
        "item_key":
            "task",
        "display_name":
            "Important task",
        "group":
            "Course",
        "duration_category":
            "UNDER_4_HOURS",
        "priority_position":
            1,
        "release_date":
            None,
        "due_date":
            "2026-10-01",
        "anchor_date":
            None,
        "remaining_fraction":
            "1",
    }]


def test_markdown_review_is_not_a_scalar_score():
    text = render_review_markdown(
        label="candidate",
        role="robust_core",
        status="ok",
        run_seed=1901,
        wall_seconds=1.0,
        algorithm_seconds=0.9,
        rows=[],
        performance=None,
    )

    assert (
        "External human-review checklist"
        in text
    )

    assert (
        "No scalar human-friendliness "
        "score is recorded."
        in text
    )
