"""
ARC frozen-contract tests: dependency lifecycle DP1-DP8.

Dependencies are explicit, completion-based hard precedence constraints.
They are neither hierarchy nor priority.  A contradictory user mutation
must be cancelled or explicitly remove the dependency; ARC never silently
violates/deletes the edge.
"""

import importlib

import pytest
from django.apps import apps
from django.core.exceptions import ValidationError

from planning.models import PlanningItem
from planning.services import hierarchy, priority

pytestmark = pytest.mark.django_db

CONTRACT_IDS = {
    "DEP-001", "DEP-002", "DEP-003", "DEP-004", "DEP-005",
    "DEP-006", "DEP-007", "DEP-008", "DEP-009", "DEP-010",
}


def _dependency_model():
    for model in apps.get_app_config("planning").get_models():
        names = {f.name for f in model._meta.get_fields()}
        if "depend" in model.__name__.lower() and (
            {"prerequisite", "dependent"} <= names
            or {"predecessor", "successor"} <= names
        ):
            return model
    return None


def _dependency_service():
    for module_name in (
        "planning.services.dependencies",
        "planning.services.dependency",
        "planning.services.relationships",
    ):
        try:
            return importlib.import_module(module_name)
        except ModuleNotFoundError:
            pass
    return None


def _require_dependency_layer():
    model = _dependency_model()
    service = _dependency_service()
    assert model is not None and service is not None, (
        "DEP MISSING: ARC needs a canonical dependency graph plus domain "
        "commands. A -> B means B cannot execute until A is complete."
    )
    return model, service


def _edge_fields(model):
    names = {f.name for f in model._meta.get_fields()}
    if {"prerequisite", "dependent"} <= names:
        return "prerequisite", "dependent"
    if {"predecessor", "successor"} <= names:
        return "predecessor", "successor"
    raise AssertionError("Dependency model has no recognised endpoint fields")


def _call(service, names, *args, **kwargs):
    for name in names:
        fn = getattr(service, name, None)
        if callable(fn):
            return fn(*args, **kwargs)
    raise AssertionError(
        f"DEP MISSING: dependency service exposes none of {tuple(names)}"
    )


def _frontier_ids(user):
    priority.reconcile(user)
    return set(priority.ordered(user).values_list("pk", flat=True))


def test_DP1_dependency_is_explicit_fact_separate_from_hierarchy_and_priority(
    user, make_item
):
    model, service = _require_dependency_layer()
    a = make_item(user, "A")
    b = make_item(user, "B")
    priority.reconcile(user)
    before_parent = b.parent_id
    before_priority = b.priority_position

    _call(service, ("add", "add_dependency", "create_dependency"), a, b)
    b.refresh_from_db()

    assert b.parent_id == before_parent
    assert b.priority_position == before_priority
    pre, dep = _edge_fields(model)
    assert model.objects.filter(**{f"{pre}_id": a.pk, f"{dep}_id": b.pk}).exists()


def test_DP2_self_dependency_is_rejected_atomically(user, make_item):
    model, service = _require_dependency_layer()
    a = make_item(user, "A")

    with pytest.raises((ValidationError, ValueError)):
        _call(service, ("add", "add_dependency", "create_dependency"), a, a)

    pre, dep = _edge_fields(model)
    assert not model.objects.filter(
        **{f"{pre}_id": a.pk, f"{dep}_id": a.pk}
    ).exists()


def test_DP5_dependency_cycle_is_rejected_without_deleting_existing_edges(
    user, make_item
):
    model, service = _require_dependency_layer()
    a = make_item(user, "A")
    b = make_item(user, "B")
    c = make_item(user, "C")
    _call(service, ("add", "add_dependency", "create_dependency"), a, b)
    _call(service, ("add", "add_dependency", "create_dependency"), b, c)

    with pytest.raises((ValidationError, ValueError)):
        _call(service, ("add", "add_dependency", "create_dependency"), c, a)

    pre, dep = _edge_fields(model)
    assert model.objects.filter(**{f"{pre}_id": a.pk, f"{dep}_id": b.pk}).exists()
    assert model.objects.filter(**{f"{pre}_id": b.pk, f"{dep}_id": c.pk}).exists()
    assert not model.objects.filter(**{f"{pre}_id": c.pk, f"{dep}_id": a.pk}).exists()


