"""Controlled adaptive roulette, Metropolis decisions and replay accounting."""
from dataclasses import FrozenInstanceError, replace
from datetime import date
import math
import random

import pytest

from arena.algorithms import PressureGreedy, HybridCostGreedy
from arena.algorithms.tests.test_constructor_zoo import mini_corpus
from arena.algorithms.tests.test_greedy import config as greedy_config
from arena.scheduling.validation import validate_plan
from arena.search import (
    DestroyOperator as D, RepairOperator as R, AdaptiveLargeNeighbourhoodConfig,
    AdaptiveLargeNeighbourhoodSearch,
)
from arena.search.adaptive_large_neighbourhood import _roulette, _update_weight
from .helpers import TODAY, DAY, item, problem, state, objective
from .test_destroy_repair import ControlledRNG, replay


def config(**overrides):
    values = dict(objective=objective(timing=1, overload=0), horizon_days=3, destroy_count=2,
                  max_iterations=4, reaction_factor=.5, initial_temperature=1,
                  cooling_rate=.5, minimum_temperature=.1, reward_best=8,
                  reward_accepted=4, reward_rejected=2, seed=7)
    values.update(overrides)
    return AdaptiveLargeNeighbourhoodConfig(**values)


class WalkRNG(ControlledRNG):
    def __init__(self, draws, indices=()):
        super().__init__(indices=indices)
        self.draws = iter(draws)
        self.draw_count = 0

    def random(self):
        self.draw_count += 1
        return next(self.draws)

    def sample(self, values, count):
        return list(values[:count])


def inject_rng(monkeypatch, rng):
    import arena.search.adaptive_large_neighbourhood as module
    monkeypatch.setattr(module.random, 'Random', lambda seed: rng)


@pytest.mark.parametrize('draw,expected', [(0, D.RANDOM), (.249, D.RANDOM), (.25, D.TEMPORAL), (.749, D.TEMPORAL), (.75, D.DEPENDENCY), (.999, D.DEPENDENCY)])
def test_exact_roulette_intervals(draw, expected):
    assert _roulette({D.RANDOM: 1, D.TEMPORAL: 2, D.DEPENDENCY: 1}, WalkRNG([draw])) is expected


def test_roulette_and_weight_arithmetic_extreme_positive_values():
    assert _update_weight(1, .25, 9) == 3
    assert _update_weight(3, .25, 1) == 2.5
    tiny = math.nextafter(0, 1)
    assert _update_weight(tiny, .5, tiny) == tiny
    assert _update_weight(1, 1, tiny) == tiny
    assert _roulette({D.RANDOM: 1e308, D.TEMPORAL: 1e308, D.DEPENDENCY: 1e308}, WalkRNG([.5])) is D.TEMPORAL


def test_real_walk_best_last_rejection_failure_weights_and_exact_draws(monkeypatch):
    # Four genuine repairs: 2->0 (best), 0->1 (worse accepted),
    # 1->2 (worse rejected), 1->1 (identical, failed without a score).
    rng = WalkRNG([0, .99, 0, .99, 0, 0, .99, .99, 0, .99], (0, 1, 2, 1))
    inject_rng(monkeypatch, rng)
    s = state(problem(item()), (2,))
    result = AdaptiveLargeNeighbourhoodSearch(config()).improve_state(s)
    assert result.final_state == state(s.problem, (0,))
    assert result.last_state == state(s.problem, (1,))
    assert result.best_objective_history == (4, 0)
    assert result.walk_objective_history == (4, 0, 1)
    assert result.final_objective.total == min(result.walk_objective_history)
    assert (result.iterations, result.evaluations, result.accepted_repairs,
            result.rejected_repairs, result.failed_repairs) == (4, 3, 2, 1, 1)
    assert result.operator_history == tuple((D.RANDOM, R.RANDOM, outcome) for outcome in ('best', 'accepted', 'rejected', 'failed'))
    assert result.destroy_weights == ((D.RANDOM, 2.5625), (D.TEMPORAL, 1), (D.DEPENDENCY, 1))
    assert result.repair_weights == ((R.EARLIEST, 1), (R.RANDOM, 2.5625))
    assert result.final_temperature == .1 and rng.draw_count == 10
    assert result.initial_state is s and result.improved and result.total_improvement == 4
    assert replay(s, result.accepted_changes_history) == result.last_state


