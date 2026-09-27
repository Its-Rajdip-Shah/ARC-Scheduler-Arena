from datetime import date
from decimal import Decimal

import pytest

from arena.scheduling.domain import (
    DependencyEdge,
    ScheduleItem,
    ScheduleProblem,
)


TODAY = date(2026, 1, 15)


def item(item_id):
    return ScheduleItem(
        item_id=item_id,
        duration_category="UNDER_1_HOUR",
        priority_position=None,
        release_date=None,
        due_date=None,
        anchor_date=None,
        percent_completed=Decimal("0"),
        remaining_fraction=Decimal("1"),
    )


def problem(ids, edges):
    return ScheduleProblem(
        today=TODAY,
        items=tuple(item(pk) for pk in ids),
        dependencies=tuple(
            DependencyEdge(a, b)
            for a, b in edges
        ),
        capacity_by_duration={
            "UNDER_1_HOUR": 4,
        },
    )


def test_dependency_fan_out():
    p = problem(
        [1, 2, 3, 4],
        [
            (1, 2),
            (1, 3),
            (1, 4),
        ],
    )

    assert p.direct_dependents(1) == frozenset({
        2,
        3,
        4,
    })

    assert p.direct_prerequisites(2) == frozenset({1})
    assert p.direct_prerequisites(3) == frozenset({1})
    assert p.direct_prerequisites(4) == frozenset({1})


def test_dependency_fan_in():
    p = problem(
        [1, 2, 3, 4],
        [
            (1, 4),
            (2, 4),
            (3, 4),
        ],
    )

    assert p.direct_prerequisites(4) == frozenset({
        1,
        2,
        3,
    })


def test_chain_implies_transitive_dependency_without_invented_edge():
    p = problem(
        [1, 2, 3],
        [
            (1, 2),
            (2, 3),
        ],
    )

    assert p.dependencies == (
        DependencyEdge(1, 2),
        DependencyEdge(2, 3),
    )

    assert p.direct_prerequisites(3) == frozenset({2})

    assert p.transitive_prerequisites(3) == frozenset({
        1,
        2,
    })

    assert p.transitive_dependents(1) == frozenset({
        2,
        3,
    })

    assert p.topological_order() == (1, 2, 3)


def test_cycle_is_rejected():
    with pytest.raises(
        ValueError,
        match="cycle",
    ):
        problem(
            [1, 2, 3],
            [
                (1, 2),
                (2, 3),
                (3, 1),
            ],
        )


def test_existing_schedule_is_optional_independent_and_immutable():
    from dataclasses import FrozenInstanceError, replace

    original = item(1)
    assert original.existing_scheduled_date is None
    snapshot = replace(original, anchor_date=TODAY,
                       existing_scheduled_date=date(2026, 1, 10))
    assert snapshot.anchor_date == TODAY
    assert snapshot.existing_scheduled_date == date(2026, 1, 10)
    with pytest.raises(FrozenInstanceError):
        snapshot.existing_scheduled_date = None
