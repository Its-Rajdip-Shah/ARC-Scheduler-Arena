"""
ARC state-semantics certification.

These tests are deliberately distinct from scheduling-invariant tests.

Invariant tests ask:
    "Is this database/schedule legal?"

These tests ask:
    "Did a legitimate state transition preserve the intended meaning of
     every piece of unrelated ARC data, recompute derived state correctly,
     and avoid stale/ghost state?"

Every scheduler-relevant mutation family should have an explicit contract
here before scheduler-algorithm experimentation begins.
"""

from dataclasses import dataclass
from enum import Enum


class Effect(str, Enum):
    PRESERVE = "preserve"
    CHANGE = "change"
    CLEAR = "clear"
    RECOMPUTE = "recompute"
    RESTORE = "restore"
    INACTIVE = "inactive"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True)
class TransitionContract:
    name: str
    hierarchy: Effect
    lifecycle: Effect
    factual_data: Effect
    priority: Effect
    scheduling: Effect
    anchor: Effect
    duration: Effect


TRANSITION_CONTRACTS = (
    # CRUD / ordinary factual edits
    TransitionContract(
        "create_root",
        Effect.CHANGE, Effect.PRESERVE, Effect.CHANGE,
        Effect.RECOMPUTE, Effect.RECOMPUTE,
        Effect.PRESERVE, Effect.CHANGE,
    ),
    TransitionContract(
        "create_child",
        Effect.CHANGE, Effect.PRESERVE, Effect.CHANGE,
        Effect.RECOMPUTE, Effect.RECOMPUTE,
        Effect.PRESERVE, Effect.CHANGE,
    ),
    TransitionContract(
        "edit_title",
        Effect.PRESERVE, Effect.PRESERVE, Effect.CHANGE,
        Effect.PRESERVE, Effect.PRESERVE,
        Effect.PRESERVE, Effect.PRESERVE,
    ),
    TransitionContract(
        "edit_duration",
        Effect.PRESERVE, Effect.PRESERVE, Effect.CHANGE,
        Effect.PRESERVE, Effect.RECOMPUTE,
        Effect.PRESERVE, Effect.CHANGE,
    ),
    TransitionContract(
        "edit_release",
        Effect.PRESERVE, Effect.PRESERVE, Effect.CHANGE,
        Effect.PRESERVE, Effect.RECOMPUTE,
        Effect.PRESERVE, Effect.PRESERVE,
    ),
    TransitionContract(
        "edit_deadline",
        Effect.PRESERVE, Effect.PRESERVE, Effect.CHANGE,
        Effect.PRESERVE, Effect.RECOMPUTE,
        Effect.PRESERVE, Effect.PRESERVE,
    ),

    # Hierarchy
    TransitionContract(
        "add_first_child",
        Effect.CHANGE, Effect.PRESERVE, Effect.PRESERVE,
        Effect.RECOMPUTE, Effect.RECOMPUTE,
        Effect.RECOMPUTE, Effect.INACTIVE,
    ),
    TransitionContract(
        "reparent_leaf",
        Effect.CHANGE, Effect.PRESERVE, Effect.PRESERVE,
        Effect.RECOMPUTE, Effect.RECOMPUTE,
        Effect.RECOMPUTE, Effect.PRESERVE,
    ),
    TransitionContract(
        "reparent_subtree",
        Effect.CHANGE, Effect.PRESERVE, Effect.PRESERVE,
        Effect.RECOMPUTE, Effect.RECOMPUTE,
        Effect.RECOMPUTE, Effect.PRESERVE,
    ),

    # Completion
    TransitionContract(
        "complete_leaf",
        Effect.PRESERVE, Effect.CHANGE, Effect.PRESERVE,
        Effect.RECOMPUTE, Effect.RECOMPUTE,
        Effect.RECOMPUTE, Effect.PRESERVE,
    ),
    TransitionContract(
        "complete_subtree",
        Effect.PRESERVE, Effect.CHANGE, Effect.PRESERVE,
        Effect.RECOMPUTE, Effect.RECOMPUTE,
        Effect.RECOMPUTE, Effect.PRESERVE,
    ),
    TransitionContract(
        "reopen_leaf",
        Effect.PRESERVE, Effect.CHANGE, Effect.PRESERVE,
        Effect.RECOMPUTE, Effect.RECOMPUTE,
        Effect.RECOMPUTE, Effect.PRESERVE,
    ),
    TransitionContract(
        "reopen_parent_only",
        Effect.PRESERVE, Effect.CHANGE, Effect.PRESERVE,
        Effect.RECOMPUTE, Effect.RECOMPUTE,
        Effect.RECOMPUTE, Effect.PRESERVE,
    ),

    # The semantic ambiguity we explicitly discovered.
    TransitionContract(
        "final_child_completed_parent_becomes_frontier",
        Effect.PRESERVE, Effect.CHANGE, Effect.PRESERVE,
        Effect.RECOMPUTE, Effect.RECOMPUTE,
        Effect.RECOMPUTE, Effect.UNRESOLVED,
    ),

    # Delete / restore
    TransitionContract(
        "delete_leaf",
        Effect.PRESERVE, Effect.CHANGE, Effect.PRESERVE,
        Effect.RECOMPUTE, Effect.RECOMPUTE,
        Effect.RECOMPUTE, Effect.PRESERVE,
    ),
    TransitionContract(
        "delete_subtree",
        Effect.PRESERVE, Effect.CHANGE, Effect.PRESERVE,
        Effect.RECOMPUTE, Effect.RECOMPUTE,
        Effect.RECOMPUTE, Effect.PRESERVE,
    ),
    TransitionContract(
        "restore_leaf",
        Effect.PRESERVE, Effect.CHANGE, Effect.RESTORE,
        Effect.RECOMPUTE, Effect.RECOMPUTE,
        Effect.RESTORE, Effect.RESTORE,
    ),
    TransitionContract(
        "restore_subtree",
        Effect.PRESERVE, Effect.CHANGE, Effect.RESTORE,
        Effect.RECOMPUTE, Effect.RECOMPUTE,
        Effect.RESTORE, Effect.RESTORE,
    ),

    # Priority
    TransitionContract(
        "priority_reorder",
        Effect.PRESERVE, Effect.PRESERVE, Effect.PRESERVE,
        Effect.CHANGE, Effect.PRESERVE,
        Effect.PRESERVE, Effect.PRESERVE,
    ),
    TransitionContract(
        "frontier_priority_departure",
        Effect.PRESERVE, Effect.PRESERVE, Effect.PRESERVE,
        Effect.RECOMPUTE, Effect.RECOMPUTE,
        Effect.RECOMPUTE, Effect.PRESERVE,
    ),
    TransitionContract(
        "frontier_priority_restoration",
        Effect.PRESERVE, Effect.PRESERVE, Effect.PRESERVE,
        Effect.RESTORE, Effect.RECOMPUTE,
        Effect.RECOMPUTE, Effect.PRESERVE,
    ),

    # Anchors
    TransitionContract(
        "create_anchor",
        Effect.PRESERVE, Effect.PRESERVE, Effect.PRESERVE,
        Effect.PRESERVE, Effect.CHANGE,
        Effect.CHANGE, Effect.PRESERVE,
    ),
    TransitionContract(
        "move_anchor",
        Effect.PRESERVE, Effect.PRESERVE, Effect.PRESERVE,
        Effect.PRESERVE, Effect.CHANGE,
        Effect.CHANGE, Effect.PRESERVE,
    ),
    TransitionContract(
        "remove_anchor",
        Effect.PRESERVE, Effect.PRESERVE, Effect.PRESERVE,
        Effect.PRESERVE, Effect.RECOMPUTE,
        Effect.CLEAR, Effect.PRESERVE,
    ),
    TransitionContract(
        "expire_anchor",
        Effect.PRESERVE, Effect.PRESERVE, Effect.PRESERVE,
        Effect.PRESERVE, Effect.RECOMPUTE,
        Effect.CLEAR, Effect.PRESERVE,
    ),

    # Time itself is a mutation of scheduler context.
    TransitionContract(
        "advance_today",
        Effect.PRESERVE, Effect.PRESERVE, Effect.PRESERVE,
        Effect.PRESERVE, Effect.RECOMPUTE,
        Effect.RECOMPUTE, Effect.PRESERVE,
    ),

    # Reversible / compound transitions.
    TransitionContract(
        "undo",
        Effect.RESTORE, Effect.RESTORE, Effect.RESTORE,
        Effect.RESTORE, Effect.RESTORE,
        Effect.RESTORE, Effect.RESTORE,
    ),
    TransitionContract(
        "redo",
        Effect.RESTORE, Effect.RESTORE, Effect.RESTORE,
        Effect.RESTORE, Effect.RESTORE,
        Effect.RESTORE, Effect.RESTORE,
    ),
)


