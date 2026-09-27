from dataclasses import replace
import math
import pytest
from arena.search import score_state, score_plan, objective_delta, apply_move, RelocateSession
from arena.scheduling.domain import SchedulePlan
from arena.scheduling.objectives import MovementCost, PowerCost
from .helpers import TODAY, DAY, item, problem, state, objective


def test_actual_completion_deadline():
    s = state(problem(item(duration_category='UNDER_8_HOURS', due_date=TODAY + 3 * DAY)), (1, 4))
    cfg = objective(risk=1, overload=0)
    assert score_state(s, cfg).deadline == 9
    n = apply_move(s, RelocateSession(1, 0, TODAY))
    assert objective_delta(s, n, cfg) == 0


def test_final_readiness_priority_and_timing_once():
    s = state(problem(item(1, priority_position=1), item(2, priority_position=2),
                      item(3, duration_category='UNDER_8_HOURS'), edges=((1, 3), (2, 3))), (2,), (2,), (4, 5))
    cost = score_state(s, objective(priority=1, timing=1, overload=0))
    assert cost.priority == 6 + 2 + 1
    assert cost.timing == 4 + 4 + 1
    n = apply_move(s, RelocateSession(3, 0, TODAY + 5 * DAY))
    assert score_state(n, objective(priority=1, overload=0)).priority == 10


@pytest.mark.parametrize('offset,expected', [(0, 0), (-2, 11), (2, 11)])
def test_movement_once_symmetric(offset, expected):
    s = state(problem(item(duration_category='UNDER_8_HOURS', existing_scheduled_date=TODAY + 3 * DAY)),
              (3 + offset, 7))
    cfg = replace(objective(overload=0), movement=MovementCost(3, PowerCost(2, 2)))
    assert score_state(s, cfg).movement == expected
    n = apply_move(s, RelocateSession(1, 1, TODAY + 8 * DAY))
    assert score_state(n, cfg).movement == expected


@pytest.mark.parametrize('allowed,exempt,expected', [(False, True, 5), (True, True, 0), (True, False, 5)])
def test_overload_cells_buckets(allowed, exempt, expected):
    p = problem(item(1, duration_category='OVER_16_HOURS'), item(2), item(3),
                allowed=frozenset({TODAY}) if allowed else frozenset())
    s = state(p, (0, 0, 0), (0,), (0,))
    cfg = objective(overload=1)
    cfg = replace(cfg, overload=replace(cfg.overload, exempt_allowed_dates=exempt))
    assert score_state(s, cfg).overload == expected  # 3 in capacity 1 => 4, other bucket => 1


@pytest.mark.parametrize('destination,sign', [(1, -1), (2, 0), (3, 1)])
def test_delta_and_total(destination, sign):
    s = state(problem(item()), (2,))
    n = state(s.problem, (destination,))
    cfg = objective(priority=1, timing=1, overload=0)
    delta = objective_delta(s, n, cfg)
    assert (delta > 0) - (delta < 0) == sign
    assert delta == score_state(n, cfg).total - score_state(s, cfg).total
    c = score_state(s, cfg)
    assert c.total == c.deadline + c.priority + c.overload + c.movement + c.timing
    assert score_plan(s.problem, s.to_plan(), cfg) == c == score_state(s, cfg)


def test_zero_missing_capacity_and_invalid_plan():
    s = state(replace(problem(item(priority_position=999)), capacity_by_duration={}), (3,))
    cfg = objective(overload=0)
    assert score_state(s, cfg).total == 0
    assert math.isfinite(score_state(s, cfg).total)
    with pytest.raises(ValueError, match='capacity'): score_state(s, objective())
    with pytest.raises(ValueError): score_plan(s.problem, SchedulePlan(()), cfg)
    with pytest.raises(TypeError): score_state(SchedulePlan(()), cfg)
    with pytest.raises(ValueError): objective_delta(s, state(problem(item()), (0,)), cfg)


def test_nonfinite_rejected():
    s = state(problem(item()), (3,))
    with pytest.raises(ValueError, match='finite'):
        score_state(s, replace(objective(overload=0), timing=PowerCost(1e308, 2)))
    with pytest.raises(ValueError, match='finite'):
        score_state(s, replace(objective(overload=0), timing=PowerCost(1, 10000)))
