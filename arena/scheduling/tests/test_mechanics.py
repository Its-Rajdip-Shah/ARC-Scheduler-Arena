from dataclasses import FrozenInstanceError, replace
from datetime import date, timedelta
from decimal import Decimal
import os
import subprocess
import sys

import pytest

from arena.scheduling.domain import DependencyEdge, ScheduleItem, ScheduleProblem
from arena.scheduling.mechanics import (
    ATOMIC, SPLIT_COUNTS, ScheduleState, SessionAction, effective_bucket,
    readiness, session_candidates, session_pieces,
)
from arena.scheduling.validation import validate_plan

TODAY = date(2026, 1, 15)
DAY = timedelta(days=1)


def item(pk=1, **kwargs):
    return replace(ScheduleItem(pk, 'UNDER_1_HOUR', None, None, None, None,
                                Decimal(0), Decimal(1)), **kwargs)


def problem(*items, edges=(), capacity=1, allowed=frozenset()):
    return ScheduleProblem(TODAY, items, tuple(DependencyEdge(*e) for e in edges),
                           {b: capacity for b in (*ATOMIC, *SPLIT_COUNTS)}, allowed)


@pytest.mark.parametrize('bucket,count', [(b, 1) for b in sorted(ATOMIC)] + list(SPLIT_COUNTS.items()))
@pytest.mark.parametrize('fraction', ['1', '.4', '.00001', '0'])
def test_pieces(bucket, count, fraction):
    obj = item(duration_category=bucket, remaining_fraction=Decimal(fraction))
    pieces = session_pieces(obj)
    assert sum(pieces, Decimal(0)) == Decimal(fraction) * 100
    assert all(p > 0 for p in pieces)
    if fraction in ('1', '.4'):
        assert len(pieces) == count
    assert pieces == session_pieces(obj)


def test_residual_and_rounding():
    obj = item(duration_category='OVER_16_HOURS', is_residual=True)
    assert effective_bucket(obj) == 'UNDER_20_MINUTES'
    assert session_pieces(obj) == (Decimal(100),)
    assert session_pieces(replace(obj, is_residual=False)) == tuple(map(Decimal, ['33.33', '33.33', '33.34']))
    with pytest.raises(ValueError):
        session_pieces(item(duration_category='unknown'))


def test_persistent_state_ranks_capacity_completion_and_no_mutation():
    p = problem(item(is_residual=True), item(2, duration_category='UNDER_8_HOURS'))
    original = ScheduleState(p)
    first = original.place(SessionAction(1, 0, TODAY))
    second = first.place(SessionAction(2, 0, TODAY))
    final = second.place(SessionAction(2, 1, TODAY + DAY))
    assert original.allocations == () and not original.usage
    assert first == original.place(SessionAction(1, 0, TODAY))
    assert second.next_rank_by_date[TODAY] == 3
    assert second.usage[TODAY, 'UNDER_20_MINUTES'] == 1
    assert second.usage[TODAY, 'UNDER_8_HOURS'] == 1
    assert 2 not in second.completion
    assert final.completion[2] == TODAY + DAY
    plan = final.to_plan()
    assert validate_plan(p, plan).is_valid
    session_candidates(original, 1, horizon=TODAY)
    assert final.to_plan() == plan and p.items[0].remaining_fraction == 1
    with pytest.raises(TypeError):
        final.usage[TODAY, 'UNDER_8_HOURS'] = 99
    with pytest.raises(FrozenInstanceError):
        final.allocations = ()
    with pytest.raises(ValueError):
        first.place(SessionAction(1, 0, TODAY))
    with pytest.raises(ValueError):
        ScheduleState(p, (replace(first.allocations[0], execution_rank=3),))


