"""Cycle prevention and cascade completion (FR-06, FR-08)."""

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from planning.models import ItemType, PlanningItem
from planning.services import hierarchy

pytestmark = pytest.mark.django_db


# --------------------------------------------------------------------------
# Cycle prevention (FR-06)
# --------------------------------------------------------------------------

def test_a_root_parent_is_always_allowed(chain):
    a, _, _ = chain
    assert hierarchy.validate_parent(a, None) is None


def test_a_normal_nesting_is_allowed(user, make_item, chain):
    a, _, c = chain
    loose = make_item(user, 'loose')
    assert hierarchy.validate_parent(loose, c) is None


def test_an_item_cannot_be_its_own_parent(chain):
    a, _, _ = chain
    with pytest.raises(ValidationError, match='its own parent'):
        hierarchy.validate_parent(a, a)


def test_an_item_cannot_move_under_its_direct_child(chain):
    a, b, _ = chain
    with pytest.raises(ValidationError, match='its own ancestor'):
        hierarchy.validate_parent(a, b)


def test_an_item_cannot_move_under_a_distant_descendant(chain):
    """The a -> b -> c -> a case: c is two levels below a, so parenting a
    under c would close the loop."""
    a, _, c = chain
    with pytest.raises(ValidationError, match='its own ancestor'):
        hierarchy.validate_parent(a, c)


def test_a_middle_item_cannot_move_under_its_own_descendant(chain):
    _, b, c = chain
    with pytest.raises(ValidationError, match='its own ancestor'):
        hierarchy.validate_parent(b, c)


def test_a_descendant_may_move_up_to_the_root(chain):
    a, _, c = chain
    assert hierarchy.validate_parent(c, a) is None


def test_an_item_cannot_be_parented_under_another_users_item(user, other_user, make_item):
    mine = make_item(user, 'mine')
    theirs = make_item(other_user, 'theirs')
    with pytest.raises(ValidationError, match="another user's item"):
        hierarchy.validate_parent(mine, theirs)


def test_an_unsaved_item_can_be_parented_anywhere_in_its_own_tree(user, chain):
    a, _, c = chain
    fresh = PlanningItem(user=user, title='fresh', item_type=ItemType.TASK)
    assert hierarchy.validate_parent(fresh, c) is None


def test_nesting_deeper_than_max_depth_is_refused(user, make_item, monkeypatch):
    monkeypatch.setattr(hierarchy, 'MAX_DEPTH', 4)
    parent = None
    for index in range(4):
        parent = make_item(user, f'level-{index}', ItemType.GOAL, parent=parent)

    with pytest.raises(ValidationError, match='levels deep'):
        hierarchy.validate_parent(make_item(user, 'too-deep'), parent)


def test_the_database_refuses_a_self_parent_even_without_the_service(chain):
    """The check constraint is the backstop if a future code path forgets to
    call validate_parent."""
    a, _, _ = chain
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            PlanningItem.objects.filter(pk=a.pk).update(parent_id=a.pk)


# --------------------------------------------------------------------------
# set_parent and sibling ordering
# --------------------------------------------------------------------------

def test_set_parent_moves_the_item_and_renumbers_both_sides(user, make_item):
    left = make_item(user, 'left', ItemType.GOAL)
    right = make_item(user, 'right', ItemType.GOAL)
    first = make_item(user, 'first', parent=left)
    second = make_item(user, 'second', parent=left)

    hierarchy.set_parent(first, right)

    first.refresh_from_db()
    second.refresh_from_db()
    assert first.parent_id == right.pk
    # 'second' was number 2 and is now the only child, so it becomes 1.
    assert second.sibling_order == 1
    assert first.sibling_order == 1


def test_set_parent_refuses_a_cycle(chain):
    a, _, c = chain
    with pytest.raises(ValidationError):
        hierarchy.set_parent(a, c)
    a.refresh_from_db()
    assert a.parent_id is None


def test_reindex_siblings_closes_gaps(user, make_item):
    root = make_item(user, 'root', ItemType.GOAL)
    children = [make_item(user, f'child-{i}', parent=root) for i in range(4)]
    PlanningItem.objects.filter(pk=children[1].pk).update(sibling_order=99)

    hierarchy.reindex_siblings(user, root)

    orders = list(
        PlanningItem.objects.filter(parent=root).order_by('sibling_order')
        .values_list('sibling_order', flat=True)
    )
    assert orders == [1, 2, 3, 4]


def test_reindex_siblings_handles_roots(user, make_item):
    make_item(user, 'r1', ItemType.GOAL)
    second = make_item(user, 'r2', ItemType.GOAL)
    PlanningItem.objects.filter(pk=second.pk).update(sibling_order=50)

    hierarchy.reindex_siblings(user, None)

    orders = list(
        PlanningItem.objects.filter(parent=None).order_by('sibling_order')
        .values_list('sibling_order', flat=True)
    )
    assert orders == [1, 2]


# --------------------------------------------------------------------------
# Cascade completion (FR-08)
# --------------------------------------------------------------------------

def test_completing_a_parent_completes_every_descendant(user, make_item):
    root = make_item(user, 'root', ItemType.GOAL)
    mid = make_item(user, 'mid', ItemType.GOAL, parent=root)
    leaf = make_item(user, 'leaf', parent=mid)
    sibling_leaf = make_item(user, 'sibling-leaf', parent=root)

    hierarchy.complete_subtree(root)

    for item in (root, mid, leaf, sibling_leaf):
        item.refresh_from_db()
        assert item.is_completed is True


def test_completing_a_subtree_leaves_the_rest_alone(user, make_item):
    root = make_item(user, 'root', ItemType.GOAL)
    inside = make_item(user, 'inside', parent=root)
    outside = make_item(user, 'outside')

    hierarchy.complete_subtree(root)

    inside.refresh_from_db()
    outside.refresh_from_db()
    assert inside.is_completed is True
    assert outside.is_completed is False


def test_completing_a_task_releases_its_priority_position(user, make_item):
    from planning.services import priority

    first = make_item(user, 'first')
    second = make_item(user, 'second')
    third = make_item(user, 'third')
    for task in (first, second, third):
        priority.assign_initial_position(task)

    hierarchy.complete_subtree(second)

    second.refresh_from_db()
    assert second.priority_position is None
    # The survivors close the gap rather than leaving a hole at 2.
    assert sorted(
        PlanningItem.objects.for_user(user)
        .exclude(priority_position=None)
        .values_list('priority_position', flat=True)
    ) == [1, 2]


def test_completion_does_not_cross_into_another_user(user, other_user, make_item):
    mine = make_item(user, 'shared-title', ItemType.GOAL)
    theirs = make_item(other_user, 'shared-title', ItemType.GOAL)

    hierarchy.complete_subtree(mine)

    theirs.refresh_from_db()
    assert theirs.is_completed is False


def test_reopening_restores_a_priority_position(user, make_item):
    from planning.services import priority

    task = make_item(user, 'task')
    priority.assign_initial_position(task)
    hierarchy.complete_subtree(task)

    hierarchy.reopen(task)

    task.refresh_from_db()
    assert task.is_completed is False
    assert task.priority_position == 1


def test_reopening_a_parent_does_not_reopen_its_children(user, make_item):
    root = make_item(user, 'root', ItemType.GOAL)
    child = make_item(user, 'child', parent=root)
    hierarchy.complete_subtree(root)

    hierarchy.reopen(root)

    root.refresh_from_db()
    child.refresh_from_db()
    assert root.is_completed is False
    assert child.is_completed is True
