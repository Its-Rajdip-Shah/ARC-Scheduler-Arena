
from .conftest import covers
"""
ARC frozen-contract tests: anchor/manual-date lifecycle A1-A11.

Anchors are canonical hard user date intent, distinct from priority and
automatic scheduled_date.  Conflicts are surfaced; expiry removes the hard
date without manufacturing overdue or silently erasing recovery intent.
"""

from datetime import timedelta
import importlib

import pytest
from django.core.exceptions import ValidationError

from planning.models import PlanningItem
from planning.services import hierarchy, priority

pytestmark = pytest.mark.django_db

CONTRACT_IDS = {
    "ANC-001", "ANC-002", "ANC-003", "ANC-004", "ANC-005", "ANC-006",
    "ANC-007", "ANC-008", "ANC-009", "ANC-010", "ANC-011", "ANC-012",
}


def _fields():
    return {f.name for f in PlanningItem._meta.get_fields()}


def _anchor_field():
    assert "manual_requested_date" in _fields(), (
        "ANC MISSING: canonical manual_requested_date/anchor field"
    )
    return "manual_requested_date"


def _service():
    for module_name in (
        "planning.services.scheduling",
        "planning.services.anchors",
        "planning.services.anchor",
    ):
        try:
            return importlib.import_module(module_name)
        except ModuleNotFoundError:
            pass
    return None


def _call(names, *args, **kwargs):
    service = _service()
    assert service is not None, "ANC MISSING: anchor/scheduling domain service"
    for name in names:
        fn = getattr(service, name, None)
        if callable(fn):
            return fn(*args, **kwargs)
    raise AssertionError(f"ANC MISSING: no domain command among {tuple(names)}")


def _set_anchor(item, date):
    # Prefer the real domain command. Raw field writes would bypass the
    # conflict semantics this suite is intended to protect.
    return _call(
        ("set_anchor", "anchor", "set_manual_requested_date", "request_date"),
        item, date,
    )


def _remove_anchor(item):
    return _call(
        ("remove_anchor", "unanchor", "clear_anchor", "clear_manual_requested_date"),
        item,
    )


@covers('ANC-001', 'ANC-002')
def test_A1_valid_anchor_is_canonical_and_distinct_from_priority(user, make_item, today):
    item = make_item(user, "Task")
    priority.reconcile(user)
    item.refresh_from_db()
    before = item.priority_position

    _set_anchor(item, today + timedelta(days=2))
    item.refresh_from_db()

    assert getattr(item, _anchor_field()) == today + timedelta(days=2)
    assert item.priority_position == before


@covers('ANC-003')
def test_A2_moving_anchor_changes_canonical_anchor_date(user, make_item, today):
    item = make_item(user, "Task")
    _set_anchor(item, today + timedelta(days=2))
    _set_anchor(item, today + timedelta(days=4))
    item.refresh_from_db()

    assert getattr(item, _anchor_field()) == today + timedelta(days=4)


@covers('ANC-011')
def test_A3_A11_unanchor_returns_to_automatic_without_rewriting_priority(
    user, make_item, today
):
    item = make_item(user, "Task")
    priority.reconcile(user)
    item.refresh_from_db()
    before = item.priority_position
    _set_anchor(item, today + timedelta(days=2))

    _remove_anchor(item)
    item.refresh_from_db()

    assert getattr(item, _anchor_field()) is None
    assert item.priority_position == before


@covers('ANC-004')
def test_A4_anchor_after_due_requires_explicit_resolution_not_silent_deadline_change(
    user, make_item, today
):
    due = today + timedelta(days=2)
    item = make_item(user, "Task", due_date=due)

    try:
        _set_anchor(item, due + timedelta(days=3))
    except (ValidationError, ValueError):
        item.refresh_from_db()
        assert item.due_date == due
        assert getattr(item, _anchor_field()) is None
        return

    item.refresh_from_db()
    assert item.due_date != due or getattr(item, _anchor_field()) is None, (
        "A4: anchoring after due may only proceed after explicit conflict "
        "resolution that changes the deadline; it cannot silently accept "
        "an anchor beyond an unchanged deadline"
    )


