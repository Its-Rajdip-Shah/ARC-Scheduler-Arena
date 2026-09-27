from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
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

from arena.tuning import (
    C7_V1_SELECTION_POLICY,
    ConfirmationCandidateLink,
    RacingRoundSpec,
    combine_seed_tuning_results,
    decide_racing_round,
    load_tuning_results,
    relabel_confirmation_results,
    subset_tuning_results,
)
from arena.tuning.workload_analysis import (
    analyze_workload_responses,
    summarize_workload_responses,
)
from scripts.cloud.run_c7_4c_confirmation import (
    extract_archive,
    load_classification,
    read_c74b_final_state,
    reconstruct_historical_seed1701,
    reconstruct_source_full_plan,
    unique_dir,
    verify_frozen_parent,
)
from scripts.run_c7_5_shortlist import (
    EXPECTED_C74C_SHA256,
    read_json,
)


EXPECTED_C75_SHA256 = (
    '86c0b3a1737525ea1e96e5749ed47e377073723a2f168dbdcf60b9a8db6debb6'
)

EXPECTED_C76_SHA256 = (
    'a14fad452a3f0d0de243dbd039e74edb50c6f5f318b0c8136c0d728ab09d9783'
)

FINALIST_LABELS = (
    'pressure+lns60',
    'aggressive+none',
    'aggressive+lns60',
    'aggressive+alns80',
    'stable+none',
    'stable+alns80',
)


