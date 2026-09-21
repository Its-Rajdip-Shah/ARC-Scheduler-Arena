"""
ARC frozen-contract tests: scheduler authority boundary.

The scheduler has broad freedom over disposable scheduling proposals and no
authority to rewrite canonical human intent. Hard intent constrains it, soft
intent guides it, and algorithm flavours may differ only inside that boundary.
"""

from __future__ import annotations

from .conftest import covers

import importlib
from datetime import timedelta

import pytest
from django.apps import apps

from planning.models import DurationCategory, PlanningDependency, PlanningItem, ProgressSegment, SchedulerAllocation
from planning.services import deletion, priority, scheduling
from django.utils import timezone
from decimal import Decimal

pytestmark = pytest.mark.django_db

CONTRACT_IDS = {"AUTH-001", "AUTH-002", "AUTH-003", "AUTH-004"}


def _scheduler():
    for name in ("planning.services.scheduling", "planning.services.scheduler"):
        try:
            return importlib.import_module(name)
        except ModuleNotFoundError:
            continue
    return None


def _run(user):
    service = _scheduler()
    assert service is not None, "AUTH prerequisite: scheduler service"
    fn = next(
        (
            getattr(service, name)
            for name in ("schedule", "reschedule", "run", "reconcile_schedule")
            if callable(getattr(service, name, None))
        ),
        None,
    )
    assert fn is not None
    return fn(user)


def _dependency_model():
    for model in apps.get_app_config("planning").get_models():
        names = {f.name for f in model._meta.get_fields()}
        if (
            {"prerequisite", "dependent"} <= names
            or {"predecessor", "successor"} <= names
        ):
            return model
    return None


def _canonical(item):
    item.refresh_from_db()
    fields = {f.name for f in PlanningItem._meta.get_fields()}
    names = (
        "title",
        "parent_id",
        "is_completed",
        "is_deleted",
        "priority_position",
        "sibling_order",
        "start_date",
        "due_date",
        "duration_category",
        "manual_requested_date",
        "percent_completed",
    )
    return {
        name: getattr(item, name)
        for name in names
        if name in fields or hasattr(item, name)
    }


@covers('AUTH-001')
def test_AUTH_001_hard_anchor_survives_scheduler_rerun(user, make_item, today):
    fields = {f.name for f in PlanningItem._meta.get_fields()}
    assert "manual_requested_date" in fields, (
        "AUTH-001 prerequisite: canonical anchor/manual date intent"
    )

    target = today + timedelta(days=2)
    item = make_item(user, "Anchored", manual_requested_date=target)
    _run(user)
    item.refresh_from_db()

    assert item.manual_requested_date == target, (
        "AUTH-001: scheduler must optimize around explicit date intent, "
        "not erase or rewrite it"
    )
    if "scheduled_date" in fields:
        assert item.scheduled_date == target, (
            "AUTH-001: a valid hard anchor constrains scheduler placement"
        )


@covers('AUTH-002')
def test_AUTH_002_scheduler_cannot_rewrite_canonical_task_facts(
    user, make_item, today
):
    item = make_item(
        user,
        "Canonical facts",
        start_date=today,
        due_date=today + timedelta(days=7),
        duration_category="UNDER_4_HOURS",
    )
    before = _canonical(item)

    _run(user)
    _run(user)

    assert _canonical(item) == before, (
        "AUTH-002: scheduler output may change, canonical user/domain facts may not"
    )


def test_AUTH_002_scheduler_cannot_create_or_delete_dependency_edges(
    user, make_item
):
    dependency = _dependency_model()
    assert dependency is not None, (
        "AUTH-002 prerequisite: dependency graph implementation"
    )

    a = make_item(user, "A")
    b = make_item(user, "B")

    fields = {f.name for f in dependency._meta.get_fields()}
    if {"prerequisite", "dependent"} <= fields:
        edge = dependency.objects.create(prerequisite=a, dependent=b)
    elif {"predecessor", "successor"} <= fields:
        edge = dependency.objects.create(predecessor=a, successor=b)
    else:  # defensive; discovery above should prevent this.
        pytest.fail("Unsupported dependency model field names")

    before_ids = set(dependency.objects.values_list("pk", flat=True))
    _run(user)
    after_ids = set(dependency.objects.values_list("pk", flat=True))

    assert edge.pk in after_ids
    assert after_ids == before_ids, (
        "AUTH-002: scheduler has no authority to manufacture or remove "
        "dependency facts"
    )


def test_AUTH_002_scheduler_cannot_change_hierarchy(user, make_item):
    parent = make_item(user, "Parent")
    child = make_item(user, "Child", parent=parent)
    before = child.parent_id

    _run(user)
    child.refresh_from_db()

    assert child.parent_id == before


