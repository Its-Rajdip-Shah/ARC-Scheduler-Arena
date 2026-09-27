"""Deterministic realistic ARC-shaped workload for C10 human review.

This is deliberately synthetic rather than user-personal data.

The fixture is expressed as canonical ARC workload state through the existing
WorkloadBlueprint -> materialize_blueprint -> problem_from_user path.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from planning.models import (
    DurationCategory,
    ItemType,
)

from arena.generation.blueprint import (
    BlueprintDependency,
    BlueprintItem,
    WorkloadBlueprint,
)


C10_TODAY = date(2026, 9, 28)
C10_FIXTURE_ID = "c10-realistic-semester-v1"
C10_FIXTURE_SEED = 10001


@dataclass(frozen=True, slots=True)
class C10Fixture:
    fixture_id: str
    today: date
    blueprint: WorkloadBlueprint
    display_names: dict[str, str]
    groups: dict[str, str]
    review_notes: tuple[str, ...]


def _goal(
    key: str,
) -> BlueprintItem:
    return BlueprintItem(
        key=key,
        parent_key=None,
        depth=0,
        item_type=ItemType.GOAL,
        duration_category=
            DurationCategory.UNDER_1_HOUR,
    )


def _item(
    key: str,
    parent: str,
    duration: str,
    *,
    item_type: str = ItemType.TASK,
    priority: int | None = None,
    start: date | None = None,
    due: date | None = None,
    anchor: date | None = None,
    percent_completed: int = 0,
) -> BlueprintItem:
    return BlueprintItem(
        key=key,
        parent_key=parent,
        depth=1,
        item_type=item_type,
        duration_category=duration,
        priority_position=priority,
        start_date=start,
        due_date=due,
        manual_requested_date=anchor,
        percent_completed=percent_completed,
        is_completed=False,
    )


def build_realistic_semester_fixture() -> C10Fixture:
    """Return the frozen C10 synthetic university-semester workload."""

    goals = (
        _goal("soft2412"),
        _goal("elec3609"),
        _goal("math"),
        _goal("personal"),
    )

    items = (
        # SOFT2412: clustered deadlines + dependency chain + long assessment.
        _item(
            "soft2412_tutorial8",
            "soft2412",
            DurationCategory.UNDER_4_HOURS,
            priority=4,
            due=date(2026, 9, 30),
        ),
        _item(
            "soft2412_a2_backend",
            "soft2412",
            DurationCategory.UNDER_8_HOURS,
            priority=2,
            start=date(2026, 9, 28),
            due=date(2026, 10, 5),
            percent_completed=25,
        ),
        _item(
            "soft2412_a2_tests",
            "soft2412",
            DurationCategory.UNDER_4_HOURS,
            priority=5,
            start=date(2026, 9, 30),
            due=date(2026, 10, 7),
        ),
        _item(
            "soft2412_a2_report",
            "soft2412",
            DurationCategory.UNDER_16_HOURS,
            item_type=ItemType.ASSIGNMENT,
            priority=1,
            start=date(2026, 10, 1),
            due=date(2026, 10, 9),
        ),
        _item(
            "soft2412_peer_review",
            "soft2412",
            DurationCategory.UNDER_1_HOUR,
            due=date(2026, 10, 10),
            anchor=date(2026, 10, 8),
        ),

        # ELEC3609 / ARC: mixed medium/long work with explicit sequencing.
        _item(
            "arc_c10_fixture_review",
            "elec3609",
            DurationCategory.UNDER_4_HOURS,
            priority=3,
            due=date(2026, 10, 1),
        ),
        _item(
            "arc_c10_human_review",
            "elec3609",
            DurationCategory.UNDER_8_HOURS,
            start=date(2026, 10, 1),
            due=date(2026, 10, 5),
        ),
        _item(
            "arc_backend_adapter",
            "elec3609",
            DurationCategory.UNDER_8_HOURS,
            start=date(2026, 10, 4),
            due=date(2026, 10, 12),
        ),
        _item(
            "arc_regression_tests",
            "elec3609",
            DurationCategory.UNDER_4_HOURS,
            start=date(2026, 10, 7),
            due=date(2026, 10, 14),
        ),
        _item(
            "arc_demo_prep",
            "elec3609",
            DurationCategory.UNDER_4_HOURS,
            due=date(2026, 10, 18),
            anchor=date(2026, 10, 16),
        ),

        # Maths: recurring study work with an eventual large revision block.
        _item(
            "math_week8_revision",
            "math",
            DurationCategory.UNDER_4_HOURS,
            priority=6,
            due=date(2026, 10, 2),
        ),
        _item(
            "math_problem_set",
            "math",
            DurationCategory.UNDER_8_HOURS,
            priority=7,
            start=date(2026, 9, 30),
            due=date(2026, 10, 7),
        ),
        _item(
            "math_practice_exam",
            "math",
            DurationCategory.UNDER_8_HOURS,
            start=date(2026, 10, 6),
            due=date(2026, 10, 13),
        ),
        _item(
            "math_midsem_revision",
            "math",
            DurationCategory.OVER_16_HOURS,
            start=date(2026, 10, 7),
            due=date(2026, 10, 19),
        ),

        # Personal/admin: short anchored and unanchored work mixed with study.
        _item(
            "groceries",
            "personal",
            DurationCategory.UNDER_1_HOUR,
            anchor=date(2026, 9, 29),
        ),
        _item(
            "laundry",
            "personal",
            DurationCategory.UNDER_1_HOUR,
            due=date(2026, 10, 2),
        ),
        _item(
            "gym_session",
            "personal",
            DurationCategory.UNDER_4_HOURS,
            anchor=date(2026, 9, 30),
        ),
        _item(
            "student_admin_email",
            "personal",
            DurationCategory.UNDER_20_MINUTES,
            priority=8,
            due=date(2026, 9, 30),
        ),
        _item(
            "weekly_planning",
            "personal",
            DurationCategory.UNDER_1_HOUR,
            anchor=date(2026, 10, 4),
        ),
        _item(
            "reading_catchup",
            "personal",
            DurationCategory.UNDER_4_HOURS,
            due=date(2026, 10, 11),
        ),
    )

    dependencies = (
        BlueprintDependency(
            "soft2412_a2_backend",
            "soft2412_a2_tests",
        ),
        BlueprintDependency(
            "soft2412_a2_tests",
            "soft2412_a2_report",
        ),
        BlueprintDependency(
            "arc_c10_fixture_review",
            "arc_c10_human_review",
        ),
        BlueprintDependency(
            "arc_c10_human_review",
            "arc_backend_adapter",
        ),
        BlueprintDependency(
            "arc_backend_adapter",
            "arc_regression_tests",
        ),
        BlueprintDependency(
            "math_week8_revision",
            "math_problem_set",
        ),
        BlueprintDependency(
            "math_problem_set",
            "math_practice_exam",
        ),
        BlueprintDependency(
            "math_practice_exam",
            "math_midsem_revision",
        ),
    )

    blueprint = WorkloadBlueprint(
        seed=C10_FIXTURE_SEED,
        items=goals + items,
        dependencies=dependencies,
    )

    names = {
        "soft2412": "SOFT2412",
        "soft2412_tutorial8": "SOFT2412 Week 8 tutorial",
        "soft2412_a2_backend": "SOFT2412 A2 backend implementation",
        "soft2412_a2_tests": "SOFT2412 A2 testing",
        "soft2412_a2_report": "SOFT2412 A2 report",
        "soft2412_peer_review": "SOFT2412 peer review",
        "elec3609": "ELEC3609 / ARC",
        "arc_c10_fixture_review": "Review C10 realistic fixture",
        "arc_c10_human_review": "C10 human-friendliness review",
        "arc_backend_adapter": "ARC backend scheduler adapter",
        "arc_regression_tests": "ARC regression testing",
        "arc_demo_prep": "ARC demo preparation",
        "math": "Mathematics",
        "math_week8_revision": "Math Week 8 revision",
        "math_problem_set": "Math problem set",
        "math_practice_exam": "Math practice exam",
        "math_midsem_revision": "Math mid-semester revision",
        "personal": "Personal",
        "groceries": "Groceries",
        "laundry": "Laundry",
        "gym_session": "Gym session",
        "student_admin_email": "Student admin email",
        "weekly_planning": "Weekly planning",
        "reading_catchup": "Reading catch-up",
    }

    groups = {
        key: (
            "SOFT2412"
            if key.startswith("soft2412")
            else "ELEC3609"
            if key.startswith("arc_") or key == "elec3609"
            else "Mathematics"
            if key.startswith("math")
            else "Personal"
        )
        for key in names
    }

    notes = (
        "Synthetic ARC-shaped semester workload; contains no private user data.",
        "Contains four hierarchy roots and twenty executable frontier items.",
        "Mixes atomic and splittable durations.",
        "Contains priorities, deadlines, release dates, anchors and dependencies.",
        "Includes one partially completed splittable item.",
        "Designed for qualitative schedule inspection, not algorithm tuning.",
    )

    return C10Fixture(
        fixture_id=C10_FIXTURE_ID,
        today=C10_TODAY,
        blueprint=blueprint,
        display_names=names,
        groups=groups,
        review_notes=notes,
    )


def fixture_manifest(
    fixture: C10Fixture,
) -> dict:
    """JSON-safe human-readable description of the frozen fixture."""

    parent_keys = {
        item.parent_key
        for item in fixture.blueprint.items
        if item.parent_key is not None
    }

    frontier = tuple(
        item
        for item in fixture.blueprint.items
        if item.key not in parent_keys
    )

    return {
        "schema_version": 1,
        "fixture_id": fixture.fixture_id,
        "today": fixture.today.isoformat(),
        "seed": fixture.blueprint.seed,
        "synthetic": True,
        "contains_personal_user_data": False,
        "item_count_total": len(
            fixture.blueprint.items
        ),
        "frontier_item_count": len(frontier),
        "dependency_count": len(
            fixture.blueprint.dependencies
        ),
        "anchored_frontier_count": sum(
            item.manual_requested_date
            is not None
            for item in frontier
        ),
        "deadline_frontier_count": sum(
            item.due_date is not None
            for item in frontier
        ),
        "release_frontier_count": sum(
            item.start_date is not None
            for item in frontier
        ),
        "priority_frontier_count": sum(
            item.priority_position
            is not None
            for item in frontier
        ),
        "partially_completed_frontier_count": sum(
            0 < item.percent_completed < 100
            for item in frontier
        ),
        "review_notes": list(
            fixture.review_notes
        ),
        "items": [
            {
                "key": item.key,
                "display_name":
                    fixture.display_names[item.key],
                "group":
                    fixture.groups[item.key],
                "parent_key": item.parent_key,
                "item_type": str(item.item_type),
                "duration_category":
                    str(item.duration_category),
                "priority_position":
                    item.priority_position,
                "start_date": (
                    None
                    if item.start_date is None
                    else item.start_date.isoformat()
                ),
                "due_date": (
                    None
                    if item.due_date is None
                    else item.due_date.isoformat()
                ),
                "manual_requested_date": (
                    None
                    if item.manual_requested_date is None
                    else item.manual_requested_date.isoformat()
                ),
                "percent_completed":
                    item.percent_completed,
            }
            for item in fixture.blueprint.items
        ],
        "dependencies": [
            {
                "prerequisite_key":
                    edge.prerequisite_key,
                "dependent_key":
                    edge.dependent_key,
            }
            for edge
            in fixture.blueprint.dependencies
        ],
    }
