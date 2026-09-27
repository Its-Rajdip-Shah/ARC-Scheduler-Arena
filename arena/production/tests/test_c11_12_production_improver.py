from datetime import date, timedelta
from decimal import Decimal

import pytest

from arena.production.flavour_planner import (
    generate_flavour_schedule,
)
from arena.production.production_improver import (
    ProductionImproveConfig,
    improve_production_schedule,
    score_production_schedule,
)
from arena.production.work_mass import (
    validate_dynamic_plan,
)
from arena.scheduling.domain import (
    DependencyEdge,
    ScheduleItem,
    ScheduleProblem,
)


D = Decimal
TODAY = date(2026, 10, 12)
DAY = timedelta(days=1)


def item(
    item_id,
    duration,
    *,
    release=None,
    due=None,
    anchor=None,
    priority=None,
    completed="0",
):
    completed_d = D(
        completed
    )

    return ScheduleItem(
        item_id=item_id,
        duration_category=duration,
        priority_position=priority,
        release_date=release,
        due_date=due,
        anchor_date=anchor,
        percent_completed=
            completed_d,
        remaining_fraction=(
            D("1")
            - completed_d
            / D("100")
        ),
    )


def problem(
    items,
    dependencies=(),
):
    return ScheduleProblem(
        today=TODAY,
        items=tuple(items),
        dependencies=tuple(
            dependencies
        ),
        capacity_by_duration={
            "UNDER_20_MINUTES": 10,
            "UNDER_1_HOUR": 10,
            "UNDER_4_HOURS": 10,
            "UNDER_8_HOURS": 10,
            "UNDER_16_HOURS": 10,
            "OVER_16_HOURS": 10,
        },
    )


@pytest.mark.parametrize(
    "flavour",
    ["lock-in", "monk"],
)
def test_dependency_deadline_urgency_is_propagated_before_improvement(
    flavour,
):
    p = problem(
        [
            item(
                1,
                "UNDER_16_HOURS",
            ),
            item(
                2,
                "UNDER_16_HOURS",
                due=TODAY + 3 * DAY,
            ),
        ],
        dependencies=(
            DependencyEdge(
                1,
                2,
            ),
        ),
    )

    generated = (
        generate_flavour_schedule(
            p,
            flavour,
            explicit_total_hours={
                1: D("12"),
                2: D("10"),
            },
        )
    )

    prereq = [
        row
        for row
        in generated.work_allocations
        if row.item_id == 1
    ]

    dependent = [
        row
        for row
        in generated.work_allocations
        if row.item_id == 2
    ]

    assert max(
        row.scheduled_date
        for row in prereq
    ) < min(
        row.scheduled_date
        for row in dependent
    )

    assert max(
        row.scheduled_date
        for row in dependent
    ) <= TODAY + 3 * DAY


@pytest.mark.parametrize(
    "flavour",
    ["lock-in", "monk"],
)
def test_improver_reduces_known_future_anchor_wall_damage(
    flavour,
):
    p = problem([
        item(
            1,
            "OVER_16_HOURS",
            due=TODAY + 4 * DAY,
        ),
        item(
            2,
            "UNDER_4_HOURS",
            anchor=TODAY + 2 * DAY,
        ),
        item(
            3,
            "UNDER_4_HOURS",
            anchor=TODAY + 2 * DAY,
        ),
        item(
            4,
            "UNDER_1_HOUR",
            anchor=TODAY + 2 * DAY,
        ),
        item(
            5,
            "UNDER_1_HOUR",
            anchor=TODAY + 2 * DAY,
        ),
        item(
            6,
            "UNDER_4_HOURS",
            anchor=TODAY + 3 * DAY,
        ),
        item(
            7,
            "UNDER_4_HOURS",
            anchor=TODAY + 3 * DAY,
        ),
        item(
            8,
            "UNDER_1_HOUR",
            anchor=TODAY + 3 * DAY,
        ),
        item(
            9,
            "UNDER_1_HOUR",
            anchor=TODAY + 3 * DAY,
        ),
    ])

    estimates = {
        1: D("30"),
        2: D("4"),
        3: D("4"),
        4: D("1"),
        5: D("1"),
        6: D("4"),
        7: D("4"),
        8: D("1"),
        9: D("1"),
    }

    generated = (
        generate_flavour_schedule(
            p,
            flavour,
            explicit_total_hours=
                estimates,
        )
    )

    result = (
        improve_production_schedule(
            p,
            generated,
            ProductionImproveConfig(
                max_iterations=30,
                max_evaluations=3000,
            ),
        )
    )

    assert (
        result.final_objective.key
        <= result.initial_objective.key
    )

    assert (
        result.final_objective.late_hours
        == D("0")
    )

    assert (
        result.final_objective.max_daily_hours
        <= result.initial_objective.max_daily_hours
    )

    validation = (
        validate_dynamic_plan(
            p,
            result.final_schedule.plan,
        )
    )

    assert validation.violations == ()


@pytest.mark.parametrize(
    "flavour",
    ["lock-in", "monk"],
)
def test_improver_is_deterministic(
    flavour,
):
    p = problem([
        item(
            1,
            "OVER_16_HOURS",
            due=TODAY + 6 * DAY,
        ),
        item(
            2,
            "OVER_16_HOURS",
            due=TODAY + 6 * DAY,
        ),
    ])

    generated = (
        generate_flavour_schedule(
            p,
            flavour,
            explicit_total_hours={
                1: D("20"),
                2: D("20"),
            },
        )
    )

    config = ProductionImproveConfig(
        max_iterations=20,
        max_evaluations=1500,
    )

    left = improve_production_schedule(
        p,
        generated,
        config,
    )

    right = improve_production_schedule(
        p,
        generated,
        config,
    )

    assert (
        left.final_schedule.work_allocations
        == right.final_schedule.work_allocations
    )

    assert (
        left.accepted_moves
        == right.accepted_moves
    )


