"""ARC canonical persistence -> pure ScheduleProblem adapter."""

from __future__ import annotations

from decimal import Decimal

from django.db.models import Exists, OuterRef

from planning.models import (
    PlanningDependency,
    PlanningItem,
    SchedulingOverload,
)
from planning.services.scheduling import capacities

from arena.scheduling.domain import (
    DependencyEdge,
    ScheduleItem,
    ScheduleProblem,
)


def problem_from_user(user, today) -> ScheduleProblem:
    """Snapshot canonical ARC scheduling input without mutation.

    The laboratory needs the complete future-schedulable population,
    not merely work executable today.

    ARC's production ``_scheduler_eligible()`` intentionally excludes work
    blocked by incomplete prerequisites. That is correct for production's
    "what can execute now?" question, but would erase downstream nodes from
    an algorithm constructing a future plan.

    We therefore preserve ARC's structural/actionable/lifecycle frontier
    semantics while deliberately NOT applying dependency blocking here.
    Explicit dependency edges are passed into ScheduleProblem instead, where
    algorithms and the shared validator enforce future precedence.
    """

    unfinished_children = PlanningItem.objects.visible().filter(
        user=user,
        parent_id=OuterRef("pk"),
        is_completed=False,
    )

    visible_children = PlanningItem.objects.visible().filter(
        user=user,
        parent_id=OuterRef("pk"),
    )

    schedulable = list(
        PlanningItem.objects.for_user(user)
        .actionable()
        .filter(
            is_completed=False,
            is_deleted=False,
        )
        .annotate(
            has_unfinished_children=Exists(
                unfinished_children
            ),
            is_residual=Exists(
                visible_children
            ),
        )
        .filter(has_unfinished_children=False)
        .distinct()
        .order_by("pk")
    )

    item_ids = {
        item.pk
        for item in schedulable
    }

    items = tuple(
        ScheduleItem(
            item_id=item.pk,
            duration_category=item.duration_category,
            priority_position=item.priority_position,
            existing_scheduled_date=item.scheduled_date,
            release_date=item.start_date,
            due_date=item.due_date,
            anchor_date=(
                item.manual_requested_date
                if (
                    item.manual_requested_date is not None
                    and item.manual_requested_date >= today
                )
                else None
            ),
            percent_completed=Decimal(
                str(item.percent_completed)
            ),
            remaining_fraction=(
                Decimal("1")
                - (
                    Decimal(str(item.percent_completed))
                    / Decimal("100")
                )
            ),
            is_residual=bool(
                getattr(item, "is_residual", False)
            ),
        )
        for item in schedulable
    )

    # Preserve explicit graph structure among the items visible to the
    # algorithm. No transitive edges are invented.
    dependencies = tuple(
        DependencyEdge(
            prerequisite_id=prerequisite_id,
            dependent_id=dependent_id,
        )
        for prerequisite_id, dependent_id
        in PlanningDependency.objects.filter(
            prerequisite_id__in=item_ids,
            dependent_id__in=item_ids,
        )
        .order_by(
            "prerequisite_id",
            "dependent_id",
        )
        .values_list(
            "prerequisite_id",
            "dependent_id",
        )
    )

    overload_dates = frozenset(
        SchedulingOverload.objects.filter(
            user=user,
            allowed=True,
        ).values_list(
            "date",
            flat=True,
        )
    )

    return ScheduleProblem(
        today=today,
        items=items,
        dependencies=dependencies,
        capacity_by_duration={
            str(key): value
            for key, value in capacities(user).items()
        },
        overload_dates=overload_dates,
    )
