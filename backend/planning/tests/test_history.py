import pytest

from planning.models import PlanningHistoryEntry, PlanningItem
from planning.services import history


pytestmark = pytest.mark.django_db


def make_item(user, title, parent=None, sibling_order=0, completed=False):
    return PlanningItem.objects.create(
        user=user,
        title=title,
        item_type="TASK",
        parent=parent,
        sibling_order=sibling_order,
        is_completed=completed,
    )


def checkpoint(user, action, before, after):
    return history.record_checkpoint(user, action, before, after)


@pytest.mark.parametrize("action_type", ["PRIORITY", "MOVE"])
def test_legacy_priority_history_ignores_siblings_but_move_restores_them(user, action_type):
    first = make_item(user, "First", sibling_order=10)
    second = make_item(user, "Second", sibling_order=20)
    PlanningItem.objects.filter(pk=first.pk).update(priority_position=2)
    PlanningItem.objects.filter(pk=second.pk).update(priority_position=1)
    before = {
        "priority": [
            {"id": first.pk, "priority_position": 1},
            {"id": second.pk, "priority_position": 2},
        ],
        "siblings": [
            {"id": first.pk, "parent_id": None, "sibling_order": 2},
            {"id": second.pk, "parent_id": None, "sibling_order": 1},
        ],
    }
    after = {
        "priority": history.capture_priority(user),
        "siblings": [
            {"id": first.pk, "parent_id": None, "sibling_order": 1},
            {"id": second.pk, "parent_id": None, "sibling_order": 2},
        ],
    }
    entry = checkpoint(user, action_type, before, after)

    for restore, expected, undone in [(history.undo, before, True), (history.redo, after, False)]:
        assert restore(user).pk == entry.pk
        assert history.capture_priority(user) == expected["priority"]
        first.refresh_from_db()
        second.refresh_from_db()
        assert (first.parent_id, second.parent_id) == (None, None)
        assert (first.sibling_order, second.sibling_order) == (
            (10, 20) if action_type == "PRIORITY" else
            tuple(state["sibling_order"] for state in expected["siblings"])
        )
        entry.refresh_from_db()
        assert entry.is_undone is undone
        assert entry.before_state == before
        assert entry.after_state == after


def test_update_undo_redo(user):
    item = make_item(user, "Before")

    before = history.capture_items(user, [item.pk])

    item.title = "After"
    item.save(update_fields=["title"])

    after = history.capture_items(user, [item.pk])
    checkpoint(user, "UPDATE", {"items": before}, {"items": after})

    history.undo(user)
    item.refresh_from_db()
    assert item.title == "Before"

    history.redo(user)
    item.refresh_from_db()
    assert item.title == "After"


def test_create_undo_redo(user):
    item = make_item(user, "Created")
    item_id = item.pk

    created = history.capture_items(user, [item_id])

    checkpoint(
        user,
        "CREATE",
        {"delete_ids": [item_id]},
        {"items": created},
    )

    history.undo(user)
    assert not PlanningItem.objects.filter(pk=item_id).exists()

    history.redo(user)
    restored = PlanningItem.objects.get(pk=item_id)
    assert restored.title == "Created"


def test_delete_subtree_undo_redo(user):
    parent = make_item(user, "Parent")
    child = make_item(user, "Child", parent=parent)

    ids = [parent.pk, child.pk]

    # DELETE now preserves the actual rows and hides them.
    PlanningItem.objects.filter(pk__in=ids).update(is_deleted=True)

    checkpoint(
        user,
        "DELETE",
        {
            "soft_delete": {
                "ids": ids,
                "value": False,
            },
        },
        {
            "soft_delete": {
                "ids": ids,
                "value": True,
            },
        },
    )

    assert PlanningItem.objects.filter(
        pk__in=ids,
        is_deleted=True,
    ).count() == 2

    history.undo(user)

    restored_parent = PlanningItem.objects.get(pk=parent.pk)
    restored_child = PlanningItem.objects.get(pk=child.pk)

    assert restored_parent.is_deleted is False
    assert restored_child.is_deleted is False
    assert restored_child.parent_id == restored_parent.pk

    history.redo(user)

    assert PlanningItem.objects.filter(
        pk__in=ids,
        is_deleted=True,
    ).count() == 2


def test_move_undo_redo(user):
    root_a = make_item(user, "A", sibling_order=0)
    root_b = make_item(user, "B", sibling_order=1)
    child = make_item(user, "Child", parent=root_a, sibling_order=0)

    before = history.capture_items(user, [child.pk])

    child.parent = root_b
    child.sibling_order = 0
    child.save(update_fields=["parent", "sibling_order"])

    after = history.capture_items(user, [child.pk])

    checkpoint(
        user,
        "MOVE",
        {"items": before},
        {"items": after},
    )

    history.undo(user)
    child.refresh_from_db()
    assert child.parent_id == root_a.pk

    history.redo(user)
    child.refresh_from_db()
    assert child.parent_id == root_b.pk


