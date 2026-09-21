"""The single global task priority order (FR-09).

Every active, actionable task of a user holds exactly one position, numbered
densely from 1, and no two share a number. Completed and non-actionable items
hold NULL. Keeping that invariant is entirely this module's job; the database
backs it up with uniq_user_priority_position.

The unique constraint is immediate on every supported database. Atomic
permutations temporarily release affected slots before assigning final values.
"""

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Max

from planning.models import PlanningItem


def ordered(user):
    """The user's positioned active tasks, highest priority first."""
    return (
        PlanningItem.objects.for_user(user)
        .actionable()
        .active()
        .exclude(priority_position=None)
        .order_by('priority_position', 'id')
    )


def _lock(user):
    """Serialise concurrent position writes for one user.

    Two simultaneous creates would otherwise read the same MAX and claim the
    same tail position.
    """
    get_user_model().objects.select_for_update().get(pk=user.pk)


@transaction.atomic
def assign_initial_position(task):
    """Place a newly active task at the end of the order.

    Does nothing for goals, completed items, or a task that already holds a
    position, so it is safe to call from a save path.
    """
    if not PlanningItem.objects.filter(pk=task.pk, user=task.user).priority_eligible().exists() or task.priority_position is not None:
        return task.priority_position

    _lock(task.user)
    highest = (
        PlanningItem.objects.filter(user_id=task.user_id)
        .aggregate(Max('priority_position'))['priority_position__max']
    )
    task.priority_position = (highest or 0) + 1
    task.save(update_fields=['priority_position'])
    return task.priority_position


@transaction.atomic
def renumber(user):
    """Rewrite the order as a dense 1..n, preserving relative sequence."""
    items = list(ordered(user))
    changed = []
    for position, item in enumerate(items, start=1):
        if item.priority_position != position:
            item.priority_position = position
            changed.append(item)
    if changed:
        _write_positions(changed)
    return items


def _remember_departures(user, departing_ids):
    rows = list(PlanningItem.objects.filter(user=user, priority_position__isnull=False)
                .order_by('priority_position', 'pk'))
    # Include temporarily absent neighbours when capturing a later departure.
    # Otherwise A leaving while B is blocked forgets that A preceded B.
    dormant = PlanningItem.objects.filter(user=user, priority_position=None).order_by('pk')
    for row in dormant:
        if row.priority_restore_context:
            _insert_restored(rows, row)
    ids = [row.pk for row in rows]
    changed = []
    for index, row in enumerate(rows):
        if row.pk in departing_ids:
            row.priority_restore_context = {'before': ids[:index], 'after': ids[index + 1:]}
            changed.append(row)
    if changed:
        PlanningItem.objects.bulk_update(changed, ['priority_restore_context'])


def _insert_restored(ordered_items, item):
    context = item.priority_restore_context
    ids = [row.pk for row in ordered_items]
    following = next((pk for pk in context.get('after', []) if pk in ids), None)
    preceding = next((pk for pk in reversed(context.get('before', [])) if pk in ids), None)
    index = ids.index(following) if following is not None else (ids.index(preceding) + 1 if preceding is not None else len(ids))
    ordered_items.insert(index, item)


def _inherit_departing_descendant_context(user, item, departing):
    """Give a newly exposed frontier ancestor its descendant's vacated slot.

    Existing restore history always wins. Otherwise, if a departing frontier
    item belongs to this item's descendant branch, inherit that item's saved
    neighbour anchors. This works for arbitrary hierarchy depth.
    """
    if item.priority_restore_context:
        return

    by_id = {
        row.pk: row
        for row in PlanningItem.objects.filter(user=user).only(
            'pk', 'parent_id', 'priority_restore_context'
        )
    }

    candidates = []

    for row in departing:
        current = row
        distance = 0

        while current.parent_id is not None:
            distance += 1

            if current.parent_id == item.pk:
                candidates.append((distance, row.pk, row))
                break

            current = by_id.get(current.parent_id)
            if current is None:
                break

    if not candidates:
        return

    # Nearest descendant wins; PK makes ties deterministic.
    _, _, source = min(candidates)

    item.priority_restore_context = dict(source.priority_restore_context or {})
    item.save(update_fields=['priority_restore_context'])


