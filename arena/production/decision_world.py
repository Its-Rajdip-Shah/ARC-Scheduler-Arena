"""C11.15 static saturated decision-coverage world.

This stage deliberately keeps one shared calendar while forcing the production
scheduler to resolve many different classes of decisions at once.

Automated audits distinguish:

- hard/structural principles that can be checked objectively;
- behavioural trade-offs that must remain visible for human review.

The goal is not to claim that one fixture proves universal optimality. The goal
is explicit decision coverage before the later progressive grow/shrink
lifecycle certification.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from arena.production.integrated_fixture import (
    DAY,
    TODAY,
    build_c11_13_base_world,
)
from arena.scheduling.domain import (
    DependencyEdge,
    ScheduleItem,
    ScheduleProblem,
)


D = Decimal


@dataclass(frozen=True, slots=True)
class DecisionCase:
    code: str
    title: str
    principle: str
    item_ids: tuple[int, ...]
    audit_kind: str  # "hard" or "observe"


@dataclass(frozen=True, slots=True)
class SaturatedDecisionWorld:
    problem: ScheduleProblem
    explicit_total_hours: dict[int, Decimal]
    labels: dict[int, str]
    cases: tuple[DecisionCase, ...]


def _item(
    item_id: int,
    duration_category: str,
    *,
    release: date | None = None,
    due: date | None = None,
    anchor: date | None = None,
    priority: int | None = None,
    completed: str = "0",
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


def build_c11_15_saturated_world() -> SaturatedDecisionWorld:
    """Extend the C11.13 world into a decision-saturated shared calendar."""

    base = build_c11_13_base_world()

    extra_items = (
        # --------------------------------------------------------------
        # Pure priority sensitivity pair:
        # same duration, same deadline, different explicit priority.
        # --------------------------------------------------------------
        _item(
            23,
            "UNDER_8_HOURS",
            due=TODAY + 13 * DAY,
            priority=1,
        ),
        _item(
            24,
            "UNDER_8_HOURS",
            due=TODAY + 13 * DAY,
            priority=8,
        ),

        # --------------------------------------------------------------
        # Diamond dependency:
        #
        # 25 ----\
        #         -> 27 -> 28
        # 26 ----/
        # --------------------------------------------------------------
        _item(
            25,
            "UNDER_8_HOURS",
            due=TODAY + 11 * DAY,
            priority=3,
        ),
        _item(
            26,
            "UNDER_8_HOURS",
            due=TODAY + 11 * DAY,
            priority=3,
        ),
        _item(
            27,
            "UNDER_8_HOURS",
            due=TODAY + 12 * DAY,
            priority=2,
        ),
        _item(
            28,
            "UNDER_8_HOURS",
            due=TODAY + 13 * DAY,
            priority=2,
        ),

        # --------------------------------------------------------------
        # One prerequisite unlocks multiple downstream tasks.
        # --------------------------------------------------------------
        _item(
            29,
            "UNDER_8_HOURS",
            due=TODAY + 10 * DAY,
            priority=4,
        ),
        _item(
            30,
            "UNDER_8_HOURS",
            due=TODAY + 11 * DAY,
            priority=3,
        ),
        _item(
            31,
            "UNDER_8_HOURS",
            due=TODAY + 11 * DAY,
            priority=5,
        ),

        # --------------------------------------------------------------
        # Strong future anchor wall: 10h fixed work on each of two days.
        # --------------------------------------------------------------
        _item(
            32,
            "UNDER_4_HOURS",
            anchor=TODAY + 8 * DAY,
        ),
        _item(
            33,
            "UNDER_4_HOURS",
            anchor=TODAY + 8 * DAY,
        ),
        _item(
            34,
            "UNDER_4_HOURS",
            anchor=TODAY + 8 * DAY,
        ),
        _item(
            35,
            "UNDER_1_HOUR",
            anchor=TODAY + 8 * DAY,
        ),

        _item(
            36,
            "UNDER_4_HOURS",
            anchor=TODAY + 9 * DAY,
        ),
        _item(
            37,
            "UNDER_4_HOURS",
            anchor=TODAY + 9 * DAY,
        ),
        _item(
            38,
            "UNDER_4_HOURS",
            anchor=TODAY + 9 * DAY,
        ),
        _item(
            39,
            "UNDER_1_HOUR",
            anchor=TODAY + 9 * DAY,
        ),

        # Future urgent work released immediately before/inside congestion.
        _item(
            40,
            "UNDER_16_HOURS",
            release=TODAY + 7 * DAY,
            due=TODAY + 10 * DAY,
            priority=2,
        ),

        # Flexible work with no deadline at all.
        _item(
            41,
            "UNDER_16_HOURS",
        ),

        # Started high-priority task: 50% of 16h already complete.
        _item(
            42,
            "UNDER_16_HOURS",
            due=TODAY + 16 * DAY,
            priority=1,
            completed="50",
        ),

        # Newly urgent moderate-priority task.
        _item(
            43,
            "UNDER_8_HOURS",
            release=TODAY + 2 * DAY,
            due=TODAY + 4 * DAY,
            priority=5,
        ),

        # Same deadline, same work, different priority.
        _item(
            44,
            "UNDER_8_HOURS",
            due=TODAY + 12 * DAY,
            priority=2,
        ),
        _item(
            45,
            "UNDER_8_HOURS",
            due=TODAY + 12 * DAY,
            priority=7,
        ),

        # --------------------------------------------------------------
        # Deliberately impossible same-day workload.
        #
        # There is no hard daily ceiling in ARC production scheduling.
        # This work is due today, so the scheduler should schedule it today
        # and expose the resulting >24h day as INFEASIBLE rather than silently
        # making the work late.
        # --------------------------------------------------------------
        _item(
            46,
            "OVER_16_HOURS",
            due=TODAY,
            priority=1,
        ),
    )

    extra_dependencies = (
        DependencyEdge(25, 27),
        DependencyEdge(26, 27),
        DependencyEdge(27, 28),
        DependencyEdge(29, 30),
        DependencyEdge(29, 31),
    )

    problem = ScheduleProblem(
        today=base.problem.today,
        items=(
            base.problem.items
            + extra_items
        ),
        dependencies=(
            base.problem.dependencies
            + extra_dependencies
        ),
        capacity_by_duration=
            base.problem.capacity_by_duration,
        overload_dates=
            base.problem.overload_dates,
    )

    explicit_total_hours = dict(
        base.explicit_total_hours
    )

    explicit_total_hours.update({
        23: D("4"),
        24: D("4"),
        25: D("4"),
        26: D("4"),
        27: D("6"),
        28: D("4"),
        29: D("5"),
        30: D("4"),
        31: D("4"),

        # 10h fixed work on each anchor-wall day.
        32: D("3"),
        33: D("3"),
        34: D("3"),
        35: D("1"),
        36: D("3"),
        37: D("3"),
        38: D("3"),
        39: D("1"),

        40: D("8"),
        41: D("8"),

        # 16h total, 50% complete -> 8h remaining.
        42: D("16"),

        43: D("5"),
        44: D("4"),
        45: D("4"),

        # Intentional >24h due-today infeasibility.
        46: D("25"),
    })

    labels = dict(
        base.labels
    )

    labels.update({
        23: "High-priority flexible peer",
        24: "Low-priority flexible peer",
        25: "Diamond prerequisite A",
        26: "Diamond prerequisite B",
        27: "Diamond join task",
        28: "Post-diamond dependent",
        29: "Shared prerequisite",
        30: "Shared-root dependent A",
        31: "Shared-root dependent B",
        32: "Anchor-wall work A1",
        33: "Anchor-wall work A2",
        34: "Anchor-wall work A3",
        35: "Anchor-wall admin A4",
        36: "Anchor-wall work B1",
        37: "Anchor-wall work B2",
        38: "Anchor-wall work B3",
        39: "Anchor-wall admin B4",
        40: "Urgent release into anchor congestion",
        41: "No-deadline flexible backlog",
        42: "Started high-priority flexible task",
        43: "Newly urgent moderate-priority task",
        44: "Same-deadline higher-priority task",
        45: "Same-deadline lower-priority task",
        46: "Impossible 25h due-today workload",
    })

    cases = (
        DecisionCase(
            "D01",
            "Urgency outranks relaxed priority",
            (
                "A low-priority near-deadline task must remain deadline-safe "
                "even when a higher-priority task has much more slack."
            ),
            (21, 22),
            "observe",
        ),
        DecisionCase(
            "D02",
            "Pure priority sensitivity",
            (
                "With comparable feasibility and deadlines, higher explicit "
                "priority should receive no worse start treatment."
            ),
            (23, 24),
            "hard",
        ),
        DecisionCase(
            "D03",
            "Multi-hop dependency urgency",
            (
                "The complete 1 -> 2 -> 3 chain must preserve completion-based "
                "precedence while inheriting downstream urgency."
            ),
            (1, 2, 3),
            "hard",
        ),
        DecisionCase(
            "D04",
            "Diamond dependency",
            (
                "Both prerequisites must complete before the join task, and "
                "the join must complete before its dependent."
            ),
            (25, 26, 27, 28),
            "hard",
        ),
        DecisionCase(
            "D05",
            "One prerequisite unlocks multiple tasks",
            (
                "Shared prerequisite 29 must complete before either downstream "
                "task starts."
            ),
            (29, 30, 31),
            "hard",
        ),
        DecisionCase(
            "D06",
            "Future anchor wall",
            (
                "The scheduler must account for two known 10h fixed-work days "
                "rather than treating them as ordinary future capacity."
            ),
            (32, 33, 34, 35, 36, 37, 38, 39),
            "hard",
        ),
        DecisionCase(
            "D07",
            "Urgent future release into congestion",
            (
                "Task 40 cannot execute before release and must compete "
                "sensibly with the known future anchor wall."
            ),
            (40,),
            "hard",
        ),
        DecisionCase(
            "D08",
            "Started work vs newly urgent work",
            (
                "Continuity/priority of started task 42 must not prevent newly "
                "urgent task 43 from receiving deadline-safe treatment."
            ),
            (42, 43),
            "observe",
        ),
        DecisionCase(
            "D09",
            "Partial progress conservation",
            (
                "Only remaining work may be scheduled for partially completed "
                "tasks."
            ),
            (7, 20, 42),
            "hard",
        ),
        DecisionCase(
            "D10",
            "No-deadline flexible backlog",
            (
                "No-deadline work should remain schedulable but lose calendar "
                "pressure to tasks with genuine constraints when appropriate."
            ),
            (41,),
            "observe",
        ),
        DecisionCase(
            "D11",
            "Same-deadline priority sensitivity",
            (
                "With equal deadline pressure, the higher-priority peer should "
                "not receive systematically worse treatment."
            ),
            (44, 45),
            "hard",
        ),
        DecisionCase(
            "D12",
            "Impossible workload semantics",
            (
                "A genuinely impossible 25h due-today workload must not be "
                "pushed late merely to protect comfort; the day should expose "
                "INFEASIBLE status."
            ),
            (46,),
            "hard",
        ),
        DecisionCase(
            "D13",
            "Future congestion lookahead",
            (
                "Flexible large work must be shaped with awareness of the "
                "future anchor wall and urgent release."
            ),
            (6, 19, 32, 36, 40),
            "observe",
        ),
        DecisionCase(
            "D14",
            "Session-shape quality under pressure",
            (
                "Large focused tasks should remain human-sized without "
                "reintroducing non-final token fragments."
            ),
            (6, 7, 19),
            "observe",
        ),
        DecisionCase(
            "D15",
            "Release collision",
            (
                "Future urgent releases must displace flexible work without "
                "violating release dates."
            ),
            (8, 9, 40),
            "observe",
        ),
        DecisionCase(
            "D16",
            "Atomic work around focused work",
            (
                "Tiny/atomic jobs must remain single allocations and coexist "
                "without being inflated into fake focus sessions."
            ),
            (14, 16, 17, 35, 39),
            "hard",
        ),
        DecisionCase(
            "D17",
            "Deadline buffer vs long Lock-in focus",
            (
                "Lock-in may accept longer focused blocks when they purchase "
                "meaningful deadline buffer; Monk should normally remain calmer."
            ),
            (19,),
            "observe",
        ),
        DecisionCase(
            "D18",
            "Flavour distinction under the same world",
            (
                "Lock-in and Monk must remain behaviourally distinct while "
                "respecting the same hard canonical constraints."
            ),
            (),
            "observe",
        ),
    )

    return SaturatedDecisionWorld(
        problem=problem,
        explicit_total_hours=
            explicit_total_hours,
        labels=labels,
        cases=cases,
    )
