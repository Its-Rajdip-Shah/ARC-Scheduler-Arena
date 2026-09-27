"""C11.16 grow -> maximum complexity -> shrink lifecycle certification.

This module does not define new scheduler behaviour.

It derives a sequence of progressively changing canonical worlds from the
already-frozen C11.15 saturated world, runs the frozen production scheduler
from scratch at every step, and records what changed.

The purpose is to verify that scheduling pressure appears and disappears
sensibly as the canonical workload grows and later shrinks.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from arena.production.decision_world import (
    SaturatedDecisionWorld,
    build_c11_15_saturated_world,
)
from arena.production.flavour_planner import (
    generate_flavour_schedule,
)
from arena.production.production_improver import (
    ProductionImproveConfig,
    ProductionImproveResult,
    improve_production_schedule,
)
from arena.production.work_mass import (
    validate_dynamic_plan,
)
from arena.scheduling.domain import (
    DependencyEdge,
    ScheduleProblem,
)


D = Decimal


@dataclass(frozen=True, slots=True)
class LifecycleStep:
    code: str
    phase: str
    title: str
    principle: str
    item_ids: frozenset[int]


@dataclass(frozen=True, slots=True)
class LifecycleWorld:
    step: LifecycleStep
    problem: ScheduleProblem
    explicit_total_hours: dict[int, Decimal]
    labels: dict[int, str]


@dataclass(frozen=True, slots=True)
class LifecycleDelta:
    previous_step: str | None
    current_step: str
    added_item_ids: tuple[int, ...]
    removed_item_ids: tuple[int, ...]
    unchanged_schedule_item_ids: tuple[int, ...]
    changed_schedule_item_ids: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class LifecycleRun:
    world: LifecycleWorld
    flavour: str
    result: ProductionImproveResult
    validation_violations: tuple[str, ...]
    delta: LifecycleDelta


_DIMENSIONS = (
    (
        "baseline",
        "Simple relaxed work",
        (
            "Start with one ordinary flexible task so later movement can be "
            "attributed to newly introduced pressure."
        ),
        frozenset({18}),
    ),
    (
        "urgency_priority",
        "Urgency versus relaxed priority",
        (
            "Introduce a near-deadline low-priority task and a relaxed "
            "high-priority task."
        ),
        frozenset({21, 22}),
    ),
    (
        "dependency_chain",
        "Multi-hop dependency chain",
        (
            "Introduce prerequisite urgency and completion-based execution "
            "order."
        ),
        frozenset({1, 2, 3}),
    ),
    (
        "anchors",
        "Fixed-date anchored work",
        (
            "Introduce fixed-date work that flexible work must route around."
        ),
        frozenset({10, 11, 12, 13}),
    ),
    (
        "future_releases",
        "Future urgent releases",
        (
            "Introduce work that is known now but cannot execute until a "
            "future release date."
        ),
        frozenset({8, 9}),
    ),
    (
        "partial_progress",
        "Partially completed work",
        (
            "Introduce large tasks whose already-completed work must not be "
            "scheduled again."
        ),
        frozenset({7, 20}),
    ),
    (
        "competing_large",
        "Competing large flexible tasks",
        (
            "Introduce multiple long-running splittable workloads competing "
            "for the same future capacity."
        ),
        frozenset({6, 19}),
    ),
    (
        "parallel_dependency",
        "Independent prerequisite chain",
        (
            "Introduce a second dependency structure so prerequisite urgency "
            "must coexist across independent work streams."
        ),
        frozenset({4, 5}),
    ),
    (
        "priority_pairs",
        "Comparable priority pairs",
        (
            "Introduce comparable peers so explicit priority sensitivity can "
            "be observed without confusing it with deadline pressure."
        ),
        frozenset({23, 24, 44, 45}),
    ),
    (
        "complex_dependencies",
        "Diamond and shared-prerequisite structures",
        (
            "Introduce branching/joining dependency structures and one "
            "prerequisite unlocking multiple dependents."
        ),
        frozenset({25, 26, 27, 28, 29, 30, 31}),
    ),
    (
        "anchor_wall",
        "Two-day anchor wall plus urgent release",
        (
            "Introduce severe known future congestion and urgent work released "
            "into that congestion."
        ),
        frozenset({
            32, 33, 34, 35,
            36, 37, 38, 39,
            40,
        }),
    ),
    (
        "started_urgent_backlog",
        "Started work, new urgency, and no-deadline backlog",
        (
            "Introduce continuity pressure, newly urgent work, and flexible "
            "backlog with no deadline."
        ),
        frozenset({41, 42, 43}),
    ),
    (
        "atomic_work",
        "Tiny atomic/admin work",
        (
            "Introduce short real-world jobs that must coexist with focused "
            "work without being inflated into fake focus sessions."
        ),
        frozenset({14, 15, 16, 17}),
    ),
    (
        "impossible_pressure",
        "Deliberately impossible due-today workload",
        (
            "Finish at maximum complexity by introducing a true infeasibility "
            "that must be surfaced honestly rather than hidden as lateness."
        ),
        frozenset({46}),
    ),
)


def lifecycle_steps() -> tuple[LifecycleStep, ...]:
    """Return deterministic grow then reverse-shrink certification steps."""

    growing: list[LifecycleStep] = []
    active: set[int] = set()

    for index, (
        _key,
        title,
        principle,
        item_ids,
    ) in enumerate(_DIMENSIONS):
        active.update(item_ids)

        growing.append(
            LifecycleStep(
                code=f"G{index:02d}",
                phase="grow",
                title=title,
                principle=principle,
                item_ids=frozenset(active),
            )
        )

    shrinking: list[LifecycleStep] = []

    # Remove every pressure dimension in exact reverse order.
    # Keep the original simple baseline as the final relaxed state.
    for shrink_index, dimension_index in enumerate(
        range(
            len(_DIMENSIONS) - 1,
            0,
            -1,
        ),
        start=1,
    ):
        (
            _key,
            title,
            principle,
            item_ids,
        ) = _DIMENSIONS[dimension_index]

        active.difference_update(item_ids)

        shrinking.append(
            LifecycleStep(
                code=f"S{shrink_index:02d}",
                phase="shrink",
                title=f"Remove: {title}",
                principle=(
                    "Remove the previously introduced pressure and verify that "
                    "the surviving workload relaxes without retaining "
                    "unnecessary consequences. Removed dimension: "
                    + principle
                ),
                item_ids=frozenset(active),
            )
        )

    return tuple(
        growing
        + shrinking
    )


def build_lifecycle_world(
    step: LifecycleStep,
    *,
    master: SaturatedDecisionWorld | None = None,
) -> LifecycleWorld:
    """Build one lifecycle world as a pure subset of frozen C11.15."""

    if master is None:
        master = build_c11_15_saturated_world()

    master_ids = {
        item.item_id
        for item in master.problem.items
    }

    unknown = (
        step.item_ids
        - master_ids
    )

    if unknown:
        raise ValueError(
            "Lifecycle step contains unknown item IDs: "
            f"{sorted(unknown)}"
        )

    items = tuple(
        item
        for item in master.problem.items
        if item.item_id
        in step.item_ids
    )

    dependencies = tuple(
        edge
        for edge in master.problem.dependencies
        if (
            edge.prerequisite_id
            in step.item_ids
            and edge.dependent_id
            in step.item_ids
        )
    )

    problem = ScheduleProblem(
        today=master.problem.today,
        items=items,
        dependencies=dependencies,
        capacity_by_duration=
            master.problem.capacity_by_duration,
        overload_dates=
            master.problem.overload_dates,
    )

    explicit_total_hours = {
        item_id: hours
        for item_id, hours
        in master.explicit_total_hours.items()
        if item_id
        in step.item_ids
    }

    labels = {
        item_id: label
        for item_id, label
        in master.labels.items()
        if item_id
        in step.item_ids
    }

    return LifecycleWorld(
        step=step,
        problem=problem,
        explicit_total_hours=explicit_total_hours,
        labels=labels,
    )


def _schedule_signature(
    schedule,
) -> dict[int, tuple[tuple[object, Decimal], ...]]:
    by_item: dict[
        int,
        list[tuple[object, Decimal]],
    ] = {}

    for row in schedule.work_allocations:
        by_item.setdefault(
            row.item_id,
            [],
        ).append((
            row.scheduled_date,
            row.hours,
        ))

    return {
        item_id: tuple(sorted(rows))
        for item_id, rows
        in by_item.items()
    }


def _delta(
    previous_run: LifecycleRun | None,
    current_step: LifecycleStep,
    current_schedule,
) -> LifecycleDelta:
    current_signature = _schedule_signature(
        current_schedule
    )

    if previous_run is None:
        return LifecycleDelta(
            previous_step=None,
            current_step=current_step.code,
            added_item_ids=tuple(
                sorted(current_step.item_ids)
            ),
            removed_item_ids=(),
            unchanged_schedule_item_ids=(),
            changed_schedule_item_ids=(),
        )

    previous_ids = (
        previous_run.world.step.item_ids
    )

    current_ids = (
        current_step.item_ids
    )

    previous_signature = (
        _schedule_signature(
            previous_run.result.final_schedule
        )
    )

    surviving = (
        previous_ids
        & current_ids
    )

    unchanged = tuple(
        sorted(
            item_id
            for item_id
            in surviving
            if (
                previous_signature.get(item_id)
                == current_signature.get(item_id)
            )
        )
    )

    changed = tuple(
        sorted(
            item_id
            for item_id
            in surviving
            if (
                previous_signature.get(item_id)
                != current_signature.get(item_id)
            )
        )
    )

    return LifecycleDelta(
        previous_step=
            previous_run.world.step.code,
        current_step=current_step.code,
        added_item_ids=tuple(
            sorted(
                current_ids
                - previous_ids
            )
        ),
        removed_item_ids=tuple(
            sorted(
                previous_ids
                - current_ids
            )
        ),
        unchanged_schedule_item_ids=
            unchanged,
        changed_schedule_item_ids=
            changed,
    )


def run_lifecycle_step(
    step: LifecycleStep,
    flavour: str,
    *,
    previous_run: LifecycleRun | None = None,
    max_iterations: int = 120,
    max_evaluations: int = 12000,
) -> LifecycleRun:
    """Run one certification step using the frozen production scheduler."""

    world = build_lifecycle_world(
        step
    )

    initial = generate_flavour_schedule(
        world.problem,
        flavour,
        explicit_total_hours=
            world.explicit_total_hours,
    )

    result = improve_production_schedule(
        world.problem,
        initial,
        ProductionImproveConfig(
            max_iterations=max_iterations,
            max_evaluations=max_evaluations,
        ),
    )

    validation = validate_dynamic_plan(
        world.problem,
        result.final_schedule.plan,
    )

    return LifecycleRun(
        world=world,
        flavour=flavour,
        result=result,
        validation_violations=
            tuple(validation.violations),
        delta=_delta(
            previous_run,
            step,
            result.final_schedule,
        ),
    )


def run_lifecycle(
    flavour: str,
    *,
    max_iterations: int = 120,
    max_evaluations: int = 12000,
) -> tuple[LifecycleRun, ...]:
    """Run the complete grow/max/shrink sequence for one flavour."""

    runs: list[LifecycleRun] = []
    previous: LifecycleRun | None = None

    for step in lifecycle_steps():
        current = run_lifecycle_step(
            step,
            flavour,
            previous_run=previous,
            max_iterations=max_iterations,
            max_evaluations=max_evaluations,
        )

        runs.append(
            current
        )

        previous = current

    return tuple(runs)
