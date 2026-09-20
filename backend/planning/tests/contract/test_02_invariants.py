
from .conftest import covers
"""
ARC frozen-contract tests: cross-cutting invariants.

This file concentrates on invariants that can already be tested against the
current PlanningItem model/services. Later files exercise dependencies,
anchors, allocations, transactions and view coherence in greater depth.
"""

import pytest
from django.core.exceptions import ValidationError

from planning.models import PlanningItem
from planning.services import hierarchy, priority

pytestmark = pytest.mark.django_db


def _active(user):
    return PlanningItem.objects.filter(user=user, is_deleted=False)


def _priority_ids(user):
    return list(
        _active(user)
        .filter(is_completed=False)
        .exclude(priority_position=None)
        .order_by("priority_position", "pk")
        .values_list("pk", flat=True)
    )


def _assert_dense_unique_priority(user):
    positions = list(
        _active(user)
        .exclude(priority_position=None)
        .order_by("priority_position", "pk")
        .values_list("priority_position", flat=True)
    )
    assert len(positions) == len(set(positions)), "priority positions must be unique"
    assert positions == list(range(1, len(positions) + 1)), (
        f"active priority positions must be dense 1..n, got {positions}"
    )


@covers('HIE-001')
def test_hierarchy_rejects_self_parent(user, make_item):
    item = make_item(user, "A")
    with pytest.raises(ValidationError):
        hierarchy.set_parent(item, item)


@covers('HIE-001')
def test_hierarchy_rejects_descendant_cycle(user, make_item):
    a = make_item(user, "A")
    b = make_item(user, "B", parent=a)
    c = make_item(user, "C", parent=b)

    with pytest.raises(ValidationError):
        hierarchy.set_parent(a, c)


@covers('HIE-002')
def test_cross_user_parent_is_rejected(user, other_user, make_item):
    item = make_item(user, "Mine")
    foreign_parent = make_item(other_user, "Theirs")

    with pytest.raises(ValidationError):
        hierarchy.set_parent(item, foreign_parent)


def test_structural_parent_is_not_frontier_while_unfinished_child_exists(
    user, make_item
):
    parent = make_item(user, "Parent")
    child = make_item(user, "Child", parent=parent)

    priority.reconcile(user)
    parent.refresh_from_db()
    child.refresh_from_db()

    assert parent.priority_position is None
    assert child.priority_position is not None


def test_completed_task_is_not_active_priority_frontier(user, make_item):
    item = make_item(user, "Task")
    priority.reconcile(user)
    assert item.pk in _priority_ids(user)

    hierarchy.complete_subtree(item)
    assert item.pk not in _priority_ids(user)


def test_deleted_task_is_not_active_priority_frontier(user, make_item):
    a = make_item(user, "A")
    b = make_item(user, "B")
    priority.reconcile(user)

    PlanningItem.objects.filter(pk=a.pk).update(is_deleted=True)
    priority.reconcile(user)

    assert a.pk not in _priority_ids(user)
    assert b.pk in _priority_ids(user)


def test_priority_reconciliation_is_idempotent(user, make_item):
    for title in ("A", "B", "C", "D"):
        make_item(user, title)

    priority.reconcile(user)
    first = list(
        PlanningItem.objects.filter(user=user)
        .order_by("pk")
        .values_list("pk", "priority_position")
    )

    priority.reconcile(user)
    second = list(
        PlanningItem.objects.filter(user=user)
        .order_by("pk")
        .values_list("pk", "priority_position")
    )

    assert second == first
    _assert_dense_unique_priority(user)


def test_reopen_does_not_reopen_completed_descendants(user, make_item):
    parent = make_item(user, "Parent")
    child = make_item(user, "Child", parent=parent)

    hierarchy.complete_subtree(parent)
    hierarchy.reopen(parent)

    parent.refresh_from_db()
    child.refresh_from_db()
    assert parent.is_completed is False
    assert child.is_completed is True


def test_complete_then_reopen_round_trip_preserves_identity_and_hierarchy(
    user, make_item
):
    parent = make_item(user, "Parent")
    item = make_item(user, "Task", parent=parent)
    priority.reconcile(user)

    before = {
        "pk": item.pk,
        "parent_id": item.parent_id,
        "title": item.title,
    }

    hierarchy.complete_subtree(item)
    hierarchy.reopen(item)
    item.refresh_from_db()

    after = {
        "pk": item.pk,
        "parent_id": item.parent_id,
        "title": item.title,
    }
    assert after == before


def test_priority_is_not_sibling_order(user, make_item):
    root = make_item(user, "Root", item_type="GOAL")
    a = make_item(user, "A", parent=root, sibling_order=1)
    b = make_item(user, "B", parent=root, sibling_order=2)
    priority.reconcile(user)

    # Explicit priority mutation must not secretly rewrite hierarchy order.
    priority.reorder(user, b.pk, 1)
    a.refresh_from_db()
    b.refresh_from_db()

    assert (a.sibling_order, b.sibling_order) == (1, 2)
    assert b.priority_position < a.priority_position
