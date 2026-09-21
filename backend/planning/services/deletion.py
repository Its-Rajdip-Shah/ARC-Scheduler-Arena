"""Validated ARC delete/restore lifecycle commands.

Deletion is a tombstone transition, not semantic amnesia.

A subtree delete:
* happens atomically;
* preserves row identity;
* remembers hierarchy/dependency/anchor restoration intent;
* removes the subtree from active projections;
* suspends incident dependency edges.

Restore validates that remembered intent against the present world before
reactivating it.  It never blindly reinstates a hierarchy cycle, dependency
cycle, dangling relationship or expired hard anchor.
"""

from __future__ import annotations

from datetime import date

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from planning.models import PlanningDependency, PlanningItem
from planning.queries import descendant_ids
from planning.services import dependencies, hierarchy, priority, scheduling


def _coerce_item(item):
    if isinstance(item, PlanningItem):
        return item
    return PlanningItem.objects.get(pk=item)


def _subtree_ids(item):
    return [item.pk] + descendant_ids(item.user_id, item.pk)


def _edge_state(edge):
    return {
        "prerequisite_id": edge.prerequisite_id,
        "dependent_id": edge.dependent_id,
    }


@transaction.atomic
def delete_subtree(item: PlanningItem):
    """Atomically tombstone an item and its currently active subtree."""

    item = _coerce_item(item)
    priority._lock(item.user)

    root = (
        PlanningItem.objects
        .select_for_update()
        .get(pk=item.pk, user=item.user)
    )

    if root.is_deleted:
        return root

    ids = _subtree_ids(root)

    rows = list(
        PlanningItem.objects
        .select_for_update()
        .filter(user=root.user, pk__in=ids)
        .order_by("pk")
    )

    active_ids = {row.pk for row in rows if not row.is_deleted}

    # Capture all incident edges before removing them from the active graph.
    incident_edges = list(
        PlanningDependency.objects
        .select_for_update()
        .filter(
            prerequisite_id__in=active_ids
        )
        | PlanningDependency.objects
        .select_for_update()
        .filter(
            dependent_id__in=active_ids
        )
    )

    # De-duplicate edges that are internal to the subtree.
    edge_states = {
        (edge.prerequisite_id, edge.dependent_id): _edge_state(edge)
        for edge in incident_edges
    }

    context = {
        "root_id": root.pk,
        "subtree_ids": sorted(active_ids),
        "parents": {
            str(row.pk): row.parent_id
            for row in rows
            if row.pk in active_ids
        },
        "sibling_orders": {
            str(row.pk): row.sibling_order
            for row in rows
            if row.pk in active_ids
        },
        "manual_requested_dates": {
            str(row.pk): (
                row.manual_requested_date.isoformat()
                if row.manual_requested_date is not None
                else None
            )
            for row in rows
            if row.pk in active_ids
        },
        "dependencies": list(edge_states.values()),
    }

    # Store the lifecycle context on the delete root.  Descendants keep their
    # own semantic fields untouched; the root owns this particular subtree
    # deletion episode.
    root.deletion_restore_context = context
    root.save(update_fields=["deletion_restore_context"])

    # Preserve priority neighbourhood before rows leave the active frontier.
    priority.release_positions(root.user, active_ids)

    # Incident edges cannot remain active while either endpoint is deleted.
    if edge_states:
        PlanningDependency.objects.filter(
            pk__in=[
                edge.pk
                for edge in incident_edges
            ]
        ).delete()

    PlanningItem.objects.filter(
        user=root.user,
        pk__in=active_ids,
    ).update(
        is_deleted=True,
        priority_position=None,
        scheduled_date=None,
    )

    # Reindex the surviving sibling projections for every affected parent.
    parent_ids = {
        row.parent_id
        for row in rows
        if row.pk in active_ids
    }

    for parent_id in parent_ids:
        parent = (
            PlanningItem.objects.filter(
                user=root.user,
                pk=parent_id,
                is_deleted=False,
            ).first()
            if parent_id is not None
            else None
        )
        hierarchy.reindex_siblings(root.user, parent)

    from . import lifecycle
    lifecycle.finish(root.user)

    root.refresh_from_db()
    return root


