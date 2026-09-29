from datetime import date
from decimal import Decimal

import pytest

from arc_scheduler import (
    SchedulerEngineV1,
    SchedulerInputV1,
    SchedulerTaskInputV1,
)


TODAY = date(2026, 9, 29)


ALL_CAPACITIES = {
    "UNDER_20_MINUTES": 10,
    "UNDER_1_HOUR": 10,
    "UNDER_4_HOURS": 10,
    "UNDER_8_HOURS": 10,
    "UNDER_16_HOURS": 10,
    "OVER_16_HOURS": 10,
}


def task(
    item_id,
    *,
    duration_category=
        "UNDER_1_HOUR",
    anchor_order=None,
    is_residual=False,
):
    return SchedulerTaskInputV1(
        item_id=item_id,
        duration_category=
            duration_category,
        priority_position=
            item_id,
        release_date=None,
        due_date=TODAY,
        anchor_date=TODAY,
        percent_completed=
            Decimal("0"),
        remaining_fraction=
            Decimal("1"),
        is_residual=
            is_residual,
        anchor_order=
            anchor_order,
    )


def request(tasks):
    return SchedulerInputV1(
        today=TODAY,
        flavour="lock-in",
        tasks=tuple(tasks),
        dependencies=(),
        capacity_by_duration=
            ALL_CAPACITIES,
        overload_dates=
            frozenset(),
    )


def test_anchor_order_requires_anchor_date():
    with pytest.raises(
        ValueError,
        match="requires anchor_date",
    ):
        SchedulerTaskInputV1(
            item_id=1,
            duration_category=
                "UNDER_1_HOUR",
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


def test_duplicate_slot_in_same_focus_bucket_is_rejected():
    with pytest.raises(
        ValueError,
        match=(
            "Duplicate anchored execution slot"
        ),
    ):
        request(
            [
                task(
                    1,
                    duration_category=
                        "UNDER_4_HOURS",
                    anchor_order=1,
                ),
                task(
                    2,
                    duration_category=
                        "OVER_16_HOURS",
                    anchor_order=1,
                ),
            ]
        )


def test_same_order_in_different_focus_buckets_is_allowed():
    value = request(
        [
            task(
                1,
                duration_category=
                    "UNDER_20_MINUTES",
                anchor_order=1,
            ),
            task(
                2,
                duration_category=
                    "UNDER_1_HOUR",
                anchor_order=1,
            ),
            task(
                3,
                duration_category=
                    "UNDER_4_HOURS",
                anchor_order=1,
            ),
        ]
    )

    assert len(
        value.tasks
    ) == 3


def test_public_engine_preserves_bucket_local_order_and_global_ranks():
    result = SchedulerEngineV1(
        max_iterations=0,
        max_evaluations=0,
    ).run(
        request(
            [
                # Baseline global item-id order begins with Boss item 1.
                # Explicit Boss position #2 moves it behind Boss item 4,
                # without taking Quick or Side positions.
                task(
                    1,
                    duration_category=
                        "UNDER_4_HOURS",
                    anchor_order=2,
                ),
                task(
                    2,
                    duration_category=
                        "UNDER_20_MINUTES",
                    anchor_order=1,
                ),
                task(
                    3,
                    duration_category=
                        "UNDER_1_HOUR",
                    anchor_order=1,
                ),
                task(
                    4,
                    duration_category=
                        "UNDER_8_HOURS",
                ),
            ]
        )
    )

    rows = sorted(
        (
            row
            for row
            in result.allocations
            if (
                row.scheduled_date
                == TODAY
            )
        ),
        key=lambda row:
            row.execution_rank,
    )

    assert [
        row.execution_rank
        for row in rows
    ] == [
        1,
        2,
        3,
        4,
    ]

    # Cross-bucket positions remain where the automatic global ordering
    # placed them. Only the two Boss rows exchange Boss-local order.
    assert [
        row.item_id
        for row in rows
    ] == [
        4,
        2,
        3,
        1,
    ]

    boss_rows = [
        row
        for row in rows
        if row.item_id
        in {
            1,
            4,
        }
    ]

    assert [
        row.item_id
        for row in boss_rows
    ] == [
        4,
        1,
    ]

    # The anchored Boss item is Boss-local #2 even though its final global
    # execution rank is #4.
    anchored = next(
        row
        for row in rows
        if row.item_id == 1
    )

    assert (
        anchored.execution_rank
        == 4
    )


def test_residual_work_shares_quick_win_ordering_bucket():
    with pytest.raises(
        ValueError,
        match=(
            "Duplicate anchored execution slot"
        ),
    ):
        request(
            [
                task(
                    1,
                    duration_category=
                        "UNDER_4_HOURS",
                    is_residual=True,
                    anchor_order=1,
                ),
                task(
                    2,
                    duration_category=
                        "UNDER_20_MINUTES",
                    anchor_order=1,
                ),
            ]
        )


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
        if (
            row.scheduled_date
            == TODAY
        )
    ] == [
        1,
        2,
        3,
    ]
