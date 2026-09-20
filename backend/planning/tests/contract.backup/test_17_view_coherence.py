"""
ARC frozen-contract tests: cross-view coherence.

Planner, Priority, Timeline and Focus are projections over one canonical ARC
state. A canonical mutation must become visible everywhere without requiring a
second "repair" action in another view. Read/convenience interactions must not
silently become planning mutations.
"""

from __future__ import annotations

import importlib
from datetime import timedelta

import pytest

from planning.models import PlanningItem
from planning.services import priority

pytestmark = pytest.mark.django_db

CONTRACT_IDS = {"VIEW-001", "VIEW-002", "VIEW-003"}


def _module(*names):
    for name in names:
        try:
            return importlib.import_module(name)
        except ModuleNotFoundError:
            continue
    return None


def _focus():
    return _module("planning.services.focus", "planning.services.focus_view")


def _scheduler():
    return _module("planning.services.scheduling", "planning.services.scheduler")


def _commands():
    return _module(
        "planning.services.commands",
        "planning.services.domain_commands",
        "planning.services.mutations",
    )


def _run_scheduler(user):
    service = _scheduler()
    assert service is not None, "VIEW-001 prerequisite: scheduling service"
    fn = next(
        (
            getattr(service, name)
            for name in ("schedule", "reschedule", "run", "reconcile_schedule")
            if callable(getattr(service, name, None))
        ),
        None,
    )
    assert fn is not None, "VIEW-001 prerequisite: scheduler entry point"
    return fn(user)


def _planning_snapshot(item):
    item.refresh_from_db()
    fields = {f.name for f in PlanningItem._meta.get_fields()}
    return {
        "parent_id": item.parent_id,
        "is_completed": item.is_completed,
        "is_deleted": item.is_deleted,
        "priority_position": item.priority_position,
        "start_date": item.start_date,
        "due_date": item.due_date,
        "duration_category": item.duration_category,
        "manual_requested_date": (
            getattr(item, "manual_requested_date")
            if "manual_requested_date" in fields
            else None
        ),
    }


def test_VIEW_001_views_do_not_define_independent_canonical_task_models():
    """There must be one planning truth, not PlannerTask/FocusTask/etc."""
    planning_models = importlib.import_module("planning.models")

    forbidden = (
        "PlannerItem",
        "PriorityItem",
        "TimelineItem",
        "TimelineTask",
        "FocusItem",
        "FocusTask",
    )
    assert not any(hasattr(planning_models, name) for name in forbidden), (
        "VIEW-001: logical views must project PlanningItem/canonical state "
        "instead of owning competing task models"
    )


def test_VIEW_001_priority_mutation_is_immediately_canonical_for_all_projections(
    user, make_item
):
    a = make_item(user, "A")
    b = make_item(user, "B")
    c = make_item(user, "C")
    priority.reconcile(user)

    move = next(
        (
            getattr(priority, name)
            for name in ("move", "move_to", "reorder", "set_position")
            if callable(getattr(priority, name, None))
        ),
        None,
    )
    assert move is not None, "VIEW-001 prerequisite: canonical priority mutation"

    # Support the common service signatures without baking UI semantics in.
    called = False
    for args in ((c, 0), (user, c, 0), (c, 1), (user, c, 1)):
        try:
            move(*args)
            called = True
            break
        except TypeError:
            continue
    assert called, "VIEW-001: could not invoke canonical priority mutation"

    ordered = list(priority.ordered(user).values_list("pk", flat=True))
    assert ordered[0] == c.pk, (
        "VIEW-001: the canonical priority projection must immediately expose "
        "the mutation; no second view-specific write may be required"
    )


def test_VIEW_002_timeline_anchor_counts_without_priority_repair_hop(
    user, make_item, today
):
    fields = {f.name for f in PlanningItem._meta.get_fields()}
    assert "manual_requested_date" in fields, (
        "VIEW-002 prerequisite: canonical manual_requested_date"
    )

    service = _scheduler()
    assert service is not None
    move = next(
        (
            getattr(service, name)
            for name in (
                "move_to_date",
                "set_anchor",
                "anchor",
                "set_manual_requested_date",
            )
            if callable(getattr(service, name, None))
        ),
        None,
    )
    assert move is not None, (
        "VIEW-002: Timeline movement needs one canonical domain operation"
    )

    item = make_item(user, "Move me")
    priority.reconcile(user)
    before_priority = item.priority_position
    target = today + timedelta(days=2)

    called = False
    for args in ((item, target), (user, item, target)):
        try:
            move(*args)
            called = True
            break
        except TypeError:
            continue
    assert called

    item.refresh_from_db()
    assert item.manual_requested_date == target
    assert item.priority_position == before_priority, (
        "VIEW-002: date intent must count globally without requiring or "
        "inventing a Priority-view repair mutation"
    )


def test_VIEW_003_focus_lookahead_is_read_only_not_global_replanning(
    user, make_item, today
):
    service = _focus()
    assert service is not None, "VIEW-003 prerequisite: Focus projection"

    item = make_item(
        user,
        "Future",
        scheduled_date=today + timedelta(days=3),
        duration_category="UNDER_4_HOURS",
    )
    before = _planning_snapshot(item)
    before_scheduled = item.scheduled_date

    fn = next(
        (
            getattr(service, name)
            for name in ("build", "get_focus", "candidates", "look_ahead")
            if callable(getattr(service, name, None))
        ),
        None,
    )
    assert fn is not None

    called = False
    for args in ((user, today), (user,)):
        try:
            fn(*args)
            called = True
            break
        except TypeError:
            continue
    assert called

    item.refresh_from_db()
    assert _planning_snapshot(item) == before
    assert item.scheduled_date == before_scheduled, (
        "VIEW-003: merely viewing/looking ahead in Focus must not replan work"
    )


def test_VIEW_003_current_focus_selection_cannot_mutate_planning_facts(
    user, make_item
):
    service = _focus()
    assert service is not None
    item = make_item(user, "A")
    before = _planning_snapshot(item)

    select = next(
        (
            getattr(service, name)
            for name in ("set_current", "select", "set_current_focus")
            if callable(getattr(service, name, None))
        ),
        None,
    )
    assert select is not None, "VIEW-003 prerequisite: current-focus command"

    called = False
    for args in ((user, item), (item,)):
        try:
            select(*args)
            called = True
            break
        except TypeError:
            continue
    assert called

    assert _planning_snapshot(item) == before


def test_VIEW_001_domain_command_boundary_exists_for_cross_view_writes():
    commands = _commands()
    assert commands is not None, (
        "VIEW-001/002: view-originated writes need a shared domain-command "
        "boundary rather than separate serializer/view databases"
    )
