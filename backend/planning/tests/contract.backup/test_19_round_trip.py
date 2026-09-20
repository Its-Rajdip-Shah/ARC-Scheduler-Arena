"""
ARC frozen-contract tests: semantic round trips RT-001..RT-004.

When an action and its valid inverse occur without a relevant intervening
change, ARC should return as closely as possible to the prior semantic state.
The toggled fact may change temporarily; unrelated intent must not drift.
"""

from __future__ import annotations

import importlib

import pytest

from planning.models import PlanningItem
from planning.services import hierarchy, priority

pytestmark = pytest.mark.django_db

CONTRACT_IDS = {"RT-001", "RT-002", "RT-003", "RT-004"}


def _lifecycle_callable(*names):
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


def _fields():
    return {f.name for f in PlanningItem._meta.get_fields()}


def _semantic(item):
    item.refresh_from_db()
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
    fields = _fields()
    return {
        name: getattr(item, name)
        for name in names
        if name in fields or hasattr(item, name)
    }


def _frontier(user):
    priority.reconcile(user)
    return list(priority.ordered(user).values_list("pk", flat=True))


def test_RT_001_delete_restore_round_trip_preserves_semantic_identity(
    user, make_item
):
    delete = _lifecycle_callable("delete", "soft_delete", "delete_item", "delete_subtree")
    restore = _lifecycle_callable("restore", "restore_item", "restore_subtree")
    assert delete is not None and restore is not None, (
        "RT-001 prerequisite: validated delete + restore domain commands"
    )

    item = make_item(
        user,
        "Round trip",
        duration_category="UNDER_4_HOURS",
    )
    priority.reconcile(user)
    before = _semantic(item)

    delete(item)
    restore(item)

    after = _semantic(item)
    assert after == before, (
        "RT-001: delete -> restore with no relevant intervening change should "
        "restore the same semantic item rather than a degraded approximation"
    )


def test_RT_002_complete_reopen_preserves_unrelated_semantics(user, make_item):
    item = make_item(user, "Task", duration_category="UNDER_4_HOURS")
    priority.reconcile(user)
    before = _semantic(item)

    hierarchy.complete_subtree(item)
    item.refresh_from_db()
    assert item.is_completed is True

    hierarchy.reopen(item)
    item.refresh_from_db()
    after = _semantic(item)

    # Completion itself is the lifecycle fact being inverted. Everything
    # represented in the semantic snapshot should now match again.
    assert after == before, (
        "RT-002: complete -> reopen must not drift dates, duration, hierarchy, "
        "priority context, anchor or progress"
    )


def test_RT_003_decompose_reverse_decompose_preserves_parent_intent(
    user, make_item, today
):
    fields = _fields()
    kwargs = {"duration_category": "UNDER_4_HOURS"}
    if "manual_requested_date" in fields:
        kwargs["manual_requested_date"] = today

    before_item = make_item(user, "Before")
    parent = make_item(user, "Parent", **kwargs)
    after_item = make_item(user, "After")
    priority.reconcile(user)

    before_parent = _semantic(parent)
    before_frontier = _frontier(user)

    child = make_item(user, "Temporary child", parent=parent)
    priority.reconcile(user)
    assert parent.pk not in _frontier(user)

    # Completing the only required child reverses the structural blocking
    # episode and exposes the unfinished parent as residual frontier work.
    hierarchy.complete_subtree(child)
    priority.reconcile(user)

    parent.refresh_from_db()
    after_parent = _semantic(parent)
    after_frontier = _frontier(user)

    assert after_parent == before_parent, (
        "RT-003: a reversible structural episode must preserve unaffected "
        "canonical parent intent"
    )
    assert after_frontier == before_frontier, (
        "RT-003: parent's priority neighbourhood must round-trip"
    )


def test_RT_004_anchor_unanchor_reanchor_does_not_corrupt_other_facts(
    user, make_item, today
):
    fields = _fields()
    assert "manual_requested_date" in fields, (
        "RT-004 prerequisite: canonical manual_requested_date"
    )

    item = make_item(
        user,
        "Anchored",
        start_date=today,
        due_date=today,
        duration_category="UNDER_4_HOURS",
        manual_requested_date=today,
    )
    priority.reconcile(user)

    before = _semantic(item)
    before_without_anchor = {
        key: value for key, value in before.items()
        if key != "manual_requested_date"
    }

    item.manual_requested_date = None
    item.save(update_fields=["manual_requested_date"])
    item.manual_requested_date = today
    item.save(update_fields=["manual_requested_date"])

    after = _semantic(item)
    after_without_anchor = {
        key: value for key, value in after.items()
        if key != "manual_requested_date"
    }

    assert item.manual_requested_date == today
    assert after_without_anchor == before_without_anchor, (
        "RT-004: anchor cycling must not mutate priority, deadline, release, "
        "hierarchy, duration or progress"
    )


def test_RT_002_repeated_complete_reopen_cycles_do_not_accumulate_drift(
    user, make_item
):
    before_item = make_item(user, "Before")
    item = make_item(user, "Target")
    after_item = make_item(user, "After")
    priority.reconcile(user)
    baseline = _semantic(item)
    baseline_frontier = _frontier(user)

    for _ in range(5):
        hierarchy.complete_subtree(item)
        hierarchy.reopen(item)
        priority.reconcile(user)

    assert _semantic(item) == baseline
    assert _frontier(user) == baseline_frontier