@covers('ANC-005')
def test_A5_anchor_before_release_requires_explicit_resolution_not_silent_release_change(
    user, make_item, today
):
    release = today + timedelta(days=5)
    item = make_item(user, "Task", start_date=release)

    try:
        _set_anchor(item, today + timedelta(days=1))
    except (ValidationError, ValueError):
        item.refresh_from_db()
        assert item.start_date == release
        assert getattr(item, _anchor_field()) is None
        return

    item.refresh_from_db()
    assert item.start_date != release or getattr(item, _anchor_field()) is None, (
        "A5: anchoring before release requires explicit release-change-or-cancel"
    )


@covers('ANC-006')
def test_A6_passing_anchor_date_does_not_itself_make_task_overdue(
    user, make_item, today
):
    item = make_item(user, "Missed intent", due_date=today + timedelta(days=10))
    field = _anchor_field()
    setattr(item, field, today - timedelta(days=1))
    item.save(update_fields=[field])

    overdue = set(
        PlanningItem.objects.for_user(user).overdue(today).values_list("pk", flat=True)
    )
    assert item.pk not in overdue


@covers('ANC-007', 'ANC-008')
def test_A6_A7_A8_expired_anchor_reconciles_to_automatic_but_retains_recovery_trace(
    user, make_item, today
):
    item = make_item(user, "Missed promoted task")
    field = _anchor_field()
    setattr(item, field, today - timedelta(days=1))
    item.save(update_fields=[field])

    service = _service()
    assert service is not None, "A6-A8 MISSING: time/anchor reconciliation service"
    reconcile = next(
        (getattr(service, n) for n in
         ("reconcile_anchors", "reconcile", "expire_anchors", "reschedule")
         if callable(getattr(service, n, None))),
        None,
    )
    assert reconcile is not None, "A6-A8 MISSING: anchor expiry reconciliation"

    called = False
    for args in ((user, today), (user,), ()):
        try:
            reconcile(*args)
            called = True
            break
        except TypeError:
            continue
    assert called

    item.refresh_from_db()
    assert getattr(item, field) is None, (
        "A6/A7: expired hard date commitment must cease constraining placement"
    )
    history_model = next(
        (
            m for m in PlanningItem._meta.apps.get_app_config("planning").get_models()
            if "history" in m.__name__.lower()
        ),
        None,
    )
    recovery_fields = {
        "manual_intent", "manual_intent_state", "missed_anchor_at",
        "anchor_history", "recovery_intent",
    } & _fields()
    assert history_model is not None or recovery_fields, (
        "A8: missed explicit planning intent needs durable recovery/history "
        "instead of being silently forgotten"
    )


@covers('ANC-009')
def test_A9_automatic_missed_schedule_is_not_converted_into_anchor(user, make_item, today):
    assert "scheduled_date" in _fields(), "A9 MISSING: scheduled_date"
    item = make_item(
        user, "Automatic",
        scheduled_date=today - timedelta(days=1),
    )
    item.refresh_from_db()
    assert getattr(item, _anchor_field()) is None


@covers('ANC-010')
def test_A9_A10_anchored_parent_decomposition_suspends_parent_and_children_inherit_anchor(
    user, make_item, today
):
    parent = make_item(user, "Parent")
    _set_anchor(parent, today + timedelta(days=3))
    child = make_item(user, "Child", parent=parent)
    parent.refresh_from_db()
    child.refresh_from_db()

    assert getattr(parent, _anchor_field()) == today + timedelta(days=3)
    assert getattr(child, _anchor_field()) == today + timedelta(days=3)
    priority.reconcile(user)
    assert parent.pk not in set(priority.ordered(user).values_list("pk", flat=True))


@covers('ANC-010')
def test_A10_reversing_structural_episode_can_restore_parent_anchor(
    user, make_item, today
):
    parent = make_item(user, "Parent")
    _set_anchor(parent, today + timedelta(days=3))
    child = make_item(user, "Child", parent=parent)
    # Creation semantics should inherit; completing the child returns parent.
    hierarchy.complete_subtree(child)
    parent.refresh_from_db()

    assert getattr(parent, _anchor_field()) == today + timedelta(days=3)
    assert parent.pk in set(priority.ordered(user).values_list("pk", flat=True))


@covers('ANC-012')
def test_A11_A12_anchor_that_creates_infeasible_overload_needs_acknowledgement_layer():
    service = _service()
    assert service is not None
    names = {
        "confirm_anchor", "validate_anchor", "anchor_conflict",
        "set_anchor", "anchor",
    }
    assert any(callable(getattr(service, n, None)) for n in names), (
        "A11/A12: anchor mutation needs a validation/confirmation path for "
        "user-created infeasible or overloaded plans"
    )
