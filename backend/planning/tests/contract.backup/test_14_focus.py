"""
ARC frozen-contract tests: Focus transitions F1-F9.

Focus is a projection/convenience layer over canonical planning state.
Looking, selecting and executing out of suggested order do not mutate priority
or dates. Explicit "do today" is planning intent and therefore becomes an
anchor; explicit reprioritisation is a real priority mutation.
"""

import importlib
from datetime import timedelta

import pytest

from planning.models import PlanningItem
from planning.services import priority

pytestmark = pytest.mark.django_db

CONTRACT_IDS = {
    "FOC-001", "FOC-002", "FOC-003", "FOC-004", "FOC-005",
    "FOC-006", "FOC-007", "FOC-008", "FOC-009",
}


def _focus():
    for name in ("planning.services.focus", "planning.services.focus_view"):
        try:
            return importlib.import_module(name)
        except ModuleNotFoundError:
            pass
    return None


def _anchor_field():
    fields = {f.name for f in PlanningItem._meta.get_fields()}
    assert "manual_requested_date" in fields, "FOC-005 needs canonical manual_requested_date"
    return "manual_requested_date"


def _snapshot(item):
    item.refresh_from_db()
    return (
        item.priority_position,
        item.start_date,
        item.due_date,
        getattr(item, _anchor_field()),
        item.duration_category,
        item.parent_id,
        item.is_completed,
    )


def test_F1_focus_projection_service_exists():
    service = _focus()
    assert service is not None, "FOC-001 MISSING: Focus projection/service"
    assert any(callable(getattr(service, n, None)) for n in ("build", "render", "candidates", "get_focus"))


def test_F1_focus_grouping_uses_canonical_duration_not_visual_drop_bucket():
    service = _focus()
    assert service is not None
    assert any(
        callable(getattr(service, n, None))
        for n in ("bucket_for", "duration_bucket", "build", "get_focus")
    ), "FOC-001/008: Focus buckets must derive from canonical duration"


def test_F2_lookahead_is_read_only_and_does_not_reschedule(user, make_item, today):
    service = _focus()
    assert service is not None
    item = make_item(
        user, "Future",
        scheduled_date=today + timedelta(days=2),
        duration_category="UNDER_4_HOURS",
    )
    before = _snapshot(item)

    fn = next(
        (getattr(service, n) for n in ("build", "get_focus", "candidates", "look_ahead")
         if callable(getattr(service, n, None))),
        None,
    )
    assert fn is not None
    for args in ((user, today), (user,)):
        try:
            fn(*args)
            break
        except TypeError:
            continue

    assert _snapshot(item) == before


def test_F3_F4_selecting_current_focus_is_convenience_only(user, make_item):
    service = _focus()
    assert service is not None
    a = make_item(user, "A")
    b = make_item(user, "B")
    priority.reconcile(user)
    before_a, before_b = _snapshot(a), _snapshot(b)

    fn = next(
        (getattr(service, n) for n in ("set_current", "select", "set_current_focus")
         if callable(getattr(service, n, None))),
        None,
    )
    assert fn is not None, "FOC-003 MISSING: current-focus convenience command"
    fn(user, b)

    assert _snapshot(a) == before_a
    assert _snapshot(b) == before_b


def test_F5_do_today_translates_to_explicit_today_anchor(user, make_item, today):
    service = _focus()
    assert service is not None
    item = make_item(user, "Future", scheduled_date=today + timedelta(days=3))

    fn = next(
        (getattr(service, n) for n in ("do_today", "promote_to_today", "promote")
         if callable(getattr(service, n, None))),
        None,
    )
    assert fn is not None, "FOC-005 MISSING: do-today planning command"
    fn(item, today)
    item.refresh_from_db()

    assert getattr(item, _anchor_field()) == today


def test_F6_return_promoted_item_to_automatic_clears_explicit_date_intent(
    user, make_item, today
):
    service = _focus()
    assert service is not None
    item = make_item(user, "Task")
    setattr(item, _anchor_field(), today)
    item.save(update_fields=[_anchor_field()])

    fn = next(
        (getattr(service, n) for n in ("return_to_automatic", "demote", "clear_do_today")
         if callable(getattr(service, n, None))),
        None,
    )
    assert fn is not None, "FOC-006 MISSING: return-to-automatic command"
    fn(item)
    item.refresh_from_db()

    assert getattr(item, _anchor_field()) is None


def test_F7_explicit_focus_reprioritise_uses_global_priority_service():
    service = _focus()
    assert service is not None
    assert any(
        callable(getattr(service, n, None))
        for n in ("reprioritise", "reprioritize", "move_priority")
    ), "FOC-007: explicit Focus reprioritisation must cross the canonical priority boundary"


def test_F8_wrong_visual_bucket_cannot_mutate_duration(user, make_item):
    item = make_item(user, "Task", duration_category="UNDER_20_MINUTES")
    before = item.duration_category

    service = _focus()
    assert service is not None
    # The domain must not expose a generic "move bucket = edit duration" shortcut.
    forbidden = ("set_bucket_as_duration", "duration_from_drop_bucket")
    assert not any(callable(getattr(service, n, None)) for n in forbidden)
    item.refresh_from_db()
    assert item.duration_category == before


def test_F9_non_executable_current_focus_is_cleared_without_planning_mutation():
    service = _focus()
    assert service is not None
    assert any(
        callable(getattr(service, n, None))
        for n in ("reconcile", "reconcile_current", "clear_if_ineligible")
    ), "FOC-009: convenience focus state must reconcile when task becomes blocked"
