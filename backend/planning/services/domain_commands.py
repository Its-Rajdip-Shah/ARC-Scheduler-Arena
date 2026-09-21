"""Canonical creation and compound edit boundary for API and integrations."""
from django.core.exceptions import ValidationError
from django.db import transaction
from planning.models import PlanningItem, DurationCategory, ItemType
from planning.services import hierarchy, lifecycle, progress

EDITABLE = {'title', 'description', 'item_type', 'parent', 'sibling_order',
            'start_date', 'due_date', 'duration_category', 'is_completed'}


def _resolve_parent(user, value):
    if value is None:
        return None
    pk = value.pk if isinstance(value, PlanningItem) else value
    parent = PlanningItem.objects.filter(pk=pk, user=user, is_deleted=False).first()
    if parent is None:
        raise ValidationError('Parent must be active and belong to this user.')
    return parent


def validate_changes(item, changes):
    unknown = set(changes) - EDITABLE
    if unknown:
        raise ValidationError({'fields': f'Fields require a specialised command: {sorted(unknown)}'})
    parent = _resolve_parent(item.user, changes.get('parent', item.parent_id))
    hierarchy.validate_parent(item, parent)
    start = changes.get('start_date', item.start_date)
    due = changes.get('due_date', item.due_date)
    if start and due and start > due:
        raise ValidationError('Release cannot follow deadline.')
    anchor = item.manual_requested_date
    if anchor and (item.pk is None or {"start_date", "due_date"} & set(changes)) and ((start and anchor < start) or (due and anchor > due)):
        raise ValidationError('Resolve the anchor before changing its temporal constraints.')
    if changes.get('duration_category', item.duration_category) not in DurationCategory.values:
        raise ValidationError('Unknown duration category.')
    if changes.get('item_type', item.item_type) not in ItemType.values:
        raise ValidationError('Unknown item type.')
    if changes.get('sibling_order', item.sibling_order) < 1:
        raise ValidationError('Sibling order must be positive.')


@transaction.atomic
def create_item(user, **values):
    from planning.services import priority
    priority._lock(user)
    if set(values) - EDITABLE:
        raise ValidationError("Creation accepts only user-editable task facts.")
    parent = _resolve_parent(user, values.pop('parent', None))
    completed = values.pop('is_completed', False)
    if parent:
        values.setdefault('start_date', parent.start_date)
        values.setdefault('due_date', parent.due_date)
    values.setdefault('sibling_order', hierarchy._next_sibling_order(user, parent))
    item = PlanningItem(user=user, parent=parent, **values)
    if parent:
        item.manual_requested_date = parent.manual_requested_date
    validate_changes(item, {})
    item.save()
    if not completed:
        lifecycle.reopen_ancestors(item)
    else:
        hierarchy.complete_subtree(item, reconcile=False)
    lifecycle.finish(user)
    item.refresh_from_db()
    return item


@transaction.atomic
def update_item(item, changes):
    item = lifecycle.active(item)
    changes = dict(changes)
    planning_changed = bool(set(changes) - {"title", "description"})
    validate_changes(item, changes)
    old_parent = item.parent
    parent = changes.pop('parent', item.parent)
    parent = _resolve_parent(item.user, parent)
    completed = changes.pop('is_completed', item.is_completed)
    duration = changes.pop('duration_category', item.duration_category)
    position = changes.pop("sibling_order", None)
    item.parent = parent
    for key, value in changes.items():
        setattr(item, key, value)
    item.save()
    if duration != item.duration_category:
        progress.set_duration(item, duration, reconcile=False)
    if old_parent != parent:
        hierarchy.reindex_siblings(item.user, old_parent)
        hierarchy.reindex_siblings(item.user, parent)
    if position is not None:
        item = hierarchy.set_sibling_order(item, position)
    if completed != item.is_completed:
        if completed:
            hierarchy.complete_subtree(item, reconcile=False)
        else:
            hierarchy.reopen(item, reconcile=False)
    if not completed:
        lifecycle.reopen_ancestors(item)
    if planning_changed:
        lifecycle.finish(item.user)
    item.refresh_from_db()
    return item


edit_item = mutate_item = apply_changes = update_item
