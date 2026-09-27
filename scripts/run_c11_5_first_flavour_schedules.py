from __future__ import annotations

import argparse
import json
import os
from hashlib import sha256
from pathlib import Path
import sys
from decimal import Decimal

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"

sys.path.insert(
    0,
    str(ROOT),
)
sys.path.insert(
    0,
    str(BACKEND),
)

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "arc_backend.settings",
)

import django
django.setup()

from arena.c10.realistic_fixture import (
    C10_TODAY,
    build_realistic_semester_fixture,
    fixture_manifest,
)
from arena.generation.materialize import (
    materialize_blueprint,
)
from arena.production.flavour_planner import (
    generate_flavour_schedule,
)
from arena.production.work_mass import (
    allocation_hours,
    validate_dynamic_plan,
)
from arena.scheduling.adapter import (
    problem_from_user,
)


EXPECTED_FIXTURE_SHA256 = (
    "7525da0537c0b401e7fed4786532d4a70d9c5822b35a876a1110c63e7cb05aa8"
)


def file_sha256(
    path: Path,
) -> str:
    digest = sha256()

    with path.open("rb") as stream:
        for chunk in iter(
            lambda:
                stream.read(
                    1024 * 1024
                ),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def write_json(
    path: Path,
    payload,
) -> None:
    path.write_text(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )


def _rows(
    *,
    generated,
    problem,
    key_by_id,
    fixture,
):
    work_by_key = {
        (
            row.item_id,
            row.scheduled_date,
        ): row
        for row
        in generated.work_allocations
    }

    result = []

    for allocation in sorted(
        generated.plan.allocations,
        key=lambda row: (
            row.scheduled_date,
            row.execution_rank,
            row.item_id,
        ),
    ):
        key = key_by_id[
            allocation.item_id
        ]

        estimate = (
            generated.estimates[
                allocation.item_id
            ]
        )

        work = work_by_key[
            (
                allocation.item_id,
                allocation.scheduled_date,
            )
        ]

        item = problem.item_by_id[
            allocation.item_id
        ]

        result.append({
            "date":
                allocation
                .scheduled_date
                .isoformat(),
            "weekday":
                allocation
                .scheduled_date
                .strftime("%A"),
            "item_key":
                key,
            "name":
                fixture
                .display_names[key],
            "group":
                fixture.groups[key],
            "hours":
                str(
                    work.hours
                    .quantize(
                        Decimal("0.01")
                    )
                ),
            "percentage":
                str(
                    allocation.percentage
                ),
            "duration_category":
                item.duration_category,
            "due_date": (
                None
                if item.due_date
                is None
                else item
                .due_date
                .isoformat()
            ),
            "anchor_date": (
                None
                if item.anchor_date
                is None
                else item
                .anchor_date
                .isoformat()
            ),
            "estimate_total_hours":
                str(
                    estimate.total_hours
                ),
            "estimate_source":
                estimate.source,
        })

    return result


def _markdown(
    flavour: str,
    rows: list[dict],
    daily_hours: dict,
) -> str:
    lines = [
        f"# ARC {flavour.upper()} — first adaptive production schedule",
        "",
        "C11.5 human-review artifact.",
        "",
        "Percentages were derived from estimated work hours; they were not fixed in advance.",
        "",
    ]

    current = None

    for row in rows:
        if row["date"] != current:
            current = row["date"]

            total = daily_hours[
                current
            ]

            lines.extend([
                "",
                (
                    "## "
                    f'{row["weekday"]}, '
                    f'{current} '
                    f'— {total:.2f}h total'
                ),
                "",
            ])

        metadata = []

        if row["due_date"]:
            metadata.append(
                f'due {row["due_date"]}'
            )

        if row["anchor_date"]:
            metadata.append(
                f'anchor {row["anchor_date"]}'
            )

        suffix = (
            ""
            if not metadata
            else (
                " — "
                + ", ".join(
                    metadata
                )
            )
        )

        lines.append(
            "- "
            f'**{row["name"]}** '
            f'[{row["group"]}] — '
            f'{row["hours"]}h '
            f'({row["percentage"]}%)'
            f'{suffix}'
        )

    lines.extend([
        "",
        "## Human reasonability review",
        "",
        "- [ ] Daily hour totals feel realistic.",
        "- [ ] Large tasks receive sensible per-day chunks.",
        "- [ ] Started work maintains momentum.",
        "- [ ] No task is crammed into one absurd day.",
        "- [ ] Empty days make sense for this flavour.",
        "- [ ] Deadline buffer feels reasonable.",
        "- [ ] Dependency chains progress naturally.",
        "- [ ] Lock-in feels aggressive without being ridiculous.",
        "- [ ] Monk feels smoother without procrastinating.",
        "",
    ])

    return "\n".join(
        lines
    ) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--fixture-artifact",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--output-root",
        type=Path,
        required=True,
    )

    args = parser.parse_args()

    fixture_artifact = (
        args.fixture_artifact.resolve()
    )

    actual_sha = file_sha256(
        fixture_artifact
    )

    if (
        actual_sha
        != EXPECTED_FIXTURE_SHA256
    ):
        raise AssertionError(
            "Frozen C10 fixture SHA mismatch: "
            + actual_sha
        )

    frozen_manifest = json.loads(
        fixture_artifact.read_text(
            encoding="utf-8"
        )
    )

    fixture = (
        build_realistic_semester_fixture()
    )

    if (
        fixture_manifest(fixture)
        != frozen_manifest
    ):
        raise AssertionError(
            "Current C10 fixture implementation "
            "does not match frozen artifact"
        )

    materialized = (
        materialize_blueprint(
            fixture.blueprint,
            email=
                "arena-c11-first-flavours@local.test",
        )
    )

    problem = (
        problem_from_user(
            materialized.user,
            C10_TODAY,
        )
    )

    key_by_id = {
        row.pk: key
        for key, row
        in materialized.by_key.items()
        if row.pk in problem.item_by_id
    }

    if len(key_by_id) != 20:
        raise AssertionError(
            "Expected 20 executable "
            "C10 frontier items"
        )

    output_root = (
        args.output_root.resolve()
    )

    if output_root.exists():
        raise FileExistsError(
            output_root
        )

    output_root.mkdir(
        parents=True,
    )

    summary = {
        "schema_version": 1,
        "stage": "C11.5",
        "purpose":
            "first_human_reviewable_adaptive_flavour_schedules",
        "source_fixture_sha256":
            EXPECTED_FIXTURE_SHA256,
        "research_scheduler_trials_executed":
            0,
        "production_schedules_generated":
            2,
        "production_parameters_frozen":
            False,
        "human_review_required":
            True,
        "flavours": {},
    }

    generated_by_flavour = {}

    for flavour in (
        "lock-in",
        "monk",
    ):
        generated = (
            generate_flavour_schedule(
                problem,
                flavour,
            )
        )

        validation = (
            validate_dynamic_plan(
                problem,
                generated.plan,
            )
        )

        if validation.violations:
            raise AssertionError(
                f"{flavour} hard violations: "
                f"{validation.violations}"
            )

        rows = _rows(
            generated=generated,
            problem=problem,
            key_by_id=
                key_by_id,
            fixture=fixture,
        )

        daily_hours = {
            day.isoformat():
                hours
            for day, hours
            in generated
            .daily_hours.items()
            if hours > 0
        }

        generated_by_flavour[
            flavour
        ] = (
            generated,
            rows,
            daily_hours,
        )

        write_json(
            output_root
            / f"{flavour}.json",
            {
                "flavour":
                    flavour,
                "calendar":
                    rows,
                "daily_hours": {
                    key: str(value)
                    for key, value
                    in daily_hours.items()
                },
                "validation": {
                    "violations": [
                        str(row)
                        for row
                        in validation
                        .violations
                    ],
                    "infeasibilities": [
                        str(row)
                        for row
                        in validation
                        .infeasibilities
                    ],
                    "soft_violations": [
                        str(row)
                        for row
                        in validation
                        .soft_violations
                    ],
                },
            },
        )

        (
            output_root
            / f"{flavour.upper()}.md"
        ).write_text(
            _markdown(
                flavour,
                rows,
                daily_hours,
            ),
            encoding="utf-8",
        )

        max_day = max(
            daily_hours.values()
        )

        active_days = len(
            daily_hours
        )

        last_day = max(
            daily_hours
        )

        summary["flavours"][
            flavour
        ] = {
            "active_day_count":
                active_days,
            "max_daily_hours":
                str(max_day),
            "final_active_date":
                last_day,
            "allocation_count":
                len(rows),
            "soft_violation_count":
                len(
                    validation
                    .soft_violations
                ),
        }

    side = [
        "# ARC C11.5 — Lock-in vs Monk",
        "",
        "First human-review comparison of the dynamic production planner.",
        "",
        "These are provisional flavour schedules, not frozen production behaviour.",
        "",
    ]

    all_dates = sorted({
        date_key
        for _, _, daily
        in generated_by_flavour.values()
        for date_key
        in daily
    })

    lock_rows = {
        day: [
            row
            for row
            in generated_by_flavour[
                "lock-in"
            ][1]
            if row["date"] == day
        ]
        for day in all_dates
    }

    monk_rows = {
        day: [
            row
            for row
            in generated_by_flavour[
                "monk"
            ][1]
            if row["date"] == day
        ]
        for day in all_dates
    }

    lock_daily = (
        generated_by_flavour[
            "lock-in"
        ][2]
    )

    monk_daily = (
        generated_by_flavour[
            "monk"
        ][2]
    )

    for day in all_dates:
        weekday = (
            date.fromisoformat(
                day
            ).strftime("%A")
        )

        side.extend([
            f"## {weekday}, {day}",
            "",
            (
                "### Lock-in — "
                f'{lock_daily.get(day, Decimal("0")):.2f}h'
            ),
            "",
        ])

        if lock_rows[day]:
            for row in lock_rows[
                day
            ]:
                side.append(
                    "- "
                    f'{row["name"]}: '
                    f'{row["hours"]}h '
                    f'({row["percentage"]}%)'
                )
        else:
            side.append(
                "- _empty_"
            )

        side.extend([
            "",
            (
                "### Monk — "
                f'{monk_daily.get(day, Decimal("0")):.2f}h'
            ),
            "",
        ])

        if monk_rows[day]:
            for row in monk_rows[
                day
            ]:
                side.append(
                    "- "
                    f'{row["name"]}: '
                    f'{row["hours"]}h '
                    f'({row["percentage"]}%)'
                )
        else:
            side.append(
                "- _empty_"
            )

        side.append("")

    (
        output_root
        / "SIDE_BY_SIDE.md"
    ).write_text(
        "\n".join(side) + "\n",
        encoding="utf-8",
    )

    write_json(
        output_root
        / "c11_5_summary.json",
        summary,
    )

    print("=" * 78)
    print(
        "ARC C11.5 FIRST ADAPTIVE FLAVOUR SCHEDULES"
    )
    print("=" * 78)

    for flavour in (
        "lock-in",
        "monk",
    ):
        info = summary[
            "flavours"
        ][flavour]

        print(
            f'{flavour}: '
            f'active_days={info["active_day_count"]} '
            f'max_daily_hours={info["max_daily_hours"]} '
            f'final_active_date={info["final_active_date"]} '
            f'allocations={info["allocation_count"]} '
            f'soft_violations={info["soft_violation_count"]}'
        )

    print()
    print(
        "RESEARCH_SCHEDULER_TRIALS_EXECUTED=0"
    )
    print(
        "PRODUCTION_SCHEDULES_GENERATED=2"
    )
    print(
        "PRODUCTION_PARAMETERS_FROZEN=0"
    )
    print(
        "HUMAN_REVIEW_REQUIRED=1"
    )
    print()
    print(
        f"LOCK_IN={output_root / 'LOCK-IN.md'}"
    )
    print(
        f"MONK={output_root / 'MONK.md'}"
    )
    print(
        f"SIDE_BY_SIDE={output_root / 'SIDE_BY_SIDE.md'}"
    )

    return 0


if __name__ == "__main__":
    from datetime import date

    raise SystemExit(
        main()
    )
