import pytest
from planning.models import ItemType, PlanningItem
from planning.services import hierarchy, history, priority

pytestmark = pytest.mark.django_db


def ids(user):
    return list(priority.ordered(user).values_list('pk', flat=True))


def test_completed_priority_returns_between_surviving_neighbours(user, other_user, make_item):
    a, b, c = [make_item(user, title) for title in 'ABC']
    other = make_item(other_user, 'Other', priority_position=1)
    priority.reconcile(user)
    hierarchy.complete_subtree(b)
    assert ids(user) == [a.pk, c.pk]
    hierarchy.reopen(b)
    assert ids(user) == [a.pk, b.pk, c.pk]
    assert ids(other_user) == [other.pk]


def test_subtree_completion_reopening_and_deleted_anchor(user, make_item):
    root = make_item(user, 'Root', ItemType.GOAL)
    a, b, c = [make_item(user, title, parent=root) for title in 'ABC']
    priority.reconcile(user)
    hierarchy.complete_subtree(root)
    assert ids(user) == []
    hierarchy.reopen(c)
    hierarchy.reopen(a)
    hierarchy.reopen(b)
    assert ids(user) == [a.pk, b.pk, c.pk]
    hierarchy.complete_subtree(b)
    PlanningItem.objects.filter(pk=c.pk).update(is_deleted=True)
    priority.reconcile(user)
    hierarchy.reopen(b)
    assert ids(user) == [a.pk, b.pk]


def test_completion_history_and_eligibility_restoration(user, api_for, make_item):
    client = api_for(user)
    a, b, c = [make_item(user, title) for title in 'ABC']
    priority.reconcile(user)
    before = history.capture_items(user, [b.pk])
    assert client.post(f'/api/planning/items/{b.pk}/complete/', {}, format='json').status_code == 200
    after = history.capture_items(user, [b.pk])
    history.undo(user)
    assert ids(user) == [a.pk, b.pk, c.pk]
    restored = history.capture_items(user, [b.pk])
    for row in restored:
        assert row["scheduled_date"] is not None
    assert [{k: v for k, v in row.items() if k != "scheduled_date"} for row in restored] == [{k: v for k, v in row.items() if k != "scheduled_date"} for row in before]
    history.redo(user)
    assert ids(user) == [a.pk, c.pk]
    assert history.capture_items(user, [b.pk]) == after
    response = client.post(f'/api/planning/items/{b.pk}/complete/', {'completed': False}, format='json')
    assert response.status_code == 200
    assert ids(user) == [a.pk, b.pk, c.pk]


def test_parent_eligibility_history_restores_membership_and_anchors(user, api_for, make_item):
    client = api_for(user)
    parent = make_item(user, 'Parent', priority_position=1)
    other = make_item(user, 'Other', priority_position=2)
    before_create = history.capture_priority(user, include_unpositioned=True)
    response = client.post('/api/planning/items/', {
        'title': 'Child', 'item_type': 'TASK', 'parent': parent.pk,
    }, format='json')
    assert response.status_code == 201
    child_id = response.data['id']
    before_complete = history.capture_priority(user, include_unpositioned=True)
    assert client.post(f'/api/planning/items/{child_id}/complete/', {}, format='json').status_code == 200
    assert ids(user) == [parent.pk, other.pk]
    after_complete = history.capture_priority(user, include_unpositioned=True)
    history.undo(user)
    assert history.capture_priority(user, include_unpositioned=True) == before_complete
    assert ids(user) == [other.pk, child_id]
    history.redo(user)
    assert history.capture_priority(user, include_unpositioned=True) == after_complete
    history.undo(user)
    history.undo(user)
    assert history.capture_priority(user, include_unpositioned=True) == before_create
    history.redo(user)
    assert history.capture_priority(user, include_unpositioned=True) == before_complete


def test_legacy_history_with_null_estimate_uses_default(user, make_item):
    from planning.models import DurationCategory

    item = make_item(user, 'Old task')
    state = history.capture_items(user, [item.pk])
    state[0]['duration_category'] = None
    entry = history.record_checkpoint(user, 'UPDATE', {'items': state},
                                      {'items': history.capture_items(user, [item.pk])})
    assert entry is not None
    assert history.undo(user) is not None
    item.refresh_from_db()
    assert item.duration_category == DurationCategory.UNDER_1_HOUR
    assert history.redo(user) is not None
    item.refresh_from_db()
    assert item.duration_category == DurationCategory.UNDER_1_HOUR


