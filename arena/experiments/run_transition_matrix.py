"""ARC infrastructure certification: deterministic hierarchy/state transitions."""

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
from planning.models import PlanningItem
from planning.services import hierarchy, scheduling

from arena.evaluation.invariants import execution_frontier, validate_schedule


TODAY = date(2026, 9, 20)


def reset():
    PlanningItem.objects.all().delete()
    User.objects.filter(email="certification@arena.test").delete()

    user = User.objects.create_user(
        email="certification@arena.test",
        password="arena-local-only",
    )

    return user


def make(
    user,
    title,
    *,
    parent=None,
    kind="TASK",
    completed=False,
    deleted=False,
    manual=False,
    scheduled=None,
    release=None,
    due=None,
):
    return PlanningItem.objects.create(
        user=user,
        title=title,
        parent=parent,
        item_type=kind,
        is_completed=completed,
        is_deleted=deleted,
        manual_requested_date=scheduled if manual else None,
        scheduled_date=scheduled,
        start_date=release,
        due_date=due or TODAY + timedelta(days=30),
    )


def run_and_assert(user):
    anchors = dict(
        PlanningItem.objects.filter(
            user=user,
            manual_requested_date__isnull=False,
            is_deleted=False,
        ).values_list("id", "manual_requested_date")
    )

    completed = dict(
        PlanningItem.objects.filter(
            user=user,
            is_completed=True,
            is_deleted=False,
        ).values_list("id", "scheduled_date")
    )

    scheduling.reschedule(user, today=TODAY)

    violations = validate_schedule(
        user,
        benchmark_today=TODAY,
        anchored_before=anchors,
        completed_before=completed,
    )

    assert not violations, violations


def frontier_ids(user):
    return {x.id for x in execution_frontier(user)}


def test_complete_final_child_exposes_parent():
    u = reset()
    p = make(u, "Parent", kind="ASSIGNMENT")
    c = make(u, "Child", parent=p)

    run_and_assert(u)
    assert c.id in frontier_ids(u)
    assert p.id not in frontier_ids(u)

    hierarchy.complete_subtree(c)
    run_and_assert(u)

    p.refresh_from_db()
    assert p.id in frontier_ids(u)
    assert p.scheduled_date is not None


def test_reopen_child_demotes_parent():
    u = reset()
    p = make(u, "Parent", kind="ASSIGNMENT")
    c = make(u, "Child", parent=p, completed=True)

    run_and_assert(u)
    assert p.id in frontier_ids(u)

    hierarchy.reopen(c)
    run_and_assert(u)

    p.refresh_from_db()
    c.refresh_from_db()

    assert p.id not in frontier_ids(u)
    assert p.scheduled_date is None
    assert c.id in frontier_ids(u)


def test_completed_child_of_frontier_reopened():
    """Explicit regression for parent→frontier→parent transition."""
    u = reset()

    root = make(u, "Root", kind="ASSIGNMENT")
    leaf = make(u, "Leaf", parent=root)
    child = make(u, "Previously completed child", parent=leaf, completed=True)

    run_and_assert(u)

    leaf.refresh_from_db()
    assert leaf.id in frontier_ids(u)
    assert leaf.scheduled_date is not None

    hierarchy.reopen(child)
    run_and_assert(u)

    leaf.refresh_from_db()
    child.refresh_from_db()

    assert leaf.id not in frontier_ids(u)
    assert leaf.scheduled_date is None
    assert child.id in frontier_ids(u)
    assert child.scheduled_date is not None


def test_only_final_sibling_completion_exposes_parent():
    u = reset()
    p = make(u, "Parent", kind="ASSIGNMENT")
    a = make(u, "A", parent=p)
    b = make(u, "B", parent=p)

    run_and_assert(u)

    hierarchy.complete_subtree(a)
    run_and_assert(u)
    assert p.id not in frontier_ids(u)

    hierarchy.complete_subtree(b)
    run_and_assert(u)
    assert p.id in frontier_ids(u)


def test_add_child_demotes_frontier_parent():
    u = reset()
    p = make(u, "Parent", kind="ASSIGNMENT")

    run_and_assert(u)
    assert p.id in frontier_ids(u)

    c = make(u, "New child", parent=p)
    run_and_assert(u)

    p.refresh_from_db()

    assert p.id not in frontier_ids(u)
    assert p.scheduled_date is None
    assert c.id in frontier_ids(u)


def test_delete_final_child_exposes_parent():
    u = reset()
    p = make(u, "Parent", kind="ASSIGNMENT")
    c = make(u, "Child", parent=p)

    run_and_assert(u)

    c.is_deleted = True
    c.save(update_fields=["is_deleted"])
    run_and_assert(u)

    assert p.id in frontier_ids(u)


def test_restore_child_demotes_parent():
    u = reset()
    p = make(u, "Parent", kind="ASSIGNMENT")
    c = make(u, "Child", parent=p, deleted=True)

    run_and_assert(u)
    assert p.id in frontier_ids(u)

    c.is_deleted = False
    c.save(update_fields=["is_deleted"])
    run_and_assert(u)

    p.refresh_from_db()

    assert p.id not in frontier_ids(u)
    assert p.scheduled_date is None
    assert c.id in frontier_ids(u)


