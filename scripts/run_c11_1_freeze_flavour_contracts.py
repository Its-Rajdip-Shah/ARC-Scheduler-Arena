from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(
    0,
    str(ROOT),
)

from arena.production.flavours import (
    flavour_contract_artifact,
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


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--output-root",
        type=Path,
        required=True,
    )

    args = parser.parse_args()

    output_root = (
        args.output_root.resolve()
    )

    if output_root.exists():
        raise FileExistsError(
            output_root
        )

    artifact = (
        flavour_contract_artifact()
    )

    output_path = (
        output_root
        / "c11_1_flavour_contracts.json"
    )

    write_json(
        output_path,
        artifact,
    )

    print("=" * 78)
    print(
        "ARC C11.1 PRODUCTION FLAVOUR CONTRACTS"
    )
    print("=" * 78)

    print(
        "flavour_count="
        f'{artifact["flavour_count"]}'
    )

    for flavour in artifact[
        "flavours"
    ]:
        print(
            "FLAVOUR "
            f'{flavour["flavour"]} '
            f'task_continuity='
            f'{flavour["task_continuity_required"]}'
        )

    print(
        "objective_status="
        f'{artifact["objective_status"]}'
    )

    print(
        "canonical_invariants_unchanged="
        f'{artifact["common_requirements"]["canonical_invariants_unchanged"]}'
    )

    print(
        "c7_c8_c9_retuning_allowed="
        f'{artifact["common_requirements"]["c7_c8_c9_retuning_allowed"]}'
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
