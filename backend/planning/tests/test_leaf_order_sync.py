"""Leaf synchronization and reversible actions through the planning API."""
import pytest
from planning.models import ItemType, PlanningHistoryEntry, PlanningItem
from planning.services import history

pytestmark = pytest.mark.django_db


def state(user):
    return list(PlanningItem.objects.filter(user=user).order_by('pk').values_list(
        'pk', 'parent_id', 'sibling_order', 'priority_position',
    ))


def assert_roundtrip(client, user, before, after):
    for action, expected in [('undo', before), ('redo', after)]:
        response = client.post(f'/api/planning/items/{action}/', {}, format='json')
        assert response.status_code == 200, response.data
        assert response.data['changed'] is True
        assert state(user) == expected


def test_cross_root_priority_sync_preserves_mixed_container_slots_and_history(user, other_user, api_for, make_item):
    client = api_for(user)
    root_a = make_item(user, 'Root A', ItemType.GOAL, sibling_order=1)
    root_b = make_item(user, 'Root B', ItemType.GOAL, sibling_order=2)
    a1 = make_item(user, 'A1', parent=root_a, sibling_order=1, priority_position=1)
    container = make_item(user, 'Container', ItemType.GOAL, parent=root_a, sibling_order=2)
    a2 = make_item(user, 'A2', parent=root_a, sibling_order=3, priority_position=4)
    b1 = make_item(user, 'B1', parent=root_b, sibling_order=1, priority_position=2)
    b2 = make_item(user, 'B2', parent=root_b, sibling_order=2, priority_position=3)
    make_item(other_user, 'Other', sibling_order=9, priority_position=1)
    before, other_before = state(user), state(other_user)
    response = client.post('/api/planning/priority/reorder/', {
        'item_id': a2.pk, 'new_position': 1,
    }, format='json')
    assert response.status_code == 200, response.data
    assert [row['item_id'] for row in response.data] == [a2.pk, a1.pk, b1.pk, b2.pk]
    for item, expected in [(root_a, 1), (root_b, 2), (container, 2), (a2, 1), (a1, 3), (b1, 1), (b2, 2)]:
        item.refresh_from_db()
        assert item.sibling_order == expected
    tree = client.get('/api/planning/items/tree/').data
    assert [node['id'] for node in tree] == [root_a.pk, root_b.pk]
    assert [node['id'] for node in tree[0]['children']] == [a2.pk, container.pk, a1.pk]
    entry = PlanningHistoryEntry.objects.get(user=user)
    assert {s['id'] for s in entry.before_state['leaf_siblings']} == {a1.pk, a2.pk, b1.pk, b2.pk}
    assert 'siblings' not in entry.before_state
    assert_roundtrip(client, user, before, state(user))
    assert state(other_user) == other_before


@pytest.mark.parametrize('move_up', [True, False])
def test_planner_leaf_move_uses_single_global_reorder_and_history(user, other_user, api_for, make_item, move_up):
    client = api_for(user)
    root = make_item(user, 'Root', ItemType.GOAL, sibling_order=1)
    a = make_item(user, 'A', parent=root, sibling_order=1, priority_position=1)
    x = make_item(user, 'X', sibling_order=2, priority_position=2)
    y = make_item(user, 'Y', sibling_order=3, priority_position=3)
    b = make_item(user, 'B', parent=root, sibling_order=2, priority_position=4)
    make_item(other_user, 'Other', sibling_order=5, priority_position=1)
    before, other_before = state(user), state(other_user)
    moved = b if move_up else a
    response = client.post(f'/api/planning/items/{moved.pk}/move/', {
        'parent_id': root.pk, 'sibling_order': 1 if move_up else 2,
    }, format='json')
    assert response.status_code == 200, response.data
    expected = [b.pk, a.pk, x.pk, y.pk] if move_up else [x.pk, y.pk, b.pk, a.pk]
    assert [s['id'] for s in history.capture_priority(user)] == expected
    assert list(PlanningItem.objects.filter(parent=root).order_by('sibling_order')
                .values_list('pk', flat=True)) == [b.pk, a.pk]
    assert_roundtrip(client, user, before, state(user))
    assert state(other_user) == other_before


def test_parent_only_move_and_history_do_not_change_priority(user, api_for, make_item):
    client = api_for(user)
    a = make_item(user, 'A', ItemType.GOAL, sibling_order=1)
    b = make_item(user, 'B', ItemType.GOAL, sibling_order=2)
    make_item(user, 'A leaf', parent=a, sibling_order=1, priority_position=1)
    make_item(user, 'B leaf', parent=b, sibling_order=1, priority_position=2)
    before = state(user)
    priority_before = history.capture_priority(user)
    response = client.post(f'/api/planning/items/{b.pk}/move/', {
        'parent_id': None, 'sibling_order': 1,
    }, format='json')
    assert response.status_code == 200, response.data
    assert history.capture_priority(user) == priority_before
    b.refresh_from_db()
    assert b.sibling_order == 1
    entry = PlanningHistoryEntry.objects.get(user=user)
    assert set(entry.before_state) == {'siblings'}
    assert set(entry.after_state) == {'siblings'}
    assert_roundtrip(client, user, before, state(user))


def test_actionable_container_is_not_a_sync_leaf(user, api_for, make_item):
    container = make_item(user, 'Container', sibling_order=1, priority_position=2)
    make_item(user, 'Done child', parent=container, is_completed=True, sibling_order=1)
    leaf = make_item(user, 'Leaf', sibling_order=2, priority_position=1)
    before = state(user)
    response = api_for(user).post('/api/planning/priority/reorder/', {
        'item_id': container.pk, 'new_position': 1,
    }, format='json')
    assert response.status_code == 200, response.data
    container.refresh_from_db()
    leaf.refresh_from_db()
    assert (container.sibling_order, leaf.sibling_order) == (1, 2)
    assert_roundtrip(api_for(user), user, before, state(user))


