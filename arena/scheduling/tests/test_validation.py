from datetime import date, timedelta
from decimal import Decimal

from arena.scheduling.domain import (
    Allocation,
    DependencyEdge,
    ScheduleItem,
    SchedulePlan,
    ScheduleProblem,
)
from arena.scheduling.validation import validate_plan


TODAY = date(2026, 1, 15)


def make_item(
    item_id,
    *,
    duration="UNDER_1_HOUR",
    remaining="1",
):
    return ScheduleItem(
        item_id=item_id,
        duration_category=duration,
        priority_position=None,
        release_date=None,
        due_date=None,
        anchor_date=None,
        percent_completed=(
            Decimal("100")
            - Decimal(remaining) * Decimal("100")
        ),
        remaining_fraction=Decimal(remaining),
    )


def alloc(item_id, offset, percentage, rank):
    return Allocation(
        item_id=item_id,
        scheduled_date=TODAY + timedelta(days=offset),
        percentage=Decimal(str(percentage)),
        execution_rank=rank,
    )


def problem(items, edges=()):
    return ScheduleProblem(
        today=TODAY,
        items=tuple(items),
        dependencies=tuple(
            DependencyEdge(a, b)
            for a, b in edges
        ),
        capacity_by_duration={
            "UNDER_20_MINUTES": 5,
            "UNDER_1_HOUR": 4,
            "UNDER_4_HOURS": 3,
            "UNDER_8_HOURS": 3,
            "UNDER_16_HOURS": 3,
            "OVER_16_HOURS": 3,
        },
    )


def codes(result):
    return {
        row.code
        for row in result.violations
    }


def test_simple_dependency_valid_when_prerequisite_finishes_first():
    p = problem(
        [
            make_item(1),
            make_item(2),
        ],
        [(1, 2)],
    )

    plan = SchedulePlan(
        allocations=(
            alloc(1, 0, 100, 1),
            alloc(2, 1, 100, 1),
        )
    )

    assert validate_plan(p, plan).is_valid


def test_dependency_rejects_dependent_before_prerequisite():
    p = problem(
        [
            make_item(1),
            make_item(2),
        ],
        [(1, 2)],
    )

    plan = SchedulePlan(
        allocations=(
            alloc(2, 0, 100, 1),
            alloc(1, 1, 100, 1),
        )
    )

    assert "dependency_precedence" in codes(
        validate_plan(p, plan)
    )


def test_chain_enforces_transitive_order_without_explicit_a_to_c():
    p = problem(
        [
            make_item(1),
            make_item(2),
            make_item(3),
        ],
        [
            (1, 2),
            (2, 3),
        ],
    )

    valid = SchedulePlan(
        allocations=(
            alloc(1, 0, 100, 1),
            alloc(2, 1, 100, 1),
            alloc(3, 2, 100, 1),
        )
    )

    assert validate_plan(p, valid).is_valid

    invalid = SchedulePlan(
        allocations=(
            alloc(1, 0, 100, 1),
            alloc(3, 1, 100, 1),
            alloc(2, 2, 100, 1),
        )
    )

    assert "dependency_precedence" in codes(
        validate_plan(p, invalid)
    )


def test_split_prerequisite_must_finish_before_dependent_begins():
    p = problem(
        [
            make_item(
                1,
                duration="UNDER_16_HOURS",
            ),
            make_item(2),
        ],
        [(1, 2)],
    )

    invalid = SchedulePlan(
        allocations=(
            alloc(1, 0, 40, 1),
            alloc(2, 1, 100, 1),
            alloc(1, 2, 60, 1),
        )
    )

    assert "dependency_precedence" in codes(
        validate_plan(p, invalid)
    )

    valid = SchedulePlan(
        allocations=(
            alloc(1, 0, 40, 1),
            alloc(1, 1, 60, 1),
            alloc(2, 2, 100, 1),
        )
    )

    assert validate_plan(p, valid).is_valid


def test_fan_in_requires_every_prerequisite_to_finish():
    p = problem(
        [
            make_item(1),
            make_item(2),
            make_item(3),
            make_item(4),
        ],
        [
            (1, 4),
            (2, 4),
            (3, 4),
        ],
    )

    plan = SchedulePlan(
        allocations=(
            alloc(1, 0, 100, 1),
            alloc(2, 0, 100, 2),
            alloc(4, 1, 100, 1),
            alloc(3, 2, 100, 1),
        )
    )

    result = validate_plan(p, plan)

    assert any(
        row.code == "dependency_precedence"
        and row.item_id == 4
        and row.related_item_id == 3
        for row in result.violations
    )


def test_fan_out_allows_all_dependents_after_shared_prerequisite():
    p = problem(
        [
            make_item(1),
            make_item(2),
            make_item(3),
            make_item(4),
        ],
        [
            (1, 2),
            (1, 3),
            (1, 4),
        ],
    )

    plan = SchedulePlan(
        allocations=(
            alloc(1, 0, 100, 1),
            alloc(2, 1, 100, 1),
            alloc(3, 1, 100, 2),
            alloc(4, 1, 100, 3),
        )
    )

    assert validate_plan(p, plan).is_valid
