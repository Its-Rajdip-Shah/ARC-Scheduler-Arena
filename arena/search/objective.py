"""Whole-plan objective built only from explicit soft cost primitives.

C11 human-shape terms are optional and default to zero. Existing C1-C10
objective configurations therefore retain identical numerical semantics.
"""
from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta
from math import isfinite

from arena.scheduling.domain import (
    SchedulePlan,
    ScheduleProblem,
)
from arena.scheduling.mechanics import (
    effective_bucket,
)
from arena.scheduling.objectives import (
    DeadlineRisk,
    MovementCost,
    OverloadCost,
    PowerCost,
    PriorityPostponement,
    ThresholdCost,
    capacity_overload,
    continuity_gap,
    daily_session_concentration,
    deadline_risk,
    movement,
    powered_count,
    priority_postponement,
    same_day_repeat,
    timing_preference,
)

from .state import SearchState


ZERO_POWER = PowerCost(
    0.0,
    1.0,
)

ZERO_THRESHOLD = ThresholdCost(
    ZERO_POWER,
    0.0,
)


@dataclass(frozen=True, slots=True)
class PlanObjectiveConfig:
    deadline: DeadlineRisk
    priority: PriorityPostponement
    overload: OverloadCost
    movement: MovementCost
    timing: PowerCost

    # C11 production-flavour vocabulary.
    # Zero defaults preserve every pre-C11 objective exactly.
    continuity: PowerCost = ZERO_POWER
    avoidable_idle: PowerCost = ZERO_POWER
    same_day_repeat: PowerCost = ZERO_POWER
    daily_concentration: ThresholdCost = ZERO_THRESHOLD


@dataclass(frozen=True, slots=True)
class PlanObjective:
    deadline: float
    priority: float
    overload: float
    movement: float
    timing: float

    continuity: float = 0.0
    avoidable_idle: float = 0.0
    same_day_repeat: float = 0.0
    daily_concentration: float = 0.0

    def __post_init__(self) -> None:
        if not all(
            isfinite(value)
            for value in (
                self.deadline,
                self.priority,
                self.overload,
                self.movement,
                self.timing,
                self.continuity,
                self.avoidable_idle,
                self.same_day_repeat,
                self.daily_concentration,
                self.total,
            )
        ):
            raise ValueError(
                'Whole-plan objective '
                'must be finite'
            )

    @property
    def total(self) -> float:
        return (
            self.deadline
            + self.priority
            + self.overload
            + self.movement
            + self.timing
            + self.continuity
            + self.avoidable_idle
            + self.same_day_repeat
            + self.daily_concentration
        )


def _readiness_by_item(
    state: SearchState,
) -> dict[int, date]:
    groups = (
        state.placements_by_item
    )

    items = (
        state.problem.item_by_id
    )

    readiness = {
        item_id: max(
            state.problem.today,
            items[item_id].release_date
            or state.problem.today,
        )
        for item_id in groups
    }

    for edge in (
        state.problem.dependencies
    ):
        if (
            edge.prerequisite_id
            in groups
            and edge.dependent_id
            in groups
        ):
            readiness[
                edge.dependent_id
            ] = max(
                readiness[
                    edge.dependent_id
                ],
                groups[
                    edge.prerequisite_id
                ][-1]
                .scheduled_date
                + timedelta(days=1),
            )

    return readiness


def _avoidable_idle_day_count(
    state: SearchState,
    readiness: dict[int, date],
) -> int:
    """Count empty days before final work where later work could start/continue.

    This is a soft observational notion of an unnecessary idle day.

    Capacity is intentionally not a hard gate here because C2 capacity is soft.
    Anchored first sessions remain fixed and therefore do not make earlier
    empty days avoidable.
    """

    if not state.placements:
        return 0

    groups = (
        state.placements_by_item
    )

    items = (
        state.problem.item_by_id
    )

    active_days = {
        placement.scheduled_date
        for placement
        in state.placements
    }

    final_day = max(
        active_days
    )

    count = 0
    day = state.problem.today

    while day < final_day:
        if day not in active_days:
            avoidable = False

            for item_id, rows in (
                groups.items()
            ):
                item = items[
                    item_id
                ]

                for index, row in enumerate(
                    rows
                ):
                    if (
                        row.scheduled_date
                        <= day
                    ):
                        continue

                    lower = readiness[
                        item_id
                    ]

                    if index > 0:
                        lower = max(
                            lower,
                            rows[
                                index - 1
                            ].scheduled_date,
                        )

                    if (
                        index == 0
                        and item.anchor_date
                        is not None
                    ):
                        continue

                    if day >= lower:
                        avoidable = True
                        break

                if avoidable:
                    break

            count += int(
                avoidable
            )

        day += timedelta(
            days=1
        )

    return count


