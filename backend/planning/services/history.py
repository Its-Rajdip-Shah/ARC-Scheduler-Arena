"""Bounded, delta-based undo/redo support for ARC planning mutations.

History stores only rows affected by an action, rather than snapshotting the
entire planner. This keeps storage and restore work proportional to the
mutation itself.
"""

from django.db import transaction

from planning.models import (
    AssignmentDetail,
    DurationCategory,
    PlanningHistoryEntry,
    PlanningItem,
    SchedulingOverload,
    SchedulingPreference,
)

MAX_HISTORY_ENTRIES = 100


# ---------------------------------------------------------------------------
# SERIALISATION
# ---------------------------------------------------------------------------

def serialize_item(item):
    """Capture the complete reversible state of one planning item."""

    assignment = getattr(item, "assignment_detail", None)

    return {
        "id": item.pk,
        "parent_id": item.parent_id,
        "item_type": item.item_type,
        "title": item.title,
        "description": item.description,
        "sibling_order": item.sibling_order,
        "start_date": item.start_date.isoformat() if item.start_date else None,
        "due_date": item.due_date.isoformat() if item.due_date else None,
        "scheduled_date": (
            item.scheduled_date.isoformat()
            if item.scheduled_date else None
        ),
        "duration_category": item.duration_category,
        "schedule_is_manual": item.schedule_is_manual,
        "priority_restore_context": item.priority_restore_context,
        "priority_position": item.priority_position,
        "is_completed": item.is_completed,
        "canvas_object_type": item.canvas_object_type,
        "canvas_object_id": item.canvas_object_id,
        "tag_ids": list(
            item.tags.order_by("id").values_list("id", flat=True)
        ),
        "assignment_detail": (
            {
                "weight_percent": (
                    str(assignment.weight_percent)
                    if assignment.weight_percent is not None
                    else None
                ),
                "submission_url": assignment.submission_url,
            }
            if assignment
            else None
        ),
    }


def capture_items(user, item_ids):
    """Capture only the requested items belonging to this user."""

    ids = set(item_ids)

    if not ids:
        return []

    items = (
        PlanningItem.objects
        .filter(user=user, pk__in=ids)
        .select_related("assignment_detail")
        .prefetch_related("tags")
        .order_by("id")
    )

    return [serialize_item(item) for item in items]


def capture_scope(user, queryset):
    """Capture the rows represented by an already-scoped queryset."""

    ids = queryset.values_list("pk", flat=True)
    return capture_items(user, ids)


# ---------------------------------------------------------------------------
# SMALL STATE CAPTURES
# ---------------------------------------------------------------------------

def capture_priority(user, *, include_unpositioned=False):
    """Capture priority membership/order.

    Include null positions and restoration anchors when eligibility can change,
    so undo restores both active membership and future reopening behaviour.
    """

    items = PlanningItem.objects.filter(user=user)
    if not include_unpositioned:
        items = items.exclude(priority_position=None)
    fields = ["id", "priority_position"]
    if include_unpositioned:
        fields.append("priority_restore_context")
    return list(items.order_by("priority_position", "id").values(*fields))


def capture_siblings(user, parent_id):
    """Capture only sibling ordering for one parent/root group."""

    return list(
        PlanningItem.objects
        .filter(user=user, parent_id=parent_id)
        .order_by("sibling_order", "id")
        .values("id", "parent_id", "sibling_order")
    )


def capture_leaf_order(user):
    """Snapshot only synchronizable leaf slots, never parent relationships."""
    from planning.services.leaf_order_sync import leaves

    return list(leaves(user).order_by('pk').values('id', 'sibling_order'))


def _restore_leaf_order(user, states):
    """Restore explicit leaf slots without allowing container writes."""
    from planning.services.leaf_order_sync import leaves

    wanted = {state['id']: state['sibling_order'] for state in states}
    items = list(leaves(user).filter(pk__in=wanted))
    for item in items:
        item.sibling_order = wanted[item.pk]
    if items:
        PlanningItem.objects.bulk_update(items, ['sibling_order'])


# ---------------------------------------------------------------------------
# SOFT-DELETE GARBAGE COLLECTION
# ---------------------------------------------------------------------------

def _delete_ids_from_entry(entry):
    """Return item IDs owned by a DELETE checkpoint."""

    if entry.action_type != "DELETE":
        return set()

    soft_delete = entry.after_state.get("soft_delete", {})

    if not soft_delete.get("value"):
        return set()

    return set(soft_delete.get("ids", []))


def _protected_delete_ids(user, exclude_entry_ids=None):
    """IDs still recoverable through surviving DELETE history."""

    exclude_entry_ids = set(exclude_entry_ids or [])

    entries = (
        PlanningHistoryEntry.objects
        .filter(user=user, action_type="DELETE")
        .exclude(pk__in=exclude_entry_ids)
        .only("id", "action_type", "after_state")
    )

    protected = set()

    for entry in entries:
        protected.update(_delete_ids_from_entry(entry))

    return protected


