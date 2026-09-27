"""Family-order and complete-scan behavioural contracts."""
from dataclasses import FrozenInstanceError, replace
from unittest.mock import patch
import pytest

from arena.search.variable_neighbourhood import (
    VariableNeighbourhoodMode as Mode, VariableNeighbourhoodConfig as Config,
    VariableNeighbourhoodSearch as Engine,
)
from arena.search import variable_neighbourhood as vn
from arena.search import (
    NeighbourhoodConfig, RelocateSession, ShiftItem, all_moves, apply_move, score_state,
    HillClimber, HillClimbConfig, ImprovementStrategy,
)
from .helpers import TODAY, DAY, item, problem, state, objective


def settings(mode=Mode.VND, **kwargs):
    return Config(objective(timing=1, overload=0), NeighbourhoodConfig(3), mode, **kwargs)


@pytest.mark.parametrize('field', ['max_iterations', 'max_evaluations'])
@pytest.mark.parametrize('value', [-1, True, False, 1.5, '1'])
def test_invalid_budget(field, value):
    with pytest.raises(ValueError): settings(**{field: value})


@pytest.mark.parametrize('value', ['vnd', 'vns', None, 0])
def test_invalid_mode(value):
    with pytest.raises(ValueError): settings(value)


@pytest.mark.parametrize('value', [True, False, 1.5, '0', None])
def test_invalid_seed(value):
    with pytest.raises(ValueError): settings(seed=value)


def test_fixed_order_empty_families_and_reset():
    initial = state(problem(item(duration_category='UNDER_8_HOURS')), (2, 3))
    cfg = replace(settings(), neighbourhood=NeighbourhoodConfig(3, 0))
    calls = []
    def recording(index, generator):
        def generate(current, config):
            calls.append(index)
            return generator(current, config)
        return generate
    assert vn._FAMILIES == (vn.relocate_session_moves, vn.swap_session_moves, vn.shift_item_moves)
    with patch.object(vn, '_FAMILIES', tuple(recording(i, g) for i, g in enumerate(vn._FAMILIES))):
        result = Engine(cfg).improve_state(initial)
    assert calls == [0, 1, 2, 0, 1, 2]
    assert result.objective_history == (4, 0)
    assert result.accepted_moves_history == (ShiftItem(1, -2),)
    assert result.iterations == 6 and result.termination_reason == 'local_optimum'


def test_family_decision_differs_from_flat_hc_decision():
    # Relocation can improve the start by one day; an atomic shift can improve
    # it by two. VND completes the relocate decision before considering shifts.
    initial = state(problem(item(duration_category='UNDER_8_HOURS')), (2, 3))
    cfg = replace(settings(max_iterations=1), neighbourhood=NeighbourhoodConfig(3, 1))
    vnd = Engine(cfg).improve_state(initial)
    hc = HillClimber(HillClimbConfig(cfg.objective, cfg.neighbourhood,
        ImprovementStrategy.BEST, max_iterations=1)).improve_state(initial)
    assert vnd.objective_history == (4, 1)
    assert hc.objective_history == (4, 0)
    assert vnd.final_state != hc.final_state


def test_tie_retains_first():
    initial = state(problem(item(existing_scheduled_date=TODAY + 3 * DAY)), (3,))
    cfg = replace(settings(max_iterations=1), objective=objective(timing=1, movement=1, overload=0))
    result = Engine(cfg).improve_state(initial)
    assert result.accepted_moves_history == (RelocateSession(1, 0, TODAY + DAY),)
    assert result.objective_history == (9, 5)


@pytest.mark.parametrize('budget,accepted', [(1, 0), (2, 0), (3, 1), (4, 1)])
def test_truncated_scan_and_exact_boundary(budget, accepted):
    initial = state(problem(item()), (3,))
    result = Engine(settings(max_evaluations=budget)).improve_state(initial)
    assert result.accepted_moves == accepted and result.evaluations == budget
    assert result.termination_reason == 'evaluation_budget'
    assert result.objective_history == ((9,) if not accepted else (9, 0))
    if not accepted: assert result.final_state is initial


@pytest.mark.parametrize('limits,reason', [
    ({'max_iterations': 0}, 'iteration_budget'),
    ({'max_evaluations': 0}, 'evaluation_budget'),
    ({'max_iterations': 0, 'max_evaluations': 0}, 'iteration_budget'),
])
def test_zero_budgets(limits, reason):
    initial = state(problem(item()), (2,))
    with patch.object(vn, 'score_state', wraps=score_state) as score:
        result = Engine(settings(**limits)).improve_state(initial)
    assert score.call_count == 1
    assert result.initial_state is result.final_state is initial
    assert result.iterations == result.evaluations == 0
    assert result.termination_reason == reason