def test_reparent_history_restores_eligibility_positions(user, api_for, make_item):
    client = api_for(user)
    old = make_item(user, 'Old', sibling_order=1)
    new = make_item(user, 'New', sibling_order=2, priority_position=2)
    child = make_item(user, 'Child', parent=old, sibling_order=1, priority_position=1)
    before = state(user)
    response = client.post(f'/api/planning/items/{child.pk}/move/', {
        'parent_id': new.pk, 'sibling_order': 1,
    }, format='json')
    assert response.status_code == 200, response.data
    assert [s['id'] for s in history.capture_priority(user)] == [child.pk, old.pk]
    assert_roundtrip(client, user, before, state(user))


def test_priority_history_never_restores_container_slots_even_in_leaf_payload(user, api_for, make_item):
    container = make_item(user, 'Container', sibling_order=3, priority_position=1)
    make_item(user, 'Done', parent=container, sibling_order=1, is_completed=True)
    leaf = make_item(user, 'Leaf', sibling_order=4, priority_position=2)
    before = state(user)
    history.record_checkpoint(user, 'PRIORITY', {
        'priority': [{'id': leaf.pk, 'priority_position': 1}, {'id': container.pk, 'priority_position': 2}],
        'siblings': [{'id': container.pk, 'parent_id': None, 'sibling_order': 99}],
        'leaf_siblings': [{'id': container.pk, 'sibling_order': 98}],
    }, {
        'priority': history.capture_priority(user),
        'siblings': [{'id': container.pk, 'parent_id': None, 'sibling_order': 97}],
        'leaf_siblings': [{'id': container.pk, 'sibling_order': 96}],
    })
    client = api_for(user)
    for action in ['undo', 'redo']:
        response = client.post(f'/api/planning/items/{action}/', {}, format='json')
        assert response.status_code == 200, response.data
        container.refresh_from_db()
        assert container.sibling_order == 3
    assert state(user) == before


@pytest.mark.parametrize('above', [True, False])
def test_leaf_crosses_recursive_container_boundary(user, other_user, api_for, make_item, above):
    client = api_for(user)
    root = make_item(user, 'Root', ItemType.GOAL, sibling_order=1)
    a = make_item(user, 'A', parent=root, sibling_order=1 if above else 2)
    f = make_item(user, 'F', parent=root, sibling_order=2 if above else 1)
    b = make_item(user, 'B', parent=a, sibling_order=1)
    e = make_item(user, 'E', parent=a, sibling_order=2)
    d = make_item(user, 'D', parent=a, sibling_order=3)
    d1 = make_item(user, 'D1', parent=d, sibling_order=1)
    c = make_item(user, 'C', parent=a, sibling_order=4)
    make_item(user, 'Completed', parent=a, sibling_order=5, is_completed=True)
    make_item(user, 'Deleted', parent=a, sibling_order=6, is_deleted=True)
    other_root = make_item(user, 'Other root', ItemType.GOAL, sibling_order=2)
    x, y, z = [make_item(user, title, parent=other_root, sibling_order=i)
               for i, title in enumerate(['X', 'Y', 'Z'], 1)]
    rest = [b, x, e, y, d1, c, z]
    initial = rest[:6] + [f, z] if above else [f] + rest
    for position, node in enumerate(initial, 1):
        PlanningItem.objects.filter(pk=node.pk).update(priority_position=position)
    make_item(other_user, 'Other user', priority_position=1, sibling_order=8)
    before, other_before = state(user), state(other_user)

    response = client.post(f'/api/planning/items/{f.pk}/move/', {
        'parent_id': root.pk, 'sibling_order': 1 if above else 2,
    }, format='json')
    assert response.status_code == 200, response.data
    expected = [f] + rest if above else rest[:6] + [f, z]
    assert [row['id'] for row in history.capture_priority(user)] == [node.pk for node in expected]
    a.refresh_from_db()
    d.refresh_from_db()
    assert a.priority_position is None
    assert d.priority_position is None
    assert a.sibling_order == (2 if above else 1)
    assert d.sibling_order == 3
    assert PlanningHistoryEntry.objects.filter(user=user).count() == 1
    assert_roundtrip(client, user, before, state(user))
    assert state(other_user) == other_before


def test_leaf_between_interleaved_container_boundaries(user, api_for, make_item):
    root = make_item(user, 'Root', ItemType.GOAL, sibling_order=1)
    a = make_item(user, 'A', ItemType.GOAL, parent=root, sibling_order=1)
    b = make_item(user, 'B', ItemType.GOAL, parent=root, sibling_order=2)
    leaf = make_item(user, 'Leaf', parent=root, sibling_order=3, priority_position=5)
    a1 = make_item(user, 'A1', parent=a, sibling_order=1, priority_position=1)
    b1 = make_item(user, 'B1', parent=b, sibling_order=1, priority_position=2)
    a2 = make_item(user, 'A2', parent=a, sibling_order=2, priority_position=3)
    b2 = make_item(user, 'B2', parent=b, sibling_order=2, priority_position=4)
    before = state(user)
    client = api_for(user)
    response = client.post(f'/api/planning/items/{leaf.pk}/move/', {
        'parent_id': root.pk, 'sibling_order': 2,
    }, format='json')
    assert response.status_code == 200, response.data
    assert [row['id'] for row in history.capture_priority(user)] == [a1.pk, a2.pk, leaf.pk, b1.pk, b2.pk]
    assert_roundtrip(client, user, before, state(user))
