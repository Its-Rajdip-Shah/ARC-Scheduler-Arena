"""Behavioural tests of HC using real C4.1 moves and whole-plan costs."""
from dataclasses import FrozenInstanceError, replace
import os
import subprocess
import sys
from unittest.mock import patch

import pytest

from arena.algorithms import HybridCostGreedy, PressureGreedy
from arena.algorithms.tests.test_constructor_zoo import mini_corpus
from arena.algorithms.tests.test_greedy import config as greedy_config
from arena.scheduling.domain import SchedulePlan
from arena.scheduling.validation import validate_plan
from arena.search import (
    HillClimber, HillClimbConfig, HillClimbResult, ImprovementStrategy,
    NeighbourhoodConfig, RelocateSession, SwapSessions, SearchState,
    all_moves, apply_move, score_state,
)
from arena.search import hill_climbing as hc
from .helpers import TODAY, DAY, item, problem, state, objective


STRATEGIES = tuple(ImprovementStrategy)


def settings(strategy=ImprovementStrategy.FIRST, **limits):
    return HillClimbConfig(objective(timing=1, overload=0), NeighbourhoodConfig(4), strategy, **limits)


def divergence_case(strategy, **limits):
    initial = state(problem(item(existing_scheduled_date=TODAY + 4 * DAY)), (4,))
    cfg = replace(settings(strategy, **limits), objective=objective(timing=1, movement=1, overload=0))
    return initial, cfg


def assert_history(result, cfg):
    assert isinstance(result, HillClimbResult)
    assert result.accepted_moves <= result.iterations
    assert len(result.objective_history) == result.accepted_moves + 1
    assert len(result.accepted_moves_history) == result.accepted_moves
    assert all(b < a for a, b in zip(result.objective_history, result.objective_history[1:]))
    assert result.improved == (result.final_objective.total < result.initial_objective.total)
    assert result.total_improvement == result.initial_objective.total - result.final_objective.total
    cursor = result.initial_state
    assert score_state(cursor, cfg.objective) == result.initial_objective
    for move, total in zip(result.accepted_moves_history, result.objective_history[1:]):
        assert move in all_moves(cursor, cfg.neighbourhood)
        cursor = apply_move(cursor, move)
        validation = validate_plan(cursor.problem, cursor.to_plan())
        assert validation.violations == validation.infeasibilities == ()
        assert score_state(cursor, cfg.objective).total == total
    assert cursor == result.final_state
    assert score_state(cursor, cfg.objective) == result.final_objective


@pytest.mark.parametrize('field', ['max_iterations', 'max_evaluations'])
@pytest.mark.parametrize('value', [-1, True, False, 1.5, '1'])
def test_invalid_limits(field, value):
    with pytest.raises(ValueError, match=field): settings(**{field: value})


@pytest.mark.parametrize('value', [None, 0, 1])
def test_valid_limits(value):
    cfg = settings(max_iterations=value, max_evaluations=value)
    assert cfg.max_iterations == cfg.max_evaluations == value


@pytest.mark.parametrize('strategy', ['first', 'best', None, 0])
def test_invalid_strategy(strategy):
    with pytest.raises(ValueError, match='ImprovementStrategy'): settings(strategy)


@pytest.mark.parametrize('limits,reason', [
    ({'max_iterations': 0}, 'iteration_budget'),
    ({'max_evaluations': 0}, 'evaluation_budget'),
    ({'max_iterations': 0, 'max_evaluations': 0}, 'iteration_budget'),
])
def test_zero_budget_scores_initial_only(limits, reason):
    initial = state(problem(item()), (3,))
    cfg = settings(**limits)
    with patch.object(hc, 'score_state', wraps=score_state) as scorer, \
         patch.object(hc, 'all_moves', wraps=all_moves) as enumerate_moves:
        result = HillClimber(cfg).improve_state(initial)
    assert scorer.call_count == 1
    enumerate_moves.assert_not_called()
    assert result.initial_state is result.final_state is initial
    assert (result.iterations, result.evaluations, result.accepted_moves) == (0, 0, 0)
    assert result.termination_reason == reason
    assert_history(result, cfg)