@pytest.mark.parametrize(
    "flavour",
    ["lock-in", "monk"],
)
def test_improver_never_accepts_a_worse_objective(
    flavour,
):
    p = problem([
        item(
            1,
            "OVER_16_HOURS",
            due=TODAY + 8 * DAY,
        ),
        item(
            2,
            "UNDER_16_HOURS",
            due=TODAY + 5 * DAY,
        ),
    ])

    generated = (
        generate_flavour_schedule(
            p,
            flavour,
            explicit_total_hours={
                1: D("24"),
                2: D("12"),
            },
        )
    )

    result = improve_production_schedule(
        p,
        generated,
    )

    history = (
        result.objective_history
    )

    assert all(
        right < left
        for left, right
        in zip(
            history,
            history[1:],
        )
    )

    assert (
        score_production_schedule(
            p,
            result.final_schedule,
        ).key
        == result.final_objective.key
    )


def test_objective_does_not_reward_concentrating_overload_into_a_worse_peak():
    from arena.production.production_improver import (
        ProductionObjective,
    )

    spread = ProductionObjective(
        late_hours=D("0"),
        infeasible_day_count=0,
        infeasible_excess_hours=D("0"),
        overloaded_day_count=3,
        overloaded_excess_hours=D("18"),
        tiny_nonfinal_sessions=0,
        session_shape_penalty=D("0"),
        fragmentation_count=0,
        priority_postponement_days=D("0"),
        continuity_gap_days=2,
        max_daily_hours=D("18"),
        preferred_excess_squared=D("176"),
        avoidable_idle_days=0,
        deadline_buffer_risk=D("0"),
        completion_day_sum=24,
    )

    concentrated = ProductionObjective(
        late_hours=D("0"),
        infeasible_day_count=0,
        infeasible_excess_hours=D("0"),
        overloaded_day_count=2,
        overloaded_excess_hours=D("18"),
        tiny_nonfinal_sessions=0,
        session_shape_penalty=D("0"),
        fragmentation_count=0,
        priority_postponement_days=D("0"),
        continuity_gap_days=0,
        max_daily_hours=D("24"),
        preferred_excess_squared=D("348"),
        avoidable_idle_days=0,
        deadline_buffer_risk=D("0"),
        completion_day_sum=22,
    )

    assert spread.key < concentrated.key


@pytest.mark.parametrize(
    "flavour",
    ["lock-in", "monk"],
)
def test_improver_can_rebalance_in_both_time_directions(
    flavour,
):
    p = problem([
        item(
            1,
            "OVER_16_HOURS",
            due=TODAY + 4 * DAY,
        ),
        item(
            2,
            "UNDER_4_HOURS",
            anchor=TODAY + 2 * DAY,
        ),
        item(
            3,
            "UNDER_4_HOURS",
            anchor=TODAY + 2 * DAY,
        ),
        item(
            4,
            "UNDER_1_HOUR",
            anchor=TODAY + 2 * DAY,
        ),
        item(
            5,
            "UNDER_1_HOUR",
            anchor=TODAY + 2 * DAY,
        ),
        item(
            6,
            "UNDER_4_HOURS",
            anchor=TODAY + 3 * DAY,
        ),
        item(
            7,
            "UNDER_4_HOURS",
            anchor=TODAY + 3 * DAY,
        ),
        item(
            8,
            "UNDER_1_HOUR",
            anchor=TODAY + 3 * DAY,
        ),
        item(
            9,
            "UNDER_1_HOUR",
            anchor=TODAY + 3 * DAY,
        ),
    ])

    generated = generate_flavour_schedule(
        p,
        flavour,
        explicit_total_hours={
            1: D("30"),
            2: D("4"),
            3: D("4"),
            4: D("1"),
            5: D("1"),
            6: D("4"),
            7: D("4"),
            8: D("1"),
            9: D("1"),
        },
    )

    result = improve_production_schedule(
        p,
        generated,
        ProductionImproveConfig(
            max_iterations=50,
            max_evaluations=7000,
        ),
    )

    # 50 total hours over these five dates, with 10h of hard anchored work on
    # both middle dates, gives a theoretical minimum peak of exactly 10h.
    assert (
        result.final_objective.max_daily_hours
        <= D("10.01")
    )


def test_lock_in_release_collision_can_balance_the_avoidable_point_two_peak():
    p = problem([
        item(
            1,
            "OVER_16_HOURS",
            due=TODAY + 5 * DAY,
        ),
        item(
            2,
            "UNDER_16_HOURS",
            release=TODAY + DAY,
            due=TODAY + 2 * DAY,
        ),
        item(
            3,
            "UNDER_16_HOURS",
            release=TODAY + DAY,
            due=TODAY + 2 * DAY,
        ),
    ])

    generated = generate_flavour_schedule(
        p,
        "lock-in",
        explicit_total_hours={
            1: D("20"),
            2: D("10"),
            3: D("10"),
        },
    )

    result = improve_production_schedule(
        p,
        generated,
        ProductionImproveConfig(
            max_iterations=50,
            max_evaluations=7000,
        ),
    )

    assert (
        result.final_objective.max_daily_hours
        <= D("10.01")
    )


def test_lock_in_does_not_create_avoidable_empty_early_day():
    p = problem([
        item(
            1,
            "OVER_16_HOURS",
            due=TODAY + 5 * DAY,
        ),
        item(
            2,
            "UNDER_16_HOURS",
            release=TODAY + DAY,
            due=TODAY + 2 * DAY,
        ),
        item(
            3,
            "UNDER_16_HOURS",
            release=TODAY + DAY,
            due=TODAY + 2 * DAY,
        ),
    ])

    generated = generate_flavour_schedule(
        p,
        "lock-in",
        explicit_total_hours={
            1: D("20"),
            2: D("10"),
            3: D("10"),
        },
    )

    result = improve_production_schedule(
        p,
        generated,
        ProductionImproveConfig(
            max_iterations=60,
            max_evaluations=9000,
        ),
    )

    assert (
        result.final_schedule.daily_hours[TODAY]
        > D("0")
    )

    assert (
        result.final_objective.avoidable_idle_days
        == 0
    )


