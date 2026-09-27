from dataclasses import FrozenInstanceError, replace
from decimal import Decimal
import pytest
from arena.search import SearchState, SessionPlacement
from arena.scheduling.domain import SchedulePlan
from arena.scheduling.mechanics import session_pieces
from arena.scheduling.validation import validate_plan
from .helpers import TODAY, DAY, item, problem, state


@pytest.mark.parametrize('bucket', ['UNDER_1_HOUR', 'UNDER_8_HOURS', 'OVER_16_HOURS'])
@pytest.mark.parametrize('fraction', ['1', '.4', '.00001', '0'])
def test_roundtrip(bucket, fraction):
    i = item(duration_category=bucket, remaining_fraction=Decimal(fraction))
    p = problem(i)
    s = state(p, tuple(range(len(session_pieces(i)))))
    plan = s.to_plan()
    before = repr((p, plan, s))
    assert SearchState.from_plan(p, plan) == s
    assert tuple(r.percentage for r in plan.allocations) == session_pieces(i)
    assert not validate_plan(p, plan).violations
    assert repr((p, plan, s)) == before
    assert hash(s) == hash(SearchState.from_plan(p, plan))
    with pytest.raises(FrozenInstanceError):
        s.placements = ()


def test_normalization_ranks_order_and_helpers():
    s = state(problem(item(1), item(2, duration_category='OVER_16_HOURS')), (0,), (0, 0, 1))
    plan = s.to_plan()
    # Reverse inter-item rank order while preserving within-item piece order.
    rows = tuple(replace(r, execution_rank={1: 3, 2: 1, 3: 2}[r.execution_rank])
                 if r.scheduled_date == TODAY else r for r in reversed(plan.allocations))
    assert SearchState.from_plan(s.problem, SchedulePlan(rows)) == s
    assert [r.execution_rank for r in plan.allocations] == [1, 2, 3, 1]
    assert s.start(2) == TODAY and s.completion(2) == TODAY + DAY
    assert s.session_date(2, 1) == TODAY
    assert s.usage(TODAY, 'OVER_16_HOURS') == 2
    with pytest.raises(TypeError):
        s.placements_by_item[1] = ()


@pytest.mark.parametrize('rows', [(), ((1, 0, 0), (1, 0, 1)), ((9, 0, 0),),
                                    ((1, 1, 0),), ((1, 0, -1),)])
def test_reject_bad_identities_dates(rows):
    with pytest.raises(ValueError):
        SearchState(problem(item()), tuple(SessionPlacement(a, b, TODAY + c * DAY) for a, b, c in rows))


@pytest.mark.parametrize('change', ['missing', 'extra', 'percentage', 'rank'])
def test_reject_malformed_plan(change):
    s = state(problem(item(duration_category='OVER_16_HOURS')), (0, 0, 1))
    rows = s.to_plan().allocations
    if change == 'missing': rows = rows[:-1]
    if change == 'extra': rows += (replace(rows[-1], execution_rank=9),)
    if change == 'percentage': rows = (replace(rows[0], percentage=Decimal('33.34')), rows[1], replace(rows[2], percentage=Decimal('33.33')))
    if change == 'rank': rows = (rows[0], replace(rows[1], execution_rank=1), rows[2])
    with pytest.raises(ValueError):
        SearchState.from_plan(s.problem, SchedulePlan(rows))


def test_soft_valid_and_canonical_infeasibility():
    s = state(problem(item(1, due_date=TODAY), item(2), capacity=0), (2,), (2,))
    assert SearchState.from_plan(s.problem, s.to_plan()) == s
    assert validate_plan(s.problem, s.to_plan()).soft_violations
    p = replace(s.problem, items=(item(1, anchor_date=TODAY + 2 * DAY), item(2)),
                dependencies=problem(item(1), item(2), edges=((1, 2),)).dependencies)
    result = validate_plan(p, s.to_plan())
    assert result.infeasibilities and not result.violations
    with pytest.raises(ValueError, match='Canonical infeasibilities'):
        SearchState.from_plan(p, s.to_plan())


@pytest.mark.parametrize('p,days', [
    (problem(item(release_date=TODAY + DAY)), (0,)),
    (problem(item(anchor_date=TODAY)), (1,)),
    (problem(item(duration_category='UNDER_8_HOURS')), (2, 1)),
])
def test_direct_hard_checks(p, days):
    with pytest.raises(ValueError): state(p, days)
