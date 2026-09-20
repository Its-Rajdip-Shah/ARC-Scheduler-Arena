"""
ARC frozen-contract tests: creation transitions C1-C6.

Contract:
C1 root creation
C2 child creation with parent date defaults
C3 explicit child temporal divergence
C4 child creation under anchored executable parent
C5 unfinished child added to completed parent
C6 decomposition of partially-completed splittable work
"""

from datetime import timedelta

import pytest

from planning.models import PlanningItem

pytestmark = pytest.mark.django_db


def _fields():
    return {field.name for field in PlanningItem._meta.get_fields()}


def _post_item(client, **payload):
    base = {"item_type": "TASK", "title": payload.pop("title", "Contract task")}
    base.update(payload)
    return client.post("/api/planning/items/", base, format="json")


def test_C1_create_root_persists_canonical_task_and_enters_reconciliation(
    user, api_for, today
):
    response = _post_item(
        api_for(user),
        title="Root task",
        start_date=str(today + timedelta(days=1)),
        due_date=str(today + timedelta(days=7)),
    )
    assert response.status_code == 201, response.data

    item = PlanningItem.objects.get(pk=response.data["id"])
    assert item.parent_id is None
    assert item.is_completed is False
    assert item.is_deleted is False
    assert item.start_date == today + timedelta(days=1)
    assert item.due_date == today + timedelta(days=7)
    assert item.priority_position is not None


def test_C2_child_creation_defaults_release_and_deadline_from_parent(
    user, api_for, make_item, today
):
    """
    The frozen contract says the create-child form/API must be able to derive
    parent dates when the user leaves them unspecified. Once committed, those
    dates belong to the child.
    """
    parent = make_item(
        user,
        "Parent",
        start_date=today + timedelta(days=2),
        due_date=today + timedelta(days=9),
    )

    response = _post_item(
        api_for(user),
        title="Child",
        parent=parent.pk,
    )
    assert response.status_code == 201, response.data

    child = PlanningItem.objects.get(pk=response.data["id"])
    assert child.parent_id == parent.pk
    assert child.start_date == parent.start_date, (
        "C2 MISSING: child creation must default release/start_date from parent"
    )
    assert child.due_date == parent.due_date, (
        "C2 MISSING: child creation must default deadline/due_date from parent"
    )


def test_C2_committed_child_dates_do_not_track_future_parent_edits(
    user, api_for, make_item, today
):
    parent = make_item(
        user,
        "Parent",
        start_date=today + timedelta(days=1),
        due_date=today + timedelta(days=8),
    )
    response = _post_item(api_for(user), title="Child", parent=parent.pk)
    assert response.status_code == 201, response.data
    child = PlanningItem.objects.get(pk=response.data["id"])

    expected = (child.start_date, child.due_date)

    parent.start_date = today + timedelta(days=3)
    parent.due_date = today + timedelta(days=12)
    parent.save(update_fields=["start_date", "due_date"])
    child.refresh_from_db()

    assert (child.start_date, child.due_date) == expected


def test_C3_explicit_child_date_divergence_is_preserved(
    user, api_for, make_item, today
):
    parent = make_item(
        user,
        "Parent",
        start_date=today + timedelta(days=3),
        due_date=today + timedelta(days=8),
    )
    explicit_release = today + timedelta(days=1)
    explicit_due = today + timedelta(days=12)

    response = _post_item(
        api_for(user),
        title="Divergent child",
        parent=parent.pk,
        start_date=str(explicit_release),
        due_date=str(explicit_due),
    )

    # A warning/confirmation protocol may eventually make the first request a
    # non-2xx "confirmation required" response. Until that transport exists,
    # acceptance is valid only if the explicit values are preserved exactly.
    assert response.status_code == 201, (
        "C3 requires either explicit-confirmation semantics or successful "
        f"creation preserving the user's divergent dates. Got {response.status_code}: "
        f"{getattr(response, 'data', None)}"
    )
    child = PlanningItem.objects.get(pk=response.data["id"])
    assert child.start_date == explicit_release
    assert child.due_date == explicit_due


def test_C4_anchored_parent_becoming_structural_preserves_parent_anchor_and_inherits_it(
    user, api_for, make_item, today
):
    if "manual_requested_date" not in _fields():
        pytest.fail("C4 MISSING: PlanningItem has no canonical manual_requested_date/anchor")

    anchor = today + timedelta(days=4)
    parent = make_item(user, "Anchored parent", scheduled_date=anchor)
    parent.manual_requested_date = anchor
    parent.save(update_fields=["manual_requested_date"])

    response = _post_item(api_for(user), title="Required child", parent=parent.pk)
    assert response.status_code == 201, response.data

    parent.refresh_from_db()
    child = PlanningItem.objects.get(pk=response.data["id"])

    assert parent.manual_requested_date == anchor, (
        "C4: structural transition must suspend/preserve, not erase, parent anchor"
    )
    assert child.manual_requested_date == anchor, (
        "C4: required child must inherit anchored parent's date intent"
    )
    assert parent.priority_position is None, (
        "C4: parent with unfinished required child is structural/non-frontier"
    )


def test_C5_adding_unfinished_child_to_completed_parent_reopens_structural_completion(
    user, api_for, make_item
):
    parent = make_item(user, "Completed parent", is_completed=True)

    response = _post_item(api_for(user), title="New unfinished child", parent=parent.pk)
    assert response.status_code == 201, response.data

    parent.refresh_from_db()
    child = PlanningItem.objects.get(pk=response.data["id"])

    assert child.is_completed is False
    assert parent.is_completed is False, (
        "C5 MISSING: a completed parent cannot remain semantically completed "
        "after an unfinished required child is added"
    )


def test_C6_decomposing_partial_splittable_task_does_not_fabricate_child_progress(
    user, api_for, make_item
):
    progress_names = ("percent_completed", "completion_percent", "progress_percent")
    progress_field = next((name for name in progress_names if name in _fields()), None)
    if progress_field is None:
        pytest.fail(
            "C6 MISSING PREREQUISITE: no canonical percent-completed field for "
            "splittable tasks"
        )

    # The exact frozen duration enum implementation is allowed to evolve.
    # This test finds a splittable category by contract-oriented names if one exists.
    duration_field = PlanningItem._meta.get_field("duration_category")
    choices = {value for value, _label in duration_field.choices}
    splittable = next(
        (
            value for value in choices
            if any(token in value.upper() for token in ("8", "16", "OVER_16", "GT_16"))
        ),
        None,
    )
    assert splittable is not None, (
        "C6 MISSING PREREQUISITE: duration categories do not represent ARC's "
        "splittable <8h/<16h/>16h classes"
    )

    parent = make_item(user, "Partial large task", duration_category=splittable)
    setattr(parent, progress_field, 45)
    parent.save(update_fields=[progress_field])

    response = _post_item(api_for(user), title="Semantic child", parent=parent.pk)
    assert response.status_code == 201, response.data
    child = PlanningItem.objects.get(pk=response.data["id"])

    # Semantic decomposition must never manufacture child completion from the
    # parent's historical 45%.
    if hasattr(child, progress_field):
        assert getattr(child, progress_field) in (0, 0.0, None)
    assert child.is_completed is False