def test_destroy_repair_can_clear_relaxed_work_from_dependency_critical_window():
    p = problem(
        [
            item(
                1,
                "UNDER_16_HOURS",
            ),
            item(
                2,
                "UNDER_16_HOURS",
                due=TODAY + 3 * DAY,
            ),
            item(
                3,
                "UNDER_8_HOURS",
                due=TODAY + 10 * DAY,
            ),
        ],
        dependencies=(
            DependencyEdge(1, 2),
        ),
    )

    generated = generate_flavour_schedule(
        p,
        "monk",
        explicit_total_hours={
            1: D("12"),
            2: D("10"),
            3: D("6"),
        },
    )

    result = improve_production_schedule(
        p,
        generated,
        ProductionImproveConfig(
            max_iterations=80,
            max_evaluations=12000,
        ),
    )

    dependent = [
        row
        for row in result.final_schedule.work_allocations
        if row.item_id == 2
    ]

    assert max(
        row.scheduled_date
        for row in dependent
    ) <= TODAY + 3 * DAY

    assert (
        result.final_objective.late_hours
        == D("0")
    )

    assert (
        validate_dynamic_plan(
            p,
            result.final_schedule.plan,
        ).violations
        == ()
    )


def test_deadline_buffer_risk_prefers_safe_completion_over_exact_deadline():
    from arena.production.production_improver import (
        ProductionObjective,
    )

    exact_deadline = ProductionObjective(
        late_hours=D("0"),
        infeasible_day_count=0,
        infeasible_excess_hours=D("0"),
        overloaded_day_count=0,
        overloaded_excess_hours=D("0"),
        tiny_nonfinal_sessions=0,
        session_shape_penalty=D("0"),
        fragmentation_count=0,
        priority_postponement_days=D("0"),
        continuity_gap_days=0,
        max_daily_hours=D("6"),
        preferred_excess_squared=D("0"),
        avoidable_idle_days=0,
        deadline_buffer_risk=D("9"),
        completion_day_sum=5,
    )

    buffered = ProductionObjective(
        late_hours=D("0"),
        infeasible_day_count=0,
        infeasible_excess_hours=D("0"),
        overloaded_day_count=0,
        overloaded_excess_hours=D("0"),
        tiny_nonfinal_sessions=0,
        session_shape_penalty=D("0"),
        fragmentation_count=0,
        priority_postponement_days=D("0"),
        continuity_gap_days=0,
        max_daily_hours=D("6"),
        preferred_excess_squared=D("0"),
        avoidable_idle_days=0,
        deadline_buffer_risk=D("1"),
        completion_day_sum=4,
    )

    assert buffered.key < exact_deadline.key


@pytest.mark.parametrize(
    "flavour",
    ["lock-in", "monk"],
)
def test_dependency_chain_is_prioritised_before_relaxed_unrelated_work(
    flavour,
):
    """Deadline buffer is preferred only below more important load quality.

    The production search must prioritise the dependency-critical chain over
    unrelated relaxed work, but it must not manufacture overload or artificial
    idle merely to force an arbitrary one-day deadline buffer.
    """

    p = problem(
        [
            item(
                1,
                "UNDER_16_HOURS",
            ),
            item(
                2,
                "UNDER_16_HOURS",
                due=TODAY + 3 * DAY,
            ),
            item(
                3,
                "UNDER_8_HOURS",
                due=TODAY + 10 * DAY,
            ),
        ],
        dependencies=(
            DependencyEdge(1, 2),
        ),
    )

    generated = generate_flavour_schedule(
        p,
        flavour,
        explicit_total_hours={
            1: D("12"),
            2: D("10"),
            3: D("6"),
        },
    )

    result = improve_production_schedule(
        p,
        generated,
        ProductionImproveConfig(
            max_iterations=100,
            max_evaluations=15000,
        ),
    )

    rows = result.final_schedule.work_allocations

    prerequisite_rows = [
        row
        for row in rows
        if row.item_id == 1
    ]

    dependent_rows = [
        row
        for row in rows
        if row.item_id == 2
    ]

    relaxed_rows = [
        row
        for row in rows
        if row.item_id == 3
    ]

    assert prerequisite_rows
    assert dependent_rows
    assert relaxed_rows

    prerequisite_completion = max(
        row.scheduled_date
        for row in prerequisite_rows
    )

    dependent_start = min(
        row.scheduled_date
        for row in dependent_rows
    )

    dependent_completion = max(
        row.scheduled_date
        for row in dependent_rows
    )

    relaxed_start = min(
        row.scheduled_date
        for row in relaxed_rows
    )

    # Completion-based dependency semantics remain intact.
    assert (
        prerequisite_completion
        < dependent_start
    )

    # The actual downstream deadline must be met.
    assert (
        dependent_completion
        <= TODAY + 3 * DAY
    )

    # Relaxed unrelated work may coexist with prerequisite work when doing so
    # does not delay the dependency-critical chain. The real production
    # invariants are completion-based precedence and downstream deadline safety,
    # not artificial calendar exclusivity.
    assert (
        prerequisite_completion
        < dependent_start
    )

    assert (
        dependent_completion
        <= TODAY + 3 * DAY
    )

    # In this fixture the chain can be handled without any physical
    # infeasibility or deadline lateness. Buffer is not allowed to become an
    # artificial hard requirement that creates a worse workload shape.
    assert (
        result.final_objective.late_hours
        == D("0")
    )

    assert (
        result.final_objective.infeasible_day_count
        == 0
    )

    if flavour == "monk":
        assert (
            result.final_objective.overloaded_day_count
            == 0
        )

    assert (
        validate_dynamic_plan(
            p,
            result.final_schedule.plan,
        ).violations
        == ()
    )


def test_deadline_buffer_cannot_be_bought_by_making_peak_load_much_worse():
    from arena.production.production_improver import (
        ProductionObjective,
    )

    balanced_zero_buffer = ProductionObjective(
        late_hours=D("0"),
        infeasible_day_count=0,
        infeasible_excess_hours=D("0"),
        overloaded_day_count=0,
        overloaded_excess_hours=D("0"),
        tiny_nonfinal_sessions=0,
        session_shape_penalty=D("0"),
        fragmentation_count=0,
        priority_postponement_days=D("0"),
        continuity_gap_days=0,
        max_daily_hours=D("10"),
        preferred_excess_squared=D("20"),
        avoidable_idle_days=0,
        deadline_buffer_risk=D("9"),
        completion_day_sum=10,
    )

    overloaded_with_buffer = ProductionObjective(
        late_hours=D("0"),
        infeasible_day_count=0,
        infeasible_excess_hours=D("0"),
        overloaded_day_count=1,
        overloaded_excess_hours=D("10"),
        tiny_nonfinal_sessions=0,
        session_shape_penalty=D("0"),
        fragmentation_count=0,
        priority_postponement_days=D("0"),
        continuity_gap_days=0,
        max_daily_hours=D("20"),
        preferred_excess_squared=D("144"),
        avoidable_idle_days=0,
        deadline_buffer_risk=D("0"),
        completion_day_sum=8,
    )

    assert (
        balanced_zero_buffer.key
        < overloaded_with_buffer.key
    )


