\
"""Shared fixtures/helpers for ARC frozen-contract tests."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date

import pytest
from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone

from planning.models import ItemType, PlanningItem

User = get_user_model()


def covers(*requirement_ids: str):
    """Attach frozen-contract requirement IDs to a pytest test function."""
    def decorate(fn):
        fn.arc_contract_ids = frozenset(requirement_ids)
        return fn
    return decorate


@pytest.fixture
def today() -> date:
    return timezone.localdate()


@pytest.fixture
def user(db):
    return User.objects.create_user(
        "contract-alice@example.com",
        "corr3ct-horse-battery",
    )


@pytest.fixture
def other_user(db):
    return User.objects.create_user(
        "contract-bob@example.com",
        "corr3ct-horse-battery",
    )


@pytest.fixture
def make_item(db) -> Callable[..., PlanningItem]:
    """Create a PlanningItem using only fields that exist in the current schema.

    Contract tests deliberately assert for missing future fields elsewhere.
    Keeping the factory schema-tolerant lets the suite report many contract
    gaps in one run instead of dying on the first missing model field.

    Child temporal/anchor inheritance here represents canonical creation-time
    defaults only. Explicit child values win and later parent edits do not
    continuously rewrite the child.
    """
    field_names = {
        field.name
        for field in PlanningItem._meta.get_fields()
        if isinstance(field, models.Field)
    }

    def _make(
        user,
        title: str,
        item_type: str = ItemType.TASK,
        *,
        parent=None,
        **overrides,
    ) -> PlanningItem:
        values = {
            "user": user,
            "title": title,
            "item_type": item_type,
            "parent": parent,
        }

        unknown = set(overrides) - field_names
        if unknown:
            raise AssertionError(
                "Test factory was asked to set model fields ARC does not "
                f"currently expose: {sorted(unknown)}"
            )

        # Creation-time defaults from the parent's current canonical state.
        # The caller may hold a stale ORM instance after a domain command.
        if parent is not None:
            parent.refresh_from_db()
            if "start_date" in field_names:
                values["start_date"] = parent.start_date
            if "due_date" in field_names:
                values["due_date"] = parent.due_date
            if "manual_requested_date" in field_names:
                values["manual_requested_date"] = parent.manual_requested_date

        values.update(overrides)

        item = PlanningItem.objects.create(**values)

        # Introducing unfinished required work makes a completed parent
        # structurally incomplete again.
        if (
            parent is not None
            and not item.is_completed
            and parent.is_completed
        ):
            parent.is_completed = False
            parent.save(update_fields=["is_completed"])

        return item

    return _make


@pytest.fixture
def task(user, make_item):
    return make_item(user, "Task A")


@pytest.fixture
def second_task(user, make_item):
    return make_item(user, "Task B")


@pytest.fixture
def goal(user, make_item):
    return make_item(user, "Goal", ItemType.GOAL)


def model_field_names(model) -> set[str]:
    return {
        field.name
        for field in model._meta.get_fields()
        if isinstance(field, models.Field)
    }


def assert_model_has_fields(model, *field_names: str) -> None:
    actual = model_field_names(model)
    missing = [name for name in field_names if name not in actual]
    assert not missing, (
        f"{model.__name__} is missing frozen-contract field(s): {missing}. "
        f"Current concrete fields: {sorted(actual)}"
    )


def snapshot_item(item: PlanningItem) -> dict:
    """Small canonical snapshot useful for round-trip assertions."""
    item.refresh_from_db()
    return {
        field.name: getattr(item, field.name)
        for field in item._meta.concrete_fields
        if field.name not in {"created_at", "updated_at"}
    }
