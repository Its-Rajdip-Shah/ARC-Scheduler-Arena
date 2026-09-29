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
            day_count = sum(
                1
                for allocation
                in plan.allocations
                if (
                    allocation.scheduled_date
                    == item.anchor_date
                )
            )

            # Exact requested slots are hard whenever the day contains
            # enough rows to represent them. A request beyond the current
            # row count degrades to the latest feasible slot rather than
            # inventing dummy work merely to satisfy an ordinal number.
            if (
                item.anchor_order
                <= day_count
                and first.execution_rank
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