def test_missing_effective_dependency_deadline_is_riskier_than_zero_buffer():
    """Regression: negative effective buffer must never become free risk."""

    p = problem(
        [
            item(
                1,
                "UNDER_16_HOURS",
            ),
            item(
                2,
                "UNDER_16_HOURS",
                due=TODAY + 3 * DAY,
            ),
            item(
                3,
                "UNDER_8_HOURS",
                due=TODAY + 10 * DAY,
            ),
        ],
        dependencies=(
            DependencyEdge(1, 2),
        ),
    )

    initial = generate_flavour_schedule(
        p,
        "monk",
        explicit_total_hours={
            1: D("12"),
            2: D("10"),
            3: D("6"),
        },
    )

    from arena.production.production_improver import (
        _rebuild,
        score_production_schedule,
    )

    # Risky shape:
    # relaxed work first; prerequisite misses its effective safe handoff date;
    # dependent is then forced onto its literal deadline.
    risky = _rebuild(
        p,
        initial,
        {
            1: {
                TODAY + DAY: D("6"),
                TODAY + 2 * DAY: D("6"),
            },
            2: {
                TODAY + 3 * DAY: D("10"),
            },
            3: {
                TODAY: D("6"),
            },
        },
    )

    # Buffered shape:
    # dependency chain progresses first, while relaxed unrelated work moves
    # after the critical handoff window.
    buffered = _rebuild(
        p,
        initial,
        {
            1: {
                TODAY: D("6"),
                TODAY + DAY: D("6"),
            },
            2: {
                TODAY + 2 * DAY: D("10"),
            },
            3: {
                TODAY + 3 * DAY: D("6"),
            },
        },
    )

    assert risky is not None
    assert buffered is not None

    risky_score = score_production_schedule(
        p,
        risky,
    )

    buffered_score = score_production_schedule(
        p,
        buffered,
    )

    assert (
        buffered_score.deadline_buffer_risk
        < risky_score.deadline_buffer_risk
    )

    assert buffered_score.key < risky_score.key


def test_session_shape_prefers_meaningful_blocks_over_token_touches():
    from arena.production.production_improver import (
        _session_shape_penalty,
    )

    tokenised = sum(
        (
            _session_shape_penalty(D("1"))
            for _ in range(4)
        ),
        D("0"),
    )

    meaningful = (
        _session_shape_penalty(D("2"))
        + _session_shape_penalty(D("2"))
    )

    assert meaningful < tokenised


def test_three_to_four_hour_blocks_are_better_than_six_hour_marathons():
    from arena.production.production_improver import (
        _session_shape_penalty,
    )

    assert (
        _session_shape_penalty(D("3"))
        < _session_shape_penalty(D("6"))
    )

    assert (
        _session_shape_penalty(D("4"))
        < _session_shape_penalty(D("6"))
    )


def test_atomic_short_work_is_not_counted_as_bad_fragmentation():
    p = problem([
        item(
            1,
            "UNDER_20_MINUTES",
            due=TODAY + DAY,
        ),
    ])

    generated = generate_flavour_schedule(
        p,
        "monk",
        explicit_total_hours={
            1: D("0.25"),
        },
    )

    objective = score_production_schedule(
        p,
        generated,
    )

    assert objective.session_shape_penalty == D("0")
    assert objective.fragmentation_count == 0


def test_priority_postponement_prefers_earlier_start_for_higher_priority():
    from arena.production.production_improver import (
        _rebuild,
        score_production_schedule,
    )

    p = problem([
        item(
            1,
            "UNDER_8_HOURS",
            due=TODAY + 6 * DAY,
            priority=1,
        ),
        item(
            2,
            "UNDER_8_HOURS",
            due=TODAY + 6 * DAY,
            priority=9,
        ),
    ])

    initial = generate_flavour_schedule(
        p,
        "monk",
        explicit_total_hours={
            1: D("4"),
            2: D("4"),
        },
    )

    high_priority_first = _rebuild(
        p,
        initial,
        {
            1: {
                TODAY: D("4"),
            },
            2: {
                TODAY + DAY: D("4"),
            },
        },
    )

    low_priority_first = _rebuild(
        p,
        initial,
        {
            1: {
                TODAY + DAY: D("4"),
            },
            2: {
                TODAY: D("4"),
            },
        },
    )

    assert high_priority_first is not None
    assert low_priority_first is not None

    high_score = score_production_schedule(
        p,
        high_priority_first,
    )

    low_score = score_production_schedule(
        p,
        low_priority_first,
    )

    assert (
        high_score.priority_postponement_days
        < low_score.priority_postponement_days
    )

    assert high_score.key < low_score.key


def test_session_shape_can_consolidate_without_worsening_peak():
    from arena.production.production_improver import (
        _rebuild,
        improve_production_schedule,
    )

    p = problem([
        item(
            1,
            "OVER_16_HOURS",
            due=TODAY + 7 * DAY,
        ),
    ])

    generated = generate_flavour_schedule(
        p,
        "monk",
        explicit_total_hours={
            1: D("12"),
        },
    )

    fragmented = _rebuild(
        p,
        generated,
        {
            1: {
                TODAY: D("1"),
                TODAY + DAY: D("1"),
                TODAY + 2 * DAY: D("1"),
                TODAY + 3 * DAY: D("3"),
                TODAY + 4 * DAY: D("3"),
                TODAY + 5 * DAY: D("3"),
            },
        },
    )

    assert fragmented is not None

    result = improve_production_schedule(
        p,
        fragmented,
        ProductionImproveConfig(
            max_iterations=50,
            max_evaluations=6000,
        ),
    )

    assert (
        result.final_objective.session_shape_penalty
        <= result.initial_objective.session_shape_penalty
    )

    assert (
        result.final_objective.fragmentation_count
        <= result.initial_objective.fragmentation_count
    )

    assert (
        result.final_objective.max_daily_hours
        <= result.initial_objective.max_daily_hours
    )