@pytest.mark.parametrize('strategy', STRATEGIES)
@pytest.mark.parametrize('empty', [False, True])
def test_local_optimum_and_empty_neighbourhood(strategy, empty):
    p = problem(item(anchor_date=TODAY if empty else None))
    initial = state(p, (0,))
    cfg = settings(strategy)
    result = HillClimber(cfg).improve_state(initial)
    assert result == HillClimber(cfg).improve_state(initial)
    assert result.final_state is initial
    assert result.termination_reason == 'local_optimum'
    assert result.iterations == 1
    assert result.evaluations == (0 if empty else 4)
    assert_history(result, cfg)


def test_first_best_divergence_and_no_duplicate_scoring():
    results = []
    for strategy, day, evaluations in [(ImprovementStrategy.FIRST, 1, 2),
                                        (ImprovementStrategy.BEST, 2, 4)]:
        initial, cfg = divergence_case(strategy, max_iterations=1)
        # Date 0 ties the source; date 1 improves, but date 2 is better.
        with patch.object(hc, 'score_state', wraps=score_state) as scorer, \
             patch.object(hc, 'all_moves', wraps=all_moves) as enumerate_moves:
            result = HillClimber(cfg).improve_state(initial)
        assert result.accepted_moves_history == (RelocateSession(1, 0, TODAY + day * DAY),)
        assert result.evaluations == evaluations
        assert scorer.call_count == evaluations + 1
        assert enumerate_moves.call_count == 1
        assert result.termination_reason == 'iteration_budget'
        assert result == HillClimber(cfg).improve_state(initial)
        assert_history(result, cfg)
        results.append(result)
    assert results[0].final_objective.total == 10
    assert results[1].final_objective.total == 8


def test_best_equal_total_retains_first_despite_components():
    initial = state(problem(item(existing_scheduled_date=TODAY + 3 * DAY)), (3,))
    cfg = replace(settings(ImprovementStrategy.BEST, max_iterations=1),
                  objective=objective(timing=1, movement=1, overload=0),
                  neighbourhood=NeighbourhoodConfig(3))
    result = HillClimber(cfg).improve_state(initial)
    assert result.accepted_moves_history == (RelocateSession(1, 0, TODAY + DAY),)
    assert result.final_objective.total == 5
    assert result.evaluations == 3
    # Date 2 ties the total but has less movement: no component tie breaker.
    alternative = score_state(state(initial.problem, (2,)), cfg.objective)
    assert alternative.total == 5
    assert alternative.movement < result.final_objective.movement


@pytest.mark.parametrize('budget', [1, 2, 3])
def test_best_truncated_scan_discards_even_improving_prefix(budget):
    initial, cfg = divergence_case(ImprovementStrategy.BEST, max_evaluations=budget)
    result = HillClimber(cfg).improve_state(initial)
    assert result.final_state is initial
    assert result.evaluations == budget
    assert result.iterations == 1
    assert result.accepted_moves == 0
    assert result.termination_reason == 'evaluation_budget'
    assert_history(result, cfg)


def test_best_exact_boundary_commits_full_scan():
    initial, cfg = divergence_case(ImprovementStrategy.BEST, max_evaluations=4)
    result = HillClimber(cfg).improve_state(initial)
    assert result.objective_history == (16, 8)
    assert result.evaluations == 4 and result.iterations == 1
    assert result.termination_reason == 'evaluation_budget'
    assert_history(result, cfg)


@pytest.mark.parametrize('strategy', STRATEGIES)
def test_full_nonimproving_scan_at_exact_budget_is_local_optimum(strategy):
    initial, cfg = divergence_case(strategy, max_evaluations=4, max_iterations=1)
    initial = state(initial.problem, (2,))
    result = HillClimber(cfg).improve_state(initial)
    assert result.termination_reason == 'local_optimum'
    assert result.evaluations == 4
    assert result.final_state is initial


