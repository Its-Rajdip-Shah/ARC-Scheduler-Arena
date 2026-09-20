"""Exercise ARC through realistic hierarchy/state transitions."""

from __future__ import annotations

import os
import sys
from datetime import date, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"

sys.path.insert(0, str(BACKEND))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "arc_backend.settings")

import django

django.setup()

from accounts.models import User
from planning.models import PlanningItem, SchedulingPreference
from planning.services import scheduling

from arena.evaluation.invariants import execution_frontier
from arena.evaluation.lifecycle import (
    schedule_map,
    snapshot,
    validate_transition,
)


TODAY = date(2026, 9, 20)


def reset():
    PlanningItem.objects.all().delete()
    SchedulingPreference.objects.all().delete()
    User.objects.filter(email="lifecycle@arena.test").delete()

    user = User.objects.create_user(
        email="lifecycle@arena.test",
        password="arena-local-only",
    )

    SchedulingPreference.objects.create(
        user=user,
        under_20=5,
        minutes_20_to_60=4,
        over_60=3,
    )

    return user


def item(
    user,
    title,
    *,
    kind="TASK",
    parent=None,
    due_days=14,
    completed=False,
    manual=False,
    scheduled=None,
):
    return PlanningItem.objects.create(
        user=user,
        title=title,
        item_type=kind,
        parent=parent,
        due_date=TODAY + timedelta(days=due_days),
        is_completed=completed,
        schedule_is_manual=manual,
        scheduled_date=scheduled,
    )


def reschedule_and_validate(user):
    anchored_before = {
        x.id: x.scheduled_date
        for x in PlanningItem.objects.filter(
            user=user,
            schedule_is_manual=True,
            is_deleted=False,
        )
    }

    completed_before = {
        x.id: x.scheduled_date
        for x in PlanningItem.objects.filter(
            user=user,
            is_completed=True,
            is_deleted=False,
        )
    }

    scheduling.reschedule(user, today=TODAY)

    return validate_transition(
        user,
        today=TODAY,
        anchored_before=anchored_before,
        completed_before=completed_before,
    )


def assert_clean(user):
    violations = reschedule_and_validate(user)
    assert not violations, violations


def test_progressive_frontier_exposure():
    user = reset()

    assignment = item(user, "Assignment", kind="ASSIGNMENT")
    section = item(user, "Implementation", parent=assignment)
    leaf_a = item(user, "Build backend", parent=section)
    leaf_b = item(user, "Write tests", parent=section)

    assert_clean(user)

    frontier = {x.id for x in execution_frontier(user)}
    assert leaf_a.id in frontier
    assert leaf_b.id in frontier
    assert section.id not in frontier
    assert assignment.id not in frontier

    leaf_a.is_completed = True
    leaf_a.save(update_fields=["is_completed"])
    assert_clean(user)

    frontier = {x.id for x in execution_frontier(user)}
    assert leaf_b.id in frontier
    assert section.id not in frontier

    leaf_b.is_completed = True
    leaf_b.save(update_fields=["is_completed"])
    assert_clean(user)

    section.refresh_from_db()
    frontier = {x.id for x in execution_frontier(user)}

    assert section.id in frontier
    assert section.scheduled_date is not None
    assert assignment.id not in frontier

    section.is_completed = True
    section.save(update_fields=["is_completed"])
    assert_clean(user)

    assignment.refresh_from_db()
    frontier = {x.id for x in execution_frontier(user)}

    assert assignment.id in frontier
    assert assignment.scheduled_date is not None


def test_reopening_child_demotes_parent():
    user = reset()

    parent = item(user, "Report", kind="ASSIGNMENT")
    child = item(user, "Draft", parent=parent, completed=True)

    assert_clean(user)

    parent.refresh_from_db()
    assert parent.scheduled_date is not None

    child.is_completed = False
    child.save(update_fields=["is_completed"])

    assert_clean(user)

    parent.refresh_from_db()
    child.refresh_from_db()

    frontier = {x.id for x in execution_frontier(user)}

    assert parent.id not in frontier
    assert parent.scheduled_date is None
    assert child.id in frontier
    assert child.scheduled_date is not None