def test_empty_and_exact_final_family_budget():
    initial = state(problem(item()), (0,))
    result = Engine(replace(settings(max_iterations=3), neighbourhood=NeighbourhoodConfig(0))).improve_state(initial)
    assert result.iterations == 3 and result.evaluations == 0
    assert result.termination_reason == 'local_optimum'
    result = Engine(settings(max_evaluations=6)).improve_state(initial)
    assert result.termination_reason == 'local_optimum'
    assert result.evaluations == 6 and result.iterations == 3


def test_immutability_replay_and_counts():
    initial = state(problem(item(1), item(2)), (2,), (3,))
    before = repr(initial)
    cfg = settings()
    engine = Engine(cfg)
    result = engine.improve_state(initial)
    cursor = initial
    assert result.initial_state is initial
    assert result.improved and result.total_improvement == 13
    for move, total in zip(result.accepted_moves_history, result.objective_history[1:], strict=True):
        cursor = apply_move(cursor, move)
        assert score_state(cursor, cfg.objective).total == total
    assert cursor == result.final_state
    assert len(result.objective_history) == result.accepted_excursions + 1
    assert result.accepted_moves == result.accepted_excursions == len(result.accepted_moves_history)
    assert all(b < a for a, b in zip(result.objective_history, result.objective_history[1:]))
    for obj, field in [(cfg, 'mode'), (engine, 'config'), (result, 'iterations')]:
        assert not hasattr(obj, '__dict__')
        with pytest.raises(FrozenInstanceError): setattr(obj, field, None)
    assert repr(initial) == before


def test_contract_violation():
    with patch.object(vn, '_FAMILIES', (lambda s, c: (object(),),)):
        with pytest.raises(RuntimeError): Engine(settings()).improve_state(state(problem(item()), (0,)))


def vns_basin():
    # Real C2 costs and all three C4.1 families: dependencies make two basins.
    p = problem(item(1, priority_position=1, existing_scheduled_date=TODAY + 2 * DAY),
                item(2, priority_position=2, existing_scheduled_date=TODAY),
                item(3, priority_position=2, existing_scheduled_date=TODAY + DAY),
                edges=((1, 3),), capacity=1)
    cfg = replace(settings(Mode.VNS), objective=objective(priority=1, overload=2, movement=1))
    return state(p, (0,), (0,), (1,)), cfg


def assert_vns_history(result, cfg):
    from arena.scheduling.validation import validate_plan
    assert result.accepted_moves == len(result.accepted_moves_history)
    assert result.accepted_excursions == len(result.objective_history) - 1
    assert result.objective_history[0] == result.initial_objective.total
    assert result.objective_history[-1] == result.final_objective.total
    assert all(b < a for a, b in zip(result.objective_history, result.objective_history[1:]))
    cursor = result.initial_state
    replay_totals = [score_state(cursor, cfg.objective).total]
    for move in result.accepted_moves_history:
        assert any(move in generator(cursor, cfg.neighbourhood) for generator in vn._FAMILIES)
        cursor = apply_move(cursor, move)
        validation = validate_plan(cursor.problem, cursor.to_plan())
        assert validation.violations == validation.infeasibilities == ()
        replay_totals.append(score_state(cursor, cfg.objective).total)
    assert cursor == result.final_state
    assert score_state(cursor, cfg.objective) == result.final_objective
    return tuple(replay_totals)


def test_vns_seeded_determinism_global_rng_and_input_immutability():
    import random
    initial, cfg = vns_basin()
    before = repr((initial.problem, initial, cfg))
    global_rng = random.getstate()
    engine = Engine(cfg)
    result = engine.improve_state(initial)
    assert result == engine.improve_state(initial)
    assert result.initial_state is initial
    assert random.getstate() == global_rng
    assert repr((initial.problem, initial, cfg)) == before
    assert_vns_history(result, cfg)
    for obj, field in [(cfg, 'seed'), (engine, 'config'), (result, 'accepted_excursions')]:
        assert not hasattr(obj, '__dict__')
        with pytest.raises(FrozenInstanceError): setattr(obj, field, None)


def test_vns_controlled_seeds_choose_different_shakes():
    initial, cfg = vns_basin()
    shakes = []
    results = []
    for seed in (0, 1):
        with patch.object(vn, 'apply_move', wraps=apply_move) as apply:
            result = Engine(replace(cfg, seed=seed, max_iterations=3)).improve_state(initial)
        shakes.append(apply.call_args_list[0].args[1])
        results.append(result)
    assert shakes == [RelocateSession(3, 0, TODAY + 2 * DAY),
                      RelocateSession(2, 0, TODAY + 2 * DAY)]
    assert results[0].objective_history == (6, 5)
    assert results[1].objective_history == (6,)


