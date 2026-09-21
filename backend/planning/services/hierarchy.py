"""Structure of the planning tree: re-parenting and cascade completion.

Covers FR-06 (an item may never become its own ancestor) and FR-08 (completing
a parent completes everything beneath it).
"""

from django.core.exceptions import ValidationError
from django.db import transaction

from planning.models import PlanningItem
from planning.queries import MAX_DEPTH, ancestor_ids, descendant_ids

from . import priority, scheduling


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

    if new_parent.is_deleted:
        raise ValidationError('A deleted item cannot be a parent.')

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
    from . import lifecycle
    original = item
    item = lifecycle.active(item)
    if new_parent is not None:
        new_parent.refresh_from_db()
    validate_parent(item, new_parent)
    old_parent = item.parent

    item.parent = new_parent
    item.sibling_order = _next_sibling_order(item.user, new_parent)
    item.save(update_fields=['parent', 'sibling_order', 'updated_at'])

    reindex_siblings(item.user, old_parent)
    reindex_siblings(item.user, new_parent)

    # Reparenting can change frontier eligibility for the moved item,
    # its old parent and its new parent. Canonical priority must therefore
    # reconcile here, before the scheduler consumes the resulting state.
    if not item.is_completed:
        lifecycle.reopen_ancestors(item)
    lifecycle.finish(item.user)

    original.refresh_from_db()
    return original


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
def complete_subtree(item, *, reconcile=True):
    """Mark an item and everything under it complete (FR-08).

    Completed tasks leave the priority order, which keeps the FR-09 invariant
    that a position belongs to an active task.
    """
    from . import lifecycle
    from planning.models import ProgressSegment, SPLITTABLE_DURATION_CATEGORIES
    from decimal import Decimal
    from django.utils import timezone
    original = item
    item = lifecycle.active(item)
    ids = [item.pk] + descendant_ids(item.user_id, item.pk)
    for row in PlanningItem.objects.for_user(item.user).filter(pk__in=ids, is_completed=False, duration_category__in=SPLITTABLE_DURATION_CATEGORIES):
        remaining = Decimal(100) - row.percent_completed
        if remaining > 0:
            ProgressSegment.objects.create(item=row, percentage=remaining, is_completed=True, completed_at=timezone.now())
        row.percent_completed = 100
        row.save(update_fields=["percent_completed"])

    PlanningItem.objects.visible().filter(
        user_id=item.user_id,
        pk__in=ids,
    ).update(is_completed=True)

    # Completion is a canonical frontier transition. Departing tasks must
    # lose their active positions while preserving restore neighbourhood,
    # and newly exposed residual ancestors must enter that neighbourhood.
    if reconcile:
        lifecycle.finish(item.user)

    original.refresh_from_db()
    return ids


@transaction.atomic
def reopen(item, *, reconcile=True):
    """Mark a single item incomplete again and give it a priority position.

    Deliberately not a cascade: FR-08 only requires completion to propagate
    downwards, and re-opening a root should not silently re-open a subtree the
    user finished individually.
    """
    from . import lifecycle
    from planning.models import SPLITTABLE_DURATION_CATEGORIES
    original = item
    item = lifecycle.active(item)
    if item.duration_category in SPLITTABLE_DURATION_CATEGORIES and item.percent_completed:
        raise ValidationError("Reverse a confirmed progress segment to reopen large work.")
    PlanningItem.objects.visible().filter(
        pk=item.pk,
        user=item.user,
    ).update(is_completed=False)

    # Reopening may return this task to the frontier and may simultaneously
    # make an ancestor structural again. Restore canonical priority first.
    lifecycle.reopen_ancestors(item)
    if reconcile:
        lifecycle.finish(item.user)

    original.refresh_from_db()
    return original


@transaction.atomic
def set_sibling_order(item, position):
    """Move within one sibling group without changing global importance."""
    from . import lifecycle
    item = lifecycle.active(item)
    siblings = list(_siblings(item.user, item.parent).exclude(pk=item.pk))
    siblings.insert(max(0, min(int(position) - 1, len(siblings))), item)
    for index, row in enumerate(siblings, 1):
        row.sibling_order = index
    PlanningItem.objects.bulk_update(siblings, ['sibling_order'])
    item.refresh_from_db()
    return item
