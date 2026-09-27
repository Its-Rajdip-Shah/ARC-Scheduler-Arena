"""Pure C1.3 observational metrics; see docs/performance_metrics.md."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from arena.scheduling.domain import SchedulePlan, ScheduleProblem
from arena.scheduling.validation import ValidationResult


@dataclass(frozen=True, slots=True)
class PerformanceVector:
    hard_violation_count: int
    canonical_infeasibility_count: int
    soft_violation_count: int
    deadline_item_count: int
    deadline_miss_count: int
    deadline_miss_rate: float | None
    mean_lateness_days: float | None
    max_lateness_days: int | None
    priority_item_count: int
    priority_comparison_count: int
    priority_inversion_count: int
    priority_inversion_rate: float | None
    peak_capacity_ratio: float | None
    overloaded_bucket_day_count: int
    excess_session_count: int
    unapproved_overloaded_bucket_day_count: int
    unapproved_excess_session_count: int
    mean_start_delay_days: float | None
    max_start_delay_days: int | None
    zero_wait_rate: float | None
    makespan_days: int | None
    split_item_count: int
    fragmented_item_count: int
    fragmented_item_rate: float | None
    mean_session_gap_days: float | None
    max_session_gap_days: int | None
    dependency_edge_count: int
    mean_dependency_wait_days: float | None
    max_dependency_wait_days: int | None
    immediate_dependency_transition_rate: float | None
    previously_scheduled_item_count: int
    moved_item_count: int
    moved_item_rate: float | None
    total_movement_days: int
    mean_movement_days: float | None
    max_movement_days: int | None
    moved_earlier_item_count: int
    moved_later_item_count: int
    unchanged_item_count: int
    deadline_slack_item_count: int
    mean_completion_slack_days: float | None
    min_completion_slack_days: int | None
    schedulable_window_item_count: int
    mean_relative_window_position: float | None
    front_loaded_item_count: int
    front_loaded_item_rate: float | None
    active_day_count: int
    mean_sessions_per_active_day: float | None
    max_sessions_on_day: int | None
    daily_session_load_variance: float | None


def _ratio(numerator: int | float, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _mean(values: list[int] | list[float]) -> float | None:
    return _ratio(sum(values), len(values))


def evaluate_plan(
    problem: ScheduleProblem,
    plan: SchedulePlan,
    validation: ValidationResult,
) -> PerformanceVector:
    """Observe a proposal without repairing it or reclassifying validation.

    Unknown rows are ignored. Missing dates exclude the item's date metrics;
    incomplete/excess work excludes completion metrics, but observed starts,
    session counts and continuity remain meaningful. Duplicate rows are counted
    as proposed sessions, but repeated item/date/rank keys cannot establish
    completion. Undefined capacities are skipped, never imputed. Quality values
    for invalid plans are diagnostic only, not eligible comparison scores.
    """
    items = problem.item_by_id
    rows = {item_id: [] for item_id in items}
    usage = Counter()
    for row in plan.allocations:
        if row.item_id not in items:
            continue
        rows[row.item_id].append(row)
        if type(row.scheduled_date) is date:
            item = items[row.item_id]
            bucket = "UNDER_20_MINUTES" if item.is_residual else item.duration_category
            usage[row.scheduled_date, bucket] += 1

    # Ordinals avoid overflow when readiness lies beyond date.max.
    starts, completions = {}, {}
    gaps = []
    split_count = fragmented_count = 0
    uncomputable_split = False
    for item_id, allocations in rows.items():
        if len(allocations) >= 2:
            split_count += 1
        if not allocations or any(type(row.scheduled_date) is not date for row in allocations):
            uncomputable_split |= len(allocations) >= 2
            continue
        ordered = sorted(allocations, key=lambda row: (row.scheduled_date, row.execution_rank))
        starts[item_id] = ordered[0].scheduled_date.toordinal()
        total = sum((row.percentage for row in ordered), Decimal(0))
        # Repeated session identities must not turn duplicated partial work
        # into an apparently complete proposal. Keep raw capacity/row counts.
        unique_sessions = len({(row.scheduled_date, row.execution_rank) for row in ordered})
        if (total == items[item_id].remaining_fraction * Decimal(100)
                and unique_sessions == len(ordered)):
            completions[item_id] = ordered[-1].scheduled_date.toordinal()
        item_gaps = [max(0, (b.scheduled_date - a.scheduled_date).days - 1)
                     for a, b in zip(ordered, ordered[1:])]
        gaps.extend(item_gaps)
        fragmented_count += int(any(item_gaps))

    incoming = {item_id: [] for item_id in items}
    for edge in problem.dependencies:
        incoming[edge.dependent_id].append(edge.prerequisite_id)
    ready = {}
    for item_id, item in items.items():
        if all(p in completions for p in incoming[item_id]):
            ready[item_id] = max(
                [max(problem.today, item.release_date or problem.today).toordinal()]
                + [completions[p] + 1 for p in incoming[item_id]]
            )

    deadlines = [item for item in problem.items if item.due_date is not None]
    lateness = [max(0, completions[item.item_id] - item.due_date.toordinal())
                for item in deadlines if item.item_id in completions]
    misses = sum(value > 0 for value in lateness)
    positioned = [item for item in problem.items if item.priority_position is not None]
    comparisons = inversions = 0
    for high in positioned:
        for low in positioned:
            if (high.priority_position < low.priority_position
                    and high.item_id in starts and low.item_id in starts
                    and high.item_id in ready
                    and ready[high.item_id] <= starts[low.item_id]):
                comparisons += 1
                inversions += int(starts[high.item_id] > starts[low.item_id])

    ratios = []
    overloaded = excess = unapproved = unapproved_excess = 0
    for (day, bucket), count in usage.items():
        capacity = problem.capacity_by_duration.get(bucket)
        if capacity is None:
            continue
        if capacity > 0:
            ratios.append(count / capacity)
        cell_excess = max(0, count - capacity)
        overloaded += int(cell_excess > 0)
        excess += cell_excess
        if day not in problem.overload_dates:
            unapproved += int(cell_excess > 0)
            unapproved_excess += cell_excess

    waits = [start - ready[item_id] for item_id, start in starts.items()
             if item_id in ready and start >= ready[item_id]]
    edge_waits = [starts[edge.dependent_id] - completions[edge.prerequisite_id] - 1
                  for edge in problem.dependencies
                  if edge.dependent_id in starts and edge.prerequisite_id in completions
                  and starts[edge.dependent_id] > completions[edge.prerequisite_id]]
    complete_starts = [starts[item_id] for item_id in completions]
    movement = [start - items[item_id].existing_scheduled_date.toordinal()
                for item_id, start in starts.items()
                if items[item_id].existing_scheduled_date is not None]
    distances = [abs(delta) for delta in movement]
    moved = sum(distance > 0 for distance in distances)
    slack = [item.due_date.toordinal() - completions[item.item_id]
             for item in deadlines if item.item_id in completions]

    positions = []
    for item_id, start in starts.items():
        due = items[item_id].due_date
        if due is None or item_id not in ready:
            continue
        width = due.toordinal() - ready[item_id]
        if width > 0:
            positions.append((start - ready[item_id]) / width)
        elif width == 0 and start == ready[item_id]:
            positions.append(0.0)
    front_loaded = sum(position < 0.5 for position in positions)

    # Count the same usable known rows as capacity, across all buckets,
    # including buckets without a capacity definition. No idle days invented.
    daily_usage = Counter()
    for (day, _bucket), count in usage.items():
        daily_usage[day] += count
    loads = list(daily_usage.values())
    mean_load = _mean(loads)
    load_variance = (_mean([(count - mean_load) ** 2 for count in loads])
                     if loads else None)

    return PerformanceVector(
        hard_violation_count=len(validation.violations),
        canonical_infeasibility_count=len(validation.infeasibilities),
        soft_violation_count=len(validation.soft_violations),
        deadline_item_count=len(deadlines),
        deadline_miss_count=misses,
        deadline_miss_rate=_ratio(misses, len(lateness)),
        mean_lateness_days=_mean(lateness),
        max_lateness_days=max(lateness, default=None),
        priority_item_count=len(positioned),
        priority_comparison_count=comparisons,
        priority_inversion_count=inversions,
        priority_inversion_rate=_ratio(inversions, comparisons),
        peak_capacity_ratio=max(ratios, default=None),
        overloaded_bucket_day_count=overloaded,
        excess_session_count=excess,
        unapproved_overloaded_bucket_day_count=unapproved,
        unapproved_excess_session_count=unapproved_excess,
        mean_start_delay_days=_mean(waits),
        max_start_delay_days=max(waits, default=None),
        zero_wait_rate=_ratio(waits.count(0), len(waits)),
        makespan_days=max(completions.values()) - min(complete_starts) + 1 if completions else None,
        split_item_count=split_count,
        fragmented_item_count=fragmented_count,
        fragmented_item_rate=(None if uncomputable_split
                              else _ratio(fragmented_count, split_count)),
        mean_session_gap_days=_mean(gaps),
        max_session_gap_days=max(gaps, default=None),
        dependency_edge_count=len(problem.dependencies),
        mean_dependency_wait_days=_mean(edge_waits),
        max_dependency_wait_days=max(edge_waits, default=None),
        immediate_dependency_transition_rate=_ratio(edge_waits.count(0), len(edge_waits)),
        previously_scheduled_item_count=len(movement),
        moved_item_count=moved,
        moved_item_rate=_ratio(moved, len(movement)),
        total_movement_days=sum(distances),
        mean_movement_days=_mean(distances),
        max_movement_days=max(distances, default=None),
        moved_earlier_item_count=sum(delta < 0 for delta in movement),
        moved_later_item_count=sum(delta > 0 for delta in movement),
        unchanged_item_count=movement.count(0),
        deadline_slack_item_count=len(slack),
        mean_completion_slack_days=_mean(slack),
        min_completion_slack_days=min(slack, default=None),
        schedulable_window_item_count=len(positions),
        mean_relative_window_position=_mean(positions),
        front_loaded_item_count=front_loaded,
        front_loaded_item_rate=_ratio(front_loaded, len(positions)),
        active_day_count=len(loads),
        mean_sessions_per_active_day=mean_load,
        max_sessions_on_day=max(loads, default=None),
        daily_session_load_variance=load_variance,
    )
