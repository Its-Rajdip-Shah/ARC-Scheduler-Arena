from __future__ import annotations

import argparse
import csv
from dataclasses import fields
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BACKEND))

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
from arena.c10.review import (
    calendar_rows,
    performance_payload,
    render_review_markdown,
)
from arena.experiments.paired import (
    WorkloadCase,
)
from arena.experiments.v1_runner import (
    _isolated_trial,
)
from arena.generation.materialize import (
    materialize_blueprint,
)
from arena.scheduling.adapter import (
    problem_from_user,
)
from scripts.cloud.run_c7_4c_confirmation import (
    reconstruct_source_full_plan,
)


EXPECTED_C101_PLAN_SHA256 = (
    "c944ae994b9d952bfcab46ff0e3d63f7dec2c0ed83f6be6f52dc01a19e71ff31"
)

EXPECTED_C101_FIXTURE_SHA256 = (
    "7525da0537c0b401e7fed4786532d4a70d9c5822b35a876a1110c63e7cb05aa8"
)

RUN_SEED = 1901
TRIAL_WALL_SECONDS = 45.0


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
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

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


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--c10-plan",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--c10-fixture",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--output-root",
        type=Path,
        required=True,
    )

    args = parser.parse_args()

    plan_path = (
        args.c10_plan.resolve()
    )

    fixture_path = (
        args.c10_fixture.resolve()
    )

    if (
        file_sha256(plan_path)
        != EXPECTED_C101_PLAN_SHA256
    ):
        raise AssertionError(
            "Frozen C10.1 plan SHA mismatch"
        )

    if (
        file_sha256(fixture_path)
        != EXPECTED_C101_FIXTURE_SHA256
    ):
        raise AssertionError(
            "Frozen C10.1 fixture SHA mismatch"
        )

    plan_artifact = json.loads(
        plan_path.read_text(
            encoding="utf-8"
        )
    )

    fixture_artifact = json.loads(
        fixture_path.read_text(
            encoding="utf-8"
        )
    )

    if (
        plan_artifact[
            "execution_status"
        ]
        != "plan_only"
    ):
        raise AssertionError(
            "C10.1 source must be plan-only"
        )

    if (
        plan_artifact[
            "scheduler_trials_executed"
        ]
        != 0
    ):
        raise AssertionError(
            "C10.1 source already executed trials"
        )

    if (
        plan_artifact["run_seed"]
        != RUN_SEED
    ):
        raise AssertionError(
            "C10.1 run seed changed"
        )

    if float(
        plan_artifact[
            "trial_wall_seconds"
        ]
    ) != TRIAL_WALL_SECONDS:
        raise AssertionError(
            "C10.1 wall budget changed"
        )

    if (
        plan_artifact["fixture"]
        != fixture_artifact
    ):
        raise AssertionError(
            "C10.1 plan/fixture mismatch"
        )

    fixture = (
        build_realistic_semester_fixture()
    )

    if (
        fixture_manifest(fixture)
        != fixture_artifact
    ):
        raise AssertionError(
            "Current fixture implementation "
            "differs from frozen C10.1 artifact"
        )

    materialized = (
        materialize_blueprint(
            fixture.blueprint,
            email=
                "arena-c10-review@local.test",
        )
    )

    problem = problem_from_user(
        materialized.user,
        C10_TODAY,
    )

    key_by_id = {
        row.pk: key
        for key, row
        in materialized.by_key.items()
        if row.pk in problem.item_by_id
    }

    if len(key_by_id) != 20:
        raise AssertionError(
            "Expected 20 canonical "
            "C10 frontier items"
        )

    scratch = (
        args.output_root.resolve()
        .with_name(
            args.output_root.name
            + "_SOURCE_SCRATCH"
        )
    )

    if scratch.exists():
        shutil.rmtree(scratch)

    source_plan = (
        reconstruct_source_full_plan(
            scratch
        )
    )

    candidate_by_id = {
        candidate.candidate_id:
            candidate
        for candidate
        in source_plan.candidates
    }

    candidate_specs = (
        plan_artifact["candidates"]
    )

    if len(candidate_specs) != 6:
        raise AssertionError(
            "Expected exactly six "
            "C10 candidates"
        )

    frozen_ids = tuple(
        row["source_candidate_id"]
        for row in candidate_specs
    )

    if len(set(frozen_ids)) != 6:
        raise AssertionError(
            "Duplicate C10 candidate"
        )

    missing = [
        candidate_id
        for candidate_id in frozen_ids
        if candidate_id
        not in candidate_by_id
    ]

    if missing:
        raise AssertionError(
            "Frozen candidate missing from "
            f"source plan: {missing}"
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

    case = WorkloadCase(
        workload_id=
            fixture.fixture_id,
        family=
            "c10_realistic_arc",
        problem=problem,
        workload_seed=
            fixture.blueprint.seed,
    )

    results = []
    all_calendar_rows = []

    print("=" * 78)
    print(
        "ARC C10.2 SIX-FINALIST "
        "HUMAN-REVIEW RUN"
    )
    print("=" * 78)
    print(
        "candidate_count=6"
    )
    print(
        "run_seed=1901"
    )
    print(
        "trial_wall_seconds=45"
    )
    print(
        "retuning_allowed=False"
    )
    print(
        "human_review_external_to_search=True"
    )
    print()

    for index, spec in enumerate(
        candidate_specs,
        start=1,
    ):
        candidate = candidate_by_id[
            spec[
                "source_candidate_id"
            ]
        ]

        print(
            f"[{index}/6] RUN "
            f'{spec["label"]} '
            f'role={spec["role"]}'
        )

        record, wall_seconds = (
            _isolated_trial(
                case,
                candidate.constructor,
                candidate.improver,
                RUN_SEED,
                candidate
                .comparison_objective,
                TRIAL_WALL_SECONDS,
            )
        )

        candidate_dir = (
            output_root
            / f"{index:02d}_{spec['label']}"
        )

        candidate_dir.mkdir(
            parents=True
        )

        if record is None:
            status = "wall_timeout"
            rows = []
            performance = None
            algorithm_seconds = None
            error_type = None
            error_message = None
            record_payload = {
                "status":
                    status,
                "wall_seconds":
                    wall_seconds,
            }

        else:
            status = record.status
            algorithm_seconds = (
                record.total_seconds
            )
            error_type = (
                record.error_type
            )
            error_message = (
                record.error_message
            )

            final_plan = (
                record.final_plan
                if status == "ok"
                else None
            )

            rows = (
                []
                if final_plan is None
                else calendar_rows(
                    problem,
                    final_plan,
                    key_by_id=
                        key_by_id,
                    display_names=
                        fixture
                        .display_names,
                    groups=
                        fixture.groups,
                )
            )

            performance = (
                None
                if record
                .final_performance
                is None
                else performance_payload(
                    record
                    .final_performance
                )
            )

            record_payload = {
                "workload_id":
                    record.workload_id,
                "family":
                    record.family,
                "workload_seed":
                    record.workload_seed,
                "run_seed":
                    record.run_seed,
                "constructor_id":
                    record.constructor_id,
                "improver_id":
                    record.improver_id,
                "status":
                    record.status,
                "constructor_seconds":
                    record
                    .constructor_seconds,
                "improver_seconds":
                    record
                    .improver_seconds,
                "total_seconds":
                    record.total_seconds,
                "isolated_wall_seconds":
                    wall_seconds,
                "iterations":
                    record.iterations,
                "evaluations":
                    record.evaluations,
                "termination_reason":
                    record
                    .termination_reason,
                "error_type":
                    record.error_type,
                "error_message":
                    record.error_message,
                "final_performance":
                    performance,
                "calendar":
                    rows,
            }

        review_payload = {
            "schema_version": 1,
            "stage": "C10.2",
            "fixture_id":
                fixture.fixture_id,
            "candidate_id":
                spec[
                    "source_candidate_id"
                ],
            "label":
                spec["label"],
            "role":
                spec["role"],
            "semantic_fingerprint":
                spec[
                    "semantic_fingerprint"
                ],
            "run_seed":
                RUN_SEED,
            "trial_wall_seconds":
                TRIAL_WALL_SECONDS,
            "status":
                status,
            "isolated_wall_seconds":
                wall_seconds,
            "algorithm_seconds":
                algorithm_seconds,
            "error_type":
                error_type,
            "error_message":
                error_message,
            "final_performance":
                performance,
            "calendar":
                rows,
            "human_review_external_to_search":
                True,
            "scalar_human_score_used":
                False,
            "retuning_allowed":
                False,
        }

        write_json(
            candidate_dir
            / "trial.json",
            record_payload,
        )

        write_json(
            candidate_dir
            / "review.json",
            review_payload,
        )

        markdown = (
            render_review_markdown(
                label=
                    spec["label"],
                role=
                    spec["role"],
                status=
                    status,
                run_seed=
                    RUN_SEED,
                wall_seconds=
                    wall_seconds,
                algorithm_seconds=
                    algorithm_seconds,
                rows=
                    rows,
                performance=
                    performance,
                error_type=
                    error_type,
                error_message=
                    error_message,
            )
        )

        (
            candidate_dir
            / "REVIEW.md"
        ).write_text(
            markdown,
            encoding="utf-8",
        )

        for row in rows:
            all_calendar_rows.append({
                "candidate_label":
                    spec["label"],
                "candidate_role":
                    spec["role"],
                **row,
            })

        results.append({
            "candidate_id":
                spec[
                    "source_candidate_id"
                ],
            "label":
                spec["label"],
            "role":
                spec["role"],
            "status":
                status,
            "isolated_wall_seconds":
                wall_seconds,
            "algorithm_seconds":
                algorithm_seconds,
            "allocation_count":
                len(rows),
            "review_path":
                str(
                    candidate_dir
                    / "REVIEW.md"
                ),
            "artifact_path":
                str(
                    candidate_dir
                    / "review.json"
                ),
        })

        print(
            "  status="
            f"{status} "
            "wall_seconds="
            f"{wall_seconds:.6f} "
            "allocations="
            f"{len(rows)}"
        )

    csv_path = (
        output_root
        / "all_candidate_calendars.csv"
    )

    fieldnames = (
        [
            "candidate_label",
            "candidate_role",
            "scheduled_date",
            "weekday",
            "execution_rank",
            "percentage",
            "item_key",
            "display_name",
            "group",
            "duration_category",
            "priority_position",
            "release_date",
            "due_date",
            "anchor_date",
            "remaining_fraction",
        ]
    )

    with csv_path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=fieldnames,
        )

        writer.writeheader()
        writer.writerows(
            all_calendar_rows
        )

    status_counts = {}

    for result in results:
        status_counts[
            result["status"]
        ] = (
            status_counts.get(
                result["status"],
                0,
            )
            + 1
        )

    index = {
        "schema_version": 1,
        "stage": "C10.2",
        "purpose":
            "six_finalist_external_human_review",
        "source_c10_1_plan_sha256":
            EXPECTED_C101_PLAN_SHA256,
        "source_c10_1_fixture_sha256":
            EXPECTED_C101_FIXTURE_SHA256,
        "fixture_id":
            fixture.fixture_id,
        "candidate_count":
            6,
        "trials_executed":
            6,
        "run_seed":
            RUN_SEED,
        "trial_wall_seconds":
            TRIAL_WALL_SECONDS,
        "status_counts":
            status_counts,
        "human_review_external_to_search":
            True,
        "scalar_human_score_used":
            False,
        "retuning_allowed":
            False,
        "automatic_router_training_allowed":
            False,
        "candidate_results":
            results,
        "combined_calendar_csv":
            str(csv_path),
    }

    write_json(
        output_root
        / "c10_2_review_index.json",
        index,
    )

    (
        output_root
        / "README_REVIEW.md"
    ).write_text(
        "\n".join([
            "# ARC C10.2 human review",
            "",
            "Open each numbered candidate directory "
            "and read `REVIEW.md`.",
            "",
            "Review the schedules qualitatively. "
            "Do not assign an overall numeric score.",
            "",
            "The purpose is to identify concrete "
            "human-friendliness concerns that C1 "
            "metrics may not capture.",
            "",
            "Do not use these observations to retune "
            "C7/C8/C9 or train an automatic router.",
            "",
        ]),
        encoding="utf-8",
    )

    print()
    print("=" * 78)
    print(
        "C10.2 EXECUTION COMPLETE"
    )
    print("=" * 78)

    print(
        "trials_executed=6"
    )

    for status in sorted(
        status_counts
    ):
        print(
            f"status_{status}="
            f"{status_counts[status]}"
        )

    print(
        "human_review_external_to_search=True"
    )

    print(
        "scalar_human_score_used=False"
    )

    print(
        "retuning_allowed=False"
    )

    print(
        "automatic_router_training_allowed=False"
    )

    print(
        "INDEX="
        f"{output_root / 'c10_2_review_index.json'}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
