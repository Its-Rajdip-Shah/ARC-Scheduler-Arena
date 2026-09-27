"""State memory, strict aspiration and complete-scan tabu decisions."""
from dataclasses import FrozenInstanceError, replace
from unittest.mock import patch
import pytest

from arena.search.tabu_search import TabuConfig, TabuSearch, _admissible
from arena.search import tabu_search as ts
from arena.search import NeighbourhoodConfig, RelocateSession, ShiftItem, apply_move, score_state
from .helpers import TODAY, DAY, item, problem, state, objective


def settings(**kwargs):
    return TabuConfig(objective(timing=1, overload=0), NeighbourhoodConfig(2), 3, **kwargs)


@pytest.mark.parametrize('value', [0, -1, True, False, 1.5, None, '1'])
def test_invalid_tenure(value):
    with pytest.raises(ValueError): replace(settings(), tabu_tenure=value)


@pytest.mark.parametrize('field', ['max_iterations', 'max_evaluations'])
@pytest.mark.parametrize('value', [-1, True, False, 1.5, '1'])
def test_invalid_budget(field, value):
    with pytest.raises(ValueError): settings(**{field: value})


def test_worsening_walk_best_return_reverse_tabu_and_no_admissible():
    initial = state(problem(item()), (0,))
    result = TabuSearch(settings()).improve_state(initial)
    assert result.walk_objective_history == (0, 1, 4)
    assert result.best_objective_history == (0,)
    assert result.final_state is result.initial_state is initial
    assert result.last_state.start(1) == TODAY + 2 * DAY
    assert result.termination_reason == 'no_admissible_move'
    assert result.iterations == 3 and result.evaluations == 6
    assert result == TabuSearch(settings()).improve_state(initial)


def test_state_attribute_different_move_representation_and_aspiration():
    initial = state(problem(item()), (2,))
    a = apply_move(initial, RelocateSession(1, 0, TODAY))
    b = apply_move(initial, ShiftItem(1, -2))
    assert a.placements == b.placements
    cfg = settings().objective
    cost = score_state(a, cfg)
    memory = {a.placements: 5}
    # Explicit memory fixture exercises aspiration with real states and scores.
    # In an ordinary static-objective walk a previously visited state cannot
    # beat best-ever; no score mutation is needed to test the strict predicate.
    assert _admissible(b, cost, score_state(initial, cfg), memory, 5)
    assert not _admissible(b, cost, cost, memory, 5)
    assert _admissible(b, cost, cost, memory, 6)


def test_different_representation_reverse_is_blocked_in_walk():
    initial = state(problem(item()), (0,))
    def generate(current, config):
        if current.start(1) == TODAY:
            return (RelocateSession(1, 0, TODAY + DAY),)
        return (ShiftItem(1, -1),)
    with patch.object(ts, 'all_moves', side_effect=generate):
        result = TabuSearch(settings()).improve_state(initial)
    assert result.walk_objective_history == (0, 1)
    assert result.termination_reason == 'no_admissible_move'


def test_tie_retains_generator_first():
    initial = state(problem(item(existing_scheduled_date=TODAY + 3 * DAY)), (3,))
    cfg = replace(settings(max_iterations=1), neighbourhood=NeighbourhoodConfig(3),
                  objective=objective(timing=1, movement=1, overload=0))
    result = TabuSearch(cfg).improve_state(initial)
    assert result.accepted_moves_history == (RelocateSession(1, 0, TODAY + DAY),)
    assert result.best_objective_history == (9, 5)


@pytest.mark.parametrize('budget,accepted', [(1, 0), (2, 1), (3, 1)])
def test_truncated_scan_and_exact_boundary(budget, accepted):
    initial = state(problem(item()), (2,))
    result = TabuSearch(settings(max_evaluations=budget)).improve_state(initial)
    assert result.evaluations == budget and result.accepted_moves == accepted
    assert result.termination_reason == 'evaluation_budget'
    assert result.walk_objective_history == ((4,) if not accepted else (4, 0))


@pytest.mark.parametrize('limits,reason', [
    ({'max_iterations': 0, 'max_evaluations': 0}, 'iteration_budget'),
    ({'max_evaluations': 0}, 'evaluation_budget'),
])
def test_zero_budgets(limits, reason):
    initial = state(problem(item()), (1,))
    with patch.object(ts, 'all_moves', wraps=ts.all_moves) as generate, \
         patch.object(ts, 'score_state', wraps=score_state) as score:
        result = TabuSearch(settings(**limits)).improve_state(initial)
    assert result.termination_reason == reason
    assert result.iterations == result.evaluations == result.accepted_moves == 0
    generate.assert_not_called()
    assert score.call_count == 1


def test_replay_immutability_and_best_history():
    initial = state(problem(item()), (2,))
    before = repr(initial)
    cfg = settings(max_iterations=5)
    engine = TabuSearch(cfg)
    result = engine.improve_state(initial)
    cursor = initial
    for move, total in zip(result.accepted_moves_history, result.walk_objective_history[1:], strict=True):
        cursor = apply_move(cursor, move)
        assert score_state(cursor, cfg.objective).total == total
    assert cursor == result.last_state
    assert len(result.walk_objective_history) == result.accepted_moves + 1
    assert all(b < a for a, b in zip(result.best_objective_history, result.best_objective_history[1:]))
    assert result.improved and result.total_improvement == 4
    for obj, field in [(cfg, 'tabu_tenure'), (engine, 'config'), (result, 'iterations')]:
        assert not hasattr(obj, '__dict__')
        with pytest.raises(FrozenInstanceError): setattr(obj, field, None)
    assert repr(initial) == before


def test_illegal_generator_contract():
    with patch.object(ts, 'all_moves', return_value=(object(),)):
        with pytest.raises(RuntimeError):
            TabuSearch(settings()).improve_state(state(problem(item()), (0,)))


def basin_case():
    p = problem(item(1, priority_position=1, existing_scheduled_date=TODAY + 2 * DAY),
                item(2, priority_position=2, existing_scheduled_date=TODAY),
                item(3, priority_position=2, existing_scheduled_date=TODAY + DAY),
                edges=((1, 3),), capacity=1)
    return state(p, (0,), (0,), (1,)), objective(priority=1, overload=2, movement=1)


def test_escapes_strict_local_optimum_through_worsening_move():
    from arena.search import all_moves
    initial, cost = basin_case()
    cfg = TabuConfig(cost, NeighbourhoodConfig(3), 3, max_iterations=3)
    assert score_state(initial, cost).total == 6
    assert all(score_state(apply_move(initial, m), cost).total > 6
               for m in all_moves(initial, cfg.neighbourhood))
    result = TabuSearch(cfg).improve_state(initial)
    assert result.walk_objective_history == (6, 8, 8, 5)
    assert result.best_objective_history == (6, 5)
    assert result.improved
