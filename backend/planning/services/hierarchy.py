"""Structure of the planning tree: re-parenting and cascade completion.

Covers FR-06 (an item may never become its own ancestor) and FR-08 (completing
a parent completes everything beneath it).
"""

from django.core.exceptions import ValidationError
from django.db import transaction

from planning.models import PlanningItem
from planning.queries import MAX_DEPTH, ancestor_ids, descendant_ids

from . import scheduling


def validate_parent(item, new_parent):
    """Refuse a re-parent that would close a loop (FR-06).

    Moving `item` under `new_parent` creates a cycle exactly when `new_parent`
    is `item` itself or sits somewhere below it. Rather than walking down from
    `item`, which could be a large subtree, this walks up from `new_parent`:
    the move is illegal if `item` appears among its ancestors. Either
    direction is correct, but the upward walk is bounded by tree depth instead
    of by subtree size.
    """
    if new_parent is None:
        return

    if new_parent.user_id != item.user_id:
        raise ValidationError('A planning item cannot be moved under another user\'s item.')

    if item.pk is not None and new_parent.pk == item.pk:
        raise ValidationError('An item cannot be its own parent.')

    chain = ancestor_ids(new_parent.user_id, new_parent.pk)

    if item.pk is not None and item.pk in chain:
        raise ValidationError('An item cannot become its own ancestor.')

    # ancestor_ids stops at MAX_DEPTH. Hitting that cap means either a tree
    # deeper than ARC supports or a cycle that already reached the database;
    # in both cases the answer above cannot be trusted.
    if len(chain) + 1 >= MAX_DEPTH:
        raise ValidationError(
            f'This move would nest the item more than {MAX_DEPTH} levels deep.'
        )


@transaction.atomic
def set_parent(item, new_parent):
    """Validate and apply a re-parent, keeping sibling numbering dense."""
    validate_parent(item, new_parent)
    old_parent = item.parent

    item.parent = new_parent
    item.sibling_order = _next_sibling_order(item.user, new_parent)
    item.save(update_fields=['parent', 'sibling_order', 'updated_at'])

    reindex_siblings(item.user, old_parent)
    reindex_siblings(item.user, new_parent)

    # Moving an item can change leaf eligibility for both its old and new parent.
    scheduling.schedule(item.user)

    item.refresh_from_db(fields=['priority_position'])
    return item


def _siblings(user, parent):
    return PlanningItem.objects.visible().filter(user=user, parent=parent).order_by(
        'sibling_order', 'id'
    )


def _next_sibling_order(user, parent):
    return _siblings(user, parent).count() + 1


@transaction.atomic
def reindex_siblings(user, parent=None):
    """Renumber one parent's children as a dense 1..n.

    Takes the user as well as the parent because ``parent=None`` means "the
    roots", and roots are only meaningful per user.
    """
    changed = []
    for order, child in enumerate(_siblings(user, parent), start=1):
        if child.sibling_order != order:
            child.sibling_order = order
            changed.append(child)
    if changed:
        PlanningItem.objects.bulk_update(changed, ['sibling_order'])
    return changed


@transaction.atomic
def complete_subtree(item):
    """Mark an item and everything under it complete (FR-08).

    Completed tasks leave the priority order, which keeps the FR-09 invariant
    that a position belongs to an active task.
    """
    ids = [item.pk] + descendant_ids(item.user_id, item.pk)
    PlanningItem.objects.visible().filter(user_id=item.user_id, pk__in=ids).update(is_completed=True)
    scheduling.schedule(item.user)
    item.is_completed = True
    return ids


@transaction.atomic
def reopen(item):
    """Mark a single item incomplete again and give it a priority position.

    Deliberately not a cascade: FR-08 only requires completion to propagate
    downwards, and re-opening a root should not silently re-open a subtree the
    user finished individually.
    """
    PlanningItem.objects.visible().filter(pk=item.pk).update(is_completed=False)
    item.is_completed = False
    scheduling.schedule(item.user)
    item.refresh_from_db(fields=['priority_position'])
    return item