def test_transition_contract_registry_has_unique_names():
    names = [contract.name for contract in TRANSITION_CONTRACTS]
    assert len(names) == len(set(names))


def test_only_known_semantic_question_is_parent_residual_duration():
    unresolved = [
        (contract.name, field)
        for contract in TRANSITION_CONTRACTS
        for field in (
            "hierarchy",
            "lifecycle",
            "factual_data",
            "priority",
            "scheduling",
            "anchor",
            "duration",
        )
        if getattr(contract, field) == Effect.UNRESOLVED
    ]

    assert unresolved == [
        ("final_child_completed_parent_becomes_frontier", "duration")
    ]


# ---------------------------------------------------------------------------
# Factual-data integrity
# ---------------------------------------------------------------------------

import pytest
from datetime import date, timedelta

from planning.models import PlanningItem, ItemType, DurationCategory
from planning.services import scheduling


@pytest.fixture
def semantic_user(django_user_model):
    return django_user_model.objects.create_user(
        email="semantic-user@example.com",
        password="test",
    )


def _semantic_item(user, title="Original", **overrides):
    """Create a richly populated item so preservation tests can detect loss."""
    values = {
        "title": title,
        "item_type": ItemType.TASK,
        "duration_category": DurationCategory.UNDER_1_HOUR,
        "start_date": date(2026, 9, 22),
        "due_date": date(2026, 10, 10),
        "is_completed": False,
        "is_deleted": False,
    }
    values.update(overrides)
    return PlanningItem.objects.create(user=user, **values)


