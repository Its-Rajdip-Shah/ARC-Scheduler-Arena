"""Materialize a validated Arena WorkloadBlueprint into canonical ARC state.

This module is intentionally NOT a domain-command workflow. The generator has
already constructed and validated a complete canonical workload state.

Materialization translates that state into ARC persistence atomically without
invoking scheduling, lifecycle reconciliation, focus reconciliation, history,
or any disposable scheduler-owned representation.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from planning.models import (
    ItemType,
    PlanningDependency,
    PlanningItem,
    ProgressSegment,
    SchedulerAllocation,
    SPLITTABLE_DURATION_CATEGORIES,
)

from arena.generation.blueprint import WorkloadBlueprint


ARENA_EMAIL = "arena-generator@local.test"

_SPLITTABLE = {
    value.value if hasattr(value, "value") else str(value)
    for value in SPLITTABLE_DURATION_CATEGORIES
}


@dataclass(frozen=True, slots=True)
class MaterializedWorkload:
    """References to one completely materialized generated workload."""

    user: object
    by_key: dict[str, PlanningItem]


def _validate_blueprint(blueprint: WorkloadBlueprint) -> None:
    keys = [item.key for item in blueprint.items]

    if len(keys) != len(set(keys)):
        raise ValueError("Blueprint item keys must be unique.")

    key_set = set(keys)
    by_key = {item.key: item for item in blueprint.items}

    parent_keys = {
        item.parent_key
        for item in blueprint.items
        if item.parent_key is not None
    }

    for item in blueprint.items:
        if item.parent_key is not None and item.parent_key not in key_set:
            raise ValueError(
                f"Unknown parent {item.parent_key!r} for {item.key!r}."
            )

        is_frontier = item.key not in parent_keys

        if item.item_type not in {
            ItemType.GOAL,
            ItemType.TASK,
            ItemType.ASSIGNMENT,
        }:
            raise ValueError(
                f"Unsupported blueprint item type: {item.item_type!r}"
            )

        if (
            not is_frontier
            and item.priority_position is not None
        ):
            raise ValueError(
                "Hierarchy parents cannot carry canonical priority positions: "
                f"{item.key!r}"
            )

        if item.is_completed and item.percent_completed != 100:
            raise ValueError(
                f"Completed item {item.key!r} must have 100% progress."
            )

        if (
            item.duration_category not in _SPLITTABLE
            and not item.is_completed
            and item.percent_completed != 0
        ):
            raise ValueError(
                f"Atomic unfinished item {item.key!r} has partial progress."
            )

    seen_edges = set()

    for edge in blueprint.dependencies:
        pair = (edge.prerequisite_key, edge.dependent_key)

        if pair in seen_edges:
            raise ValueError(f"Duplicate dependency edge: {pair!r}")
        seen_edges.add(pair)

        if edge.prerequisite_key not in key_set:
            raise ValueError(
                f"Unknown prerequisite: {edge.prerequisite_key!r}"
            )

        if edge.dependent_key not in key_set:
            raise ValueError(
                f"Unknown dependent: {edge.dependent_key!r}"
            )

        if edge.prerequisite_key == edge.dependent_key:
            raise ValueError("Blueprint dependency cannot be a self-edge.")

        prerequisite = by_key[edge.prerequisite_key]
        dependent = by_key[edge.dependent_key]

        if dependent.is_completed and not prerequisite.is_completed:
            raise ValueError(
                "Completed dependent cannot have unfinished prerequisite."
            )

    positions = sorted(
        item.priority_position
        for item in blueprint.items
        if item.priority_position is not None
    )

    if positions != list(range(1, len(positions) + 1)):
        raise ValueError(
            "Blueprint priority positions must be unique and dense."
        )


@transaction.atomic
def materialize_blueprint(
    blueprint: WorkloadBlueprint,
    *,
    email: str = ARENA_EMAIL,
) -> MaterializedWorkload:
    """Replace disposable Arena state with exactly one generated workload."""

    _validate_blueprint(blueprint)

    User = get_user_model()

    # Arena state is disposable, just like the legacy characterization
    # importer. Delete the previous generated benchmark user/state only.
    existing = User.objects.filter(email=email).first()
    if existing is not None:
        existing.delete()

    user = User.objects.create_user(
        email=email,
        password="arena-generator-local-only",
    )

    parent_keys = {
        item.parent_key
        for item in blueprint.items
        if item.parent_key is not None
    }

    by_key: dict[str, PlanningItem] = {}
    remaining = list(blueprint.items)

    # Hierarchy insertion is topological with respect to parent relationships.
    # sibling_order follows deterministic blueprint order.
    sibling_counts: dict[str | None, int] = {}

    while remaining:
        progressed = False

        for item in remaining[:]:
            if (
                item.parent_key is not None
                and item.parent_key not in by_key
            ):
                continue

            sibling_counts[item.parent_key] = (
                sibling_counts.get(item.parent_key, 0) + 1
            )

            row = PlanningItem.objects.create(
                user=user,
                parent=by_key.get(item.parent_key),
                item_type=item.item_type,
                title=item.key,
                sibling_order=sibling_counts[item.parent_key],
                duration_category=item.duration_category,
                start_date=item.start_date,
                due_date=item.due_date,
                manual_requested_date=item.manual_requested_date,
                expired_manual_requested_date=(
                    item.expired_manual_requested_date
                ),
                priority_position=item.priority_position,
                percent_completed=Decimal(str(item.percent_completed)),
                is_completed=item.is_completed,

                # Scheduler-owned state must start empty.
                scheduled_date=None,
                execution_rank=None,
            )

            by_key[item.key] = row
            remaining.remove(item)
            progressed = True

        if not progressed:
            unresolved = [
                (item.key, item.parent_key)
                for item in remaining
            ]
            raise ValueError(
                "Blueprint hierarchy is cyclic or unresolved: "
                f"{unresolved!r}"
            )

    # The blueprint has already been DAG/canonicality validated. Direct
    # persistence avoids dependency.add(), whose lifecycle.finish() boundary
    # intentionally invokes scheduling.
    PlanningDependency.objects.bulk_create(
        [
            PlanningDependency(
                prerequisite=by_key[edge.prerequisite_key],
                dependent=by_key[edge.dependent_key],
            )
            for edge in blueprint.dependencies
        ]
    )

    # Represent generated splittable progress as durable confirmed history.
    # This makes percent_completed and ProgressSegment agree canonically.
    progress_rows = []

    for item in blueprint.items:
        if (
            item.duration_category in _SPLITTABLE
            and item.percent_completed > 0
        ):
            progress_rows.append(
                ProgressSegment(
                    item=by_key[item.key],
                    percentage=Decimal(str(item.percent_completed)),
                    scheduled_date=None,
                    is_completed=True,
                    completed_at=timezone.now(),
                )
            )

    ProgressSegment.objects.bulk_create(progress_rows)

    # Materialization must never manufacture disposable scheduling state.
    if SchedulerAllocation.objects.filter(item__user=user).exists():
        raise AssertionError(
            "Materialization unexpectedly created SchedulerAllocation rows."
        )

    # Validate canonical graph semantics without lifecycle.finish(), because
    # finish() intentionally crosses into scheduler reconciliation.
    from planning.services.lifecycle import validate_graph

    validate_graph(user)

    return MaterializedWorkload(
        user=user,
        by_key=by_key,
    )
