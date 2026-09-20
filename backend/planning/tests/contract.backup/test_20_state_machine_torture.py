"""
ARC frozen-contract tests: deterministic state-machine torture RT-005/RT-006.

This module intentionally composes ordinary valid and invalid transitions many
times. It is not a replacement for focused tests: it catches semantic entropy,
non-idempotent reconciliation and failed-transition residue that only appear
after transition sequences.
"""

from __future__ import annotations

import random

import pytest
from django.core.exceptions import ValidationError

from planning.models import PlanningItem
from planning.services import hierarchy, priority

pytestmark = pytest.mark.django_db(transaction=True)

CONTRACT_IDS = {"RT-005", "RT-006"}


def _active(user):
    return PlanningItem.objects.filter(user=user, is_deleted=False)


def _assert_hierarchy_acyclic(user):
    items = list(_active(user).only("id", "parent_id"))
    parent_of = {item.pk: item.parent_id for item in items}

    for start in parent_of:
        seen = set()
        node = start
        while node is not None:
            assert node not in seen, (
                f"RT-005: hierarchy cycle detected while walking from {start}"
            )
            seen.add(node)
            node = parent_of.get(node)


def _assert_no_self_parent(user):
    for item in _active(user).only("id", "parent_id"):
        assert item.parent_id != item.pk, "RT-005: item became its own parent"


def _assert_priority_projection_sane(user):
    priority.reconcile(user)
    ordered = list(priority.ordered(user))

    ids = [item.pk for item in ordered]
    assert len(ids) == len(set(ids)), "RT-005: duplicate item in priority frontier"

    positions = [
        item.priority_position
        for item in ordered
        if item.priority_position is not None
    ]
    assert len(positions) == len(set(positions)), (
        "RT-005: duplicate canonical priority positions"
    )

    for item in ordered:
        assert item.is_deleted is False
        assert item.is_completed is False


def _assert_frontier_excludes_structural_parents(user):
    priority.reconcile(user)
    frontier = set(priority.ordered(user).values_list("pk", flat=True))

    for item in _active(user).filter(is_completed=False):
        has_unfinished_child = _active(user).filter(
            parent=item,
            is_completed=False,
        ).exists()
        if has_unfinished_child:
            assert item.pk not in frontier, (
                "RT-005: structural parent leaked into execution frontier"
            )


def _assert_all(user):
    _assert_hierarchy_acyclic(user)
    _assert_no_self_parent(user)
    _assert_priority_projection_sane(user)
    _assert_frontier_excludes_structural_parents(user)


def _snapshot(user):
    return list(
        PlanningItem.objects.filter(user=user)
        .order_by("pk")
        .values(
            "id",
            "parent_id",
            "title",
            "is_completed",
            "is_deleted",
            "priority_position",
            "sibling_order",
            "start_date",
            "due_date",
            "duration_category",
        )
    )


def test_RT_005_repeated_valid_transition_sequences_preserve_hard_invariants(
    user, make_item
):
    rng = random.Random(3609)

    roots = [make_item(user, f"Root {i}") for i in range(5)]
    children = [
        make_item(user, f"Child {i}", parent=roots[i % len(roots)])
        for i in range(5)
    ]
    items = roots + children
    priority.reconcile(user)
    _assert_all(user)

    for _ in range(80):
        item = rng.choice(items)
        item.refresh_from_db()

        op = rng.choice(("complete", "reopen", "reparent", "reconcile"))

        if op == "complete":
            hierarchy.complete_subtree(item)

        elif op == "reopen":
            hierarchy.reopen(item)

        elif op == "reparent":
            candidates = [x for x in items if x.pk != item.pk]
            target = rng.choice(candidates + [None])

            # Try the transition only when it is valid. The focused invalid
            # transition test below checks rejection behaviour.
            if target is not None:
                target.refresh_from_db()
                # Avoid knowingly choosing a descendant as the new parent.
                node = target
                descendant = False
                while node.parent_id is not None:
                    if node.parent_id == item.pk:
                        descendant = True
                        break
                    node = PlanningItem.objects.get(pk=node.parent_id)
                if descendant:
                    continue

            try:
                hierarchy.set_parent(item, target)
            except (ValidationError, ValueError):
                # A valid state machine may reject additional domain-invalid
                # combinations; rejection itself must not damage state.
                pass

        else:
            priority.reconcile(user)

        _assert_all(user)


def test_RT_006_invalid_self_parent_transition_is_atomic_and_non_poisoning(
    user, make_item
):
    item = make_item(user, "Target")
    other = make_item(user, "Other")
    priority.reconcile(user)
    before = _snapshot(user)

    with pytest.raises((ValidationError, ValueError)):
        hierarchy.set_parent(item, item)

    assert _snapshot(user) == before, (
        "RT-006: rejected self-parent transition left residue"
    )

    # Subsequent valid operations must still work normally.
    hierarchy.complete_subtree(other)
    hierarchy.reopen(other)
    priority.reconcile(user)
    _assert_all(user)


def test_RT_006_invalid_cycle_transition_is_atomic_and_non_poisoning(
    user, make_item
):
    root = make_item(user, "Root")
    child = make_item(user, "Child", parent=root)
    grandchild = make_item(user, "Grandchild", parent=child)
    priority.reconcile(user)
    before = _snapshot(user)

    with pytest.raises((ValidationError, ValueError)):
        hierarchy.set_parent(root, grandchild)

    assert _snapshot(user) == before, (
        "RT-006: rejected hierarchy cycle partially mutated canonical state"
    )

    _assert_all(user)


def test_RT_005_reconciliation_torture_is_idempotent(user, make_item):
    parent = make_item(user, "Parent")
    child = make_item(user, "Child", parent=parent)
    siblings = [make_item(user, f"Sibling {i}") for i in range(8)]

    priority.reconcile(user)
    first = _snapshot(user)

    for _ in range(100):
        priority.reconcile(user)
        _assert_all(user)

    assert _snapshot(user) == first, (
        "RT-005: repeated reconciliation accumulated semantic drift"
    )


def test_RT_006_failed_transition_does_not_break_future_inverse_round_trip(
    user, make_item
):
    a = make_item(user, "A")
    b = make_item(user, "B")
    priority.reconcile(user)

    with pytest.raises((ValidationError, ValueError)):
        hierarchy.set_parent(a, a)

    baseline = _snapshot(user)

    hierarchy.complete_subtree(b)
    hierarchy.reopen(b)
    priority.reconcile(user)

    assert _snapshot(user) == baseline, (
        "RT-006: an earlier rejected transition poisoned a later valid "
        "complete/reopen round trip"
    )
