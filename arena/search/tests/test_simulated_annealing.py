"""Metropolis decisions use real legal moves and configured plan costs."""
from dataclasses import FrozenInstanceError, replace
import random
from unittest.mock import patch

import pytest

from arena.search.simulated_annealing import SimulatedAnnealing, SimulatedAnnealingConfig
from arena.search import simulated_annealing as sa
from arena.search import NeighbourhoodConfig, apply_move, score_state
from .helpers import item, problem, state, objective


def settings(**kwargs):
    return SimulatedAnnealingConfig(objective(timing=1, overload=0),
        NeighbourhoodConfig(2), 10, .5, .1, **kwargs)


@pytest.mark.parametrize('field', ['initial_temperature', 'cooling_rate', 'minimum_temperature'])
@pytest.mark.parametrize('value', [float('nan'), float('inf'), -1, 0, True, False, '1', None])
def test_invalid_temperature(field, value):
    with pytest.raises(ValueError): replace(settings(), **{field: value})


@pytest.mark.parametrize('change', [{'cooling_rate': 1}, {'cooling_rate': 2},
    {'minimum_temperature': 11}, {'seed': True}, {'seed': 1.5}])
def test_invalid_bounds(change):
    with pytest.raises(ValueError): replace(settings(), **change)


@pytest.mark.parametrize('field', ['max_iterations', 'max_evaluations'])
@pytest.mark.parametrize('value', [-1, True, False, 1.5, '1'])
def test_invalid_budget(field, value):
    with pytest.raises(ValueError): settings(**{field: value})


class ControlledRandom:
    def __init__(self, draw):
        self.draw = draw
        self.calls = 0

    def randrange(self, size):
        return 0

    def random(self):
        self.calls += 1
        assert self.draw is not None, 'non-worsening move drew a probability'
        return self.draw


@pytest.mark.parametrize('initial_day,weight,draw,accepted', [
    (1, 1, None, True), (0, 0, None, True),
    (0, 1, 0, True), (0, 1, .999999, False),
])
def test_acceptance_and_cooling(initial_day, weight, draw, accepted):
    initial = state(problem(item()), (initial_day,))
    cfg = replace(settings(max_iterations=1), objective=objective(timing=weight, overload=0))
    rng = ControlledRandom(draw)
    with patch.object(sa.random, 'Random', return_value=rng):
        result = SimulatedAnnealing(cfg).improve_state(initial)
    assert result.accepted_moves == int(accepted)
    assert result.rejected_moves == int(not accepted)
    assert result.final_temperature == 5
    assert result.evaluations == result.iterations == 1
    assert rng.calls == int(draw is not None)
    if initial_day == 0:
        assert result.final_state is initial
    if accepted and draw is not None:
        assert result.last_objective.total > result.final_objective.total


def test_reproducibility_replay_immutability_and_counts():
    initial = state(problem(item()), (1,))
    before = repr(initial)
    global_rng = random.getstate()
    results = []
    for seed in range(4):
        cfg = settings(seed=seed)
        engine = SimulatedAnnealing(cfg)
        result = engine.improve_state(initial)
        assert result == engine.improve_state(initial)
        assert result.initial_state is initial
        assert result.accepted_moves + result.rejected_moves == result.iterations == result.evaluations
        assert len(result.walk_objective_history) == result.accepted_moves + 1
        cursor = initial
        for move, total in zip(result.accepted_moves_history, result.walk_objective_history[1:], strict=True):
            cursor = apply_move(cursor, move)
            assert score_state(cursor, cfg.objective).total == total
        assert cursor == result.last_state
        assert all(b < a for a, b in zip(result.best_objective_history, result.best_objective_history[1:]))
        for obj, field in [(cfg, 'seed'), (engine, 'config'), (result, 'iterations')]:
            assert not hasattr(obj, '__dict__')
            with pytest.raises(FrozenInstanceError): setattr(obj, field, None)
        results.append(result.accepted_moves_history)
    assert len(set(results)) > 1
    assert random.getstate() == global_rng
    assert repr(initial) == before


@pytest.mark.parametrize('limits,reason,count', [
    ({'max_iterations': 0, 'max_evaluations': 0}, 'iteration_budget', 0),
    ({'max_evaluations': 0}, 'evaluation_budget', 0),
    ({'max_iterations': 2}, 'iteration_budget', 2),
    ({'max_evaluations': 2}, 'evaluation_budget', 2),
])
def test_budget_precedence(limits, reason, count):
    initial = state(problem(item()), (0,))
    with patch.object(sa, 'all_moves', wraps=sa.all_moves) as generate, \
         patch.object(sa, 'score_state', wraps=score_state) as score:
        result = SimulatedAnnealing(settings(**limits)).improve_state(initial)
    assert result.termination_reason == reason
    assert result.iterations == result.evaluations == count
    assert generate.call_count == count
    assert score.call_count == count + 1


def test_floor_and_empty():
    initial = state(problem(item()), (0,))
    result = SimulatedAnnealing(replace(settings(), minimum_temperature=10)).improve_state(initial)
    assert result.termination_reason == 'temperature_floor' and result.iterations == 1
    result = SimulatedAnnealing(replace(settings(), neighbourhood=NeighbourhoodConfig(0))).improve_state(initial)
    assert result.termination_reason == 'no_neighbour' and result.iterations == 0


def test_contract_violation():
    with patch.object(sa, 'all_moves', return_value=(object(),)):
        with pytest.raises(RuntimeError):
            SimulatedAnnealing(settings()).improve_state(state(problem(item()), (0,)))