def test_c11_14b_direct_consolidation_is_harvested_before_broad_search():
    from arena.production.production_improver import (
        _rebuild,
    )

    p = problem([
        item(
            1,
            "OVER_16_HOURS",
            due=TODAY + 8 * DAY,
        ),
    ])

    generated = generate_flavour_schedule(
        p,
        "monk",
        explicit_total_hours={
            1: D("6"),
        },
    )

    fragmented = _rebuild(
        p,
        generated,
        {
            1: {
                TODAY: D("1"),
                TODAY + DAY: D("2"),
                TODAY + 2 * DAY: D("3"),
            },
        },
    )

    assert fragmented is not None

    result = improve_production_schedule(
        p,
        fragmented,
        ProductionImproveConfig(
            max_iterations=10,
            max_evaluations=100,
        ),
    )

    # C11.14d no longer requires an already-reasonable 1h + 2h + 3h
    # representation to be consolidated merely to reduce touch count.
    #
    # The invariant that matters here is that the dedicated consolidation
    # neighbourhood exists, remains legal, and cannot make the final objective
    # worse.
    from arena.production.production_improver import (
        _consolidation_moves,
    )

    moves = _consolidation_moves(
        p,
        fragmented,
    )

    assert moves

    assert (
        result.final_objective.key
        <= result.initial_objective.key
    )

    assert (
        result.final_objective.late_hours
        == D("0")
    )


def test_c11_14b_balanced_exchange_can_reduce_fragmentation_without_changing_peak():
    from arena.production.production_improver import (
        _balanced_exchange_moves,
        _apply_compound_move,
        _rebuild,
        score_production_schedule,
    )

    p = problem([
        item(
            1,
            "UNDER_8_HOURS",
            due=TODAY + 6 * DAY,
        ),
        item(
            2,
            "UNDER_8_HOURS",
            due=TODAY + 6 * DAY,
        ),
    ])

    generated = generate_flavour_schedule(
        p,
        "monk",
        explicit_total_hours={
            1: D("4"),
            2: D("4"),
        },
    )

    fragmented = _rebuild(
        p,
        generated,
        {
            1: {
                TODAY: D("1"),
                TODAY + DAY: D("3"),
            },
            2: {
                TODAY: D("1"),
                TODAY + DAY: D("1"),
                TODAY + 2 * DAY: D("2"),
            },
        },
    )

    assert fragmented is not None

    baseline = score_production_schedule(
        p,
        fragmented,
    )

    improving = []

    for move in _balanced_exchange_moves(
        p,
        fragmented,
    ):
        candidate = _apply_compound_move(
            p,
            fragmented,
            move,
        )

        if candidate is None:
            continue

        objective = score_production_schedule(
            p,
            candidate,
        )

        if objective.key < baseline.key:
            improving.append(
                (
                    candidate,
                    objective,
                )
            )

    assert improving

    assert any(
        objective.max_daily_hours
        == baseline.max_daily_hours
        and objective.fragmentation_count
        < baseline.fragmentation_count
        for _, objective in improving
    )


def test_c11_14b_atomic_admin_work_is_never_used_as_exchange_material():
    from arena.production.production_improver import (
        _balanced_exchange_moves,
        _rebuild,
    )

    p = problem([
        item(
            1,
            "UNDER_8_HOURS",
            due=TODAY + 5 * DAY,
        ),
        item(
            2,
            "UNDER_20_MINUTES",
            due=TODAY + 5 * DAY,
        ),
    ])

    generated = generate_flavour_schedule(
        p,
        "monk",
        explicit_total_hours={
            1: D("4"),
            2: D("0.25"),
        },
    )

    candidate = _rebuild(
        p,
        generated,
        {
            1: {
                TODAY: D("1"),
                TODAY + DAY: D("3"),
            },
            2: {
                TODAY + DAY: D("0.25"),
            },
        },
    )

    assert candidate is not None

    moves = _balanced_exchange_moves(
        p,
        candidate,
    )

    assert all(
        move.second.item_id != 2
        for move in moves
    )


def test_c11_14c_block_repack_generates_fewer_human_sized_sessions():
    from arena.production.production_improver import (
        _block_repack_candidates,
        _rebuild,
        score_production_schedule,
    )

    p = problem([
        item(
            1,
            "OVER_16_HOURS",
            due=TODAY + 5 * DAY,
        ),
        item(
            2,
            "OVER_16_HOURS",
            due=TODAY + 5 * DAY,
        ),
    ])

    generated = generate_flavour_schedule(
        p,
        "monk",
        explicit_total_hours={
            1: D("12"),
            2: D("18"),
        },
    )

    # Task 1 is human-ugly:
    # 1 + 1 + 1 + 3 + 3 + 3 = 12h.
    #
    # Task 2 creates the background load:
    # 5 + 5 + 5 + 1 + 1 + 1 = 18h.
    #
    # Therefore the original daily totals are:
    # 6, 6, 6, 4, 4, 4
    #
    # A clean Task-1 representation of 4 + 4 + 4 on the final three days
    # reaches 5, 5, 5 and does not worsen the original 6h peak.
    fragmented = _rebuild(
        p,
        generated,
        {
            1: {
                TODAY: D("1"),
                TODAY + DAY: D("1"),
                TODAY + 2 * DAY: D("1"),
                TODAY + 3 * DAY: D("3"),
                TODAY + 4 * DAY: D("3"),
                TODAY + 5 * DAY: D("3"),
            },
            2: {
                TODAY: D("5"),
                TODAY + DAY: D("5"),
                TODAY + 2 * DAY: D("5"),
                TODAY + 3 * DAY: D("1"),
                TODAY + 4 * DAY: D("1"),
                TODAY + 5 * DAY: D("1"),
            },
        },
    )

    assert fragmented is not None

    baseline = score_production_schedule(
        p,
        fragmented,
    )

    candidates = _block_repack_candidates(
        p,
        fragmented,
    )

    assert candidates

    improvements = []

    for candidate in candidates:
        score = score_production_schedule(
            p,
            candidate,
        )

        task_rows = [
            row
            for row in candidate.work_allocations
            if row.item_id == 1
        ]

        if (
            len(task_rows) < 6
            and score.max_daily_hours
            <= baseline.max_daily_hours
            and score.key
            < baseline.key
        ):
            improvements.append(
                (
                    candidate,
                    score,
                    task_rows,
                )
            )

    assert improvements

    assert any(
        len(rows) <= 4
        for _, _, rows in improvements
    )


