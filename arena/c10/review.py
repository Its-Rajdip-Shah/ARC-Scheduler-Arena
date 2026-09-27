"""Human-readable C10 schedule-review artifacts.

These utilities only render already-produced schedules. They do not score,
rank, repair, select, or otherwise feed qualitative review back into search.
"""
from __future__ import annotations

from dataclasses import fields
from decimal import Decimal

from arena.evaluation.performance import PerformanceVector
from arena.scheduling.domain import (
    SchedulePlan,
    ScheduleProblem,
)


def performance_payload(
    performance: PerformanceVector,
) -> dict:
    if not isinstance(
        performance,
        PerformanceVector,
    ):
        raise TypeError(
            "Expected PerformanceVector"
        )

    return {
        field.name:
            getattr(
                performance,
                field.name,
            )
        for field in fields(
            PerformanceVector
        )
    }


def calendar_rows(
    problem: ScheduleProblem,
    plan: SchedulePlan,
    *,
    key_by_id: dict[int, str],
    display_names: dict[str, str],
    groups: dict[str, str],
) -> list[dict]:
    if not isinstance(
        problem,
        ScheduleProblem,
    ):
        raise TypeError(
            "Expected ScheduleProblem"
        )

    if not isinstance(
        plan,
        SchedulePlan,
    ):
        raise TypeError(
            "Expected SchedulePlan"
        )

    item_by_id = problem.item_by_id

    rows = []

    for allocation in sorted(
        plan.allocations,
        key=lambda row: (
            row.scheduled_date,
            row.execution_rank,
            row.item_id,
        ),
    ):
        if allocation.item_id not in key_by_id:
            raise ValueError(
                "Allocation references "
                "unknown fixture item"
            )

        key = key_by_id[
            allocation.item_id
        ]

        if key not in display_names:
            raise ValueError(
                "Missing display name"
            )

        if key not in groups:
            raise ValueError(
                "Missing fixture group"
            )

        item = item_by_id[
            allocation.item_id
        ]

        rows.append({
            "scheduled_date":
                allocation
                .scheduled_date
                .isoformat(),
            "weekday":
                allocation
                .scheduled_date
                .strftime("%A"),
            "execution_rank":
                allocation.execution_rank,
            "percentage":
                str(
                    allocation.percentage
                ),
            "item_key":
                key,
            "display_name":
                display_names[key],
            "group":
                groups[key],
            "duration_category":
                item.duration_category,
            "priority_position":
                item.priority_position,
            "release_date": (
                None
                if item.release_date is None
                else item
                .release_date
                .isoformat()
            ),
            "due_date": (
                None
                if item.due_date is None
                else item
                .due_date
                .isoformat()
            ),
            "anchor_date": (
                None
                if item.anchor_date is None
                else item
                .anchor_date
                .isoformat()
            ),
            "remaining_fraction":
                str(
                    item.remaining_fraction
                ),
        })

    return rows


def render_review_markdown(
    *,
    label: str,
    role: str,
    status: str,
    run_seed: int,
    wall_seconds: float,
    algorithm_seconds: float | None,
    rows: list[dict],
    performance: dict | None,
    error_type: str | None = None,
    error_message: str | None = None,
) -> str:
    lines = [
        f"# C10 schedule review — {label}",
        "",
        f"- Policy role: `{role}`",
        f"- Trial status: `{status}`",
        f"- Run seed: `{run_seed}`",
        f"- Isolated wall time: `{wall_seconds:.6f}s`",
    ]

    if algorithm_seconds is not None:
        lines.append(
            "- Algorithm-reported total time: "
            f"`{algorithm_seconds:.6f}s`"
        )

    if error_type is not None:
        lines.extend([
            f"- Error type: `{error_type}`",
            f"- Error message: `{error_message}`",
        ])

    lines.extend([
        "",
        "## Independent C1 observations",
        "",
    ])

    if performance is None:
        lines.append(
            "No final C1 performance vector is "
            "available for this trial."
        )
    else:
        keys = (
            "hard_violation_count",
            "canonical_infeasibility_count",
            "deadline_miss_rate",
            "mean_lateness_days",
            "priority_inversion_rate",
            "unapproved_excess_session_count",
            "fragmented_item_rate",
            "mean_session_gap_days",
            "mean_dependency_wait_days",
            "mean_start_delay_days",
            "active_day_count",
            "mean_sessions_per_active_day",
            "max_sessions_on_day",
            "daily_session_load_variance",
        )

        for key in keys:
            lines.append(
                f"- `{key}`: "
                f"`{performance.get(key)}`"
            )

    lines.extend([
        "",
        "## Proposed calendar",
        "",
    ])

    if not rows:
        lines.append(
            "No final schedule is available "
            "for human review."
        )
    else:
        current_date = None

        for row in rows:
            if (
                row["scheduled_date"]
                != current_date
            ):
                current_date = (
                    row["scheduled_date"]
                )

                lines.extend([
                    "",
                    "### "
                    f'{row["weekday"]}, '
                    f'{row["scheduled_date"]}',
                    "",
                ])

            metadata = []

            if (
                row["priority_position"]
                is not None
            ):
                metadata.append(
                    "priority "
                    f'{row["priority_position"]}'
                )

            if row["due_date"]:
                metadata.append(
                    f'due {row["due_date"]}'
                )

            if row["anchor_date"]:
                metadata.append(
                    "anchor "
                    f'{row["anchor_date"]}'
                )

            suffix = (
                ""
                if not metadata
                else " — " + ", ".join(
                    metadata
                )
            )

            lines.append(
                "- "
                f'**{row["display_name"]}** '
                f'[{row["group"]}] — '
                f'{row["percentage"]}% '
                f'({row["duration_category"]})'
                f'{suffix}'
            )

    lines.extend([
        "",
        "## External human-review checklist",
        "",
        "This section is deliberately qualitative "
        "and must not be fed back into the search "
        "objective or used to retune the candidates.",
        "",
        "- [ ] Daily workload feels realistically followable.",
        "- [ ] Long work is split into sensible sessions.",
        "- [ ] There is no obviously unpleasant bunching.",
        "- [ ] There are no strange avoidable idle stretches.",
        "- [ ] Dependency chains progress in a natural order.",
        "- [ ] Deadline-critical work has sensible buffer.",
        "- [ ] Anchored work appears where a user would expect it.",
        "- [ ] Priority ordering feels understandable.",
        "- [ ] Personal/admin work is not awkwardly mixed with deep work.",
        "- [ ] I would realistically follow this schedule.",
        "",
        "### Free-form observations",
        "",
        "- Surprising placements:",
        "- Unpleasant fragmentation:",
        "- Excessive concentration:",
        "- Good schedule characteristics:",
        "- Other comments:",
        "",
        "No scalar human-friendliness score is recorded.",
        "",
    ])

    return "\n".join(lines)


def decimal_json(
    value,
):
    if isinstance(value, Decimal):
        return str(value)

    raise TypeError(
        f"Unsupported JSON value: "
        f"{type(value).__name__}"
    )
