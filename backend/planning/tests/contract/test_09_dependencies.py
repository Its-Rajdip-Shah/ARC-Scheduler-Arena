
from .conftest import covers
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


@covers('DEP-001')
def test_DP1_dependency_is_explicit_fact_separate_from_hierarchy_and_priority(
    user, make_item
):
    model, service = _require_dependency_layer()
    a = make_item(user, "A")
    b = make_item(user, "B")
    priority.reconcile(user)
    # reconcile() may bulk-update priority state; refresh before capturing the
    # canonical precondition rather than reading a stale ORM instance.
    b.refresh_from_db()
    before_parent = b.parent_id
    before_priority = b.priority_position

    _call(service, ("add", "add_dependency", "create_dependency"), a, b)
    b.refresh_from_db()

    assert b.parent_id == before_parent
    # Blocking removes active frontier membership, while saved neighbours
    # preserve preference. DP4 below requires immediate blocked exclusion.
    assert b.priority_position is None
    assert b.priority_restore_context['before'] == [a.pk]
    pre, dep = _edge_fields(model)
    assert model.objects.filter(**{f"{pre}_id": a.pk, f"{dep}_id": b.pk}).exists()
    service.remove(a, b)
    b.refresh_from_db()
    assert b.priority_position == before_priority


@covers('DEP-002')
def test_DP2_self_dependency_is_rejected_atomically(user, make_item):
    model, service = _require_dependency_layer()
    a = make_item(user, "A")

    with pytest.raises((ValidationError, ValueError)):
        _call(service, ("add", "add_dependency", "create_dependency"), a, a)

    pre, dep = _edge_fields(model)
    assert not model.objects.filter(
        **{f"{pre}_id": a.pk, f"{dep}_id": a.pk}
    ).exists()


@covers('DEP-003')
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


@covers('DEP-007')
def test_DP1_DP7_dependency_edits_are_tenant_isolated(user, other_user, make_item):
    _, service = _require_dependency_layer()
    a = make_item(user, "A")
    foreign = make_item(other_user, "Foreign B")

    with pytest.raises((ValidationError, ValueError, PermissionError)):
        _call(service, ("add", "add_dependency", "create_dependency"), a, foreign)


@covers('DEP-004')
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


@covers('DEP-004')
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


@covers('DEP-005', 'DEP-006')
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


@covers('DEP-008')
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


@covers('DEP-010')
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


@covers("DEP-009")
def test_DP9_scheduler_cannot_place_dependant_before_incomplete_prerequisite(
    user, make_item, today
):
    """A scheduler flavour violating hard dependency precedence is invalid."""
    import importlib

    dependency_service = None
    for module_name in (
        "planning.services.dependencies",
        "planning.services.dependency",
    ):
        try:
            dependency_service = importlib.import_module(module_name)
            break
        except ModuleNotFoundError:
            continue

    assert dependency_service is not None, (
        "DEP-009 prerequisite: canonical dependency service/graph"
    )

    add = next(
        (
            getattr(dependency_service, name)
            for name in (
                "add_dependency",
                "create_dependency",
                "depend_on",
                "add",
            )
            if callable(getattr(dependency_service, name, None))
        ),
        None,
    )
    assert add is not None, "DEP-009 prerequisite: dependency creation command"

    prerequisite = make_item(user, "Prerequisite")
    dependant = make_item(user, "Dependant")

    created = False
    for args in (
        (user, prerequisite, dependant),
        (prerequisite, dependant),
        (user, prerequisite.pk, dependant.pk),
        (prerequisite.pk, dependant.pk),
    ):
        try:
            add(*args)
            created = True
            break
        except TypeError:
            continue

    assert created, "DEP-009: dependency command has no supported domain signature"

    scheduler = _scheduler_service() if "_scheduler_service" in globals() else None
    if scheduler is None:
        for module_name in (
            "planning.services.scheduling",
            "planning.services.scheduler",
        ):
            try:
                scheduler = importlib.import_module(module_name)
                break
            except ModuleNotFoundError:
                continue

    assert scheduler is not None, "DEP-009 prerequisite: scheduler service"

    fn = next(
        (
            getattr(scheduler, name)
            for name in ("schedule", "reschedule", "run", "reconcile_schedule")
            if callable(getattr(scheduler, name, None))
        ),
        None,
    )
    assert fn is not None

    try:
        fn(user)
    except TypeError:
        fn(user, today)

    dependant.refresh_from_db()
    prerequisite.refresh_from_db()

    # An incomplete prerequisite must prevent executable placement of dependant.
    assert prerequisite.is_completed or dependant.scheduled_date is None, (
        "DEP-009: scheduler placed a dependant while its hard prerequisite "
        "remained incomplete."
    )
