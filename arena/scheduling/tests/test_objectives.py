from dataclasses import FrozenInstanceError, replace
from datetime import date, timedelta
from decimal import Decimal

import pytest

from arena.scheduling.domain import ScheduleItem
from arena.scheduling.objectives import (
    DeadlineRisk, MovementCost, OverloadCost, PowerCost, PriorityPostponement,
    capacity_overload, deadline_risk, movement, priority_postponement, timing_preference,
)

TODAY = date(2026, 1, 15)
DAY = timedelta(days=1)
ITEM = ScheduleItem(1, 'UNDER_1_HOUR', 1, None, TODAY + 5 * DAY, None,
                    Decimal(0), Decimal(1), existing_scheduled_date=TODAY)


@pytest.mark.parametrize('offset,expected', [(0, 0), (-2, 11), (2, 11)])
def test_movement(offset, expected):
    assert movement(ITEM, TODAY + offset * DAY, MovementCost(3, PowerCost(2, 2))) == expected
    assert movement(replace(ITEM, existing_scheduled_date=None), TODAY, MovementCost(3, PowerCost(2, 2))) == 0


def test_overload_convexity_and_exemptions():
    cfg = OverloadCost(PowerCost(1, 2), True)
    assert capacity_overload(5, 1, allowed=False, config=cfg) > 4 * capacity_overload(2, 1, allowed=False, config=cfg)
    assert capacity_overload(5, 1, allowed=True, config=cfg) == 0
    assert capacity_overload(5, 1, allowed=True, config=replace(cfg, exempt_allowed_dates=False)) == 16
    assert capacity_overload(2, 0, allowed=False, config=cfg) == 4
    with pytest.raises(ValueError):
        capacity_overload(2, None, allowed=False, config=cfg)


def test_priority_orientation_and_configuration():
    weights = {1: 5, 2: 2}
    cfg = PriorityPostponement(PowerCost(2, 1), weights, 0)
    weights[1] = 0
    assert priority_postponement(ITEM, TODAY + DAY, TODAY, cfg) == 10
    assert priority_postponement(replace(ITEM, priority_position=2), TODAY + DAY, TODAY, cfg) == 4
    assert priority_postponement(ITEM, TODAY, TODAY, cfg) == 0
    with pytest.raises(TypeError):
        cfg.multipliers[1] = 0
    with pytest.raises(ValueError):
        PriorityPostponement(PowerCost(1, 1), {1: 1, 2: 2}, 0)


def test_deadline_and_timing_orientation():
    cfg = DeadlineRisk(PowerCost(2, 2), 3)
    values = [deadline_risk(ITEM, TODAY + n * DAY, cfg) for n in (2, 3, 4, 5, 6)]
    assert values == [0, 2, 8, 18, 32]
    assert deadline_risk(replace(ITEM, due_date=None), TODAY, cfg) == 0
    assert timing_preference(TODAY, TODAY, PowerCost(1, 2)) < timing_preference(TODAY + DAY, TODAY, PowerCost(1, 2))
    assert timing_preference(TODAY, TODAY + DAY, PowerCost(1, 2)) > timing_preference(TODAY + DAY, TODAY + DAY, PowerCost(1, 2))


def test_zero_weights_short_circuit_and_independent_components():
    zero = PowerCost(0, 10000)
    assert deadline_risk(ITEM, date.max, DeadlineRisk(zero, 3)) == 0
    assert priority_postponement(ITEM, date.max, TODAY, PriorityPostponement(zero, {}, 0)) == 0
    assert capacity_overload(9999, None, allowed=False, config=OverloadCost(zero, False)) == 0
    assert movement(ITEM, date.max, MovementCost(0, zero)) == 0
    assert movement(ITEM, date.max, MovementCost(3, zero)) == 3
    assert timing_preference(date.max, TODAY, zero) == 0
    with pytest.raises(FrozenInstanceError):
        zero.weight = 1


@pytest.mark.parametrize('weight,exponent', [(-1, 1), (1, 0), (1, -1), (float('nan'), 1), (1, float('inf'))])
def test_invalid_configuration(weight, exponent):
    with pytest.raises(ValueError):
        PowerCost(weight, exponent)
