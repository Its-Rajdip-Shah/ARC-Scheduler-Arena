"""C11 dynamic production-plan improvement.

This ports the proven C4 search architecture to C11's dynamic work-mass
representation.

What is reused from the research programme:
- constructor/improver separation;
- deterministic neighbourhood enumeration;
- strict improvement only;
- best-improvement scans;
- explicit evaluation/iteration budgets;
- independent validation of every candidate;
- objective/search separated from canonical state.

What is deliberately NOT reused:
- legacy fixed session_index identities;
- equal session pieces;
- C1-C10 SearchState representation.

Production moves operate in estimated work-hours.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from arena.production.flavour_planner import (
    ATOMIC_BUCKETS,
    PlannedSchedule,
    _policy,
)
from arena.production.load_status import (
    classify_day,
    monthly_statuses,
    weekly_statuses,
)
from arena.production.work_mass import (
    DayHeadroom,
    WorkAllocation,
    allocate_work_mass,
    validate_dynamic_plan,
    work_allocations_to_plan,
)
from arena.scheduling.domain import (
    ScheduleProblem,
)
from arena.scheduling.mechanics import effective_bucket


D = Decimal


@dataclass(frozen=True, slots=True)
class ProductionObjective:
    """Lexicographic production objective.

    Earlier components are strictly more important.

    Deadline lateness deliberately outranks comfort. This matches ARC's
    semantics: if unavoidable work must overload a day to meet a deadline,
    schedule it and report the overload rather than manufacturing lateness.
    """

    late_hours: Decimal

    infeasible_day_count: int
    infeasible_excess_hours: Decimal

    overloaded_day_count: int
    overloaded_excess_hours: Decimal

    tiny_nonfinal_sessions: int

    # Human work-shape diagnostics for splittable tasks.
    #
    # session_shape_penalty measures how far allocations are from useful
    # focused-work blocks. fragmentation_count measures repeated task touches.
    # priority_postponement_days keeps explicit user priority meaningful after
    # the constructor, rather than allowing the improver to erase it.
    session_shape_penalty: Decimal
    fragmentation_count: int
    priority_postponement_days: Decimal

    continuity_gap_days: int

    max_daily_hours: Decimal
    preferred_excess_squared: Decimal

    avoidable_idle_days: int
    deadline_buffer_risk: Decimal
    completion_day_sum: int

    # C11.15.8:
    #
    # Severe focused marathons are treated separately from ordinary session
    # aesthetics. This metric is non-zero only when a splittable session is
    # materially beyond the flavour's ordinary focused-session range AND the
    # task lacks meaningful effective deadline buffer.
    #
    # Kept as a defaulted trailing field so historical unit tests that build
    # ProductionObjective directly remain source-compatible.
    unjustified_marathon_excess_hours: Decimal = D("0")

    @property
    def key(self) -> tuple:
        # Human-facing severity is minimised before the number of bad days.
        #
        # Otherwise search can "improve" a schedule by combining several
        # moderate overloads into one absurdly heavy day. That is formally
        # fewer overloaded dates but clearly worse for a human.
        #
        # Deadline correctness still dominates comfort: unavoidable overload
        # is preferable to manufacturing avoidable lateness.
        return (
            self.late_hours,

            self.infeasible_day_count,
            self.infeasible_excess_hours,

            # A non-final sub-hour focused-work fragment is a near-hard
            # human-shape defect. It may be introduced only to improve actual
            # deadline lateness or physical infeasibility, which appear above
            # it in this key. Ordinary load smoothing, idle reduction,
            # priority, or continuity may not manufacture token work sessions.
            self.tiny_nonfinal_sessions,

            # Lock-in must not manufacture avoidable early idle merely to
            # obtain prettier downstream load distribution.
            self.avoidable_idle_days,

            # Human load severity outranks deadline-buffer niceness.
            #
            # Deadline buffer is valuable, but ARC must not buy an extra
            # buffer day by turning a reasonable 10h workload into a 15h/20h
            # overload. Actual lateness still remains dominant above both.
            self.max_daily_hours,
            self.overloaded_excess_hours,
            self.overloaded_day_count,

            # C11.15.8 severe-marathon semantics.
            #
            # Ordinary session aesthetics still remain below deadline-buffer
            # preference. But a genuinely oversized focused block with no
            # meaningful effective deadline buffer has no behavioural
            # justification and is therefore repaired before buying marginal
            # additional buffer.
            self.unjustified_marathon_excess_hours,

            self.deadline_buffer_risk,

            # Explicit priority must survive constructor -> improver. It stays
            # below deadlines, infeasibility and serious workload severity, so
            # priority cannot make ARC do something physically stupid.
            self.priority_postponement_days,

            # Human session quality now outranks the crude continuity metric.
            # A few meaningful blocks should beat daily token touches.
            self.session_shape_penalty,
            self.fragmentation_count,

            self.preferred_excess_squared,

            self.continuity_gap_days,
            self.completion_day_sum,
        )


@dataclass(frozen=True, slots=True)
class WorkHourMove:
    item_id: int
    from_date: date
    to_date: date
    hours: Decimal


@dataclass(frozen=True, slots=True)
class CompoundWorkHourMove:
    """Two coordinated relocations evaluated atomically.

    This is the production analogue of the small destroy/repair insight from
    the frozen research pipeline: some useful changes cannot be reached by
    strict single-move hill climbing because the first half alone is neutral
    or worse.
    """

    first: WorkHourMove
    second: WorkHourMove


@dataclass(frozen=True, slots=True)
class ProductionImproveConfig:
    max_iterations: int = 40
    max_evaluations: int = 4000

    def __post_init__(self) -> None:
        if (
            type(self.max_iterations) is not int
            or self.max_iterations < 0
        ):
            raise ValueError(
                "max_iterations must be a nonnegative exact int"
            )

        if (
            type(self.max_evaluations) is not int
            or self.max_evaluations < 0
        ):
            raise ValueError(
                "max_evaluations must be a nonnegative exact int"
            )


@dataclass(frozen=True, slots=True)
class ProductionImproveResult:
    initial_schedule: PlannedSchedule
    final_schedule: PlannedSchedule

    initial_objective: ProductionObjective
    final_objective: ProductionObjective

    iterations: int
    evaluations: int
    accepted_moves: tuple[
        WorkHourMove
        | CompoundWorkHourMove
        | str,
        ...,
    ]
    objective_history: tuple[tuple, ...]
    termination_reason: str

    @property
    def improved(self) -> bool:
        return (
            self.final_objective.key
            < self.initial_objective.key
        )


def _session_shape_penalty(
    hours: Decimal,
) -> Decimal:
    """Human-quality penalty for one splittable work allocation.

    This is deliberately a soft curve rather than a fixed session size.

    Approximate interpretation:

        <1h       strongly undesirable
        1-1.5h    mildly undesirable
        1.5-2h    acceptable
        2-4h      sweet spot
        4-5h      good / mild penalty
        5-6h      acceptable / larger penalty
        >6h       increasingly undesirable

    Atomic/admin items never use this function.
    """

    if hours <= 0:
        return D("0")

    if hours < D("1"):
        # 0.5h -> 6; approaching zero becomes increasingly bad.
        shortfall = D("1") - hours
        return D("4") + D("4") * shortfall

    if hours < D("1.5"):
        return D("2") * (D("1.5") - hours)

    if hours < D("2"):
        return D("0.5") * (D("2") - hours)

    if hours <= D("4"):
        return D("0")

    if hours <= D("5"):
        return D("0.5") * (hours - D("4"))

    if hours <= D("6"):
        return (
            D("0.5")
            + D("1.5") * (hours - D("5"))
        )

    excess = hours - D("6")

    return (
        D("2")
        + excess
        + excess * excess
    )


def _priority_weight(
    priority_position: int | None,
) -> Decimal:
    """Convert priority position to an explicit postponement weight.

    Priority 1 is strongest. Unset priority contributes no postponement
    preference. Lower-priority work may still beat higher-priority work when
    deadlines, dependencies, releases or workload severity demand it.
    """

    if priority_position is None:
        return D("0")

    # Preserve useful distinction beyond the first few positions without
    # making priority an absolute commandment.
    return D("1") / D(priority_position)


def score_production_schedule(
    problem: ScheduleProblem,
    schedule: PlannedSchedule,
) -> ProductionObjective:
    policy = _policy(
        schedule.flavour
    )

    item_by_id = problem.item_by_id

    late_hours = D("0")

    by_item: dict[
        int,
        list[WorkAllocation],
    ] = defaultdict(list)

    for row in schedule.work_allocations:
        by_item[
            row.item_id
        ].append(row)

        item = item_by_id[
            row.item_id
        ]

        if (
            item.due_date is not None
            and row.scheduled_date
            > item.due_date
        ):
            late_hours += row.hours

    infeasible_day_count = 0
    infeasible_excess_hours = D("0")

    overloaded_day_count = 0
    overloaded_excess_hours = D("0")

    max_daily_hours = D("0")
    preferred_excess_squared = D("0")

    for hours in schedule.daily_hours.values():
        max_daily_hours = max(
            max_daily_hours,
            hours,
        )

        if hours > D("24"):
            infeasible_day_count += 1
            infeasible_excess_hours += (
                hours - D("24")
            )

        if (
            hours
            > policy.soft_max_daily_hours
        ):
            overloaded_day_count += 1
            overloaded_excess_hours += (
                hours
                - policy.soft_max_daily_hours
            )

        preferred_excess = max(
            D("0"),
            (
                hours
                - policy.preferred_daily_hours
            ),
        )

        preferred_excess_squared += (
            preferred_excess
            * preferred_excess
        )

    tiny_nonfinal_sessions = 0
    session_shape_penalty = D("0")
    fragmentation_count = 0
    priority_postponement_days = D("0")
    continuity_gap_days = 0

    for item_id, rows in by_item.items():
        item = item_by_id[item_id]

        rows = sorted(
            rows,
            key=lambda row:
                row.scheduled_date,
        )

        bucket = effective_bucket(item)

        if bucket not in ATOMIC_BUCKETS:
            # A splittable task pays for repeated context restarts. One
            # allocation is the zero-fragment baseline.
            fragmentation_count += max(
                0,
                len(rows) - 1,
            )

            for index, row in enumerate(rows):
                is_final = index == len(rows) - 1

                # A genuinely small final remainder is allowed. We do not want
                # a 0.7h tail to force an unnecessary extra day or overload.
                if not (
                    is_final
                    and row.hours
                    < policy.minimum_useful_session_hours
                ):
                    session_shape_penalty += (
                        _session_shape_penalty(
                            row.hours
                        )
                    )

                if (
                    not is_final
                    and row.hours
                    < policy.minimum_useful_session_hours
                ):
                    tiny_nonfinal_sessions += 1

        for left, right in zip(
            rows,
            rows[1:],
        ):
            gap = (
                right.scheduled_date
                - left.scheduled_date
            ).days - 1

            if gap > 0:
                continuity_gap_days += gap

        # Priority postponement is measured only after a task could actually
        # begin. Dependency completion in THIS candidate schedule therefore
        # shifts the earliest feasible start forward correctly.
        weight = _priority_weight(
            item.priority_position
        )

        if weight > 0 and rows:
            earliest = max(
                problem.today,
                item.release_date
                or problem.today,
            )

            if item.anchor_date is not None:
                earliest = item.anchor_date
            else:
                for prerequisite_id in (
                    problem.direct_prerequisites(
                        item_id
                    )
                ):
                    prerequisite_rows = (
                        by_item.get(
                            prerequisite_id,
                            ()
                        )
                    )

                    if prerequisite_rows:
                        prerequisite_completion = max(
                            row.scheduled_date
                            for row
                            in prerequisite_rows
                        )

                        earliest = max(
                            earliest,
                            prerequisite_completion
                            + timedelta(days=1),
                        )

            actual_start = rows[0].scheduled_date

            delay = max(
                0,
                (
                    actual_start
                    - earliest
                ).days,
            )

            priority_postponement_days += (
                D(delay) * weight
            )

    completion_day_sum = 0

    # Planner-only propagated deadlines are reused for human deadline-risk
    # scoring. Canonical task due dates remain untouched.
    from arena.production.flavour_planner import (
        _effective_due_dates,
    )

    # Effective dependency deadlines must be derived using the actual amount
    # of remaining work represented by this production schedule. Passing zero
    # here would incorrectly imply that downstream tasks require zero work
    # sessions and would weaken inherited prerequisite urgency.
    represented_remaining = {
        item.item_id: sum(
            (
                row.hours
                for row in by_item.get(
                    item.item_id,
                    ()
                )
            ),
            D("0"),
        )
        for item in problem.items
    }

    effective_due_dates = _effective_due_dates(
        problem=problem,
        remaining=represented_remaining,
        policy=policy,
    )

    deadline_buffer_risk = D("0")
    unjustified_marathon_excess_hours = D("0")

    # One extra hour beyond the ordinary flavour-specific focused-session cap
    # separates "not ideal" from "severe marathon".
    #
    # Lock-in: ordinary max 6h -> severe above 7h.
    # Monk:    ordinary max 5h -> severe above 6h.
    severe_marathon_threshold = (
        policy.maximum_focused_session_hours
        + D("1")
    )

    for item_id, rows in by_item.items():
        if not rows:
            continue

        item = item_by_id[item_id]
        bucket = effective_bucket(item)

        effective_due = effective_due_dates.get(
            item_id
        )

        completion = max(
            row.scheduled_date
            for row in rows
        )

        # A long focused block is considered justified when the task has at
        # least two full days of effective deadline buffer. This preserves the
        # previously accepted Lock-in behaviour where a long session genuinely
        # buys early completion / dependency handoff.
        meaningful_buffer = False

        if effective_due is not None:
            buffer_days = (
                effective_due
                - completion
            ).days

            meaningful_buffer = (
                buffer_days >= 2
            )
        else:
            buffer_days = None

        # C11.15.9:
        #
        # A concentrated session is only an "unjustified marathon" when the
        # task actually had another legal calendar date available over which
        # the work could have been distributed.
        #
        # Example: a 25h task due today has exactly one legal scheduling date.
        # Its overload is genuinely infeasible, but its same-day concentration
        # is not a human-shape choice and therefore must not pollute this
        # metric.
        earliest_legal_date = max(
            problem.today,
            item.release_date
            or problem.today,
        )

        has_alternative_legal_date = (
            effective_due is None
            or effective_due
            > earliest_legal_date
        )

        if (
            bucket not in ATOMIC_BUCKETS
            and not meaningful_buffer
            and has_alternative_legal_date
        ):
            for row in rows:
                unjustified_marathon_excess_hours += max(
                    D("0"),
                    (
                        row.hours
                        - severe_marathon_threshold
                    ),
                )

        if effective_due is None:
            continue

        # Convex short-buffer / effective-deadline-risk penalty:
        #
        # +3 days or more -> 0
        # +2 days         -> 1
        # +1 day          -> 4
        #  0 days         -> 9
        # -1 day          -> 16
        # -2 days         -> 25
        #
        # A negative buffer against a planner-only effective deadline is not
        # canonical lateness. Actual due-date lateness remains separately and
        # lexicographically dominant in late_hours.
        #
        # But missing the calculated safe handoff point must be MORE risky
        # than reaching it with zero buffer, not accidentally free.
        shortfall = max(
            0,
            3 - buffer_days,
        )

        deadline_buffer_risk += D(
            shortfall * shortfall
        )

    # Lock-in should not manufacture early empty dates while executable,
    # movable work is simply being postponed. Monk intentionally does not
    # receive the same strong pressure toward calendar compression.
    avoidable_idle_days = 0

    if schedule.flavour == "lock-in":
        if schedule.work_allocations:
            final_active = max(
                row.scheduled_date
                for row in schedule.work_allocations
            )

            allocated_by_day = {
                row.scheduled_date
                for row in schedule.work_allocations
            }

            cursor = problem.today

            while cursor < final_active:
                if cursor not in allocated_by_day:
                    for item in problem.items:
                        rows = by_item.get(
                            item.item_id,
                            [],
                        )

                        if not rows:
                            continue

                        if (
                            item.release_date is not None
                            and cursor < item.release_date
                        ):
                            continue

                        if (
                            item.anchor_date is not None
                            and cursor != item.anchor_date
                        ):
                            continue

                        if any(
                            row.scheduled_date > cursor
                            for row in rows
                        ):
                            avoidable_idle_days += 1
                            break

                cursor += timedelta(days=1)

    for rows in by_item.values():
        completion = max(
            row.scheduled_date
            for row in rows
        )

        completion_day_sum += (
            completion
            - problem.today
        ).days

    return ProductionObjective(
        late_hours=late_hours,
        infeasible_day_count=
            infeasible_day_count,
        infeasible_excess_hours=
            infeasible_excess_hours,
        overloaded_day_count=
            overloaded_day_count,
        overloaded_excess_hours=
            overloaded_excess_hours,
        tiny_nonfinal_sessions=
            tiny_nonfinal_sessions,
        session_shape_penalty=
            session_shape_penalty,
        fragmentation_count=
            fragmentation_count,
        priority_postponement_days=
            priority_postponement_days,
        continuity_gap_days=
            continuity_gap_days,
        max_daily_hours=
            max_daily_hours,
        preferred_excess_squared=
            preferred_excess_squared,
        avoidable_idle_days=
            avoidable_idle_days,
        deadline_buffer_risk=
            deadline_buffer_risk,
        completion_day_sum=
            completion_day_sum,
        unjustified_marathon_excess_hours=
            unjustified_marathon_excess_hours,
    )


def _hour_map(
    schedule: PlannedSchedule,
) -> dict[int, dict[date, Decimal]]:
    result: dict[
        int,
        dict[date, Decimal],
    ] = defaultdict(dict)

    for row in schedule.work_allocations:
        result[
            row.item_id
        ][
            row.scheduled_date
        ] = row.hours

    return {
        item_id: dict(rows)
        for item_id, rows
        in result.items()
    }


def _rebuild(
    problem: ScheduleProblem,
    original: PlannedSchedule,
    hours_by_item:
        dict[int, dict[date, Decimal]],
) -> PlannedSchedule | None:
    work_rows: list[
        WorkAllocation
    ] = []

    item_by_id = problem.item_by_id

    try:
        for item_id in sorted(
            hours_by_item
        ):
            positive = tuple(
                DayHeadroom(
                    scheduled_date=day,
                    hours=hours,
                )
                for day, hours
                in sorted(
                    hours_by_item[
                        item_id
                    ].items()
                )
                if hours > 0
            )

            if not positive:
                return None

            work_rows.extend(
                allocate_work_mass(
                    item_by_id[
                        item_id
                    ],
                    original.estimates[
                        item_id
                    ],
                    positive,
                )
            )

        work_allocations = tuple(
            sorted(
                work_rows,
                key=lambda row: (
                    row.scheduled_date,
                    row.item_id,
                ),
            )
        )

        plan = (
            work_allocations_to_plan(
                work_allocations
            )
        )

        validation = (
            validate_dynamic_plan(
                problem,
                plan,
            )
        )

        if validation.violations:
            return None

    except (
        ValueError,
        KeyError,
    ):
        return None

    daily_raw: dict[
        date,
        Decimal,
    ] = defaultdict(
        lambda: D("0")
    )

    for row in work_allocations:
        daily_raw[
            row.scheduled_date
        ] += row.hours

    if work_allocations:
        final_date = max(
            row.scheduled_date
            for row in work_allocations
        )
    else:
        final_date = problem.today

    daily_hours: dict[
        date,
        Decimal,
    ] = {}

    cursor = problem.today

    while cursor <= final_date:
        daily_hours[
            cursor
        ] = daily_raw.get(
            cursor,
            D("0"),
        )

        cursor += timedelta(
            days=1
        )

    policy = _policy(
        original.flavour
    )

    daily_status = {
        day: classify_day(
            hours,
            preferred_daily_hours=
                policy.preferred_daily_hours,
            soft_max_daily_hours=
                policy.soft_max_daily_hours,
        )
        for day, hours
        in daily_hours.items()
    }

    return PlannedSchedule(
        flavour=original.flavour,
        plan=plan,
        work_allocations=
            work_allocations,
        estimates=original.estimates,
        daily_hours=daily_hours,
        daily_status=daily_status,
        weekly_status=weekly_statuses(
            daily_hours,
            preferred_daily_hours=
                policy.preferred_daily_hours,
            soft_max_daily_hours=
                policy.soft_max_daily_hours,
        ),
        monthly_status=
            monthly_statuses(
                daily_hours,
                preferred_daily_hours=
                    policy.preferred_daily_hours,
                soft_max_daily_hours=
                    policy.soft_max_daily_hours,
            ),
    )


def _candidate_amounts(
    *,
    source_hours: Decimal,
    target_load: Decimal,
    policy,
) -> tuple[Decimal, ...]:
    amounts: set[
        Decimal
    ] = set()

    amounts.add(
        source_hours
    )

    amounts.add(
        min(
            source_hours,
            policy.maximum_focused_session_hours,
        )
    )

    ordinary_room = max(
        D("0"),
        (
            policy.preferred_daily_hours
            - target_load
        ),
    )

    if ordinary_room > 0:
        amounts.add(
            min(
                source_hours,
                ordinary_room,
            )
        )

    soft_room = max(
        D("0"),
        (
            policy.soft_max_daily_hours
            - target_load
        ),
    )

    if soft_room > 0:
        amounts.add(
            min(
                source_hours,
                soft_room,
            )
        )

    amounts.add(
        min(
            source_hours,
            policy.minimum_useful_session_hours,
        )
    )

    result = []

    for amount in sorted(
        amounts,
        reverse=True,
    ):
        if amount <= 0:
            continue

        tail = (
            source_hours
            - amount
        )

        if (
            tail > 0
            and tail
            < policy.minimum_useful_session_hours
        ):
            amount = (
                source_hours
            )

        if amount not in result:
            result.append(
                amount
            )

    return tuple(result)


def _anchored_congestion_recovery_moves(
    problem: ScheduleProblem,
    schedule: PlannedSchedule,
    *,
    max_candidates: int = 220,
) -> tuple[WorkHourMove, ...]:
    """Prioritise evacuation of movable work from congested anchor days.

    Anchored work is unavoidable on its fixed date. If movable work shares
    that date and the total day is already above the flavour soft maximum,
    broad search should not spend thousands of evaluations elsewhere before
    considering legal moves that free the anchored day.

    This changes neighbourhood ordering only. Candidate acceptance still uses
    the normal lexicographic production objective and independent rebuild
    validation.
    """

    policy = _policy(
        schedule.flavour
    )

    anchored_days = set()

    for row in schedule.work_allocations:
        item = problem.item_by_id[
            row.item_id
        ]

        if item.anchor_date is not None:
            anchored_days.add(
                row.scheduled_date
            )

    congested_days = {
        day
        for day in anchored_days
        if (
            schedule.daily_hours.get(
                day,
                D("0"),
            )
            > policy.soft_max_daily_hours
        )
    }

    if not congested_days:
        return ()

    candidates = []

    for move in _moves(
        problem,
        schedule,
    ):
        if move.from_date not in congested_days:
            continue

        item = problem.item_by_id[
            move.item_id
        ]

        if item.anchor_date is not None:
            continue

        # This recovery operator exists to evacuate the anchored date, not
        # shuffle movable work between two already-congested anchor dates.
        if move.to_date in congested_days:
            continue

        target_load = (
            schedule.daily_hours.get(
                move.to_date,
                D("0"),
            )
        )

        candidates.append(
            (
                # Prefer relieving the most congested source day first.
                -schedule.daily_hours.get(
                    move.from_date,
                    D("0"),
                ),

                # Then prefer calmer destinations.
                target_load,

                # Higher-priority movable work receives the earlier tie break.
                (
                    item.priority_position
                    if item.priority_position
                    is not None
                    else 10_000
                ),

                move.from_date,
                move.to_date,
                move.item_id,
                -move.hours,
                move,
            )
        )

    candidates.sort(
        key=lambda entry:
            entry[:-1]
    )

    return tuple(
        entry[-1]
        for entry
        in candidates[:max_candidates]
    )


def _lateness_recovery_moves(
    problem: ScheduleProblem,
    schedule: PlannedSchedule,
    *,
    max_candidates: int = 180,
) -> tuple[WorkHourMove, ...]:
    """Focused recovery neighbourhood while actual due-date work is late.

    Actual lateness is the first production objective. When late work exists,
    spending thousands of evaluations polishing session shape or generic load
    balance before examining the late dependency region is wasteful.

    The recovery set contains:

    - allocations that are actually after their canonical due date;
    - prerequisite ancestors of those late tasks, because moving a dependent
      earlier can be impossible until its prerequisite chain moves earlier.

    Ancestors use planner-only propagated effective deadlines. Canonical due
    dates remain unchanged.

    This is intentionally bounded and deterministic. The ordinary production
    neighbourhood remains available if this focused pass cannot improve the
    current plan.
    """

    policy = _policy(
        schedule.flavour
    )

    by_item: dict[
        int,
        list[WorkAllocation],
    ] = defaultdict(list)

    for row in schedule.work_allocations:
        by_item[row.item_id].append(
            row
        )

    late_ids = set()

    for item_id, rows in by_item.items():
        item = problem.item_by_id[
            item_id
        ]

        if item.due_date is None:
            continue

        if any(
            row.scheduled_date
            > item.due_date
            for row in rows
        ):
            late_ids.add(
                item_id
            )

    if not late_ids:
        return ()

    relevant_ids = set(
        late_ids
    )

    stack = list(
        late_ids
    )

    while stack:
        item_id = stack.pop()

        for prerequisite_id in (
            problem.direct_prerequisites(
                item_id
            )
        ):
            if (
                prerequisite_id
                in relevant_ids
            ):
                continue

            relevant_ids.add(
                prerequisite_id
            )
            stack.append(
                prerequisite_id
            )

    from arena.production.flavour_planner import (
        _effective_due_dates,
    )

    represented_remaining = {
        item.item_id: sum(
            (
                row.hours
                for row
                in by_item.get(
                    item.item_id,
                    ()
                )
            ),
            D("0"),
        )
        for item in problem.items
    }

    effective_due_dates = (
        _effective_due_dates(
            problem=problem,
            remaining=
                represented_remaining,
            policy=policy,
        )
    )

    ranked = []

    for item_id in sorted(
        relevant_ids
    ):
        item = problem.item_by_id[
            item_id
        ]

        if item.anchor_date is not None:
            continue

        rows = sorted(
            by_item.get(
                item_id,
                (),
            ),
            key=lambda row:
                row.scheduled_date,
        )

        if not rows:
            continue

        actually_late = (
            item_id in late_ids
        )

        recovery_due = (
            item.due_date
            if actually_late
            else effective_due_dates.get(
                item_id
            )
        )

        if recovery_due is None:
            continue

        earliest = max(
            problem.today,
            item.release_date
            or problem.today,
        )

        for row in rows:
            # For the actually-late task, spend the fast-path budget on the
            # rows that are themselves late. For prerequisite ancestors, any
            # allocation may need to move earlier to unlock the chain.
            if (
                actually_late
                and row.scheduled_date
                <= item.due_date
            ):
                continue

            latest_target = min(
                recovery_due,
                row.scheduled_date
                - timedelta(days=1),
            )

            if latest_target < earliest:
                continue

            target_days = []

            cursor = earliest

            while cursor <= latest_target:
                target_days.append(
                    cursor
                )
                cursor += timedelta(
                    days=1
                )

            target_days.sort(
                key=lambda day: (
                    schedule.daily_hours.get(
                        day,
                        D("0"),
                    ) > D("24"),
                    schedule.daily_hours.get(
                        day,
                        D("0"),
                    ),
                    abs(
                        (
                            latest_target
                            - day
                        ).days
                    ),
                    day,
                )
            )

            bucket = effective_bucket(
                item
            )

            for target in target_days:
                if bucket in ATOMIC_BUCKETS:
                    amounts = (
                        row.hours,
                    )
                else:
                    target_load = (
                        schedule.daily_hours.get(
                            target,
                            D("0"),
                        )
                    )

                    raw_amounts = [
                        row.hours,
                        min(
                            row.hours,
                            policy.maximum_focused_session_hours,
                        ),
                    ]

                    preferred_room = max(
                        D("0"),
                        (
                            policy.preferred_daily_hours
                            - target_load
                        ),
                    )

                    if preferred_room > 0:
                        raw_amounts.append(
                            min(
                                row.hours,
                                preferred_room,
                            )
                        )

                    amounts = tuple(
                        dict.fromkeys(
                            amount
                            for amount
                            in raw_amounts
                            if amount > 0
                        )
                    )

                for amount in amounts:
                    tail = (
                        row.hours
                        - amount
                    )

                    if (
                        tail > 0
                        and tail
                        < policy.minimum_useful_session_hours
                    ):
                        amount = (
                            row.hours
                        )

                    move = WorkHourMove(
                        item_id=item_id,
                        from_date=
                            row.scheduled_date,
                        to_date=target,
                        hours=amount,
                    )

                    ranked.append(
                        (
                            0
                            if actually_late
                            else 1,
                            recovery_due,
                            schedule.daily_hours.get(
                                target,
                                D("0"),
                            ),
                            abs(
                                (
                                    latest_target
                                    - target
                                ).days
                            ),
                            (
                                item.priority_position
                                if item.priority_position
                                is not None
                                else 10_000
                            ),
                            item_id,
                            row.scheduled_date,
                            target,
                            -amount,
                            move,
                        )
                    )

    ranked.sort(
        key=lambda entry:
            entry[:-1]
    )

    return tuple(
        entry[-1]
        for entry
        in ranked[:max_candidates]
    )


def _moves(
    problem: ScheduleProblem,
    schedule: PlannedSchedule,
) -> tuple[WorkHourMove, ...]:
    """Deterministic dynamic relocation neighbourhood.

    Unlike the first C11.12 neighbourhood, work may move either earlier or
    later. Independent validation decides legality; the objective decides
    usefulness.

    This prevents the search from overshooting an earlier date and then being
    unable to rebalance work back toward a later legal date.
    """

    policy = _policy(
        schedule.flavour
    )

    daily = schedule.daily_hours

    if schedule.work_allocations:
        horizon_end = max(
            row.scheduled_date
            for row
            in schedule.work_allocations
        )
    else:
        horizon_end = (
            problem.today
        )

    due_dates = [
        item.due_date
        for item in problem.items
        if item.due_date is not None
    ]

    if due_dates:
        horizon_end = max(
            horizon_end,
            max(due_dates),
        )

    result = []

    for row in sorted(
        schedule.work_allocations,
        key=lambda row: (
            row.scheduled_date,
            row.item_id,
        ),
    ):
        item = problem.item_by_id[
            row.item_id
        ]

        bucket = effective_bucket(
            item
        )

        earliest = max(
            problem.today,
            item.release_date
            or problem.today,
        )

        latest = (
            item.due_date
            if item.due_date
            is not None
            else horizon_end
        )

        if (
            item.anchor_date
            is not None
        ):
            earliest = max(
                earliest,
                item.anchor_date,
            )
            latest = min(
                latest,
                item.anchor_date,
            )

        target = earliest

        while target <= latest:
            if target == row.scheduled_date:
                target += timedelta(
                    days=1
                )
                continue

            if bucket in ATOMIC_BUCKETS:
                amounts = (
                    row.hours,
                )
            else:
                amounts = (
                    _candidate_amounts(
                        source_hours=
                            row.hours,
                        target_load=
                            daily.get(
                                target,
                                D("0"),
                            ),
                        policy=policy,
                    )
                )

                # Fine-grained balancing amount. This lets search repair
                # 10.20h / 9.80h type imbalances rather than being limited to
                # whole session-sized relocations.
                balance_delta = abs(
                    daily.get(
                        row.scheduled_date,
                        D("0"),
                    )
                    - daily.get(
                        target,
                        D("0"),
                    )
                ) / D("2")

                if (
                    balance_delta > 0
                    and balance_delta
                    <= row.hours
                ):
                    amounts = tuple(
                        dict.fromkeys(
                            amounts
                            + (
                                balance_delta,
                            )
                        )
                    )

            for amount in amounts:
                if amount <= 0:
                    continue

                result.append(
                    WorkHourMove(
                        item_id=
                            row.item_id,
                        from_date=
                            row.scheduled_date,
                        to_date=target,
                        hours=amount,
                    )
                )

            target += timedelta(
                days=1
            )

    return tuple(result)



def _apply_move(
    problem: ScheduleProblem,
    schedule: PlannedSchedule,
    move: WorkHourMove,
) -> PlannedSchedule | None:
    hours_by_item = _hour_map(
        schedule
    )

    rows = hours_by_item.get(
        move.item_id
    )

    if rows is None:
        return None

    source = rows.get(
        move.from_date,
        D("0"),
    )

    if (
        move.to_date
        == move.from_date
        or move.hours <= 0
        or move.hours > source
    ):
        return None

    item = problem.item_by_id[
        move.item_id
    ]

    bucket = effective_bucket(
        item
    )

    if (
        bucket in ATOMIC_BUCKETS
        and move.hours != source
    ):
        return None

    rows[
        move.from_date
    ] = (
        source - move.hours
    )

    if rows[
        move.from_date
    ] <= 0:
        del rows[
            move.from_date
        ]

    rows[
        move.to_date
    ] = (
        rows.get(
            move.to_date,
            D("0"),
        )
        + move.hours
    )

    return _rebuild(
        problem,
        schedule,
        hours_by_item,
    )


def _apply_compound_move(
    problem: ScheduleProblem,
    schedule: PlannedSchedule,
    move: CompoundWorkHourMove,
) -> PlannedSchedule | None:
    """Apply two relocations atomically, validating only the finished state."""

    hours_by_item = _hour_map(
        schedule
    )

    for part in (
        move.first,
        move.second,
    ):
        rows = hours_by_item.get(
            part.item_id
        )

        if rows is None:
            return None

        source = rows.get(
            part.from_date,
            D("0"),
        )

        if (
            part.from_date
            == part.to_date
            or part.hours <= 0
            or part.hours > source
        ):
            return None

        item = problem.item_by_id[
            part.item_id
        ]

        if (
            effective_bucket(item)
            in ATOMIC_BUCKETS
            and part.hours != source
        ):
            return None

        rows[
            part.from_date
        ] = (
            source
            - part.hours
        )

        if rows[
            part.from_date
        ] <= 0:
            del rows[
                part.from_date
            ]

        rows[
            part.to_date
        ] = (
            rows.get(
                part.to_date,
                D("0"),
            )
            + part.hours
        )

    return _rebuild(
        problem,
        schedule,
        hours_by_item,
    )


def _compound_moves(
    problem: ScheduleProblem,
    schedule: PlannedSchedule,
    single_moves:
        tuple[WorkHourMove, ...],
) -> tuple[CompoundWorkHourMove, ...]:
    """Bounded deterministic pair neighbourhood.

    Pair moves are intentionally conservative. We only combine relocations
    that touch different tasks and exchange pressure between overlapping
    dates. This captures useful small destroy/repair behaviour without
    exploding into an unrestricted O(n^2) search over arbitrary pairs.
    """

    result = []

    candidates = single_moves[
        : min(
            len(single_moves),
            120,
        )
    ]

    for index, first in enumerate(
        candidates
    ):
        for second in candidates[
            index + 1:
        ]:
            if (
                first.item_id
                == second.item_id
            ):
                continue

            touches = {
                first.from_date,
                first.to_date,
            } & {
                second.from_date,
                second.to_date,
            }

            if not touches:
                continue

            result.append(
                CompoundWorkHourMove(
                    first=first,
                    second=second,
                )
            )

            if len(result) >= 1500:
                return tuple(
                    result
                )

    return tuple(result)


def _consolidation_moves(
    problem: ScheduleProblem,
    schedule: PlannedSchedule,
) -> tuple[WorkHourMove, ...]:
    """Whole-fragment consolidation neighbourhood.

    The general relocation neighbourhood is intentionally broad and can spend
    most of its evaluation budget on load-balancing alternatives before it
    reaches obvious human-quality repairs.

    This neighbourhood therefore runs first and only asks:

        Can one complete splittable allocation be merged into another
        existing allocation of the SAME task?

    Moving the whole source allocation removes one task touch if the candidate
    remains legal. The normal production objective decides whether the merge
    is actually worthwhile.
    """

    by_item: dict[
        int,
        list[WorkAllocation],
    ] = defaultdict(list)

    for row in schedule.work_allocations:
        by_item[row.item_id].append(row)

    ranked = []

    for item_id, rows in by_item.items():
        item = problem.item_by_id[item_id]

        if effective_bucket(item) in ATOMIC_BUCKETS:
            continue

        if len(rows) < 2:
            continue

        ordered = sorted(
            rows,
            key=lambda row: (
                -_session_shape_penalty(
                    row.hours
                ),
                row.hours,
                row.scheduled_date,
            ),
        )

        for source in ordered:
            for target in rows:
                if (
                    target.scheduled_date
                    == source.scheduled_date
                ):
                    continue

                move = WorkHourMove(
                    item_id=item_id,
                    from_date=
                        source.scheduled_date,
                    to_date=
                        target.scheduled_date,
                    hours=source.hours,
                )

                resulting_hours = (
                    target.hours
                    + source.hours
                )

                shape_delta_hint = (
                    _session_shape_penalty(
                        resulting_hours
                    )
                    - _session_shape_penalty(
                        source.hours
                    )
                    - _session_shape_penalty(
                        target.hours
                    )
                )

                ranked.append(
                    (
                        shape_delta_hint,
                        -_session_shape_penalty(
                            source.hours
                        ),
                        source.scheduled_date,
                        target.scheduled_date,
                        item_id,
                        move,
                    )
                )

    ranked.sort(
        key=lambda row: row[:-1]
    )

    return tuple(
        row[-1]
        for row in ranked[:600]
    )


def _balanced_exchange_moves(
    problem: ScheduleProblem,
    schedule: PlannedSchedule,
) -> tuple[CompoundWorkHourMove, ...]:
    """Load-preserving fragment consolidation through a two-task exchange.

    A whole fragment of one splittable task is moved into another existing
    session of that task. An equal amount of a DIFFERENT splittable task is
    simultaneously moved back to the vacated day.

    Example:

        Monday:
            assignment A 1.5h

        Tuesday:
            assignment A 1.5h
            assignment B 3h

    Candidate:

        A: Monday -> Tuesday 1.5h
        B: Tuesday -> Monday 1.5h

    Monday and Tuesday retain exactly the same total workload, but assignment A
    now has one fewer restart.

    Independent plan validation still decides legality. This is deliberately a
    small targeted exchange, not unrestricted combinatorial swapping.
    """

    by_item: dict[
        int,
        list[WorkAllocation],
    ] = defaultdict(list)

    by_day: dict[
        date,
        list[WorkAllocation],
    ] = defaultdict(list)

    for row in schedule.work_allocations:
        by_item[row.item_id].append(row)
        by_day[row.scheduled_date].append(row)

    ranked = []

    for focus_id, focus_rows in by_item.items():
        focus_item = problem.item_by_id[
            focus_id
        ]

        if (
            effective_bucket(focus_item)
            in ATOMIC_BUCKETS
        ):
            continue

        if len(focus_rows) < 2:
            continue

        focus_sources = sorted(
            focus_rows,
            key=lambda row: (
                -_session_shape_penalty(
                    row.hours
                ),
                row.hours,
                row.scheduled_date,
            ),
        )

        for source in focus_sources:
            amount = source.hours

            if amount <= 0:
                continue

            for target in focus_rows:
                if (
                    target.scheduled_date
                    == source.scheduled_date
                ):
                    continue

                target_day = (
                    target.scheduled_date
                )

                for displaced in by_day.get(
                    target_day,
                    (),
                ):
                    if (
                        displaced.item_id
                        == focus_id
                    ):
                        continue

                    displaced_item = (
                        problem.item_by_id[
                            displaced.item_id
                        ]
                    )

                    if (
                        effective_bucket(
                            displaced_item
                        )
                        in ATOMIC_BUCKETS
                    ):
                        continue

                    # Exact counterbalance preserves BOTH affected day totals.
                    if displaced.hours < amount:
                        continue

                    first = WorkHourMove(
                        item_id=focus_id,
                        from_date=
                            source.scheduled_date,
                        to_date=target_day,
                        hours=amount,
                    )

                    second = WorkHourMove(
                        item_id=
                            displaced.item_id,
                        from_date=target_day,
                        to_date=
                            source.scheduled_date,
                        hours=amount,
                    )

                    resulting_focus = (
                        target.hours
                        + amount
                    )

                    shape_hint = (
                        _session_shape_penalty(
                            resulting_focus
                        )
                        - _session_shape_penalty(
                            source.hours
                        )
                        - _session_shape_penalty(
                            target.hours
                        )
                    )

                    ranked.append(
                        (
                            shape_hint,
                            -_session_shape_penalty(
                                source.hours
                            ),
                            source.scheduled_date,
                            target_day,
                            focus_id,
                            displaced.item_id,
                            CompoundWorkHourMove(
                                first=first,
                                second=second,
                            ),
                        )
                    )

    ranked.sort(
        key=lambda row: row[:-1]
    )

    return tuple(
        row[-1]
        for row in ranked[:1200]
    )


def _load_preserving_window_repack_candidates(
    problem: ScheduleProblem,
    schedule: PlannedSchedule,
) -> tuple[PlannedSchedule, ...]:
    """Multi-task load-preserving human-shape repacking.

    C11.14b's balanced exchange requires one other task on the target day to
    provide the complete counterweight. That is too restrictive for crowded
    real calendars: the spare movable load may be distributed across several
    flexible tasks.

    This neighbourhood therefore:

    1. identifies a poor focused-work allocation;
    2. moves part/all of it to another nearby legal active day;
    3. moves an equal amount of one OR MORE flexible allocations back;
    4. thereby preserves the total workload on both affected days exactly.

    Daily peak/load is therefore unchanged by construction. The normal
    objective still decides whether changes to deadline buffer, priority,
    fragmentation, session shape, etc. are worthwhile.

    Independent validation remains authoritative.
    """

    if not schedule.work_allocations:
        return ()

    policy = _policy(
        schedule.flavour
    )

    by_item: dict[
        int,
        list[WorkAllocation],
    ] = defaultdict(list)

    by_day: dict[
        date,
        list[WorkAllocation],
    ] = defaultdict(list)

    for row in schedule.work_allocations:
        by_item[row.item_id].append(
            row
        )

        by_day[row.scheduled_date].append(
            row
        )

    current_map = _hour_map(
        schedule
    )

    active_days = sorted(
        by_day
    )

    results = []
    seen = set()

    for focus_id in sorted(
        by_item
    ):
        focus_item = problem.item_by_id[
            focus_id
        ]

        if (
            effective_bucket(focus_item)
            in ATOMIC_BUCKETS
        ):
            continue

        if focus_item.anchor_date is not None:
            continue

        focus_rows = sorted(
            by_item[focus_id],
            key=lambda row:
                row.scheduled_date,
        )

        for source_index, source in enumerate(
            focus_rows
        ):
            is_final = (
                source_index
                == len(focus_rows) - 1
            )

            oversized = (
                source.hours > D("6")
            )

            undersized = (
                not is_final
                and source.hours
                < D("1.5")
            )

            if not (
                oversized
                or undersized
            ):
                continue

            source_day = (
                source.scheduled_date
            )

            earliest = max(
                problem.today,
                focus_item.release_date
                or problem.today,
            )

            latest = (
                focus_item.due_date
                if focus_item.due_date
                is not None
                else active_days[-1]
            )

            target_days = [
                day
                for day in active_days
                if (
                    day != source_day
                    and earliest <= day <= latest
                    and abs(
                        (
                            day
                            - source_day
                        ).days
                    ) <= 5
                )
            ]

            # Keep Lock-in's natural earlier-work tendency when otherwise
            # equivalent. Monk simply favours nearby dates.
            if schedule.flavour == "lock-in":
                target_days.sort(
                    key=lambda day: (
                        day > source_day,
                        abs(
                            (
                                day
                                - source_day
                            ).days
                        ),
                        day,
                    )
                )
            else:
                target_days.sort(
                    key=lambda day: (
                        abs(
                            (
                                day
                                - source_day
                            ).days
                        ),
                        day,
                    )
                )

            if oversized:
                amounts = []

                for desired_remainder in (
                    D("4"),
                    D("5"),
                    D("3.5"),
                ):
                    amount = (
                        source.hours
                        - desired_remainder
                    )

                    if amount <= 0:
                        continue

                    if amount not in amounts:
                        amounts.append(
                            amount
                        )
            else:
                # Remove the whole token allocation when possible.
                amounts = [
                    source.hours
                ]

            for target_day in target_days:
                existing_focus = (
                    current_map[
                        focus_id
                    ].get(
                        target_day,
                        D("0"),
                    )
                )

                for amount in amounts:
                    if amount <= 0:
                        continue

                    if amount > source.hours:
                        continue

                    resulting_target_focus = (
                        existing_focus
                        + amount
                    )

                    # Do not fix one marathon by manufacturing another.
                    if (
                        resulting_target_focus
                        > D("6")
                    ):
                        continue

                    donors = []

                    for donor in by_day[
                        target_day
                    ]:
                        if (
                            donor.item_id
                            == focus_id
                        ):
                            continue

                        donor_item = (
                            problem.item_by_id[
                                donor.item_id
                            ]
                        )

                        if (
                            effective_bucket(
                                donor_item
                            )
                            in ATOMIC_BUCKETS
                        ):
                            continue

                        if (
                            donor_item.anchor_date
                            is not None
                        ):
                            continue

                        donor_earliest = max(
                            problem.today,
                            donor_item.release_date
                            or problem.today,
                        )

                        donor_latest = (
                            donor_item.due_date
                            if donor_item.due_date
                            is not None
                            else active_days[-1]
                        )

                        if not (
                            donor_earliest
                            <= source_day
                            <= donor_latest
                        ):
                            continue

                        # Prefer moving work that already has another block on
                        # the destination day, because that tends to avoid
                        # creating a new context switch.
                        donor_has_source_block = (
                            current_map[
                                donor.item_id
                            ].get(
                                source_day,
                                D("0"),
                            )
                            > 0
                        )

                        donors.append(
                            (
                                not donor_has_source_block,
                                -donor.hours,
                                donor.item_id,
                                donor,
                            )
                        )

                    donors.sort(
                        key=lambda row:
                            row[:-1]
                    )

                    available = sum(
                        (
                            donor.hours
                            for *_, donor
                            in donors
                        ),
                        D("0"),
                    )

                    if available < amount:
                        continue

                    remaining = amount
                    transfers = []

                    for *_, donor in donors:
                        if remaining <= 0:
                            break

                        donor_source_existing = (
                            current_map[
                                donor.item_id
                            ].get(
                                source_day,
                                D("0"),
                            )
                        )

                        # C11.14f donor-shape safety:
                        #
                        # A load-preserving repair must not fix the focus task
                        # by manufacturing an oversized focused block for one
                        # of the counterbalancing donor tasks.
                        #
                        # Existing long sessions remain legal elsewhere. This
                        # guard only limits NEW collateral concentration caused
                        # by this neighbourhood.
                        donor_source_room = max(
                            D("0"),
                            (
                                policy.maximum_focused_session_hours
                                - donor_source_existing
                            ),
                        )

                        transfer = min(
                            donor.hours,
                            remaining,
                            donor_source_room,
                        )

                        if transfer <= 0:
                            continue

                        donor_left = (
                            donor.hours
                            - transfer
                        )

                        # Avoid deliberately creating a new token remainder.
                        # A complete move is fine; otherwise leave at least one
                        # useful hour on the donor's original date.
                        if (
                            donor_left > 0
                            and donor_left
                            < policy.minimum_useful_session_hours
                        ):
                            continue

                        transfers.append(
                            (
                                donor.item_id,
                                transfer,
                            )
                        )

                        remaining -= transfer

                    if remaining != 0:
                        continue

                    identity = (
                        focus_id,
                        source_day,
                        target_day,
                        amount,
                        tuple(
                            transfers
                        ),
                    )

                    if identity in seen:
                        continue

                    seen.add(
                        identity
                    )

                    repacked = {
                        item_id:
                            dict(day_map)
                        for item_id, day_map
                        in current_map.items()
                    }

                    # Focus task: source -> target.
                    repacked[
                        focus_id
                    ][
                        source_day
                    ] -= amount

                    if (
                        repacked[
                            focus_id
                        ][
                            source_day
                        ]
                        <= 0
                    ):
                        del repacked[
                            focus_id
                        ][
                            source_day
                        ]

                    repacked[
                        focus_id
                    ][
                        target_day
                    ] = (
                        repacked[
                            focus_id
                        ].get(
                            target_day,
                            D("0"),
                        )
                        + amount
                    )

                    # One-or-more donor tasks: target -> source.
                    for (
                        donor_id,
                        transfer,
                    ) in transfers:
                        repacked[
                            donor_id
                        ][
                            target_day
                        ] -= transfer

                        if (
                            repacked[
                                donor_id
                            ][
                                target_day
                            ]
                            <= 0
                        ):
                            del repacked[
                                donor_id
                            ][
                                target_day
                            ]

                        repacked[
                            donor_id
                        ][
                            source_day
                        ] = (
                            repacked[
                                donor_id
                            ].get(
                                source_day,
                                D("0"),
                            )
                            + transfer
                        )

                    candidate = _rebuild(
                        problem,
                        schedule,
                        repacked,
                    )

                    if candidate is None:
                        continue

                    # This neighbourhood promises exact day-load
                    # preservation. Assert the contract before exposing the
                    # candidate to search.
                    if (
                        candidate.daily_hours.get(
                            source_day,
                            D("0"),
                        )
                        != schedule.daily_hours.get(
                            source_day,
                            D("0"),
                        )
                    ):
                        continue

                    if (
                        candidate.daily_hours.get(
                            target_day,
                            D("0"),
                        )
                        != schedule.daily_hours.get(
                            target_day,
                            D("0"),
                        )
                    ):
                        continue

                    results.append(
                        candidate
                    )

                    if len(results) >= 500:
                        return tuple(
                            results
                        )

    return tuple(
        results
    )


def _decimal_ceil_div(
    total: Decimal,
    divisor: Decimal,
) -> int:
    quotient = int(
        total // divisor
    )

    if total % divisor > 0:
        quotient += 1

    return quotient


def _block_repack_candidates(
    problem: ScheduleProblem,
    schedule: PlannedSchedule,
) -> tuple[PlannedSchedule, ...]:
    """Targeted human block repacking for fragmented splittable tasks.

    This neighbourhood does NOT impose a fixed session duration.

    Instead, for an already-fragmented task it considers a small deterministic
    family of lower-touch representations whose average session size sits in
    the human-useful region established in C11.14.

    Examples:

        12h -> 3 x 4h
             4 x 3h
             5 x 2.4h

        24h -> 6 x 4h
             7 x ~3.43h
             8 x 3h

    Candidate days are chosen from the task's legal calendar using current
    non-task workload as the main placement signal.

    The production objective and independent validator remain authoritative:
    this operator merely supplies better-shaped candidates to search.
    """

    if not schedule.work_allocations:
        return ()

    policy = _policy(
        schedule.flavour
    )

    by_item: dict[
        int,
        list[WorkAllocation],
    ] = defaultdict(list)

    for row in schedule.work_allocations:
        by_item[row.item_id].append(
            row
        )

    current_map = _hour_map(
        schedule
    )

    final_active = max(
        row.scheduled_date
        for row in schedule.work_allocations
    )

    dated_due = [
        item.due_date
        for item in problem.items
        if item.due_date is not None
    ]

    horizon_end = final_active

    if dated_due:
        horizon_end = max(
            horizon_end,
            max(dated_due),
        )

    results = []
    seen = set()

    for item_id, rows in sorted(
        by_item.items()
    ):
        item = problem.item_by_id[
            item_id
        ]

        if (
            effective_bucket(item)
            in ATOMIC_BUCKETS
        ):
            continue

        if item.anchor_date is not None:
            continue

        ordered_rows = sorted(
            rows,
            key=lambda row:
                row.scheduled_date,
        )

        has_oversized_session = any(
            row.hours > D("6")
            for row in ordered_rows
        )

        has_tiny_nonfinal = any(
            row.hours
            < policy.minimum_useful_session_hours
            for row in ordered_rows[:-1]
        )

        # Repacking is useful for either fragmentation OR a bad session shape.
        # In particular, an oversized >6h block may need one additional touch
        # to become humane, while a tiny token fragment may need the same
        # number of touches redistributed rather than strictly reduced.
        if (
            len(rows) < 3
            and not has_oversized_session
            and not has_tiny_nonfinal
        ):
            continue

        total = sum(
            (
                row.hours
                for row in rows
            ),
            D("0"),
        )

        if total < D("2"):
            continue

        current_touches = len(
            rows
        )

        # The sweet region is approximately 2-4h, but we deliberately test a
        # few neighbouring counts rather than asserting one session length.
        minimum_count = max(
            1,
            _decimal_ceil_div(
                total,
                D("4"),
            ),
        )

        maximum_useful_count = (
            _decimal_ceil_div(
                total,
                D("2"),
            )
        )

        candidate_counts = []

        # Normally block repacking prefers fewer touches.
        #
        # But if the CURRENT shape itself contains a >6h focus marathon or a
        # non-final sub-hour token session, also permit same-touch or slightly
        # higher-touch representations. This lets:
        #
        #   0.09 + 3.6 + ... -> sensible redistribution
        #
        # and:
        #
        #   3.6 + 3.6 + 3.6 + 7.2
        #       -> 5 x ~3.6
        #
        # without establishing a fixed session count.
        count_ceiling = current_touches

        if (
            has_oversized_session
            or has_tiny_nonfinal
        ):
            count_ceiling = (
                current_touches + 2
            )

        for count in (
            minimum_count,
            minimum_count + 1,
            minimum_count + 2,
            current_touches,
            current_touches + 1,
        ):
            if count < 1:
                continue

            if (
                count
                > maximum_useful_count
            ):
                continue

            if count > count_ceiling:
                continue

            if (
                count > current_touches
                and not (
                    has_oversized_session
                    or has_tiny_nonfinal
                )
            ):
                continue

            if count not in candidate_counts:
                candidate_counts.append(
                    count
                )

        if not candidate_counts:
            continue

        earliest = max(
            problem.today,
            item.release_date
            or problem.today,
        )

        latest = (
            item.due_date
            if item.due_date is not None
            else horizon_end
        )

        if latest < earliest:
            continue

        legal_days = []

        cursor = earliest

        while cursor <= latest:
            legal_days.append(
                cursor
            )
            cursor += timedelta(
                days=1
            )

        if not legal_days:
            continue

        item_hours_by_day = {
            row.scheduled_date:
                row.hours
            for row in rows
        }

        base_load = {
            day: (
                schedule.daily_hours.get(
                    day,
                    D("0"),
                )
                - item_hours_by_day.get(
                    day,
                    D("0"),
                )
            )
            for day in legal_days
        }

        for count in candidate_counts:
            if len(legal_days) < count:
                continue

            average = (
                total
                / D(count)
            )

            # Do not generate block-repack candidates outside the broad human
            # focus region. The general search remains responsible for cases
            # where pressure genuinely requires unusual session sizes.
            if (
                average < D("1.5")
                or average > D("4")
            ):
                continue

            if schedule.flavour == "monk":
                preferred_order = sorted(
                    legal_days,
                    key=lambda day: (
                        max(
                            D("0"),
                            (
                                base_load[day]
                                + average
                                - policy.preferred_daily_hours
                            ),
                        ),
                        max(
                            D("0"),
                            (
                                base_load[day]
                                + average
                                - policy.soft_max_daily_hours
                            ),
                        ),
                        base_load[day],
                        day,
                    ),
                )
            else:
                preferred_order = sorted(
                    legal_days,
                    key=lambda day: (
                        (
                            base_load[day]
                            + average
                        )
                        > policy.soft_max_daily_hours,
                        day,
                        base_load[day],
                    ),
                )

            low_load_order = sorted(
                legal_days,
                key=lambda day: (
                    base_load[day],
                    day,
                ),
            )

            chronological_order = list(
                legal_days
            )

            orderings = (
                preferred_order,
                low_load_order,
                chronological_order,
            )

            for ordering in orderings:
                selected = tuple(
                    sorted(
                        ordering[:count]
                    )
                )

                identity = (
                    item_id,
                    selected,
                    count,
                )

                if identity in seen:
                    continue

                seen.add(
                    identity
                )

                replacement = {
                    target_day: average
                    for target_day
                    in selected
                }

                # Decimal division is exact for many common cases, but force
                # exact work conservation through the final block regardless.
                allocated = (
                    average
                    * D(count - 1)
                )

                replacement[
                    selected[-1]
                ] = (
                    total
                    - allocated
                )

                repacked = {
                    candidate_item:
                        dict(day_map)
                    for candidate_item, day_map
                    in current_map.items()
                }

                repacked[
                    item_id
                ] = replacement

                candidate = _rebuild(
                    problem,
                    schedule,
                    repacked,
                )

                if candidate is not None:
                    results.append(
                        candidate
                    )

                if len(results) >= 240:
                    return tuple(
                        results
                    )

    return tuple(
        results
    )


def _repair_window_candidates(
    problem: ScheduleProblem,
    schedule: PlannedSchedule,
) -> tuple[PlannedSchedule, ...]:
    """Small deterministic destroy/repair neighbourhood.

    This is the dynamic-work-mass analogue of the useful LNS principle from
    the frozen research pipeline.

    We destroy movable allocations inside short windows and rebuild the same
    conserved task work across that window using deterministic candidate day
    order. Every completed candidate is independently validated.
    """

    if not schedule.work_allocations:
        return ()

    policy = _policy(schedule.flavour)

    first_day = min(
        row.scheduled_date
        for row in schedule.work_allocations
    )

    last_day = max(
        row.scheduled_date
        for row in schedule.work_allocations
    )

    original_hours = _hour_map(schedule)

    results = []

    window_start = first_day

    while window_start <= last_day:
        for width in (3, 4, 5):
            window_end = min(
                last_day,
                window_start + timedelta(days=width - 1),
            )

            movable_ids = set()

            for row in schedule.work_allocations:
                if not (
                    window_start
                    <= row.scheduled_date
                    <= window_end
                ):
                    continue

                item = problem.item_by_id[row.item_id]

                if item.anchor_date is not None:
                    continue

                movable_ids.add(row.item_id)

            if len(movable_ids) < 1:
                continue

            destroyed = {
                item_id: dict(rows)
                for item_id, rows
                in original_hours.items()
            }

            work_to_repair = {}

            for item_id in sorted(movable_ids):
                rows = destroyed[item_id]

                removed = D("0")

                for day in list(rows):
                    if window_start <= day <= window_end:
                        removed += rows.pop(day)

                if removed > 0:
                    work_to_repair[item_id] = removed

            if not work_to_repair:
                continue

            current_daily = defaultdict(
                lambda: D("0")
            )

            for rows in destroyed.values():
                for day, hours in rows.items():
                    current_daily[day] += hours

            for item_id in sorted(
                work_to_repair,
                key=lambda item_id: (
                    problem.item_by_id[item_id].due_date
                    or date.max,
                    problem.item_by_id[item_id].priority_position
                    if problem.item_by_id[item_id].priority_position
                    is not None
                    else 10_000,
                    item_id,
                ),
            ):
                item = problem.item_by_id[item_id]
                remaining = work_to_repair[item_id]

                earliest = max(
                    window_start,
                    problem.today,
                    item.release_date or problem.today,
                )

                latest = window_end

                if item.due_date is not None:
                    latest = min(
                        latest,
                        item.due_date,
                    )

                candidate_days = []

                cursor = earliest

                while cursor <= latest:
                    candidate_days.append(cursor)
                    cursor += timedelta(days=1)

                if schedule.flavour == "lock-in":
                    candidate_days.sort(
                        key=lambda day: (
                            current_daily[day]
                            >= policy.soft_max_daily_hours,
                            day,
                            current_daily[day],
                        )
                    )
                else:
                    candidate_days.sort(
                        key=lambda day: (
                            current_daily[day],
                            day,
                        )
                    )

                for day in candidate_days:
                    if remaining <= 0:
                        break

                    preferred_room = max(
                        D("0"),
                        policy.preferred_daily_hours
                        - current_daily[day],
                    )

                    soft_room = max(
                        D("0"),
                        policy.soft_max_daily_hours
                        - current_daily[day],
                    )

                    if schedule.flavour == "lock-in":
                        target_room = max(
                            preferred_room,
                            min(
                                soft_room,
                                policy.maximum_focused_session_hours,
                            ),
                        )
                    else:
                        target_room = min(
                            policy.maximum_focused_session_hours,
                            max(
                                preferred_room,
                                D("0"),
                            ),
                        )

                    if target_room <= 0:
                        continue

                    amount = min(
                        remaining,
                        target_room,
                        policy.maximum_focused_session_hours,
                    )

                    if (
                        remaining - amount > 0
                        and remaining - amount
                        < policy.minimum_useful_session_hours
                    ):
                        amount = remaining

                    destroyed[item_id][day] = (
                        destroyed[item_id].get(
                            day,
                            D("0"),
                        )
                        + amount
                    )

                    current_daily[day] += amount
                    remaining -= amount

                # If normal placement could not absorb all work, preserve
                # completeness by placing the residue on the latest legal
                # window date. The resulting overload remains visible to the
                # objective/status layer.
                if remaining > 0 and candidate_days:
                    day = candidate_days[-1]

                    destroyed[item_id][day] = (
                        destroyed[item_id].get(
                            day,
                            D("0"),
                        )
                        + remaining
                    )

                    current_daily[day] += remaining
                    remaining = D("0")

                if remaining > 0:
                    destroyed = None
                    break

            if destroyed is None:
                continue

            candidate = _rebuild(
                problem,
                schedule,
                destroyed,
            )

            if candidate is not None:
                results.append(candidate)

        window_start += timedelta(days=1)

    return tuple(results)


def improve_production_schedule(
    problem: ScheduleProblem,
    initial: PlannedSchedule,
    config: ProductionImproveConfig =
        ProductionImproveConfig(),
) -> ProductionImproveResult:
    """Deterministic BEST strict hill climbing over dynamic work-hour moves."""

    initial_validation = (
        validate_dynamic_plan(
            problem,
            initial.plan,
        )
    )

    if initial_validation.violations:
        raise ValueError(
            "Production improver requires "
            "a hard-legal complete plan"
        )

    current = initial

    initial_objective = (
        score_production_schedule(
            problem,
            current,
        )
    )

    current_objective = (
        initial_objective
    )

    accepted = []
    history = [
        current_objective.key
    ]

    iterations = 0
    evaluations = 0

    while True:
        if (
            iterations
            >= config.max_iterations
        ):
            reason = (
                "iteration_budget"
            )
            break

        if (
            evaluations
            >= config.max_evaluations
        ):
            reason = (
                "evaluation_budget"
            )
            break

        iterations += 1

        best_move = None
        best_schedule = None
        best_objective = (
            current_objective
        )

        # --------------------------------------------------------------
        # C11.15.2 deadline-recovery fast path.
        #
        # Actual lateness is the first production objective. While late work
        # exists, search the late task + prerequisite region BEFORE spending
        # evaluations on human-shape polishing or the broad relocation space.
        # --------------------------------------------------------------
        if (
            current_objective.late_hours
            > D("0")
        ):
            recovery_complete = True

            for move in _lateness_recovery_moves(
                problem,
                current,
            ):
                if (
                    evaluations
                    >= config.max_evaluations
                ):
                    recovery_complete = False
                    break

                candidate = _apply_move(
                    problem,
                    current,
                    move,
                )

                if candidate is None:
                    continue

                objective = (
                    score_production_schedule(
                        problem,
                        candidate,
                    )
                )

                evaluations += 1

                if (
                    objective.key
                    < best_objective.key
                ):
                    best_move = move
                    best_schedule = candidate
                    best_objective = objective

            if not recovery_complete:
                reason = (
                    "evaluation_budget"
                )
                break

            if best_move is not None:
                current = best_schedule
                current_objective = (
                    best_objective
                )

                accepted.append(
                    best_move
                )

                history.append(
                    current_objective.key
                )

                continue

        # --------------------------------------------------------------
        # C11.15.5 anchored-congestion recovery fast path.
        #
        # Once actual lateness has been handled, do not waste the remaining
        # search budget polishing unrelated parts of the calendar while
        # movable work is sitting on an overloaded day whose anchored work is
        # unavoidable.
        # --------------------------------------------------------------
        congestion_complete = True
        congestion_move = None
        congestion_schedule = None
        congestion_objective = None

        # C11.15.6:
        #
        # This neighbourhood is already deterministically ranked toward the
        # worst anchored congestion and calmer destinations. Evaluating the
        # entire bounded set before every accepted evacuation wastes a large
        # fraction of the global search budget.
        #
        # Use first STRICT improvement here. The normal lexicographic
        # objective still decides whether the candidate is acceptable.
        for move in _anchored_congestion_recovery_moves(
            problem,
            current,
        ):
            if (
                evaluations
                >= config.max_evaluations
            ):
                congestion_complete = False
                break

            candidate = _apply_move(
                problem,
                current,
                move,
            )

            if candidate is None:
                continue

            objective = (
                score_production_schedule(
                    problem,
                    candidate,
                )
            )

            evaluations += 1

            if (
                objective.key
                < current_objective.key
            ):
                congestion_move = move
                congestion_schedule = candidate
                congestion_objective = objective
                break

        if not congestion_complete:
            reason = "evaluation_budget"
            break

        if congestion_move is not None:
            current = congestion_schedule
            current_objective = congestion_objective

            accepted.append(
                congestion_move
            )

            history.append(
                current_objective.key
            )

            continue

        # --------------------------------------------------------------
        # C11.14e multi-task load-preserving repack.
        #
        # First attempt human-shape repairs that preserve both affected daily
        # totals EXACTLY. This is especially useful when one task has an
        # oversized block but repacking that task alone would create a higher
        # peak.
        # --------------------------------------------------------------
        dedicated_complete = True

        for candidate in (
            _load_preserving_window_repack_candidates(
                problem,
                current,
            )
        ):
            if (
                evaluations
                >= config.max_evaluations
            ):
                dedicated_complete = False
                break

            objective = (
                score_production_schedule(
                    problem,
                    candidate,
                )
            )

            evaluations += 1

            if (
                objective.key
                < best_objective.key
            ):
                best_move = (
                    "load_preserving_window_repack"
                )
                best_schedule = candidate
                best_objective = objective

        if not dedicated_complete:
            reason = (
                "evaluation_budget"
            )
            break

        if best_move is not None:
            current = best_schedule
            current_objective = (
                best_objective
            )

            accepted.append(
                best_move
            )

            history.append(
                current_objective.key
            )

            continue

        # --------------------------------------------------------------
        # C11.14c human block-repack pre-pass.
        #
        # Before scanning thousands of individual relocation moves, ask
        # whether an already-fragmented flexible task can be rebuilt into a
        # smaller number of useful 2-4h-ish blocks on legal low-pressure days.
        #
        # This operator does not impose a fixed block length. It supplies a
        # bounded family of candidate representations and lets the normal
        # lexicographic production objective choose.
        # --------------------------------------------------------------
        dedicated_complete = True

        for candidate in _block_repack_candidates(
            problem,
            current,
        ):
            if (
                evaluations
                >= config.max_evaluations
            ):
                dedicated_complete = False
                break

            objective = (
                score_production_schedule(
                    problem,
                    candidate,
                )
            )

            evaluations += 1

            if (
                objective.key
                < best_objective.key
            ):
                best_move = (
                    "block_repack"
                )
                best_schedule = candidate
                best_objective = (
                    objective
                )

        if not dedicated_complete:
            reason = (
                "evaluation_budget"
            )
            break

        if best_move is not None:
            current = best_schedule
            current_objective = (
                best_objective
            )

            accepted.append(
                best_move
            )

            history.append(
                current_objective.key
            )

            continue

        # --------------------------------------------------------------
        # C11.14b consolidation/exchange pre-pass.
        #
        # Harvest cheap whole-fragment consolidations BEFORE spending the
        # evaluation budget on the broad relocation neighbourhood.
        # --------------------------------------------------------------
        for move in _consolidation_moves(
            problem,
            current,
        ):
            if (
                evaluations
                >= config.max_evaluations
            ):
                dedicated_complete = False
                break

            candidate = _apply_move(
                problem,
                current,
                move,
            )

            if candidate is None:
                continue

            objective = (
                score_production_schedule(
                    problem,
                    candidate,
                )
            )

            evaluations += 1

            if (
                objective.key
                < best_objective.key
            ):
                best_move = move
                best_schedule = candidate
                best_objective = objective

        # If no direct same-task merge works, attempt a load-preserving
        # two-task exchange. This can consolidate a fragmented task without
        # increasing either affected day's total work.
        if (
            dedicated_complete
            and best_move is None
        ):
            for move in _balanced_exchange_moves(
                problem,
                current,
            ):
                if (
                    evaluations
                    >= config.max_evaluations
                ):
                    dedicated_complete = False
                    break

                candidate = (
                    _apply_compound_move(
                        problem,
                        current,
                        move,
                    )
                )

                if candidate is None:
                    continue

                objective = (
                    score_production_schedule(
                        problem,
                        candidate,
                    )
                )

                evaluations += 1

                if (
                    objective.key
                    < best_objective.key
                ):
                    best_move = move
                    best_schedule = candidate
                    best_objective = objective

        if not dedicated_complete:
            reason = (
                "evaluation_budget"
            )
            break

        if best_move is not None:
            current = best_schedule
            current_objective = (
                best_objective
            )

            accepted.append(
                best_move
            )

            history.append(
                current_objective.key
            )

            continue

        moves = _moves(
            problem,
            current,
        )

        complete_scan = True

        for move in moves:
            if (
                evaluations
                >= config.max_evaluations
            ):
                complete_scan = False
                break

            candidate = _apply_move(
                problem,
                current,
                move,
            )

            if candidate is None:
                continue

            objective = (
                score_production_schedule(
                    problem,
                    candidate,
                )
            )

            evaluations += 1

            if (
                objective.key
                < best_objective.key
            ):
                best_move = move
                best_schedule = candidate
                best_objective = (
                    objective
                )

        # If no strict single relocation helps, try a bounded atomic pair
        # neighbourhood. This ports the useful destroy/repair principle from
        # the research pipeline without reintroducing fixed session pieces.
        if (
            complete_scan
            and best_move is None
        ):
            for move in _compound_moves(
                problem,
                current,
                moves,
            ):
                if (
                    evaluations
                    >= config.max_evaluations
                ):
                    complete_scan = False
                    break

                candidate = (
                    _apply_compound_move(
                        problem,
                        current,
                        move,
                    )
                )

                if candidate is None:
                    continue

                objective = (
                    score_production_schedule(
                        problem,
                        candidate,
                    )
                )

                evaluations += 1

                if (
                    objective.key
                    < best_objective.key
                ):
                    best_move = move
                    best_schedule = (
                        candidate
                    )
                    best_objective = (
                        objective
                    )

        # If relocation neighbourhoods cannot improve the schedule, try a
        # bounded short-window destroy/repair pass before declaring a local
        # optimum.
        if (
            complete_scan
            and best_move is None
        ):
            for candidate in _repair_window_candidates(
                problem,
                current,
            ):
                if (
                    evaluations
                    >= config.max_evaluations
                ):
                    complete_scan = False
                    break

                objective = score_production_schedule(
                    problem,
                    candidate,
                )

                evaluations += 1

                if objective.key < best_objective.key:
                    best_move = "destroy_repair"
                    best_schedule = candidate
                    best_objective = objective

        if not complete_scan:
            reason = (
                "evaluation_budget"
            )
            break

        if best_move is None:
            reason = (
                "local_optimum"
            )
            break

        current = best_schedule
        current_objective = (
            best_objective
        )

        accepted.append(
            best_move
        )

        history.append(
            current_objective.key
        )

    return ProductionImproveResult(
        initial_schedule=initial,
        final_schedule=current,
        initial_objective=
            initial_objective,
        final_objective=
            current_objective,
        iterations=iterations,
        evaluations=evaluations,
        accepted_moves=tuple(
            accepted
        ),
        objective_history=tuple(
            history
        ),
        termination_reason=reason,
    )
