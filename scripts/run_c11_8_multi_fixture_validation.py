from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import date
from decimal import Decimal
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


from arena.production.flavour_planner import (
    generate_flavour_schedule,
)
from arena.production.validation_suite import (
    validation_scenarios,
)
from arena.production.work_mass import (
    validate_dynamic_plan,
)


D = Decimal


def write_json(path: Path, payload) -> None:
    path.write_text(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ) + "\n",
        encoding="utf-8",
    )


def metrics(
    scenario,
    generated,
) -> dict:
    allocations = tuple(
        sorted(
            generated.work_allocations,
            key=lambda row: (
                row.scheduled_date,
                row.item_id,
            ),
        )
    )

    by_item = defaultdict(list)

    for row in allocations:
        by_item[row.item_id].append(row)

    continuity_gap_count = 0
    max_gap_days = 0
    sub_hour_session_count = 0
    max_single_session = D("0")

    for rows in by_item.values():
        for index, row in enumerate(rows):
            max_single_session = max(
                max_single_session,
                row.hours,
            )

            if (
                row.hours < D("1")
                and index < len(rows) - 1
            ):
                sub_hour_session_count += 1

        for left, right in zip(
            rows,
            rows[1:],
        ):
            gap = (
                right.scheduled_date
                - left.scheduled_date
            ).days - 1

            if gap > 0:
                continuity_gap_count += 1
                max_gap_days = max(
                    max_gap_days,
                    gap,
                )

    active_daily = {
        day: hours
        for day, hours
        in generated.daily_hours.items()
        if hours > 0
    }

    final_date = max(
        row.scheduled_date
        for row in allocations
    )

    mean_daily = (
        sum(
            active_daily.values(),
            D("0"),
        )
        / D(len(active_daily))
    )

    return {
        "allocation_count":
            len(allocations),
        "active_day_count":
            len(active_daily),
        "first_active_date":
            min(active_daily).isoformat(),
        "final_active_date":
            final_date.isoformat(),
        "max_daily_hours":
            str(max(active_daily.values())),
        "mean_active_day_hours":
            str(
                mean_daily.quantize(
                    D("0.01")
                )
            ),
        "max_single_session_hours":
            str(max_single_session),
        "continuity_gap_count":
            continuity_gap_count,
        "max_continuity_gap_days":
            max_gap_days,
        "sub_hour_nonfinal_session_count":
            sub_hour_session_count,
    }