def _factual_snapshot(item):
    """Fields whose meaning must not silently drift during unrelated edits."""
    item.refresh_from_db()
    return {
        "title": item.title,
        "item_type": item.item_type,
        "duration_category": item.duration_category,
        "start_date": item.start_date,
        "due_date": item.due_date,
        "parent_id": item.parent_id,
        "is_completed": item.is_completed,
        "is_deleted": item.is_deleted,
    }


@pytest.mark.django_db
def test_title_edit_preserves_all_other_factual_data(semantic_user):
    item = _semantic_item(semantic_user)
    before = _factual_snapshot(item)

    item.title = "Renamed only"
    item.save(update_fields=["title"])

    after = _factual_snapshot(item)

    assert after == {
        **before,
        "title": "Renamed only",
    }


@pytest.mark.django_db
def test_duration_edit_preserves_unrelated_factual_data(semantic_user):
    item = _semantic_item(semantic_user)
    before = _factual_snapshot(item)

    item.duration_category = DurationCategory.UNDER_4_HOURS
    item.save(update_fields=["duration_category"])

    after = _factual_snapshot(item)

    assert after == {
        **before,
        "duration_category": DurationCategory.UNDER_4_HOURS,
    }


@pytest.mark.django_db
def test_release_edit_preserves_unrelated_factual_data(semantic_user):
    item = _semantic_item(semantic_user)
    before = _factual_snapshot(item)

    new_release = date(2026, 9, 25)
    item.start_date = new_release
    item.save(update_fields=["start_date"])

    after = _factual_snapshot(item)

    assert after == {
        **before,
        "start_date": new_release,
    }


@pytest.mark.django_db
def test_deadline_edit_preserves_unrelated_factual_data(semantic_user):
    item = _semantic_item(semantic_user)
    before = _factual_snapshot(item)

    new_due = date(2026, 10, 20)
    item.due_date = new_due
    item.save(update_fields=["due_date"])

    after = _factual_snapshot(item)

    assert after == {
        **before,
        "due_date": new_due,
    }


@pytest.mark.django_db
def test_repeated_factual_edits_do_not_accumulate_semantic_drift(semantic_user):
    item = _semantic_item(semantic_user)
    original = _factual_snapshot(item)

    # Hammer mutable factual properties repeatedly.
    for i in range(50):
        item.title = f"Temporary {i}"
        item.duration_category = (
            DurationCategory.UNDER_4_HOURS
            if i % 2
            else DurationCategory.UNDER_20_MINUTES
        )
        item.start_date = date(2026, 9, 22) + timedelta(days=i % 5)
        item.due_date = date(2026, 10, 10) + timedelta(days=i % 7)
        item.save()

    # Return every edited factual property to its starting value.
    item.title = original["title"]
    item.duration_category = original["duration_category"]
    item.start_date = original["start_date"]
    item.due_date = original["due_date"]
    item.save()

    assert _factual_snapshot(item) == original


