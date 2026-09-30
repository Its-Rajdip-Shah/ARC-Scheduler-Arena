"""Independent validation of pure SchedulePlan proposals."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from arc_scheduler.engine.domain import (
    Allocation,
    SchedulePlan,
    ScheduleProblem,
)
from arc_scheduler.focus_order import focus_bucket_key


@dataclass(frozen=True, slots=True, order=True)
class PlanViolation:
    code: str
    item_id: int | None = None
    related_item_id: int | None = None
    scheduled_date: date | None = None


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """Independent classification of a proposed schedule.

    ``violations`` are algorithm-created hard-invalid states.

    ``infeasibilities`` are conflicts already implied by canonical hard
    constraints. An algorithm cannot repair these without violating another
    canonical requirement.

    ``soft_violations`` are permitted ARC scheduling costs such as capacity
    overload or deadline lateness.

    A plan is structurally valid iff it contains no hard violations.
    """

    violations: tuple[PlanViolation, ...]
    infeasibilities: tuple[PlanViolation, ...] = ()
    soft_violations: tuple[PlanViolation, ...] = ()

    @property
    def is_valid(self) -> bool:
        return not self.violations


def validate_plan(
    problem: ScheduleProblem,
    plan: SchedulePlan,
) -> ValidationResult:
    """Validate algorithm output against shared ARC scheduling semantics.

    Dependency precedence is completion-based:

        prerequisite -> dependent

    means ALL proposed prerequisite work must complete before ANY proposed
    dependent work begins.

    Checking every explicit edge is sufficient for arbitrary chains. For
    A -> B -> C, validating A before B and B before C necessarily makes A
    precede C without inventing an explicit A -> C edge.
    """

    item_by_id = problem.item_by_id

    # Algorithm-created hard invalidity.
    violations: set[PlanViolation] = set()

    # Mutually incompatible canonical hard constraints.
    infeasibilities: set[PlanViolation] = set()

    # ARC-permitted scheduling cost / degradation.
    soft_violations: set[PlanViolation] = set()

    allocations_by_item: dict[int, list[Allocation]] = {
        item_id: []
        for item_id in item_by_id
    }

    rank_keys: set[tuple[date, int]] = set()

    for allocation in plan.allocations:
        item = item_by_id.get(allocation.item_id)

        if item is None:
            violations.add(
                PlanViolation(
                    "unknown_item",
                    item_id=allocation.item_id,
                    scheduled_date=allocation.scheduled_date,
                )
            )
            continue

        allocations_by_item[allocation.item_id].append(
            allocation
        )

        rank_key = (
            allocation.scheduled_date,
            allocation.execution_rank,
        )

        if rank_key in rank_keys:
            violations.add(
                PlanViolation(
                    "duplicate_execution_rank",
                    item_id=allocation.item_id,
                    scheduled_date=allocation.scheduled_date,
                )
            )
        rank_keys.add(rank_key)

        if allocation.scheduled_date < problem.today:
            violations.add(
                PlanViolation(
                    "past_date",
                    item_id=item.item_id,
                    scheduled_date=allocation.scheduled_date,
                )
            )

        if (
            item.release_date is not None
            and allocation.scheduled_date < item.release_date
        ):
            violations.add(
                PlanViolation(
                    "before_release",
                    item_id=item.item_id,
                    scheduled_date=allocation.scheduled_date,
                )
            )

        if (
            item.due_date is not None
            and allocation.scheduled_date > item.due_date
        ):
            # ARC production scheduling explicitly permits deadline misses
            # when the legal scheduling window is infeasible. Keep lateness
            # visible for evaluation without making the plan structurally
            # invalid.
            soft_violations.add(
                PlanViolation(
                    "after_deadline",
                    item_id=item.item_id,
                    scheduled_date=allocation.scheduled_date,
                )
            )


    # ARC anchor semantics constrain the first proposed execution date.
    # Splittable work may continue on later dates; those follow-up sessions
    # are not anchor violations.
    for item_id, item in item_by_id.items():
        if item.anchor_date is None:
            continue

        rows = allocations_by_item[item_id]

        if not rows:
            # Missing work is diagnosed by the completeness checks below.
            continue

        first = min(
            rows,
            key=lambda allocation: (
                allocation.scheduled_date,
                allocation.execution_rank,
            ),
        )

        if first.scheduled_date != item.anchor_date:
            violations.add(
                PlanViolation(
                    "anchor_violation",
                    item_id=item_id,
                    scheduled_date=first.scheduled_date,
                )
            )

        if (
            item.anchor_order is not None
            and first.scheduled_date
            == item.anchor_date
        ):
            bucket = focus_bucket_key(
                item.duration_category,
                is_residual=
                    item.is_residual,
            )

            bucket_rows = sorted(
                (
                    allocation
                    for allocation
                    in plan.allocations
                    if (
                        allocation.scheduled_date
                        == item.anchor_date
                        and focus_bucket_key(
                            item_by_id[
                                allocation.item_id
                            ].duration_category,
                            is_residual=
                                item_by_id[
                                    allocation.item_id
                                ].is_residual,
                        )
                        == bucket
                    )
                ),
                key=lambda allocation:
                    allocation.execution_rank,
            )

            local_position = next(
                (
                    index
                    for index, allocation
                    in enumerate(
                        bucket_rows,
                        start=1,
                    )
                    if (
                        allocation.item_id
                        == item_id
                    )
                ),
                None,
            )

            # Exact requested bucket positions are hard whenever that bucket
            # contains enough rows to represent the ordinal. A request beyond
            # the current bucket size degrades to the latest feasible local
            # position rather than manufacturing dummy work.
            if (
                item.anchor_order
                <= len(bucket_rows)
                and local_position
                != item.anchor_order
            ):
                violations.add(
                    PlanViolation(
                        "anchor_order_violation",
                        item_id=item_id,
                        scheduled_date=
                            first.scheduled_date,
                    )
                )

    # Every algorithm-visible unfinished item must receive exactly its
    # remaining work. This prevents algorithms from silently dropping work or
    # manufacturing extra completion.
    for item_id, item in item_by_id.items():
        rows = allocations_by_item[item_id]

        total = sum(
            (
                allocation.percentage
                for allocation in rows
            ),
            Decimal("0"),
        )

        expected = (
            item.remaining_fraction
            * Decimal("100")
        )

        if total != expected:
            violations.add(
                PlanViolation(
                    "allocation_total_mismatch",
                    item_id=item_id,
                )
            )

        if not rows:
            continue

        bucket = (
            "UNDER_20_MINUTES"
            if item.is_residual
            else item.duration_category
        )

        # Atomic ARC duration buckets must remain one-day proposals.
        if bucket in {
            "UNDER_20_MINUTES",
            "UNDER_1_HOUR",
            "UNDER_4_HOURS",
        } and len(rows) != 1:
            violations.add(
                PlanViolation(
                    "atomic_item_split",
                    item_id=item_id,
                )
            )

    # Completion-based dependency precedence.
    for edge in problem.dependencies:
        prerequisite_rows = allocations_by_item[
            edge.prerequisite_id
        ]
        dependent_rows = allocations_by_item[
            edge.dependent_id
        ]

        if not prerequisite_rows or not dependent_rows:
            continue

        prerequisite_completion = max(
            row.scheduled_date
            for row in prerequisite_rows
        )
        dependent_start = min(
            row.scheduled_date
            for row in dependent_rows
        )

        # "cannot become executable until prerequisite is complete":
        # with day-granularity scheduling, dependent work starts strictly
        # after the prerequisite's final scheduled day.
        if dependent_start <= prerequisite_completion:
            prerequisite = item_by_id[
                edge.prerequisite_id
            ]
            dependent = item_by_id[
                edge.dependent_id
            ]

            violation = PlanViolation(
                "dependency_precedence",
                item_id=edge.dependent_id,
                related_item_id=edge.prerequisite_id,
                scheduled_date=dependent_start,
            )

            # An anchored dependent cannot be moved later by an algorithm,
            # and an anchored prerequisite cannot be moved earlier. If either
            # canonical anchor participates in the precedence conflict, the
            # input constraints themselves are infeasible.
            if (
                prerequisite.anchor_date is not None
                or dependent.anchor_date is not None
            ):
                infeasibilities.add(violation)
            else:
                violations.add(violation)

    # Capacity is soft in ARC. We therefore REPORT overload rather than make
    # the plan structurally invalid by hiding it. Allowed overload dates are
    # explicitly exempt.
    usage = Counter()

    for allocation in plan.allocations:
        item = item_by_id.get(allocation.item_id)

        if item is None:
            continue

        bucket = (
            "UNDER_20_MINUTES"
            if item.is_residual
            else item.duration_category
        )

        usage[(allocation.scheduled_date, bucket)] += 1

    for (day, bucket), count in usage.items():
        limit = problem.capacity_by_duration.get(bucket)

        if (
            limit is not None
            and count > limit
            and day not in problem.overload_dates
        ):
            soft_violations.add(
                PlanViolation(
                    "capacity_exceeded",
                    scheduled_date=day,
                )
            )

    return ValidationResult(
        violations=tuple(sorted(violations)),
        infeasibilities=tuple(sorted(infeasibilities)),
        soft_violations=tuple(sorted(soft_violations)),
    )


def is_plan_hard_valid(
    problem: ScheduleProblem,
    plan: SchedulePlan,
) -> bool:
    """Fast boolean check for hard-invalid candidate states only."""

    item_by_id = problem.item_by_id

    allocations_by_item = {
        item_id: []
        for item_id in item_by_id
    }

    percentage_by_item = {
        item_id: Decimal("0")
        for item_id in item_by_id
    }

    first_by_item = {}
    start_date_by_item = {}
    completion_date_by_item = {}
    bucket_rows = {}
    rank_keys = set()

    for allocation in plan.allocations:
        item = item_by_id.get(
            allocation.item_id
        )

        if item is None:
            return False

        rank_key = (
            allocation.scheduled_date,
            allocation.execution_rank,
        )

        if rank_key in rank_keys:
            return False

        rank_keys.add(rank_key)

        if allocation.scheduled_date < problem.today:
            return False

        if (
            item.release_date is not None
            and allocation.scheduled_date
            < item.release_date
        ):
            return False

        item_id = allocation.item_id

        allocations_by_item[
            item_id
        ].append(allocation)

        percentage_by_item[
            item_id
        ] += allocation.percentage

        previous_first = first_by_item.get(
            item_id
        )

        if (
            previous_first is None
            or (
                allocation.scheduled_date,
                allocation.execution_rank,
            )
            < (
                previous_first.scheduled_date,
                previous_first.execution_rank,
            )
        ):
            first_by_item[
                item_id
            ] = allocation

        previous_start = start_date_by_item.get(
            item_id
        )

        if (
            previous_start is None
            or allocation.scheduled_date
            < previous_start
        ):
            start_date_by_item[
                item_id
            ] = allocation.scheduled_date

        previous_completion = (
            completion_date_by_item.get(
                item_id
            )
        )

        if (
            previous_completion is None
            or allocation.scheduled_date
            > previous_completion
        ):
            completion_date_by_item[
                item_id
            ] = allocation.scheduled_date

        focus_bucket = focus_bucket_key(
            item.duration_category,
            is_residual=item.is_residual,
        )

        bucket_rows.setdefault(
            (
                allocation.scheduled_date,
                focus_bucket,
            ),
            [],
        ).append(allocation)

    for item_id, item in item_by_id.items():
        rows = allocations_by_item[
            item_id
        ]

        if (
            percentage_by_item[item_id]
            != item.remaining_fraction
            * Decimal("100")
        ):
            return False

        if rows:
            bucket = (
                "UNDER_20_MINUTES"
                if item.is_residual
                else item.duration_category
            )

            if (
                bucket
                in {
                    "UNDER_20_MINUTES",
                    "UNDER_1_HOUR",
                    "UNDER_4_HOURS",
                }
                and len(rows) != 1
            ):
                return False

        if (
            item.anchor_date is None
            or not rows
        ):
            continue

        first = first_by_item[
            item_id
        ]

        if (
            first.scheduled_date
            != item.anchor_date
        ):
            return False

        if item.anchor_order is None:
            continue

        focus_bucket = focus_bucket_key(
            item.duration_category,
            is_residual=item.is_residual,
        )

        ordered_bucket = sorted(
            bucket_rows.get(
                (
                    item.anchor_date,
                    focus_bucket,
                ),
                (),
            ),
            key=lambda row:
                row.execution_rank,
        )

        local_position = next(
            (
                index
                for index, row
                in enumerate(
                    ordered_bucket,
                    start=1,
                )
                if row.item_id
                == item_id
            ),
            None,
        )

        if (
            item.anchor_order
            <= len(ordered_bucket)
            and local_position
            != item.anchor_order
        ):
            return False

    for edge in problem.dependencies:
        prerequisite_completion = (
            completion_date_by_item.get(
                edge.prerequisite_id
            )
        )

        dependent_start = (
            start_date_by_item.get(
                edge.dependent_id
            )
        )

        if (
            prerequisite_completion is None
            or dependent_start is None
            or dependent_start
            > prerequisite_completion
        ):
            continue

        prerequisite = item_by_id[
            edge.prerequisite_id
        ]

        dependent = item_by_id[
            edge.dependent_id
        ]

        if (
            prerequisite.anchor_date is None
            and dependent.anchor_date is None
        ):
            return False

    return True


def is_plan_hard_valid_incremental(
    problem: ScheduleProblem,
    original_plan: SchedulePlan,
    plan: SchedulePlan,
    *,
    changed_item_ids: frozenset[int],
    changed_dates: frozenset[date],
) -> bool:
    """Validate only hard constraints a local production move can change."""

    if not changed_item_ids:
        return is_plan_hard_valid(
            problem,
            plan,
        )

    item_by_id = problem.item_by_id

    tracked_item_ids = set(
        changed_item_ids
    )

    for item_id in changed_item_ids:
        tracked_item_ids.update(
            problem.direct_prerequisites(
                item_id
            )
        )
        tracked_item_ids.update(
            problem.direct_dependents(
                item_id
            )
        )

    changed_rows = {
        item_id: []
        for item_id in changed_item_ids
    }

    percentage_by_changed_item = {
        item_id: Decimal("0")
        for item_id in changed_item_ids
    }

    first_by_changed_item = {}

    start_date_by_tracked_item = {}
    completion_date_by_tracked_item = {}

    rows_by_changed_date_and_bucket = {}

    rank_keys_on_changed_dates = set()

    for allocation in plan.allocations:
        item = item_by_id.get(
            allocation.item_id
        )

        if item is None:
            return False

        item_id = allocation.item_id
        day = allocation.scheduled_date

        if day in changed_dates:
            rank_key = (
                day,
                allocation.execution_rank,
            )

            if (
                rank_key
                in rank_keys_on_changed_dates
            ):
                return False

            rank_keys_on_changed_dates.add(
                rank_key
            )

            focus_bucket = focus_bucket_key(
                item.duration_category,
                is_residual=item.is_residual,
            )

            rows_by_changed_date_and_bucket.setdefault(
                (
                    day,
                    focus_bucket,
                ),
                [],
            ).append(
                allocation
            )

        if item_id in tracked_item_ids:
            previous_start = (
                start_date_by_tracked_item.get(
                    item_id
                )
            )

            if (
                previous_start is None
                or day < previous_start
            ):
                start_date_by_tracked_item[
                    item_id
                ] = day

            previous_completion = (
                completion_date_by_tracked_item.get(
                    item_id
                )
            )

            if (
                previous_completion is None
                or day > previous_completion
            ):
                completion_date_by_tracked_item[
                    item_id
                ] = day

        if item_id not in changed_item_ids:
            continue

        if day < problem.today:
            return False

        if (
            item.release_date is not None
            and day < item.release_date
        ):
            return False

        changed_rows[
            item_id
        ].append(
            allocation
        )

        percentage_by_changed_item[
            item_id
        ] += allocation.percentage

        previous_first = (
            first_by_changed_item.get(
                item_id
            )
        )

        if (
            previous_first is None
            or (
                day,
                allocation.execution_rank,
            )
            < (
                previous_first.scheduled_date,
                previous_first.execution_rank,
            )
        ):
            first_by_changed_item[
                item_id
            ] = allocation

    for item_id in changed_item_ids:
        item = item_by_id[
            item_id
        ]

        rows = changed_rows[
            item_id
        ]

        if (
            percentage_by_changed_item[
                item_id
            ]
            != item.remaining_fraction
            * Decimal("100")
        ):
            return False

        if rows:
            bucket = (
                "UNDER_20_MINUTES"
                if item.is_residual
                else item.duration_category
            )

            if (
                bucket
                in {
                    "UNDER_20_MINUTES",
                    "UNDER_1_HOUR",
                    "UNDER_4_HOURS",
                }
                and len(rows) != 1
            ):
                return False

        if (
            item.anchor_date is not None
            and rows
            and first_by_changed_item[
                item_id
            ].scheduled_date
            != item.anchor_date
        ):
            return False

    for item in problem.items:
        if (
            item.anchor_date is None
            or item.anchor_order is None
            or item.anchor_date
            not in changed_dates
        ):
            continue

        focus_bucket = focus_bucket_key(
            item.duration_category,
            is_residual=item.is_residual,
        )

        ordered_bucket = sorted(
            rows_by_changed_date_and_bucket.get(
                (
                    item.anchor_date,
                    focus_bucket,
                ),
                (),
            ),
            key=lambda row:
                row.execution_rank,
        )

        local_position = next(
            (
                index
                for index, row
                in enumerate(
                    ordered_bucket,
                    start=1,
                )
                if row.item_id
                == item.item_id
            ),
            None,
        )

        if (
            item.anchor_order
            <= len(ordered_bucket)
            and local_position
            != item.anchor_order
        ):
            return False

    for edge in problem.dependencies:
        if (
            edge.prerequisite_id
            not in changed_item_ids
            and edge.dependent_id
            not in changed_item_ids
        ):
            continue

        prerequisite_completion = (
            completion_date_by_tracked_item.get(
                edge.prerequisite_id
            )
        )

        dependent_start = (
            start_date_by_tracked_item.get(
                edge.dependent_id
            )
        )

        if (
            prerequisite_completion is None
            or dependent_start is None
            or dependent_start
            > prerequisite_completion
        ):
            continue

        prerequisite = item_by_id[
            edge.prerequisite_id
        ]

        dependent = item_by_id[
            edge.dependent_id
        ]

        if (
            prerequisite.anchor_date is None
            and dependent.anchor_date is None
        ):
            return False

    return True
