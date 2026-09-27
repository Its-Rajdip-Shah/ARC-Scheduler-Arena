from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / 'backend'

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BACKEND))

import os

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
from arena.tuning.shortlist import (
    build_metric_witness_shortlist,
    shortlist_artifact,
)
from scripts.cloud.run_c7_4c_confirmation import (
    EXPECTED_CLASSIFICATION_SHA256,
    EXPECTED_FINAL_C74B_SHA256,
    EXPECTED_PARENT_SHA256,
    EXPECTED_PRIOR_R1_SHA256,
    EXPECTED_PRIOR_R2_SHA256,
    extract_archive,
    load_classification,
    read_c74b_final_state,
    reconstruct_historical_seed1701,
    reconstruct_source_full_plan,
    require_sha,
    unique_dir,
    verify_frozen_parent,
)


EXPECTED_C74C_SHA256 = (
    '6ff9a924ddee7f7c3097e0ef5c28387'
    'f2dfce6e8427f0b74523596d50a285870'
)

EXPECTED_CONFIRMED_COUNT = 19
EXPECTED_SHORTLIST_COUNT = 6
EXPECTED_POOLED_TRIALS = 3021
EXPECTED_PAIRED_QUALITY_CELLS = 153
EXPECTED_COMMON_MODE_TIMEOUT_CELLS = (
    ('G016-R0', 1701),
    ('G016-R0', 1702),
    ('G016-R0', 1703),
    ('G016-R1', 1701),
    ('G016-R1', 1702),
    ('G016-R1', 1703),
)


def read_json(path: Path) -> dict:
    return json.loads(
        path.read_text(
            encoding='utf-8'
        )
    )


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


