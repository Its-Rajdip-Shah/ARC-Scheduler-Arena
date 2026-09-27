from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / 'backend'

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BACKEND))

os.environ.setdefault(
    'DJANGO_SETTINGS_MODULE',
    'arc_backend.settings',
)

import django
django.setup()

from arena.tuning.contestants import (
    c8_contestant_artifact,
    freeze_c8_contestants,
)
from scripts.cloud.run_c7_4c_confirmation import (
    reconstruct_source_full_plan,
    verify_frozen_parent,
)


EXPECTED_C75_SHORTLIST_SHA256 = (
    '86c0b3a1737525ea1e96e5749ed47e377073723a2f168dbdcf60b9a8db6debb6'
)

EXPECTED_C74C_SHA256 = (
    '6ff9a924ddee7f7c3097e0ef5c28387f2dfce6e8427f0b74523596d50a285870'
)

EXPECTED_SHORTLIST_LABELS = (
    'pressure+lns60',
    'aggressive+none',
    'aggressive+lns60',
    'aggressive+alns80',
    'stable+none',
    'stable+alns80',
)

EXPECTED_CONTESTANT_COUNT = 6
EXPECTED_HOLDOUT_COUNT = 24


def file_sha256(
    path: Path,
) -> str:
    digest = sha256()

    with path.open('rb') as stream:
        for chunk in iter(
            lambda: stream.read(
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

    if path.exists():
        existing = path.read_text(
            encoding='utf-8'
        )

        if existing != encoded:
            raise ValueError(
                'Existing C7.6 artifact differs'
            )

        return

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
        '--parent-round1',
        type=Path,
        required=True,
    )

    parser.add_argument(
        '--c75-shortlist',
        type=Path,
        required=True,
    )

    parser.add_argument(
        '--c74c-results',
        type=Path,
        required=True,
    )

    parser.add_argument(
        '--output-root',
        type=Path,
        required=True,
    )

    args = parser.parse_args()

    parent = args.parent_round1.resolve()
    shortlist_path = (
        args.c75_shortlist.resolve()
    )
    c74c_path = (
        args.c74c_results.resolve()
    )
    output_root = (
        args.output_root.resolve()
    )

    if (
        file_sha256(shortlist_path)
        != EXPECTED_C75_SHORTLIST_SHA256
    ):
        raise AssertionError(
            'Frozen C7.5 shortlist hash mismatch'
        )

    if (
        file_sha256(c74c_path)
        != EXPECTED_C74C_SHA256
    ):
        raise AssertionError(
            'Frozen C7.4c evidence hash mismatch'
        )

    shortlist = json.loads(
        shortlist_path.read_text(
            encoding='utf-8'
        )
    )

    if shortlist.get('stage') != 'C7.5':
        raise AssertionError(
            'Expected C7.5 shortlist artifact'
        )

    if (
        shortlist.get('method')
        != 'exact_pooled_C1_metric_witnesses'
    ):
        raise AssertionError(
            'Unexpected C7.5 shortlist method'
        )

    if (
        shortlist.get(
            'source_evidence_sha256'
        )
        != EXPECTED_C74C_SHA256
    ):
        raise AssertionError(
            'C7.5 source evidence changed'
        )

    if (
        shortlist.get(
            'shortlist_candidate_count'
        )
        != EXPECTED_CONTESTANT_COUNT
    ):
        raise AssertionError(
            'Expected six C7.5 shortlist candidates'
        )

    if (
        shortlist.get('holdout_accessed')
        is not False
        or shortlist.get(
            'scalar_ranking_used'
        )
        is not False
        or shortlist.get(
            'epsilon_used'
        )
        is not False
        or shortlist.get(
            'runtime_tiebreak_used'
        )
        is not False
    ):
        raise AssertionError(
            'C7.5 provenance policy changed'
        )

    shortlisted_ids = tuple(
        shortlist[
            'shortlisted_candidate_ids'
        ]
    )

    rows = {
        row['candidate_id']: row
        for row in shortlist['candidates']
    }

    labels = {
        candidate_id:
            rows[candidate_id]['label']
        for candidate_id
        in shortlisted_ids
    }

    actual_labels = tuple(
        labels[candidate_id]
        for candidate_id
        in shortlisted_ids
    )

    if actual_labels != EXPECTED_SHORTLIST_LABELS:
        raise AssertionError(
            'C7.5 shortlist identities/order changed'
        )

    witnesses = {
        candidate_id:
            tuple(
                rows[candidate_id][
                    'witness_metrics'
                ]
            )
        for candidate_id
        in shortlisted_ids
    }

    source_plan = (
        reconstruct_source_full_plan(
            output_root.with_name(
                output_root.name
                + '_PLANNING_SCRATCH'
            )
        )
    )

    verify_frozen_parent(
        source_plan,
        parent,
    )

    if (
        len(source_plan.holdout_scenario_ids)
        != EXPECTED_HOLDOUT_COUNT
    ):
        raise AssertionError(
            'Expected 24 reserved holdout scenarios'
        )

    field = freeze_c8_contestants(
        source_candidates=
            source_plan.candidates,
        shortlisted_candidate_ids=
            shortlisted_ids,
        labels=labels,
        witness_metrics=witnesses,
        holdout_scenario_ids=
            source_plan.holdout_scenario_ids,
    )

    artifact = c8_contestant_artifact(
        field,
        c75_shortlist_sha256=
            EXPECTED_C75_SHORTLIST_SHA256,
        c74c_evidence_sha256=
            EXPECTED_C74C_SHA256,
    )

    output_path = (
        output_root
        / 'c7_6_c8_contestants.json'
    )

    write_json(
        output_path,
        artifact,
    )

    print('=' * 78)
    print(
        'ARC C7.6 FREEZE C8 CONTESTANTS'
    )
    print('=' * 78)

    print(
        f'contestant_count='
        f'{len(field.contestants)}'
    )

    print(
        f'holdout_scenario_count='
        f'{len(field.holdout_scenario_ids)}'
    )

    print('holdout_accessed=False')
    print(
        'additional_development_selection=False'
    )
    print('scalar_ranking_used=False')

    print()

    for contestant in field.contestants:
        print(
            'CONTESTANT '
            f'{contestant.label} '
            f'{contestant.source_candidate_id} '
            'semantic='
            f'{contestant.semantic_fingerprint} '
            'witnesses='
            f'{",".join(contestant.witness_metrics)}'
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