delete = delete_subtree
soft_delete = delete_subtree
delete_item = delete_subtree


def _validate_restored_parent(row, parent_id, restoring_ids):
    if parent_id is None:
        return None

    parent = PlanningItem.objects.filter(
        pk=parent_id,
        user=row.user,
    ).first()

    if parent is None:
        raise ValidationError(
            "The original parent no longer exists; choose a valid restore "
            "destination explicitly."
        )

    if parent.is_deleted and parent.pk not in restoring_ids:
        raise ValidationError(
            "The original parent is currently deleted; choose a valid restore "
            "destination explicitly."
        )

    # hierarchy.validate_parent uses the present graph and therefore catches
    # an original relationship that has become cyclic while this item was
    # deleted.
    hierarchy.validate_parent(row, parent)
    return parent


def _validate_dependency_restore(edge_states, user, restoring_ids):
    """Validate remembered edges against the prospective restored graph.

    We validate using the same cycle semantics as dependencies.add(), but do
    not commit any edge until every remembered edge is known to be valid.
    """

    candidates = []

    for state in edge_states:
        prerequisite = PlanningItem.objects.filter(
            pk=state["prerequisite_id"],
            user=user,
        ).first()
        dependent = PlanningItem.objects.filter(
            pk=state["dependent_id"],
            user=user,
        ).first()

        if prerequisite is None or dependent is None:
            raise ValidationError(
                "A dependency endpoint no longer exists; restore requires "
                "explicit dependency resolution."
            )

        if (
            prerequisite.is_deleted
            and prerequisite.pk not in restoring_ids
        ) or (
            dependent.is_deleted
            and dependent.pk not in restoring_ids
        ):
            raise ValidationError(
                "A dependency endpoint is currently deleted; restore requires "
                "explicit dependency resolution."
            )

        candidates.append((prerequisite, dependent))

    # Validate the complete prospective graph in memory. This catches cycles
    # involving multiple remembered edges, not merely one edge at a time.
    active_edges = list(
        PlanningDependency.objects.filter(
            prerequisite__user=user,
            dependent__user=user,
            prerequisite__is_deleted=False,
            dependent__is_deleted=False,
        ).values_list("prerequisite_id", "dependent_id")
    )

    graph = {}
    for prerequisite_id, dependent_id in active_edges:
        graph.setdefault(prerequisite_id, set()).add(dependent_id)

    for prerequisite, dependent in candidates:
        if prerequisite.pk == dependent.pk:
            raise ValidationError(
                "Restoring this dependency would create a self-cycle."
            )

        graph.setdefault(prerequisite.pk, set()).add(dependent.pk)

    def reaches(start, target):
        stack = [start]
        visited = set()

        while stack:
            current = stack.pop()
            if current == target:
                return True
            if current in visited:
                continue
            visited.add(current)
            stack.extend(graph.get(current, ()))

        return False

    # Validate the complete prospective graph, including interactions among
    # multiple remembered edges.  A directed graph is valid iff DFS finds no
    # back-edge.
    visiting = set()
    visited = set()

    def visit(node):
        if node in visiting:
            return True
        if node in visited:
            return False

        visiting.add(node)

        for nxt in graph.get(node, ()):
            if visit(nxt):
                return True

        visiting.remove(node)
        visited.add(node)
        return False

    nodes = set(graph)
    for targets in graph.values():
        nodes.update(targets)

    if any(visit(node) for node in nodes if node not in visited):
        raise ValidationError(
            "Restoring the original dependencies would create a cycle in "
            "the present dependency graph."
        )

    return candidates


