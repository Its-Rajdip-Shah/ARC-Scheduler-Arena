"""Canonical ARC domain-command boundary.

All compound canonical-state mutations belong behind this boundary.
Commands validate the prospective final state before committing and execute
inside one database transaction.
"""

from __future__ import annotations

from collections.abc import Mapping

from django.core.exceptions import ValidationError
from django.db import transaction

from planning.models import PlanningItem
from planning.services import hierarchy, priority


def _resolve_parent(user, value):
    if value is None or isinstance(value, PlanningItem):
        return value

    return PlanningItem.objects.get(
        pk=value,
        user=user,
        is_deleted=False,
    )


def validate_changes(
    item: PlanningItem,
    changes: Mapping,
) -> None:
    """Validate the prospective final state without mutating canonical state."""

    field_names = {
        field.name
        for field in PlanningItem._meta.get_fields()
        if getattr(field, "concrete", False)
    }

    unknown = set(changes) - field_names
    if unknown:
        raise ValidationError(
            {
                "fields": (
                    "Unknown PlanningItem fields: "
                    f"{sorted(unknown)}"
                )
            }
        )

    if "parent" in changes:
        new_parent = _resolve_parent(
            item.user,
            changes["parent"],
        )
        hierarchy.validate_parent(item, new_parent)

    percent = changes.get(
        "percent_completed",
        item.percent_completed,
    )

    if percent is not None and not 0 <= percent <= 100:
        raise ValidationError(
            {
                "percent_completed":
                    "Progress must be between 0 and 100."
            }
        )


@transaction.atomic
def update_item(
    item: PlanningItem,
    changes: Mapping,
) -> PlanningItem:
    """Apply one compound edit atomically.

    Validation occurs against the intended final mutation before any canonical
    field is written. A validation failure therefore leaves the original
    canonical state untouched.
    """

    locked = (
        PlanningItem.objects
        .select_for_update()
        .get(
            pk=item.pk,
            user=item.user,
        )
    )

    validate_changes(locked, changes)

    update_fields = []

    for name, value in changes.items():
        if name == "parent":
            value = _resolve_parent(
                locked.user,
                value,
            )

        setattr(locked, name, value)
        update_fields.append(name)

    if update_fields:
        locked.save(update_fields=update_fields)

    # Canonical priority reconciliation is part of the domain transition,
    # rather than something a projection/scheduler should silently repair.
    priority.reconcile(locked.user)

    locked.refresh_from_db()
    return locked


# Stable semantic aliases. These let callers depend on the command boundary
# rather than a particular UI/API vocabulary.
edit_item = update_item
mutate_item = update_item
apply_changes = update_item
