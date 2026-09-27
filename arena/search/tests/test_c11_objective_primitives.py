from dataclasses import replace

from arena.scheduling.objectives import (
    PowerCost,
    ThresholdCost,
)
from arena.search.objective import (
    score_state,
)

from .helpers import (
    TODAY,
    DAY,
    item,
    objective,
    problem,
    state,
)


def test_pre_c11_objective_semantics_are_zero_by_default():
    s = state(
        problem(
            item(
                duration_category=
                    'OVER_16_HOURS',
            ),
        ),
        (0, 0, 3),
    )

    score = score_state(
        s,
        objective(
            timing=1,
            overload=0,
        ),
    )

    assert (
        score.continuity
        == 0
    )

    assert (
        score.avoidable_idle
        == 0
    )

    assert (
        score.same_day_repeat
        == 0
    )

    assert (
        score.daily_concentration
        == 0
    )

    assert score.total == (
        score.deadline
        + score.priority
        + score.overload
        + score.movement
        + score.timing
    )


def test_continuity_penalises_only_calendar_gaps_between_sessions():
    p = problem(
        item(
            duration_category=
                'OVER_16_HOURS',
        ),
    )

    consecutive = state(
        p,
        (0, 1, 2),
    )

    gapped = state(
        p,
        (0, 1, 3),
    )

    cfg = replace(
        objective(
            overload=0,
        ),
        continuity=
            PowerCost(
                2,
                1,
            ),
    )

    assert (
        score_state(
            consecutive,
            cfg,
        ).continuity
        == 0
    )

    assert (
        score_state(
            gapped,
            cfg,
        ).continuity
        == 2
    )


def test_same_day_repeat_detects_cramming_without_calling_it_fragmentation():
    p = problem(
        item(
            duration_category=
                'OVER_16_HOURS',
        ),
    )

    crammed = state(
        p,
        (0, 0, 0),
    )

    spread = state(
        p,
        (0, 1, 2),
    )

    cfg = replace(
        objective(
            overload=0,
        ),
        same_day_repeat=
            PowerCost(
                3,
                1,
            ),
    )

    assert (
        score_state(
            crammed,
            cfg,
        ).same_day_repeat
        == 6
    )

    assert (
        score_state(
            spread,
            cfg,
        ).same_day_repeat
        == 0
    )


def test_daily_concentration_penalises_sessions_above_soft_comfort_threshold():
    p = problem(
        item(1),
        item(2),
        item(3),
        item(4),
    )

    heavy = state(
        p,
        (0,),
        (0,),
        (0,),
        (0,),
    )

    smooth = state(
        p,
        (0,),
        (0,),
        (1,),
        (1,),
    )

    cfg = replace(
        objective(
            overload=0,
        ),
        daily_concentration=
            ThresholdCost(
                PowerCost(
                    1,
                    2,
                ),
                2,
            ),
    )

    assert (
        score_state(
            heavy,
            cfg,
        ).daily_concentration
        == 4
    )

    assert (
        score_state(
            smooth,
            cfg,
        ).daily_concentration
        == 0
    )


def test_avoidable_idle_detects_empty_day_before_legally_movable_future_work():
    p = problem(
        item(1),
        item(2),
    )

    with_gap = state(
        p,
        (0,),
        (2,),
    )

    without_gap = state(
        p,
        (0,),
        (1,),
    )

    cfg = replace(
        objective(
            overload=0,
        ),
        avoidable_idle=
            PowerCost(
                5,
                1,
            ),
    )

    assert (
        score_state(
            with_gap,
            cfg,
        ).avoidable_idle
        == 5
    )

    assert (
        score_state(
            without_gap,
            cfg,
        ).avoidable_idle
        == 0
    )


def test_release_forced_empty_day_is_not_avoidable_idle():
    p = problem(
        item(1),
        item(
            2,
            release_date=
                TODAY + 2 * DAY,
        ),
    )

    s = state(
        p,
        (0,),
        (2,),
    )

    cfg = replace(
        objective(
            overload=0,
        ),
        avoidable_idle=
            PowerCost(
                5,
                1,
            ),
    )

    assert (
        score_state(
            s,
            cfg,
        ).avoidable_idle
        == 0
    )