@pytest.mark.django_db
def test_title_change_is_scheduler_metamorphic(semantic_user):
    """
    A title contains no scheduling semantics.

    Renaming an item must therefore leave its scheduling result unchanged.
    """
    today = date(2026, 9, 20)

    item = _semantic_item(
        semantic_user,
        start_date=today,
        due_date=today + timedelta(days=10),
    )

    scheduling.schedule(semantic_user, today=today, mode="global")
    item.refresh_from_db()

    before = (
        item.scheduled_date,
        item.manual_requested_date,
        item.priority_position,
    )

    item.title = "Completely different words"
    item.save(update_fields=["title"])

    scheduling.schedule(semantic_user, today=today, mode="global")
    item.refresh_from_db()

    after = (
        item.scheduled_date,
        item.manual_requested_date,
        item.priority_position,
    )

    assert after == before


# ---------------------------------------------------------------------------
# Hierarchy / execution-frontier semantic integrity
# ---------------------------------------------------------------------------

from planning.services import hierarchy


def _semantic_state(item):
    """Full scheduler-relevant semantic state of one PlanningItem."""
    item.refresh_from_db()
    return {
        # Identity / factual meaning
        "title": item.title,
        "item_type": item.item_type,
        "description": item.description,
        "duration_category": item.duration_category,
        "start_date": item.start_date,
        "due_date": item.due_date,

        # Structure
        "parent_id": item.parent_id,
        "sibling_order": item.sibling_order,

        # Lifecycle
        "is_completed": item.is_completed,
        "is_deleted": item.is_deleted,

        # Scheduling-derived state
        "scheduled_date": item.scheduled_date,
        "manual_requested_date": item.manual_requested_date,
        "priority_position": item.priority_position,
        "priority_restore_context": item.priority_restore_context,
    }


def _factual_meaning(item):
    """
    Data whose meaning must survive hierarchy/scheduler transitions unless
    that transition explicitly targets the field.
    """
    state = _semantic_state(item)
    return {
        key: state[key]
        for key in (
            "title",
            "item_type",
            "description",
            "duration_category",
            "start_date",
            "due_date",
        )
    }


def _is_execution_frontier(item):
    item.refresh_from_db()

    if (
        item.is_completed
        or item.is_deleted
        or item.item_type not in (ItemType.TASK, ItemType.ASSIGNMENT)
    ):
        return False

    return not PlanningItem.objects.filter(
        user=item.user,
        parent=item,
        is_completed=False,
        is_deleted=False,
    ).exists()


@pytest.mark.django_db
def test_adding_first_child_preserves_parent_factual_meaning(semantic_user):
    today = date(2026, 9, 20)

    parent = _semantic_item(
        semantic_user,
        "Assignment",
        item_type=ItemType.ASSIGNMENT,
        start_date=today,
        due_date=today + timedelta(days=14),
    )

    scheduling.schedule(semantic_user, today=today, mode="global")
    parent.refresh_from_db()

    assert _is_execution_frontier(parent)
    before = _factual_meaning(parent)

    child = _semantic_item(
        semantic_user,
        "Implementation",
        parent=parent,
        start_date=today,
        due_date=today + timedelta(days=10),
    )

    scheduling.schedule(semantic_user, today=today, mode="global")

    assert _factual_meaning(parent) == before
    assert not _is_execution_frontier(parent)
    assert _is_execution_frontier(child)

    parent.refresh_from_db()
    assert parent.scheduled_date is None
    assert child.scheduled_date is not None


@pytest.mark.django_db
def test_reopening_child_demotes_exposed_parent_without_factual_damage(
    semantic_user,
):
    today = date(2026, 9, 20)

    parent = _semantic_item(
        semantic_user,
        "Assignment",
        item_type=ItemType.ASSIGNMENT,
        start_date=today,
        due_date=today + timedelta(days=14),
    )
    child = _semantic_item(
        semantic_user,
        "Implementation",
        parent=parent,
        start_date=today,
        due_date=today + timedelta(days=10),
        is_completed=True,
    )

    scheduling.schedule(semantic_user, today=today, mode="global")
    assert _is_execution_frontier(parent)

    parent_before = _factual_meaning(parent)
    child_before = _factual_meaning(child)

    hierarchy.reopen(child)

    assert _factual_meaning(parent) == parent_before
    assert _factual_meaning(child) == child_before
    assert not _is_execution_frontier(parent)
    assert _is_execution_frontier(child)

    parent.refresh_from_db()
    assert parent.scheduled_date is None