def test_new_parent_inherits_final_child_frontier_slot(user, make_item):
    """A newly exposed parent inherits the frontier neighbourhood it replaces."""
    before = make_item(user, 'Before')
    parent = make_item(user, 'Parent', ItemType.ASSIGNMENT)
    child = make_item(user, 'Final child', parent=parent)
    after = make_item(user, 'After')

    priority.reconcile(user)

    # Establish a deterministic frontier where the child sits between neighbours.
    priority.reorder(user, before.pk, 1)
    priority.reorder(user, child.pk, 2)
    priority.reorder(user, after.pk, 3)
    assert ids(user) == [before.pk, child.pk, after.pk]

    # Parent has never itself occupied the priority frontier.
    parent.refresh_from_db()
    assert parent.priority_position is None
    assert not parent.priority_restore_context

    hierarchy.complete_subtree(child)

    # Completing the final child exposes Parent. Its logical frontier slot
    # should replace the child rather than being appended to the end.
    assert ids(user) == [before.pk, parent.pk, after.pk]


def test_non_final_child_completion_does_not_promote_parent(user, make_item):
    """Parent stays outside the frontier while another incomplete child remains."""
    before = make_item(user, 'Before')
    parent = make_item(user, 'Parent', ItemType.ASSIGNMENT)
    first = make_item(user, 'First child', parent=parent)
    remaining = make_item(user, 'Remaining child', parent=parent)
    after = make_item(user, 'After')

    priority.reconcile(user)
    priority.reorder(user, before.pk, 1)
    priority.reorder(user, first.pk, 2)
    priority.reorder(user, remaining.pk, 3)
    priority.reorder(user, after.pk, 4)

    hierarchy.complete_subtree(first)

    current = ids(user)

    assert parent.pk not in current
    assert remaining.pk in current


def test_deeply_exposed_ancestor_inherits_descendant_frontier_slot(user, make_item):
    """Frontier-slot inheritance works across more than one hierarchy level."""
    before = make_item(user, 'Before')
    ancestor = make_item(user, 'Ancestor', ItemType.ASSIGNMENT)
    middle = make_item(user, 'Middle', parent=ancestor)
    leaf = make_item(user, 'Leaf', parent=middle)
    after = make_item(user, 'After')

    priority.reconcile(user)
    priority.reorder(user, before.pk, 1)
    priority.reorder(user, leaf.pk, 2)
    priority.reorder(user, after.pk, 3)

    hierarchy.complete_subtree(leaf)
    hierarchy.complete_subtree(middle)

    assert ids(user) == [before.pk, ancestor.pk, after.pk]


def test_existing_restore_context_wins_over_descendant_context(user, make_item):
    """A returning item's own history must not be overwritten by inheritance."""
    before = make_item(user, 'Before')
    parent = make_item(user, 'Parent', ItemType.ASSIGNMENT)
    after = make_item(user, 'After')

    priority.reconcile(user)
    priority.reorder(user, parent.pk, 2)

    # Creating a child removes Parent from the frontier and records Parent's
    # own restoration context.
    child = make_item(user, 'Child', parent=parent)
    priority.reconcile(user)

    parent.refresh_from_db()
    original_context = dict(parent.priority_restore_context)
    assert original_context

    hierarchy.complete_subtree(child)

    parent.refresh_from_db()

    assert parent.priority_restore_context == original_context
    assert ids(user) == [before.pk, parent.pk, after.pk]


def test_unrelated_new_work_does_not_inherit_departing_context(user, make_item):
    """Frontier inheritance is restricted to ancestors of departing work."""
    before = make_item(user, 'Before')
    parent = make_item(user, 'Parent', ItemType.ASSIGNMENT)
    child = make_item(user, 'Child', parent=parent)
    after = make_item(user, 'After')

    priority.reconcile(user)
    priority.reorder(user, before.pk, 1)
    priority.reorder(user, child.pk, 2)
    priority.reorder(user, after.pk, 3)

    unrelated = make_item(user, 'Unrelated')
    hierarchy.complete_subtree(child)

    current = ids(user)

    assert current.index(parent.pk) == 1
    assert current.index(unrelated.pk) > current.index(after.pk)
