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

from arena.tuning.workload_policy import (
    freeze_workload_policy,
    workload_policy_artifact,
)


EXPECTED_C91_SHA256 = (
    '257c8077b5fe6d042be43b29e7bbabb66a4ad69e156fadbdd70b96b96bd75c23'
)

EXPECTED_C76_SHA256 = (
    'a14fad452a3f0d0de243dbd039e74edb50c6f5f318b0c8136c0d728ab09d9783'
)

EXPECTED_LABELS = (
    'pressure+lns60',
    'aggressive+none',
    'aggressive+lns60',
    'aggressive+alns80',
    'stable+none',
    'stable+alns80',
)


def sha256_file(
    path: Path,
) -> str:
    digest = sha256()

    with path.open('rb') as stream:
        for chunk in iter(
            lambda:
                stream.read(
                    1024 * 1024
                ),
            b'',
        ):
            digest.update(chunk)

    return digest.hexdigest()


def write_json(
    path: Path,
    payload: dict,
) -> None:
    encoded = (
        json.dumps(
            payload,
            sort_keys=True,
            separators=(',', ':'),
            ensure_ascii=True,
            allow_nan=False,
        )
        + '\n'
    )

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        encoded,
        encoding='utf-8',
    )


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        '--c91-analysis',
        type=Path,
        required=True,
    )

    parser.add_argument(
        '--c76-contestants',
        type=Path,
        required=True,
    )

    parser.add_argument(
        '--output-root',
        type=Path,
        required=True,
    )

    args = parser.parse_args()

    c91 = (
        args.c91_analysis.resolve()
    )

    c76 = (
        args
        .c76_contestants
        .resolve()
    )

    output_root = (
        args.output_root.resolve()
    )

    if (
        sha256_file(c91)
        != EXPECTED_C91_SHA256
    ):
        raise AssertionError(
            'Frozen C9.1 SHA mismatch'
        )

    if (
        sha256_file(c76)
        != EXPECTED_C76_SHA256
    ):
        raise AssertionError(
            'Frozen C7.6 SHA mismatch'
        )

    c91_artifact = json.loads(
        c91.read_text(
            encoding='utf-8'
        )
    )

    c76_artifact = json.loads(
        c76.read_text(
            encoding='utf-8'
        )
    )

    c76_labels = tuple(
        row['label']
        for row in c76_artifact[
            'contestants'
        ]
    )

    if c76_labels != EXPECTED_LABELS:
        raise AssertionError(
            'Frozen C7.6 contestant '
            'identity/order changed'
        )

    c91_labels = tuple(
        row['label']
        for row in c91_artifact[
            'candidates'
        ]
    )

    if c91_labels != EXPECTED_LABELS:
        raise AssertionError(
            'Frozen C9.1 candidate '
            'identity/order changed'
        )

    policy = freeze_workload_policy(
        c91_artifact,
        expected_candidate_labels=
            EXPECTED_LABELS,
    )

    policy_ids = {
        role.candidate_id
        for role in policy.roles
    }

    c76_ids = {
        row[
            'source_candidate_id'
        ]
        for row
        in c76_artifact[
            'contestants'
        ]
    }

    if policy_ids != c76_ids:
        raise AssertionError(
            'C9.2 policy candidate IDs '
            'do not exactly match frozen C7.6'
        )

    artifact = (
        workload_policy_artifact(
            policy,
            c91_sha256=
                EXPECTED_C91_SHA256,
            c76_sha256=
                EXPECTED_C76_SHA256,
        )
    )

    output_path = (
        output_root
        / 'c9_2_workload_policy.json'
    )

    write_json(
        output_path,
        artifact,
    )

    print('=' * 78)
    print(
        'ARC C9.2 FROZEN WORKLOAD POLICY'
    )
    print('=' * 78)

    print(
        f'candidate_count='
        f'{artifact["candidate_count"]}'
    )

    print(
        'automatic_router_enabled='
        f'{artifact["automatic_router_enabled"]}'
    )

    print(
        'learned_classifier_used='
        f'{artifact["learned_classifier_used"]}'
    )

    print(
        'c8_evidence_used_for_policy='
        f'{artifact["c8_evidence_used_for_policy"]}'
    )

    print(
        'scalar_candidate_score_used='
        f'{artifact["scalar_candidate_score_used"]}'
    )

    print(
        'development_only_policy='
        f'{artifact["development_only_policy"]}'
    )

    print()

    for row in artifact['roles']:
        print(
            'ROLE '
            f'{row["role"]} '
            f'{row["label"]} '
            f'pareto='
            f'{row["pareto_scenario_count"]}/'
            f'{row["scorable_scenario_count"]}'
        )

    print()

    print(
        f'ARTIFACT={output_path}'
    )

    print(
        'SCHEDULER_TRIALS_EXECUTED=0'
    )

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
