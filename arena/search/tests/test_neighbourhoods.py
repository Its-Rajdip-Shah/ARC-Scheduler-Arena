from dataclasses import replace
from datetime import date
from itertools import product
import hashlib
import os
import subprocess
import sys
import pytest
from arena.search import (SearchState, SessionPlacement, NeighbourhoodConfig, RelocateSession,
    SwapSessions, ShiftItem, apply_move, relocate_session_moves, swap_session_moves,
    shift_item_moves, all_moves)
from arena.scheduling.domain import Allocation, SchedulePlan
from arena.scheduling.mechanics import session_pieces
from arena.scheduling.validation import validate_plan
from arena.algorithms import EarliestFeasible, PressureGreedy, HybridCostGreedy
from arena.algorithms.tests.test_greedy import config
from arena.algorithms.tests.test_constructor_zoo import mini_corpus, FAMILIES
from .helpers import TODAY, DAY, item, problem, state


@pytest.mark.parametrize('generator', [relocate_session_moves, swap_session_moves, shift_item_moves, all_moves])
def test_determinism_unique_horizon_and_validity(generator):
    s = state(problem(item(1, duration_category='UNDER_8_HOURS', anchor_date=TODAY),
                      item(2, due_date=TODAY), item(3), edges=((1, 3),), capacity=0),
              (0, 1), (1,), (4,))
    cfg = NeighbourhoodConfig(3)
    moves = generator(s, cfg)
    assert moves == generator(s, cfg)
    neighbours = [apply_move(s, m) for m in moves]
    assert len(set(neighbours)) == len(neighbours)
    for n in neighbours:
        assert n is not None and n != s
        assert not validate_plan(s.problem, n.to_plan()).violations
        for a, b in zip(s.placements, n.placements):
            if a != b: assert b.scheduled_date <= TODAY + 3 * DAY
    assert s.completion(3) == TODAY + 4 * DAY


def test_exact_bounds_and_combined_order():
    s = state(problem(item()), (2,))
    cfg = NeighbourhoodConfig(4, 1)
    assert relocate_session_moves(s, cfg) == (RelocateSession(1, 0, TODAY + DAY), RelocateSession(1, 0, TODAY + 3 * DAY))
    assert shift_item_moves(s, cfg) == tuple(ShiftItem(1, d) for d in (-2, -1, 1, 2))
    assert all_moves(s, cfg) == (*relocate_session_moves(s, cfg), ShiftItem(1, -2), ShiftItem(1, 2))
    s = state(problem(item(1), item(2), item(3)), (0,), (1,), (2,))
    assert swap_session_moves(s, cfg) == (SwapSessions(1, 0, 2, 0), SwapSessions(1, 0, 3, 0), SwapSessions(2, 0, 3, 0))
    assert all_moves(s, NeighbourhoodConfig(0)) == (RelocateSession(2, 0, TODAY), RelocateSession(3, 0, TODAY))


@pytest.mark.parametrize('kwargs', [{'horizon_days': -1}, {'horizon_days': None}, {'horizon_days': True},
                                    {'horizon_days': 1.5}, {'horizon_days': 0, 'max_relocation_distance_days': -1}])
def test_bad_config(kwargs):
    with pytest.raises(ValueError): NeighbourhoodConfig(**kwargs)


def test_horizon_overflow():
    s = SearchState(replace(problem(), today=date.max), ())
    with pytest.raises(ValueError, match='calendar'): all_moves(s, NeighbourhoodConfig(1))


def test_exhaustive_independent_relocations():
    p = problem(item(1, duration_category='UNDER_8_HOURS'), item(2), edges=((1, 2),), capacity=0)
    s = state(p, (0, 1), (2,))
    expected = set()
    for days in product(range(4), repeat=3):
        if sum(d != old for d, old in zip(days, (0, 1, 2))) != 1 or days[0] > days[1]: continue
        rows = tuple(Allocation(pk, TODAY + d * DAY, percent, rank)
                     for rank, (pk, d, percent) in enumerate(zip((1, 1, 2), days, (50, 50, 100)), 1))
        if not validate_plan(p, SchedulePlan(rows)).violations:
            expected.add(tuple(TODAY + d * DAY for d in days))
    actual = {tuple(p.scheduled_date for p in apply_move(s, m).placements)
              for m in relocate_session_moves(s, NeighbourhoodConfig(3))}
    assert actual == expected


@pytest.mark.parametrize('solver', [EarliestFeasible(), PressureGreedy(config()), HybridCostGreedy(config())])
def test_constructor_integration(solver):
    for p in mini_corpus():
        s = SearchState.from_plan(p, solver.solve(p))
        for move in all_moves(s, NeighbourhoodConfig(5)):
            n = apply_move(s, move)
            assert n is not None
            assert not validate_plan(p, n.to_plan()).violations


def test_c3_fingerprint_after_conversion():
    settings = (config(timing=1), config(timing=10), config(movement=10, risk=1), config(timing=1, movement=1, risk=1))
    results = []
    for family, cfg in zip(FAMILIES, settings):
        for p in mini_corpus():
            plan = family(cfg).solve(p)
            SearchState.from_plan(p, plan).to_plan()
            results.append(repr(plan))
    assert hashlib.sha256('\n'.join(results).encode()).hexdigest() == '8613c8bcfd3a76994905ca18cf921ac3afd516fa0d444a3c55fd00ce4a9cfcfc'


def test_architecture():
    env = dict(os.environ)
    env.pop('DJANGO_SETTINGS_MODULE', None)
    subprocess.run([sys.executable, '-c', 'import sys; import arena.search; '
        'assert not any(k == "django" or k.startswith("django.") for k in sys.modules); '
        'assert "arena.evaluation.performance" not in sys.modules; '
        'assert "arena.algorithms.greedy" not in sys.modules'], env=env, check=True)
