"""Deterministic state-machine torture test for ARC scheduling infrastructure."""

from __future__ import annotations

import os
import random
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

from arena.evaluation.invariants import validate_schedule


TODAY = date(2026, 9, 20)

SEEDS = 100
STEPS_PER_SEED = 100
INITIAL_ITEMS = 20


def reset(seed):
    PlanningItem.objects.all().delete()
    User.objects.filter(email="torture@arena.test").delete()

    user = User.objects.create_user(
        email="torture@arena.test",
        password="arena-local-only",
    )

    rng = random.Random(seed)

    roots = []

    for i in range(4):
        roots.append(
            PlanningItem.objects.create(
                user=user,
                title=f"Root {i}",
                item_type="ASSIGNMENT",
                due_date=TODAY + timedelta(days=rng.randint(10, 40)),
            )
        )

    existing = list(roots)

    for i in range(INITIAL_ITEMS - len(roots)):
        parent = rng.choice(existing)

        child = PlanningItem.objects.create(
            user=user,
            title=f"Initial {i}",
            item_type="TASK",
            parent=parent,
            due_date=TODAY + timedelta(days=rng.randint(2, 40)),
        )

        existing.append(child)

    return user, rng


def active(user):
    return list(
        PlanningItem.objects.filter(
            user=user,
            is_deleted=False,
        )
    )


def reschedule_and_validate(user):
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

    if violations:
        raise AssertionError(
            "; ".join(
                f"{v.kind}:{v.item_id}:{v.detail}"
                for v in violations
            )
        )


def op_complete(user, rng):
    candidates = [
        x for x in active(user)
        if not x.is_completed
    ]
    if not candidates:
        return "complete:no-op"

    item = rng.choice(candidates)
    hierarchy.complete_subtree(item)
    return f"complete:{item.id}"


def op_reopen(user, rng):
    candidates = [
        x for x in active(user)
        if x.is_completed
    ]
    if not candidates:
        return "reopen:no-op"

    item = rng.choice(candidates)
    hierarchy.reopen(item)
    return f"reopen:{item.id}"


def op_add_child(user, rng):
    candidates = [
        x for x in active(user)
        if not x.is_completed and x.manual_requested_date is None
    ]
    if not candidates:
        return "add_child:no-op"

    parent = rng.choice(candidates)

    child = PlanningItem.objects.create(
        user=user,
        title=f"Generated child {rng.randrange(1_000_000)}",
        item_type="TASK",
        parent=parent,
        due_date=TODAY + timedelta(days=rng.randint(1, 45)),
    )

    return f"add_child:{parent.id}->{child.id}"


def op_delete(user, rng):
    candidates = [
        x for x in active(user)
        if x.manual_requested_date is None
    ]
    if not candidates:
        return "delete:no-op"

    item = rng.choice(candidates)
    item.is_deleted = True
    item.save(update_fields=["is_deleted"])

    return f"delete:{item.id}"


def op_restore(user, rng):
    candidates = list(
        PlanningItem.objects.filter(
            user=user,
            is_deleted=True,
            manual_requested_date__isnull=True,
        )
    )

    if not candidates:
        return "restore:no-op"

    item = rng.choice(candidates)
    item.is_deleted = False
    item.save(update_fields=["is_deleted"])

    return f"restore:{item.id}"


def op_reparent(user, rng):
    candidates = [
        x for x in active(user)
        if not x.is_completed and x.manual_requested_date is None
    ]

    if len(candidates) < 2:
        return "reparent:no-op"

    rng.shuffle(candidates)

    for item in candidates:
        possible = [x for x in candidates if x.pk != item.pk]
        rng.shuffle(possible)

        for parent in possible:
            try:
                hierarchy.set_parent(item, parent)
                return f"reparent:{item.id}->{parent.id}"
            except Exception:
                continue

    return "reparent:no-op"


def op_change_release(user, rng):
    candidates = [
        x for x in active(user)
        if not x.is_completed and x.manual_requested_date is None
    ]
    if not candidates:
        return "release:no-op"

    item = rng.choice(candidates)

    latest = max(0, (item.due_date - TODAY).days if item.due_date else 30)
    offset = rng.randint(0, latest)

    item.start_date = TODAY + timedelta(days=offset)
    item.save(update_fields=["start_date"])

    return f"release:{item.id}:{item.start_date}"


def op_change_due(user, rng):
    candidates = [
        x for x in active(user)
        if not x.is_completed and x.manual_requested_date is None
    ]
    if not candidates:
        return "due:no-op"

    item = rng.choice(candidates)

    earliest = (
        max(TODAY, item.start_date)
        if item.start_date
        else TODAY
    )

    item.due_date = earliest + timedelta(days=rng.randint(0, 45))
    item.save(update_fields=["due_date"])

    return f"due:{item.id}:{item.due_date}"


OPERATIONS = [
    op_complete,
    op_reopen,
    op_add_child,
    op_delete,
    op_restore,
    op_reparent,
    op_change_release,
    op_change_due,
]


def run_seed(seed):
    user, rng = reset(seed)
    history = []

    reschedule_and_validate(user)

    for step in range(STEPS_PER_SEED):
        op = rng.choice(OPERATIONS)

        try:
            description = op(user, rng)
            history.append(description)

            reschedule_and_validate(user)

            # Idempotence check after every mutation.
            before = dict(
                PlanningItem.objects.filter(user=user)
                .values_list("id", "scheduled_date")
            )

            reschedule_and_validate(user)

            after = dict(
                PlanningItem.objects.filter(user=user)
                .values_list("id", "scheduled_date")
            )

            assert before == after, "reschedule is not idempotent"

        except Exception as exc:
            print()
            print("=" * 78)
            print("STATE-MACHINE FAILURE")
            print("=" * 78)
            print(f"seed:      {seed}")
            print(f"step:      {step}")
            print(f"operation: {history[-1] if history else '<initial>'}")
            print(f"error:     {type(exc).__name__}: {exc}")
            print()
            print("REPLAY HISTORY")
            print("-" * 78)

            for i, event in enumerate(history):
                print(f"{i:03d}  {event}")

            raise


def main():
    print("=" * 78)
    print("ARC SEEDED STATE-MACHINE TORTURE")
    print(
        f"{SEEDS} seeds × {STEPS_PER_SEED} transitions "
        f"= {SEEDS * STEPS_PER_SEED:,} states"
    )
    print("=" * 78)

    for seed in range(SEEDS):
        run_seed(seed)

        if (seed + 1) % 10 == 0:
            print(f"PASS  seeds 0–{seed}")

    print()
    print("=" * 78)
    print(
        f"PASS — {SEEDS * STEPS_PER_SEED:,} "
        "state transitions survived"
    )
    print("=" * 78)


if __name__ == "__main__":
    main()
