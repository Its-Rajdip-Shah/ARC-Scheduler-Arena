"""
ARC frozen-contract tests: canonical state ownership.

These tests deliberately describe the frozen contract, not the current
implementation. A failure therefore means either:
  1. the backend is missing contract state/semantics, or
  2. the test must be changed only if the frozen contract itself changes.
"""

from datetime import timedelta

import pytest
from django.core.exceptions import FieldDoesNotExist

from planning.models import PlanningItem

pytestmark = pytest.mark.django_db


# Canonical fields required by the frozen contract. Names are the backend-facing
# contract names used by this suite. If implementation chooses another internal
# name, expose an equivalent domain property/API and update the adapter here,
# rather than weakening the behavioural tests.
REQUIRED_CANONICAL_FIELD_GROUPS = {
    "deletion/tombstone": ("is_deleted",),
    "manual date intent / anchor": ("manual_requested_date",),
    "duration category": ("duration_category",),
    "release date": ("start_date",),
    "deadline": ("due_date",),
    "completion": ("is_completed",),
    "priority": ("priority_position",),
    "hierarchy": ("parent",),
}

# These concepts are required by the frozen architecture but were absent from
# the audited backend. Tests stay explicit so a missing implementation is
# reported as a contract gap rather than silently skipped.
REQUIRED_NEW_CONCEPTS = {
    "confirmed splittable progress": (
        "percent_completed",
        "completion_percent",
        "progress_percent",
    ),
}


def _field_names(model):
    return {field.name for field in model._meta.get_fields()}


def _has_any_field(model, candidates):
    names = _field_names(model)
    return any(name in names for name in candidates)


@pytest.mark.parametrize(
    ("concept", "candidates"),
    REQUIRED_CANONICAL_FIELD_GROUPS.items(),
)
def test_required_existing_canonical_state_is_persisted(concept, candidates):
    assert _has_any_field(PlanningItem, candidates), (
        f"Frozen ARC contract requires canonical {concept!r} state. "
        f"Expected one of {candidates}; PlanningItem has {_field_names(PlanningItem)}"
    )


@pytest.mark.parametrize(("concept", "candidates"), REQUIRED_NEW_CONCEPTS.items())
def test_required_new_canonical_state_exists(concept, candidates):
    assert _has_any_field(PlanningItem, candidates), (
        f"MISSING CONTRACT IMPLEMENTATION: {concept}. "
        f"Expected one of {candidates}. This is canonical user/domain state, "
        "not a scheduler-only value."
    )


def test_scheduled_date_and_anchor_are_distinct_fields():
    names = _field_names(PlanningItem)
    assert "scheduled_date" in names
    assert "manual_requested_date" in names
    assert "scheduled_date" != "manual_requested_date"


def test_scheduler_date_can_change_without_destroying_anchor(user, make_item, today):
    """Scheduled placement is disposable; explicit date intent is canonical."""
    anchor = today + timedelta(days=3)
    item = make_item(user, "Anchored", scheduled_date=anchor)

    if "manual_requested_date" not in _field_names(PlanningItem):
        pytest.fail("MISSING CONTRACT IMPLEMENTATION: canonical anchor/manual date intent")

    item.manual_requested_date = anchor
    item.save(update_fields=["manual_requested_date"])

    # Simulate replacement of scheduler proposal only.
    PlanningItem.objects.filter(pk=item.pk).update(
        scheduled_date=anchor + timedelta(days=1)
    )
    item.refresh_from_db()

    assert item.manual_requested_date == anchor
    assert item.scheduled_date == anchor + timedelta(days=1)


def test_derived_overdue_is_not_required_as_competing_canonical_truth():
    """Overdue is derived from deadline + completion + current time."""
    try:
        field = PlanningItem._meta.get_field("overdue")
    except FieldDoesNotExist:
        return

    pytest.fail(
        "PlanningItem.overdue is persisted. Frozen ARC contract defines overdue "
        "as derived state; remove it or prove it is a non-authoritative cache "
        f"with reconciliation semantics. Field: {field!r}"
    )


def test_priority_and_scheduled_date_are_independent(user, make_item, today):
    item = make_item(
        user,
        "Independent facts",
        priority_position=1,
        scheduled_date=today + timedelta(days=4),
    )

    PlanningItem.objects.filter(pk=item.pk).update(
        scheduled_date=today + timedelta(days=2)
    )
    item.refresh_from_db()

    assert item.priority_position == 1


def test_parent_dates_are_owned_by_child_after_creation(user, make_item, today):
    """Parent defaults are creation convenience, not perpetual inheritance."""
    parent = make_item(
        user,
        "Parent",
        start_date=today + timedelta(days=2),
        due_date=today + timedelta(days=10),
    )
    child = make_item(
        user,
        "Child",
        parent=parent,
        start_date=parent.start_date,
        due_date=parent.due_date,
    )

    old_child_dates = (child.start_date, child.due_date)
    parent.start_date = today + timedelta(days=4)
    parent.due_date = today + timedelta(days=12)
    parent.save(update_fields=["start_date", "due_date"])

    child.refresh_from_db()
    assert (child.start_date, child.due_date) == old_child_dates