@pytest.mark.parametrize('budget,accepted', [(1, 0), (2, 1), (3, 1)])
def test_first_evaluation_budget(budget, accepted):
    initial, cfg = divergence_case(ImprovementStrategy.FIRST, max_evaluations=budget)
    result = HillClimber(cfg).improve_state(initial)
    assert result.evaluations == budget
    assert result.accepted_moves == accepted
    assert result.termination_reason == 'evaluation_budget'
    assert_history(result, cfg)


@pytest.mark.parametrize('strategy', STRATEGIES)
def test_multiple_iterations_regenerate_and_reach_local_optimum(strategy):
    initial = state(problem(item(1), item(2)), (2,), (2,))
    cfg = settings(strategy)
    with patch.object(hc, 'all_moves', wraps=all_moves) as enumerate_moves, \
         patch.object(hc, 'score_state', wraps=score_state) as scorer:
        result = HillClimber(cfg).improve_state(initial)
    assert result.objective_history == (8, 4, 0)
    assert result.accepted_moves == 2 and result.iterations == 3
    assert enumerate_moves.call_count == 3
    assert scorer.call_count == result.evaluations + 1
    scanned_states = [call.args[0] for call in enumerate_moves.call_args_list]
    assert scanned_states[0] is initial
    assert scanned_states[-1] is result.final_state
    assert len(set(scanned_states)) == 3
    assert result.termination_reason == 'local_optimum'
    assert all(score_state(apply_move(result.final_state, m), cfg.objective).total >= result.final_objective.total
               for m in all_moves(result.final_state, cfg.neighbourhood))
    assert_history(result, cfg)


@pytest.mark.parametrize('strategy', STRATEGIES)
def test_iteration_budget_no_speculative_scan(strategy):
    initial = state(problem(item(1), item(2)), (2,), (2,))
    cfg = settings(strategy, max_iterations=1)
    with patch.object(hc, 'all_moves', wraps=all_moves) as enumerate_moves:
        result = HillClimber(cfg).improve_state(initial)
    assert enumerate_moves.call_count == 1
    assert result.iterations == result.accepted_moves == 1
    assert result.termination_reason == 'iteration_budget'
    assert result.objective_history == (8, 4)


def test_best_truncation_after_earlier_acceptance_preserves_current():
    initial = state(problem(item(1), item(2)), (2,), (2,))
    size = len(all_moves(initial, NeighbourhoodConfig(4)))
    cfg = settings(ImprovementStrategy.BEST, max_evaluations=size + 1)
    result = HillClimber(cfg).improve_state(initial)
    assert result.iterations == 2 and result.evaluations == size + 1
    assert result.objective_history == (8, 4)
    assert result.termination_reason == 'evaluation_budget'
    assert_history(result, cfg)


def test_frozen_objects_input_identity_and_immutability():
    initial, cfg = divergence_case(ImprovementStrategy.FIRST)
    before = repr((initial, initial.problem, initial.placements, cfg))
    climber = HillClimber(cfg)
    result = climber.improve_state(initial)
    assert result.initial_state is initial
    assert repr((initial, initial.problem, initial.placements, cfg)) == before
    for obj, field, value in [(cfg, 'strategy', ImprovementStrategy.BEST),
                              (climber, 'config', cfg), (result, 'iterations', 99)]:
        assert not hasattr(obj, '__dict__')
        with pytest.raises(FrozenInstanceError): setattr(obj, field, value)


