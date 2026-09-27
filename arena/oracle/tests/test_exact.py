from dataclasses import FrozenInstanceError, replace
from datetime import date
from decimal import Decimal
import os
import subprocess
import sys

import pytest

from arena.oracle import (
    ExactOracle, ExactOracleConfig, ExactOracleResult, OptimalityGap, gap_to_optimum,
)
from arena.scheduling.domain import SchedulePlan
from arena.scheduling.objectives import DeadlineRisk, PowerCost
from arena.scheduling.validation import validate_plan
from arena.search import PlanObjective, SearchState, score_plan, score_state
from arena.search.tests.helpers import DAY, TODAY, item, objective, problem, state


def solve(p, *, horizon=1, sessions=10, nodes=10000, cost=None):
    return ExactOracle(ExactOracleConfig(
        objective(timing=1) if cost is None else cost, horizon, sessions, nodes,
    )).solve(p)


def dates(result):
    return tuple((p.scheduled_date - result.problem.today).days
                 for p in result.state.placements)


def test_atomic_hand_table_and_input_order():
    # Capacity 1, timing weight 1, overload weight 10, both quadratic.
    # Dates (0,0), (0,1), (1,0), (1,1) cost 10, 1, 1, 12.
    p = problem(item(), item(2))
    expected = {(0, 0): 10, (0, 1): 1, (1, 0): 1, (1, 1): 12}
    for (a, b), total in expected.items():
        assert score_state(state(p, (a,), (b,)), objective(timing=1)).total == total
    result = solve(p)
    assert isinstance(result, ExactOracleResult)
    assert result.status == 'optimal'
    assert dates(result) == (0, 1)
    assert result.objective.total == result.proven_lower_bound == 1
    assert (result.nodes_visited, result.leaves_evaluated) == (7, 4)
    reordered = solve(replace(p, items=tuple(reversed(p.items))))
    assert reordered.state.placements == result.state.placements
    assert reordered.objective == result.objective


@pytest.mark.parametrize('overload,winner,total', [(0, (0, 0), 0), (10, (0, 1), 0)])
def test_split_hand_enumeration(overload, winner, total):
    p = problem(item(duration_category='UNDER_8_HOURS'))
    cost = objective(timing=1, overload=overload)
    # All six nondecreasing pairs on three days. Timing counts START once.
    hand_costs = {(0, 0): overload, (0, 1): 0, (0, 2): 0,
                  (1, 1): 1 + overload, (1, 2): 1, (2, 2): 4 + overload}
    for pair, expected in hand_costs.items():
        assert score_state(state(p, pair), cost).total == expected
    result = solve(p, horizon=2, sessions=2, cost=cost)
    assert dates(result) == winner
    assert result.objective.total == total
    assert result.leaves_evaluated == 6
    assert result.nodes_visited == 10


def test_chain_fanin_zero_work_and_reordering():
    p = problem(item(), item(2, duration_category='UNDER_8_HOURS'), item(3),
                item(4), item(5, remaining_fraction=Decimal(0),
                              release_date=TODAY + 20 * DAY),
                edges=((1, 3), (2, 3), (3, 4), (5, 1)))
    result = solve(p, horizon=2, cost=objective(overload=0))
    assert result.status == 'optimal'
    assert dates(result) == (0, 0, 0, 1, 2)
    assert result.state.start(3) > result.state.completion(1)
    assert result.state.start(3) > result.state.completion(2)
    assert result.state.start(4) > result.state.completion(3)
    reordered = solve(replace(p, items=p.items[::-1], dependencies=p.dependencies[::-1]),
                      horizon=2, cost=objective(overload=0))
    assert reordered.state.placements == result.state.placements
    assert (reordered.nodes_visited, reordered.leaves_evaluated) == (
        result.nodes_visited, result.leaves_evaluated)
    assert solve(p, horizon=1).status == 'infeasible'


def test_canonical_tie_key_can_replace_first_optimum_in_traversal():
    p = problem(item(), item(2), item(3), item(4, remaining_fraction=Decimal(0)),
                edges=((3, 1), (4, 1)))
    # Three distinct days avoid overload. In canonical item order the only
    # zero-cost triples are (2,0,1), (2,1,0), (1,2,0). DFS finds (2,0,1)
    # first because it decides item 2 before item 3 before item 1.
    result = solve(p, horizon=2, cost=objective())
    assert result.objective.total == 0
    assert dates(result) == (1, 2, 0)
    reordered = solve(replace(p, items=p.items[::-1], dependencies=p.dependencies[::-1]),
                      horizon=2, cost=objective())
    assert reordered.state.placements == result.state.placements


def test_release_anchor_only_first_session_and_size_limit():
    p = problem(item(duration_category='UNDER_8_HOURS',
                     release_date=TODAY + DAY, anchor_date=TODAY + DAY))
    result = solve(p, horizon=2, sessions=2)
    assert dates(result) == (1, 2)
    assert result.leaves_evaluated == 2  # (1,1) and (1,2); anchor fixes only start.
    with pytest.raises(ValueError, match='^Instance exceeds max_sessions$'):
        solve(p, sessions=1, nodes=0)
    assert solve(p, horizon=0).status == 'infeasible'


