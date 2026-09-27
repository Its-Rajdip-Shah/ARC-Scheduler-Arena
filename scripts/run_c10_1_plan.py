from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
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
from arena.evaluation.features import (
    characterize_workload,
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


EXPECTED_C76_SHA256 = (
    "a14fad452a3f0d0de243dbd039e74edb50c6f5f318b0c8136c0d728ab09d9783"
)

EXPECTED_C92_SHA256 = (
    "b14beb3ef2fd19f3cc3d349c386a4872951636e4af41f8527c4a304e01a339c4"
)


def file_sha256(path: Path) -> str:
    digest = sha256()

    with path.open("rb") as stream:
        for chunk in iter(
            lambda: stream.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def write_json(
    path: Path,
    value: dict,
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(
            value,
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
        "--c76-contestants",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--c92-policy",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--output-root",
        type=Path,
        required=True,
    )

    args = parser.parse_args()

    c76_path = (
        args.c76_contestants.resolve()
    )

    c92_path = (
        args.c92_policy.resolve()
    )

    if (
        file_sha256(c76_path)
        != EXPECTED_C76_SHA256
    ):
        raise AssertionError(
            "Frozen C7.6 SHA mismatch"
        )

    if (
        file_sha256(c92_path)
        != EXPECTED_C92_SHA256
    ):
        raise AssertionError(
            "Frozen C9.2 SHA mismatch"
        )

    c76 = json.loads(
        c76_path.read_text(
            encoding="utf-8"
        )
    )

    c92 = json.loads(
        c92_path.read_text(
            encoding="utf-8"
        )
    )

    frozen_rows = c76["contestants"]

    if len(frozen_rows) != 6:
        raise AssertionError(
            "Expected six C7.6 contestants"
        )

    role_by_id = {
        row["candidate_id"]:
            row["role"]
        for row in c92["roles"]
    }

    frozen_ids = tuple(
        row["source_candidate_id"]
        for row in frozen_rows
    )

    if set(role_by_id) != set(frozen_ids):
        raise AssertionError(
            "C9.2/C7.6 candidate identity mismatch"
        )

    output_root = (
        args.output_root.resolve()
    )

    if output_root.exists():
        raise FileExistsError(
            output_root
        )

    scratch = (
        output_root.with_name(
            output_root.name
            + "_SOURCE_SCRATCH"
        )
    )

    if scratch.exists():
        import shutil
        shutil.rmtree(scratch)

    source_plan = (
        reconstruct_source_full_plan(
            scratch
        )
    )

    candidates_by_id = {
        candidate.candidate_id:
            candidate
        for candidate
        in source_plan.candidates
    }

    missing = [
        candidate_id
        for candidate_id in frozen_ids
        if candidate_id
        not in candidates_by_id
    ]

    if missing:
        raise AssertionError(
            f"Frozen candidates missing from "
            f"reconstructed source plan: {missing}"
        )

    fixture = (
        build_realistic_semester_fixture()
    )

    materialized = (
        materialize_blueprint(
            fixture.blueprint,
            email=
                "arena-c10-realistic@local.test",
        )
    )

    problem = problem_from_user(
        materialized.user,
        C10_TODAY,
    )

    characterization = (
        characterize_workload(
            materialized.user,
            C10_TODAY,
        )
    )

    key_by_pk = {
        row.pk: key
        for key, row
        in materialized.by_key.items()
    }

    problem_snapshot = {
        "today":
            problem.today.isoformat(),
        "item_count":
            len(problem.items),
        "dependency_count":
            len(problem.dependencies),
        "capacity_by_duration":
            dict(
                problem.capacity_by_duration
            ),
        "overload_dates": sorted(
            day.isoformat()
            for day
            in problem.overload_dates
        ),
        "items": [
            {
                "key":
                    key_by_pk[
                        item.item_id
                    ],
                "duration_category":
                    item.duration_category,
                "priority_position":
                    item.priority_position,
                "release_date": (
                    None
                    if item.release_date is None
                    else item.release_date.isoformat()
                ),
                "due_date": (
                    None
                    if item.due_date is None
                    else item.due_date.isoformat()
                ),
                "anchor_date": (
                    None
                    if item.anchor_date is None
                    else item.anchor_date.isoformat()
                ),
                "percent_completed":
                    str(
                        item.percent_completed
                    ),
                "remaining_fraction":
                    str(
                        item.remaining_fraction
                    ),
                "is_residual":
                    item.is_residual,
            }
            for item in problem.items
        ],
        "dependencies": [
            {
                "prerequisite_key":
                    key_by_pk[
                        edge.prerequisite_id
                    ],
                "dependent_key":
                    key_by_pk[
                        edge.dependent_id
                    ],
            }
            for edge
            in problem.dependencies
        ],
    }

    candidate_rows = []

    for frozen in frozen_rows:
        candidate = candidates_by_id[
            frozen[
                "source_candidate_id"
            ]
        ]

        candidate_rows.append({
            "source_candidate_id":
                candidate.candidate_id,
            "label":
                frozen["label"],
            "role":
                role_by_id[
                    candidate.candidate_id
                ],
            "objective_id":
                candidate.objective_id,
            "constructor_arm_id":
                candidate
                .constructor
                .arm_id,
            "improver_arm_id":
                candidate
                .improver
                .arm_id,
            "semantic_fingerprint":
                frozen[
                    "semantic_fingerprint"
                ],
        })

    artifact = {
        "schema_version": 1,
        "stage": "C10.1",
        "purpose":
            "realistic_arc_fixture_review_plan",
        "execution_status":
            "plan_only",
        "scheduler_trials_executed":
            0,
        "synthetic_fixture":
            True,
        "contains_personal_user_data":
            False,
        "c7_6_sha256":
            EXPECTED_C76_SHA256,
        "c9_2_sha256":
            EXPECTED_C92_SHA256,
        "candidate_count":
            len(candidate_rows),
        "run_seed":
            1901,
        "trial_wall_seconds":
            45,
        "human_review_external_to_search":
            True,
        "retuning_allowed":
            False,
        "automatic_router_training_allowed":
            False,
        "fixture":
            fixture_manifest(fixture),
        "problem_snapshot":
            problem_snapshot,
        "phi89": {
            name: value
            for name, value
            in characterization.raw
        },
        "candidates":
            candidate_rows,
        "next_stage": (
            "Execute exactly one frozen "
            "C10 review trial for each of "
            "the six candidates on this "
            "fixture and export human-readable "
            "calendar/review artifacts."
        ),
    }

    write_json(
        output_root
        / "c10_1_review_plan.json",
        artifact,
    )

    write_json(
        output_root
        / "c10_1_fixture.json",
        fixture_manifest(fixture),
    )

    print("=" * 78)
    print(
        "ARC C10.1 REALISTIC FIXTURE PLAN"
    )
    print("=" * 78)

    print(
        f"fixture_id="
        f"{fixture.fixture_id}"
    )

    print(
        f"canonical_items="
        f"{len(problem.items)}"
    )

    print(
        f"dependencies="
        f"{len(problem.dependencies)}"
    )

    print(
        f"phi89_features="
        f"{len(characterization.raw)}"
    )

    print(
        f"candidate_count="
        f"{len(candidate_rows)}"
    )

    for row in candidate_rows:
        print(
            "CANDIDATE "
            f'{row["role"]} '
            f'{row["label"]} '
            f'{row["source_candidate_id"]}'
        )

    print(
        "contains_personal_user_data=False"
    )

    print(
        "human_review_external_to_search=True"
    )

    print(
        "retuning_allowed=False"
    )

    print(
        "SCHEDULER_TRIALS_EXECUTED=0"
    )

    print(
        "PLAN="
        f"{output_root / 'c10_1_review_plan.json'}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
