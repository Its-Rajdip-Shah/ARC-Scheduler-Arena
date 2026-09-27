from dataclasses import FrozenInstanceError, replace
from datetime import date
from decimal import Decimal

import pytest

from arena.algorithms import (
    AggressiveEarlierGreedy,
    GreedyObjectiveConfig,
    HybridCostGreedy,
    PressureGreedy,
    StableRiskGreedy,
)
from arena.algorithms.greedy import candidate_cost, predicted_completion, pressure_key
from arena.scheduling.mechanics import ScheduleState, SessionAction, session_candidates
from arena.scheduling.objectives import (
    DeadlineRisk, MovementCost, OverloadCost, PowerCost, PriorityPostponement,
)
from arena.scheduling.tests.test_mechanics import TODAY, DAY, item, problem
from arena.scheduling.validation import validate_plan


def config(*, timing=0, movement=0, overload=10, risk=0, priority=0, horizon=5):
    return GreedyObjectiveConfig(
        DeadlineRisk(PowerCost(risk, 2), 2),
        PriorityPostponement(PowerCost(priority, 1), {1: 3, 2: 1}, 1),
        OverloadCost(PowerCost(overload, 2), True),
        MovementCost(0, PowerCost(movement, 2)), PowerCost(timing, 2), horizon,
    )


@pytest.mark.parametrize('horizon', [-1, 1.5, True])
def test_invalid_horizon(horizon):
    with pytest.raises(ValueError, match='nonnegative integer'):
        config(horizon=horizon)


def test_calendar_overflow():
    with pytest.raises(ValueError, match='calendar'):
        HybridCostGreedy(config()).solve(replace(problem(item()), today=date.max))


def test_completion_rollout_accounts_for_remaining_pieces_and_does_not_reserve():
    p = problem(item(duration_category='OVER_16_HOURS', due_date=TODAY + 2 * DAY))
    state = ScheduleState(p)
    candidate = session_candidates(state, 1, horizon=TODAY + 5 * DAY)[0]
    assert predicted_completion(state, candidate, TODAY + 5 * DAY) == TODAY + 2 * DAY
    assert candidate_cost(state, candidate, config(risk=1), TODAY + 5 * DAY).deadline == 4
    assert state.allocations == ()
    # C2 permits same-day overload if no capacity-respecting continuation exists.
    assert predicted_completion(state, candidate, TODAY) == TODAY


def test_start_costs_only_once_and_overload_is_convex_delta():
    p = problem(item(duration_category='UNDER_8_HOURS', priority_position=1,
                     existing_scheduled_date=TODAY + 3 * DAY), capacity=0)
    state = ScheduleState(p)
    candidate = session_candidates(state, 1, horizon=TODAY + DAY)[1]
    cfg = config(timing=2, movement=3, priority=4, overload=5)
    first = candidate_cost(state, candidate, cfg, TODAY + DAY)
    assert (first.priority, first.movement, first.timing, first.overload) == (12, 12, 2, 5)
    state = state.place(candidate.action)
    second = candidate_cost(state, session_candidates(state, 1, horizon=TODAY + DAY)[0], cfg, TODAY + DAY)
    assert (second.priority, second.movement, second.timing, second.overload) == (0, 0, 0, 15)
    assert first.total == 31


@pytest.mark.parametrize('allowed,expected', [(False, [0, 1]), (True, [0, 0])])
def test_capacity_and_allowed_overload(allowed, expected):
    p = problem(item(), item(2), allowed=frozenset({TODAY}) if allowed else frozenset())
    plan = HybridCostGreedy(config()).solve(p)
    assert [(a.scheduled_date - TODAY).days for a in plan.allocations] == expected
    assert validate_plan(p, plan).is_valid


def test_unavoidable_overload_and_exemption_configurable():
    p = problem(item(due_date=TODAY), item(2, due_date=TODAY), capacity=0)
    plan = HybridCostGreedy(config()).solve(p)
    assert len(plan.allocations) == 2 and validate_plan(p, plan).is_valid
    assert any(v.code == 'capacity_exceeded' for v in validate_plan(p, plan).soft_violations)
    allowed = replace(p, overload_dates=frozenset({TODAY}))
    state = ScheduleState(allowed)
    c = session_candidates(state, 1, horizon=TODAY)[0]
    cfg = config()
    assert candidate_cost(state, c, cfg, TODAY).overload == 0
    cfg = replace(cfg, overload=replace(cfg.overload, exempt_allowed_dates=False))
    assert candidate_cost(state, c, cfg, TODAY).overload == 10


def test_pressure_includes_remaining_sessions_and_priority():
    p = problem(item(1, due_date=TODAY + 4 * DAY),
                item(2, due_date=TODAY + DAY),
                item(3, duration_category='OVER_16_HOURS', due_date=TODAY + 2 * DAY))
    state = ScheduleState(p)
    keys = {i.item_id: pressure_key(state, i.item_id, session_candidates(state, i.item_id), TODAY + 5 * DAY)
            for i in p.items}
    assert keys[3] < keys[2] < keys[1]  # Not simply earliest due date.
    assert PressureGreedy(config()).solve(p).allocations[0].item_id == 3
    tied = problem(item(1, priority_position=None), item(2, priority_position=1))
    assert PressureGreedy(config()).solve(tied).allocations[0].item_id == 2