@pytest.mark.parametrize('p', [
    problem(item(release_date=TODAY + DAY, anchor_date=TODAY)),
    problem(item(anchor_date=TODAY - DAY)),
    problem(item(anchor_date=TODAY + 2 * DAY)),
    problem(item(release_date=TODAY + 2 * DAY)),
    problem(item(anchor_date=TODAY), item(2, anchor_date=TODAY), edges=((1, 2),)),
])
def test_hard_conflicts_are_horizon_infeasible(p):
    result = solve(p)
    assert result.status == 'infeasible'
    assert result.state is result.plan is result.objective is result.proven_lower_bound is None
    assert result.leaves_evaluated == 0


def test_due_date_does_not_bound_true_movement_optimum():
    p = problem(item(due_date=TODAY, existing_scheduled_date=TODAY + 2 * DAY))
    cost = replace(objective(movement=10), deadline=DeadlineRisk(PowerCost(1, 2), 0))
    # Day d costs d^2 + 10*(2-d)^2: 40, 11, 4. On-time day 0 is legal.
    assert [score_state(state(p, (d,)), cost).total for d in range(3)] == [40, 11, 4]
    result = solve(p, horizon=2, cost=cost)
    assert result.status == 'optimal'
    assert dates(result) == (2,)
    assert result.objective.total == 4
    assert result.leaves_evaluated == 3
    assert {v.code for v in validate_plan(p, result.plan).soft_violations} == {'after_deadline'}


@pytest.mark.parametrize('capacity,allowed,exempt,expected', [
    (1, False, True, 10), (0, False, True, 40),
    (0, True, True, 0), (0, True, False, 40),
])
def test_soft_overload_zero_capacity_and_allowed_dates(capacity, allowed, exempt, expected):
    p = problem(item(), item(2), capacity=capacity,
                allowed=frozenset({TODAY}) if allowed else frozenset())
    cost = objective()
    cost = replace(cost, overload=replace(cost.overload, exempt_allowed_dates=exempt))
    result = solve(p, horizon=0, cost=cost)
    assert result.status == 'optimal'
    assert dates(result) == (0, 0)
    assert result.objective.total == result.objective.overload == expected
    validation = validate_plan(p, result.plan)
    assert not validation.violations and not validation.infeasibilities
    assert bool(validation.soft_violations) is (not allowed)


@pytest.mark.parametrize('budget,status,leaves,incumbent,bound', [
    (0, 'node_limit', 0, None, None),
    (1, 'node_limit', 0, None, None),
    (2, 'node_limit', 0, None, None),
    (3, 'node_limit', 1, 10, None),
    (4, 'node_limit', 2, 1, None),
    (6, 'node_limit', 3, 1, None),
    (7, 'optimal', 4, 1, 1),
])
def test_precise_node_budgets(budget, status, leaves, incumbent, bound):
    result = solve(problem(item(), item(2)), nodes=budget)
    assert result.status == status
    assert result.nodes_visited == budget
    assert result.leaves_evaluated == leaves
    assert (None if result.objective is None else result.objective.total) == incumbent
    assert (result.state is None) is (incumbent is None)
    assert (result.plan is None) is (incumbent is None)
    assert result.proven_lower_bound == bound
    assert result.elapsed_seconds >= 0


def test_exact_budget_infeasible_and_empty_root():
    impossible = problem(item(release_date=TODAY + DAY))
    result = solve(impossible, horizon=0, nodes=1)
    assert (result.status, result.nodes_visited, result.leaves_evaluated) == ('infeasible', 1, 0)
    for p in (problem(), problem(item(remaining_fraction=Decimal(0)))):
        limited = solve(p, sessions=0, nodes=0)
        assert limited.status == 'node_limit' and limited.nodes_visited == 0
        result = solve(p, sessions=0, nodes=1)
        assert (result.status, result.nodes_visited, result.leaves_evaluated) == ('optimal', 1, 1)
        assert result.state.placements == ()
        assert result.plan == SchedulePlan(())
        assert result.objective.total == result.proven_lower_bound == 0


@pytest.mark.parametrize('field', ['horizon_days', 'max_sessions', 'max_nodes'])
@pytest.mark.parametrize('value', [True, False, 1.0, -1])
def test_invalid_limits(field, value):
    kwargs = dict(objective=objective(), horizon_days=1, max_sessions=2, max_nodes=7)
    kwargs[field] = value
    with pytest.raises(ValueError, match='nonnegative integer'):
        ExactOracleConfig(**kwargs)


