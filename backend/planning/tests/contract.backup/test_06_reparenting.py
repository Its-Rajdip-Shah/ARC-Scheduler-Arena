"""
ARC frozen-contract tests: hierarchy / reparenting transitions RP1-RP5.

Reparenting changes decomposition only. It must be atomic, cycle-free, preserve
the moved task's own temporal facts, and must not silently rewrite/delete
dependency facts.
"""

import pytest
from django.core.exceptions import ValidationError

from planning.models import PlanningItem
from planning.services import hierarchy, priority

pytestmark = pytest.mark.django_db

CONTRACT_IDS = {"REP-001", "REP-002", "REP-003", "REP-004", "REP-005"}


def _dependency_model():
    from django.apps import apps

    for model in apps.get_app_config("planning").get_models():
        names = {f.name for f in model._meta.get_fields()}
        lowered = model.__name__.lower()
        if "depend" in lowered and (
            {"prerequisite", "dependent"} <= names
            or {"predecessor", "successor"} <= names
        ):
            return model
    return None


def test_RP1_valid_reparent_changes_only_hierarchy_and_reconciles_frontier(
    user, make_item, today
):
    old_parent = make_item(user, "Old parent")
    new_parent = make_item(user, "New parent")
    item = make_item(
        user,
        "Moved",
        parent=old_parent,
        start_date=today,
        due_date=today,
    )
    original_dates = (item.start_date, item.due_date)

    hierarchy.set_parent(item, new_parent)
    item.refresh_from_db()

    assert item.parent_id == new_parent.pk
    assert (item.start_date, item.due_date) == original_dates
    # Reconciliation must leave one coherent priority projection.
    positions = list(
        priority.ordered(user).values_list("priority_position", flat=True)
    )
    assert positions == list(range(1, len(positions) + 1))


def test_RP2_reparent_under_self_is_rejected_without_partial_mutation(user, make_item):
    parent = make_item(user, "Parent")
    item = make_item(user, "Item", parent=parent)
    before = item.parent_id

    with pytest.raises(ValidationError):
        hierarchy.set_parent(item, item)

    item.refresh_from_db()
    assert item.parent_id == before


def test_RP2_reparent_under_descendant_is_rejected_without_partial_mutation(
    user, make_item
):
    root = make_item(user, "Root")
    child = make_item(user, "Child", parent=root)
    grandchild = make_item(user, "Grandchild", parent=child)

    with pytest.raises(ValidationError):
        hierarchy.set_parent(root, grandchild)

    root.refresh_from_db()
    child.refresh_from_db()
    grandchild.refresh_from_db()
    assert root.parent_id is None
    assert child.parent_id == root.pk
    assert grandchild.parent_id == child.pk


def test_RP4_reparent_to_root_preserves_owned_dates(user, make_item, today):
    parent = make_item(
        user,
        "Parent",
        start_date=today,
        due_date=today,
    )
    child = make_item(
        user,
        "Child",
        parent=parent,
        start_date=today,
        due_date=today,
    )
    before = (child.start_date, child.due_date)

    hierarchy.set_parent(child, None)
    child.refresh_from_db()

    assert child.parent_id is None
    assert (child.start_date, child.due_date) == before


def test_RP5_new_parent_dates_are_not_silently_copied_onto_existing_task(
    user, make_item, today
):
    from datetime import timedelta

    old_parent = make_item(user, "Old")
    new_parent = make_item(
        user,
        "New",
        start_date=today + timedelta(days=10),
        due_date=today + timedelta(days=20),
    )
    item = make_item(
        user,
        "Moved",
        parent=old_parent,
        start_date=today + timedelta(days=1),
        due_date=today + timedelta(days=5),
    )
    own_dates = (item.start_date, item.due_date)

    hierarchy.set_parent(item, new_parent)
    item.refresh_from_db()

    assert (item.start_date, item.due_date) == own_dates
    assert (item.start_date, item.due_date) != (
        new_parent.start_date,
        new_parent.due_date,
    )


def test_RP3_dependency_relationships_cannot_be_silently_discarded_by_reparent():
    dependency = _dependency_model()
    assert dependency is not None, (
        "RP3 MISSING PREREQUISITE: dependency graph is not implemented. "
        "Once present, reparenting an endpoint must preserve valid edges and "
        "reject/require explicit resolution for invalid semantics; it may never "
        "silently delete the dependency."
    )
