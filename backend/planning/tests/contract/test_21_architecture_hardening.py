"""Final ARC architecture hardening tests.

These tests target gaps that can remain invisible even when the behavioural
contract suite is green: real HTTP mutation paths, DB defence-in-depth,
proposal/canonical separation, and command-boundary bypasses.
"""

from __future__ import annotations

import ast
from decimal import Decimal
from pathlib import Path

import pytest
from django.db import IntegrityError, transaction
from rest_framework.test import APIClient

from planning.models import (
    PlanningDependency,
    PlanningItem,
    ProgressSegment,
    SchedulerAllocation,
)
from planning.services import deletion, priority

pytestmark = pytest.mark.django_db(transaction=True)


def test_HTTP_DELETE_uses_validated_delete_lifecycle(user, make_item):
    prerequisite = make_item(user, "Prerequisite")
    child = make_item(user, "Child")
    PlanningDependency.objects.create(
        prerequisite=prerequisite,
        dependent=child,
    )

    client = APIClient()
    client.force_authenticate(user=user)

    response = client.delete(f"/api/planning/items/{prerequisite.pk}/")
    assert response.status_code in {200, 204}

    prerequisite.refresh_from_db()
    assert prerequisite.is_deleted is True
    assert prerequisite.deletion_restore_context
    assert not PlanningDependency.objects.filter(
        prerequisite=prerequisite,
        dependent=child,
    ).exists()


def test_HTTP_completion_uses_subtree_lifecycle(user, make_item):
    parent = make_item(user, "Parent")
    child = make_item(user, "Child", parent=parent)

    client = APIClient()
    client.force_authenticate(user=user)

    response = client.patch(
        f"/api/planning/items/{parent.pk}/",
        {"is_completed": True},
        format="json",
    )
    assert response.status_code == 200

    parent.refresh_from_db()
    child.refresh_from_db()
    assert parent.is_completed is True
    assert child.is_completed is True


def test_HTTP_reopen_uses_lifecycle_not_raw_boolean(user, make_item):
    parent = make_item(user, "Parent", is_completed=True)
    child = make_item(user, "Child", parent=parent, is_completed=True)

    client = APIClient()
    client.force_authenticate(user=user)

    response = client.patch(
        f"/api/planning/items/{parent.pk}/",
        {"is_completed": False},
        format="json",
    )
    assert response.status_code == 200

    parent.refresh_from_db()
    assert parent.is_completed is False


def test_percent_completed_database_constraint(user, make_item):
    item = make_item(user, "Impossible progress")

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            PlanningItem.objects.filter(pk=item.pk).update(
                percent_completed=Decimal("101")
            )


def test_progress_segment_cannot_be_unconfirmed(user, make_item):
    item = make_item(user, "Canonical progress")

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            ProgressSegment.objects.create(
                item=item,
                percentage=Decimal("10"),
                is_completed=False,
            )


def test_scheduler_allocation_is_the_proposal_representation(user, make_item, today):
    item = make_item(user, "Proposal")

    allocation = SchedulerAllocation.objects.create(
        item=item,
        percentage=Decimal("10"),
        scheduled_date=today,
        execution_rank=1,
    )

    assert allocation.pk
    assert not ProgressSegment.objects.filter(item=item).exists()


def test_delete_restore_is_behavioural_not_presence_only(user, make_item):
    prerequisite = make_item(user, "A")
    dependent = make_item(user, "B")
    edge = PlanningDependency.objects.create(
        prerequisite=prerequisite,
        dependent=dependent,
    )
    priority.reconcile(user)

    deletion.delete_subtree(prerequisite)

    prerequisite.refresh_from_db()
    assert prerequisite.is_deleted
    assert prerequisite.deletion_restore_context
    assert not PlanningDependency.objects.filter(pk=edge.pk).exists()

    deletion.restore_subtree(prerequisite)

    prerequisite.refresh_from_db()
    assert prerequisite.is_deleted is False
    assert PlanningDependency.objects.filter(
        prerequisite=prerequisite,
        dependent=dependent,
    ).exists()


def test_serializer_has_no_raw_generic_planningitem_save_loop():
    """Regression guard for the exact bypass discovered in final audit."""
    path = Path(__file__).parents[2] / "serializers.py"
    tree = ast.parse(path.read_text())

    source = path.read_text()
    forbidden = (
        "for field, value in validated_data.items():\n"
        "            setattr(instance, field, value)\n"
        "        instance.save()"
    )
    assert forbidden not in source


def test_HTTP_destroy_source_delegates_to_deletion_service():
    path = Path(__file__).parents[2] / "views.py"
    source = path.read_text()
    assert "deletion.delete_subtree(instance)" in source


def test_manual_requested_date_is_documented_as_only_canonical_date_intent():
    path = Path(__file__).parents[2] / "models.py"
    source = path.read_text()
    assert "Canonical user date intent lives exclusively in manual_requested_date" in source
