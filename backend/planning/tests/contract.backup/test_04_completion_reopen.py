"""
ARC frozen-contract tests: completion <-> reopen transitions CR1-CR9.

Atomic completion tests use the current service/API. Splittable-progress and
dependency-conflict tests intentionally fail with clear messages until those
contract concepts exist.
"""

import pytest

from planning.models import PlanningItem
from planning.services import hierarchy, priority

pytestmark = pytest.mark.django_db


def _fields():
    return {field.name for field in PlanningItem._meta.get_fields()}


def _progress_field():
    for name in ("percent_completed", "completion_percent", "progress_percent"):
        if name in _fields():
            return name
    return None


def _dependency_model():
    """
    Locate a planning dependency model without hard-coding a future class name.
    A proper adapter can replace this once dependency implementation lands.
    """
    from django.apps import apps

    for model in apps.get_app_config("planning").get_models():
        names = {f.name for f in model._meta.get_fields()}
        lowered = model.__name__.lower()
        if "depend" in lowered and (
            {"prerequisite", "dependent"} <= names
            or {"predecessor", "successor"} <= names
        ):
            return model
    return None


def test_CR1_complete_atomic_leaf_leaves_active_frontier(user, make_item):
    item = make_item(user, "Atomic")
    priority.reconcile(user)
    assert item.priority_position is not None

    hierarchy.complete_subtree(item)
    item.refresh_from_db()

    assert item.is_completed is True
    assert item.priority_position is None


def test_CR2_reopen_atomic_task_returns_to_frontier_with_priority_context(
    user, make_item
):
    a = make_item(user, "A")
    b = make_item(user, "B")
    c = make_item(user, "C")
    priority.reconcile(user)

    before = [a.pk, b.pk, c.pk]
    assert list(priority.ordered(user).values_list("pk", flat=True)) == before

    hierarchy.complete_subtree(b)
    hierarchy.reopen(b)

    assert list(priority.ordered(user).values_list("pk", flat=True)) == before


def test_CR9_accidental_complete_then_reopen_round_trips_semantics(
    user, make_item
):
    parent = make_item(user, "Parent", item_type="GOAL")
    item = make_item(user, "Task", parent=parent)
    other = make_item(user, "Other")
    priority.reconcile(user)

    def semantic_snapshot():
        item.refresh_from_db()
        parent.refresh_from_db()
        other.refresh_from_db()
        return {
            "item_parent": item.parent_id,
            "item_completed": item.is_completed,
            "item_priority": item.priority_position,
            "parent_completed": parent.is_completed,
            "other_completed": other.is_completed,
            "priority_order": list(
                priority.ordered(user).values_list("pk", flat=True)
            ),
        }

    before = semantic_snapshot()
    hierarchy.complete_subtree(item)
    hierarchy.reopen(item)
    after = semantic_snapshot()

    assert after == before


def test_reopening_parent_does_not_cascade_reopen_to_completed_children(
    user, make_item
):
    parent = make_item(user, "Parent")
    child = make_item(user, "Child", parent=parent)

    hierarchy.complete_subtree(parent)
    hierarchy.reopen(parent)

    parent.refresh_from_db()
    child.refresh_from_db()
    assert parent.is_completed is False
    assert child.is_completed is True


def test_CR3_CR6_splittable_completion_has_canonical_progress_state():
    field = _progress_field()
    assert field is not None, (
        "CR3-CR6 MISSING: ARC needs canonical %completed plus reversible "
        "completed progress-segment history for splittable tasks"
    )


def test_CR3_future_scheduler_allocation_is_not_progress_until_confirmed():
    """
    This is primarily a schema/ownership guard until allocation models land:
    proposed allocation percentages must not be the same field as canonical
    confirmed progress.
    """
    progress = _progress_field()
    assert progress is not None, (
        "CR3 MISSING PREREQUISITE: canonical splittable progress not implemented"
    )

    from django.apps import apps

    allocation_models = [
        model
        for model in apps.get_app_config("planning").get_models()
        if "allocat" in model.__name__.lower()
    ]
    assert allocation_models, (
        "CR3 MISSING: no scheduler allocation/session representation exists. "
        "Future allocation must remain disposable until user confirms progress."
    )


def test_CR4_reopening_one_progress_segment_requires_segment_identity():
    progress = _progress_field()
    assert progress is not None, (
        "CR4 MISSING PREREQUISITE: canonical splittable progress not implemented"
    )

    from django.apps import apps

    candidate_models = []
    for model in apps.get_app_config("planning").get_models():
        lowered = model.__name__.lower()
        if any(token in lowered for token in ("progress", "segment", "allocation")):
            candidate_models.append(model)

    assert candidate_models, (
        "CR4 MISSING: reversible completed progress segments need canonical "
        "identity/history so reopening one segment does not erase unrelated progress"
    )


def test_CR7_dependency_conflict_on_completing_dependent_requires_explicit_resolution():
    dependency = _dependency_model()
    assert dependency is not None, (
        "CR7 MISSING PREREQUISITE: dependency graph is not implemented. "
        "When it exists, completing B while prerequisite A is incomplete must "
        "require cancel OR explicit edge removal; ARC may not silently break A->B."
    )


def test_CR8_reopening_completed_prerequisite_requires_explicit_resolution():
    dependency = _dependency_model()
    assert dependency is not None, (
        "CR8 MISSING PREREQUISITE: dependency graph is not implemented. "
        "Reopening prerequisite A while dependent B remains complete must require "
        "explicit conflict resolution rather than silently violating/removing A->B."
    )


def test_completion_endpoint_does_not_mutate_identity_dates_or_parent(
    user, make_item, today
):
    item = make_item(
        user,
        "Stable facts",
        start_date=today,
        due_date=today,
    )
    before = (item.pk, item.parent_id, item.start_date, item.due_date)

    hierarchy.complete_subtree(item)
    item.refresh_from_db()

    assert (item.pk, item.parent_id, item.start_date, item.due_date) == before


def test_reopen_endpoint_does_not_mutate_identity_dates_or_parent(
    user, make_item, today
):
    item = make_item(
        user,
        "Stable facts",
        start_date=today,
        due_date=today,
    )
    hierarchy.complete_subtree(item)
    before = (item.pk, item.parent_id, item.start_date, item.due_date)

    hierarchy.reopen(item)
    item.refresh_from_db()

    assert (item.pk, item.parent_id, item.start_date, item.due_date) == before
