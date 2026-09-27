"""First adaptive C11 production flavour planner.

This planner is intentionally separate from the frozen C1-C10 research engine.

The planner works in estimated HOURS. Percentage allocations are derived only
after the planner has decided how much work belongs on each day.

Lock-in and Monk share:
- canonical releases;
- anchors;
- completion-based dependencies;
- exact work conservation;
- task continuity preference;
- independent ARC validation.

They differ only in human scheduling policy.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from arena.production.flavours import ProductionFlavour
from arena.production.load_status import (
    LoadStatus,
    classify_day,
    monthly_statuses,
    weekly_statuses,
)
from arena.production.work_mass import (
    DayHeadroom,
    WorkAllocation,
    WorkEstimate,
    allocate_work_mass,
    remaining_work_hours,
    validate_dynamic_plan,
    work_allocations_to_plan,
)
from arena.scheduling.domain import (
    ScheduleItem,
    SchedulePlan,
    ScheduleProblem,
)
from arena.scheduling.mechanics import effective_bucket


D = Decimal


# These are fallback work-estimate priors, not fixed session sizes.
#
# Production data can override them with an explicit per-task estimate.
#
# The bounded categories use their stated upper bound because that preserves
# a simple physical interpretation:
#
#   hours assigned / estimated total hours = allocation %
#
# OVER_16_HOURS has no upper bound, so its fallback is deliberately marked
# as a prior and must not be treated as canonical truth.
DURATION_HOUR_PRIORS = {
    "UNDER_20_MINUTES": D("0.33"),
    "UNDER_1_HOUR": D("1"),
    "UNDER_4_HOURS": D("4"),
    "UNDER_8_HOURS": D("8"),
    "UNDER_16_HOURS": D("16"),
    "OVER_16_HOURS": D("24"),
}


ATOMIC_BUCKETS = frozenset({
    "UNDER_20_MINUTES",
    "UNDER_1_HOUR",
    "UNDER_4_HOURS",
})


@dataclass(frozen=True, slots=True)
class FlavourPolicy:
    flavour: ProductionFlavour

    # Desired total work on an ordinary day.
    preferred_daily_hours: Decimal

    # A soft ceiling. Deadline/anchor pressure may exceed it, but normal
    # scheduling should remain below it.
    soft_max_daily_hours: Decimal

    # The share of an ordinary day's target that one splittable item may
    # consume while other ready tasks are available.
    focused_task_share: Decimal

    # Small sessions are undesirable unless they finish an item.
    minimum_useful_session_hours: Decimal

    # Maximum ordinary amount of one flexible task on one day.
    # This is hour-based, not a fixed percentage/session rule.
    maximum_focused_session_hours: Decimal

    # Once substantial work has started, favour a meaningful
    # continuation session whenever daily headroom permits.
    continuation_target_share: Decimal

    # How strongly a started task should remain at the front of the queue.
    continuation_bonus: int


LOCK_IN_POLICY = FlavourPolicy(
    flavour=ProductionFlavour.LOCK_IN,
    preferred_daily_hours=D("8"),
    soft_max_daily_hours=D("10"),
    focused_task_share=D("0.65"),
    minimum_useful_session_hours=D("1"),
    maximum_focused_session_hours=D("6"),
    continuation_target_share=D("0.60"),
    continuation_bonus=1000,
)


MONK_POLICY = FlavourPolicy(
    flavour=ProductionFlavour.MONK,
    preferred_daily_hours=D("6"),
    soft_max_daily_hours=D("8"),
    focused_task_share=D("0.50"),
    minimum_useful_session_hours=D("1"),
    maximum_focused_session_hours=D("5"),
    continuation_target_share=D("0.50"),
    continuation_bonus=1000,
)


@dataclass(frozen=True, slots=True)
class PlannedSchedule:
    flavour: ProductionFlavour
    plan: SchedulePlan
    work_allocations: tuple[WorkAllocation, ...]
    estimates: dict[int, WorkEstimate]
    daily_hours: dict[date, Decimal]
    daily_status: dict[date, LoadStatus]
    weekly_status: dict[str, object]
    monthly_status: dict[str, object]


def fallback_estimate(
    item: ScheduleItem,
) -> WorkEstimate:
    bucket = effective_bucket(item)

    try:
        hours = DURATION_HOUR_PRIORS[
            bucket
        ]
    except KeyError as exc:
        raise ValueError(
            f"No duration-hour prior for {bucket!r}"
        ) from exc

    return WorkEstimate(
        item_id=item.item_id,
        total_hours=hours,
        source=(
            "duration_category_upper_bound"
            if bucket != "OVER_16_HOURS"
            else "duration_category_prior_over_16h"
        ),
    )


def build_estimates(
    problem: ScheduleProblem,
    *,
    explicit_total_hours: dict[
        int,
        Decimal,
    ] | None = None,
) -> dict[int, WorkEstimate]:
    explicit_total_hours = (
        explicit_total_hours or {}
    )

    result = {}

    for item in problem.items:
        if item.item_id in explicit_total_hours:
            result[item.item_id] = (
                WorkEstimate(
                    item_id=item.item_id,
                    total_hours=
                        explicit_total_hours[
                            item.item_id
                        ],
                    source="explicit_task_estimate",
                )
            )
        else:
            result[item.item_id] = (
                fallback_estimate(item)
            )

    return result


def _policy(
    flavour: ProductionFlavour | str,
) -> FlavourPolicy:
    flavour = ProductionFlavour(
        flavour
    )

    if flavour is ProductionFlavour.LOCK_IN:
        return LOCK_IN_POLICY

    if flavour is ProductionFlavour.MONK:
        return MONK_POLICY

    raise ValueError(
        flavour
    )


def _days_to_due(
    item: ScheduleItem,
    day: date,
) -> int:
    if item.due_date is None:
        return 10_000

    return (
        item.due_date - day
    ).days


def _priority_value(
    item: ScheduleItem,
) -> int:
    if item.priority_position is None:
        return 10_000

    return item.priority_position


def _dependency_unlock_count(
    problem: ScheduleProblem,
    item_id: int,
) -> int:
    return len(
        problem.direct_dependents(
            item_id
        )
    )


def _ready(
    *,
    problem: ScheduleProblem,
    item: ScheduleItem,
    day: date,
    remaining: dict[int, Decimal],
    completed_on: dict[int, date],
    started_on: dict[int, date],
) -> bool:
    if remaining[item.item_id] <= 0:
        return False

    if (
        item.release_date is not None
        and day < item.release_date
    ):
        return False

    if (
        item.anchor_date is not None
        and item.item_id not in started_on
    ):
        return day == item.anchor_date

    for prerequisite_id in (
        problem.direct_prerequisites(
            item.item_id
        )
    ):
        completion = completed_on.get(
            prerequisite_id
        )

        if (
            completion is None
            or completion >= day
        ):
            return False

    return True


def _minimum_sessions_needed(
    *,
    item: ScheduleItem,
    remaining_hours: Decimal,
    policy: FlavourPolicy,
) -> int:
    """Minimum number of sane work sessions still needed.

    This is a feasibility estimate, not a fixed session-count policy.

    Atomic items require one whole session. Splittable work uses the flavour's
    maximum ordinary focused-session size to estimate how many future work
    opportunities are needed.
    """

    if remaining_hours <= 0:
        return 0

    if effective_bucket(item) in ATOMIC_BUCKETS:
        return 1

    session = policy.maximum_focused_session_hours

    quotient = (
        remaining_hours
        / session
    )

    whole = int(quotient)

    if D(whole) * session < remaining_hours:
        whole += 1

    return max(1, whole)


def _effective_due_dates(
    *,
    problem: ScheduleProblem,
    remaining: dict[int, Decimal],
    policy: FlavourPolicy,
) -> dict[int, date | None]:
    """Planner-only effective deadlines with downstream urgency propagation.

    Canonical due dates are never changed.

    If A -> B and B needs k sensible work days before B's effective deadline,
    A must finish before those k downstream work days can begin.

    Anchored dependents also propagate urgency backward because their
    prerequisite must already be complete before the anchor date.
    """

    result = {
        item.item_id:
            item.due_date
        for item in problem.items
    }

    item_by_id = (
        problem.item_by_id
    )

    for item_id in reversed(
        problem.topological_order()
    ):
        effective = result[
            item_id
        ]

        for dependent_id in sorted(
            problem.direct_dependents(
                item_id
            )
        ):
            dependent = (
                item_by_id[
                    dependent_id
                ]
            )

            downstream_due = (
                result[
                    dependent_id
                ]
            )

            candidates = []

            if downstream_due is not None:
                sessions = (
                    _minimum_sessions_needed(
                        item=dependent,
                        remaining_hours=
                            remaining[
                                dependent_id
                            ],
                        policy=policy,
                    )
                )

                candidates.append(
                    downstream_due
                    - timedelta(
                        days=sessions
                    )
                )

            if (
                dependent.anchor_date
                is not None
            ):
                candidates.append(
                    dependent.anchor_date
                    - timedelta(days=1)
                )

            for candidate in candidates:
                if (
                    effective is None
                    or candidate
                    < effective
                ):
                    effective = (
                        candidate
                    )

        result[
            item_id
        ] = effective

    return result


def _deadline_pressure_tier(
    *,
    item: ScheduleItem,
    remaining_hours: Decimal,
    day: date,
    effective_due_date:
        date | None,
    policy: FlavourPolicy,
) -> int:
    """Classify deadline feasibility before continuity preference."""

    if effective_due_date is None:
        return 3

    usable_days = max(
        1,
        (
            effective_due_date
            - day
        ).days + 1,
    )

    sessions_needed = (
        _minimum_sessions_needed(
            item=item,
            remaining_hours=
                remaining_hours,
            policy=policy,
        )
    )

    slack = (
        usable_days
        - sessions_needed
    )

    if slack <= 0:
        return 0

    if slack == 1:
        return 1

    if slack <= 3:
        return 2

    return 3


def _sort_key(
    *,
    problem: ScheduleProblem,
    item: ScheduleItem,
    day: date,
    remaining_hours: Decimal,
    effective_due_date:
        date | None,
    started_on: dict[int, date],
    policy: FlavourPolicy,
) -> tuple:
    started = (
        item.item_id
        in started_on
    )

    # Anchors remain first because they are hard first-date semantics.
    anchor_rank = (
        0
        if (
            not started
            and item.anchor_date == day
        )
        else 1
    )

    pressure_rank = (
        _deadline_pressure_tier(
            item=item,
            remaining_hours=
                remaining_hours,
            day=day,
            effective_due_date=
                effective_due_date,
            policy=policy,
        )
    )

    # Continuity is deliberately below deadline-feasibility pressure.
    continuation_rank = (
        -policy.continuation_bonus
        if started
        else 0
    )

    due = (
        10_000
        if effective_due_date is None
        else (
            effective_due_date
            - day
        ).days
    )

    priority = _priority_value(
        item
    )

    unlock = -_dependency_unlock_count(
        problem,
        item.item_id,
    )

    return (
        anchor_rank,
        pressure_rank,
        continuation_rank,
        due,
        priority,
        unlock,
        item.item_id,
    )


def _remaining_usable_days(
    item: ScheduleItem,
    day: date,
) -> int:
    if item.due_date is None:
        return 999

    return max(
        1,
        (
            item.due_date - day
        ).days + 1,
    )


def _required_today_hours(
    *,
    item: ScheduleItem,
    remaining_hours: Decimal,
    day: date,
) -> Decimal:
    """Simple deadline-pressure lower bound.

    If 12h remain and only 3 usable calendar days remain before the deadline,
    an average of 4h/day is required.

    This does not force equal allocations. It only prevents a flavour from
    smoothing so aggressively that a deadline becomes obviously impossible.
    """

    days = _remaining_usable_days(
        item,
        day,
    )

    if days >= 999:
        return D("0")

    return (
        remaining_hours
        / D(days)
    )


def _session_hours(
    *,
    item: ScheduleItem,
    remaining_hours: Decimal,
    day: date,
    current_day_load: Decimal,
    ready_count: int,
    policy: FlavourPolicy,
    already_started: bool = False,
) -> Decimal:
    bucket = effective_bucket(
        item
    )

    ordinary_headroom = max(
        D("0"),
        (
            policy.preferred_daily_hours
            - current_day_load
        ),
    )

    max_headroom = max(
        D("0"),
        (
            policy.soft_max_daily_hours
            - current_day_load
        ),
    )

    required = _required_today_hours(
        item=item,
        remaining_hours=
            remaining_hours,
        day=day,
    )

    if bucket in ATOMIC_BUCKETS:
        # Atomic items stay whole.
        #
        # The flavour soft maximum is not a hard scheduling ceiling. If the
        # atomic task is due now, schedule it even when that overloads the day.
        if (
            item.due_date is not None
            and item.due_date <= day
        ):
            return remaining_hours

        if (
            remaining_hours
            <= ordinary_headroom
        ):
            return remaining_hours

        if (
            remaining_hours
            <= max_headroom
        ):
            return remaining_hours

        return D("0")

    if max_headroom <= 0:
        return D("0")

    if ready_count <= 1:
        ordinary_candidate = min(
            ordinary_headroom,
            policy.maximum_focused_session_hours,
        )
    else:
        ordinary_candidate = (
            policy.preferred_daily_hours
            * policy.focused_task_share
        )

        ordinary_candidate = min(
            ordinary_candidate,
            ordinary_headroom,
            policy.maximum_focused_session_hours,
        )

    # A started task should make meaningful progress while room exists,
    # rather than receiving repeated token sessions.
    if already_started:
        continuation_target = (
            policy.preferred_daily_hours
            * policy.continuation_target_share
        )

        continuation_target = min(
            continuation_target,
            ordinary_headroom,
            policy.maximum_focused_session_hours,
            remaining_hours,
        )

        ordinary_candidate = max(
            ordinary_candidate,
            continuation_target,
        )

    # preferred_daily_hours and soft_max_daily_hours describe normal human
    # workload bands; they are not hard ceilings.
    #
    # Ordinary discretionary work stays inside normal headroom. Deadline
    # feasibility may require exceeding it. In that case the work is still
    # scheduled and the resulting day is classified overloaded/infeasible.
    candidate = max(
        ordinary_candidate,
        required,
    )

    candidate = min(
        candidate,
        remaining_hours,
    )

    if candidate <= 0:
        return D("0")

    # Avoid manufacturing a tiny final tail. If the proposed session would
    # leave less than one useful session and today's soft-max headroom can
    # absorb that remainder, finish the item now.
    tail = (
        remaining_hours
        - candidate
    )

    if (
        tail > 0
        and tail
        < policy.minimum_useful_session_hours
    ):
        # If deadline pressure already requires an overloaded day, absorbing
        # a tiny tail is preferable to manufacturing a token cleanup session.
        if candidate > max_headroom:
            absorbed = tail
        else:
            absorbable = max(
                D("0"),
                max_headroom
                - candidate,
            )

            absorbed = min(
                tail,
                absorbable,
            )

        candidate += absorbed
        tail -= absorbed

    # A tiny non-final fragment is still undesirable.
    if (
        candidate
        < policy.minimum_useful_session_hours
        and candidate
        < remaining_hours
    ):
        return D("0")

    return candidate


def _force_anchor_if_needed(
    *,
    item: ScheduleItem,
    remaining_hours: Decimal,
    day: date,
    current_day_load: Decimal,
    policy: FlavourPolicy,
) -> Decimal:
    """Anchors are hard first-date semantics.

    If an atomic anchored item exceeds the preferred day target, scheduling it
    is still necessary. For splittable anchored work, at least one useful
    session starts on the anchor date.
    """

    if item.anchor_date != day:
        return D("0")

    bucket = effective_bucket(
        item
    )

    if bucket in ATOMIC_BUCKETS:
        return remaining_hours

    normal = _session_hours(
        item=item,
        remaining_hours=
            remaining_hours,
        day=day,
        current_day_load=
            current_day_load,
        ready_count=1,
        policy=policy,
    )

    if normal > 0:
        return normal

    return min(
        remaining_hours,
        max(
            policy.minimum_useful_session_hours,
            D("0.25"),
        ),
    )


def generate_flavour_schedule(
    problem: ScheduleProblem,
    flavour: ProductionFlavour | str,
    *,
    explicit_total_hours: dict[
        int,
        Decimal,
    ] | None = None,
) -> PlannedSchedule:
    """Generate one deterministic adaptive production schedule."""

    policy = _policy(
        flavour
    )

    estimates = build_estimates(
        problem,
        explicit_total_hours=
            explicit_total_hours,
    )

    remaining = {
        item.item_id:
            remaining_work_hours(
                item,
                estimates[
                    item.item_id
                ],
            )
        for item in problem.items
    }

    started_on: dict[
        int,
        date,
    ] = {}

    completed_on: dict[
        int,
        date,
    ] = {}

    # Planner decision output before conversion to percentages:
    #
    # item_id -> date -> assigned hours
    assigned: dict[
        int,
        dict[date, Decimal],
    ] = defaultdict(
        lambda: defaultdict(
            lambda: D("0")
        )
    )

    daily_hours: dict[
        date,
        Decimal,
    ] = defaultdict(
        lambda: D("0")
    )

    day = problem.today

    latest_known_date = max(
        [
            problem.today,
            *[
                candidate
                for item in problem.items
                for candidate in (
                    item.release_date,
                    item.due_date,
                    item.anchor_date,
                )
                if candidate is not None
            ],
        ]
    )

    # Safety horizon only prevents infinite loops caused by a planner bug.
    # It is not a scheduling preference.
    hard_stop = (
        latest_known_date
        + timedelta(days=90)
    )

    item_by_id = problem.item_by_id

    while any(
        hours > 0
        for hours in remaining.values()
    ):
        if day > hard_stop:
            pending = {
                item_id: str(hours)
                for item_id, hours
                in remaining.items()
                if hours > 0
            }

            raise RuntimeError(
                "Adaptive planner exceeded "
                f"safety horizon: {pending}"
            )

        # A single calendar day may receive several different tasks, but one
        # item receives at most one production allocation on that day.
        placed_today: set[int] = set()

        while True:
            effective_due_dates = (
                _effective_due_dates(
                    problem=problem,
                    remaining=remaining,
                    policy=policy,
                )
            )

            ready_items = [
                item
                for item in problem.items
                if (
                    item.item_id
                    not in placed_today
                    and _ready(
                        problem=problem,
                        item=item,
                        day=day,
                        remaining=remaining,
                        completed_on=
                            completed_on,
                        started_on=
                            started_on,
                    )
                )
            ]

            if not ready_items:
                break

            ready_items.sort(
                key=lambda item:
                    _sort_key(
                        problem=problem,
                        item=item,
                        day=day,
                        remaining_hours=
                            remaining[
                                item.item_id
                            ],
                        effective_due_date=
                            effective_due_dates[
                                item.item_id
                            ],
                        started_on=
                            started_on,
                        policy=policy,
                    )
            )

            chosen = None
            chosen_hours = D("0")

            # Try candidates in dynamic priority order. An atomic item that
            # cannot fit today should not block another task that can.
            for item in ready_items:
                hours = _session_hours(
                    item=item,
                    remaining_hours=
                        remaining[
                            item.item_id
                        ],
                    day=day,
                    current_day_load=
                        daily_hours[day],
                    ready_count=
                        len(ready_items),
                    policy=policy,
                    already_started=(
                        item.item_id
                        in started_on
                    ),
                )

                if (
                    hours <= 0
                    and item.anchor_date
                    == day
                    and item.item_id
                    not in started_on
                ):
                    hours = (
                        _force_anchor_if_needed(
                            item=item,
                            remaining_hours=
                                remaining[
                                    item.item_id
                                ],
                            day=day,
                            current_day_load=
                                daily_hours[
                                    day
                                ],
                            policy=policy,
                        )
                    )

                if hours > 0:
                    chosen = item
                    chosen_hours = hours
                    break

            if chosen is None:
                break

            item_id = (
                chosen.item_id
            )

            assigned[
                item_id
            ][day] += chosen_hours

            daily_hours[
                day
            ] += chosen_hours

            remaining[
                item_id
            ] -= chosen_hours

            if (
                item_id
                not in started_on
            ):
                started_on[
                    item_id
                ] = day

            placed_today.add(
                item_id
            )

            if (
                remaining[
                    item_id
                ]
                <= D("0")
            ):
                remaining[
                    item_id
                ] = D("0")

                completed_on[
                    item_id
                ] = day

        day += timedelta(
            days=1
        )

    work_allocations: list[
        WorkAllocation
    ] = []

    for item_id in sorted(
        assigned
    ):
        item = item_by_id[
            item_id
        ]

        estimate = estimates[
            item_id
        ]

        headroom = tuple(
            DayHeadroom(
                scheduled_date=day,
                hours=hours,
            )
            for day, hours
            in sorted(
                assigned[
                    item_id
                ].items()
            )
        )

        dynamic_rows = (
            allocate_work_mass(
                item,
                estimate,
                headroom,
            )
        )

        work_allocations.extend(
            dynamic_rows
        )

    plan = (
        work_allocations_to_plan(
            tuple(
                work_allocations
            )
        )
    )

    validation = (
        validate_dynamic_plan(
            problem,
            plan,
        )
    )

    if validation.violations:
        raise AssertionError(
            "Adaptive production planner "
            "created hard-invalid plan: "
            f"{validation.violations}"
        )

    if validation.infeasibilities:
        raise AssertionError(
            "C11.5 fixture unexpectedly "
            "contains hard infeasibility: "
            f"{validation.infeasibilities}"
        )

    if work_allocations:
        final_active_date = max(
            row.scheduled_date
            for row in work_allocations
        )
    else:
        final_active_date = (
            problem.today
        )

    final_daily_hours = {}

    cursor = problem.today

    while cursor <= final_active_date:
        final_daily_hours[
            cursor
        ] = daily_hours.get(
            cursor,
            D("0"),
        )

        cursor += timedelta(
            days=1
        )

    final_daily_status = {
        scheduled_date: classify_day(
            hours,
            preferred_daily_hours=
                policy.preferred_daily_hours,
            soft_max_daily_hours=
                policy.soft_max_daily_hours,
        )
        for scheduled_date, hours
        in final_daily_hours.items()
    }

    return PlannedSchedule(
        flavour=policy.flavour,
        plan=plan,
        work_allocations=tuple(
            sorted(
                work_allocations,
                key=lambda row: (
                    row.scheduled_date,
                    row.item_id,
                ),
            )
        ),
        estimates=estimates,
        daily_hours=final_daily_hours,
        daily_status=final_daily_status,
        weekly_status=weekly_statuses(
            final_daily_hours,
            preferred_daily_hours=
                policy.preferred_daily_hours,
            soft_max_daily_hours=
                policy.soft_max_daily_hours,
        ),
        monthly_status=monthly_statuses(
            final_daily_hours,
            preferred_daily_hours=
                policy.preferred_daily_hours,
            soft_max_daily_hours=
                policy.soft_max_daily_hours,
        ),
    )
