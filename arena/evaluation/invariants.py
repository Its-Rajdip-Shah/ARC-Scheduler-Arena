"""Hard-invariant validation shared by every Arena scheduler."""

from __future__ import annotations

from dataclasses import dataclass

from planning.models import PlanningItem


@dataclass(frozen=True)
class Violation:
    kind: str
    item_id: int
    title: str
    detail: str


def actionable_items(user):
    return PlanningItem.objects.filter(
        user=user,
        is_deleted=False,
        is_completed=False,
        item_type__in=("TASK", "ASSIGNMENT"),
    )


def execution_frontier(user):
    """Incomplete actionable items with no incomplete visible children."""
    candidates = actionable_items(user).prefetch_related("children")

    return [
        item
        for item in candidates
        if not item.children.filter(
            is_deleted=False,
            is_completed=False,
        ).exists()
    ]


def validate_schedule(
    user,
    *,
    benchmark_today,
    anchored_before=None,
    completed_before=None,
):
    violations: list[Violation] = []
    frontier_ids = {item.id for item in execution_frontier(user)}

    scheduled = PlanningItem.objects.filter(
        user=user,
        is_deleted=False,
        is_completed=False,
        scheduled_date__isnull=False,
    )

    for item in scheduled:
        if item.item_type not in ("TASK", "ASSIGNMENT"):
            violations.append(
                Violation(
                    "non_actionable_scheduled",
                    item.id,
                    item.title,
                    f"{item.item_type} scheduled on {item.scheduled_date}",
                )
            )
            continue

        if item.id not in frontier_ids:
            violations.append(
                Violation(
                    "non_frontier_scheduled",
                    item.id,
                    item.title,
                    "item has unfinished child work",
                )
            )

        if not item.schedule_is_manual and item.scheduled_date < benchmark_today:
            violations.append(
                Violation(
                    "scheduled_in_past",
                    item.id,
                    item.title,
                    f"{item.scheduled_date} < benchmark today {benchmark_today}",
                )
            )

        if item.start_date and item.scheduled_date < item.start_date:
            violations.append(
                Violation(
                    "before_release",
                    item.id,
                    item.title,
                    f"{item.scheduled_date} < release {item.start_date}",
                )
            )

        if item.due_date and item.scheduled_date > item.due_date:
            violations.append(
                Violation(
                    "after_deadline",
                    item.id,
                    item.title,
                    f"{item.scheduled_date} > deadline {item.due_date}",
                )
            )

    current = {
        item.id: item
        for item in PlanningItem.objects.filter(user=user)
    }

    for item_id, original_date in (anchored_before or {}).items():
        item = current.get(item_id)
        if item is None or item.scheduled_date != original_date:
            violations.append(
                Violation(
                    "anchor_moved",
                    item_id,
                    item.title if item else "<missing>",
                    f"{original_date} -> "
                    f"{item.scheduled_date if item else '<missing>'}",
                )
            )

    for item_id, original_date in (completed_before or {}).items():
        item = current.get(item_id)
        if item is None or item.scheduled_date != original_date:
            violations.append(
                Violation(
                    "completed_item_changed",
                    item_id,
                    item.title if item else "<missing>",
                    f"{original_date} -> "
                    f"{item.scheduled_date if item else '<missing>'}",
                )
            )

    return violations
