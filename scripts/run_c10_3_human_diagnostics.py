from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(
    0,
    str(ROOT),
)

from arena.c10.human_diagnostics import (
    compute_human_diagnostics,
    diagnostics_payload,
)


EXPECTED_INDEX_SHA256 = (
    "149331e345fdbea6dfdf57d51c87b56a8875b20d19df6247810df739e07c1914"
)


def file_sha256(
    path: Path,
) -> str:
    digest = sha256()

    with path.open("rb") as stream:
        for chunk in iter(
            lambda: stream.read(
                1024 * 1024
            ),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def write_json(
    path: Path,
    payload: dict,
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
        "--review-root",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--output-root",
        type=Path,
        required=True,
    )

    args = parser.parse_args()

    review_root = (
        args.review_root.resolve()
    )

    index_path = (
        review_root
        / "c10_2_review_index.json"
    )

    actual_index_sha = (
        file_sha256(
            index_path
        )
    )

    if (
        actual_index_sha
        != EXPECTED_INDEX_SHA256
    ):
        raise AssertionError(
            "Frozen C10.2 index SHA mismatch: "
            f"{actual_index_sha}"
        )

    index = json.loads(
        index_path.read_text(
            encoding="utf-8"
        )
    )

    if (
        index["trials_executed"]
        != 6
        or index["status_counts"]
        != {"ok": 6}
    ):
        raise AssertionError(
            "C10.2 source execution changed"
        )

    rows = []
    signatures = {}

    for result in index[
        "candidate_results"
    ]:
        artifact = Path(
            result["artifact_path"]
        )

        if not artifact.exists():
            artifact = (
                review_root
                / Path(
                    result[
                        "artifact_path"
                    ]
                ).parent.name
                / "review.json"
            )

        review = json.loads(
            artifact.read_text(
                encoding="utf-8"
            )
        )

        if (
            review["status"]
            != "ok"
        ):
            raise AssertionError(
                "Expected successful "
                "C10.2 review artifact"
            )

        calendar = (
            review["calendar"]
        )

        diagnostics = (
            compute_human_diagnostics(
                calendar
            )
        )

        allocation_signature = tuple(
            sorted(
                (
                    row["scheduled_date"],
                    row["item_key"],
                    row["percentage"],
                )
                for row in calendar
            )
        )

        signatures[
            result["label"]
        ] = allocation_signature

        rows.append({
            "candidate_id":
                result["candidate_id"],
            "label":
                result["label"],
            "role":
                result["role"],
            "diagnostics":
                diagnostics_payload(
                    diagnostics
                ),
        })

    unique_signatures = {
        signature
        for signature
        in signatures.values()
    }

    artifact = {
        "schema_version": 1,
        "stage": "C10.3",
        "purpose":
            "external_human_friendliness_diagnostics",
        "source_c10_2_index_sha256":
            EXPECTED_INDEX_SHA256,
        "candidate_count":
            len(rows),
        "scheduler_trials_executed":
            0,
        "human_review_external_to_search":
            True,
        "scalar_human_score_used":
            False,
        "retuning_allowed":
            False,
        "automatic_router_training_allowed":
            False,
        "unique_calendar_signature_count":
            len(unique_signatures),
        "all_candidates_same_calendar_dates_and_percentages":
            len(unique_signatures) == 1,
        "candidates":
            rows,
    }

    output_path = (
        args.output_root.resolve()
        / "c10_3_human_diagnostics.json"
    )

    write_json(
        output_path,
        artifact,
    )

    print("=" * 78)
    print(
        "ARC C10.3 HUMAN-FRIENDLINESS DIAGNOSTICS"
    )
    print("=" * 78)

    print(
        "candidate_count="
        f'{artifact["candidate_count"]}'
    )

    print(
        "unique_calendar_signature_count="
        f'{artifact["unique_calendar_signature_count"]}'
    )

    print(
        "all_candidates_same_calendar_dates_and_percentages="
        f'{artifact["all_candidates_same_calendar_dates_and_percentages"]}'
    )

    for row in rows:
        diagnostics = (
            row["diagnostics"]
        )

        print(
            "DIAGNOSTIC "
            f'{row["label"]} '
            f'first_day='
            f'{diagnostics["first_day_session_count"]} '
            f'max_day='
            f'{diagnostics["max_sessions_on_day"]} '
            f'same_item_extra='
            f'{diagnostics["same_item_same_day_extra_session_count"]} '
            f'busy4='
            f'{diagnostics["busy_day_count_ge_4"]} '
            f'first_week_fraction='
            f'{diagnostics["first_week_session_fraction"]:.4f}'
        )

    print(
        "SCHEDULER_TRIALS_EXECUTED=0"
    )

    print(
        f"ARTIFACT={output_path}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