@pytest.mark.django_db
def test_final_child_completion_exposes_parent_without_factual_damage(
    semantic_user,
):
    """
    This intentionally does NOT yet assert the correct residual duration.

    It proves all other parent meaning survives the frontier transition while
    keeping residual-parent duration as our explicit unresolved contract.
    """
    today = date(2026, 9, 20)

    parent = _semantic_item(
        semantic_user,
        "Large assignment",
        item_type=ItemType.ASSIGNMENT,
        duration_category=DurationCategory.UNDER_4_HOURS,
        start_date=today,
        due_date=today + timedelta(days=14),
    )
    child = _semantic_item(
        semantic_user,
        "Final child",
        parent=parent,
        start_date=today,
        due_date=today + timedelta(days=10),
    )

    parent_before = _factual_meaning(parent)

    hierarchy.complete_subtree(child)

    assert _is_execution_frontier(parent)

    # Check everything except duration, whose frontier semantics are unresolved.
    after = _factual_meaning(parent)
    for field in (
        "title",
        "item_type",
        "description",
        "start_date",
        "due_date",
    ):
        assert after[field] == parent_before[field]


@pytest.mark.django_db
def test_reparent_leaf_preserves_child_factual_meaning_and_reconciles_both_branches(
    semantic_user,
):
    today = date(2026, 9, 20)

    source = _semantic_item(
        semantic_user,
        "Source",
        item_type=ItemType.ASSIGNMENT,
        start_date=today,
        due_date=today + timedelta(days=20),
    )
    target = _semantic_item(
        semantic_user,
        "Target",
        item_type=ItemType.ASSIGNMENT,
        start_date=today,
        due_date=today + timedelta(days=20),
    )
    child = _semantic_item(
        semantic_user,
        "Movable child",
        parent=source,
        start_date=today,
        due_date=today + timedelta(days=10),
    )

    child_before = _factual_meaning(child)

    scheduling.schedule(semantic_user, today=today, mode="global")

    assert not _is_execution_frontier(source)
    assert _is_execution_frontier(target)
    assert _is_execution_frontier(child)

    hierarchy.set_parent(child, target)

    assert _factual_meaning(child) == child_before
    assert child.parent_id == target.pk

    # Source lost its unfinished child and becomes executable.
    assert _is_execution_frontier(source)

    # Target gained the unfinished child and becomes structural.
    assert not _is_execution_frontier(target)

    target.refresh_from_db()
    assert target.scheduled_date is None


@pytest.mark.django_db
def test_reparent_subtree_preserves_descendant_meaning(semantic_user):
    today = date(2026, 9, 20)

    source = _semantic_item(
        semantic_user,
        "Source",
        item_type=ItemType.ASSIGNMENT,
        start_date=today,
    )
    target = _semantic_item(
        semantic_user,
        "Target",
        item_type=ItemType.ASSIGNMENT,
        start_date=today,
    )
    branch = _semantic_item(
        semantic_user,
        "Branch",
        item_type=ItemType.ASSIGNMENT,
        parent=source,
        start_date=today,
    )
    leaf = _semantic_item(
        semantic_user,
        "Deep leaf",
        parent=branch,
        duration_category=DurationCategory.UNDER_4_HOURS,
        start_date=today + timedelta(days=1),
        due_date=today + timedelta(days=12),
    )

    branch_before = _factual_meaning(branch)
    leaf_before = _factual_meaning(leaf)

    hierarchy.set_parent(branch, target)

    assert _factual_meaning(branch) == branch_before
    assert _factual_meaning(leaf) == leaf_before

    branch.refresh_from_db()
    leaf.refresh_from_db()

    assert branch.parent_id == target.pk
    assert leaf.parent_id == branch.pk


