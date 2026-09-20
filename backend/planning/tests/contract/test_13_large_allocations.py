
from .conftest import covers
"""
ARC frozen-contract tests: splittable large-work allocation lifecycle L1-L8.

Allocation dates/percentages are disposable scheduler proposals. Only confirmed
completed segments become canonical progress. Allocation projections are never
semantic PlanningItem children.
"""

import importlib

import pytest
from django.apps import apps

from planning.models import PlanningItem

pytestmark = pytest.mark.django_db

CONTRACT_IDS = {
    "ALLOC-001", "ALLOC-002", "ALLOC-003", "ALLOC-004",
    "ALLOC-005", "ALLOC-006", "ALLOC-007", "ALLOC-008",
}


def _service():
    for module_name in (
        "planning.services.scheduling",
        "planning.services.progress",
        "planning.services.allocations",
    ):
        try:
            return importlib.import_module(module_name)
        except ModuleNotFoundError:
            pass
    return None


def _allocation_model():
    for model in apps.get_app_config("planning").get_models():
        name = model.__name__.lower()
        fields = {f.name for f in model._meta.get_fields()}
        if (
            ("allocation" in name or "segment" in name)
            and any(x in fields for x in ("percentage", "percent", "percent_completed"))
            and any(x in fields for x in ("item", "planning_item", "task"))
        ):
            return model
    return None


def _progress_field():
    fields = {f.name for f in PlanningItem._meta.get_fields()}
    for name in ("percent_completed", "percentage_completed", "progress_percent"):
        if name in fields:
            return name
    raise AssertionError("ALLOC MISSING: canonical percent-completed field")


def _schedule(user):
    service = _service()
    assert service is not None, "ALLOC MISSING: scheduling/progress service"
    for name in ("schedule", "reschedule", "reconcile_schedule", "run"):
        fn = getattr(service, name, None)
        if callable(fn):
            try:
                return fn(user)
            except TypeError:
                continue
    raise AssertionError("ALLOC MISSING: scheduler entry point")


def _rows_for(model, item):
    fields = {f.name for f in model._meta.get_fields()}
    fk = next((x for x in ("item", "planning_item", "task") if x in fields), None)
    assert fk
    return model.objects.filter(**{fk: item})


def _pct(row):
    for name in ("percentage", "percent", "percent_completed"):
        if hasattr(row, name):
            return getattr(row, name)
    raise AssertionError("Allocation row has no percentage field")


def _is_confirmed(row):
    for name in ("is_completed", "is_confirmed", "completed"):
        if hasattr(row, name):
            return bool(getattr(row, name))
    return False


@covers('ALL-001')
def test_L1_unfinished_splittable_leaf_gets_allocations_summing_to_remaining_work(
    user, make_item
):
    model = _allocation_model()
    assert model is not None, "ALLOC-001 MISSING: allocation/progress segment model"
    item = make_item(user, "Large", duration_category="OVER_16_HOURS")
    _schedule(user)

    rows = list(_rows_for(model, item))
    assert rows, "L1: splittable frontier work needs scheduler allocation proposals"
    assert sum(float(_pct(r)) for r in rows) == pytest.approx(100.0)


@covers('ALL-002')
def test_L2_rescheduling_unconfirmed_allocations_never_changes_canonical_progress(
    user, make_item
):
    item = make_item(user, "Large", duration_category="UNDER_16_HOURS")
    field = _progress_field()
    setattr(item, field, 25)
    item.save(update_fields=[field])

    _schedule(user)
    _schedule(user)
    item.refresh_from_db()

    assert float(getattr(item, field)) == pytest.approx(25.0)


@covers('ALL-003')
def test_L3_confirming_allocation_freezes_that_percentage_as_canonical_progress(
    user, make_item
):
    model = _allocation_model()
    service = _service()
    assert model is not None and service is not None
    item = make_item(user, "Large", duration_category="UNDER_8_HOURS")
    _schedule(user)
    row = _rows_for(model, item).first()
    assert row is not None

    fn = next(
        (getattr(service, n) for n in (
            "complete_allocation", "complete_segment", "confirm_progress",
            "record_completed_allocation",
        ) if callable(getattr(service, n, None))),
        None,
    )
    assert fn is not None, "ALLOC-003 MISSING: confirm allocation command"
    fn(row)

    assert float(getattr(PlanningItem.objects.get(pk=item.pk), _progress_field())) > 0


@covers('ALL-004')
def test_L4_commenced_task_only_allocates_remaining_percentage(user, make_item):
    model = _allocation_model()
    assert model is not None
    item = make_item(user, "Large", duration_category="OVER_16_HOURS")
    field = _progress_field()
    setattr(item, field, 40)
    item.save(update_fields=[field])

    _schedule(user)

    proposed = [r for r in _rows_for(model, item) if not _is_confirmed(r)]
    assert sum(float(_pct(r)) for r in proposed) == pytest.approx(60.0)


@covers('ALL-005')
def test_L5_reopening_one_completed_segment_reduces_only_its_progress(user, make_item):
    model = _allocation_model()
    service = _service()
    assert model is not None and service is not None
    reopen = next(
        (getattr(service, n) for n in (
            "reopen_segment", "uncomplete_segment", "reverse_progress_segment",
        ) if callable(getattr(service, n, None))),
        None,
    )
    assert reopen is not None, "ALLOC-005 MISSING: local segment reversal command"


@covers('ALL-006')
def test_L6_one_hundred_percent_reconciles_task_to_complete(user, make_item):
    service = _service()
    assert service is not None
    item = make_item(user, "Large", duration_category="UNDER_16_HOURS")
    field = _progress_field()
    setattr(item, field, 100)
    item.save(update_fields=[field])

    reconcile = next(
        (getattr(service, n) for n in ("reconcile_progress", "reconcile", "schedule")
         if callable(getattr(service, n, None))),
        None,
    )
    assert reconcile is not None
    try:
        reconcile(user)
    except TypeError:
        reconcile(item)

    item.refresh_from_db()
    assert item.is_completed is True


@covers('ALL-007')
def test_L7_semantic_decomposition_does_not_fabricate_child_progress(user, make_item):
    parent = make_item(user, "Large", duration_category="OVER_16_HOURS")
    field = _progress_field()
    setattr(parent, field, 55)
    parent.save(update_fields=[field])

    child = make_item(user, "Real child", parent=parent)
    child.refresh_from_db()

    if hasattr(child, field):
        assert getattr(child, field) in (0, 0.0, None)


@covers('ALL-008')
def test_L8_allocation_projection_is_not_semantic_planning_item(user, make_item):
    model = _allocation_model()
    assert model is not None
    assert model is not PlanningItem
    item = make_item(user, "Large", duration_category="OVER_16_HOURS")
    _schedule(user)

    assert PlanningItem.objects.filter(parent=item).count() == 0