def test_fanin_and_partial_prerequisite():
    p = problem(item(), item(2, duration_category='UNDER_8_HOURS'), item(3), edges=((1, 3), (2, 3)))
    state = ScheduleState(p)
    assert readiness(p, state, 3).missing_prerequisites == {1, 2}
    assert session_candidates(state, 3, horizon=TODAY + 5 * DAY) == ()
    with pytest.raises(ValueError):
        state.place(SessionAction(3, 0, TODAY))
    state = state.place(SessionAction(1, 0, TODAY)).place(SessionAction(2, 0, TODAY))
    assert readiness(p, state, 3).missing_prerequisites == {2}
    state = state.place(SessionAction(2, 1, TODAY + 2 * DAY))
    assert readiness(p, state, 3).lower_bound == TODAY + 3 * DAY


@pytest.mark.parametrize('release,expected', [(TODAY - DAY, TODAY), (TODAY + DAY, TODAY + DAY), (None, TODAY)])
def test_release_today(release, expected):
    p = problem(item(release_date=release, anchor_date=TODAY + 5 * DAY))
    assert readiness(p, ScheduleState(p), 1).lower_bound == expected


def test_anchor_and_followups_and_conflict():
    p = problem(item(duration_category='UNDER_8_HOURS', anchor_date=TODAY + DAY, due_date=TODAY))
    state = ScheduleState(p)
    candidates = session_candidates(state, 1)
    assert [c.action.scheduled_date for c in candidates] == [TODAY + DAY]
    state = state.place(candidates[0].action)
    assert [c.action.scheduled_date for c in session_candidates(state, 1, horizon=TODAY + 3 * DAY)] == [TODAY + i * DAY for i in (1, 2, 3)]
    bad = ScheduleState(problem(item(anchor_date=TODAY, release_date=TODAY + DAY)))
    assert session_candidates(bad, 1, horizon=TODAY + DAY) == ()
    with pytest.raises(ValueError):
        bad.place(SessionAction(1, 0, TODAY))


@pytest.mark.parametrize('capacity', [0, 1])
def test_deadline_capacity_soft_and_allowed(capacity):
    p = problem(item(due_date=TODAY + DAY), item(2, due_date=TODAY + DAY),
                capacity=capacity, allowed=frozenset({TODAY}))
    state = ScheduleState(p).place(SessionAction(1, 0, TODAY))
    candidates = session_candidates(state, 2)
    assert [c.action.scheduled_date for c in candidates] == [TODAY, TODAY + DAY]
    assert candidates[0].excess_after == 2 - capacity
    assert candidates[0].overload_allowed
    assert not candidates[1].overload_allowed
    assert candidates == session_candidates(state, 2)
    assert validate_plan(p, state.place(candidates[0].action).to_plan()).is_valid


def test_horizons_missing_capacity_and_late_fallback():
    state = ScheduleState(problem(item()))
    with pytest.raises(ValueError, match='horizon'):
        session_candidates(state, 1)
    assert len(session_candidates(state, 1, horizon=TODAY + 2 * DAY)) == 3
    assert session_candidates(state, 1, horizon=TODAY - DAY) == ()
    late = ScheduleState(problem(item(due_date=TODAY - DAY)))
    with pytest.raises(ValueError, match='horizon'):
        session_candidates(late, 1)
    assert len(session_candidates(late, 1, horizon=TODAY + DAY)) == 2
    missing = ScheduleState(replace(state.problem, capacity_by_duration={}))
    with pytest.raises(ValueError, match='capacity definition'):
        session_candidates(missing, 1, horizon=TODAY)


def test_calendar_boundary():
    p = problem(item(), item(2), edges=((1, 2),))
    state = ScheduleState(p).place(SessionAction(1, 0, date.max))
    ready = readiness(p, state, 2)
    assert ready.lower_bound is None and ready.calendar_exhausted
    assert session_candidates(state, 2, horizon=date.max) == ()
    end = ScheduleState(replace(problem(item(due_date=date.max)), today=date.max))
    assert len(session_candidates(end, 1)) == 1


def test_django_free_import():
    env = dict(os.environ)
    env.pop('DJANGO_SETTINGS_MODULE', None)
    subprocess.run([sys.executable, '-c',
                    "import sys; import arena.scheduling.mechanics; import arena.scheduling.objectives; "
                    "assert not any(k == 'django' or k.startswith('django.') for k in sys.modules); "
                    "assert 'arena.evaluation.performance' not in sys.modules"], env=env, check=True)


