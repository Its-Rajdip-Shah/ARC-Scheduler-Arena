"""A0 — current ARC production scheduler, unchanged."""

from planning.models import PlanningItem
from planning.services.scheduling import reschedule


NAME = "A0 — Current ARC Scheduler"


def run(user, today):
    anchored_before = {
        item.id: item.manual_requested_date
        for item in PlanningItem.objects.filter(
            user=user,
            manual_requested_date__isnull=False,
            is_deleted=False,
        )
    }

    completed_before = {
        item.id: item.scheduled_date
        for item in PlanningItem.objects.filter(
            user=user,
            is_completed=True,
            is_deleted=False,
        )
    }

    result = reschedule(user, today=today)

    return {
        "algorithm": NAME,
        "anchored_before": anchored_before,
        "completed_before": completed_before,
        "arc_result": result,
    }
