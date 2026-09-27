"""Exact destruction order and complete-state repair boundary."""
from dataclasses import FrozenInstanceError, replace
from datetime import date
from decimal import Decimal
import random

import pytest

from arena.scheduling.validation import validate_plan
from arena.search import SearchState, SessionPlacement, DestroyOperator as D, RepairOperator as R
from arena.search.destroy_repair import (
    _select_items, _destroy, _repair, _changed_placements,
)
from .helpers import TODAY, DAY, item, problem, state


class ControlledRNG:
    def __init__(self, seed_item=1, indices=()):
        self.seed_item = seed_item
        self.indices = iter(indices)
        self.sizes = []

    def choice(self, values):
        assert self.seed_item in values
        return self.seed_item

    def randrange(self, size):
        self.sizes.append(size)
        index = next(self.indices)
        assert 0 <= index < size
        return index


def replay(initial, history):
    current = initial
    for changes in history:
        assert changes == tuple(sorted(changes)) and changes
        rows = {(p.item_id, p.session_index): p for p in current.placements}
        for row in changes:
            assert rows[row.item_id, row.session_index] != row
            rows[row.item_id, row.session_index] = row
        current = SearchState(current.problem, tuple(rows.values()))
        assert validate_plan(current.problem, current.to_plan()).is_valid
    return current


def test_exact_temporal_ties_and_seed_first():
    s = state(problem(*(item(i) for i in range(1, 6))), (2,), (1,), (2,), (3,), (5,))
    # Seed first, including ahead of smaller IDs on the exact same date.
    assert _select_items(s, 5, D.TEMPORAL, ControlledRNG(3)) == (3, 1, 2, 4, 5)
    assert _select_items(s, 2, D.TEMPORAL, ControlledRNG(3)) == (3, 1)


def test_dependency_sorted_breadth_first_undirected_and_temporal_fill():
    p = problem(*(item(i) for i in range(1, 8)),
                edges=((1, 3), (1, 2), (3, 5), (4, 5)))
    s = state(p, (0,), (2,), (1,), (0,), (3,), (1,), (1,))
    assert _select_items(s, 7, D.DEPENDENCY, ControlledRNG(3)) == (3, 1, 5, 2, 4, 6, 7)
    assert _select_items(s, 4, D.DEPENDENCY, ControlledRNG(3)) == (3, 1, 5, 2)
    assert p.dependencies == s.problem.dependencies


def test_random_uniform_sample_seeded_and_global_rng_untouched():
    s = state(problem(*(item(i) for i in range(1, 6))), *((2,) for _ in range(5)))
    before = random.getstate()
    assert _select_items(s, 3, D.RANDOM, random.Random(7)) == (3, 2, 4)
    for destroy in D:
        assert _select_items(s, 99, destroy, random.Random(8)) == _select_items(s, 99, destroy, random.Random(8))
        assert set(_select_items(s, 99, destroy, random.Random(8))) == {1, 2, 3, 4, 5}
    assert random.getstate() == before


def test_zero_work_edges_ignored_and_whole_item_removal_frozen():
    p = problem(item(1, duration_category='OVER_16_HOURS'),
                item(2, remaining_fraction=Decimal(0)), item(3), edges=((1, 2), (2, 3)))
    s = state(p, (3, 4, 5), (), (2,))
    assert _select_items(s, 99, D.DEPENDENCY, ControlledRNG(3)) == (3, 1)
    partial = _destroy(s, (1, 1))
    assert partial.original is s and partial.removed_item_ids == (1,)
    assert partial.retained == (s.placements[-1],)
    assert partial.retained[0] is s.placements[-1]
    with pytest.raises(FrozenInstanceError):
        partial.retained = ()
    repaired = _repair(partial, 5, R.EARLIEST, random.Random(0))
    assert repaired == state(p, (0, 0, 0), (), (2,))
    assert validate_plan(p, repaired.to_plan()).is_valid
    with pytest.raises(ValueError):
        _destroy(s, (2,))
    assert _select_items(state(problem()), 1, D.RANDOM, random.Random()) == ()


@pytest.mark.parametrize('destroy', list(D))
@pytest.mark.parametrize('repair', list(R))
def test_all_operators_multisession_retention_percentages_and_immutability(destroy, repair):
    p = problem(item(1, duration_category='OVER_16_HOURS', remaining_fraction=Decimal('.4')),
                item(2, duration_category='UNDER_8_HOURS'), item(3, is_residual=True))
    s = state(p, (3, 4, 5), (4, 5), (5,))
    before = repr((p, s))
    selected = _select_items(s, 2, destroy, random.Random(8))
    partial = _destroy(s, selected)
    candidate = _repair(partial, 5, repair, random.Random(3))
    assert candidate is not None and candidate.problem is p
    assert {(r.item_id, r.session_index) for r in candidate.placements} == {(r.item_id, r.session_index) for r in s.placements}
    for row in partial.retained:
        assert next(r for r in candidate.placements if (r.item_id, r.session_index) == (row.item_id, row.session_index)) is row
    assert validate_plan(p, candidate.to_plan()).violations == ()
    for obj in p.items:
        assert sum((r.percentage for r in candidate.to_plan().allocations_for(obj.item_id)), Decimal(0)) == obj.remaining_fraction * 100
    assert replay(s, (_changed_placements(s, candidate),)) == candidate
    assert repr((p, s)) == before


