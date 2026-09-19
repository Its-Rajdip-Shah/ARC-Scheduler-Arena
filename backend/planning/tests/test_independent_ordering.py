"""Container organisation is independent; eligible sibling leaves share priority order."""

import pytest

from planning.models import ItemType, PlanningHistoryEntry, PlanningItem
from planning.services import history

pytestmark = pytest.mark.django_db


def sibling_state(user):
    return list(PlanningItem.objects.filter(user=user).order_by('pk').values_list(
        'pk', 'parent_id', 'sibling_order',
    ))


def planner_order(client):
    response = client.get('/api/planning/items/tree/')
    assert response.status_code == 200, response.data

    def structure(nodes):
        return [(node['id'], node['sibling_order'], structure(node['children'])) for node in nodes]

    return structure(response.data)


def test_priority_reorder_and_history_leave_containers_unchanged(user, other_user, api_for, make_item):
    client = api_for(user)
    root_z = make_item(user, 'Z root', ItemType.GOAL, sibling_order=1)
    root_a = make_item(user, 'A root', ItemType.GOAL, sibling_order=2)
    first = make_item(user, 'First', parent=root_a, sibling_order=1, priority_position=1)
    second = make_item(user, 'Second', parent=root_z, sibling_order=1, priority_position=2)
    third = make_item(user, 'Third', parent=root_a, sibling_order=2, priority_position=3)
    make_item(other_user, 'Other', sibling_order=7, priority_position=1)
    siblings_before = sibling_state(user)
    other_before = list(PlanningItem.objects.filter(user=other_user).values())
    tree_before = planner_order(client)
    before = history.capture_priority(user)

    response = client.post('/api/planning/priority/reorder/', {
        'item_id': third.pk, 'new_position': 1,
    }, format='json')
    assert response.status_code == 200, response.data
    assert [(row['item_id'], row['position']) for row in response.data] == [
        (third.pk, 1), (first.pk, 2), (second.pk, 3),
    ]
    after = history.capture_priority(user)
    assert after == [
        {'id': third.pk, 'priority_position': 1},
        {'id': first.pk, 'priority_position': 2},
        {'id': second.pk, 'priority_position': 3},
    ]
    entry = PlanningHistoryEntry.objects.get(user=user)
    assert entry.action_type == 'PRIORITY'
    assert entry.before_state['priority'] == before
    assert entry.after_state['priority'] == after
    assert 'leaf_siblings' in entry.before_state
    siblings_after = sibling_state(user)
    tree_after = planner_order(client)
    assert siblings_after != siblings_before
    assert tree_after[1][2][0][0] == third.pk
    assert [(node[0], node[1]) for node in tree_after] == [(node[0], node[1]) for node in tree_before]

    for action, expected, undone in [('undo', before, True), ('redo', after, False)]:
        response = client.post(f'/api/planning/items/{action}/', {}, format='json')
        assert response.status_code == 200, response.data
        assert response.data['changed'] is True
        assert response.data['action_type'] == 'PRIORITY'
        assert history.capture_priority(user) == expected
        assert sibling_state(user) == (siblings_before if undone else siblings_after)
        assert planner_order(client) == (tree_before if undone else tree_after)
        assert list(PlanningItem.objects.filter(user=other_user).values()) == other_before
        entry.refresh_from_db()
        assert entry.is_undone is undone
    assert PlanningHistoryEntry.objects.filter(user=user).count() == 1
    assert not PlanningHistoryEntry.objects.filter(user=other_user).exists()


@pytest.mark.parametrize('reparent', [False, True])
def test_planner_leaf_move_updates_only_required_priority(
    user, api_for, make_item, reparent,
):
    client = api_for(user)
    root = make_item(user, 'Root', ItemType.GOAL, sibling_order=1)
    destination = make_item(user, 'Destination', ItemType.GOAL, sibling_order=2) if reparent else root
    first = make_item(user, 'Alpha', parent=root, sibling_order=1, priority_position=1)
    last = make_item(user, 'Zulu', parent=root, sibling_order=2, priority_position=2)
    priority_before = history.capture_priority(user)

    response = client.post(f'/api/planning/items/{last.pk}/move/', {
        'parent_id': destination.pk, 'sibling_order': 1,
    }, format='json')
    assert response.status_code == 200, response.data
    last.refresh_from_db()
    assert (last.parent_id, last.sibling_order) == (destination.pk, 1)
    response = client.get('/api/planning/items/tree/')
    assert response.status_code == 200
    node = next(node for node in response.data if node['id'] == destination.pk)
    assert [child['id'] for child in node['children']] == (
        [last.pk] if reparent else [last.pk, first.pk]
    )
    assert history.capture_priority(user) == (priority_before if reparent else [
        {'id': last.pk, 'priority_position': 1},
        {'id': first.pk, 'priority_position': 2},
    ])


def test_create_complete_reopen_and_delete_reconcile_parent_eligibility(user, api_for, make_item):
    client = api_for(user)
    parent = make_item(user, 'Parent', priority_position=1)
    existing = make_item(user, 'Existing', priority_position=2)

    def assert_priority(*items):
        assert history.capture_priority(user) == [
            {'id': item_id, 'priority_position': position}
            for position, item_id in enumerate(items, start=1)
        ]
        assert set(PlanningItem.objects.for_user(user).priority_eligible()
                   .values_list('pk', flat=True)) == set(items)
        parent.refresh_from_db()
        assert parent.is_completed is False
        assert parent.priority_position == (items.index(parent.pk) + 1 if parent.pk in items else None)

    response = client.post('/api/planning/items/', {
        'title': 'Child', 'item_type': 'TASK', 'parent': parent.pk,
    }, format='json')
    assert response.status_code == 201, response.data
    child_id = response.data['id']
    assert_priority(existing.pk, child_id)

    for completed, expected in [(True, (parent.pk, existing.pk)), (False, (existing.pk, child_id))]:
        response = client.post(f'/api/planning/items/{child_id}/complete/', {
            'completed': completed,
        }, format='json')
        assert response.status_code == 200, response.data
        assert_priority(*expected)

    response = client.delete(f'/api/planning/items/{child_id}/')
    assert response.status_code == 204
    assert_priority(parent.pk, existing.pk)


def test_reparent_reconciles_both_parents_and_preserves_remaining_priority_order(user, api_for, make_item):
    old_parent = make_item(user, 'Old parent')
    new_parent = make_item(user, 'New parent', priority_position=2)
    child = make_item(user, 'Child', parent=old_parent, priority_position=1)
    existing = make_item(user, 'Existing', priority_position=3)

    response = api_for(user).post(f'/api/planning/items/{child.pk}/move/', {
        'parent_id': new_parent.pk, 'sibling_order': 1,
    }, format='json')
    assert response.status_code == 200, response.data
    assert history.capture_priority(user) == [
        {'id': child.pk, 'priority_position': 1},
        {'id': existing.pk, 'priority_position': 2},
        {'id': old_parent.pk, 'priority_position': 3},
    ]
    new_parent.refresh_from_db()
    old_parent.refresh_from_db()
    assert new_parent.priority_position is None
    assert old_parent.is_completed is False