def candidate_label(
    candidate,
) -> str:
    constructor = (
        candidate
        .constructor
        .arm_id
        .split('_', 1)[0]
    )

    improver = (
        candidate
        .improver
        .arm_id
        .split('_', 1)[0]
    )

    if improver == 'none':
        return (
            f'{constructor}+none'
        )

    engine = (
        candidate.improver.engine
    )

    config = getattr(
        engine,
        'config',
        None,
    )

    max_evaluations = getattr(
        config,
        'max_evaluations',
        None,
    )

    if max_evaluations is None:
        return (
            f'{constructor}+{improver}'
        )

    return (
        f'{constructor}+'
        f'{improver}{max_evaluations}'
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

    parent = args.parent_round1.resolve()
    prior_r1 = (
        args
        .prior_round1_results
        .resolve()
    )
    prior_r2 = (
        args
        .prior_round2_results
        .resolve()
    )
    final_c74b = (
        args
        .final_c74b_results
        .resolve()
    )
    c74c_archive = (
        args.c74c_results.resolve()
    )
    classification_path = (
        args
        .feasibility_classification
        .resolve()
    )
    output_root = (
        args.output_root.resolve()
    )

    require_sha(
        parent,
        EXPECTED_PARENT_SHA256,
        'Frozen C7.4a Round-1',
    )

    require_sha(
        prior_r1,
        EXPECTED_PRIOR_R1_SHA256,
        'Frozen C7.4b Round-1',
    )

    require_sha(
        prior_r2,
        EXPECTED_PRIOR_R2_SHA256,
        'Frozen C7.4b Round-2',
    )

    require_sha(
        final_c74b,
        EXPECTED_FINAL_C74B_SHA256,
        'Frozen C7.4b final',
    )

    require_sha(
        classification_path,
        EXPECTED_CLASSIFICATION_SHA256,
        'Frozen feasibility classification',
    )

    require_sha(
        c74c_archive,
        EXPECTED_C74C_SHA256,
        'Frozen C7.4c confirmation',
    )

    if output_root.exists():
        shutil.rmtree(
            output_root
        )

    scratch = (
        output_root.with_name(
            output_root.name
            + '_SCRATCH'
        )
    )

    if scratch.exists():
        shutil.rmtree(
            scratch
        )

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
        parent,
    )

    proof = load_classification(
        classification_path
    )

    (
        c74b_survivors,
        feasible_ids,
        holdout_ids,
    ) = read_c74b_final_state(
        final_c74b,
        proof,
    )

    historical = (
        reconstruct_historical_seed1701(
            survivors=
                c74b_survivors,
            feasible_ids=
                feasible_ids,
            prior_r1_archive=
                prior_r1,
            prior_r2_archive=
                prior_r2,
            final_archive=
                final_c74b,
            scratch_root=
                scratch / 'historical',
        )
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
        for row
        in source_map[
            'candidate_links'
        ]
    )

    fresh = (
        relabel_confirmation_results(
            fresh_raw,
            links,
        )
    )

    report = read_json(
        fresh_root
        / 'confirmation_report.json'
    )

    if (
        report.get(
            'holdout_accessed'
        )
        is not False
    ):
        raise AssertionError(
            'C7.4c reports holdout access'
        )

    confirmed = tuple(
        report[
            'confirmed_candidate_ids'
        ]
    )

    if (
        len(confirmed)
        != EXPECTED_CONFIRMED_COUNT
        or len(set(confirmed))
        != EXPECTED_CONFIRMED_COUNT
    ):
        raise AssertionError(
            'Expected exactly 19 '
            'C7.4c confirmed candidates'
        )

    if (
        tuple(
            report[
                'fresh_confirmation'
            ][
                'pareto_candidate_ids'
            ]
        )
        != confirmed
    ):
        raise AssertionError(
            'Fresh C7.4c Pareto field '
            'differs from confirmed field'
        )

    if (
        tuple(
            report[
                'pooled_development'
            ][
                'pareto_candidate_ids'
            ]
        )
        != confirmed
    ):
        raise AssertionError(
            'Pooled C7.4c Pareto field '
            'differs from confirmed field'
        )

    historical_19 = (
        subset_tuning_results(
            historical,
            candidate_ids=confirmed,
            scenario_ids=feasible_ids,
        )
    )

    fresh_19 = (
        subset_tuning_results(
            fresh,
            candidate_ids=confirmed,
            scenario_ids=feasible_ids,
        )
    )

    pooled = (
        combine_seed_tuning_results(
            historical_19,
            fresh_19,
            candidate_ids=confirmed,
        )
    )

    if (
        pooled.completed_trials
        != EXPECTED_POOLED_TRIALS
    ):
        raise AssertionError(
            'Expected 3021 pooled '
            'confirmed-candidate trials'
        )

    if pooled.seeds != (
        1701,
        1702,
        1703,
    ):
        raise AssertionError(
            'Unexpected pooled seed set'
        )

    if (
        pooled
        .holdout_scenario_ids
        != holdout_ids
    ):
        raise AssertionError(
            'Holdout identity changed'
        )

    decision = decide_racing_round(
        pooled,
        RacingRoundSpec(
            round_index=1,
            expected_candidate_ids=
                confirmed,
            target_survivor_count=
                len(confirmed),
            selection_policy=
                C7_V1_SELECTION_POLICY,
        ),
    )

    if (
        decision
        .survivor_candidate_ids
        != confirmed
    ):
        raise AssertionError(
            'Confirmed 19 are no longer '
            'the pooled Pareto field'
        )

    if (
        decision
        .common_mode_timeout_cells
        != EXPECTED_COMMON_MODE_TIMEOUT_CELLS
    ):
        raise AssertionError(
            'Common-mode G016 coverage '
            'gap changed'
        )

    if (
        len(
            decision
            .selection
            .paired_quality_cells
        )
        != EXPECTED_PAIRED_QUALITY_CELLS
    ):
        raise AssertionError(
            'Expected 153 paired '
            'pooled quality cells'
        )

    shortlist = (
        build_metric_witness_shortlist(
            pooled,
            decision.selection,
            expected_candidate_ids=
                confirmed,
        )
    )

    if (
        len(
            shortlist
            .shortlisted_candidate_ids
        )
        != EXPECTED_SHORTLIST_COUNT
    ):
        raise AssertionError(
            'Frozen pooled evidence no '
            'longer yields six metric witnesses'
        )

    source_candidates = {
        candidate.candidate_id:
            candidate
        for candidate
        in source_plan.candidates
    }

    labels = {
        candidate_id:
            candidate_label(
                source_candidates[
                    candidate_id
                ]
            )
        for candidate_id
        in confirmed
    }

    artifact = shortlist_artifact(
        shortlist,
        candidate_labels=labels,
    )

    artifact.update({
        'source_stage': 'C7.4c',
        'source_evidence_sha256':
            EXPECTED_C74C_SHA256,
        'historical_seeds': [1701],
        'fresh_confirmation_seeds': [
            1702,
            1703,
        ],
        'pooled_seeds': [
            1701,
            1702,
            1703,
        ],
        'pooled_trial_count':
            pooled.completed_trials,
        'feasible_development_scenario_count':
            len(feasible_ids),
        'certified_infeasible_scenario_count':
            41,
        'holdout_scenario_count':
            len(holdout_ids),
        'holdout_accessed': False,
        'common_mode_timeout_cells': [
            [scenario_id, seed]
            for scenario_id, seed
            in decision
            .common_mode_timeout_cells
        ],
    })

    output_root.mkdir(
        parents=True,
    )

    write_json(
        output_root
        / 'c7_5_shortlist.json',
        artifact,
    )

    print('=' * 78)
    print(
        'ARC C7.5 DEVELOPMENT SHORTLIST'
    )
    print('=' * 78)

    print(
        f'confirmed_source_candidates='
        f'{len(confirmed)}'
    )

    print(
        f'pooled_trials='
        f'{pooled.completed_trials}'
    )

    print(
        f'pooled_seeds={pooled.seeds}'
    )

    print(
        f'paired_quality_cells='
        f'{len(shortlist.paired_quality_cells)}'
    )

    print(
        f'active_metrics='
        f'{len(shortlist.metric_witnesses)}'
    )

    print(
        'scalar_ranking_used=False'
    )

    print(
        'epsilon_used=False'
    )

    print(
        'holdout_accessed=False'
    )

    print()

    for witness in (
        shortlist.metric_witnesses
    ):
        names = ', '.join(
            labels[candidate_id]
            for candidate_id
            in witness.candidate_ids
        )

        print(
            'METRIC_WITNESS '
            f'{witness.metric_name} '
            f'best={witness.best_value:.12g} '
            f'candidates={names}'
        )

    print()
    print(
        f'shortlist_count='
        f'{len(shortlist.shortlisted_candidate_ids)}'
    )

    for candidate_id in (
        shortlist
        .shortlisted_candidate_ids
    ):
        metrics = [
            witness.metric_name
            for witness
            in shortlist.metric_witnesses
            if candidate_id
            in witness.candidate_ids
        ]

        print(
            'SHORTLIST '
            f'{labels[candidate_id]} '
            f'{candidate_id} '
            f'witnesses={",".join(metrics)}'
        )

    print()
    print(
        f'ARTIFACT='
        f'{output_root / "c7_5_shortlist.json"}'
    )

    print(
        'SCHEDULER_TRIALS_EXECUTED=0'
    )

    return 0


if __name__ == '__main__':
    raise SystemExit(
        main()
    )