def test_regret_reconsiders_split_item_after_each_session():
    # A's anchor forces its first session. B has higher start-delay regret than
    # A's continuation and must get day 1 before A's remaining two pieces.
    p = problem(item(1, duration_category='OVER_16_HOURS', anchor_date=TODAY,
                     due_date=TODAY + 3 * DAY),
                item(2, duration_category='OVER_16_HOURS', release_date=TODAY + DAY,
                     due_date=TODAY + 2 * DAY))
    plan = HybridCostGreedy(config(timing=1)).solve(p)
    assert [a.item_id for a in plan.allocations][:2] == [1, 2]
    assert plan.allocations_for(2)[0].scheduled_date == TODAY + DAY
    assert validate_plan(p, plan).is_valid
    # Explicit counterfactual wholesale A construction consumes B's first slot.
    state = ScheduleState(p)
    for index, day in enumerate((TODAY, TODAY + DAY, TODAY + 2 * DAY)):
        state = state.place(SessionAction(1, index, day))
    candidates = session_candidates(state, 2, horizon=TODAY + 5 * DAY)
    assert all(c.excess_after > 0 for c in candidates)


def test_forced_regret_precedes_flexible_item_and_priority_breaks_ties():
    p = problem(item(1), item(2, due_date=TODAY))
    plan = HybridCostGreedy(config(timing=1)).solve(p)
    assert plan.allocations[0].item_id == 2
    p = problem(item(1, priority_position=2), item(2, priority_position=1))
    plan = HybridCostGreedy(config(priority=1)).solve(p)
    assert plan.allocations[0].item_id == 2
    assert validate_plan(p, plan).is_valid


def test_horizon_partial_and_blocked_diagnostics():
    p = problem(item(), item(2), item(3, release_date=TODAY + 2 * DAY),
                edges=((1, 2),))
    solver = HybridCostGreedy(config(horizon=0))
    plan = solver.solve(p)
    assert [a.item_id for a in plan.allocations] == [1]
    assert plan.conflicts == ('2:no_candidate_within_horizon', '3:no_candidate_within_horizon')
    assert dict(plan.diagnostics)['status'] == 'partial_no_legal_progress'
    assert repr(plan) == repr(solver.solve(p))
    blocked = problem(item(1, anchor_date=TODAY, release_date=TODAY + DAY), item(2), edges=((1, 2),))
    assert solver.solve(blocked).conflicts == ('1:anchor_before_readiness', '2:blocked_prerequisites:1')


def test_zero_weights_and_immutable_inputs():
    zero = PowerCost(0, 10000)
    cfg = GreedyObjectiveConfig(DeadlineRisk(zero, 0), PriorityPostponement(zero, {}, 0),
                               OverloadCost(zero, False), MovementCost(0, zero), zero, 2)
    p = problem(item(priority_position=999, existing_scheduled_date=date.min))
    before = repr(p), repr(cfg)
    assert HybridCostGreedy(cfg).solve(p).allocations[0].scheduled_date == TODAY
    assert (repr(p), repr(cfg)) == before
    with pytest.raises(FrozenInstanceError):
        cfg.horizon_days = 3
    with pytest.raises(TypeError):
        cfg.priority.multipliers[999] = 1


def test_empty_zero_work_and_calendar_exhaustion():
    assert HybridCostGreedy(config()).solve(problem()).allocations == ()
    assert HybridCostGreedy(config()).solve(problem(item(remaining_fraction=Decimal(0)))).conflicts == ()
    p = replace(problem(item(), item(2), edges=((1, 2),)), today=date.max)
    assert HybridCostGreedy(config(horizon=0)).solve(p).conflicts == ('2:readiness_exceeds_calendar',)


@pytest.mark.parametrize(
    "constructor_cls",
    (
        PressureGreedy,
        AggressiveEarlierGreedy,
        StableRiskGreedy,
        HybridCostGreedy,
    ),
)
def test_constructor_preserves_downstream_anchor_feasibility(
    constructor_cls,
):
    # Item 2 is fixed tomorrow. Because dependencies require the dependent to
    # start strictly after prerequisite completion, all three sessions of item 1
    # must finish today. A greedy constructor must not spend tomorrow on the
    # prerequisite and thereby destroy a feasible anchored continuation.
    p = problem(
        item(
            1,
            duration_category="OVER_16_HOURS",
        ),
        item(
            2,
            anchor_date=TODAY + DAY,
            due_date=TODAY + DAY,
        ),
        edges=((1, 2),),
    )

    plan = constructor_cls(config(horizon=5)).solve(p)

    assert plan.conflicts == ()
    assert validate_plan(p, plan).is_valid

    prerequisite = plan.allocations_for(1)
    dependent = plan.allocations_for(2)

    assert len(prerequisite) == 3
    assert {
        allocation.scheduled_date
        for allocation in prerequisite
    } == {TODAY}

    assert {
        allocation.scheduled_date
        for allocation in dependent
    } == {TODAY + DAY}


@pytest.mark.parametrize(
    "constructor_cls",
    (
        PressureGreedy,
        AggressiveEarlierGreedy,
        StableRiskGreedy,
        HybridCostGreedy,
    ),
)
def test_constructor_propagates_anchor_feasibility_through_dependency_chain(
    constructor_cls,
):
    # 1 -> 2 -> 3, with 3 anchored two days from today.
    # Therefore item 2 must complete tomorrow and item 1 must complete today.
    p = problem(
        item(
            1,
            duration_category="UNDER_8_HOURS",
        ),
        item(
            2,
            duration_category="UNDER_8_HOURS",
        ),
        item(
            3,
            anchor_date=TODAY + 2 * DAY,
        ),
        edges=((1, 2), (2, 3)),
    )

    plan = constructor_cls(config(horizon=5)).solve(p)

    assert plan.conflicts == ()
    assert validate_plan(p, plan).is_valid

    assert {
        allocation.scheduled_date
        for allocation in plan.allocations_for(1)
    } == {TODAY}

    assert {
        allocation.scheduled_date
        for allocation in plan.allocations_for(2)
    } == {TODAY + DAY}

    assert {
        allocation.scheduled_date
        for allocation in plan.allocations_for(3)
    } == {TODAY + 2 * DAY}
