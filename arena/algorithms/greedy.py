"""Session-at-a-time configurable constructors over the frozen C2 mechanics."""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, timedelta
from enum import Enum
from math import isfinite
from typing import ClassVar

from arena.scheduling.domain import ScheduleItem, SchedulePlan, ScheduleProblem
from arena.scheduling.mechanics import (
    ScheduleState, SessionCandidate, readiness, session_candidates, session_pieces,
)
from arena.scheduling.objectives import (
    DeadlineRisk, MovementCost, OverloadCost, PowerCost, PriorityPostponement,
    capacity_overload, deadline_risk, movement, priority_postponement, timing_preference,
)


class ItemSelectionPolicy(str, Enum):
    PRESSURE = 'pressure'
    REGRET = 'regret'


@dataclass(frozen=True, slots=True)
class GreedyObjectiveConfig:
    """All weights are required experimental inputs, never optimal defaults."""
    deadline: DeadlineRisk
    priority: PriorityPostponement
    overload: OverloadCost
    movement: MovementCost
    timing: PowerCost
    horizon_days: int

    def __post_init__(self) -> None:
        if type(self.horizon_days) is not int or self.horizon_days < 0:
            raise ValueError('horizon_days must be a nonnegative integer')


def _priority(item: ScheduleItem) -> tuple[bool, int]:
    return (item.priority_position is None, item.priority_position or 0)


def downstream_anchor_completion_limits(
    problem: ScheduleProblem,
) -> dict[int, date]:
    """Latest completion dates required by downstream anchored work.

    Dependencies impose a strict next-day readiness rule. Therefore, if a
    dependent is anchored on day D, each direct prerequisite must complete no
    later than D - 1 day.

    Propagate those upper bounds backwards through the dependency DAG. Because
    C2 permits all remaining sessions of one item on the same day, a
    non-anchored dependent whose latest feasible completion is L can itself
    start and complete on L, so each prerequisite must complete by L - 1.

    These are hard-feasibility bounds, not optimisation preferences.
    """
    limits: dict[int, date] = {}

    for item_id in reversed(problem.topological_order()):
        candidates: list[date] = []

        for dependent_id in sorted(
            problem.direct_dependents(item_id)
        ):
            dependent = problem.item_by_id[dependent_id]

            if dependent.anchor_date is not None:
                dependent_latest_start = dependent.anchor_date
            else:
                dependent_latest_start = limits.get(dependent_id)

            if dependent_latest_start is None:
                continue

            try:
                candidates.append(
                    dependent_latest_start - timedelta(days=1)
                )
            except OverflowError:
                candidates.append(date.min)

        if candidates:
            limits[item_id] = min(candidates)

    return limits


def pressure_key(state: ScheduleState, item_id: int,
                 candidates: tuple[SessionCandidate, ...], horizon: date) -> tuple:
    """Opportunity minus remaining pieces, window end, readiness, priority, ID.

    Opportunity is the number of legal next-session dates, not a hard capacity
    bound: same-day pieces and soft overload remain legal under C2.
    """
    item = state.problem.item_by_id[item_id]
    remaining = len(session_pieces(item)) - candidates[0].action.session_index
    return (len(candidates) - remaining, min(item.due_date or horizon, horizon),
            readiness(state.problem, state, item_id).lower_bound,
            _priority(item), item_id)


def predicted_completion(state: ScheduleState, candidate: SessionCandidate,
                         horizon: date) -> date | None:
    """Capacity-first earliest continuation in a disposable C2 state.

    At each remaining piece choose earliest normal/allowed capacity; if none
    exists use earliest soft-overload candidate. This is an estimate conditional
    on current usage, not a reservation or a guarantee against future contention.
    """
    probe = state.place(candidate.action)
    item_id = candidate.action.item_id
    while item_id not in probe.completion:
        options = session_candidates(probe, item_id, horizon=horizon)
        if not options:
            return None
        chosen = min(options, key=lambda c: (
            c.excess_after > 0 and not c.overload_allowed, c.action.scheduled_date))
        probe = probe.place(chosen.action)
    return probe.completion[item_id]


@dataclass(frozen=True, slots=True)
class CandidateCost:
    deadline: float
    priority: float
    overload: float
    movement: float
    timing: float

    @property
    def total(self) -> float:
        return self.deadline + self.priority + self.overload + self.movement + self.timing


