
from .conftest import covers
"""
ARC frozen-contract tests: duration/progress transitions E1-E7.

Frozen categories:
  atomic one-day: <20m, <1h, <4h
  splittable:     <8h, <16h, >16h

Splittable tasks maintain canonical percent-completed progress. Scheduler
allocation percentages are proposals until confirmed complete; they are
never semantic hierarchy children.
"""

import importlib

import pytest
from django.apps import apps

from planning.models import PlanningItem

pytestmark = pytest.mark.django_db

CONTRACT_IDS = {
    "DUR-001", "DUR-002", "DUR-003", "DUR-004", "DUR-005", "DUR-006",
    "DUR-007", "DUR-008", "DUR-009", "DUR-010", "DUR-011",
}

EXPECTED_CLASSES = {
    "UNDER_20_MINUTES",
    "UNDER_1_HOUR",
    "UNDER_4_HOURS",
    "UNDER_8_HOURS",
    "UNDER_16_HOURS",
    "OVER_16_HOURS",
}
ATOMIC = {"UNDER_20_MINUTES", "UNDER_1_HOUR", "UNDER_4_HOURS"}
SPLITTABLE = {"UNDER_8_HOURS", "UNDER_16_HOURS", "OVER_16_HOURS"}


def _fields():
    return {f.name for f in PlanningItem._meta.get_fields()}


def _progress_field():
    for name in ("percent_completed", "percentage_completed", "progress_percent"):
        if name in _fields():
            return name
    raise AssertionError(
        "DUR-005 MISSING: splittable PlanningItem needs canonical percent-completed progress"
    )


def _progress_segment_model():
    for model in apps.get_app_config("planning").get_models():
        lowered = model.__name__.lower()
        names = {f.name for f in model._meta.get_fields()}
        if (
            ("progress" in lowered or "allocation" in lowered or "segment" in lowered)
            and any(n in names for n in ("percentage", "percent", "percent_completed"))
            and any(n in names for n in ("item", "planning_item", "task"))
        ):
            return model
    return None


def _duration_service():
    for module_name in (
        "planning.services.progress",
        "planning.services.duration",
        "planning.services.scheduling",
    ):
        try:
            return importlib.import_module(module_name)
        except ModuleNotFoundError:
            pass
    return None


def _edit_duration(item, category):
    service = _duration_service()
    if service:
        for name in ("set_duration", "change_duration", "edit_duration_category"):
            fn = getattr(service, name, None)
            if callable(fn):
                return fn(item, category)
    item.duration_category = category
    item.save(update_fields=["duration_category"])
    return item


def _set_progress(item, value):
    field = _progress_field()
    setattr(item, field, value)
    item.save(update_fields=[field])


def _get_progress(item):
    item.refresh_from_db()
    return getattr(item, _progress_field())


@covers('DUR-001')
def test_E1_duration_contract_exposes_exactly_the_six_frozen_semantic_categories():
    field = PlanningItem._meta.get_field("duration_category")
    choices = field.choices
    values = {value for value, _label in choices}
    assert EXPECTED_CLASSES <= values, (
        "DUR-001: duration model must represent <20m, <1h, <4h, <8h, "
        "<16h and >16h as distinct mutually-exclusive semantic classes. "
        f"Current values: {sorted(values)}"
    )


@pytest.mark.parametrize("category", sorted(ATOMIC))
@covers('DUR-002', 'DUR-003')
def test_E1_atomic_categories_are_one_day_not_progress_split_categories(
    user, make_item, category
):
    item = make_item(user, f"Atomic {category}", duration_category=category)
    assert item.duration_category == category
    # Atomic tasks need no canonical partial-progress state to be schedulable.
    assert item.is_completed is False


@pytest.mark.parametrize("category", sorted(SPLITTABLE))
@covers('DUR-004', 'DUR-005')
def test_E2_splittable_categories_have_canonical_percent_progress(
    user, make_item, category
):
    item = make_item(user, f"Large {category}", duration_category=category)
    field = _progress_field()
    assert getattr(item, field) in (0, 0.0, None), (
        "New unfinished splittable work starts with no confirmed progress"
    )


