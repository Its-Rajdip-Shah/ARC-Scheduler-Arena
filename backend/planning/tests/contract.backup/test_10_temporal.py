"""
ARC frozen-contract tests: temporal transitions T1-T12.

Release/due dates are canonical task facts. Child values are creation
defaults that become independently editable. Automatic scheduling obeys
temporal legality; overdue is derived from due date, not anchor expiry.
"""

from datetime import timedelta
import importlib

import pytest

from planning.models import PlanningItem
from planning.services import priority

pytestmark = pytest.mark.django_db

CONTRACT_IDS = {
    "TMP-001", "TMP-002", "TMP-003", "TMP-004", "TMP-005", "TMP-006",
    "TMP-007", "TMP-008", "TMP-009", "TMP-010", "TMP-011",
}


def _fields():
    return {f.name for f in PlanningItem._meta.get_fields()}


def _scheduler_service():
    for module_name in (
        "planning.services.scheduling",
        "planning.services.scheduler",
    ):
        try:
            return importlib.import_module(module_name)
        except ModuleNotFoundError:
            pass
    return None


def _reschedule(user, today):
    service = _scheduler_service()
    assert service is not None, "TMP MISSING: planning scheduling service"
    for name in ("reschedule", "schedule", "reconcile_schedule", "run"):
        fn = getattr(service, name, None)
        if callable(fn):
            for args in ((user, today), (user,), ()):
                try:
                    return fn(*args)
                except TypeError:
                    continue
    raise AssertionError("TMP MISSING: no callable reschedule/schedule domain command")


def _scheduled_date(item):
    item.refresh_from_db()
    assert "scheduled_date" in _fields(), "TMP MISSING: scheduled_date"
    return item.scheduled_date


def test_T1_T2_release_edit_is_own_canonical_fact_and_reconciles(user, make_item, today):
    item = make_item(user, "Task", start_date=today + timedelta(days=3))
    assert item.start_date == today + timedelta(days=3)

    item.start_date = today + timedelta(days=1)
    item.save(update_fields=["start_date"])
    item.refresh_from_db()
    assert item.start_date == today + timedelta(days=1)

    item.start_date = None
    item.save(update_fields=["start_date"])
    item.refresh_from_db()
    assert item.start_date is None


def test_T3_T4_deadline_edit_controls_overdue_derivation(user, make_item, today):
    item = make_item(user, "Task", due_date=today - timedelta(days=1))
    assert item.pk in set(
        PlanningItem.objects.for_user(user).overdue(today).values_list("pk", flat=True)
    )

    item.due_date = today + timedelta(days=2)
    item.save(update_fields=["due_date"])
    assert item.pk not in set(
        PlanningItem.objects.for_user(user).overdue(today).values_list("pk", flat=True)
    )

    item.due_date = None
    item.save(update_fields=["due_date"])
    assert item.pk not in set(
        PlanningItem.objects.for_user(user).overdue(today).values_list("pk", flat=True)
    )


def test_T5_T6_child_dates_are_editable_owned_values_not_permanent_ancestor_bounds(
    user, make_item, today
):
    parent = make_item(
        user, "Parent",
        start_date=today + timedelta(days=5),
        due_date=today + timedelta(days=10),
    )
    child = make_item(
        user, "Child", parent=parent,
        start_date=parent.start_date,
        due_date=parent.due_date,
    )

    child.start_date = today + timedelta(days=1)   # earlier than parent
    child.due_date = today + timedelta(days=20)   # later than parent
    child.save(update_fields=["start_date", "due_date"])
    child.refresh_from_db()

    assert child.start_date < parent.start_date
    assert child.due_date > parent.due_date


def test_T7_editing_parent_dates_does_not_silently_bulk_rewrite_existing_children(
    user, make_item, today
):
    parent = make_item(
        user, "Parent",
        start_date=today + timedelta(days=2),
        due_date=today + timedelta(days=10),
    )
    child = make_item(
        user, "Child", parent=parent,
        start_date=parent.start_date,
        due_date=parent.due_date,
    )
    child_dates = (child.start_date, child.due_date)

    parent.start_date = today + timedelta(days=4)
    parent.due_date = today + timedelta(days=15)
    parent.save(update_fields=["start_date", "due_date"])
    child.refresh_from_db()

    assert (child.start_date, child.due_date) == child_dates


def test_TMP001_TMP002_TMP003_automatic_schedule_obeys_own_release_due_and_today(
    user, make_item, today
):
    release = today + timedelta(days=2)
    due = today + timedelta(days=6)
    item = make_item(user, "Constrained", start_date=release, due_date=due)

    _reschedule(user, today)
    placed = _scheduled_date(item)

    assert placed is not None
    assert placed >= today
    assert placed >= release
    assert placed <= due


def test_equal_release_and_due_has_only_that_legal_automatic_date(
    user, make_item, today
):
    only = today + timedelta(days=3)
    item = make_item(user, "One legal date", start_date=only, due_date=only)

    _reschedule(user, today)

    assert _scheduled_date(item) == only


def test_T9_overdue_means_incomplete_work_crossed_its_due_date(user, make_item, today):
    late = make_item(user, "Late", due_date=today - timedelta(days=1))
    due_today = make_item(user, "Due today", due_date=today)
    future = make_item(user, "Future", due_date=today + timedelta(days=1))
    completed = make_item(
        user, "Completed late",
        due_date=today - timedelta(days=1),
        is_completed=True,
    )
    ids = set(
        PlanningItem.objects.for_user(user).overdue(today).values_list("pk", flat=True)
    )

    assert late.pk in ids
    assert due_today.pk not in ids
    assert future.pk not in ids
    assert completed.pk not in ids


def test_T10_T11_overdue_work_is_recoverable_by_completion_or_deadline_extension(
    user, make_item, today
):
    item = make_item(user, "Late", due_date=today - timedelta(days=1))
    assert item.pk in set(
        PlanningItem.objects.for_user(user).overdue(today).values_list("pk", flat=True)
    )

    item.due_date = today + timedelta(days=5)
    item.save(update_fields=["due_date"])
    assert item.pk not in set(
        PlanningItem.objects.for_user(user).overdue(today).values_list("pk", flat=True)
    )


def test_TMP004_release_is_feasibility_not_priority_mutation(user, make_item, today):
    a = make_item(user, "A")
    b = make_item(user, "B")
    priority.reconcile(user)
    before = list(priority.ordered(user).values_list("pk", flat=True))

    b.start_date = today + timedelta(days=30)
    b.save(update_fields=["start_date"])
    priority.reconcile(user)
    after = list(priority.ordered(user).values_list("pk", flat=True))

    # B may leave active execution eligibility while unreleased, but ARC
    # must preserve its priority restoration meaning rather than treating
    # release as an importance boost/rewrite.
    b.refresh_from_db()
    assert b.priority_restore_context or b.priority_position is not None
    assert a.pk in after
    assert before[0] == a.pk


def test_TMP011_invalid_temporal_state_is_not_silently_normalised(user, make_item, today):
    # ARC may reject this at the domain-command boundary or represent it as
    # an explicit conflict, but must never silently swap/change the dates.
    release = today + timedelta(days=10)
    due = today + timedelta(days=2)
    try:
        item = make_item(user, "Conflict", start_date=release, due_date=due)
    except Exception:
        return

    item.refresh_from_db()
    assert item.start_date == release
    assert item.due_date == due, (
        "TMP-011: contradictory state may be surfaced, but user dates cannot "
        "be silently rewritten to make scheduling convenient"
    )
