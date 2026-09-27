from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from datetime import date
from decimal import Decimal
from enum import Enum

import pytest

from arena.production.integrated_fixture import build_c11_13_base_world
from arena.production.flavour_planner import (
    generate_flavour_schedule as old_generate,
)
from arena.production.production_improver import (
    ProductionImproveConfig as OldConfig,
    improve_production_schedule as old_improve,
)

from arc_scheduler.engine.domain import (
    DependencyEdge as NewDependencyEdge,
    ScheduleItem as NewScheduleItem,
    ScheduleProblem as NewScheduleProblem,
)
from arc_scheduler.engine.flavour_planner import (
    generate_flavour_schedule as new_generate,
)
from arc_scheduler.engine.production_improver import (
    ProductionImproveConfig as NewConfig,
    improve_production_schedule as new_improve,
)


def _canonical(value):
    """Normalize old/new engine objects into implementation-neutral values."""

    if is_dataclass(value) and not isinstance(value, type):
        return tuple(
            (field.name, _canonical(getattr(value, field.name)))
            for field in fields(value)
        )

    if isinstance(value, Enum):
        return _canonical(value.value)

    if isinstance(value, Decimal):
        return ("Decimal", str(value))

    if isinstance(value, date):
        return ("date", value.isoformat())

    if isinstance(value, Mapping):
        return tuple(
            sorted(
                (
                    _canonical(key),
                    _canonical(item),
                )
                for key, item in value.items()
            )
        )

    if isinstance(value, (tuple, list)):
        return tuple(_canonical(item) for item in value)

    if isinstance(value, (set, frozenset)):
        return tuple(sorted(_canonical(item) for item in value))

    return value


def _new_problem_from_old(old_problem):
    items = tuple(
        NewScheduleItem(
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
        for item in old_problem.items
    )

    dependencies = tuple(
        NewDependencyEdge(
            prerequisite_id=edge.prerequisite_id,
            dependent_id=edge.dependent_id,
        )
        for edge in old_problem.dependencies
    )

    return NewScheduleProblem(
        today=old_problem.today,
        items=items,
        dependencies=dependencies,
        capacity_by_duration=dict(old_problem.capacity_by_duration),
        overload_dates=frozenset(old_problem.overload_dates),
    )


@pytest.mark.parametrize("flavour", ("lock-in", "monk"))
def test_extracted_engine_is_exactly_equivalent_to_frozen_arena_engine(flavour):
    world = build_c11_13_base_world()

    old_problem = world.problem
    new_problem = _new_problem_from_old(old_problem)

    assert _canonical(old_problem) == _canonical(new_problem)

    old_initial = old_generate(
        old_problem,
        flavour,
        explicit_total_hours=world.explicit_total_hours,
    )

    new_initial = new_generate(
        new_problem,
        flavour,
        explicit_total_hours=world.explicit_total_hours,
    )

    assert _canonical(old_initial) == _canonical(new_initial)

    old_result = old_improve(
        old_problem,
        old_initial,
        OldConfig(
            max_iterations=40,
            max_evaluations=4000,
        ),
    )

    new_result = new_improve(
        new_problem,
        new_initial,
        NewConfig(
            max_iterations=40,
            max_evaluations=4000,
        ),
    )

    assert _canonical(old_result) == _canonical(new_result)