def _garbage_collect_discarded_entries(user, entries):
    """Hard-delete unreachable rows from discarded DELETE checkpoints.

    A row is removed only when:
    1. its DELETE checkpoint is being permanently discarded,
    2. the row is still soft-deleted, and
    3. no surviving DELETE checkpoint still protects it.
    """

    entries = list(entries)

    if not entries:
        return

    discarded_ids = {entry.pk for entry in entries}

    candidates = set()

    for entry in entries:
        candidates.update(_delete_ids_from_entry(entry))

    if not candidates:
        return

    protected = _protected_delete_ids(
        user,
        exclude_entry_ids=discarded_ids,
    )

    hard_delete_ids = candidates - protected

    if not hard_delete_ids:
        return

    # Only physically remove rows that are STILL deleted.
    #
    # If a DELETE was undone and its redo branch is discarded,
    # those rows are visible again and must remain.
    PlanningItem.objects.filter(
        user=user,
        pk__in=hard_delete_ids,
        is_deleted=True,
    ).delete()


# ---------------------------------------------------------------------------
# HISTORY RECORDING
# ---------------------------------------------------------------------------

def record_checkpoint(
    user,
    action_type,
    before_state,
    after_state,
):
    """Record one user action and invalidate the old redo branch."""

    if before_state == after_state:
        return None

    # Standard undo semantics:
    #
    # A -> B -> C
    #         undo C
    #         perform D
    #
    # C can no longer be redone.
    discarded_redo = list(
        PlanningHistoryEntry.objects.filter(
            user=user,
            is_undone=True,
        )
    )

    _garbage_collect_discarded_entries(
        user,
        discarded_redo,
    )

    if discarded_redo:
        PlanningHistoryEntry.objects.filter(
            pk__in=[entry.pk for entry in discarded_redo],
        ).delete()

    entry = PlanningHistoryEntry.objects.create(
        user=user,
        action_type=action_type,
        before_state=before_state,
        after_state=after_state,
    )

    prune_history(user)

    return entry


def prune_history(user):
    """Keep at most MAX_HISTORY_ENTRIES checkpoints per user."""

    keep_ids = list(
        PlanningHistoryEntry.objects
        .filter(user=user)
        .order_by("-id")
        .values_list("id", flat=True)[:MAX_HISTORY_ENTRIES]
    )

    if keep_ids:
        pruned = list(
            PlanningHistoryEntry.objects
            .filter(user=user)
            .exclude(pk__in=keep_ids)
        )

        _garbage_collect_discarded_entries(
            user,
            pruned,
        )

        if pruned:
            PlanningHistoryEntry.objects.filter(
                pk__in=[entry.pk for entry in pruned],
            ).delete()


# ---------------------------------------------------------------------------
# RESTORATION HELPERS
# ---------------------------------------------------------------------------

def _restore_item_states(user, states):
    """Restore/create only items represented in the supplied delta."""

    if not states:
        return

    ids = [state["id"] for state in states]

    existing = {
        item.pk: item
        for item in PlanningItem.objects.filter(
            user=user,
            pk__in=ids,
        )
    }

    # Pass 1: scalar state without parent FK.
    for state in states:
        values = {
            "user": user,
            "parent": None,
            "item_type": state["item_type"],
            "title": state["title"],
            "description": state["description"],
            "sibling_order": state["sibling_order"],
            "start_date": state["start_date"],
            "due_date": state["due_date"],
            "scheduled_date": state["scheduled_date"],
            "duration_category": state.get("duration_category") or DurationCategory.MIN_20_TO_60,
            "schedule_is_manual": state.get("schedule_is_manual", False),
            "priority_restore_context": state.get("priority_restore_context", {}),
            "priority_position": state["priority_position"],
            "is_completed": state["is_completed"],
            "canvas_object_type": state["canvas_object_type"],
            "canvas_object_id": state["canvas_object_id"],
        }

        item = existing.get(state["id"])

        if item is None:
            item = PlanningItem(id=state["id"], **values)
            item.save(force_insert=True)
            existing[item.pk] = item
        else:
            for field, value in values.items():
                setattr(item, field, value)

            item.save()

    # Pass 2: hierarchy after all required rows exist.
    for state in states:
        item = existing[state["id"]]

        if item.parent_id != state["parent_id"]:
            item.parent_id = state["parent_id"]
            item.save(update_fields=["parent"])

    # Pass 3: M2M + assignment detail.
    for state in states:
        item = existing[state["id"]]

        item.tags.set(state["tag_ids"])

        detail = state["assignment_detail"]

        if detail is None:
            AssignmentDetail.objects.filter(
                planning_item=item
            ).delete()
        else:
            AssignmentDetail.objects.update_or_create(
                planning_item=item,
                defaults={
                    "weight_percent": detail["weight_percent"],
                    "submission_url": detail["submission_url"],
                },
            )