def candidate_cost(state: ScheduleState, candidate: SessionCandidate,
                   config: GreedyObjectiveConfig, horizon: date) -> CandidateCost:
    item = state.problem.item_by_id[candidate.action.item_id]
    day = candidate.action.scheduled_date
    first = candidate.action.session_index == 0
    ready = readiness(state.problem, state, item.item_id).lower_bound
    assert ready is not None  # Candidates originate exclusively in C2.
    risk = 0.0
    if config.deadline.cost.weight and item.due_date is not None:
        completion = predicted_completion(state, candidate, horizon)
        if completion is None:
            raise ValueError('Candidate has no completion within horizon')
        risk = deadline_risk(item, completion, config.deadline)
    before = capacity_overload(candidate.usage_before, candidate.capacity,
                               allowed=candidate.overload_allowed, config=config.overload)
    after = capacity_overload(candidate.usage_before + 1, candidate.capacity,
                              allowed=candidate.overload_allowed, config=config.overload)
    cost = CandidateCost(
        risk,
        priority_postponement(item, day, ready, config.priority) if first else 0.0,
        after - before,
        movement(item, day, config.movement) if first else 0.0,
        timing_preference(day, ready, config.timing) if first else 0.0,
    )
    if not all(isfinite(v) for v in (cost.deadline, cost.priority, cost.overload,
                                    cost.movement, cost.timing, cost.total)):
        raise ValueError('Candidate objective must be finite; reduce cost parameters')
    return cost


def _candidate_key(candidate: SessionCandidate, cost: CandidateCost,
                   item: ScheduleItem) -> tuple:
    return (cost.total, cost.deadline, cost.movement, candidate.action.scheduled_date,
            _priority(item), item.item_id)


@dataclass(frozen=True, slots=True)
class GreedyConstructor:
    """Configurable engine; named families fix the item policy, never weights."""
    config: GreedyObjectiveConfig
    item_policy: ClassVar[ItemSelectionPolicy] = ItemSelectionPolicy.REGRET
    name: ClassVar[str] = 'configurable-greedy'

    def solve(self, problem: ScheduleProblem) -> SchedulePlan:
        try:
            horizon = problem.today + timedelta(days=self.config.horizon_days)
        except OverflowError as exc:
            raise ValueError('Configured horizon exceeds calendar') from exc
        state = ScheduleState(problem)
        items = sorted(problem.items, key=lambda item: item.item_id)
        anchor_completion_limits = downstream_anchor_completion_limits(problem)
        while True:
            choices = []
            for item in items:
                if not session_pieces(item) or item.item_id in state.completion:
                    continue
                if readiness(problem, state, item.item_id).lower_bound is None:
                    continue
                candidates = session_candidates(state, item.item_id, horizon=horizon)

                latest_completion = anchor_completion_limits.get(
                    item.item_id
                )

                if latest_completion is not None:
                    candidates = tuple(
                        candidate
                        for candidate in candidates
                        if (
                            candidate.action.scheduled_date
                            <= latest_completion
                        )
                    )

                if not candidates:
                    continue
                scored = [(c, candidate_cost(state, c, self.config, horizon)) for c in candidates]
                scored.sort(key=lambda pair: _candidate_key(*pair, item))
                pressure = pressure_key(state, item.item_id, candidates, horizon)
                if self.item_policy == ItemSelectionPolicy.PRESSURE:
                    key = pressure
                else:
                    forced = len(scored) == 1
                    regret = 0.0 if forced else scored[1][1].total - scored[0][1].total
                    key = (not forced, -regret, *pressure)
                choices.append((key, scored[0][0]))
            if not choices:
                break
            chosen = min(choices, key=lambda pair: pair[0])[1]
            state = state.place(chosen.action)
        conflicts = []
        for item in items:
            if not session_pieces(item) or item.item_id in state.completion:
                continue
            ready = readiness(problem, state, item.item_id)
            if ready.missing_prerequisites:
                reason = 'blocked_prerequisites:' + ','.join(map(str, sorted(ready.missing_prerequisites)))
            elif ready.calendar_exhausted:
                reason = 'readiness_exceeds_calendar'
            elif item.anchor_date is not None and ready.lower_bound > item.anchor_date:
                reason = 'anchor_before_readiness'
            else:
                reason = 'no_candidate_within_horizon'
            conflicts.append(f'{item.item_id}:{reason}')
        return replace(state.to_plan(), conflicts=tuple(conflicts), diagnostics=(
            ('constructor', self.name), ('item_policy', self.item_policy.value),
            ('horizon_days', str(self.config.horizon_days)),
            ('status', 'partial_no_legal_progress' if conflicts else 'complete'),
        ))
