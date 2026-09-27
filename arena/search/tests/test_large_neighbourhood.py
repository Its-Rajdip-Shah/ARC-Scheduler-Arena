"""Strict LNS trajectories, budgets and compatibility with frozen foundations."""
from dataclasses import FrozenInstanceError, replace
from datetime import date
import os
import random
import subprocess
import sys

import pytest

from arena.algorithms import PressureGreedy, HybridCostGreedy
from arena.algorithms.tests.test_constructor_zoo import mini_corpus
from arena.algorithms.tests.test_greedy import config as greedy_config
from arena.scheduling.validation import validate_plan
from arena.search import (
    DestroyOperator as D, RepairOperator as R, LargeNeighbourhoodConfig,
    LargeNeighbourhoodSearch, NeighbourhoodConfig, all_moves, apply_move, score_state,
)
from .helpers import TODAY, DAY, item, problem, state, objective
from .test_destroy_repair import replay


def config(**overrides):
    values = dict(objective=objective(timing=1, overload=0), horizon_days=5,
                  destroy_count=2, destroy_operator=D.RANDOM, repair_operator=R.EARLIEST,
                  max_iterations=5, seed=4)
    values.update(overrides)
    return LargeNeighbourhoodConfig(**values)


def test_real_multi_item_improvement_unavailable_to_strict_c41_move():
    s = state(problem(item(1), item(2), edges=((1, 2),)), (1,), (2,))
    cfg = config(max_evaluations=1)
    initial_cost = score_state(s, cfg.objective).total
    assert initial_cost == 1
    moves = all_moves(s, NeighbourhoodConfig(5))
    assert moves and all(score_state(apply_move(s, move), cfg.objective).total >= initial_cost for move in moves)
    result = LargeNeighbourhoodSearch(cfg).improve_state(s)
    assert result.final_state == state(s.problem, (0,), (1,))
    assert result.objective_history == (1, 0)
    assert (result.iterations, result.evaluations, result.accepted_repairs) == (1, 1, 1)
    assert result.termination_reason == 'evaluation_budget'
    assert result.initial_state is s and result.improved and result.total_improvement == 1
    assert len(result.accepted_changes_history[0]) == 2
    assert replay(s, result.accepted_changes_history) == result.final_state


@pytest.mark.parametrize('cost', [objective(overload=0), objective(movement=1, overload=0)])
def test_equal_and_worse_candidates_rejected(cost):
    s = state(problem(item(existing_scheduled_date=TODAY + 2 * DAY)), (2,))
    result = LargeNeighbourhoodSearch(config(objective=cost, max_iterations=3)).improve_state(s)
    assert result.final_state is s
    assert result.iterations == result.evaluations == 3
    assert result.accepted_repairs == 0 and result.accepted_changes_history == ()
    assert result.objective_history == (0,)


@pytest.mark.parametrize('iterations,evaluations,reason', [(0, 0, 'iteration_budget'), (0, None, 'iteration_budget'), (3, 0, 'evaluation_budget'), (1, 1, 'iteration_budget'), (3, 1, 'evaluation_budget')])
def test_exact_budget_boundaries(iterations, evaluations, reason):
    result = LargeNeighbourhoodSearch(config(max_iterations=iterations, max_evaluations=evaluations)).improve_state(state(problem(item()), (3,)))
    attempted = int(iterations > 0 and evaluations != 0)
    assert result.termination_reason == reason
    assert result.iterations == result.evaluations == result.accepted_repairs == attempted


def test_noops_and_empty_items_accounting():
    result = LargeNeighbourhoodSearch(config()).improve_state(state(problem(item()), (0,)))
    assert result.iterations == 5 and result.evaluations == result.accepted_repairs == 0
    assert result.termination_reason == 'iteration_budget'
    result = LargeNeighbourhoodSearch(config()).improve_state(state(problem()))
    assert result.termination_reason == 'no_schedulable_items'
    assert result.iterations == result.evaluations == 0


