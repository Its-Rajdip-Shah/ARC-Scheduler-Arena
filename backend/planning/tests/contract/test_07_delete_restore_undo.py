
from .conftest import covers
"""
ARC frozen-contract tests: delete / restore / undo transitions D1-D10.

Deletion is a tombstone/lifecycle mutation, not semantic amnesia. Restore and
undo are validated against the present world and must never resurrect dangling,
cyclic, expired, or otherwise contradictory state silently.
"""

import pytest

from planning.models import PlanningItem
from planning.services import priority

pytestmark = pytest.mark.django_db

CONTRACT_IDS = {
    "DEL-001", "DEL-002", "DEL-003",
    "DEL-004", "DEL-005", "DEL-006",
}


def _active_ids(user):
    return set(
        PlanningItem.objects.filter(user=user, is_deleted=False)
        .values_list("pk", flat=True)
    )


def _service_callable(*names):
    """Find a domain-level lifecycle command if implementation has landed."""
    import importlib

    for module_name in (
        "planning.services.hierarchy",
        "planning.services.history",
        "planning.services.lifecycle",
        "planning.services.deletion",
    ):
        try:
            module = importlib.import_module(module_name)
        except ModuleNotFoundError:
            continue
        for name in names:
            fn = getattr(module, name, None)
            if callable(fn):
                return fn
    return None


def _dependency_model():
    from django.apps import apps

    for model in apps.get_app_config("planning").get_models():
        names = {f.name for f in model._meta.get_fields()}
        if "depend" in model.__name__.lower() and (
            {"prerequisite", "dependent"} <= names
            or {"predecessor", "successor"} <= names
        ):
            return model
    return None


@covers('DEL-001')
def test_D1_tombstoned_task_leaves_active_projection_but_identity_and_history_survive(
    user, make_item
):
    item = make_item(user, "Delete me")
    pk = item.pk

    PlanningItem.objects.filter(pk=pk).update(is_deleted=True)
    priority.reconcile(user)

    assert pk not in _active_ids(user)
    stored = PlanningItem.objects.get(pk=pk)
    assert stored.pk == pk
    assert stored.title == "Delete me"
    assert stored.is_deleted is True
    assert stored.priority_position is None


@covers('DEL-002')
def test_D2_subtree_delete_requires_atomic_domain_semantics(user, make_item):
    parent = make_item(user, "Parent")
    make_item(user, "Child", parent=parent)

    delete = _service_callable("delete", "soft_delete", "delete_item", "delete_subtree")
    assert delete is not None, (
        "D2 MISSING: ARC needs one atomic domain command for deleting a "
        "parent/subtree so active descendants/parent references cannot be left "
        "dangling by a partial multi-write operation"
    )


@covers('DEL-003')
def test_D3_deleting_dependency_endpoint_requires_edge_restore_history():
    dependency = _dependency_model()
    assert dependency is not None, (
        "D3 MISSING PREREQUISITE: dependency graph is not implemented. "
        "Deleting an endpoint must suspend/remove incident active edges while "
        "retaining enough canonical/history context for safe restore."
    )


@covers('DEL-001', 'DEL-002')
def test_D4_restore_is_a_validated_domain_command_not_raw_flag_flip():
    restore = _service_callable("restore", "restore_item", "restore_subtree")
    assert restore is not None, (
        "D4 MISSING: restore must be a domain command that validates the "
        "original parent/dependency relationships against the current world; "
        "raw is_deleted=False is insufficient."
    )


def test_D5_restore_must_revalidate_hierarchy_cycle():
    restore = _service_callable("restore", "restore_item", "restore_subtree")
    assert restore is not None, (
        "D5 MISSING PREREQUISITE: no validated restore command exists. "
        "Restore must reject/redirect an original parent relationship that "
        "would now create a hierarchy cycle."
    )


def test_D6_restore_must_revalidate_dependency_cycle():
    restore = _service_callable("restore", "restore_item", "restore_subtree")
    dependency = _dependency_model()
    assert restore is not None and dependency is not None, (
        "D6 MISSING PREREQUISITE: safe restore + dependency graph are required. "
        "An old dependency edge may not be silently reactivated if it would "
        "create a dependency cycle in the present world."
    )


@covers('DEL-005')
def test_D7_restoring_old_anchor_after_its_date_cannot_blindly_reactivate_it():
    names = {f.name for f in PlanningItem._meta.get_fields()}
    assert "manual_requested_date" in names, (
        "D7 MISSING PREREQUISITE: canonical anchor/manual date intent"
    )
    restore = _service_callable("restore", "restore_item", "restore_subtree")
    assert restore is not None, (
        "D7 MISSING: restore must reconcile expired anchor semantics against now"
    )


def test_D8_restored_incomplete_past_deadline_derives_overdue(user, make_item, today):
    from datetime import timedelta

    item = make_item(
        user,
        "Late deleted task",
        due_date=today - timedelta(days=1),
        is_completed=False,
    )
    PlanningItem.objects.filter(pk=item.pk).update(is_deleted=True)

    # This assertion is about derivation, independent of whether the final
    # restore command has landed yet.
    PlanningItem.objects.filter(pk=item.pk).update(is_deleted=False)
    overdue = PlanningItem.objects.for_user(user).overdue(today)

    assert item.pk in set(overdue.values_list("pk", flat=True))


@covers('DEL-004', 'DEL-006')
def test_D9_undo_without_intervening_conflict_requires_domain_undo_support():
    undo = _service_callable("undo", "undo_last", "undo_transition")
    assert undo is not None, (
        "D9 MISSING: reversible lifecycle mutations need semantic undo so an "
        "inverse with no intervening relevant change can round-trip prior state"
    )


@covers('DEL-004', 'DEL-005', 'DEL-006')
def test_D10_undo_must_validate_against_present_world_not_bulldoze_newer_facts():
    undo = _service_callable("undo", "undo_last", "undo_transition")
    assert undo is not None, (
        "D10 MISSING PREREQUISITE: no domain undo implementation exists. "
        "When added, it must validate the inverse against newer hierarchy, "
        "dependency, temporal and anchor facts rather than blindly restoring "
        "an old snapshot."
    )