def markdown_schedule(
    scenario,
    flavour,
    generated,
) -> str:
    rows = sorted(
        generated.work_allocations,
        key=lambda row: (
            row.scheduled_date,
            row.item_id,
        ),
    )

    item_by_id = (
        scenario.problem.item_by_id
    )

    lines = [
        (
            f"# {scenario.scenario_id} — "
            f"{flavour}"
        ),
        "",
        scenario.description,
        "",
    ]

    current = None

    for row in rows:
        if row.scheduled_date != current:
            current = row.scheduled_date

            lines.extend([
                (
                    "## "
                    f"{current.isoformat()} "
                    f"— "
                    f"{generated.daily_hours[current]}h"
                ),
                "",
            ])

        item = item_by_id[
            row.item_id
        ]

        metadata = []

        if item.due_date:
            metadata.append(
                "due "
                + item.due_date.isoformat()
            )

        if item.release_date:
            metadata.append(
                "release "
                + item.release_date.isoformat()
            )

        if item.anchor_date:
            metadata.append(
                "anchor "
                + item.anchor_date.isoformat()
            )

        suffix = (
            ""
            if not metadata
            else " — " + ", ".join(metadata)
        )

        lines.append(
            "- "
            f"item {row.item_id}: "
            f"{row.hours}h "
            f"({row.percentage}%)"
            f"{suffix}"
        )

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--output-root",
        type=Path,
        required=True,
    )

    args = parser.parse_args()

    root = args.output_root.resolve()

    if root.exists():
        raise FileExistsError(root)

    root.mkdir(parents=True)

    artifact = {
        "schema_version": 1,
        "stage": "C11.8",
        "purpose":
            "multi_fixture_production_flavour_validation",
        "scenario_count": 0,
        "production_schedules_generated": 0,
        "research_scheduler_trials_executed": 0,
        "production_parameters_frozen": False,
        "scenarios": {},
    }

    review = [
        "# ARC C11.8 multi-fixture human review",
        "",
        (
            "These scenarios challenge the production planner; "
            "they are not tuning workloads."
        ),
        "",
    ]

    failures = []

    for scenario in validation_scenarios():
        artifact["scenario_count"] += 1

        scenario_payload = {
            "description":
                scenario.description,
            "flavours": {},
        }

        generated_rows = {}

        for flavour in (
            "lock-in",
            "monk",
        ):
            generated = (
                generate_flavour_schedule(
                    scenario.problem,
                    flavour,
                    explicit_total_hours=
                        scenario.explicit_total_hours,
                )
            )

            validation = (
                validate_dynamic_plan(
                    scenario.problem,
                    generated.plan,
                )
            )

            if validation.violations:
                failures.append(
                    (
                        scenario.scenario_id,
                        flavour,
                        "hard_validation",
                        [
                            str(row)
                            for row in
                            validation.violations
                        ],
                    )
                )

            data = metrics(
                scenario,
                generated,
            )

            data["hard_violation_count"] = (
                len(validation.violations)
            )

            data["soft_violation_count"] = (
                len(validation.soft_violations)
            )

            scenario_payload[
                "flavours"
            ][flavour] = data

            generated_rows[
                flavour
            ] = generated

            artifact[
                "production_schedules_generated"
            ] += 1

            (
                root
                / (
                    scenario.scenario_id
                    + "__"
                    + flavour
                    + ".md"
                )
            ).write_text(
                markdown_schedule(
                    scenario,
                    flavour,
                    generated,
                ),
                encoding="utf-8",
            )

        lock = (
            scenario_payload[
                "flavours"
            ]["lock-in"]
        )

        monk = (
            scenario_payload[
                "flavours"
            ]["monk"]
        )

        scenario_payload[
            "relationship_checks"
        ] = {
            "monk_peak_not_above_lock_in":
                D(monk["max_daily_hours"])
                <= D(lock["max_daily_hours"]),
            "lock_in_finishes_no_later":
                lock["final_active_date"]
                <= monk["final_active_date"],
        }

        artifact[
            "scenarios"
        ][
            scenario.scenario_id
        ] = scenario_payload

        review.extend([
            (
                "## "
                + scenario.scenario_id
            ),
            "",
            scenario.description,
            "",
            (
                "**Lock-in:** "
                f'{lock["active_day_count"]} active days, '
                f'peak {lock["max_daily_hours"]}h, '
                f'mean {lock["mean_active_day_hours"]}h, '
                f'max session {lock["max_single_session_hours"]}h, '
                f'gaps {lock["continuity_gap_count"]}, '
                f'non-final <1h sessions '
                f'{lock["sub_hour_nonfinal_session_count"]}.'
            ),
            "",
            (
                "**Monk:** "
                f'{monk["active_day_count"]} active days, '
                f'peak {monk["max_daily_hours"]}h, '
                f'mean {monk["mean_active_day_hours"]}h, '
                f'max session {monk["max_single_session_hours"]}h, '
                f'gaps {monk["continuity_gap_count"]}, '
                f'non-final <1h sessions '
                f'{monk["sub_hour_nonfinal_session_count"]}.'
            ),
            "",
            (
                "Relationship checks: "
                f'Monk peak <= Lock-in = '
                f'{scenario_payload["relationship_checks"]["monk_peak_not_above_lock_in"]}; '
                f'Lock-in finishes no later = '
                f'{scenario_payload["relationship_checks"]["lock_in_finishes_no_later"]}.'
            ),
            "",
        ])

    artifact[
        "hard_validation_failure_count"
    ] = len(failures)

    artifact[
        "hard_validation_failures"
    ] = failures

    write_json(
        root / "c11_8_validation.json",
        artifact,
    )

    (
        root / "HUMAN_REVIEW.md"
    ).write_text(
        "\n".join(review) + "\n",
        encoding="utf-8",
    )

    print("=" * 78)
    print(
        "ARC C11.8 MULTI-FIXTURE VALIDATION"
    )
    print("=" * 78)

    print(
        "scenario_count="
        f'{artifact["scenario_count"]}'
    )

    print(
        "production_schedules_generated="
        f'{artifact["production_schedules_generated"]}'
    )

    print(
        "hard_validation_failure_count="
        f'{artifact["hard_validation_failure_count"]}'
    )

    print(
        "research_scheduler_trials_executed=0"
    )

    print(
        "production_parameters_frozen=False"
    )

    print()
    print(
        root / "HUMAN_REVIEW.md"
    )

    return (
        0
        if not failures
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