@pytest.mark.django_db
def test_parent_frontier_round_trip_does_not_accumulate_semantic_drift(
    semantic_user,
):
    """
    Repeated structural <-> frontier transitions must not progressively
    corrupt factual parent/child data.
    """
    today = date(2026, 9, 20)

    parent = _semantic_item(
        semantic_user,
        "Stable parent",
        item_type=ItemType.ASSIGNMENT,
        start_date=today,
        due_date=today + timedelta(days=30),
    )
    child = _semantic_item(
        semantic_user,
        "Stable child",
        parent=parent,
        start_date=today,
        due_date=today + timedelta(days=20),
    )

    parent_original = _factual_meaning(parent)
    child_original = _factual_meaning(child)

    for _ in range(25):
        hierarchy.complete_subtree(child)

        assert _is_execution_frontier(parent)

        hierarchy.reopen(child)

        assert not _is_execution_frontier(parent)
        assert _is_execution_frontier(child)

    assert _factual_meaning(parent) == parent_original
    assert _factual_meaning(child) == child_original


# ---------------------------------------------------------------------------
# Completion / deletion / restoration / priority semantic integrity
# ---------------------------------------------------------------------------

from planning.services import priority


def _active_frontier_ids(user):
    """Current execution frontier, independent of ordering."""
    items = PlanningItem.objects.filter(
        user=user,
        is_completed=False,
        is_deleted=False,
        item_type__in=(ItemType.TASK, ItemType.ASSIGNMENT),
    )
    return {
        item.pk
        for item in items
        if _is_execution_frontier(item)
    }


@pytest.mark.django_db
def test_complete_subtree_changes_only_lifecycle_not_factual_meaning(
    semantic_user,
):
    today = date(2026, 9, 20)

    parent = _semantic_item(
        semantic_user,
        "Branch",
        item_type=ItemType.ASSIGNMENT,
        start_date=today,
        due_date=today + timedelta(days=20),
    )
    child = _semantic_item(
        semantic_user,
        "Child",
        parent=parent,
        duration_category=DurationCategory.UNDER_4_HOURS,
        start_date=today + timedelta(days=1),
        due_date=today + timedelta(days=10),
    )
    grandchild = _semantic_item(
        semantic_user,
        "Grandchild",
        parent=child,
        start_date=today + timedelta(days=2),
        due_date=today + timedelta(days=8),
    )

    factual_before = {
        x.pk: _factual_meaning(x)
        for x in (parent, child, grandchild)
    }

    hierarchy.complete_subtree(parent)

    for item in (parent, child, grandchild):
        item.refresh_from_db()
        assert item.is_completed is True
        assert _factual_meaning(item) == factual_before[item.pk]
        assert item.scheduled_date is None
        assert item.priority_position is None


@pytest.mark.django_db
def test_reopen_parent_only_does_not_silently_reopen_descendants(
    semantic_user,
):
    today = date(2026, 9, 20)

    parent = _semantic_item(
        semantic_user,
        "Parent",
        item_type=ItemType.ASSIGNMENT,
        is_completed=True,
        start_date=today,
    )
    child = _semantic_item(
        semantic_user,
        "Child",
        parent=parent,
        is_completed=True,
        start_date=today,
    )
    grandchild = _semantic_item(
        semantic_user,
        "Grandchild",
        parent=child,
        is_completed=True,
        start_date=today,
    )

    child_before = _factual_meaning(child)
    grandchild_before = _factual_meaning(grandchild)

    hierarchy.reopen(parent)

    parent.refresh_from_db()
    child.refresh_from_db()
    grandchild.refresh_from_db()

    assert parent.is_completed is False
    assert child.is_completed is True
    assert grandchild.is_completed is True

    assert _factual_meaning(child) == child_before
    assert _factual_meaning(grandchild) == grandchild_before

    # Completed descendants do not prevent the reopened parent being frontier.
    assert _is_execution_frontier(parent)


@pytest.mark.django_db
def test_reopening_descendant_demotes_parent_and_preserves_factual_state(
    semantic_user,
):
    today = date(2026, 9, 20)

    parent = _semantic_item(
        semantic_user,
        "Parent",
        item_type=ItemType.ASSIGNMENT,
        start_date=today,
    )
    child = _semantic_item(
        semantic_user,
        "Child",
        parent=parent,
        is_completed=True,
        start_date=today,
    )

    scheduling.schedule(semantic_user, today=today, mode="global")
    assert _is_execution_frontier(parent)

    parent_before = _factual_meaning(parent)
    child_before = _factual_meaning(child)

    hierarchy.reopen(child)
    scheduling.schedule(semantic_user, today=today, mode="global")

    assert not _is_execution_frontier(parent)
    assert _is_execution_frontier(child)
    assert _factual_meaning(parent) == parent_before
    assert _factual_meaning(child) == child_before

    parent.refresh_from_db()
    assert parent.scheduled_date is None
    assert parent.priority_position is None


