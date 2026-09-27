from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(
    0,
    str(ROOT),
)

from arena.production.acceptance import (
    evaluate_parameters,
    parameter_grid,
    satisfies_flavour,
)


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


def _accepted_rows(
    flavour: str,
) -> list:
    return [
        row
        for row in parameter_grid()
        if satisfies_flavour(
            flavour,
            row,
        )
    ]


def _boundary_examples(
    flavour: str,
    accepted: list,
) -> list[dict]:
    """Return deterministic examples only.

    These are not selected production parameters.
    """

    ordered = sorted(
        accepted,
        key=lambda row: (
            row.timing_weight,
            row.continuity_weight,
            row.avoidable_idle_weight,
            row.same_day_repeat_weight,
            row.concentration_weight,
            row.concentration_free_sessions,
        ),
    )

    examples = []

    for row in ordered[:5]:
        examples.append({
            "parameters":
                asdict(row),
            "acceptance": [
                {
                    "case_id":
                        result.case_id,
                    "preferred_cost":
                        result.preferred_cost,
                    "rejected_cost":
                        result.rejected_cost,
                    "passes":
                        result.passes,
                }
                for result
                in evaluate_parameters(
                    flavour,
                    row,
                )
            ],
        })

    return examples


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--output-root",
        type=Path,
        required=True,
    )

    args = parser.parse_args()

    grid = parameter_grid()

    lock_in = _accepted_rows(
        "lock-in"
    )

    monk = _accepted_rows(
        "monk"
    )

    if not lock_in:
        raise AssertionError(
            "No Lock-in parameters satisfy "
            "the frozen behavioural contract"
        )

    if not monk:
        raise AssertionError(
            "No Monk parameters satisfy "
            "the frozen behavioural contract"
        )

    artifact = {
        "schema_version": 1,
        "stage": "C11.3",
        "purpose":
            "behavioural_acceptance_parameter_feasibility",
        "grid_size":
            len(grid),
        "scheduler_trials_executed":
            0,
        "benchmark_scenarios_used":
            0,
        "c7_c8_c9_c10_retuned":
            False,
        "production_parameters_selected":
            False,
        "acceptance_cases": {
            "common": [
                "common_continuity",
                "common_anti_cram",
            ],
            "lock-in": [
                "lock_in_avoid_idle",
                "lock_in_prefers_earlier_progress",
            ],
            "monk": [
                "monk_smooths_heavy_day",
                "monk_prefers_smooth_over_earliest",
            ],
        },
        "lock-in": {
            "accepted_parameter_count":
                len(lock_in),
            "accepted_fraction":
                len(lock_in)
                / len(grid),
            "boundary_examples":
                _boundary_examples(
                    "lock-in",
                    lock_in,
                ),
        },
        "monk": {
            "accepted_parameter_count":
                len(monk),
            "accepted_fraction":
                len(monk)
                / len(grid),
            "boundary_examples":
                _boundary_examples(
                    "monk",
                    monk,
                ),
        },
    }

    output_path = (
        args.output_root.resolve()
        / "c11_3_acceptance_search.json"
    )

    write_json(
        output_path,
        artifact,
    )

    print("=" * 78)
    print(
        "ARC C11.3 BEHAVIOURAL ACCEPTANCE SEARCH"
    )
    print("=" * 78)

    print(
        f'grid_size={artifact["grid_size"]}'
    )

    print(
        "lock_in_accepted="
        f'{artifact["lock-in"]["accepted_parameter_count"]}'
    )

    print(
        "monk_accepted="
        f'{artifact["monk"]["accepted_parameter_count"]}'
    )

    print(
        "production_parameters_selected=False"
    )

    print(
        "benchmark_scenarios_used=0"
    )

    print(
        "SCHEDULER_TRIALS_EXECUTED=0"
    )

    print(
        "C7_C8_C9_C10_RETUNED=0"
    )

    print(
        f"ARTIFACT={output_path}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
