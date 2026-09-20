"""Canonical duration/progress operations for ARC splittable work."""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from planning.models import (
    ATOMIC_DURATION_CATEGORIES,
    SPLITTABLE_DURATION_CATEGORIES,
    PlanningItem,
    ProgressSegment,
    SchedulerAllocation,
)


def _decimal(value):
    return Decimal(str(value))


@transaction.atomic
def set_duration(item: PlanningItem, category: str):
    """Change duration category while preserving frozen progress semantics.

    splittable -> splittable:
        preserve percent completed.

    splittable -> atomic:
        discard partial-progress semantics. If the task was not already fully
        complete, it becomes an ordinary incomplete atomic task.

    atomic -> splittable:
        start unfinished splittable progress at zero; discarded historical
        partial progress is never resurrected.
    """
    if category not in {
        *(str(v) for v in ATOMIC_DURATION_CATEGORIES),
        *(str(v) for v in SPLITTABLE_DURATION_CATEGORIES),
    }:
        # TextChoices values compare as strings, but make the validation
        # explicit so invalid categories cannot enter canonical state.
        valid = {
            v.value if hasattr(v, "value") else str(v)
            for v in (*ATOMIC_DURATION_CATEGORIES, *SPLITTABLE_DURATION_CATEGORIES)
        }
        if category not in valid:
            raise ValidationError({"duration_category": "Unknown ARC duration category."})

    old = item.duration_category

    atomic_values = {str(v) for v in ATOMIC_DURATION_CATEGORIES}
    splittable_values = {str(v) for v in SPLITTABLE_DURATION_CATEGORIES}

    # TextChoices members stringify to their stored value in Django.
    was_split = old in splittable_values
    becomes_atomic = category in atomic_values
    was_atomic = old in atomic_values
    becomes_split = category in splittable_values

    item.duration_category = category
    update_fields = ["duration_category"]

    if was_split and becomes_atomic:
        if not item.is_completed:
            item.percent_completed = Decimal("0")
            update_fields.append("percent_completed")

        # Old progress segments no longer carry active partial scheduling
        # semantics once the canonical task becomes atomic.
        ProgressSegment.objects.filter(item=item).delete()

    elif was_atomic and becomes_split and not item.is_completed:
        item.percent_completed = Decimal("0")
        update_fields.append("percent_completed")
        ProgressSegment.objects.filter(item=item).delete()

    item.save(update_fields=update_fields)
    return item


change_duration = set_duration
edit_duration_category = set_duration


@transaction.atomic
def complete_segment(segment):
    """Confirm one allocation/segment as durable canonical progress.

    SchedulerAllocation is disposable proposal state. Confirmation creates a
    ProgressSegment with durable identity before canonical progress changes.

    Passing an existing ProgressSegment remains supported for compatibility.
    """

    if isinstance(segment, SchedulerAllocation):
        allocation = (
            SchedulerAllocation.objects
            .select_for_update()
            .select_related("item")
            .get(pk=segment.pk)
        )

        item = (
            PlanningItem.objects
            .select_for_update()
            .get(pk=allocation.item_id)
        )

        if item.duration_category not in {
            str(v) for v in SPLITTABLE_DURATION_CATEGORIES
        }:
            raise ValidationError(
                "Atomic work cannot confirm partial allocations."
            )

        remaining = Decimal("100") - _decimal(item.percent_completed)
        amount = min(_decimal(allocation.percentage), remaining)

        if amount <= 0:
            allocation.delete()
            return None

        canonical = ProgressSegment.objects.create(
            item=item,
            percentage=amount,
            scheduled_date=allocation.scheduled_date,
            is_completed=True,
            completed_at=timezone.now(),
        )

        item.percent_completed = min(
            Decimal("100"),
            _decimal(item.percent_completed) + amount,
        )

        if item.percent_completed >= Decimal("100"):
            item.percent_completed = Decimal("100")
            item.is_completed = True
            item.save(
                update_fields=[
                    "percent_completed",
                    "is_completed",
                ]
            )
        else:
            item.save(update_fields=["percent_completed"])

        # This proposal has now crossed the authority boundary and has been
        # replaced by canonical progress history.
        allocation.delete()

        return canonical

    segment = (
        ProgressSegment.objects
        .select_for_update()
        .select_related("item")
        .get(pk=segment.pk)
    )

    item = (
        PlanningItem.objects
        .select_for_update()
        .get(pk=segment.item_id)
    )

    if segment.is_completed:
        return segment

    if item.duration_category not in {
        str(v) for v in SPLITTABLE_DURATION_CATEGORIES
    }:
        raise ValidationError(
            "Atomic work cannot confirm partial progress segments."
        )

    remaining = Decimal("100") - _decimal(item.percent_completed)
    amount = min(_decimal(segment.percentage), remaining)

    segment.percentage = amount
    segment.is_completed = True
    segment.completed_at = timezone.now()
    segment.save(
        update_fields=[
            "percentage",
            "is_completed",
            "completed_at",
        ]
    )

    item.percent_completed = min(
        Decimal("100"),
        _decimal(item.percent_completed) + amount,
    )

    if item.percent_completed >= Decimal("100"):
        item.percent_completed = Decimal("100")
        item.is_completed = True
        item.save(
            update_fields=[
                "percent_completed",
                "is_completed",
            ]
        )
    else:
        item.save(update_fields=["percent_completed"])

    return segment


complete_allocation = complete_segment
confirm_progress = complete_segment
record_completed_allocation = complete_segment


@transaction.atomic
def reopen_segment(segment: ProgressSegment):
    """Reverse exactly one confirmed segment without disturbing the others."""
    segment = ProgressSegment.objects.select_for_update().select_related("item").get(
        pk=segment.pk
    )
    item = PlanningItem.objects.select_for_update().get(pk=segment.item_id)

    if not segment.is_completed:
        return segment

    item.percent_completed = max(
        Decimal("0"),
        _decimal(item.percent_completed) - _decimal(segment.percentage),
    )
    item.is_completed = False
    item.save(update_fields=["percent_completed", "is_completed"])

    segment.is_completed = False
    segment.completed_at = None
    segment.save(update_fields=["is_completed", "completed_at"])

    return segment


uncomplete_segment = reopen_segment
reverse_progress_segment = reopen_segment


@transaction.atomic
def reconcile_progress(subject):
    """Reconcile 100%-progress state for one item or a user's items."""
    if isinstance(subject, PlanningItem):
        items = [subject]
    else:
        items = list(PlanningItem.objects.filter(user=subject))

    changed = []

    for item in items:
        should_complete = (
            item.duration_category in {str(v) for v in SPLITTABLE_DURATION_CATEGORIES}
            and _decimal(item.percent_completed) >= Decimal("100")
        )

        if should_complete and not item.is_completed:
            item.percent_completed = Decimal("100")
            item.is_completed = True
            item.save(update_fields=["percent_completed", "is_completed"])
            changed.append(item.pk)

    return changed


reconcile = reconcile_progress