@pytest.mark.parametrize('strategy', STRATEGIES)
def test_constructor_local_decision_improved_by_swap(strategy):
    # Pressure forces the tight-window low-priority item first. The high-priority
    # item then avoids overload by taking day 1. Whole-plan swap costs less,
    # since lateness is soft and deadline weight is explicitly zero here.
    p = problem(item(1, priority_position=2, due_date=TODAY),
                item(2, priority_position=1, due_date=TODAY + 2 * DAY))
    plan = PressureGreedy(greedy_config(priority=1, overload=10, horizon=2)).solve(p)
    before = repr((p, plan))
    cfg = HillClimbConfig(objective(priority=1, overload=10), NeighbourhoodConfig(2), strategy)
    result = HillClimber(cfg).improve_plan(p, plan)
    assert result.initial_state.start(1) == TODAY
    assert result.initial_state.start(2) == TODAY + DAY
    assert result.objective_history == (3, 1)
    assert result.accepted_moves_history == (SwapSessions(1, 0, 2, 0),)
    assert result.improved and result.total_improvement == 2
    assert result.termination_reason == 'local_optimum'
    assert repr((p, plan)) == before
    assert_history(result, cfg)
    assert validate_plan(p, result.final_state.to_plan()).soft_violations


@pytest.mark.parametrize('constructor', [PressureGreedy, HybridCostGreedy])
@pytest.mark.parametrize('strategy', STRATEGIES)
def test_constructor_roundtrip_and_hard_constraints(constructor, strategy):
    cfg = settings(strategy)
    for p in mini_corpus():
        plan = constructor(greedy_config(timing=1, movement=2, risk=1)).solve(p)
        before = repr((p, plan))
        result = HillClimber(cfg).improve_plan(p, plan)
        assert result.initial_state == SearchState.from_plan(p, plan)
        assert repr((p, plan)) == before
        assert_history(result, cfg)
        validation = validate_plan(p, result.final_state.to_plan())
        assert validation.violations == validation.infeasibilities == ()


def test_constructor_already_optimal_and_invalid_plan_rejected():
    p = problem(item())
    plan = HybridCostGreedy(greedy_config(timing=1)).solve(p)
    climber = HillClimber(settings())
    result = climber.improve_plan(p, plan)
    assert result.final_state == result.initial_state
    assert not result.improved and result.total_improvement == 0
    assert result.termination_reason == 'local_optimum'
    with pytest.raises(ValueError): climber.improve_plan(p, SchedulePlan(()))


def test_public_import_is_django_evaluator_and_constructor_free():
    env = dict(os.environ)
    env.pop('DJANGO_SETTINGS_MODULE', None)
    subprocess.run([sys.executable, '-c',
        'from arena.search import HillClimber, HillClimbConfig, HillClimbResult, ImprovementStrategy; '
        'import sys; assert not any(k == "django" or k.startswith("django.") for k in sys.modules); '
        'assert "arena.evaluation.performance" not in sys.modules; '
        'assert "arena.algorithms.greedy" not in sys.modules'], check=True, env=env)


@pytest.mark.parametrize('strategy', STRATEGIES)
def test_strict_comparison_without_epsilon_or_sideways_moves(strategy):
    initial = state(problem(item()), (1,))
    cfg = replace(settings(strategy), objective=objective(timing=1e-20, overload=0))
    result = HillClimber(cfg).improve_state(initial)
    assert result.improved
    assert result.objective_history == (1e-20, 0)
    tied = HillClimber(replace(cfg, objective=objective(overload=0))).improve_state(initial)
    assert tied.final_state is initial and tied.accepted_moves == 0
    assert tied.termination_reason == 'local_optimum'


def test_accepted_objective_is_reused_without_rescoring():
    initial, cfg = divergence_case(ImprovementStrategy.BEST, max_iterations=1)
    scored = []
    def recording_score(s, objective_config):
        result = score_state(s, objective_config)
        scored.append((s, result))
        return result
    with patch.object(hc, 'score_state', side_effect=recording_score):
        result = HillClimber(cfg).improve_state(initial)
    assert result.initial_objective is scored[0][1]
    accepted_scores = [cost for s, cost in scored if s is result.final_state]
    assert len(accepted_scores) == 1
    assert result.final_objective is accepted_scores[0]


def test_simultaneous_positive_limits_prefer_iteration_budget():
    initial, cfg = divergence_case(ImprovementStrategy.BEST, max_iterations=1, max_evaluations=4)
    result = HillClimber(cfg).improve_state(initial)
    assert result.accepted_moves == 1
    assert result.termination_reason == 'iteration_budget'
