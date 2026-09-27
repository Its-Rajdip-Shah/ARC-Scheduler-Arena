from arena.c10.human_diagnostics import (
    compute_human_diagnostics,
)


def test_human_diagnostics_detect_concentration_and_repeat_sessions():
    rows = [
        {
            "scheduled_date": "2026-09-28",
            "item_key": "a",
            "group": "A",
        },
        {
            "scheduled_date": "2026-09-28",
            "item_key": "a",
            "group": "A",
        },
        {
            "scheduled_date": "2026-09-28",
            "item_key": "b",
            "group": "B",
        },
        {
            "scheduled_date": "2026-09-29",
            "item_key": "c",
            "group": "A",
        },
    ]

    diagnostics = (
        compute_human_diagnostics(
            rows
        )
    )

    assert diagnostics.active_day_count == 2
    assert diagnostics.total_session_count == 4
    assert diagnostics.first_day_session_count == 3
    assert diagnostics.max_sessions_on_day == 3
    assert (
        diagnostics
        .multi_session_same_day_item_count
        == 1
    )
    assert (
        diagnostics
        .same_item_same_day_extra_session_count
        == 1
    )
    assert diagnostics.mixed_group_day_count == 1
