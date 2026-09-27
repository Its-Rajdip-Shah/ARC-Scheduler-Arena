from datetime import date
from dataclasses import replace
import pytest
from arena.search import RelocateSession, SwapSessions, ShiftItem, apply_move, SearchState, SessionPlacement
from arena.scheduling.validation import validate_plan
from .helpers import TODAY, DAY, item, problem, state


@pytest.mark.parametrize('move,legal', [
    (RelocateSession(1, 0, TODAY), True), (RelocateSession(1, 0, TODAY + 5 * DAY), True),
    (RelocateSession(1, 0, TODAY - DAY), False), (RelocateSession(9, 0, TODAY), False),
    (RelocateSession(1, 0, TODAY + DAY), False), (SwapSessions(1, 0, 2, 0), True),
    (SwapSessions(1, 0, 1, 0), False), (ShiftItem(1, 0), False),
    (ShiftItem(1, 10**20), False), (ShiftItem(9, 1), False),
])
def test_moves_and_immutability(move, legal):
    s = state(problem(item(1, due_date=TODAY), item(2), capacity=0), (1,), (2,))
    before = repr(s)
    n = apply_move(s, move)
    assert (n is not None) == legal
    assert repr(s) == before
    if n:
        assert n.problem is s.problem
        assert not validate_plan(s.problem, n.to_plan()).violations


def test_split_anchor_order_release_and_same_date_swap():
    s = state(problem(item(1, duration_category='OVER_16_HOURS', anchor_date=TODAY),
                      item(2, release_date=TODAY + DAY)), (0, 2, 4), (2,))
    for move in (RelocateSession(1, 0, TODAY + DAY), ShiftItem(1, 1),
                 RelocateSession(1, 1, TODAY + 5 * DAY), RelocateSession(2, 0, TODAY),
                 SwapSessions(1, 0, 2, 0), SwapSessions(1, 1, 2, 0), ShiftItem(2, -2)):
        assert apply_move(s, move) is None
    assert apply_move(s, RelocateSession(1, 2, TODAY + 6 * DAY)) is not None


def test_shift_gaps_chain_fanin_and_swaps():
    p = problem(item(1, duration_category='UNDER_8_HOURS'), item(2), item(3), item(4),
                edges=((1, 3), (2, 3), (3, 4)))
    s = state(p, (1, 3), (2,), (5,), (7,))
    n = apply_move(s, ShiftItem(1, 1))
    assert n.completion(1) - n.start(1) == 2 * DAY
    for move in (ShiftItem(1, 2), ShiftItem(3, -2), ShiftItem(3, 2),
                 RelocateSession(2, 0, TODAY + 5 * DAY), SwapSessions(1, 1, 3, 0)):
        assert apply_move(s, move) is None


@pytest.mark.parametrize('day,delta', [(date.max, 1), (date.min, -1)])
def test_calendar_overflow(day, delta):
    p = replace(problem(item()), today=day)
    s = SearchState(p, (SessionPlacement(1, 0, day),))
    assert apply_move(s, ShiftItem(1, delta)) is None