def test_equal_candidate_accepted_without_probability_draw(monkeypatch):
    rng = WalkRNG([0, 0])
    inject_rng(monkeypatch, rng)
    s = state(problem(item()), (2,))
    result = AdaptiveLargeNeighbourhoodSearch(config(objective=objective(overload=0), max_iterations=1)).improve_state(s)
    assert result.accepted_repairs == 1 and result.last_state != s and result.final_state is s
    assert result.best_objective_history == (0,) and result.walk_objective_history == (0, 0)
    assert result.operator_history == ((D.RANDOM, R.EARLIEST, 'accepted'),)
    assert dict(result.destroy_weights)[D.RANDOM] == 2.5 and rng.draw_count == 2


def test_exact_metropolis_strict_threshold(monkeypatch):
    rng = WalkRNG([0, .99, math.exp(-1)], (1,))
    inject_rng(monkeypatch, rng)
    s = state(problem(item()), (0,))
    result = AdaptiveLargeNeighbourhoodSearch(config(max_iterations=1)).improve_state(s)
    assert result.rejected_repairs == 1 and result.last_state is s
    assert result.evaluations == 1 and result.operator_history[0][-1] == 'rejected'


def test_anchor_failure_cools_and_updates_only_selected_weights(monkeypatch):
    rng = WalkRNG([0, .99] * 4, (2,) * 4)
    inject_rng(monkeypatch, rng)
    s = state(problem(item(1), item(2, anchor_date=TODAY + DAY), edges=((1, 2),)), (0,), (1,))
    result = AdaptiveLargeNeighbourhoodSearch(config()).improve_state(s)
    assert result.iterations == result.failed_repairs == 4
    assert result.accepted_repairs == result.rejected_repairs == result.evaluations == 0
    assert result.last_state is result.final_state is s and result.accepted_changes_history == ()
    assert result.final_temperature == .1
    assert result.destroy_weights == ((D.RANDOM, 1.9375), (D.TEMPORAL, 1), (D.DEPENDENCY, 1))
    assert result.repair_weights == ((R.EARLIEST, 1), (R.RANDOM, 1.9375))
    assert result.termination_reason == 'iteration_budget'


@pytest.mark.parametrize('iterations,evaluations,reason', [(0, 0, 'iteration_budget'), (0, None, 'iteration_budget'), (2, 0, 'evaluation_budget'), (1, 1, 'iteration_budget'), (2, 1, 'evaluation_budget')])
def test_budget_precedence_and_last_evaluation_acceptance(monkeypatch, iterations, evaluations, reason):
    rng = WalkRNG([0, 0])
    inject_rng(monkeypatch, rng)
    s = state(problem(item()), (2,))
    result = AdaptiveLargeNeighbourhoodSearch(config(max_iterations=iterations, max_evaluations=evaluations)).improve_state(s)
    attempted = int(iterations > 0 and evaluations != 0)
    assert result.termination_reason == reason
    assert result.iterations == result.evaluations == result.accepted_repairs == attempted
    assert result.final_objective.total == (0 if attempted else 4)


def test_no_items_and_temperature_floor_does_not_stop():
    result = AdaptiveLargeNeighbourhoodSearch(config()).improve_state(state(problem()))
    assert result.termination_reason == 'no_schedulable_items' and result.iterations == 0
    assert all(w == 1 for _, w in result.destroy_weights + result.repair_weights)
    result = AdaptiveLargeNeighbourhoodSearch(config(horizon_days=0, max_iterations=10,
        initial_temperature=.1, cooling_rate=1)).improve_state(state(problem(item()), (0,)))
    assert result.iterations == result.failed_repairs == 10 and result.evaluations == 0
    assert result.final_temperature == .1


