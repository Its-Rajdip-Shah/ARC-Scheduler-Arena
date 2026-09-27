"""C11.13 integrated production torture-world fixture.

Unlike the earlier isolated adversarial scenarios, this fixture deliberately
places many different scheduling pressures into one shared calendar.

The purpose is human evaluation of interactions between tasks, not merely
isolated legality checks.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from arena.scheduling.domain import (
    DependencyEdge,
    ScheduleItem,
    ScheduleProblem,
)


D = Decimal
TODAY = date(2026, 10, 12)
DAY = timedelta(days=1)


@dataclass(frozen=True, slots=True)
class IntegratedWorld:
    problem: ScheduleProblem
    explicit_total_hours: dict[int, Decimal]
    labels: dict[int, str]


def _item(
    item_id: int,
    duration_category: str,
    *,
    release=None,
    due=None,
    anchor=None,
    priority=None,
    completed="0",
) -> ScheduleItem:
    completed_decimal = D(completed)

    return ScheduleItem(
        item_id=item_id,
        duration_category=duration_category,
        priority_position=priority,
        release_date=release,
        due_date=due,
        anchor_date=anchor,
        percent_completed=completed_decimal,
        remaining_fraction=(
            D("1")
            - completed_decimal / D("100")
        ),
    )


def build_c11_13_base_world() -> IntegratedWorld:
    """Return the first integrated human-review world.

    This intentionally combines:
    - multi-hop dependency urgency;
    - an independent dependency chain;
    - large interruptible work;
    - partial progress;
    - future releases;
    - fixed-date atomic work;
    - tiny chores/admin;
    - priorities conflicting with deadline urgency;
    - relaxed background work.
    """

    items = (
        # ------------------------------------------------------------------
        # Dependency chain A:
        #
        # architecture -> implementation -> integration report
        #
        # The final report is due relatively soon, so urgency must propagate
        # backward through both prerequisite levels.
        # ------------------------------------------------------------------
        _item(
            1,
            "UNDER_16_HOURS",
            due=TODAY + 7 * DAY,
            priority=2,
        ),
        _item(
            2,
            "UNDER_8_HOURS",
            due=TODAY + 7 * DAY,
            priority=2,
        ),
        _item(
            3,
            "UNDER_8_HOURS",
            due=TODAY + 7 * DAY,
            priority=2,
        ),

        # ------------------------------------------------------------------
        # Independent dependency chain B.
        # ------------------------------------------------------------------
        _item(
            4,
            "UNDER_8_HOURS",
            due=TODAY + 10 * DAY,
        ),
        _item(
            5,
            "UNDER_16_HOURS",
            due=TODAY + 10 * DAY,
        ),

        # ------------------------------------------------------------------
        # Large flexible work.
        # ------------------------------------------------------------------
        _item(
            6,
            "OVER_16_HOURS",
            due=TODAY + 14 * DAY,
            priority=3,
        ),

        # 40% of a 20h report is already complete:
        # only 12h remain to schedule.
        _item(
            7,
            "OVER_16_HOURS",
            due=TODAY + 12 * DAY,
            completed="40",
        ),

        # ------------------------------------------------------------------
        # Known future urgent releases.
        # ------------------------------------------------------------------
        _item(
            8,
            "UNDER_16_HOURS",
            release=TODAY + 3 * DAY,
            due=TODAY + 5 * DAY,
            priority=1,
        ),
        _item(
            9,
            "UNDER_8_HOURS",
            release=TODAY + 4 * DAY,
            due=TODAY + 6 * DAY,
        ),

        # ------------------------------------------------------------------
        # Known fixed-date atomic work.
        # ------------------------------------------------------------------
        _item(
            10,
            "UNDER_4_HOURS",
            anchor=TODAY + 2 * DAY,
        ),
        _item(
            11,
            "UNDER_1_HOUR",
            anchor=TODAY + 2 * DAY,
        ),
        _item(
            12,
            "UNDER_4_HOURS",
            anchor=TODAY + 6 * DAY,
        ),
        _item(
            13,
            "UNDER_1_HOUR",
            anchor=TODAY + 6 * DAY,
        ),

        # ------------------------------------------------------------------
        # Tiny real-world jobs.
        # ------------------------------------------------------------------
        _item(
            14,
            "UNDER_20_MINUTES",
            due=TODAY + DAY,
            priority=1,
        ),
        _item(
            15,
            "UNDER_1_HOUR",
            due=TODAY + 3 * DAY,
        ),
        _item(
            16,
            "UNDER_20_MINUTES",
        ),
        _item(
            17,
            "UNDER_1_HOUR",
            due=TODAY + 2 * DAY,
        ),

        # ------------------------------------------------------------------
        # Relaxed work that should lose calendar space to real urgency when
        # appropriate.
        # ------------------------------------------------------------------
        _item(
            18,
            "UNDER_8_HOURS",
            due=TODAY + 20 * DAY,
        ),

        # Large revision workload.
        _item(
            19,
            "OVER_16_HOURS",
            due=TODAY + 18 * DAY,
        ),

        # Another large task, already 50% complete.
        _item(
            20,
            "OVER_16_HOURS",
            due=TODAY + 15 * DAY,
            completed="50",
        ),

        # ------------------------------------------------------------------
        # Priority-vs-urgency conflict.
        #
        # Task 21 has low explicit priority but an immediate deadline.
        # Task 22 has high priority but far more calendar freedom.
        # ------------------------------------------------------------------
        _item(
            21,
            "UNDER_4_HOURS",
            due=TODAY + 2 * DAY,
            priority=9,
        ),
        _item(
            22,
            "UNDER_16_HOURS",
            due=TODAY + 14 * DAY,
            priority=1,
        ),
    )

    dependencies = (
        DependencyEdge(1, 2),
        DependencyEdge(2, 3),
        DependencyEdge(4, 5),
    )

    problem = ScheduleProblem(
        today=TODAY,
        items=items,
        dependencies=dependencies,
        capacity_by_duration={
            "UNDER_20_MINUTES": 10,
            "UNDER_1_HOUR": 10,
            "UNDER_4_HOURS": 10,
            "UNDER_8_HOURS": 10,
            "UNDER_16_HOURS": 10,
            "OVER_16_HOURS": 10,
        },
    )

    explicit_total_hours = {
        1: D("8"),
        2: D("6"),
        3: D("5"),
        4: D("4"),
        5: D("8"),
        6: D("24"),
        7: D("20"),
        8: D("8"),
        9: D("6"),
        10: D("2"),
        11: D("0.5"),
        12: D("3"),
        13: D("0.5"),
        14: D("0.25"),
        15: D("0.5"),

        # Laundry / quick household chore: 15 minutes.
        16: D("0.25"),

        17: D("0.5"),
        18: D("6"),
        19: D("18"),
        20: D("24"),
        21: D("3"),
        22: D("8"),
    }

    labels = {
        1: "Architecture/design draft",
        2: "Core implementation",
        3: "Integration report",
        4: "Dataset cleanup",
        5: "Analysis after dataset cleanup",
        6: "Major assignment",
        7: "Partially completed report",
        8: "Future urgent patch",
        9: "Future urgent review",
        10: "Anchored lab preparation",
        11: "Anchored submission/admin",
        12: "Anchored workshop preparation",
        13: "Anchored follow-up admin",
        14: "Tomorrow admin deadline",
        15: "Email / admin follow-up",
        16: "Laundry / quick household chore",
        17: "Book appointment",
        18: "Relaxed background reading",
        19: "Large revision block",
        20: "Already-started large coding task",
        21: "Low-priority but urgent task",
        22: "High-priority relaxed task",
    }

    return IntegratedWorld(
        problem=problem,
        explicit_total_hours=explicit_total_hours,
        labels=labels,
    )