def score_state(
    state: SearchState,
    config: PlanObjectiveConfig,
) -> PlanObjective:
    if not isinstance(
        state,
        SearchState,
    ):
        raise TypeError(
            'Expected a complete SearchState'
        )

    groups = (
        state.placements_by_item
    )

    items = (
        state.problem.item_by_id
    )

    readiness = (
        _readiness_by_item(
            state
        )
    )

    deadline = 0.0
    priority = 0.0
    moved = 0.0
    timing = 0.0
    continuity = 0.0

    try:
        for item_id, rows in (
            groups.items()
        ):
            item = items[
                item_id
            ]

            start = (
                rows[0].scheduled_date
            )

            ready = readiness[
                item_id
            ]

            deadline += deadline_risk(
                item,
                rows[-1].scheduled_date,
                config.deadline,
            )

            priority += priority_postponement(
                item,
                start,
                ready,
                config.priority,
            )

            moved += movement(
                item,
                start,
                config.movement,
            )

            timing += timing_preference(
                start,
                ready,
                config.timing,
            )

            for earlier, later in zip(
                rows,
                rows[1:],
            ):
                continuity += (
                    continuity_gap(
                        earlier.scheduled_date,
                        later.scheduled_date,
                        config.continuity,
                    )
                )

        bucket_usage = Counter(
            (
                placement.scheduled_date,
                effective_bucket(
                    items[
                        placement.item_id
                    ]
                ),
            )
            for placement
            in state.placements
        )

        overload = sum(
            capacity_overload(
                count,
                state.problem
                .capacity_by_duration
                .get(bucket),
                allowed=(
                    day
                    in state.problem
                    .overload_dates
                ),
                config=config.overload,
            )
            for (
                day,
                bucket,
            ), count
            in sorted(
                bucket_usage.items()
            )
        )

        item_day_usage = Counter(
            (
                placement.item_id,
                placement.scheduled_date,
            )
            for placement
            in state.placements
        )

        repeat_cost = sum(
            same_day_repeat(
                count,
                config.same_day_repeat,
            )
            for count
            in item_day_usage.values()
        )

        day_usage = Counter(
            placement.scheduled_date
            for placement
            in state.placements
        )

        concentration = sum(
            daily_session_concentration(
                count,
                config.daily_concentration,
            )
            for count
            in day_usage.values()
        )

        avoidable_idle_count = (
            _avoidable_idle_day_count(
                state,
                readiness,
            )
        )

        idle_cost = powered_count(
            avoidable_idle_count,
            config.avoidable_idle,
        )

        return PlanObjective(
            deadline,
            priority,
            overload,
            moved,
            timing,
            continuity,
            idle_cost,
            repeat_cost,
            concentration,
        )

    except OverflowError as exc:
        raise ValueError(
            'Whole-plan objective '
            'exceeds finite range'
        ) from exc


def score_plan(
    problem: ScheduleProblem,
    plan: SchedulePlan,
    config: PlanObjectiveConfig,
) -> PlanObjective:
    return score_state(
        SearchState.from_plan(
            problem,
            plan,
        ),
        config,
    )


def objective_delta(
    state: SearchState,
    neighbour: SearchState,
    config: PlanObjectiveConfig,
) -> float:
    """Neighbour minus source; negative improves. Recomputes both full scores."""

    if (
        state.problem
        != neighbour.problem
    ):
        raise ValueError(
            'Objective delta requires '
            'the same problem'
        )

    delta = (
        score_state(
            neighbour,
            config,
        ).total
        - score_state(
            state,
            config,
        ).total
    )

    if not isfinite(
        delta
    ):
        raise ValueError(
            'Objective delta '
            'must be finite'
        )

    return delta
