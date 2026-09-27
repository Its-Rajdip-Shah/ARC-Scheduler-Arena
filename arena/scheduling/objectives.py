"""Independent configurable cost primitives, never a feasibility test or evaluator.

All costs are minimized. No aggregate formula or winning parameters are supplied.

C11 adds human-shape primitives with zero-default integration in the whole-plan
objective. They remain soft preferences and never redefine C2 legality.
"""
from dataclasses import dataclass
from datetime import date
from math import isfinite
from types import MappingProxyType
from typing import Mapping

from arena.scheduling.domain import ScheduleItem


def _nonnegative(**values: float) -> None:
    if any(
        not isfinite(value) or value < 0
        for value in values.values()
    ):
        raise ValueError(
            'Parameters must be finite and nonnegative'
        )


@dataclass(frozen=True, slots=True)
class PowerCost:
    """Explicit weight and positive power; no default experimental settings."""

    weight: float
    exponent: float

    def __post_init__(self) -> None:
        _nonnegative(
            weight=self.weight,
            exponent=self.exponent,
        )

        if self.exponent == 0:
            raise ValueError(
                'Exponent must be positive'
            )


@dataclass(frozen=True, slots=True)
class ThresholdCost:
    """Powered excess above a soft, explicitly configured free threshold."""

    cost: PowerCost
    free_units: float

    def __post_init__(self) -> None:
        _nonnegative(
            free_units=self.free_units,
        )


@dataclass(frozen=True, slots=True)
class DeadlineRisk:
    cost: PowerCost
    buffer_days: float

    def __post_init__(self) -> None:
        _nonnegative(
            buffer_days=self.buffer_days
        )


@dataclass(frozen=True, slots=True)
class PriorityPostponement:
    cost: PowerCost
    multipliers: Mapping[int, float]
    unpositioned_multiplier: float

    def __post_init__(self) -> None:
        multipliers = dict(
            self.multipliers
        )

        _nonnegative(
            unpositioned=
                self.unpositioned_multiplier,
            **{
                str(k): v
                for k, v
                in multipliers.items()
            },
        )

        ordered = sorted(
            multipliers
        )

        if any(
            multipliers[a]
            < multipliers[b]
            for a, b
            in zip(
                ordered,
                ordered[1:],
            )
        ):
            raise ValueError(
                'Smaller priority positions '
                'must have at least as much weight'
            )

        object.__setattr__(
            self,
            'multipliers',
            MappingProxyType(
                multipliers
            ),
        )


@dataclass(frozen=True, slots=True)
class OverloadCost:
    cost: PowerCost
    exempt_allowed_dates: bool


@dataclass(frozen=True, slots=True)
class MovementCost:
    fixed_weight: float
    distance: PowerCost

    def __post_init__(self) -> None:
        _nonnegative(
            fixed_weight=
                self.fixed_weight
        )


def powered_count(
    value: int | float,
    config: PowerCost,
) -> float:
    """Generic powered nonnegative count cost."""

    if value < 0:
        raise ValueError(
            'Count-like objective value '
            'must be nonnegative'
        )

    if config.weight == 0:
        return 0.0

    return (
        config.weight
        * value ** config.exponent
    )


def threshold_excess(
    value: int | float,
    config: ThresholdCost,
) -> float:
    """Powered excess above a soft threshold."""

    if value < 0:
        raise ValueError(
            'Thresholded objective value '
            'must be nonnegative'
        )

    if config.cost.weight == 0:
        return 0.0

    excess = max(
        0.0,
        value - config.free_units,
    )

    return (
        config.cost.weight
        * excess ** config.cost.exponent
    )


def continuity_gap(
    earlier: date,
    later: date,
    config: PowerCost,
) -> float:
    """Cost idle calendar days between consecutive sessions of one item.

    Consecutive-day sessions have zero gap. Same-day sessions also have zero
    continuity cost; same-day cramming is measured separately.
    """

    if later < earlier:
        raise ValueError(
            'Session dates must be nondecreasing'
        )

    gap_days = max(
        0,
        (later - earlier).days - 1,
    )

    return powered_count(
        gap_days,
        config,
    )


def same_day_repeat(
    session_count: int,
    config: PowerCost,
) -> float:
    """Cost extra sessions of the same item placed on one calendar day."""

    if type(session_count) is not int:
        raise TypeError(
            'session_count must be int'
        )

    if session_count < 0:
        raise ValueError(
            'session_count must be nonnegative'
        )

    extra = max(
        0,
        session_count - 1,
    )

    return powered_count(
        extra,
        config,
    )


def daily_session_concentration(
    session_count: int,
    config: ThresholdCost,
) -> float:
    """Human-shape cost for sessions above a configured comfortable day load.

    This is deliberately separate from C2 per-duration capacity overload.
    It is a soft production preference, not a legality rule.
    """

    if type(session_count) is not int:
        raise TypeError(
            'session_count must be int'
        )

    return threshold_excess(
        session_count,
        config,
    )


def deadline_risk(
    item: ScheduleItem,
    completion: date,
    config: DeadlineRisk,
) -> float:
    """Weighted powered buffer deficit; signed slack = due minus completion."""

    if (
        config.cost.weight == 0
        or item.due_date is None
    ):
        return 0.0

    slack = (
        item.due_date - completion
    ).days

    return (
        config.cost.weight
        * max(
            0,
            config.buffer_days - slack,
        ) ** config.cost.exponent
    )


def priority_postponement(
    item: ScheduleItem,
    start: date,
    ready: date,
    config: PriorityPostponement,
) -> float:
    """Weighted delay from readiness, with explicit position multipliers."""

    if config.cost.weight == 0:
        return 0.0

    multiplier = (
        config.unpositioned_multiplier
        if item.priority_position is None
        else config.multipliers[
            item.priority_position
        ]
    )

    if multiplier == 0:
        return 0.0

    return (
        config.cost.weight
        * multiplier
        * max(
            0,
            (start - ready).days,
        ) ** config.cost.exponent
    )


def capacity_overload(
    usage: int,
    capacity: int | None,
    *,
    allowed: bool,
    config: OverloadCost,
) -> float:
    """Cost of one bucket/day, not a delta; missing capacity is unknown."""

    if (
        config.cost.weight == 0
        or (
            allowed
            and config.exempt_allowed_dates
        )
    ):
        return 0.0

    if capacity is None:
        raise ValueError(
            'Cannot score undefined capacity'
        )

    return (
        config.cost.weight
        * max(
            0,
            usage - capacity,
        ) ** config.cost.exponent
    )


def movement(
    item: ScheduleItem,
    start: date,
    config: MovementCost,
) -> float:
    """One item-start cost, symmetric for earlier/later movement."""

    if (
        config.fixed_weight == 0
        and config.distance.weight == 0
    ):
        return 0.0

    if (
        item.existing_scheduled_date
        is None
        or start
        == item.existing_scheduled_date
    ):
        return 0.0

    distance = abs(
        (
            start
            - item.existing_scheduled_date
        ).days
    )

    variable = (
        0.0
        if config.distance.weight == 0
        else (
            config.distance.weight
            * distance
            ** config.distance.exponent
        )
    )

    return (
        config.fixed_weight
        + variable
    )


def timing_preference(
    start: date,
    target: date,
    config: PowerCost,
) -> float:
    """Powered distance from an explicit preferred date (e.g. readiness)."""

    if config.weight == 0:
        return 0.0

    return (
        config.weight
        * abs(
            (start - target).days
        ) ** config.exponent
    )