def test_topological_fanin_release_anchor_same_day_and_soft_costs():
    p = problem(item(1, due_date=TODAY, release_date=TODAY + DAY),
                item(2, duration_category='UNDER_8_HOURS', due_date=TODAY),
                item(3, anchor_date=TODAY + 3 * DAY), item(4),
                edges=((1, 3), (2, 3), (3, 4)), capacity=0)
    s = state(p, (2,), (1, 2), (3,), (5,))
    candidate = _repair(_destroy(s, (4, 3, 2, 1)), 5, R.EARLIEST, random.Random())
    assert candidate == state(p, (1,), (0, 0), (3,), (4,))
    validation = validate_plan(p, candidate.to_plan())
    assert validation.violations == validation.infeasibilities == ()
    assert {'capacity_exceeded', 'after_deadline'} <= {v.code for v in validation.soft_violations}


def test_retained_successor_strict_upper_bound_and_enumeration():
    s = state(problem(item(1), item(2, anchor_date=TODAY + 2 * DAY), edges=((1, 2),)), (0,), (2,))
    rng = ControlledRNG(indices=(1,))
    result = _repair(_destroy(s, (1,)), 5, R.RANDOM, rng)
    assert rng.sizes == [2] and result == state(s.problem, (1,), (2,))


def test_random_choice_blocks_removed_anchor_clean_failure():
    s = state(problem(item(1), item(2, anchor_date=TODAY + DAY), edges=((1, 2),)), (0,), (1,))
    before = repr(s)
    rng = ControlledRNG(indices=(2,))
    assert _repair(_destroy(s, (1, 2)), 3, R.RANDOM, rng) is None
    assert rng.sizes == [4] and repr(s) == before
    assert _repair(_destroy(s, (1, 2)), 3, R.EARLIEST, random.Random()) is None


def test_original_outside_horizon_is_only_fallback_and_anchor_stays_exact():
    p = problem(item(1, duration_category='UNDER_8_HOURS', anchor_date=TODAY + 8 * DAY),
                item(2, release_date=TODAY + 6 * DAY), item(3))
    s = state(p, (8, 9), (7,), (3,))
    result = _repair(_destroy(s, (1, 2, 3)), 2, R.EARLIEST, random.Random())
    assert result == state(p, (8, 9), (7,), (0,))
    # Date 4 is this session's own fallback, not an extended horizon of 0..4.
    s = state(problem(item()), (4,))
    rng = ControlledRNG(indices=(1,))
    result = _repair(_destroy(s, (1,)), 1, R.RANDOM, rng)
    assert rng.sizes == [3] and result == state(s.problem, (1,))
    assert _repair(_destroy(s, (1,)), 1, R.RANDOM, ControlledRNG(indices=(2,))) is None


def test_outside_fallback_must_satisfy_new_prerequisite_completion():
    p = problem(item(1), item(2, anchor_date=TODAY + 4 * DAY), edges=((1, 2),))
    s = state(p, (0,), (4,))
    assert _repair(_destroy(s, (1, 2)), 5, R.RANDOM, ControlledRNG(indices=(5,))) is None


def test_calendar_max_inclusive_and_overflow_rejection():
    p = replace(problem(item(1), item(2), edges=((1, 2),)), today=date.max - 2 * DAY)
    s = SearchState(p, (SessionPlacement(1, 0, date.max - DAY), SessionPlacement(2, 0, date.max)))
    result = _repair(_destroy(s, (1, 2)), 2, R.EARLIEST, random.Random())
    assert result.start(1) == p.today and result.start(2) == date.max - DAY
    # A choice of date.max requires an impossible date.max + 1 for its dependent.
    assert _repair(_destroy(s, (1, 2)), 2, R.RANDOM, ControlledRNG(indices=(2,))) is None
    with pytest.raises(ValueError, match='calendar'):
        _repair(_destroy(s, (1,)), 3, R.EARLIEST, random.Random())
    p = replace(problem(item()), today=date.max)
    s = SearchState(p, (SessionPlacement(1, 0, date.max),))
    assert _repair(_destroy(s, (1,)), 0, R.EARLIEST, random.Random()) is None


def test_unexpected_complete_state_rejection_is_contract_error(monkeypatch):
    import arena.search.destroy_repair as module
    s = state(problem(item()), (2,))
    def reject(*args):
        raise ValueError('unexpected')
    monkeypatch.setattr(module, 'SearchState', reject)
    with pytest.raises(RuntimeError, match='contract'):
        _repair(_destroy(s, (1,)), 2, R.EARLIEST, random.Random())