def test_invalid_objective_and_frozen_api():
    with pytest.raises(ValueError, match='PlanObjectiveConfig'):
        ExactOracleConfig(None, 0, 0, 0)
    cfg = ExactOracleConfig(objective(), 1, 2, 7)
    solver = ExactOracle(cfg)
    result = solver.solve(problem(item(), item(2)))
    gap = gap_to_optimum(result, result.plan)
    assert isinstance(gap, OptimalityGap)
    for obj, field, value in ((cfg, 'max_nodes', 8), (solver, 'config', cfg),
                              (result, 'status', 'infeasible'), (gap, 'absolute', 99)):
        with pytest.raises(FrozenInstanceError):
            setattr(obj, field, value)
        assert not hasattr(obj, '__dict__')
    again = solver.solve(result.problem)
    assert replace(again, elapsed_seconds=result.elapsed_seconds) == result


def test_calendar_overflow_and_last_day_enumeration():
    p = replace(problem(item()), today=date.max)
    with pytest.raises(ValueError, match='calendar'):
        solve(p, horizon=1, nodes=0)
    with pytest.raises(ValueError, match='calendar'):
        solve(problem(), horizon=10**30)
    assert solve(p, horizon=0).state.start(1) == date.max
    chain = replace(problem(item(), item(2), edges=((1, 2),)), today=date.max)
    result = solve(chain, horizon=0)
    assert (result.status, result.nodes_visited, result.leaves_evaluated) == ('infeasible', 2, 0)
    almost = replace(chain, today=date.max - DAY)
    result = solve(almost, horizon=1)
    assert dates(result) == (0, 1)
    assert result.leaves_evaluated == 1


def test_scoring_errors_propagate_and_short_circuits_remain():
    p = replace(problem(item()), capacity_by_duration={})
    with pytest.raises(ValueError, match='undefined capacity'):
        solve(p)
    assert solve(p, cost=objective(overload=0)).status == 'optimal'
    assert solve(replace(p, overload_dates=frozenset({TODAY})), horizon=0).status == 'optimal'
    cost = objective(timing=1)
    cost = replace(cost, timing=PowerCost(1, 10000))
    with pytest.raises(ValueError, match='finite range'):
        solve(problem(item()), horizon=2, cost=cost)


def test_best_plan_validation_roundtrip_and_positive_gap():
    p = problem(item(), item(2))
    result = solve(p)
    validation = validate_plan(p, result.plan)
    assert not validation.violations and not validation.infeasibilities
    assert SearchState.from_plan(p, result.plan) == result.state
    assert score_plan(p, result.plan, result.config.objective) == result.objective
    heuristic = state(p, (1,), (1,)).to_plan()
    gap = gap_to_optimum(result, heuristic)
    assert gap.heuristic_objective.total == 12
    assert gap.absolute == 11 and gap.relative == 11
    assert gap_to_optimum(result, result.plan).absolute == 0


def test_zero_optimum_gaps():
    p = problem(item())
    result = solve(p)
    assert result.objective.total == 0
    same = gap_to_optimum(result, result.plan)
    assert (same.absolute, same.relative) == (0, 0.0)
    worse = gap_to_optimum(result, state(p, (1,)).to_plan())
    assert (worse.absolute, worse.relative) == (1, None)


def test_gap_rejects_invalid_and_out_of_horizon_plans():
    p = problem(item())
    result = solve(p)
    with pytest.raises(ValueError, match='Invalid plan'):
        gap_to_optimum(result, SchedulePlan(()))
    with pytest.raises(ValueError, match='Invalid plan'):
        gap_to_optimum(result, SchedulePlan((replace(result.plan.allocations[0],
                                                   scheduled_date=TODAY - DAY),)))
    with pytest.raises(ValueError, match='horizon'):
        gap_to_optimum(result, state(p, (2,)).to_plan())
    # A forged claimed optimum must not silently clamp a negative gap.
    forged = replace(result, objective=PlanObjective(0, 0, 0, 0, 2))
    with pytest.raises(ValueError, match='below the claimed optimum'):
        gap_to_optimum(forged, result.plan)


def test_gap_rejects_every_unproven_result_and_missing_proof_fields():
    p = problem(item(), item(2))
    valid_plan = state(p, (0,), (1,)).to_plan()
    for result in (solve(p, nodes=0), solve(p, nodes=3),
                   solve(problem(item(release_date=TODAY + 2 * DAY)))):
        with pytest.raises(ValueError, match='proven optimal'):
            gap_to_optimum(result, valid_plan)
    result = solve(p)
    for incomplete in (replace(result, state=None), replace(result, objective=None)):
        with pytest.raises(ValueError, match='proven optimal'):
            gap_to_optimum(incomplete, valid_plan)


def test_import_has_no_constructor_evaluator_or_django_dependency():
    env = dict(os.environ)
    env.pop('DJANGO_SETTINGS_MODULE', None)
    subprocess.run([sys.executable, '-c',
                    "import sys; import arena.oracle; "
                    "assert not any(k == 'django' or k.startswith('django.') for k in sys.modules); "
                    "assert 'arena.algorithms.greedy' not in sys.modules; "
                    "assert 'arena.evaluation.performance' not in sys.modules"],
                   env=env, check=True)