def _restore_priority(user, states):
    """Restore only priority positions represented in a checkpoint."""

    if states is None:
        return

    wanted = {
        state["id"]: state
        for state in states
    }

    if not wanted:
        return

    items = list(
        PlanningItem.objects.filter(
            user=user,
            pk__in=wanted.keys(),
        )
    )

    changed = []

    for item in items:
        state = wanted[item.pk]
        position = state["priority_position"]
        context = state.get("priority_restore_context", item.priority_restore_context)
        if item.priority_position != position or item.priority_restore_context != context:
            item.priority_position = position
            item.priority_restore_context = context
            changed.append(item)

    if changed:
        PlanningItem.objects.bulk_update(
            changed,
            ["priority_position", "priority_restore_context"],
        )


def _restore_siblings(user, states):
    """Restore sibling parent/order values represented by the delta."""

    if not states:
        return

    wanted = {state["id"]: state for state in states}

    items = list(
        PlanningItem.objects.filter(
            user=user,
            pk__in=wanted.keys(),
        )
    )

    changed = []

    for item in items:
        state = wanted[item.pk]

        if (
            item.parent_id != state["parent_id"]
            or item.sibling_order != state["sibling_order"]
        ):
            item.parent_id = state["parent_id"]
            item.sibling_order = state["sibling_order"]
            changed.append(item)

    if changed:
        PlanningItem.objects.bulk_update(
            changed,
            ["parent", "sibling_order"],
        )


def _apply_delta(user, state, action_type):
    """Apply one operation-scoped state payload."""

    if action_type == "PRIORITY":
        # Ignore legacy whole-hierarchy 'siblings' snapshots. New checkpoints
        # explicitly name leaf slots, and restoration cannot write containers.
        _restore_priority(user, state.get("priority"))
        _restore_leaf_order(user, state.get("leaf_siblings", []))
        return

    if action_type == "SCHEDULE":
        _restore_priority(user, state.get('priority'))
        _restore_leaf_order(user, state.get('leaf_siblings', []))
        for row in state.get('schedule', []):
            PlanningItem.objects.filter(user=user, pk=row['id']).update(
                scheduled_date=row['scheduled_date'], schedule_is_manual=row['schedule_is_manual'],
                priority_restore_context=row['priority_restore_context'],
            )
        SchedulingOverload.objects.filter(user=user).delete()
        SchedulingOverload.objects.bulk_create([
            SchedulingOverload(user=user, **row) for row in state.get('overload', [])
        ])
        if state.get('capacity'):
            SchedulingPreference.objects.update_or_create(user=user, defaults=state['capacity'][0])
        else:
            SchedulingPreference.objects.filter(user=user).delete()
        return

    # Soft-delete / restore existing rows in one bulk UPDATE.
    soft_delete = state.get("soft_delete")
    if soft_delete:
        PlanningItem.objects.filter(
            user=user,
            pk__in=soft_delete["ids"],
        ).update(is_deleted=soft_delete["value"])

    # Delete rows that should not exist in this state.
    delete_ids = state.get("delete_ids", [])

    if delete_ids:
        PlanningItem.objects.filter(
            user=user,
            pk__in=delete_ids,
        ).delete()

    # Restore/create complete item states where necessary.
    _restore_item_states(
        user,
        state.get("items", []),
    )

    # Restore lightweight structural deltas.
    _restore_siblings(
        user,
        state.get("siblings", []),
    )

    _restore_priority(
        user,
        state.get("priority"),
    )


# ---------------------------------------------------------------------------
# UNDO / REDO
# ---------------------------------------------------------------------------

@transaction.atomic
def undo(user):
    entry = (
        PlanningHistoryEntry.objects
        .select_for_update()
        .filter(user=user, is_undone=False)
        .order_by("-id")
        .first()
    )

    if entry is None:
        return None

    _apply_delta(user, entry.before_state, entry.action_type)

    entry.is_undone = True
    entry.save(update_fields=["is_undone"])

    return entry


@transaction.atomic
def redo(user):
    # Among undone entries, the lowest ID is the first operation
    # that must be reapplied.
    entry = (
        PlanningHistoryEntry.objects
        .select_for_update()
        .filter(user=user, is_undone=True)
        .order_by("id")
        .first()
    )

    if entry is None:
        return None

    _apply_delta(user, entry.after_state, entry.action_type)

    entry.is_undone = False
    entry.save(update_fields=["is_undone"])

    return entry


def history_status(user):
    history = PlanningHistoryEntry.objects.filter(user=user)

    return {
        "can_undo": history.filter(is_undone=False).exists(),
        "can_redo": history.filter(is_undone=True).exists(),
    }