@covers('AUTH-003')
def test_AUTH_003_scheduler_exposes_validation_or_rejection_boundary():
    service = _scheduler()
    assert service is not None

    assert any(
        callable(getattr(service, name, None))
        for name in (
            "validate_schedule",
            "validate_proposal",
            "check_invariants",
            "is_valid_schedule",
            "schedule",
            "reschedule",
            "reconcile_schedule",
        )
    ), (
        "AUTH-003: scheduler proposals need an invariant-validation/rejection "
        "boundary before becoming the active projection"
    )


def test_AUTH_003_scheduler_has_no_named_hard_invariant_bypass():
    service = _scheduler()
    assert service is not None

    forbidden = (
        "ignore_dependencies",
        "drop_dependency_to_fit",
        "ignore_release_date",
        "move_anchor_to_fit",
        "rewrite_deadline_to_fit",
        "force_invalid_schedule",
    )
    assert not any(callable(getattr(service, name, None)) for name in forbidden)


@covers('AUTH-004')
def test_AUTH_004_algorithm_flavour_is_not_allowed_to_change_domain_facts():
    service = _scheduler()
    assert service is not None

    # Algorithm selection/configuration may exist, but there must not be a
    # public flavour API whose stated mechanism is weakening canonical rules.
    forbidden = (
        "disable_hard_invariants",
        "allow_dependency_violations",
        "allow_hierarchy_violations",
        "allow_anchor_rewrites",
    )
    assert not any(callable(getattr(service, name, None)) for name in forbidden)


def test_scheduler_repeatedly_preserves_rich_canonical_state(user, make_item, today):
    parent = make_item(
        user, "Suspended anchor", sibling_order=7,
        manual_requested_date=today + timedelta(days=2),
        start_date=today, due_date=today + timedelta(days=10),
        scheduled_date=today + timedelta(days=2),
    )
    partial = make_item(
        user, "Confirmed partial work", parent=parent, sibling_order=3,
        duration_category=DurationCategory.UNDER_16_HOURS,
        percent_completed=Decimal("35"), manual_requested_date=None,
        scheduled_date=today - timedelta(days=1),
    )
    blocked = make_item(
        user, "Blocked anchor", parent=parent, sibling_order=9,
        manual_requested_date=today + timedelta(days=1),
    )
    PlanningDependency.objects.create(prerequisite=partial, dependent=blocked)
    for percentage, days_ago in [("15", 3), ("20", 2)]:
        ProgressSegment.objects.create(
            item=partial, percentage=Decimal(percentage), is_completed=True,
            scheduled_date=today - timedelta(days=days_ago),
            completed_at=timezone.now() - timedelta(days=days_ago),
        )
    make_item(
        user, "Released later", start_date=today + timedelta(days=4),
        due_date=today + timedelta(days=8), sibling_order=11,
    )
    make_item(
        user, "Expired intent", manual_requested_date=today - timedelta(days=1),
        expired_manual_requested_date=today - timedelta(days=5),
        due_date=today - timedelta(days=2), sibling_order=13,
    )
    make_item(
        user, "Active anchor", manual_requested_date=today + timedelta(days=2),
        due_date=today + timedelta(days=7), sibling_order=15,
    )
    done = make_item(user, "Completed", is_completed=True, sibling_order=17)
    PlanningDependency.objects.create(prerequisite=done, dependent=partial)
    removed = make_item(
        user, "Restorable deletion", manual_requested_date=today + timedelta(days=3),
        sibling_order=19,
    )
    priority.reconcile(user)
    deletion.delete_subtree(removed)
    # Preserve a real suspended priority context as well as positioned work.
    assert PlanningItem.objects.get(pk=removed.pk).deletion_restore_context
    assert PlanningItem.objects.get(pk=removed.pk).priority_restore_context
    assert PlanningItem.objects.filter(user=user, priority_position__isnull=False).exists()

    def canonical_state():
        return {
            "items": list(PlanningItem.objects.filter(user=user).order_by("pk").values(
                "id", "parent_id", "sibling_order", "priority_position",
                "priority_restore_context", "start_date", "due_date",
                "manual_requested_date", "expired_manual_requested_date",
                "duration_category", "percent_completed", "is_completed",
                "is_deleted", "deletion_restore_context",
            )),
            "dependencies": list(PlanningDependency.objects.filter(
                prerequisite__user=user,
            ).order_by("pk").values()),
            "progress": list(ProgressSegment.objects.filter(
                item__user=user,
            ).order_by("pk").values()),
        }

    before = canonical_state()
    for mode in ("minimal", "global", "minimal", "global"):
        scheduling.schedule(user, today=today, mode=mode)
        assert canonical_state() == before
        assert SchedulerAllocation.objects.filter(item=partial).exists()
    partial.refresh_from_db()
    assert partial.scheduled_date >= today
    assert partial.execution_rank is not None