def test_adding_child_demotes_scheduled_parent():
    user = reset()

    parent = item(user, "Submit project", kind="ASSIGNMENT")

    assert_clean(user)
    parent.refresh_from_db()
    assert parent.scheduled_date is not None

    child = item(user, "Final review", parent=parent)

    assert_clean(user)

    parent.refresh_from_db()
    child.refresh_from_db()

    assert parent.scheduled_date is None
    assert child.scheduled_date is not None


def test_completing_one_leaf_does_not_expose_parent_early():
    user = reset()

    parent = item(user, "Assignment", kind="ASSIGNMENT")
    a = item(user, "Part A", parent=parent)
    b = item(user, "Part B", parent=parent)

    assert_clean(user)

    a.is_completed = True
    a.save(update_fields=["is_completed"])

    assert_clean(user)

    parent.refresh_from_db()
    b.refresh_from_db()

    assert parent.scheduled_date is None
    assert b.scheduled_date is not None


def test_anchor_survives_other_completions():
    user = reset()

    parent = item(user, "Coursework", kind="ASSIGNMENT")

    anchored = item(
        user,
        "Presentation",
        parent=parent,
        manual=True,
        scheduled=TODAY + timedelta(days=5),
    )

    other = item(user, "Research", parent=parent)

    assert_clean(user)

    other.is_completed = True
    other.save(update_fields=["is_completed"])

    assert_clean(user)

    anchored.refresh_from_db()
    assert anchored.scheduled_date == TODAY + timedelta(days=5)


def test_reschedule_is_idempotent():
    user = reset()

    parent = item(user, "Project", kind="ASSIGNMENT")

    for n in range(8):
        item(
            user,
            f"Task {n + 1}",
            parent=parent,
            due_days=5 + n,
        )

    assert_clean(user)
    first = snapshot(user)

    assert_clean(user)
    second = snapshot(user)

    assert first == second


def test_repeated_completion_sequence_remains_valid():
    user = reset()

    root = item(user, "Large Assignment", kind="ASSIGNMENT")

    phase_a = item(user, "Research Phase", parent=root)
    phase_b = item(user, "Build Phase", parent=root)
    phase_c = item(user, "Report Phase", parent=root)

    leaves = [
        item(user, "Find sources", parent=phase_a),
        item(user, "Read papers", parent=phase_a),
        item(user, "Implement core", parent=phase_b),
        item(user, "Integration tests", parent=phase_b),
        item(user, "Draft report", parent=phase_c),
        item(user, "Proofread", parent=phase_c),
    ]

    assert_clean(user)

    for leaf in leaves:
        leaf.is_completed = True
        leaf.save(update_fields=["is_completed"])
        assert_clean(user)

    for phase in (phase_a, phase_b, phase_c):
        phase.refresh_from_db()

    assert all(
        phase.id in {x.id for x in execution_frontier(user)}
        for phase in (phase_a, phase_b, phase_c)
    )


TESTS = [
    test_progressive_frontier_exposure,
    test_reopening_child_demotes_parent,
    test_adding_child_demotes_scheduled_parent,
    test_completing_one_leaf_does_not_expose_parent_early,
    test_anchor_survives_other_completions,
    test_reschedule_is_idempotent,
    test_repeated_completion_sequence_remains_valid,
]


def main():
    print("=" * 78)
    print("A0 DYNAMIC LIFECYCLE GAUNTLET")
    print("=" * 78)

    failures = []

    for test in TESTS:
        try:
            test()
            print(f"PASS  {test.__name__}")
        except Exception as exc:
            failures.append((test.__name__, exc))
            print(f"FAIL  {test.__name__}")
            print(f"      {type(exc).__name__}: {exc}")

    print()
    print("=" * 78)
    print(f"RESULT: {len(TESTS) - len(failures)}/{len(TESTS)} lifecycle tests passed")
    print("=" * 78)

    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
