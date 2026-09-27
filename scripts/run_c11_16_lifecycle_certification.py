from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(
    0,
    str(ROOT),
)


from arena.production.lifecycle_certification import (
    run_lifecycle,
)


def format_ids(
    ids,
) -> str:
    if not ids:
        return "-"

    return ",".join(
        str(item_id)
        for item_id in ids
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run C11.16 grow -> max -> shrink "
            "production lifecycle certification."
        )
    )

    parser.add_argument(
        "--flavour",
        choices=(
            "lock-in",
            "monk",
            "both",
        ),
        default="both",
    )

    parser.add_argument(
        "--iterations",
        type=int,
        default=120,
    )

    parser.add_argument(
        "--evaluations",
        type=int,
        default=12000,
    )

    args = parser.parse_args()

    flavours = (
        ("lock-in", "monk")
        if args.flavour == "both"
        else (args.flavour,)
    )

    overall_failure = False

    print(
        "#" * 108
    )
    print(
        "C11.16 GROW -> MAXIMUM COMPLEXITY -> SHRINK "
        "LIFECYCLE CERTIFICATION"
    )
    print(
        "#" * 108
    )
    print(
        f"iterations={args.iterations}"
    )
    print(
        f"evaluations={args.evaluations}"
    )
    print(
        "scheduler_semantics_changed=0"
    )

    for flavour in flavours:
        print()
        print(
            "=" * 108
        )
        print(
            flavour.upper()
        )
        print(
            "=" * 108
        )

        runs = run_lifecycle(
            flavour,
            max_iterations=
                args.iterations,
            max_evaluations=
                args.evaluations,
        )

        for run in runs:
            step = run.world.step
            objective = (
                run.result.final_objective
            )
            delta = run.delta

            if run.validation_violations:
                overall_failure = True

            print()
            print(
                f"{step.code} [{step.phase.upper()}] "
                f"{step.title}"
            )
            print(
                f"  items={len(step.item_ids)} "
                f"dependencies="
                f"{len(run.world.problem.dependencies)}"
            )
            print(
                f"  validation_violations="
                f"{len(run.validation_violations)}"
            )
            print(
                f"  late_hours="
                f"{objective.late_hours}"
            )
            print(
                f"  infeasible_days="
                f"{objective.infeasible_day_count}"
            )
            print(
                f"  peak="
                f"{objective.max_daily_hours}"
            )
            print(
                f"  overloaded_days="
                f"{objective.overloaded_day_count}"
            )
            print(
                f"  tiny_nonfinal="
                f"{objective.tiny_nonfinal_sessions}"
            )
            print(
                f"  marathon_excess="
                f"{objective.unjustified_marathon_excess_hours}"
            )
            print(
                f"  evaluations="
                f"{run.result.evaluations}"
            )
            print(
                f"  termination="
                f"{run.result.termination_reason}"
            )
            print(
                "  added="
                + format_ids(
                    delta.added_item_ids
                )
            )
            print(
                "  removed="
                + format_ids(
                    delta.removed_item_ids
                )
            )
            print(
                "  surviving_unchanged="
                + format_ids(
                    delta.unchanged_schedule_item_ids
                )
            )
            print(
                "  surviving_changed="
                + format_ids(
                    delta.changed_schedule_item_ids
                )
            )

            if (
                run.validation_violations
            ):
                print(
                    "  VIOLATIONS:"
                )

                for violation in (
                    run.validation_violations
                ):
                    print(
                        "    - "
                        + str(violation)
                    )

        grow_runs = tuple(
            run
            for run in runs
            if run.world.step.phase == "grow"
        )

        shrink_runs = tuple(
            run
            for run in runs
            if run.world.step.phase == "shrink"
        )

        print()
        print("MIRRORED REVERSIBILITY")

        mirror_failures = []

        for shrink_index, shrink_run in enumerate(
            shrink_runs
        ):
            grow_run = grow_runs[
                len(grow_runs) - 2 - shrink_index
            ]

            same_world = (
                grow_run.world.problem
                == shrink_run.world.problem
                and grow_run.world.explicit_total_hours
                == shrink_run.world.explicit_total_hours
            )

            same_schedule = (
                grow_run.result.final_schedule
                == shrink_run.result.final_schedule
            )

            same_objective = (
                grow_run.result.final_objective
                == shrink_run.result.final_objective
            )

            exact = (
                same_world
                and same_schedule
                and same_objective
            )

            print(
                f"  {grow_run.world.step.code}"
                f" <-> {shrink_run.world.step.code}"
                f" exact={int(exact)}"
            )

            if not exact:
                mirror_failures.append(
                    (
                        grow_run.world.step.code,
                        shrink_run.world.step.code,
                    )
                )

        if mirror_failures:
            overall_failure = True

        print(
            f"{flavour.upper()}_ALL_MIRRORED_STATES_EXACT="
            f"{int(not mirror_failures)}"
        )

        first = runs[0]
        last = runs[-1]

        first_signature = tuple(
            (
                row.item_id,
                row.scheduled_date,
                row.hours,
            )
            for row
            in first.result.final_schedule.work_allocations
        )

        last_signature = tuple(
            (
                row.item_id,
                row.scheduled_date,
                row.hours,
            )
            for row
            in last.result.final_schedule.work_allocations
        )

        relaxed_back_to_baseline = (
            first_signature
            == last_signature
        )

        if not relaxed_back_to_baseline:
            overall_failure = True

        print()
        print(
            f"{flavour.upper()}_RETURN_TO_BASELINE="
            f"{int(relaxed_back_to_baseline)}"
        )

    print()
    print(
        "#" * 108
    )
    print(
        "C11.16 CERTIFICATION SUMMARY"
    )
    print(
        "#" * 108
    )
    print(
        "HARD_VALIDATION_FAILURES="
        + (
            "1"
            if overall_failure
            else "0"
        )
    )
    print(
        "C11_16_LIFECYCLE_CERTIFICATION_COMPLETE=1"
    )

    return (
        1
        if overall_failure
        else 0
    )


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