@pytest.mark.parametrize('name,value', [
    ('horizon_days', True), ('horizon_days', -1), ('horizon_days', 1.5), ('horizon_days', None),
    ('horizon_days', date.max.toordinal()), ('destroy_count', True), ('destroy_count', 0),
    ('destroy_count', -1), ('destroy_count', 1.5), ('max_iterations', None),
    ('max_iterations', True), ('max_iterations', -1), ('max_iterations', 1.5),
    ('max_evaluations', True), ('max_evaluations', -1), ('max_evaluations', 1.5),
    ('seed', True), ('seed', None), ('seed', 1.5), ('objective', None),
    ('reaction_factor', 1.01), ('cooling_rate', 1.01), ('minimum_temperature', 2),
    ('reward_best', 4), ('reward_accepted', 8), ('reward_rejected', 4),
])
def test_invalid_config(name, value):
    with pytest.raises(ValueError):
        config(**{name: value})


@pytest.mark.parametrize('name', ['reaction_factor', 'initial_temperature', 'cooling_rate', 'minimum_temperature', 'reward_best', 'reward_accepted', 'reward_rejected'])
@pytest.mark.parametrize('value', [True, 0, -1, math.nan, math.inf, -math.inf, '1', None])
def test_invalid_positive_finite_parameters(name, value):
    with pytest.raises(ValueError):
        config(**{name: value})


def test_required_bounded_config_frozen_api_and_calendar_checks():
    with pytest.raises(TypeError):
        AdaptiveLargeNeighbourhoodConfig(objective=objective())
    cfg = config(reaction_factor=1, cooling_rate=1)
    engine = AdaptiveLargeNeighbourhoodSearch(cfg)
    result = engine.improve_state(state(problem(item()), (0,)))
    for obj, field, value in [(cfg, 'seed', 4), (engine, 'config', cfg), (result, 'iterations', 4)]:
        assert not hasattr(obj, '__dict__')
        with pytest.raises(FrozenInstanceError):
            setattr(obj, field, value)
    with pytest.raises(ValueError, match='calendar'):
        AdaptiveLargeNeighbourhoodSearch(config(horizon_days=date.max.toordinal() - TODAY.toordinal() + 1,
                                               max_iterations=0)).improve_state(state(problem()))


@pytest.mark.parametrize('constructor', [PressureGreedy, HybridCostGreedy])
def test_constructor_roundtrip_seeded_operator_variation_and_accounting(constructor):
    engine = AdaptiveLargeNeighbourhoodSearch(config(max_iterations=30, horizon_days=5))
    global_before = random.getstate()
    seen_destroy, seen_repair = set(), set()
    for p in mini_corpus():
        plan = constructor(greedy_config(timing=1, movement=2, risk=1)).solve(p)
        before = repr((p, plan))
        result = engine.improve_plan(p, plan)
        assert result == engine.improve_state(result.initial_state)
        assert result.accepted_repairs + result.rejected_repairs + result.failed_repairs == result.iterations
        assert result.evaluations == result.accepted_repairs + result.rejected_repairs
        assert len(result.operator_history) == result.iterations
        assert len(result.accepted_changes_history) == result.accepted_repairs
        assert len(result.walk_objective_history) == result.accepted_repairs + 1
        assert result.final_objective.total == min(result.walk_objective_history)
        assert all(a > b for a, b in zip(result.best_objective_history, result.best_objective_history[1:]))
        assert replay(result.initial_state, result.accepted_changes_history) == result.last_state
        for output in (result.last_state, result.final_state):
            validation = validate_plan(p, output.to_plan())
            assert validation.violations == validation.infeasibilities == ()
        for destroy, repair, _ in result.operator_history:
            seen_destroy.add(destroy)
            seen_repair.add(repair)
        assert all(weight > 0 for _, weight in result.destroy_weights + result.repair_weights)
        assert repr((p, plan)) == before
    assert seen_destroy == set(D) and seen_repair == set(R)
    assert random.getstate() == global_before
