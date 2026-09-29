from datetime import date
from decimal import Decimal

import pytest

from arc_scheduler import (
    SchedulerEngineV1,
    SchedulerInputV1,
    SchedulerTaskInputV1,
)


TODAY = date(2026, 9, 29)


def task(
    item_id,
    *,
    anchor_order=None,
):
    return SchedulerTaskInputV1(
        item_id=item_id,
        duration_category="UNDER_1_HOUR",
        priority_position=item_id,
        release_date=None,
        due_date=TODAY,
        anchor_date=TODAY,
        percent_completed=Decimal("0"),
        remaining_fraction=Decimal("1"),
        anchor_order=anchor_order,
    )


def request(tasks):
    return SchedulerInputV1(
        today=TODAY,
        flavour="lock-in",
        tasks=tuple(tasks),
        dependencies=(),
        capacity_by_duration={
            "UNDER_1_HOUR": 10,
        },
        overload_dates=frozenset(),
    )


def test_anchor_order_requires_anchor_date():
    with pytest.raises(
        ValueError,
        match="requires anchor_date",
    ):
        SchedulerTaskInputV1(
            item_id=1,
            duration_category="UNDER_1_HOUR",
            priority_position=1,
            release_date=None,
            due_date=TODAY,
            anchor_date=None,
            percent_completed=0,
            remaining_fraction=1,
            anchor_order=1,
        )


def test_anchor_order_must_be_positive():
    with pytest.raises(
        ValueError,
        match="must be positive",
    ):
        task(
            1,
            anchor_order=0,
        )


def test_duplicate_anchored_slots_are_rejected():
    with pytest.raises(
        ValueError,
        match="Duplicate anchored execution slot",
    ):
        request(
            [
                task(
                    1,
                    anchor_order=2,
                ),
                task(
                    2,
                    anchor_order=2,
                ),
            ]
        )


def test_public_engine_respects_anchored_within_day_position():
    result = SchedulerEngineV1(
        max_iterations=0,
        max_evaluations=0,
    ).run(
        request(
            [
                task(1),
                task(2),
                task(
                    3,
                    anchor_order=2,
                ),
            ]
        )
    )

    rows = [
        row
        for row in result.allocations
        if row.scheduled_date
        == TODAY
    ]

    assert [
        row.execution_rank
        for row in rows
    ] == [
        1,
        2,
        3,
    ]

    anchored = next(
        row
        for row in rows
        if row.item_id == 3
    )

    assert anchored.execution_rank == 2


def test_inputs_without_anchor_order_keep_historical_item_order():
    result = SchedulerEngineV1(
        max_iterations=0,
        max_evaluations=0,
    ).run(
        request(
            [
                task(3),
                task(1),
                task(2),
            ]
        )
    )

    assert [
        row.item_id
        for row in result.allocations
        if row.scheduled_date
        == TODAY
    ] == [
        1,
        2,
        3,
    ]
