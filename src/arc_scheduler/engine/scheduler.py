"""Stable public V1 façade over the frozen production scheduler."""

from __future__ import annotations

from arc_scheduler.contracts import (
    DayLoadOutputV1,
    ENGINE_VERSION,
    INPUT_CONTRACT_VERSION,
    LoadStatusV1,
    OUTPUT_CONTRACT_VERSION,
    PeriodLoadOutputV1,
    ProductionObjectiveOutputV1,
    SchedulerAllocationOutputV1,
    SchedulerInputV1,
    SchedulerOutputV1,
    SchedulerRunMetadataV1,
    WorkEstimateOutputV1,
)

from .domain import DependencyEdge, ScheduleItem, ScheduleProblem
from .flavour_planner import generate_flavour_schedule
from .production_improver import (
    ProductionImproveConfig,
    improve_production_schedule,
)


def _problem_from_input(request: SchedulerInputV1) -> ScheduleProblem:
    return ScheduleProblem(
        today=request.today,
        items=tuple(
            ScheduleItem(
                item_id=task.item_id,
                duration_category=task.duration_category,
                priority_position=task.priority_position,
                release_date=task.release_date,
                due_date=task.due_date,
                anchor_date=task.anchor_date,
                percent_completed=task.percent_completed,
                remaining_fraction=task.remaining_fraction,
                is_residual=task.is_residual,
                existing_scheduled_date=task.existing_scheduled_date,
            )
            for task in request.tasks
        ),
        dependencies=tuple(
            DependencyEdge(
                prerequisite_id=edge.prerequisite_id,
                dependent_id=edge.dependent_id,
            )
            for edge in request.dependencies
        ),
        capacity_by_duration=request.capacity_by_duration,
        overload_dates=request.overload_dates,
    )


def _objective_output(objective) -> ProductionObjectiveOutputV1:
    return ProductionObjectiveOutputV1(
        late_hours=objective.late_hours,
        infeasible_day_count=objective.infeasible_day_count,
        infeasible_excess_hours=objective.infeasible_excess_hours,
        tiny_nonfinal_sessions=objective.tiny_nonfinal_sessions,
        avoidable_idle_days=objective.avoidable_idle_days,
        max_daily_hours=objective.max_daily_hours,
        overloaded_excess_hours=objective.overloaded_excess_hours,
        overloaded_day_count=objective.overloaded_day_count,
        unjustified_marathon_excess_hours=(
            objective.unjustified_marathon_excess_hours
        ),
        deadline_buffer_risk=objective.deadline_buffer_risk,
        priority_postponement_days=objective.priority_postponement_days,
        session_shape_penalty=objective.session_shape_penalty,
        fragmentation_count=objective.fragmentation_count,
        preferred_excess_squared=objective.preferred_excess_squared,
        continuity_gap_days=objective.continuity_gap_days,
        completion_day_sum=objective.completion_day_sum,
    )


class SchedulerEngineV1:
    """Versioned public façade for the frozen production engine."""

    def __init__(
        self,
        *,
        max_iterations: int = 40,
        max_evaluations: int = 4000,
    ) -> None:
        self._config = ProductionImproveConfig(
            max_iterations=max_iterations,
            max_evaluations=max_evaluations,
        )

    def run(self, request: SchedulerInputV1) -> SchedulerOutputV1:
        problem = _problem_from_input(request)

        initial = generate_flavour_schedule(
            problem,
            request.flavour.value,
            explicit_total_hours=dict(request.explicit_total_hours),
        )

        result = improve_production_schedule(
            problem,
            initial,
            self._config,
        )

        schedule = result.final_schedule

        work_by_key = {}

        for row in schedule.work_allocations:
            key = (row.item_id, row.scheduled_date)

            if key in work_by_key:
                raise AssertionError(
                    "Duplicate item/day work allocation returned by engine: "
                    f"{key}"
                )

            work_by_key[key] = row

        allocations = []

        for row in schedule.plan.allocations:
            key = (row.item_id, row.scheduled_date)

            if key not in work_by_key:
                raise AssertionError(
                    "SchedulePlan allocation has no corresponding "
                    f"WorkAllocation: {key}"
                )

            work = work_by_key[key]

            if work.percentage != row.percentage:
                raise AssertionError(
                    "SchedulePlan and WorkAllocation percentages disagree "
                    f"for {key}: {row.percentage} != {work.percentage}"
                )

            allocations.append(
                SchedulerAllocationOutputV1(
                    item_id=row.item_id,
                    scheduled_date=row.scheduled_date,
                    hours=work.hours,
                    percentage=row.percentage,
                    execution_rank=row.execution_rank,
                )
            )

        if len(allocations) != len(work_by_key):
            raise AssertionError(
                "WorkAllocation exists without corresponding "
                "SchedulePlan allocation."
            )

        estimates = tuple(
            WorkEstimateOutputV1(
                item_id=estimate.item_id,
                total_hours=estimate.total_hours,
                source=estimate.source,
            )
            for _, estimate in sorted(schedule.estimates.items())
        )

        daily_load = tuple(
            DayLoadOutputV1(
                scheduled_date=day,
                hours=hours,
                status=LoadStatusV1(schedule.daily_status[day].value),
            )
            for day, hours in sorted(schedule.daily_hours.items())
        )

        weekly_load = tuple(
            PeriodLoadOutputV1(
                period=period,
                hours=band.hours,
                status=LoadStatusV1(band.status.value),
            )
            for period, band in sorted(schedule.weekly_status.items())
        )

        monthly_load = tuple(
            PeriodLoadOutputV1(
                period=period,
                hours=band.hours,
                status=LoadStatusV1(band.status.value),
            )
            for period, band in sorted(schedule.monthly_status.items())
        )

        return SchedulerOutputV1(
            allocations=tuple(allocations),
            estimates=estimates,
            daily_load=daily_load,
            weekly_load=weekly_load,
            monthly_load=monthly_load,
            objective=_objective_output(result.final_objective),
            conflicts=tuple(schedule.plan.conflicts),
            diagnostics=tuple(schedule.plan.diagnostics),
            metadata=SchedulerRunMetadataV1(
                engine_version=ENGINE_VERSION,
                input_contract_version=INPUT_CONTRACT_VERSION,
                output_contract_version=OUTPUT_CONTRACT_VERSION,
                flavour=request.flavour,
                iterations=result.iterations,
                evaluations=result.evaluations,
                termination_reason=result.termination_reason,
            ),
        )
