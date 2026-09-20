"""Canonical hard-precedence dependency graph operations."""

from django.core.exceptions import ValidationError
from django.db import transaction

from planning.models import PlanningDependency, PlanningItem


def _validate_endpoint(item):
    if not isinstance(item, PlanningItem) or item.pk is None:
        raise ValidationError("Dependency endpoints must be persisted PlanningItems.")
    if item.is_deleted:
        raise ValidationError("Deleted work cannot participate in a new dependency.")


def _would_create_cycle(prerequisite, dependent):
    """Return True if dependent already reaches prerequisite."""
    target = prerequisite.pk
    frontier = [dependent.pk]
    visited = set()

    while frontier:
        current = frontier.pop()

        if current == target:
            return True

        if current in visited:
            continue

        visited.add(current)

        frontier.extend(
            PlanningDependency.objects.filter(
                prerequisite_id=current
            ).values_list("dependent_id", flat=True)
        )

    return False


@transaction.atomic
def add(prerequisite: PlanningItem, dependent: PlanningItem):
    """Create prerequisite -> dependent atomically."""
    _validate_endpoint(prerequisite)
    _validate_endpoint(dependent)

    # Lock both endpoints so concurrent graph edits cannot race validation.
    locked = {
        item.pk: item
        for item in PlanningItem.objects.select_for_update().filter(
            pk__in=[prerequisite.pk, dependent.pk]
        )
    }
    prerequisite = locked[prerequisite.pk]
    dependent = locked[dependent.pk]

    if prerequisite.pk == dependent.pk:
        raise ValidationError("A task cannot depend on itself.")

    if prerequisite.user_id != dependent.user_id:
        raise ValidationError("Dependencies cannot cross users.")

    existing = PlanningDependency.objects.filter(
        prerequisite=prerequisite,
        dependent=dependent,
    ).first()

    if existing:
        return existing

    if _would_create_cycle(prerequisite, dependent):
        raise ValidationError("This dependency would create a cycle.")

    return PlanningDependency.objects.create(
        prerequisite=prerequisite,
        dependent=dependent,
    )


add_dependency = add
create_dependency = add


@transaction.atomic
def remove(prerequisite: PlanningItem, dependent: PlanningItem):
    """Explicitly remove one hard-precedence edge."""
    if prerequisite.user_id != dependent.user_id:
        raise ValidationError("Dependencies cannot cross users.")

    deleted, _ = PlanningDependency.objects.filter(
        prerequisite=prerequisite,
        dependent=dependent,
    ).delete()

    return bool(deleted)


remove_dependency = remove
delete_dependency = remove


def prerequisites_for(item):
    return PlanningItem.objects.filter(
        required_by_dependencies__dependent=item,
    ).distinct()


def dependants_for(item):
    return PlanningItem.objects.filter(
        blocked_by_dependencies__prerequisite=item,
    ).distinct()


def is_blocked(item):
    return PlanningDependency.objects.filter(
        dependent=item,
        prerequisite__is_completed=False,
        prerequisite__is_deleted=False,
    ).exists()