def test_vns_worsening_shake_escapes_strict_local_optimum():
    initial, cfg = vns_basin()
    cfg = replace(cfg, max_iterations=3)
    assert all(score_state(apply_move(initial, m), cfg.objective).total > 6
               for m in all_moves(initial, cfg.neighbourhood))
    hc = HillClimber(HillClimbConfig(cfg.objective, cfg.neighbourhood,
        ImprovementStrategy.BEST)).improve_state(initial)
    assert hc.final_state is initial and hc.termination_reason == 'local_optimum'
    with patch.object(vn, 'score_state', wraps=score_state) as score:
        result = Engine(cfg).improve_state(initial)
    assert score.call_count == result.evaluations + 1
    assert result.objective_history == (6, 5)
    assert result.accepted_moves == 2 and result.accepted_excursions == 1
    assert result.accepted_moves_history == (
        RelocateSession(3, 0, TODAY + 2 * DAY), RelocateSession(1, 0, TODAY + DAY))
    assert assert_vns_history(result, cfg) == (6, 8, 5)
    assert result.iterations == 3 and result.evaluations == 13
    assert result.improved and result.total_improvement == 1


def test_vns_rejected_excursions_advance_families_from_incumbent():
    initial = state(problem(item()), (0,))
    cfg = settings(Mode.VNS)
    calls = []
    def recording(index, generator):
        def generate(current, config):
            calls.append((index, current))
            return generator(current, config)
        return generate
    with patch.object(vn, '_FAMILIES', tuple(recording(i, g) for i, g in enumerate(vn._FAMILIES))):
        result = Engine(cfg).improve_state(initial)
    assert [index for index, _ in calls] == [0, 1, 2]
    assert all(current is initial for _, current in calls)
    assert result.final_state is initial
    assert result.objective_history == (0,) and result.accepted_moves_history == ()
    assert result.accepted_moves == result.accepted_excursions == 0
    assert result.termination_reason == 'local_optimum'
    assert result.evaluations > 0


@pytest.mark.parametrize('budget,iterations', [(1, 1), (2, 2), (7, 2), (8, 3), (12, 3)])
def test_vns_evaluation_interruption_discards_whole_excursion(budget, iterations):
    initial, cfg = vns_basin()
    cfg = replace(cfg, max_evaluations=budget)
    result = Engine(cfg).improve_state(initial)
    assert result.final_state is initial
    assert result.termination_reason == 'evaluation_budget'
    assert result.iterations == iterations and result.evaluations == budget
    assert result.accepted_moves_history == () and result.objective_history == (6,)
    assert result.accepted_moves == result.accepted_excursions == 0


@pytest.mark.parametrize('budget,evaluations', [(1, 1), (2, 7)])
def test_vns_iteration_interruption_after_shake_or_improving_descent(budget, evaluations):
    initial, cfg = vns_basin()
    with patch.object(vn, 'all_moves', wraps=all_moves) as scans:
        result = Engine(replace(cfg, max_iterations=budget)).improve_state(initial)
    assert result.final_state is initial
    assert result.iterations == budget and result.evaluations == evaluations
    assert scans.call_count == budget - 1
    assert result.termination_reason == 'iteration_budget'
    assert result.objective_history == (6,) and result.accepted_moves_history == ()
    assert result.accepted_excursions == result.accepted_moves == 0


@pytest.mark.parametrize('limits,reason', [
    ({'max_evaluations': 13}, 'evaluation_budget'),
    ({'max_evaluations': 13, 'max_iterations': 3}, 'iteration_budget'),
])
def test_vns_exact_complete_proof_boundary_accepts(limits, reason):
    initial, cfg = vns_basin()
    result = Engine(replace(cfg, **limits)).improve_state(initial)
    assert result.objective_history == (6, 5) and result.accepted_excursions == 1
    assert result.iterations == 3 and result.evaluations == 13
    assert result.termination_reason == reason
    assert_vns_history(result, cfg)


def test_vns_interrupt_later_excursion_preserves_previous_acceptance():
    initial, cfg = vns_basin()
    result = Engine(replace(cfg, max_evaluations=15)).improve_state(initial)
    assert result.objective_history == (6, 5)
    assert result.accepted_excursions == 1 and result.accepted_moves == 2
    assert result.evaluations == 15 and result.iterations == 5
    assert result.termination_reason == 'evaluation_budget'
    assert_vns_history(result, cfg)


def test_vns_multiple_accepted_excursions_replay_and_reset():
    initial, cfg = vns_basin()
    initial = state(initial.problem, (0,), (0,), (2,))
    cfg = replace(cfg, seed=6)
    families = []
    def recording(index, generator):
        def generate(current, config):
            families.append((index, score_state(current, cfg.objective).total))
            return generator(current, config)
        return generate
    with patch.object(vn, '_FAMILIES', tuple(recording(i, g) for i, g in enumerate(vn._FAMILIES))):
        result = Engine(cfg).improve_state(initial)
    assert result.objective_history == (8, 6, 5)
    assert result.accepted_excursions == 2 and result.accepted_moves == 3
    assert assert_vns_history(result, cfg) == (8, 6, 8, 5)
    for total in (6, 5):
        assert next(index for index, value in families if value == total) == 0