def test_completion_states_undo_redo(user):
    parent = make_item(user, "Parent", completed=False)
    child = make_item(user, "Child", parent=parent, completed=False)

    ids = [parent.pk, child.pk]
    before = history.capture_items(user, ids)

    PlanningItem.objects.filter(pk__in=ids).update(is_completed=True)

    after = history.capture_items(user, ids)

    checkpoint(
        user,
        "COMPLETE",
        {"items": before},
        {"items": after},
    )

    history.undo(user)

    assert not PlanningItem.objects.get(pk=parent.pk).is_completed
    assert not PlanningItem.objects.get(pk=child.pk).is_completed

    history.redo(user)

    assert PlanningItem.objects.get(pk=parent.pk).is_completed
    assert PlanningItem.objects.get(pk=child.pk).is_completed


def test_new_action_after_undo_discards_redo_branch(user):
    item = make_item(user, "A")

    before_a = history.capture_items(user, [item.pk])
    item.title = "B"
    item.save(update_fields=["title"])
    after_b = history.capture_items(user, [item.pk])

    checkpoint(user, "UPDATE", {"items": before_a}, {"items": after_b})

    history.undo(user)

    item.refresh_from_db()
    before_c = history.capture_items(user, [item.pk])

    item.title = "C"
    item.save(update_fields=["title"])
    after_c = history.capture_items(user, [item.pk])

    checkpoint(user, "UPDATE", {"items": before_c}, {"items": after_c})

    assert not PlanningHistoryEntry.objects.filter(
        user=user,
        is_undone=True,
    ).exists()

    assert history.redo(user) is None


def test_history_is_capped_at_100(user):
    item = make_item(user, "Start")

    for i in range(105):
        before = history.capture_items(user, [item.pk])

        item.title = f"Edit {i}"
        item.save(update_fields=["title"])

        after = history.capture_items(user, [item.pk])

        checkpoint(
            user,
            "UPDATE",
            {"items": before},
            {"items": after},
        )

    assert PlanningHistoryEntry.objects.filter(user=user).count() == 100


def test_history_status(user):
    item = make_item(user, "A")

    before = history.capture_items(user, [item.pk])
    item.title = "B"
    item.save(update_fields=["title"])
    after = history.capture_items(user, [item.pk])

    checkpoint(user, "UPDATE", {"items": before}, {"items": after})

    assert history.history_status(user) == {
        "can_undo": True,
        "can_redo": False,
    }

    history.undo(user)

    assert history.history_status(user) == {
        "can_undo": False,
        "can_redo": True,
    }


def test_discarded_redo_delete_does_not_remove_restored_rows(user):
    parent = make_item(user, "Parent")
    child = make_item(user, "Child", parent=parent)
    ids = [parent.pk, child.pk]

    PlanningItem.objects.filter(pk__in=ids).update(is_deleted=True)

    checkpoint(
        user,
        "DELETE",
        {
            "soft_delete": {"ids": ids, "value": False},
        },
        {
            "soft_delete": {"ids": ids, "value": True},
        },
    )

    # Restore subtree; DELETE checkpoint is now on redo branch.
    history.undo(user)

    assert PlanningItem.objects.filter(
        pk__in=ids,
        is_deleted=False,
    ).count() == 2

    # New action destroys redo branch and triggers GC.
    other = make_item(user, "Other")

    before = history.capture_items(user, [other.pk])
    other.title = "Changed"
    other.save(update_fields=["title"])
    after = history.capture_items(user, [other.pk])

    checkpoint(
        user,
        "UPDATE",
        {"items": before},
        {"items": after},
    )

    # Because the deleted subtree had been restored, GC must keep it.
    assert PlanningItem.objects.filter(pk__in=ids).count() == 2


def test_pruned_delete_hard_deletes_still_deleted_rows(user):
    doomed = make_item(user, "Doomed")
    doomed_id = doomed.pk

    PlanningItem.objects.filter(pk=doomed_id).update(is_deleted=True)

    checkpoint(
        user,
        "DELETE",
        {
            "soft_delete": {
                "ids": [doomed_id],
                "value": False,
            },
        },
        {
            "soft_delete": {
                "ids": [doomed_id],
                "value": True,
            },
        },
    )

    other = make_item(user, "Other")

    # Push the DELETE checkpoint beyond the 100-entry history boundary.
    for i in range(100):
        before = history.capture_items(user, [other.pk])

        other.title = f"Change {i}"
        other.save(update_fields=["title"])

        after = history.capture_items(user, [other.pk])

        checkpoint(
            user,
            "UPDATE",
            {"items": before},
            {"items": after},
        )

    assert PlanningHistoryEntry.objects.filter(user=user).count() == 100

    # DELETE checkpoint is gone and its row was still soft-deleted,
    # therefore it is now permanently unreachable and should be gone.
    assert not PlanningItem.objects.filter(pk=doomed_id).exists()