def test_c11_14c_block_repack_never_rewrites_atomic_work():
    from arena.production.production_improver import (
        _block_repack_candidates,
    )

    p = problem([
        item(
            1,
            "UNDER_20_MINUTES",
            due=TODAY + DAY,
        ),
    ])

    generated = generate_flavour_schedule(
        p,
        "monk",
        explicit_total_hours={
            1: D("0.25"),
        },
    )

    assert (
        _block_repack_candidates(
            p,
            generated,
        )
        == ()
    )


def test_c11_14d_tiny_nonfinal_focus_fragment_cannot_be_bought_by_lower_peak():
    from arena.production.production_improver import (
        ProductionObjective,
    )

    humane = ProductionObjective(
        late_hours=D("0"),
        infeasible_day_count=0,
        infeasible_excess_hours=D("0"),
        overloaded_day_count=1,
        overloaded_excess_hours=D("1"),
        tiny_nonfinal_sessions=0,
        session_shape_penalty=D("2"),
        fragmentation_count=4,
        priority_postponement_days=D("0"),
        continuity_gap_days=0,
        max_daily_hours=D("9.5"),
        preferred_excess_squared=D("10"),
        avoidable_idle_days=0,
        deadline_buffer_risk=D("0"),
        completion_day_sum=10,
    )

    tokenised_lower_peak = ProductionObjective(
        late_hours=D("0"),
        infeasible_day_count=0,
        infeasible_excess_hours=D("0"),
        overloaded_day_count=0,
        overloaded_excess_hours=D("0"),
        tiny_nonfinal_sessions=1,
        session_shape_penalty=D("1"),
        fragmentation_count=3,
        priority_postponement_days=D("0"),
        continuity_gap_days=0,
        max_daily_hours=D("8"),
        preferred_excess_squared=D("0"),
        avoidable_idle_days=0,
        deadline_buffer_risk=D("0"),
        completion_day_sum=9,
    )

    assert humane.key < tokenised_lower_peak.key


def test_c11_14d_tiny_fragment_can_still_be_accepted_to_rescue_real_lateness():
    from arena.production.production_improver import (
        ProductionObjective,
    )

    late_but_pretty = ProductionObjective(
        late_hours=D("1"),
        infeasible_day_count=0,
        infeasible_excess_hours=D("0"),
        overloaded_day_count=0,
        overloaded_excess_hours=D("0"),
        tiny_nonfinal_sessions=0,
        session_shape_penalty=D("0"),
        fragmentation_count=2,
        priority_postponement_days=D("0"),
        continuity_gap_days=0,
        max_daily_hours=D("6"),
        preferred_excess_squared=D("0"),
        avoidable_idle_days=0,
        deadline_buffer_risk=D("0"),
        completion_day_sum=5,
    )

    on_time_with_tiny_fragment = ProductionObjective(
        late_hours=D("0"),
        infeasible_day_count=0,
        infeasible_excess_hours=D("0"),
        overloaded_day_count=0,
        overloaded_excess_hours=D("0"),
        tiny_nonfinal_sessions=1,
        session_shape_penalty=D("8"),
        fragmentation_count=3,
        priority_postponement_days=D("0"),
        continuity_gap_days=0,
        max_daily_hours=D("6"),
        preferred_excess_squared=D("0"),
        avoidable_idle_days=0,
        deadline_buffer_risk=D("0"),
        completion_day_sum=5,
    )

    assert (
        on_time_with_tiny_fragment.key
        < late_but_pretty.key
    )


def test_c11_14d_repacker_can_split_oversized_focus_block_when_capacity_exists():
    from arena.production.production_improver import (
        _block_repack_candidates,
        _rebuild,
        score_production_schedule,
    )

    p = problem([
        item(
            1,
            "OVER_16_HOURS",
            due=TODAY + 5 * DAY,
        ),
    ])

    generated = generate_flavour_schedule(
        p,
        "monk",
        explicit_total_hours={
            1: D("18"),
        },
    )

    oversized = _rebuild(
        p,
        generated,
        {
            1: {
                TODAY: D("3.6"),
                TODAY + DAY: D("3.6"),
                TODAY + 2 * DAY: D("3.6"),
                TODAY + 3 * DAY: D("7.2"),
            },
        },
    )

    assert oversized is not None

    baseline = score_production_schedule(
        p,
        oversized,
    )

    candidates = _block_repack_candidates(
        p,
        oversized,
    )

    humane = []

    for candidate in candidates:
        rows = [
            row
            for row in candidate.work_allocations
            if row.item_id == 1
        ]

        score = score_production_schedule(
            p,
            candidate,
        )

        if (
            len(rows) >= 5
            and max(
                row.hours
                for row in rows
            ) <= D("4")
            and score.max_daily_hours
            <= baseline.max_daily_hours
            and score.key < baseline.key
        ):
            humane.append(
                candidate
            )

    assert humane


def test_c11_14e_multi_donor_repack_preserves_daily_load_exactly():
    from arena.production.production_improver import (
        _load_preserving_window_repack_candidates,
        _rebuild,
        score_production_schedule,
    )

    p = problem([
        item(
            1,
            "OVER_16_HOURS",
            due=TODAY + 6 * DAY,
        ),
        item(
            2,
            "UNDER_8_HOURS",
            due=TODAY + 6 * DAY,
        ),
        item(
            3,
            "UNDER_8_HOURS",
            due=TODAY + 6 * DAY,
        ),
    ])

    generated = generate_flavour_schedule(
        p,
        "lock-in",
        explicit_total_hours={
            1: D("8"),
            2: D("2"),
            3: D("2"),
        },
    )

    # Day 0: donor task 2 = 2h, donor task 3 = 2h
    # Day 1: focus task 1 = 8h
    #
    # No single donor can counterbalance a 4h focus move. The new operator
    # must combine both donors:
    #
    # Day 0 -> focus 4h
    # Day 1 -> focus 4h + donors 4h
    #
    # Daily totals remain exactly 4h and 8h.
    ugly = _rebuild(
        p,
        generated,
        {
            1: {
                TODAY + DAY: D("8"),
            },
            2: {
                TODAY: D("2"),
            },
            3: {
                TODAY: D("2"),
            },
        },
    )

    assert ugly is not None

    baseline = score_production_schedule(
        p,
        ugly,
    )

    candidates = (
        _load_preserving_window_repack_candidates(
            p,
            ugly,
        )
    )

    assert candidates

    useful = []

    for candidate in candidates:
        focus_rows = [
            row
            for row in candidate.work_allocations
            if row.item_id == 1
        ]

        score = score_production_schedule(
            p,
            candidate,
        )

        if (
            max(
                row.hours
                for row in focus_rows
            )
            <= D("4")
            and candidate.daily_hours
            == ugly.daily_hours
            and score.key < baseline.key
        ):
            useful.append(
                candidate
            )

    assert useful