def test_DP1_DP7_dependency_edits_are_tenant_isolated(user, other_user, make_item):
    _, service = _require_dependency_layer()
    a = make_item(user, "A")
    foreign = make_item(other_user, "Foreign B")

    with pytest.raises((ValidationError, ValueError, PermissionError)):
        _call(service, ("add", "add_dependency", "create_dependency"), a, foreign)


def test_DP4_incomplete_prerequisite_blocks_dependant_from_execution_frontier(
    user, make_item
):
    _, service = _require_dependency_layer()
    a = make_item(user, "A")
    b = make_item(user, "B")
    _call(service, ("add", "add_dependency", "create_dependency"), a, b)

    assert a.pk in _frontier_ids(user)
    assert b.pk not in _frontier_ids(user), (
        "DP4: B cannot be executable while required prerequisite A is incomplete"
    )


def test_DP3_completing_prerequisite_may_unblock_dependant(user, make_item):
    _, service = _require_dependency_layer()
    a = make_item(user, "A")
    b = make_item(user, "B")
    _call(service, ("add", "add_dependency", "create_dependency"), a, b)
    assert b.pk not in _frontier_ids(user)

    hierarchy.complete_subtree(a)

    assert b.pk in _frontier_ids(user)


def test_DP4_reopening_prerequisite_reblocks_unfinished_dependant(user, make_item):
    _, service = _require_dependency_layer()
    a = make_item(user, "A")
    b = make_item(user, "B")
    _call(service, ("add", "add_dependency", "create_dependency"), a, b)
    hierarchy.complete_subtree(a)
    assert b.pk in _frontier_ids(user)

    hierarchy.reopen(a)

    assert b.pk not in _frontier_ids(user)


def test_DP5_DP6_dependency_on_parent_blocks_dependant_until_required_subtree_and_parent_complete(
    user, make_item
):
    _, service = _require_dependency_layer()
    parent = make_item(user, "A parent")
    child = make_item(user, "A child", parent=parent)
    b = make_item(user, "B")
    _call(service, ("add", "add_dependency", "create_dependency"), parent, b)

    assert b.pk not in _frontier_ids(user)
    hierarchy.complete_subtree(child)
    assert b.pk not in _frontier_ids(user), (
        "Completing A's child exposes residual A; it does not yet satisfy A -> B"
    )
    hierarchy.complete_subtree(parent)
    assert b.pk in _frontier_ids(user)


def test_DP8_contradictory_completion_requires_explicit_resolution_not_silent_edge_delete(
    user, make_item
):
    model, service = _require_dependency_layer()
    a = make_item(user, "A")
    b = make_item(user, "B")
    _call(service, ("add", "add_dependency", "create_dependency"), a, b)
    pre, dep = _edge_fields(model)

    # Raw hierarchy completion must not be allowed to make B complete while
    # silently deleting A -> B. A domain command may instead raise a
    # conflict that the UI resolves as cancel OR remove-edge-and-proceed.
    try:
        hierarchy.complete_subtree(b)
    except (ValidationError, ValueError):
        pass

    assert model.objects.filter(**{f"{pre}_id": a.pk, f"{dep}_id": b.pk}).exists(), (
        "DP8: contradictory action may be rejected, but dependency cannot vanish silently"
    )


def test_DP10_mvp_dependency_satisfaction_is_binary_completion_not_percent_threshold():
    model, _ = _require_dependency_layer()
    field_names = {f.name for f in model._meta.get_fields()}
    forbidden_threshold_fields = {
        "required_percent", "threshold_percent", "progress_threshold",
        "completion_threshold",
    }
    assert not (field_names & forbidden_threshold_fields), (
        "DP10: partial/progress-threshold dependencies are deferred from MVP"
    )