@transaction.atomic
def restore_subtree(item: PlanningItem, *, today=None):
    """Restore a deleted subtree only when remembered semantics remain valid."""

    item = _coerce_item(item)
    priority._lock(item.user)
    today = today or timezone.localdate()

    root = (
        PlanningItem.objects
        .select_for_update()
        .get(pk=item.pk, user=item.user)
    )

    if not root.is_deleted:
        return root

    context = dict(root.deletion_restore_context or {})
    ids = context.get("subtree_ids") or [root.pk]
    restoring_ids = {int(pk) for pk in ids}

    rows = list(
        PlanningItem.objects
        .select_for_update()
        .filter(user=root.user, pk__in=restoring_ids)
        .order_by("pk")
    )

    if {row.pk for row in rows} != restoring_ids:
        raise ValidationError(
            "The deleted subtree can no longer be restored intact."
        )

    parents = context.get("parents", {})

    # ----- Validate hierarchy against CURRENT world ---------------------
    for row in rows:
        parent_id = parents.get(str(row.pk), row.parent_id)

        # Relationships wholly inside the same restoring subtree are restored
        # together. They still cannot contain a self-reference.
        if parent_id in restoring_ids:
            if parent_id == row.pk:
                raise ValidationError(
                    "Restoring the original hierarchy would create a cycle."
                )
            continue

        _validate_restored_parent(row, parent_id, restoring_ids)

    # Validate the prospective restored subtree itself for cycles.
    prospective_parent = {
        row.pk: parents.get(str(row.pk), row.parent_id)
        for row in rows
    }

    for row in rows:
        seen = {row.pk}
        current = prospective_parent.get(row.pk)

        while current in restoring_ids:
            if current in seen:
                raise ValidationError(
                    "Restoring the original hierarchy would create a cycle."
                )
            seen.add(current)
            current = prospective_parent.get(current)

    # ----- Validate remembered dependencies before committing ----------
    dependency_candidates = _validate_dependency_restore(
        context.get("dependencies", []),
        root.user,
        restoring_ids,
    )

    # ----- Commit subtree restoration ----------------------------------
    changed = []

    for row in rows:
        row.is_deleted = False
        row.parent_id = prospective_parent.get(row.pk)

        sibling_order = context.get(
            "sibling_orders", {}
        ).get(str(row.pk))

        if sibling_order is not None:
            row.sibling_order = sibling_order

        old_anchor = context.get(
            "manual_requested_dates", {}
        ).get(str(row.pk))

        if old_anchor:
            anchor_day = date.fromisoformat(old_anchor)

            # D7: a missed historical anchor is not resurrected as a new hard
            # current commitment merely because the task was restored later.
            if anchor_day < today:
                row.expired_manual_requested_date = anchor_day
                row.manual_requested_date = None
            else:
                row.manual_requested_date = anchor_day

        changed.append(row)

    PlanningItem.objects.bulk_update(
        changed,
        [
            "is_deleted",
            "parent",
            "sibling_order",
            "manual_requested_date",
            "expired_manual_requested_date",
        ],
    )

    # Every remembered dependency was validated before any is recreated.
    for prerequisite, dependent in dependency_candidates:
        PlanningDependency.objects.get_or_create(
            prerequisite=prerequisite,
            dependent=dependent,
        )

    affected_parent_ids = set(prospective_parent.values())

    for parent_id in affected_parent_ids:
        parent = (
            PlanningItem.objects.filter(
                user=root.user,
                pk=parent_id,
                is_deleted=False,
            ).first()
            if parent_id is not None
            else None
        )
        hierarchy.reindex_siblings(root.user, parent)

    from . import lifecycle
    for row in rows:
        if not row.is_completed:
            lifecycle.reopen_ancestors(row)
    lifecycle.finish(root.user, today)

    root.refresh_from_db()
    return root


restore = restore_subtree
restore_item = restore_subtree