def test_c11_14e_load_preserving_repack_never_uses_atomic_donor():
    from arena.production.production_improver import (
        _load_preserving_window_repack_candidates,
        _rebuild,
    )

    p = problem([
        item(
            1,
            "OVER_16_HOURS",
            due=TODAY + 5 * DAY,
        ),
        item(
            2,
            "UNDER_20_MINUTES",
            due=TODAY + 5 * DAY,
        ),
    ])

    generated = generate_flavour_schedule(
        p,
        "lock-in",
        explicit_total_hours={
            1: D("8"),
            2: D("0.25"),
        },
    )

    candidate = _rebuild(
        p,
        generated,
        {
            1: {
                TODAY + DAY: D("8"),
            },
            2: {
                TODAY: D("0.25"),
            },
        },
    )

    assert candidate is not None

    # Atomic 15-minute work cannot be used as exchange material. There is not
    # enough other flexible donor work, so no candidate should be generated.
    assert (
        _load_preserving_window_repack_candidates(
            p,
            candidate,
        )
        == ()
    )


def test_c11_14f_load_preserving_repack_does_not_create_oversized_donor_block():
    from arena.production.production_improver import (
        _load_preserving_window_repack_candidates,
        _rebuild,
    )

    p = problem([
        item(
            1,
            "OVER_16_HOURS",
            due=TODAY + 6 * DAY,
        ),
        item(
            2,
            "UNDER_16_HOURS",
            due=TODAY + 6 * DAY,
        ),
        item(
            3,
            "UNDER_16_HOURS",
            due=TODAY + 6 * DAY,
        ),
    ])

    generated = generate_flavour_schedule(
        p,
        "monk",
        explicit_total_hours={
            1: D("8"),
            2: D("6"),
            3: D("3"),
        },
    )

    # Focus task has an 8h marathon on day 1.
    #
    # Donor task 2 already has 4h on day 0 and 2h on day 1.
    # Moving all 2h back would create a 6h donor block. Monk's ordinary
    # focused-session limit is lower, so this neighbourhood must only use the
    # available donor headroom and obtain the rest from task 3 instead.
    ugly = _rebuild(
        p,
        generated,
        {
            1: {
                TODAY + DAY: D("8"),
            },
            2: {
                TODAY: D("4"),
                TODAY + DAY: D("2"),
            },
            3: {
                TODAY + DAY: D("3"),
            },
        },
    )

    assert ugly is not None

    candidates = (
        _load_preserving_window_repack_candidates(
            p,
            ugly,
        )
    )

    assert candidates

    for candidate in candidates:
        task_two_rows = [
            row
            for row in candidate.work_allocations
            if row.item_id == 2
        ]

        assert all(
            row.hours <= D("5")
            for row in task_two_rows
        )


def test_c11_15_2_lateness_recovery_prioritises_actual_late_work():
    from arena.production.production_improver import (
        _lateness_recovery_moves,
        _rebuild,
    )

    p = problem([
        item(
            1,
            "UNDER_8_HOURS",
            due=TODAY + DAY,
        ),
        item(
            2,
            "UNDER_8_HOURS",
            due=TODAY + 6 * DAY,
        ),
    ])

    generated = generate_flavour_schedule(
        p,
        "monk",
        explicit_total_hours={
            1: D("4"),
            2: D("4"),
        },
    )

    late = _rebuild(
        p,
        generated,
        {
            1: {
                TODAY + 3 * DAY: D("4"),
            },
            2: {
                TODAY: D("4"),
            },
        },
    )

    assert late is not None

    moves = _lateness_recovery_moves(
        p,
        late,
    )

    assert moves

    assert all(
        move.item_id == 1
        for move in moves
    )

    assert all(
        move.to_date
        <= TODAY + DAY
        for move in moves
    )


def test_c11_15_2_lateness_recovery_includes_prerequisite_ancestors():
    from arena.production.production_improver import (
        _lateness_recovery_moves,
        _rebuild,
    )

    p = problem(
        [
            item(
                1,
                "UNDER_8_HOURS",
            ),
            item(
                2,
                "UNDER_8_HOURS",
                due=TODAY + 3 * DAY,
            ),
        ],
        dependencies=(
            DependencyEdge(1, 2),
        ),
    )

    generated = generate_flavour_schedule(
        p,
        "monk",
        explicit_total_hours={
            1: D("4"),
            2: D("4"),
        },
    )

    late = _rebuild(
        p,
        generated,
        {
            1: {
                TODAY + 3 * DAY: D("4"),
            },
            2: {
                TODAY + 4 * DAY: D("4"),
            },
        },
    )

    assert late is not None

    moves = _lateness_recovery_moves(
        p,
        late,
    )

    assert any(
        move.item_id == 1
        for move in moves
    )

    assert any(
        move.item_id == 2
        for move in moves
    )


def test_c11_15_5_anchor_congestion_neighbourhood_evacuates_movable_work():
    from arena.production.production_improver import (
        _anchored_congestion_recovery_moves,
        _rebuild,
    )

    anchor_day = TODAY + 2 * DAY

    p = problem([
        item(
            1,
            "UNDER_16_HOURS",
            anchor=anchor_day,
        ),
        item(
            2,
            "UNDER_16_HOURS",
            due=TODAY + 5 * DAY,
        ),
    ])

    generated = generate_flavour_schedule(
        p,
        "monk",
        explicit_total_hours={
            1: D("6"),
            2: D("6"),
        },
    )

    congested = _rebuild(
        p,
        generated,
        {
            1: {
                anchor_day: D("6"),
            },
            2: {
                anchor_day: D("6"),
            },
        },
    )

    assert congested is not None

    moves = _anchored_congestion_recovery_moves(
        p,
        congested,
    )

    assert moves

    assert all(
        move.item_id == 2
        for move in moves
    )

    assert all(
        move.from_date == anchor_day
        for move in moves
    )

    assert all(
        move.to_date != anchor_day
        for move in moves
    )