def test_move_child_recomputes_both_parents():
    u = reset()

    a = make(u, "Parent A", kind="ASSIGNMENT")
    b = make(u, "Parent B", kind="ASSIGNMENT")
    c = make(u, "Child", parent=a)

    run_and_assert(u)

    hierarchy.set_parent(c, b)
    run_and_assert(u)

    a.refresh_from_db()
    b.refresh_from_db()
    c.refresh_from_db()

    assert a.id in frontier_ids(u)
    assert b.id not in frontier_ids(u)
    assert c.id in frontier_ids(u)

    assert a.scheduled_date is not None
    assert b.scheduled_date is None


def test_deep_reopen_propagates_frontier_correctly():
    u = reset()

    a = make(u, "A", kind="ASSIGNMENT")
    b = make(u, "B", parent=a)
    c = make(u, "C", parent=b)
    d = make(u, "D", parent=c, completed=True)

    run_and_assert(u)

    assert c.id in frontier_ids(u)

    hierarchy.reopen(d)
    run_and_assert(u)

    assert d.id in frontier_ids(u)
    assert c.id not in frontier_ids(u)
    assert b.id not in frontier_ids(u)
    assert a.id not in frontier_ids(u)

    hierarchy.complete_subtree(d)
    run_and_assert(u)
    assert c.id in frontier_ids(u)

    hierarchy.complete_subtree(c)
    run_and_assert(u)
    assert b.id in frontier_ids(u)

    hierarchy.complete_subtree(b)
    run_and_assert(u)
    assert a.id in frontier_ids(u)


def test_release_lower_bound():
    u = reset()
    t = make(
        u,
        "Released later",
        release=TODAY + timedelta(days=5),
        due=TODAY + timedelta(days=10),
    )

    run_and_assert(u)
    t.refresh_from_db()

    assert t.scheduled_date >= t.start_date


def test_due_upper_bound():
    u = reset()
    t = make(
        u,
        "Hard deadline",
        due=TODAY + timedelta(days=2),
    )

    run_and_assert(u)
    t.refresh_from_db()

    assert t.scheduled_date <= t.due_date


def test_release_equals_due():
    u = reset()
    exact = TODAY + timedelta(days=4)

    t = make(
        u,
        "One legal day",
        release=exact,
        due=exact,
    )

    run_and_assert(u)
    t.refresh_from_db()

    assert t.scheduled_date == exact


def test_anchor_immutable_under_unrelated_change():
    u = reset()

    anchored = make(
        u,
        "Anchored",
        manual=True,
        scheduled=TODAY + timedelta(days=6),
    )
    other = make(u, "Other")

    run_and_assert(u)

    hierarchy.complete_subtree(other)
    run_and_assert(u)

    anchored.refresh_from_db()
    assert anchored.scheduled_date == TODAY + timedelta(days=6)


def test_unanchor_returns_item_to_scheduler():
    u = reset()

    t = make(
        u,
        "Manual",
        manual=True,
        scheduled=TODAY + timedelta(days=10),
    )

    run_and_assert(u)

    t.manual_requested_date = None
    t.save(update_fields=["manual_requested_date"])

    run_and_assert(u)
    t.refresh_from_db()

    assert t.scheduled_date is not None


def test_completed_work_unchanged():
    u = reset()

    historical = TODAY - timedelta(days=3)
    t = make(
        u,
        "Completed",
        completed=True,
        scheduled=historical,
    )

    run_and_assert(u)
    t.refresh_from_db()

    assert t.scheduled_date == historical


def test_deleted_work_excluded():
    u = reset()

    t = make(u, "Deleted", deleted=True)
    run_and_assert(u)

    t.refresh_from_db()
    assert t.id not in frontier_ids(u)


def test_idempotence():
    u = reset()

    p = make(u, "Project", kind="ASSIGNMENT")
    for i in range(10):
        make(u, f"Task {i}", parent=p, due=TODAY + timedelta(days=5 + i))

    run_and_assert(u)

    before = dict(
        PlanningItem.objects.filter(user=u)
        .values_list("id", "scheduled_date")
    )

    run_and_assert(u)

    after = dict(
        PlanningItem.objects.filter(user=u)
        .values_list("id", "scheduled_date")
    )

    assert before == after


def test_determinism_after_reset():
    def produce():
        u = reset()
        p = make(u, "Project", kind="ASSIGNMENT")

        for i in range(12):
            make(
                u,
                f"Task {i}",
                parent=p,
                due=TODAY + timedelta(days=(i % 5) + 2),
            )

        run_and_assert(u)

        return list(
            PlanningItem.objects.filter(
                user=u,
                is_deleted=False,
                is_completed=False,
            )
            .order_by("title")
            .values_list("title", "scheduled_date")
        )

    first = produce()
    second = produce()

    assert first == second


TESTS = [
    test_complete_final_child_exposes_parent,
    test_reopen_child_demotes_parent,
    test_completed_child_of_frontier_reopened,
    test_only_final_sibling_completion_exposes_parent,
    test_add_child_demotes_frontier_parent,
    test_delete_final_child_exposes_parent,
    test_restore_child_demotes_parent,
    test_move_child_recomputes_both_parents,
    test_deep_reopen_propagates_frontier_correctly,
    test_release_lower_bound,
    test_due_upper_bound,
    test_release_equals_due,
    test_anchor_immutable_under_unrelated_change,
    test_unanchor_returns_item_to_scheduler,
    test_completed_work_unchanged,
    test_deleted_work_excluded,
    test_idempotence,
    test_determinism_after_reset,
]


def main():
    print("=" * 78)
    print("ARC INFRASTRUCTURE — TRANSITION MATRIX")
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
    print(
        f"RESULT: {len(TESTS) - len(failures)}/{len(TESTS)} "
        "transition tests passed"
    )
    print("=" * 78)

    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