@pytest.mark.django_db
def test_priority_neighbourhood_survives_frontier_departure_and_return(
    semantic_user,
):
    """
    B leaving and later returning to the frontier should restore it to its
    meaningful priority neighbourhood rather than append it arbitrarily.
    """
    today = date(2026, 9, 20)

    a = _semantic_item(semantic_user, "A", start_date=today)
    b = _semantic_item(semantic_user, "B", start_date=today)
    c = _semantic_item(semantic_user, "C", start_date=today)

    # Raw test construction bypasses ARC's normal scheduling boundary.
    # Domain mutations reconcile priority; scheduler runs never own it.
    priority.reconcile(semantic_user)

    priority.reorder(semantic_user, a.pk, 1)
    priority.reorder(semantic_user, b.pk, 2)
    priority.reorder(semantic_user, c.pk, 3)

    a.refresh_from_db()
    b.refresh_from_db()
    c.refresh_from_db()

    assert [a.priority_position, b.priority_position, c.priority_position] == [1, 2, 3]

    # Adding an unfinished child removes B from the execution frontier.
    child = _semantic_item(
        semantic_user,
        "B child",
        parent=b,
        start_date=today,
    )
    priority.reconcile(semantic_user)
    scheduling.schedule(semantic_user, today=today, mode="global")

    b.refresh_from_db()
    assert not _is_execution_frontier(b)
    assert b.priority_position is None

    # Completing that child exposes B again.
    hierarchy.complete_subtree(child)
    scheduling.schedule(semantic_user, today=today, mode="global")

    a.refresh_from_db()
    b.refresh_from_db()
    c.refresh_from_db()

    assert _is_execution_frontier(b)
    assert [a.priority_position, b.priority_position, c.priority_position] == [1, 2, 3]


@pytest.mark.django_db
def test_repeated_priority_frontier_round_trip_has_no_order_drift(
    semantic_user,
):
    today = date(2026, 9, 20)

    a = _semantic_item(semantic_user, "A", start_date=today)
    b = _semantic_item(semantic_user, "B", start_date=today)
    c = _semantic_item(semantic_user, "C", start_date=today)

    # Raw test construction bypasses ARC's normal scheduling boundary.
    # Domain mutations reconcile priority; scheduler runs never own it.
    priority.reconcile(semantic_user)

    priority.reorder(semantic_user, a.pk, 1)
    priority.reorder(semantic_user, b.pk, 2)
    priority.reorder(semantic_user, c.pk, 3)

    child = _semantic_item(
        semantic_user,
        "B child",
        parent=b,
        is_completed=True,
        start_date=today,
    )

    for _ in range(25):
        hierarchy.reopen(child)
        scheduling.schedule(semantic_user, today=today, mode="global")

        hierarchy.complete_subtree(child)
        scheduling.schedule(semantic_user, today=today, mode="global")

        a.refresh_from_db()
        b.refresh_from_db()
        c.refresh_from_db()

        assert [a.priority_position, b.priority_position, c.priority_position] == [1, 2, 3]


@pytest.mark.django_db
def test_soft_delete_preserves_factual_row_data(semantic_user):
    """
    Soft deletion itself must not destroy factual meaning.

    This exercises the model state directly; API/history round-trip behaviour
    is certified separately.
    """
    item = _semantic_item(
        semantic_user,
        "Delete me",
        description="Important factual description",
    )

    before = _factual_meaning(item)

    item.is_deleted = True
    item.save(update_fields=["is_deleted"])

    assert _factual_meaning(item) == before

    item.refresh_from_db()
    assert item.is_deleted is True


@pytest.mark.django_db
def test_delete_restore_round_trip_preserves_factual_meaning(
    semantic_user,
):
    item = _semantic_item(
        semantic_user,
        "Round trip",
        description="Must survive",
        duration_category=DurationCategory.UNDER_4_HOURS,
        start_date=date(2026, 9, 25),
        due_date=date(2026, 10, 8),
    )

    original = _factual_meaning(item)

    for _ in range(25):
        item.is_deleted = True
        item.save(update_fields=["is_deleted"])

        item.is_deleted = False
        item.save(update_fields=["is_deleted"])

    assert _factual_meaning(item) == original
