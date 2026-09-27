"""C11.8 deterministic production-flavour validation scenarios.

These fixtures are not tuning data.

They exist to challenge the adaptive production planner under structurally
different scheduling situations before production behaviour is frozen.
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
TODAY = date(2026, 10, 1)
DAY = timedelta(days=1)


@dataclass(frozen=True, slots=True)
class ValidationScenario:
    scenario_id: str
    description: str
    problem: ScheduleProblem
    explicit_total_hours: dict[int, Decimal]


def _item(
    item_id: int,
    duration: str,
    *,
    release: int | None = None,
    due: int | None = None,
    anchor: int | None = None,
    priority: int | None = None,
    completed: str = "0",
) -> ScheduleItem:
    completed_d = D(completed)

    return ScheduleItem(
        item_id=item_id,
        duration_category=duration,
        priority_position=priority,
        release_date=(
            None
            if release is None
            else TODAY + release * DAY
        ),
        due_date=(
            None
            if due is None
            else TODAY + due * DAY
        ),
        anchor_date=(
            None
            if anchor is None
            else TODAY + anchor * DAY
        ),
        percent_completed=completed_d,
        remaining_fraction=(
            D("1")
            - completed_d / D("100")
        ),
    )


def _problem(
    items,
    dependencies=(),
) -> ScheduleProblem:
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


def validation_scenarios() -> tuple[ValidationScenario, ...]:
    return (
        ValidationScenario(
            scenario_id="open_parallel_work",
            description=(
                "Several splittable tasks are immediately executable with "
                "comfortable deadlines."
            ),
            problem=_problem([
                _item(1, "UNDER_16_HOURS", due=12, priority=1),
                _item(2, "UNDER_16_HOURS", due=14, priority=2),
                _item(3, "UNDER_8_HOURS", due=10, priority=3),
                _item(4, "UNDER_4_HOURS", due=9),
            ]),
            explicit_total_hours={
                1: D("14"),
                2: D("12"),
                3: D("7"),
                4: D("3"),
            },
        ),

        ValidationScenario(
            scenario_id="anchor_pressure",
            description=(
                "Flexible work surrounds multiple fixed commitments."
            ),
            problem=_problem([
                _item(1, "UNDER_16_HOURS", due=10),
                _item(2, "UNDER_8_HOURS", due=8),
                _item(3, "UNDER_4_HOURS", anchor=1),
                _item(4, "UNDER_1_HOUR", anchor=3),
                _item(5, "UNDER_4_HOURS", anchor=5),
            ]),
            explicit_total_hours={
                1: D("14"),
                2: D("7"),
                3: D("4"),
                4: D("1"),
                5: D("3"),
            },
        ),

        ValidationScenario(
            scenario_id="dependency_chain",
            description=(
                "A three-stage project where downstream work cannot begin "
                "until the prerequisite is completed."
            ),
            problem=_problem(
                [
                    _item(1, "UNDER_8_HOURS", due=5),
                    _item(2, "UNDER_16_HOURS", due=11),
                    _item(3, "UNDER_8_HOURS", due=16),
                ],
                dependencies=(
                    DependencyEdge(1, 2),
                    DependencyEdge(2, 3),
                ),
            ),
            explicit_total_hours={
                1: D("7"),
                2: D("14"),
                3: D("8"),
            },
        ),

        ValidationScenario(
            scenario_id="deadline_compression",
            description=(
                "Substantial work with several close deadlines."
            ),
            problem=_problem([
                _item(1, "UNDER_16_HOURS", due=3, priority=1),
                _item(2, "UNDER_8_HOURS", due=4, priority=2),
                _item(3, "UNDER_8_HOURS", due=5, priority=3),
                _item(4, "UNDER_4_HOURS", due=2),
            ]),
            explicit_total_hours={
                1: D("12"),
                2: D("7"),
                3: D("6"),
                4: D("3"),
            },
        ),

        ValidationScenario(
            scenario_id="staggered_releases",
            description=(
                "New work becomes executable gradually across the horizon."
            ),
            problem=_problem([
                _item(1, "UNDER_8_HOURS", release=0, due=12),
                _item(2, "UNDER_16_HOURS", release=2, due=14),
                _item(3, "UNDER_8_HOURS", release=4, due=15),
                _item(4, "UNDER_4_HOURS", release=6, due=16),
            ]),
            explicit_total_hours={
                1: D("7"),
                2: D("15"),
                3: D("7"),
                4: D("4"),
            },
        ),

        ValidationScenario(
            scenario_id="partial_progress",
            description=(
                "Tasks enter scheduling already partially completed."
            ),
            problem=_problem([
                _item(
                    1,
                    "UNDER_16_HOURS",
                    due=10,
                    completed="50",
                ),
                _item(
                    2,
                    "OVER_16_HOURS",
                    due=16,
                    completed="25",
                ),
                _item(
                    3,
                    "UNDER_8_HOURS",
                    due=8,
                    completed="37.5",
                ),
            ]),
            explicit_total_hours={
                1: D("16"),
                2: D("24"),
                3: D("8"),
            },
        ),

        ValidationScenario(
            scenario_id="single_large_task",
            description=(
                "One 30-hour task tests pure session shaping and continuity."
            ),
            problem=_problem([
                _item(
                    1,
                    "OVER_16_HOURS",
                    due=14,
                ),
            ]),
            explicit_total_hours={
                1: D("30"),
            },
        ),
    )
