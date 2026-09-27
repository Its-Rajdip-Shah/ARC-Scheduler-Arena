from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


from arena.production.decision_world import (
    TODAY,
    build_c11_15_saturated_world,
)
from arena.production.flavour_planner import (
    generate_flavour_schedule,
)
from arena.production.production_improver import (
    ProductionImproveConfig,
    improve_production_schedule,
)
from arena.production.work_mass import (
    validate_dynamic_plan,
)


def by_item(
    schedule,
):
    result = defaultdict(list)

    for row in schedule.work_allocations:
        result[row.item_id].append(
            row
        )

    for rows in result.values():
        rows.sort(
            key=lambda row:
                row.scheduled_date
        )

    return result


def timeline(
    rows,
):
    return ", ".join(
        (
            row.scheduled_date
            .strftime("%d %b")
            + f":{row.hours:.2f}h"
        )
        for row in rows
    )


def precedence_pass(
    rows,
    prerequisite,
    dependent,
):
    prerequisite_completion = max(
        row.scheduled_date
        for row in rows[
            prerequisite
        ]
    )

    dependent_start = min(
        row.scheduled_date
        for row in rows[
            dependent
        ]
    )

    return (
        prerequisite_completion
        < dependent_start
    )


def case_status(
    case,
    world,
    schedule,
):
    rows = by_item(
        schedule
    )

    if case.code == "D02":
        return (
            "PASS"
            if min(
                row.scheduled_date
                for row in rows[23]
            )
            <= min(
                row.scheduled_date
                for row in rows[24]
            )
            else "FAIL"
        )

    if case.code == "D03":
        return (
            "PASS"
            if (
                precedence_pass(
                    rows,
                    1,
                    2,
                )
                and precedence_pass(
                    rows,
                    2,
                    3,
                )
            )
            else "FAIL"
        )

    if case.code == "D04":
        return (
            "PASS"
            if all((
                precedence_pass(
                    rows,
                    25,
                    27,
                ),
                precedence_pass(
                    rows,
                    26,
                    27,
                ),
                precedence_pass(
                    rows,
                    27,
                    28,
                ),
            ))
            else "FAIL"
        )

    if case.code == "D05":
        return (
            "PASS"
            if (
                precedence_pass(
                    rows,
                    29,
                    30,
                )
                and precedence_pass(
                    rows,
                    29,
                    31,
                )
            )
            else "FAIL"
        )

    if case.code == "D06":
        correct_a = all(
            rows[item_id][0].scheduled_date
            == TODAY
            + __import__("datetime")
            .timedelta(days=8)
            for item_id in (
                32,
                33,
                34,
                35,
            )
        )

        correct_b = all(
            rows[item_id][0].scheduled_date
            == TODAY
            + __import__("datetime")
            .timedelta(days=9)
            for item_id in (
                36,
                37,
                38,
                39,
            )
        )

        return (
            "PASS"
            if correct_a
            and correct_b
            else "FAIL"
        )

    if case.code == "D07":
        release = (
            world.problem.item_by_id[
                40
            ].release_date
        )

        return (
            "PASS"
            if all(
                row.scheduled_date
                >= release
                for row in rows[40]
            )
            else "FAIL"
        )

    if case.code == "D09":
        expected = {
            7: 12,
            20: 12,
            42: 8,
        }

        return (
            "PASS"
            if all(
                float(
                    sum(
                        row.hours
                        for row
                        in rows[item_id]
                    )
                )
                == expected_hours
                for (
                    item_id,
                    expected_hours,
                )
                in expected.items()
            )
            else "FAIL"
        )

    if case.code == "D11":
        return (
            "PASS"
            if min(
                row.scheduled_date
                for row in rows[44]
            )
            <= min(
                row.scheduled_date
                for row in rows[45]
            )
            else "FAIL"
        )

    if case.code == "D12":
        today_only = all(
            row.scheduled_date
            == TODAY
            for row in rows[46]
        )

        infeasible = (
            schedule.daily_status[
                TODAY
            ].value
            == "infeasible"
        )

        return (
            "PASS"
            if today_only
            and infeasible
            else "FAIL"
        )

    if case.code == "D16":
        return (
            "PASS"
            if all(
                len(rows[item_id])
                == 1
                for item_id in (
                    14,
                    16,
                    17,
                    35,
                    39,
                )
            )
            else "FAIL"
        )

    return "OBSERVE"