@transaction.atomic
def reconcile(user):
    """Make stored priority positions match current priority eligibility.

    Existing eligible tasks keep their relative order. Newly eligible tasks
    return near surviving anchors, or join the end without prior context.
    Ineligible tasks lose their position. The final order is
    dense from 1..n.
    """
    _lock(user)

    eligible_ids = set(
        PlanningItem.objects.for_user(user)
        .priority_eligible()
        .values_list('pk', flat=True)
    )

    departing_ids = set(PlanningItem.objects.filter(user=user, priority_position__isnull=False)
                        .exclude(pk__in=eligible_ids).values_list('pk', flat=True))
    _remember_departures(user, departing_ids)

    # Capture departing rows after their neighbour contexts have been stored.
    # A newly exposed ancestor can inherit the frontier neighbourhood vacated
    # by a descendant from the same hierarchy branch.
    departing = list(
        PlanningItem.objects.filter(user=user, pk__in=departing_ids)
        .only('pk', 'parent_id', 'priority_restore_context')
    )

    # Remove positions from tasks that are no longer eligible.
    PlanningItem.objects.filter(
        user_id=user.pk,
        priority_position__isnull=False,
    ).exclude(pk__in=eligible_ids).update(priority_position=None)

    # Preserve the relative order of existing eligible tasks.
    positioned = list(
        PlanningItem.objects.filter(
            user_id=user.pk,
            pk__in=eligible_ids,
            priority_position__isnull=False,
        ).order_by('priority_position', 'id')
    )

    # Restore prior neighbours when possible; genuinely new work joins the end.
    unpositioned = list(
        PlanningItem.objects.filter(
            user_id=user.pk,
            pk__in=eligible_ids,
            priority_position=None,
        ).order_by('id')
    )

    ordered_items = positioned
    for item in unpositioned:
        _inherit_departing_descendant_context(user, item, departing)
        _insert_restored(ordered_items, item)

    changed = []
    for position, item in enumerate(ordered_items, start=1):
        if item.priority_position != position:
            item.priority_position = position
            changed.append(item)

    if changed:
        _write_positions(changed)

    return ordered_items


@transaction.atomic
def reorder(user, item_id, new_position):
    """Move one task to a new row and close the gap it left behind.

    Positions outside the current range are clamped rather than rejected, so
    a drag past either end of the Priority View behaves the way it looks.
    """
    _lock(user)
    items = list(ordered(user).select_for_update())

    index = next((i for i, item in enumerate(items) if item.pk == item_id), None)
    if index is None:
        raise ValidationError('That task is not in the priority order.')

    moved = items.pop(index)
    target = max(1, min(int(new_position), len(items) + 1))
    items.insert(target - 1, moved)

    changed = []
    for position, item in enumerate(items, start=1):
        if item.priority_position != position:
            item.priority_position = position
            changed.append(item)
    if changed:
        # Apply an atomic permutation without transient duplicate positions.
        _write_positions(changed)

    return items


@transaction.atomic
def release_position(task):
    """Drop a task out of the order, on completion or before deletion."""
    if task.priority_position is None:
        return
    _remember_departures(task.user, {task.pk})
    task.priority_position = None
    task.save(update_fields=['priority_position'])
    renumber(task.user)


@transaction.atomic
def release_positions(user, item_ids):
    """Remember and release priority for a whole subtree together."""
    _remember_departures(user, set(item_ids))
    PlanningItem.objects.filter(user=user, pk__in=item_ids).exclude(
        priority_position=None
    ).update(priority_position=None)
    renumber(user)


@transaction.atomic
def restore_position(task):
    """Return reopened work near its surviving priority neighbours."""
    if task.priority_position is not None:
        return task.priority_position
    reconcile(task.user)
    task.refresh_from_db(fields=['priority_position'])
    return task.priority_position


def _write_positions(items):
    """Release affected slots before assigning a permutation on either DB."""
    if items:
        PlanningItem.objects.filter(pk__in=[item.pk for item in items]).update(priority_position=None)
        PlanningItem.objects.bulk_update(items, ['priority_position'])