def sha256_file(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()

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
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(',', ':'),
            ensure_ascii=True,
            allow_nan=False,
        )
        + '\n',
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
        '--prior-round1-results',
        type=Path,
        required=True,
    )

    parser.add_argument(
        '--prior-round2-results',
        type=Path,
        required=True,
    )

    parser.add_argument(
        '--final-c74b-results',
        type=Path,
        required=True,
    )

    parser.add_argument(
        '--c74c-results',
        type=Path,
        required=True,
    )

    parser.add_argument(
        '--c75-shortlist',
        type=Path,
        required=True,
    )

    parser.add_argument(
        '--c76-contestants',
        type=Path,
        required=True,
    )

    parser.add_argument(
        '--feasibility-classification',
        type=Path,
        required=True,
    )

    parser.add_argument(
        '--output-root',
        type=Path,
        required=True,
    )

    args = parser.parse_args()

    c75 = args.c75_shortlist.resolve()
    c76 = args.c76_contestants.resolve()

    if (
        sha256_file(c75)
        != EXPECTED_C75_SHA256
    ):
        raise AssertionError(
            'Frozen C7.5 shortlist SHA changed'
        )

    if (
        sha256_file(c76)
        != EXPECTED_C76_SHA256
    ):
        raise AssertionError(
            'Frozen C7.6 contestant SHA changed'
        )

    shortlist = read_json(c75)
    contestants = read_json(c76)

    finalist_ids = tuple(
        shortlist[
            'shortlisted_candidate_ids'
        ]
    )

    rows = {
        row['candidate_id']: row
        for row in shortlist[
            'candidates'
        ]
    }

    labels = {
        candidate_id:
            rows[candidate_id]['label']
        for candidate_id in finalist_ids
    }

    if tuple(
        labels[candidate_id]
        for candidate_id
        in finalist_ids
    ) != FINALIST_LABELS:
        raise AssertionError(
            'Frozen finalist identities changed'
        )

    c76_ids = tuple(
        row[
            'source_candidate_id'
        ]
        for row in contestants[
            'contestants'
        ]
    )

    if c76_ids != finalist_ids:
        raise AssertionError(
            'C7.5/C7.6 finalist identity mismatch'
        )

    output_root = (
        args.output_root.resolve()
    )

    scratch = (
        output_root.with_name(
            output_root.name
            + '_SCRATCH'
        )
    )

    for path in (
        output_root,
        scratch,
    ):
        if path.exists():
            shutil.rmtree(path)

    scratch.mkdir(
        parents=True,
    )

    source_plan = (
        reconstruct_source_full_plan(
            scratch / 'source-plan'
        )
    )

    verify_frozen_parent(
        source_plan,
        args.parent_round1.resolve(),
    )

    proof = load_classification(
        args
        .feasibility_classification
        .resolve()
    )

    (
        c74b_survivors,
        feasible_ids,
        holdout_ids,
    ) = read_c74b_final_state(
        args
        .final_c74b_results
        .resolve(),
        proof,
    )

    historical = (
        reconstruct_historical_seed1701(
            survivors=
                c74b_survivors,
            feasible_ids=
                feasible_ids,
            prior_r1_archive=
                args
                .prior_round1_results
                .resolve(),
            prior_r2_archive=
                args
                .prior_round2_results
                .resolve(),
            final_archive=
                args
                .final_c74b_results
                .resolve(),
            scratch_root=
                scratch / 'historical',
        )
    )

    c74c_archive = (
        args.c74c_results.resolve()
    )

    if (
        sha256_file(c74c_archive)
        != EXPECTED_C74C_SHA256
    ):
        raise AssertionError(
            'Frozen C7.4c SHA changed'
        )

    extracted = (
        scratch / 'c74c'
    )

    extract_archive(
        c74c_archive,
        extracted,
    )

    fresh_root = unique_dir(
        extracted,
        '**/ARC_C7_4C_CONFIRMATION',
    )

    fresh_raw = load_tuning_results(
        fresh_root
    )

    source_map = read_json(
        fresh_root
        / 'source_candidate_map.json'
    )

    links = tuple(
        ConfirmationCandidateLink(
            source_candidate_id=
                row[
                    'source_candidate_id'
                ],
            confirmation_candidate_id=
                row[
                    'confirmation_candidate_id'
                ],
        )
        for row in source_map[
            'candidate_links'
        ]
    )

    fresh = (
        relabel_confirmation_results(
            fresh_raw,
            links,
        )
    )

    historical_6 = (
        subset_tuning_results(
            historical,
            candidate_ids=
                finalist_ids,
            scenario_ids=
                feasible_ids,
        )
    )

    fresh_6 = (
        subset_tuning_results(
            fresh,
            candidate_ids=
                finalist_ids,
            scenario_ids=
                feasible_ids,
        )
    )

    pooled = (
        combine_seed_tuning_results(
            historical_6,
            fresh_6,
            candidate_ids=
                finalist_ids,
        )
    )

    if (
        pooled.seeds
        != (1701, 1702, 1703)
    ):
        raise AssertionError(
            'Unexpected C9 development seed set'
        )

    if (
        pooled
        .holdout_scenario_ids
        != holdout_ids
    ):
        raise AssertionError(
            'Development evidence split changed'
        )

    decision = decide_racing_round(
        pooled,
        RacingRoundSpec(
            round_index=1,
            expected_candidate_ids=
                finalist_ids,
            target_survivor_count=
                len(finalist_ids),
            selection_policy=
                C7_V1_SELECTION_POLICY,
        ),
    )

    if (
        decision
        .survivor_candidate_ids
        != finalist_ids
    ):
        raise AssertionError(
            'Frozen six are no longer the '
            'development Pareto field'
        )

    active_metrics = tuple(
        metric.name
        for metric
        in decision
        .selection
        .active_metrics
    )

    workloads_path = (
        ROOT
        / 'arena'
        / 'benchmarks'
        / 'v1'
        / 'workloads.json'
    )

    workloads = json.loads(
        workloads_path.read_text(
            encoding='utf-8'
        )
    )

    features_by_scenario = {}
    metadata_by_scenario = {}

    for row in workloads:
        scenario_id = (
            row['metadata'][
                'scenario_id'
            ]
        )

        features_by_scenario[
            scenario_id
        ] = row['features']

        metadata_by_scenario[
            scenario_id
        ] = row['metadata']

    responses = (
        analyze_workload_responses(
            pooled,
            candidate_ids=
                finalist_ids,
            active_metrics=
                active_metrics,
        )
    )

    artifact = (
        summarize_workload_responses(
            responses,
            candidate_ids=
                finalist_ids,
            labels=labels,
            features_by_scenario=
                features_by_scenario,
            metadata_by_scenario=
                metadata_by_scenario,
            active_metrics=
                active_metrics,
        )
    )

    artifact.update({
        'source_stage': 'C7.6',
        'c75_shortlist_sha256':
            EXPECTED_C75_SHA256,
        'c76_contestants_sha256':
            EXPECTED_C76_SHA256,
        'c74c_development_evidence_sha256':
            EXPECTED_C74C_SHA256,
        'development_seeds': [
            1701,
            1702,
            1703,
        ],
        'development_trial_count':
            pooled.completed_trials,
        'reserved_holdout_scenario_count':
            len(holdout_ids),
        'reserved_holdout_scenario_ids':
            list(holdout_ids),
        'c8_evidence_consumed':
            False,
    })

    output_path = (
        output_root
        / 'c9_1_workload_response.json'
    )

    write_json(
        output_path,
        artifact,
    )

    print('=' * 78)
    print(
        'ARC C9.1 WORKLOAD-RESPONSE ANALYSIS'
    )
    print('=' * 78)

    print(
        f'candidate_count='
        f'{artifact["candidate_count"]}'
    )

    print(
        f'development_scenarios='
        f'{artifact["development_scenario_count"]}'
    )

    print(
        f'scorable_scenarios='
        f'{artifact["scorable_scenario_count"]}'
    )

    print(
        'common_mode_coverage_gaps='
        f'{artifact["common_mode_coverage_gap_count"]}'
    )

    print(
        f'active_metrics='
        f'{len(active_metrics)}'
    )

    print(
        'holdout_used_for_training=False'
    )

    print(
        'c8_evidence_consumed=False'
    )

    print(
        'scalar_candidate_score_used=False'
    )

    print()

    for row in artifact[
        'candidates'
    ]:
        print(
            'CANDIDATE '
            f'{row["label"]} '
            'pareto_scenarios='
            f'{row["pareto_scenario_count"]}/'
            f'{artifact["scorable_scenario_count"]} '
            'fraction='
            f'{row["pareto_scenario_fraction"]:.3f}'
        )

    consistency = artifact[
        'replicate_consistency'
    ]

    print()
    print(
        'replicate_pair_count='
        f'{consistency["paired_design_count"]}'
    )

    print(
        'mean_replicate_pareto_jaccard='
        f'{consistency["mean_pareto_jaccard"]}'
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
    raise SystemExit(
        main()
    )