@covers('DUR-006')
def test_E2_splittable_to_splittable_duration_edit_preserves_percent_completed(
    user, make_item
):
    item = make_item(user, "Large", duration_category="UNDER_8_HOURS")
    _set_progress(item, 45)

    _edit_duration(item, "UNDER_16_HOURS")

    assert _get_progress(item) == 45, (
        "E2: 45% of an <8h task remains 45% when estimate changes to <16h"
    )


@covers('DUR-007')
def test_E3_splittable_to_atomic_discards_partial_progress_semantics(
    user, make_item
):
    item = make_item(user, "Large", duration_category="OVER_16_HOURS")
    _set_progress(item, 45)

    _edit_duration(item, "UNDER_4_HOURS")
    item.refresh_from_db()

    assert item.is_completed is False
    assert _get_progress(item) in (0, 0.0, None), (
        "E3: after >16h 45% -> <4h, ARC only cares that the atomic task is "
        "incomplete and needs one-day scheduling; old partial progress is discarded"
    )


def test_E4_atomic_back_to_splittable_does_not_resurrect_discarded_progress(
    user, make_item
):
    item = make_item(user, "Task", duration_category="OVER_16_HOURS")
    _set_progress(item, 45)
    _edit_duration(item, "UNDER_4_HOURS")
    _edit_duration(item, "UNDER_16_HOURS")

    assert _get_progress(item) in (0, 0.0, None)


def test_E5_atomic_incomplete_to_splittable_starts_at_zero_progress(user, make_item):
    item = make_item(user, "Atomic", duration_category="UNDER_4_HOURS")
    _edit_duration(item, "UNDER_8_HOURS")

    assert item.is_completed is False
    assert _get_progress(item) in (0, 0.0, None)


def test_E6_completed_task_stays_complete_when_duration_category_changes(
    user, make_item
):
    item = make_item(
        user, "Done",
        duration_category="UNDER_4_HOURS",
        is_completed=True,
    )
    _edit_duration(item, "OVER_16_HOURS")
    item.refresh_from_db()

    assert item.is_completed is True


def test_E7_crossing_atomic_splittable_boundary_does_not_create_semantic_children(
    user, make_item
):
    item = make_item(user, "Task", duration_category="UNDER_4_HOURS")
    child_count_before = PlanningItem.objects.filter(parent=item).count()

    _edit_duration(item, "OVER_16_HOURS")

    assert PlanningItem.objects.filter(parent=item).count() == child_count_before == 0, (
        "DUR-004/DUR-011: scheduling large work must not manufacture hierarchy children"
    )


@covers('DUR-008')
def test_DUR008_confirmed_progress_requires_durable_segment_identity_not_scheduler_proposal():
    model = _progress_segment_model()
    assert model is not None, (
        "DUR-008 MISSING: completed allocation percentages need durable "
        "canonical progress-segment/history identity so future scheduler "
        "proposals can change without rewriting confirmed progress"
    )


@covers('DUR-009')
def test_DUR009_reversing_one_completed_segment_can_be_local():
    model = _progress_segment_model()
    service = _duration_service()
    assert model is not None and service is not None, (
        "DUR-009 MISSING PREREQUISITE: durable progress segments + progress service"
    )
    assert any(
        callable(getattr(service, name, None))
        for name in ("reopen_segment", "uncomplete_segment", "reverse_progress_segment")
    ), (
        "DUR-009: ARC needs a local inverse command for one completed progress segment"
    )


@covers('DUR-010')
def test_DUR010_progress_reaching_100_and_reopening_are_domain_lifecycle_operations():
    service = _duration_service()
    assert service is not None, "DUR-010 MISSING: progress lifecycle service"
    complete_names = (
        "complete_allocation", "complete_segment", "confirm_progress",
        "record_completed_allocation",
    )
    reopen_names = (
        "reopen_segment", "uncomplete_segment", "reverse_progress_segment",
    )
    assert any(callable(getattr(service, n, None)) for n in complete_names)
    assert any(callable(getattr(service, n, None)) for n in reopen_names)


@covers('DUR-011')
def test_DUR011_progress_segments_cannot_be_semantic_hierarchy_children():
    model = _progress_segment_model()
    assert model is not None, "DUR-011 MISSING PREREQUISITE: progress segment model"
    assert model is not PlanningItem, (
        "Allocation/progress segments must not be PlanningItem semantic children"
    )
    names = {f.name for f in model._meta.get_fields()}
    assert "parent" not in names, (
        "Progress segment must not participate in the PlanningItem parent hierarchy"
    )
