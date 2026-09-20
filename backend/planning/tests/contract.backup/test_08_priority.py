"""
ARC frozen-contract tests: canonical global priority transitions P1-P7.

Priority is a user preference over generally-sooner attention. It is not a
dependency, deadline, scheduled date, sibling order, or execution log.
Temporary frontier departure must preserve enough context to restore meaningful
relative order without cumulative drift.
"""

import pytest

from planning.models import PlanningItem
from planning.services import hierarchy, priority

pytestmark = pytest.mark.django_db

CONTRACT_IDS = {
    "PRI-001", "PRI-002", "PRI-003", "PRI-004",
    "PRI-005", "PRI-006", "PRI-007", "PRI-008",
}


def _order(user):
    priority.reconcile(user)
    return list(priority.ordered(user).values_list("pk", flat=True))


def test_P1_reprioritise_mutates_one_canonical_global_order(user, make_item):
    a = make_item(user, "A")
    b = make_item(user, "B")
    c = make_item(user, "C")
    priority.reconcile(user)
    assert _order(user) == [a.pk, b.pk, c.pk]

    priority.reorder(user, c.pk, 1)

    assert _order(user) == [c.pk, a.pk, b.pk]


def test_P2_completion_removes_active_position_but_preserves_restore_context(
    user, make_item
):
    a = make_item(user, "A")
    b = make_item(user, "B")
    c = make_item(user, "C")
    priority.reconcile(user)
    assert _order(user) == [a.pk, b.pk, c.pk]

    hierarchy.complete_subtree(b)
    b.refresh_from_db()

    assert b.priority_position is None
    assert b.priority_restore_context, (
        "P2: completion may remove active priority position but must preserve "
        "meaningful canonical restore context/history"
    )
    assert _order(user) == [a.pk, c.pk]


def test_P3_reopen_restores_meaningful_priority_neighbourhood(user, make_item):
    a = make_item(user, "A")
    b = make_item(user, "B")
    c = make_item(user, "C")
    priority.reconcile(user)
    initial = [a.pk, b.pk, c.pk]

    hierarchy.complete_subtree(b)
    hierarchy.reopen(b)

    assert _order(user) == initial


def test_P4_leaf_becoming_structural_does_not_destroy_parent_priority_context(
    user, make_item
):
    a = make_item(user, "A")
    parent = make_item(user, "Parent")
    z = make_item(user, "Z")
    priority.reconcile(user)
    initial = [a.pk, parent.pk, z.pk]
    assert _order(user) == initial

    child = make_item(user, "Child", parent=parent)
    priority.reconcile(user)
    parent.refresh_from_db()

    assert parent.priority_position is None
    assert parent.priority_restore_context, (
        "P4: structural departure must preserve the parent's canonical "
        "priority neighbourhood instead of forgetting where it belonged"
    )

    hierarchy.complete_subtree(child)
    assert _order(user) == initial


def test_P5_newly_exposed_ancestor_inherits_descendant_neighbourhood(user, make_item):
    before = make_item(user, "Before")
    parent = make_item(user, "Parent")
    child = make_item(user, "Child", parent=parent)
    after = make_item(user, "After")
    priority.reconcile(user)

    # Parent is structural; the active branch is Before, Child, After.
    active_before = _order(user)
    assert active_before == [before.pk, child.pk, after.pk]

    hierarchy.complete_subtree(child)

    assert _order(user) == [before.pk, parent.pk, after.pk], (
        "P5: when descendant departure exposes its ancestor, the ancestor "
        "should occupy the branch's meaningful global-priority neighbourhood"
    )


def test_P5_repeated_frontier_departure_return_has_no_cumulative_priority_drift(
    user, make_item
):
    left = make_item(user, "Left")
    parent = make_item(user, "Parent")
    right = make_item(user, "Right")
    priority.reconcile(user)
    baseline = [left.pk, parent.pk, right.pk]
    assert _order(user) == baseline

    child = make_item(user, "Child", parent=parent)
    hierarchy.complete_subtree(child)
    assert _order(user) == baseline

    hierarchy.reopen(child)
    hierarchy.complete_subtree(child)
    assert _order(user) == baseline


def test_P6_explicit_precedence_preference_is_global_priority_not_view_local_order(
    user, make_item
):
    a = make_item(user, "A")
    b = make_item(user, "B")
    priority.reconcile(user)
    assert _order(user) == [a.pk, b.pk]

    # This service is the canonical operation that Timeline/Focus must call
    # when the user's actual meaning is "B should generally precede A".
    priority.reorder(user, b.pk, 1)

    b.refresh_from_db()
    a.refresh_from_db()
    assert b.priority_position == 1
    assert a.priority_position == 2
    assert _order(user) == [b.pk, a.pk]


def test_P7_merely_executing_lower_ranked_item_first_does_not_mutate_priority(
    user, make_item
):
    a = make_item(user, "A")
    b = make_item(user, "B")
    priority.reconcile(user)
    before = _order(user)

    # "I worked on B first" is execution behaviour, not a planning command.
    # No priority service is called.
    b.refresh_from_db()
    after = _order(user)

    assert after == before


def test_priority_is_not_dependency_sibling_order_or_scheduled_date(
    user, make_item, today
):
    from datetime import timedelta

    root = make_item(user, "Root", item_type="GOAL")
    a = make_item(
        user,
        "A",
        parent=root,
        sibling_order=2,
        scheduled_date=today + timedelta(days=5),
    )
    b = make_item(
        user,
        "B",
        parent=root,
        sibling_order=1,
        scheduled_date=today,
    )
    priority.reconcile(user)

    priority.reorder(user, a.pk, 1)
    a.refresh_from_db()
    b.refresh_from_db()

    assert a.priority_position < b.priority_position
    assert a.sibling_order == 2
    assert b.sibling_order == 1
    assert a.scheduled_date == today + timedelta(days=5)
    assert b.scheduled_date == today