def print_decision_case(
    case,
    world,
    schedule,
):
    rows = by_item(
        schedule
    )

    status = case_status(
        case,
        world,
        schedule,
    )

    print()
    print(
        f"{case.code}  [{status}]  "
        f"{case.title}"
    )

    print(
        f"    Principle: "
        f"{case.principle}"
    )

    for item_id in case.item_ids:
        item = world.problem.item_by_id[
            item_id
        ]

        metadata = []

        if item.priority_position is not None:
            metadata.append(
                "priority="
                + str(
                    item.priority_position
                )
            )

        if item.release_date is not None:
            metadata.append(
                "release="
                + item.release_date.isoformat()
            )

        if item.due_date is not None:
            metadata.append(
                "due="
                + item.due_date.isoformat()
            )

        if item.anchor_date is not None:
            metadata.append(
                "anchor="
                + item.anchor_date.isoformat()
            )

        print(
            f"    #{item_id:02d} "
            f"{world.labels[item_id]}"
        )

        print(
            "        "
            + (
                " | ".join(metadata)
                if metadata
                else "no extra metadata"
            )
        )

        print(
            "        schedule: "
            + timeline(
                rows[item_id]
            )
        )


def print_calendar(
    world,
    schedule,
):
    rows_by_day = defaultdict(list)

    for row in schedule.work_allocations:
        rows_by_day[
            row.scheduled_date
        ].append(row)

    print()
    print("=" * 110)
    print("FULL CALENDAR")
    print("=" * 110)

    for day in sorted(
        schedule.daily_hours
    ):
        print()
        print(
            f"{day.strftime('%a %d %b %Y').upper()}"
            f"   {schedule.daily_hours[day]:.2f}h"
            f"   [{schedule.daily_status[day].value.upper()}]"
        )

        for row in sorted(
            rows_by_day.get(
                day,
                (),
            ),
            key=lambda row: (
                row.item_id,
                row.hours,
            ),
        ):
            print(
                f"    #{row.item_id:02d} "
                f"{world.labels[row.item_id]}"
                f" — {row.hours:.2f}h"
                f" ({row.percentage}%)"
            )


def main() -> int:
    world = (
        build_c11_15_saturated_world()
    )

    print()
    print("#" * 110)
    print(
        "C11.15 STATIC SATURATED "
        "DECISION-COVERAGE WORLD"
    )
    print("#" * 110)

    print(
        f"tasks={len(world.problem.items)}"
        f"  dependencies="
        f"{len(world.problem.dependencies)}"
        f"  decision_cases="
        f"{len(world.cases)}"
    )

    print()
    print(
        "PASS = objective/structural principle "
        "checked automatically"
    )
    print(
        "OBSERVE = deliberately left for human "
        "trade-off review"
    )

    rc = 0

    for flavour in (
        "lock-in",
        "monk",
    ):
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
                max_iterations=100,
                max_evaluations=12000,
            ),
        )

        schedule = (
            result.final_schedule
        )

        validation = validate_dynamic_plan(
            world.problem,
            schedule.plan,
        )

        print()
        print()
        print("#" * 110)
        print(
            f"{flavour.upper()} "
            "DECISION AUDIT"
        )
        print("#" * 110)

        for case in world.cases:
            print_decision_case(
                case,
                world,
                schedule,
            )

            status = case_status(
                case,
                world,
                schedule,
            )

            if status == "FAIL":
                rc = 1

        print()
        print("=" * 110)
        print("SEARCH / VALIDATION SUMMARY")
        print("=" * 110)

        print(
            "hard_violations=",
            len(
                validation.violations
            ),
        )

        print(
            "infeasibilities=",
            len(
                validation.infeasibilities
            ),
        )

        print(
            "soft_violations=",
            len(
                validation.soft_violations
            ),
        )

        print(
            "late_hours=",
            result.final_objective
            .late_hours,
        )

        print(
            "infeasible_days=",
            result.final_objective
            .infeasible_day_count,
        )

        print(
            "peak_day_hours=",
            result.final_objective
            .max_daily_hours,
        )

        print(
            "priority_delay=",
            result.final_objective
            .priority_postponement_days,
        )

        print(
            "session_shape_penalty=",
            result.final_objective
            .session_shape_penalty,
        )

        print(
            "fragments=",
            result.final_objective
            .fragmentation_count,
        )

        print(
            "tiny_nonfinal=",
            result.final_objective
            .tiny_nonfinal_sessions,
        )

        print(
            "termination=",
            result.termination_reason,
        )

        print(
            "evaluations=",
            result.evaluations,
        )

        print_calendar(
            world,
            schedule,
        )

    print()
    print("#" * 110)
    print("C11.15 HUMAN REVIEW TARGETS")
    print("#" * 110)

    print(
        """
Focus especially on the OBSERVE cases:

D01 urgency vs relaxed priority
D08 started work vs newly urgent work
D10 no-deadline backlog placement
D13 future congestion lookahead
D14 session-shape quality under saturated pressure
D15 release collision behaviour
D17 Lock-in deadline buffer vs long focus
D18 Lock-in vs Monk distinction

Then inspect whether any formally PASS case still creates a calendar decision
that feels obviously stupid in context.

The static world is intentionally saturated. It is not the final grow/shrink
lifecycle certification.
"""
    )

    print(
        "C11_15_STATIC_DECISION_AUDIT_COMPLETE=1"
    )

    return rc


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