def test_rejects_invalid_actions_without_repair():
    p = problem(item(duration_category='UNDER_8_HOURS'))
    state = ScheduleState(p)
    with pytest.raises(ValueError):
        state.place(SessionAction(1, 1, TODAY))
    with pytest.raises(ValueError):
        state.place(SessionAction(1, 0, TODAY - DAY))
    partial = state.place(SessionAction(1, 0, TODAY + DAY))
    with pytest.raises(ValueError):
        partial.place(SessionAction(1, 1, TODAY))
    final = partial.place(SessionAction(1, 1, TODAY + DAY))
    assert final.usage[TODAY + DAY, 'UNDER_8_HOURS'] == 2
    assert validate_plan(p, final.to_plan()).is_valid
    assert session_candidates(final, 1, horizon=TODAY + DAY) == ()
    with pytest.raises(ValueError, match='different problem'):
        readiness(problem(item(2)), state, 2)


@pytest.mark.parametrize('bucket,count', [(b, 1) for b in sorted(ATOMIC)] + list(SPLIT_COUNTS.items()))
def test_conservation_at_tiny_fraction_rounding_boundaries(bucket, count):
    from arena.algorithms.earliest_feasible import EarliestFeasible

    # Dense sweep crosses .005 percentage rounding ties and the historical
    # three-session failure interval (.00015, .00020) remaining fraction.
    fractions = [Decimal(n) / Decimal(1000000) for n in range(1, 501)]
    fractions += [Decimal(value) for value in (
        '0', '1e-100', '.0001499999999999999999999999999',
        '.00015', '.0001500000000000000000000000001', '.00016',
        '.0001999999999999999999999999999', '.0002', '.0002000000000000000000000000001',
        '.4', '1',
    )]
    for fraction in fractions:
        obj = item(duration_category=bucket, remaining_fraction=fraction)
        expected = fraction * Decimal(100)
        pieces = session_pieces(obj)
        assert sum(pieces, Decimal(0)) == expected
        assert all(piece > 0 for piece in pieces)
        assert len(pieces) <= count
        assert pieces == session_pieces(obj)
        legacy = EarliestFeasible._pieces(obj)
        if sum(legacy, Decimal(0)) == expected:
            assert pieces == legacy
        state = ScheduleState(problem(obj))
        for index in range(len(pieces)):
            candidates = session_candidates(state, 1, horizon=TODAY + 3 * DAY)
            action = next(c.action for c in candidates if c.action.scheduled_date == TODAY + index * DAY)
            state = state.place(action)
            assert sum((row.percentage for row in state.allocations), Decimal(0)) <= expected
        assert sum((row.percentage for row in state.allocations), Decimal(0)) == expected
        if fraction:
            assert state.completion[1] == TODAY + (len(pieces) - 1) * DAY
        else:
            assert pieces == () and not state.completion


def test_tiny_rounding_failure_collapses_without_fabricating_work():
    obj = item(duration_category='OVER_16_HOURS', remaining_fraction=Decimal('.00016'))
    assert session_pieces(obj) == (Decimal('.016'),)


def test_unapproved_overload_remains_soft_and_readiness_anchor_stays_hard():
    p = problem(item(due_date=TODAY), item(2, due_date=TODAY))
    state = ScheduleState(p).place(SessionAction(1, 0, TODAY))
    candidate, = session_candidates(state, 2)
    assert candidate.excess_after == 1 and not candidate.overload_allowed
    result = validate_plan(p, state.place(candidate.action).to_plan())
    assert result.is_valid
    assert any(v.code == 'capacity_exceeded' for v in result.soft_violations)
    anchored = ScheduleState(problem(item(anchor_date=TODAY + DAY)))
    with pytest.raises(ValueError, match='Anchor'):
        anchored.place(SessionAction(1, 0, TODAY))