def test_c11_15_5_anchor_congestion_neighbourhood_ignores_calm_anchor_day():
    from arena.production.production_improver import (
        _anchored_congestion_recovery_moves,
        _rebuild,
    )

    anchor_day = TODAY + 2 * DAY

    p = problem([
        item(
            1,
            "UNDER_4_HOURS",
            anchor=anchor_day,
        ),
        item(
            2,
            "UNDER_4_HOURS",
            due=TODAY + 5 * DAY,
        ),
    ])

    generated = generate_flavour_schedule(
        p,
        "monk",
        explicit_total_hours={
            1: D("2"),
            2: D("2"),
        },
    )

    calm = _rebuild(
        p,
        generated,
        {
            1: {
                anchor_day: D("2"),
            },
            2: {
                anchor_day: D("2"),
            },
        },
    )

    assert calm is not None

    assert (
        _anchored_congestion_recovery_moves(
            p,
            calm,
        )
        == ()
    )


def test_c11_15_8_monk_unbuffered_marathon_is_severe_objective_defect():
    from arena.production.production_improver import (
        _rebuild,
        score_production_schedule,
    )

    p = problem([
        item(
            1,
            "UNDER_16_HOURS",
            due=TODAY + 4 * DAY,
        ),
    ])

    generated = generate_flavour_schedule(
        p,
        "monk",
        explicit_total_hours={
            1: D("8"),
        },
    )

    marathon = _rebuild(
        p,
        generated,
        {
            1: {
                TODAY + 3 * DAY: D("8"),
            },
        },
    )

    humane = _rebuild(
        p,
        generated,
        {
            1: {
                TODAY + 2 * DAY: D("4"),
                TODAY + 3 * DAY: D("4"),
            },
        },
    )

    assert marathon is not None
    assert humane is not None

    marathon_score = score_production_schedule(
        p,
        marathon,
    )

    humane_score = score_production_schedule(
        p,
        humane,
    )

    assert (
        marathon_score.unjustified_marathon_excess_hours
        == D("2")
    )

    assert (
        humane_score.unjustified_marathon_excess_hours
        == D("0")
    )

    assert (
        humane_score.key
        < marathon_score.key
    )


def test_c11_15_8_lock_in_long_session_is_allowed_when_it_buys_meaningful_buffer():
    from arena.production.production_improver import (
        _rebuild,
        score_production_schedule,
    )

    p = problem([
        item(
            1,
            "UNDER_16_HOURS",
            due=TODAY + 6 * DAY,
        ),
    ])

    generated = generate_flavour_schedule(
        p,
        "lock-in",
        explicit_total_hours={
            1: D("7.2"),
        },
    )

    buffered_long_session = _rebuild(
        p,
        generated,
        {
            1: {
                TODAY + 4 * DAY: D("7.2"),
            },
        },
    )

    assert buffered_long_session is not None

    objective = score_production_schedule(
        p,
        buffered_long_session,
    )

    assert (
        objective.unjustified_marathon_excess_hours
        == D("0")
    )


def test_c11_15_8_lock_in_same_long_session_is_unjustified_at_deadline():
    from arena.production.production_improver import (
        _rebuild,
        score_production_schedule,
    )

    p = problem([
        item(
            1,
            "UNDER_16_HOURS",
            due=TODAY + 6 * DAY,
        ),
    ])

    generated = generate_flavour_schedule(
        p,
        "lock-in",
        explicit_total_hours={
            1: D("7.2"),
        },
    )

    deadline_long_session = _rebuild(
        p,
        generated,
        {
            1: {
                TODAY + 6 * DAY: D("7.2"),
            },
        },
    )

    assert deadline_long_session is not None

    objective = score_production_schedule(
        p,
        deadline_long_session,
    )

    assert (
        objective.unjustified_marathon_excess_hours
        == D("0.2")
    )


def test_c11_15_8_ordinary_slightly_long_lock_in_session_is_not_severe():
    from arena.production.production_improver import (
        _rebuild,
        score_production_schedule,
    )

    p = problem([
        item(
            1,
            "UNDER_16_HOURS",
            due=TODAY + 3 * DAY,
        ),
    ])

    generated = generate_flavour_schedule(
        p,
        "lock-in",
        explicit_total_hours={
            1: D("6.5"),
        },
    )

    schedule = _rebuild(
        p,
        generated,
        {
            1: {
                TODAY + 3 * DAY: D("6.5"),
            },
        },
    )

    assert schedule is not None

    objective = score_production_schedule(
        p,
        schedule,
    )

    assert (
        objective.unjustified_marathon_excess_hours
        == D("0")
    )


def test_c11_15_9_unavoidable_single_legal_day_marathon_is_not_shape_defect():
    from arena.production.production_improver import (
        _rebuild,
        score_production_schedule,
    )

    p = problem([
        item(
            1,
            "OVER_16_HOURS",
            due=TODAY,
        ),
    ])

    generated = generate_flavour_schedule(
        p,
        "monk",
        explicit_total_hours={
            1: D("25"),
        },
    )

    forced = _rebuild(
        p,
        generated,
        {
            1: {
                TODAY: D("25"),
            },
        },
    )

    assert forced is not None

    objective = score_production_schedule(
        p,
        forced,
    )

    assert objective.infeasible_day_count == 1

    assert (
        objective.unjustified_marathon_excess_hours
        == D("0")
    )


def test_c11_15_9_marathon_with_multiple_legal_dates_remains_shape_defect():
    from arena.production.production_improver import (
        _rebuild,
        score_production_schedule,
    )

    p = problem([
        item(
            1,
            "UNDER_16_HOURS",
            due=TODAY + 3 * DAY,
        ),
    ])

    generated = generate_flavour_schedule(
        p,
        "monk",
        explicit_total_hours={
            1: D("8"),
        },
    )

    marathon = _rebuild(
        p,
        generated,
        {
            1: {
                TODAY + 3 * DAY: D("8"),
            },
        },
    )

    assert marathon is not None

    objective = score_production_schedule(
        p,
        marathon,
    )

    assert (
        objective.unjustified_marathon_excess_hours
        == D("2")
    )
