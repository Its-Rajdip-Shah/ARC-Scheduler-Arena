"""C11.3 behavioural acceptance cases for production flavours.

These are synthetic contract tests, not benchmark workloads.

They exist to determine whether explicit objective parameters can express
Lock-in and Monk semantics without retuning C7-C10 evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from itertools import product

from arena.scheduling.domain import (
    Allocation,
    ScheduleItem,
    SchedulePlan,
    ScheduleProblem,
)
from arena.scheduling.objectives import (
    DeadlineRisk,
    MovementCost,
    OverloadCost,
    PowerCost,
    PriorityPostponement,
    ThresholdCost,
)
from arena.search.objective import (
    PlanObjectiveConfig,
    score_plan,
)


TODAY = date(2026, 10, 7)


@dataclass(frozen=True, slots=True)
class FlavourParameters:
    timing_weight: float
    continuity_weight: float
    avoidable_idle_weight: float
    same_day_repeat_weight: float
    concentration_weight: float
    concentration_free_sessions: int


@dataclass(frozen=True, slots=True)
class AcceptanceResult:
    case_id: str
    preferred_cost: float
    rejected_cost: float

    @property
    def passes(self) -> bool:
        return self.preferred_cost < self.rejected_cost


def _item(
    item_id: int,
    *,
    duration: str = "UNDER_4_HOURS",
    release_offset: int | None = None,
) -> ScheduleItem:
    return ScheduleItem(
        item_id=item_id,
        duration_category=duration,
        priority_position=None,
        release_date=(
            None
            if release_offset is None
            else TODAY + timedelta(
                days=release_offset
            )
        ),
        due_date=None,
        anchor_date=None,
        percent_completed=Decimal("0"),
        remaining_fraction=Decimal("1"),
    )


def _problem(
    *items: ScheduleItem,
) -> ScheduleProblem:
    return ScheduleProblem(
        today=TODAY,
        items=tuple(items),
        dependencies=(),
        capacity_by_duration={
            "UNDER_20_MINUTES": 10,
            "UNDER_1_HOUR": 10,
            "UNDER_4_HOURS": 10,
            "UNDER_8_HOURS": 10,
            "UNDER_16_HOURS": 10,
            "OVER_16_HOURS": 10,
        },
    )


def _plan(
    *allocations: tuple[
        int,
        int,
        str,
    ],
) -> SchedulePlan:
    return SchedulePlan(
        allocations=tuple(
            Allocation(
                item_id=item_id,
                scheduled_date=(
                    TODAY
                    + timedelta(
                        days=day_offset
                    )
                ),
                percentage=
                    Decimal(percentage),
                execution_rank=index,
            )
            for index, (
                item_id,
                day_offset,
                percentage,
            )
            in enumerate(
                allocations,
                start=1,
            )
        )
    )


def objective_for(
    parameters: FlavourParameters,
) -> PlanObjectiveConfig:
    zero = PowerCost(
        0.0,
        1.0,
    )

    return PlanObjectiveConfig(
        deadline=DeadlineRisk(
            zero,
            0.0,
        ),
        priority=PriorityPostponement(
            zero,
            {},
            0.0,
        ),
        overload=OverloadCost(
            zero,
            False,
        ),
        movement=MovementCost(
            0.0,
            zero,
        ),
        timing=PowerCost(
            parameters.timing_weight,
            1.0,
        ),
        continuity=PowerCost(
            parameters.continuity_weight,
            1.0,
        ),
        avoidable_idle=PowerCost(
            parameters
            .avoidable_idle_weight,
            1.0,
        ),
        same_day_repeat=PowerCost(
            parameters
            .same_day_repeat_weight,
            1.0,
        ),
        daily_concentration=
            ThresholdCost(
                PowerCost(
                    parameters
                    .concentration_weight,
                    2.0,
                ),
                float(
                    parameters
                    .concentration_free_sessions
                ),
            ),
    )


def _cost(
    problem: ScheduleProblem,
    plan: SchedulePlan,
    parameters: FlavourParameters,
) -> float:
    return score_plan(
        problem,
        plan,
        objective_for(parameters),
    ).total


def common_acceptance_cases(
    parameters: FlavourParameters,
) -> tuple[AcceptanceResult, ...]:
    large = _problem(
        _item(
            1,
            duration="OVER_16_HOURS",
        ),
    )

    continuous = _plan(
        (1, 0, "33.33"),
        (1, 1, "33.33"),
        (1, 3, "33.34"),
    )

    scattered = _plan(
        (1, 0, "33.33"),
        (1, 4, "33.33"),
        (1, 8, "33.34"),
    )

    cram = _plan(
        (1, 0, "33.33"),
        (1, 0, "33.33"),
        (1, 0, "33.34"),
    )

    return (
        AcceptanceResult(
            case_id=
                "common_continuity",
            preferred_cost=_cost(
                large,
                continuous,
                parameters,
            ),
            rejected_cost=_cost(
                large,
                scattered,
                parameters,
            ),
        ),
        AcceptanceResult(
            case_id=
                "common_anti_cram",
            preferred_cost=_cost(
                large,
                continuous,
                parameters,
            ),
            rejected_cost=_cost(
                large,
                cram,
                parameters,
            ),
        ),
    )


def lock_in_acceptance_cases(
    parameters: FlavourParameters,
) -> tuple[AcceptanceResult, ...]:
    two_items = _problem(
        _item(1),
        _item(2),
    )

    no_gap = _plan(
        (1, 0, "100"),
        (2, 1, "100"),
    )

    avoidable_gap = _plan(
        (1, 0, "100"),
        (2, 2, "100"),
    )

    tradeoff_problem = _problem(
        _item(1),
        _item(2),
        _item(3),
        _item(4),
    )

    early_heavy = _plan(
        (1, 0, "100"),
        (2, 0, "100"),
        (3, 0, "100"),
        (4, 1, "100"),
    )

    smoother_later = _plan(
        (1, 0, "100"),
        (2, 0, "100"),
        (3, 1, "100"),
        (4, 1, "100"),
    )

    return (
        AcceptanceResult(
            case_id=
                "lock_in_avoid_idle",
            preferred_cost=_cost(
                two_items,
                no_gap,
                parameters,
            ),
            rejected_cost=_cost(
                two_items,
                avoidable_gap,
                parameters,
            ),
        ),
        AcceptanceResult(
            case_id=
                "lock_in_prefers_earlier_progress",
            preferred_cost=_cost(
                tradeoff_problem,
                early_heavy,
                parameters,
            ),
            rejected_cost=_cost(
                tradeoff_problem,
                smoother_later,
                parameters,
            ),
        ),
    )


def monk_acceptance_cases(
    parameters: FlavourParameters,
) -> tuple[AcceptanceResult, ...]:
    smooth_problem = _problem(
        *(
            _item(item_id)
            for item_id in range(
                1,
                8,
            )
        )
    )

    heavy = _plan(
        (1, 0, "100"),
        (2, 0, "100"),
        (3, 0, "100"),
        (4, 0, "100"),
        (5, 0, "100"),
        (6, 0, "100"),
        (7, 1, "100"),
    )

    smooth = _plan(
        (1, 0, "100"),
        (2, 0, "100"),
        (3, 0, "100"),
        (4, 1, "100"),
        (5, 1, "100"),
        (6, 1, "100"),
        (7, 2, "100"),
    )

    tradeoff_problem = _problem(
        _item(1),
        _item(2),
        _item(3),
        _item(4),
    )

    early_heavy = _plan(
        (1, 0, "100"),
        (2, 0, "100"),
        (3, 0, "100"),
        (4, 1, "100"),
    )

    smoother_later = _plan(
        (1, 0, "100"),
        (2, 0, "100"),
        (3, 1, "100"),
        (4, 1, "100"),
    )

    return (
        AcceptanceResult(
            case_id=
                "monk_smooths_heavy_day",
            preferred_cost=_cost(
                smooth_problem,
                smooth,
                parameters,
            ),
            rejected_cost=_cost(
                smooth_problem,
                heavy,
                parameters,
            ),
        ),
        AcceptanceResult(
            case_id=
                "monk_prefers_smooth_over_earliest",
            preferred_cost=_cost(
                tradeoff_problem,
                smoother_later,
                parameters,
            ),
            rejected_cost=_cost(
                tradeoff_problem,
                early_heavy,
                parameters,
            ),
        ),
    )


def evaluate_parameters(
    flavour: str,
    parameters: FlavourParameters,
) -> tuple[AcceptanceResult, ...]:
    common = (
        common_acceptance_cases(
            parameters
        )
    )

    if flavour == "lock-in":
        specific = (
            lock_in_acceptance_cases(
                parameters
            )
        )
    elif flavour == "monk":
        specific = (
            monk_acceptance_cases(
                parameters
            )
        )
    else:
        raise ValueError(
            f"Unknown flavour: {flavour}"
        )

    return common + specific


def satisfies_flavour(
    flavour: str,
    parameters: FlavourParameters,
) -> bool:
    return all(
        result.passes
        for result
        in evaluate_parameters(
            flavour,
            parameters,
        )
    )


def parameter_grid(
) -> tuple[FlavourParameters, ...]:
    """Small deterministic grid.

    This is behavioural feasibility exploration, not benchmark tuning.
    """

    rows = []

    for (
        timing,
        continuity,
        idle,
        repeat,
        concentration,
        threshold,
    ) in product(
        (0.0, 1.0, 2.0, 4.0),
        (1.0, 2.0, 4.0, 8.0),
        (0.0, 1.0, 2.0, 4.0),
        (1.0, 2.0, 4.0, 8.0),
        (0.0, 1.0, 2.0, 4.0, 8.0),
        (2, 3, 4),
    ):
        rows.append(
            FlavourParameters(
                timing_weight=timing,
                continuity_weight=
                    continuity,
                avoidable_idle_weight=
                    idle,
                same_day_repeat_weight=
                    repeat,
                concentration_weight=
                    concentration,
                concentration_free_sessions=
                    threshold,
            )
        )

    return tuple(rows)
