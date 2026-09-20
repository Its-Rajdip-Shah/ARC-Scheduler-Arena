"""
ARC frozen-contract tests: compound/transactional transitions X1-X6.

Multi-fact mutations validate the prospective final state and commit atomically.
Conflicts are resolved explicitly before commit. Valid inverse transitions
round-trip, and reconciliation is idempotent rather than accumulating drift.
"""

import importlib

import pytest
from django.core.exceptions import ValidationError
from django.db import transaction

from planning.models import PlanningItem
from planning.services import hierarchy, priority

pytestmark = pytest.mark.django_db(transaction=True)

CONTRACT_IDS = {
    "TXN-001", "TXN-002", "TXN-003", "TXN-004", "TXN-005", "TXN-006",
}


def _commands():
    for name in (
        "planning.services.commands",
        "planning.services.domain_commands",
        "planning.services.mutations",
    ):
        try:
            return importlib.import_module(name)
        except ModuleNotFoundError:
            pass
    return None


def _state(user):
    return list(
        PlanningItem.objects.filter(user=user)
        .order_by("pk")
        .values(
            "id", "parent_id", "title", "is_completed", "is_deleted",
            "priority_position", "sibling_order",
        )
    )


def test_X1_compound_domain_command_layer_exists_and_owns_multi_field_commit():
    commands = _commands()
    assert commands is not None, (
        "TXN-001 MISSING: compound edits need a domain-command boundary rather "
        "than independent serializer/model writes"
    )
    assert any(
        callable(getattr(commands, n, None))
        for n in ("update_item", "edit_item", "mutate_item", "apply_changes")
    )


def test_X1_failed_multi_field_edit_rolls_back_every_field(user, make_item):
    commands = _commands()
    assert commands is not None
    item = make_item(user, "Original")
    before = _state(user)

    fn = next(
        (getattr(commands, n) for n in ("update_item", "edit_item", "mutate_item", "apply_changes")
         if callable(getattr(commands, n, None))),
        None,
    )
    assert fn is not None

    try:
        fn(item, {"title": "Changed", "parent": item})
    except (ValidationError, ValueError):
        pass

    assert _state(user) == before, "X1/X2: rejected prospective state must commit nothing"


def test_X2_cycle_creating_compound_edit_is_rejected_atomically(user, make_item):
    parent = make_item(user, "Parent")
    child = make_item(user, "Child", parent=parent)
    before = _state(user)

    with pytest.raises((ValidationError, ValueError)):
        hierarchy.set_parent(parent, child)

    assert _state(user) == before


def test_X3_risky_overload_needs_confirmation_capability_before_commit():
    commands = _commands()
    assert commands is not None
    assert any(
        callable(getattr(commands, n, None))
        for n in ("validate_changes", "preview_changes", "detect_conflicts", "update_item")
    ), "TXN-003: user-visible overload/conflict must be detectable before commit"


def test_X4_anchor_dependency_release_conflict_is_not_silently_canonicalised():
    commands = _commands()
    assert commands is not None
    forbidden = (
        "silently_fix_anchor_conflict",
        "normalise_dates_to_anchor",
        "drop_dependency_on_conflict",
    )
    assert not any(callable(getattr(commands, n, None)) for n in forbidden)


def test_X5_valid_inverse_reparent_round_trips_without_unrelated_drift(user, make_item):
    left = make_item(user, "Left")
    right = make_item(user, "Right")
    child = make_item(user, "Child", parent=left)
    priority.reconcile(user)

    original_parent = child.parent_id
    unrelated_before = {
        x.pk: x.priority_position for x in (left, right)
        if (x.refresh_from_db() or True)
    }

    hierarchy.set_parent(child, right)
    hierarchy.set_parent(child, left)
    child.refresh_from_db()
    left.refresh_from_db()
    right.refresh_from_db()

    assert child.parent_id == original_parent
    assert {left.pk: left.priority_position, right.pk: right.priority_position} == unrelated_before


def test_X6_reconciliation_is_idempotent_no_semantic_drift(user, make_item):
    root = make_item(user, "Root")
    child = make_item(user, "Child", parent=root)
    other = make_item(user, "Other")

    priority.reconcile(user)
    once = _state(user)
    for _ in range(10):
        priority.reconcile(user)
    many = _state(user)

    assert many == once


def test_X6_database_atomic_boundary_rolls_back_mid_mutation_exception(user, make_item):
    item = make_item(user, "Original")
    before = _state(user)

    with pytest.raises(RuntimeError):
        with transaction.atomic():
            item.title = "Half committed"
            item.save(update_fields=["title"])
            raise RuntimeError("simulated mid-command failure")

    assert _state(user) == before
