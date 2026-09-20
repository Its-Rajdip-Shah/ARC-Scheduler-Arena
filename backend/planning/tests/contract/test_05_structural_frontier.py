
from .conftest import covers
"""
ARC frozen-contract tests: leaf <-> structural / frontier transitions H1-H7.

The hierarchy is decomposition; the execution frontier is derived. Structural
parents are not independently scheduled while unfinished required children
exist. When a structural episode ends, the parent may return as residual
closure work without corrupting original scope, priority context, or anchors.
"""

import pytest

from planning.models import PlanningItem
from planning.services import hierarchy, priority

pytestmark = pytest.mark.django_db

# Coverage-manifest claims for this module.
CONTRACT_IDS = {
    "HIE-001", "HIE-002", "HIE-003", "HIE-004",
    "HIE-005", "HIE-006", "HIE-007", "HIE-008",
}


def _fields():
    return {f.name for f in PlanningItem._meta.get_fields()}


def _frontier_ids(user):
    priority.reconcile(user)
    return set(priority.ordered(user).values_list("pk", flat=True))


def _anchor_field():
    return "manual_requested_date" if "manual_requested_date" in _fields() else None


@covers('HIE-003')
def test_H1_first_unfinished_child_makes_parent_structural_non_frontier(user, make_item):
    parent = make_item(user, "Parent")
    priority.reconcile(user)
    assert parent.pk in _frontier_ids(user)

    child = make_item(user, "Required child", parent=parent)
    priority.reconcile(user)

    assert parent.pk not in _frontier_ids(user)
    assert child.pk in _frontier_ids(user)


@covers('HIE-004', 'HIE-005', 'HIE-008')
def test_H2_finishing_last_required_child_exposes_parent_as_residual_frontier(
    user, make_item
):
    parent = make_item(user, "Parent")
    child = make_item(user, "Child", parent=parent)
    priority.reconcile(user)
    assert parent.pk not in _frontier_ids(user)

    hierarchy.complete_subtree(child)
    parent.refresh_from_db()
    child.refresh_from_db()

    assert child.is_completed is True
    assert parent.is_completed is False
    assert parent.pk in _frontier_ids(user), (
        "H2: once no unfinished required child remains, an unfinished parent "
        "must be eligible as residual closure work"
    )


@covers('HIE-004')
def test_H3_completing_residual_parent_removes_it_from_frontier(user, make_item):
    parent = make_item(user, "Parent")
    child = make_item(user, "Child", parent=parent)
    hierarchy.complete_subtree(child)
    assert parent.pk in _frontier_ids(user)

    hierarchy.complete_subtree(parent)
    parent.refresh_from_db()

    assert parent.is_completed is True
    assert parent.pk not in _frontier_ids(user)


@covers('HIE-006')
def test_H4_reopening_child_restructuralises_residual_parent_without_reopening_parent(
    user, make_item
):
    parent = make_item(user, "Parent")
    child = make_item(user, "Child", parent=parent)
    hierarchy.complete_subtree(child)
    priority.reconcile(user)
    assert parent.pk in _frontier_ids(user)

    hierarchy.reopen(child)
    parent.refresh_from_db()
    child.refresh_from_db()

    assert child.is_completed is False
    assert parent.is_completed is False
    assert parent.pk not in _frontier_ids(user)
    assert child.pk in _frontier_ids(user)


def test_H4_structural_round_trip_preserves_original_duration_category(user, make_item):
    parent = make_item(user, "Parent", duration_category="UNDER_4_HOURS")
    original = parent.duration_category
    child = make_item(user, "Child", parent=parent)

    hierarchy.complete_subtree(child)
    hierarchy.reopen(child)
    hierarchy.complete_subtree(child)

    parent.refresh_from_db()
    assert parent.duration_category == original, (
        "H4/H5: structural episodes must not overwrite the user's original "
        "scope estimate with residual scheduling effort"
    )


@covers('HIE-007')
def test_H5_repeated_structural_episodes_do_not_accumulate_priority_drift(user, make_item):
    before = make_item(user, "Before")
    parent = make_item(user, "Parent")
    after = make_item(user, "After")
    priority.reconcile(user)
    initial = list(priority.ordered(user).values_list("pk", flat=True))
    assert initial == [before.pk, parent.pk, after.pk]

    child = make_item(user, "Child", parent=parent)
    priority.reconcile(user)
    hierarchy.complete_subtree(child)
    first_return = list(priority.ordered(user).values_list("pk", flat=True))

    hierarchy.reopen(child)
    priority.reconcile(user)
    hierarchy.complete_subtree(child)
    second_return = list(priority.ordered(user).values_list("pk", flat=True))

    assert first_return == initial
    assert second_return == initial, (
        "H5: repeated leaf->structural->leaf cycles must not progressively "
        "move the parent through global priority"
    )


def test_H6_anchored_leaf_becoming_structural_preserves_parent_anchor_and_inherits_child(
    user, make_item, today
):
    field = _anchor_field()
    assert field is not None, (
        "H6 MISSING PREREQUISITE: canonical manual_requested_date/anchor "
        "must exist before anchor suspension/inheritance can be implemented"
    )

    parent = make_item(user, "Anchored parent")
    setattr(parent, field, today)
    parent.save(update_fields=[field])

    child = make_item(user, "Child", parent=parent)
    parent.refresh_from_db()
    child.refresh_from_db()

    assert getattr(parent, field) == today, (
        "H6: becoming structural suspends the parent's anchor semantics; "
        "it must not erase the canonical user intent"
    )
    assert getattr(child, field) == today, (
        "H6: required children created under an anchored parent inherit "
        "that anchored date intent"
    )
    assert parent.pk not in _frontier_ids(user)


@covers('HIE-008')
def test_H7_reversing_anchored_structural_transition_restores_parent_intent(
    user, make_item, today
):
    field = _anchor_field()
    assert field is not None, (
        "H7 MISSING PREREQUISITE: canonical manual_requested_date/anchor"
    )

    parent = make_item(user, "Anchored parent")
    setattr(parent, field, today)
    parent.save(update_fields=[field])
    child = make_item(user, "Temporary child", parent=parent)
    setattr(child, field, today)
    child.save(update_fields=[field])

    # Reverse the structural episode without any unrelated planning mutation.
    hierarchy.complete_subtree(child)
    parent.refresh_from_db()

    assert parent.pk in _frontier_ids(user)
    assert getattr(parent, field) == today, (
        "H7: a valid inverse structural transition should restore the parent's "
        "prior anchor semantics as closely as current time permits"
    )