def test_failed_attempt_not_scored(monkeypatch):
    import arena.search.large_neighbourhood as module
    from .test_destroy_repair import ControlledRNG
    class RNG(ControlledRNG):
        def sample(self, population, count):
            return list(population[:count])
    monkeypatch.setattr(module.random, 'Random', lambda seed: RNG(indices=(2,)))
    s = state(problem(item(1), item(2, anchor_date=TODAY + DAY), edges=((1, 2),)), (0,), (1,))
    calls = []
    original_score = module.score_state
    def score(candidate, cost):
        calls.append(candidate)
        return original_score(candidate, cost)
    monkeypatch.setattr(module, 'score_state', score)
    result = LargeNeighbourhoodSearch(config(max_iterations=1, repair_operator=R.RANDOM)).improve_state(s)
    assert result.iterations == 1 and result.evaluations == 0 and calls == [s]
    assert result.final_state is s and result.accepted_changes_history == ()


@pytest.mark.parametrize('name,value', [
    ('horizon_days', True), ('horizon_days', -1), ('horizon_days', 1.5), ('horizon_days', None),
    ('destroy_count', 0), ('destroy_count', True), ('destroy_count', -1), ('destroy_count', 1.0),
    ('max_iterations', None), ('max_iterations', True), ('max_iterations', -1), ('max_iterations', 1.0),
    ('max_evaluations', True), ('max_evaluations', -1), ('max_evaluations', 1.0),
    ('seed', True), ('seed', 1.5), ('seed', None),
    ('destroy_operator', 'random'), ('repair_operator', 'earliest'), ('objective', None),
    ('horizon_days', date.max.toordinal()),
])
def test_invalid_config(name, value):
    with pytest.raises(ValueError):
        config(**{name: value})


def test_required_arguments_and_frozen_types_calendar_even_zero_budget():
    with pytest.raises(TypeError):
        LargeNeighbourhoodConfig(objective(), 1, 1, D.RANDOM, R.EARLIEST)
    cfg = config(max_iterations=0)
    engine = LargeNeighbourhoodSearch(cfg)
    result = engine.improve_state(state(problem(item()), (0,)))
    for obj, field, value in [(cfg, 'seed', 2), (engine, 'config', cfg), (result, 'iterations', 9)]:
        assert not hasattr(obj, '__dict__')
        with pytest.raises(FrozenInstanceError):
            setattr(obj, field, value)
    with pytest.raises(ValueError, match='calendar'):
        LargeNeighbourhoodSearch(config(horizon_days=date.max.toordinal() - TODAY.toordinal() + 1,
                                       max_iterations=0)).improve_state(state(problem()))


@pytest.mark.parametrize('constructor', [PressureGreedy, HybridCostGreedy])
@pytest.mark.parametrize('destroy', list(D))
@pytest.mark.parametrize('repair', list(R))
def test_constructor_plans_seeded_determinism_validation(constructor, destroy, repair):
    engine = LargeNeighbourhoodSearch(config(destroy_operator=destroy, repair_operator=repair))
    global_before = random.getstate()
    for p in mini_corpus():
        plan = constructor(greedy_config(timing=1, movement=2, risk=1)).solve(p)
        before = repr((p, plan))
        result = engine.improve_plan(p, plan)
        assert result == engine.improve_state(result.initial_state)
        assert replay(result.initial_state, result.accepted_changes_history) == result.final_state
        validation = validate_plan(p, result.final_state.to_plan())
        assert validation.violations == validation.infeasibilities == ()
        assert all(a > b for a, b in zip(result.objective_history, result.objective_history[1:]))
        assert repr((p, plan)) == before
    assert random.getstate() == global_before


def test_public_standalone_import_isolation():
    env = dict(os.environ)
    env.pop('DJANGO_SETTINGS_MODULE', None)
    subprocess.run([sys.executable, '-c',
        'from arena.search import (DestroyOperator, RepairOperator, LargeNeighbourhoodConfig, '
        'LargeNeighbourhoodResult, LargeNeighbourhoodSearch, AdaptiveLargeNeighbourhoodConfig, '
        'AdaptiveLargeNeighbourhoodResult, AdaptiveLargeNeighbourhoodSearch); '
        'import sys; assert not any(k == "django" or k.startswith("django.") for k in sys.modules); '
        'assert "arena.evaluation.performance" not in sys.modules'], env=env, check=True)
