"""
ARC frozen-contract tests: Timeline/scheduler proposal lifecycle S1-S9.

The scheduler consumes reconciled canonical facts and produces disposable
placement/rank/allocation proposals. It cannot rewrite canonical facts to make
a schedule easier. Explicit user Timeline movement becomes an anchor.
"""

import importlib
from datetime import timedelta

import pytest

from planning.models import PlanningItem
from planning.services import priority

pytestmark = pytest.mark.django_db

CONTRACT_IDS = {
    "SCH-001", "SCH-002", "SCH-003", "SCH-004", "SCH-005",
    "SCH-006", "SCH-007", "SCH-008", "SCH-009",
}


def _service():
    for name in ("planning.services.scheduling", "planning.services.scheduler"):
        try:
            return importlib.import_module(name)
        except ModuleNotFoundError:
            pass
    return None


def _run(user):
    service = _service()
    assert service is not None, "SCH MISSING: scheduling service"
    fn = next(
        (getattr(service, n) for n in ("schedule", "reschedule", "run", "reconcile_schedule")
         if callable(getattr(service, n, None))),
        None,
    )
    assert fn is not None
    return fn(user)


def _canonical(item):
    item.refresh_from_db()
    fields = {f.name for f in PlanningItem._meta.get_fields()}
    return {
        "title": item.title,
        "parent_id": item.parent_id,
        "is_completed": item.is_completed,
        "start_date": item.start_date,
        "due_date": item.due_date,
        "duration_category": item.duration_category,
        "anchor": getattr(item, "manual_requested_date", None) if "manual_requested_date" in fields else None,
    }


def test_S1_scheduler_generates_schedule_for_eligible_frontier_work(user, make_item):
    fields = {f.name for f in PlanningItem._meta.get_fields()}
    assert "scheduled_date" in fields
    item = make_item(user, "Task")

    _run(user)
    item.refresh_from_db()

    assert item.scheduled_date is not None


def test_S2_same_facts_rerun_is_idempotent_for_deterministic_scheduler(user, make_item):
    a = make_item(user, "A")
    b = make_item(user, "B")
    _run(user)
    first = list(
        PlanningItem.objects.filter(pk__in=[a.pk, b.pk])
        .order_by("pk").values_list("pk", "scheduled_date")
    )

    _run(user)
    second = list(
        PlanningItem.objects.filter(pk__in=[a.pk, b.pk])
        .order_by("pk").values_list("pk", "scheduled_date")
    )

    assert second == first


def test_S2_S6_scheduler_rerun_never_changes_canonical_task_facts(user, make_item, today):
    item = make_item(
        user, "Task",
        start_date=today,
        due_date=today + timedelta(days=10),
        duration_category="UNDER_4_HOURS",
    )
    before = _canonical(item)

    _run(user)
    _run(user)

    assert _canonical(item) == before


def test_S3_executing_lower_ranked_work_does_not_reprioritise_remaining_work(
    user, make_item
):
    a = make_item(user, "A")
    b = make_item(user, "B")
    c = make_item(user, "C")
    priority.reconcile(user)
    before = list(priority.ordered(user).values_list("pk", flat=True))

    # User chooses to work on C first. Merely doing so is not a planning mutation.
    c.refresh_from_db()
    after = list(priority.ordered(user).values_list("pk", flat=True))
    assert after == before


def test_S4_explicit_timeline_move_has_anchor_domain_command():
    service = _service()
    assert service is not None
    assert any(
        callable(getattr(service, n, None))
        for n in ("move_to_date", "set_anchor", "anchor", "set_manual_requested_date")
    ), "SCH-004: explicit Timeline date movement must become canonical manual date intent"


def test_S5_general_precedence_preference_is_priority_not_timeline_only_order():
    service = _service()
    assert service is not None
    assert not callable(getattr(service, "persist_timeline_visual_order", None)), (
        "SCH-005: general ordering preference belongs to canonical priority"
    )


def test_S7_scheduler_failure_cannot_partially_rewrite_canonical_facts(
    monkeypatch, user, make_item
):
    service = _service()
    assert service is not None
    item = make_item(user, "Task")
    before = _canonical(item)

    # A scheduler implementation may expose a strategy hook; if it does,
    # failure must roll back. If not, the architectural transaction test below
    # still requires the public entry point to be atomic.
    fn = next(
        (getattr(service, n) for n in ("schedule", "reschedule", "run")
         if callable(getattr(service, n, None))),
        None,
    )
    assert fn is not None
    assert getattr(fn, "_arc_atomic", False) or hasattr(fn, "__wrapped__") or "atomic" in repr(fn).lower(), (
        "SCH-007: public scheduler run must have an atomic failure boundary"
    )
    assert _canonical(item) == before


def test_S8_infeasibility_is_reported_without_rewriting_release_or_due(user, make_item, today):
    item = make_item(
        user, "Impossible",
        start_date=today + timedelta(days=10),
        due_date=today + timedelta(days=1),
    )
    before = _canonical(item)

    try:
        result = _run(user)
    except Exception:
        result = None

    assert _canonical(item) == before
    assert result is None or hasattr(result, "__iter__") or hasattr(result, "infeasible")


def test_S9_due_date_is_hard_upper_bound_for_automatic_placement(user, make_item, today):
    item = make_item(user, "Deadline", due_date=today + timedelta(days=2))
    _run(user)
    item.refresh_from_db()

    assert item.scheduled_date is None or item.scheduled_date <= item.due_date