@pytest.mark.parametrize('limits,reason', [
    ({'max_iterations': 0}, 'iteration_budget'),
    ({'max_evaluations': 0}, 'evaluation_budget'),
    ({'max_iterations': 0, 'max_evaluations': 0}, 'iteration_budget'),
])
def test_vns_zero_budgets_do_not_generate(limits, reason):
    initial, cfg = vns_basin()
    with patch.object(vn, '_FAMILIES', (pytest.fail,)), \
         patch.object(vn, 'score_state', wraps=score_state) as score:
        result = Engine(replace(cfg, **limits)).improve_state(initial)
    assert result.termination_reason == reason
    assert score.call_count == 1
    assert result.iterations == result.evaluations == 0
    assert result.final_state is initial
    assert_vns_history(result, cfg)


def test_vns_empty_families_and_empty_descent_proof():
    initial = state(problem(item()), (0,))
    cfg = replace(settings(Mode.VNS, max_iterations=3), neighbourhood=NeighbourhoodConfig(0))
    result = Engine(cfg).improve_state(initial)
    assert result.termination_reason == 'local_optimum'
    assert result.iterations == 3 and result.evaluations == 0
    # An initially out-of-horizon session can enter a horizon with no neighbours.
    initial = state(initial.problem, (1,))
    result = Engine(replace(cfg, max_iterations=2)).improve_state(initial)
    assert result.objective_history == (1, 0)
    assert result.iterations == 2 and result.evaluations == 1
    assert result.accepted_moves == result.accepted_excursions == 1
    assert_vns_history(result, cfg)


def test_vns_descent_ties_retain_first_occurrence():
    initial = state(problem(item(existing_scheduled_date=TODAY + 3 * DAY)), (3,))
    cfg = replace(settings(Mode.VNS, seed=1, max_iterations=3),
                  objective=objective(timing=1, movement=1, overload=0))
    result = Engine(cfg).improve_state(initial)
    assert result.accepted_moves_history == (
        RelocateSession(1, 0, TODAY), RelocateSession(1, 0, TODAY + DAY))
    assert result.objective_history == (9, 5)
    assert_vns_history(result, cfg)


@pytest.mark.parametrize('where', ['shake', 'descent'])
def test_vns_illegal_generator_contract(where):
    initial, cfg = vns_basin()
    target, value = ('_FAMILIES', (lambda s, c: (object(),),)) if where == 'shake' else (
        'all_moves', lambda s, c: (object(),))
    with patch.object(vn, target, value):
        with pytest.raises(RuntimeError, match='C4.1 neighbourhood'):
            Engine(cfg).improve_state(initial)


@pytest.mark.parametrize('constructor_name', ['PressureGreedy', 'HybridCostGreedy'])
def test_vns_constructor_plan_roundtrip(constructor_name):
    import arena.algorithms as algorithms
    from arena.algorithms.tests.test_constructor_zoo import mini_corpus
    from arena.algorithms.tests.test_greedy import config as greedy_config
    from arena.scheduling.validation import validate_plan
    constructor = getattr(algorithms, constructor_name)(greedy_config(timing=1, movement=2, risk=1))
    cfg = replace(settings(Mode.VNS, max_iterations=20, max_evaluations=200),
                  neighbourhood=NeighbourhoodConfig(5))
    for p in mini_corpus():
        plan = constructor.solve(p)
        before = repr((p, plan, cfg))
        result = Engine(cfg).improve_plan(p, plan)
        validation = validate_plan(p, result.final_state.to_plan())
        assert validation.violations == validation.infeasibilities == ()
        assert result.final_state.problem is p
        assert repr((p, plan, cfg)) == before
        assert_vns_history(result, cfg)


@pytest.mark.parametrize('budget,reason,iterations', [
    (3, 'evaluation_budget', 3), (6, 'local_optimum', 7),
])
def test_vns_exact_complete_proof_boundary_rejects_equal_excursion(budget, reason, iterations):
    initial = state(problem(item()), (0,))
    cfg = replace(settings(Mode.VNS, max_evaluations=budget), neighbourhood=NeighbourhoodConfig(1))
    result = Engine(cfg).improve_state(initial)
    # Every nonempty family shakes 0 -> 1 and descends 1 -> 0, then proves
    # local optimality. The equal endpoint is rejected, even at the boundary.
    assert result.final_state is initial
    assert result.objective_history == (0,) and result.accepted_moves_history == ()
    assert result.accepted_moves == result.accepted_excursions == 0
    assert result.evaluations == budget and result.iterations == iterations
    assert result.termination_reason == reason
