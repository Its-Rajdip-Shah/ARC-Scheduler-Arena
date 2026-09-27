"""Certification for the versioned public scheduler boundary."""

from dataclasses import asdict

import pytest

from arena.production.integrated_fixture import build_c11_13_base_world

from arc_scheduler import (
    SchedulerDependencyInputV1,
    SchedulerEngineV1,
    SchedulerInputV1,
    SchedulerTaskInputV1,
)
from arc_scheduler.engine.domain import (
    DependencyEdge,
    ScheduleItem,
    ScheduleProblem,
)
from arc_scheduler.engine.flavour_planner import generate_flavour_schedule
from arc_scheduler.engine.production_improver import (
    ProductionImproveConfig,
    improve_production_schedule,
)


def _request(world, flavour):
    problem = world.problem

    return SchedulerInputV1(
        today=problem.today,
        flavour=flavour,
        tasks=tuple(
            SchedulerTaskInputV1(
                item_id=item.item_id,
                duration_category=item.duration_category,
                priority_position=item.priority_position,
                release_date=item.release_date,
                due_date=item.due_date,
                anchor_date=item.anchor_date,
                percent_completed=item.percent_completed,
                remaining_fraction=item.remaining_fraction,
                is_residual=item.is_residual,
                existing_scheduled_date=item.existing_scheduled_date,
            )
            for item in problem.items
        ),
        dependencies=tuple(
            SchedulerDependencyInputV1(
                prerequisite_id=edge.prerequisite_id,
                dependent_id=edge.dependent_id,
            )
            for edge in problem.dependencies
        ),
        capacity_by_duration=dict(problem.capacity_by_duration),
        overload_dates=frozenset(problem.overload_dates),
        explicit_total_hours=world.explicit_total_hours,
    )


def _direct_problem(request):
    return ScheduleProblem(
        today=request.today,
        items=tuple(
            ScheduleItem(
                item_id=item.item_id,
                duration_category=item.duration_category,
                priority_position=item.priority_position,
                release_date=item.release_date,
                due_date=item.due_date,
                anchor_date=item.anchor_date,
                percent_completed=item.percent_completed,
                remaining_fraction=item.remaining_fraction,
                is_residual=item.is_residual,
                existing_scheduled_date=item.existing_scheduled_date,
            )
            for item in request.tasks
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


@pytest.mark.parametrize("flavour", ("lock-in", "monk"))
def test_v1_facade_preserves_frozen_engine_result(flavour):
    world = build_c11_13_base_world()
    request = _request(world, flavour)

    public = SchedulerEngineV1().run(request)

    problem = _direct_problem(request)

    initial = generate_flavour_schedule(
        problem,
        flavour,
        explicit_total_hours=dict(request.explicit_total_hours),
    )

    direct = improve_production_schedule(
        problem,
        initial,
        ProductionImproveConfig(
            max_iterations=40,
            max_evaluations=4000,
        ),
    )

    direct_work = {
        (row.item_id, row.scheduled_date): row
        for row in direct.final_schedule.work_allocations
    }

    expected_allocations = tuple(
        (
            row.item_id,
            row.scheduled_date,
            direct_work[(row.item_id, row.scheduled_date)].hours,
            row.percentage,
            row.execution_rank,
        )
        for row in direct.final_schedule.plan.allocations
    )

    actual_allocations = tuple(
        (
            row.item_id,
            row.scheduled_date,
            row.hours,
            row.percentage,
            row.execution_rank,
        )
        for row in public.allocations
    )

    assert actual_allocations == expected_allocations

    assert asdict(public.objective) == {
        "late_hours": direct.final_objective.late_hours,
        "infeasible_day_count": direct.final_objective.infeasible_day_count,
        "infeasible_excess_hours": direct.final_objective.infeasible_excess_hours,
        "tiny_nonfinal_sessions": direct.final_objective.tiny_nonfinal_sessions,
        "avoidable_idle_days": direct.final_objective.avoidable_idle_days,
        "max_daily_hours": direct.final_objective.max_daily_hours,
        "overloaded_excess_hours": direct.final_objective.overloaded_excess_hours,
        "overloaded_day_count": direct.final_objective.overloaded_day_count,
        "unjustified_marathon_excess_hours": (
            direct.final_objective.unjustified_marathon_excess_hours
        ),
        "deadline_buffer_risk": direct.final_objective.deadline_buffer_risk,
        "priority_postponement_days": (
            direct.final_objective.priority_postponement_days
        ),
        "session_shape_penalty": direct.final_objective.session_shape_penalty,
        "fragmentation_count": direct.final_objective.fragmentation_count,
        "preferred_excess_squared": (
            direct.final_objective.preferred_excess_squared
        ),
        "continuity_gap_days": direct.final_objective.continuity_gap_days,
        "completion_day_sum": direct.final_objective.completion_day_sum,
    }

    assert public.metadata.engine_version == "c11.15.9"
    assert public.metadata.input_contract_version == "1"
    assert public.metadata.output_contract_version == "1"
    assert public.metadata.flavour.value == flavour

    assert public.metadata.iterations == direct.iterations
    assert public.metadata.evaluations == direct.evaluations
    assert public.metadata.termination_reason == direct.termination_reason


def test_v1_contract_rejects_unknown_estimate_item():
    world = build_c11_13_base_world()
    request = _request(world, "lock-in")

    with pytest.raises(ValueError, match="unknown items"):
        SchedulerInputV1(
            today=request.today,
            flavour=request.flavour,
            tasks=request.tasks,
            dependencies=request.dependencies,
            capacity_by_duration=request.capacity_by_duration,
            overload_dates=request.overload_dates,
            explicit_total_hours={
                **dict(request.explicit_total_hours),
                999999: 4,
            },
        )
