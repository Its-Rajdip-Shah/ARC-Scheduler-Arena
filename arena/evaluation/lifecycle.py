"""Dynamic scheduling lifecycle checks for ARC Scheduler Arena."""

from __future__ import annotations

from dataclasses import dataclass

from planning.models import PlanningItem

from arena.evaluation.invariants import execution_frontier, validate_schedule


@dataclass(frozen=True)
class ScheduleSnapshot:
    scheduled: tuple[tuple[int, object], ...]
    frontier: tuple[int, ...]


def snapshot(user) -> ScheduleSnapshot:
    scheduled = tuple(
        PlanningItem.objects.filter(
            user=user,
            is_deleted=False,
            is_completed=False,
            scheduled_date__isnull=False,
        )
        .order_by("id")
        .values_list("id", "scheduled_date")
    )

    frontier = tuple(
        sorted(item.id for item in execution_frontier(user))
    )

    return ScheduleSnapshot(
        scheduled=scheduled,
        frontier=frontier,
    )


def schedule_map(user):
    return dict(
        PlanningItem.objects.filter(
            user=user,
            is_deleted=False,
            is_completed=False,
        ).values_list("id", "scheduled_date")
    )


def movement_count(before, after):
    keys = set(before) & set(after)
    return sum(before[k] != after[k] for k in keys)


def validate_transition(
    user,
    *,
    today,
    anchored_before,
    completed_before,
):
    return validate_schedule(
        user,
        benchmark_today=today,
        anchored_before=anchored_before,
        completed_before=completed_before,
    )
