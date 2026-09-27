from __future__ import annotations

import argparse
from dataclasses import replace
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
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
    RacingRoundSpec,
    decide_racing_round,
    plan_tuning_study,
)
from arena.tuning.faceoff import (
    C8_FACE_OFF_SEEDS,
    C8_TRIAL_WALL_SECONDS,
    build_c8_faceoff_plan,
    c8_metric_means,
    execute_c8_faceoff,
    load_c8_faceoff_results,
    write_c8_faceoff_plan,
)
from scripts.cloud.run_c7_4c_confirmation import (
    reconstruct_source_full_plan,
    verify_frozen_parent,
)


EXPECTED_ROUND1_SHA256 = (
    'dfc0b017f5f2936708d9454758a9bd95017eb085566f0d829f5505b34a1f59fe'
)

EXPECTED_C76_SHA256 = (
    'a14fad452a3f0d0de243dbd039e74edb50c6f5f318b0c8136c0d728ab09d9783'
)

EXPECTED_CONTESTANTS = 6
EXPECTED_HOLDOUT = 24
EXPECTED_TRIALS = 432


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


def require_sha(
    path: Path,
    expected: str,
    label: str,
) -> None:
    if not path.is_file():
        raise FileNotFoundError(path)

    actual = file_sha256(path)

    if actual != expected:
        raise AssertionError(
            f'{label} SHA mismatch\n'
            f'expected={expected}\n'
            f'actual={actual}'
        )


def canonical_json(value) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(',', ':'),
        ensure_ascii=True,
        allow_nan=False,
    )


def write_json(
    path: Path,
    payload: dict,
) -> None:
    encoded = (
        canonical_json(payload)
        + '\n'
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
        '--c76-contestants',
        type=Path,
        required=True,
    )

    parser.add_argument(
        '--output-root',
        type=Path,
        required=True,
    )

    parser.add_argument(
        '--workers',
        type=int,
        default=50,
    )

    parser.add_argument(
        '--environment-id',
        default='c8-holdout-faceoff',
    )

    parser.add_argument(
        '--plan-only',
        action='store_true',
    )

    parser.add_argument(
        '--resume',
        action='store_true',
    )

    args = parser.parse_args()

    if args.workers <= 0:
        raise ValueError(
            'workers must be positive'
        )

    parent = (
        args.parent_round1.resolve()
    )

    c76_path = (
        args.c76_contestants.resolve()
    )

    output_root = (
        args.output_root.resolve()
    )

    require_sha(
        parent,
        EXPECTED_ROUND1_SHA256,
        'Frozen C7 Round-1',
    )

    require_sha(
        c76_path,
        EXPECTED_C76_SHA256,
        'Frozen C7.6 contestant field',
    )

    frozen = json.loads(
        c76_path.read_text(
            encoding='utf-8'
        )
    )

    source_scratch = (
        output_root.with_name(
            output_root.name
            + '_SOURCE_SCRATCH'
        )
    )

    fresh_scratch = (
        output_root.with_name(
            output_root.name
            + '_FRESH_SCRATCH'
        )
    )

    for scratch in (
        source_scratch,
        fresh_scratch,
    ):
        if scratch.exists():
            shutil.rmtree(
                scratch
            )

    source_plan = (
        reconstruct_source_full_plan(
            source_scratch
        )
    )

    verify_frozen_parent(
        source_plan,
        parent,
    )

    fresh_expected = (
        len(source_plan.candidates)
        * len(
            source_plan
            .development_scenario_ids
        )
        * len(C8_FACE_OFF_SEEDS)
    )

    fresh_spec = replace(
        source_plan.spec,
        seeds=C8_FACE_OFF_SEEDS,
        output_root=fresh_scratch,
        trial_wall_seconds=
            C8_TRIAL_WALL_SECONDS,
        max_candidates=
            len(source_plan.candidates),
        max_trials=fresh_expected,
    )

    fresh_plan = plan_tuning_study(
        fresh_spec
    )

    plan = build_c8_faceoff_plan(
        source_plan,
        fresh_plan,
        frozen,
        output_root=output_root,
    )

    if (
        len(plan.candidate_links)
        != EXPECTED_CONTESTANTS
        or len(
            plan.holdout_scenario_ids
        )
        != EXPECTED_HOLDOUT
        or plan.expected_trials
        != EXPECTED_TRIALS
    ):
        raise AssertionError(
            'Frozen C8 cardinality changed'
        )

    if (
        set(plan.holdout_scenario_ids)
        & set(
            plan.development_scenario_ids
        )
    ):
        raise AssertionError(
            'C8 holdout/development overlap'
        )

    print('=' * 78)
    print(
        'ARC C8 UNTOUCHED HOLDOUT FACE-OFF'
    )
    print('=' * 78)

    print(
        f'contestant_count='
        f'{len(plan.candidate_links)}'
    )

    print(
        f'holdout_scenario_count='
        f'{len(plan.holdout_scenario_ids)}'
    )

    print(
        f'fresh_seeds={plan.seeds}'
    )

    print(
        f'trial_wall_seconds='
        f'{plan.trial_wall_seconds}'
    )

    print(
        f'execution_groups='
        f'{len(plan.run_configs)}'
    )

    print(
        f'expected_trials='
        f'{plan.expected_trials}'
    )

    print(
        'selection='
        'paired_C1_strict_Pareto_no_scalar'
    )

    print(
        'winner_declared_by_protocol=False'
    )

    print(
        'posthoc_budget_adaptation_allowed=False'
    )

    for link in plan.candidate_links:
        print(
            'CONTESTANT '
            f'{link.label} '
            f'{link.source_candidate_id} '
            f'execution={link.execution_candidate_id} '
            f'semantic={link.semantic_fingerprint}'
        )

    if args.plan_only:
        print()
        print(
            'C8_PLAN_ONLY=PASS'
        )
        print(
            'C7_6_PROVENANCE=PASS'
        )
        print(
            'FRESH_SEED_MAPPING=PASS'
        )
        print(
            'HOLDOUT_IDENTITY=PASS'
        )
        print(
            'SCHEDULER_TRIALS_EXECUTED=0'
        )
        return 0

    if output_root.exists():
        if not args.resume:
            raise FileExistsError(
                output_root
            )
    else:
        write_c8_faceoff_plan(
            plan
        )

    (
        run_results,
        completed,
        timed_out,
    ) = execute_c8_faceoff(
        plan,
        max_workers=args.workers,
        execution_environment_id=
            args.environment_id,
        resume=args.resume,
    )

    results = (
        load_c8_faceoff_results(
            plan
        )
    )

    decision = decide_racing_round(
        results,
        RacingRoundSpec(
            round_index=1,
            expected_candidate_ids=
                tuple(
                    link
                    .source_candidate_id
                    for link
                    in plan
                    .candidate_links
                ),
            target_survivor_count=
                len(
                    plan
                    .candidate_links
                ),
            selection_policy=
                C7_V1_SELECTION_POLICY,
        ),
    )

    if (
        decision
        .selection
        .unresolved_cells
    ):
        raise RuntimeError(
            'C8 contains unresolved no-success '
            'holdout cells. Protocol forbids '
            'post-hoc budget adaptation.'
        )

    labels = {
        link.source_candidate_id:
            link.label
        for link in plan.candidate_links
    }

    metric_means = c8_metric_means(
        results,
        decision.selection,
    )

    report = {
        'schema_version': 1,
        'stage': 'C8',
        'status': 'complete',
        'protocol':
            'untouched_holdout_faceoff_v1',
        'c76_contestant_sha256':
            EXPECTED_C76_SHA256,
        'holdout_accessed': True,
        'holdout_execution_completed':
            True,
        'winner_declared': False,
        'scalar_ranking_used': False,
        'posthoc_budget_adaptation_used':
            False,
        'contestant_count':
            len(plan.candidate_links),
        'holdout_scenario_count':
            len(
                plan
                .holdout_scenario_ids
            ),
        'seeds':
            list(plan.seeds),
        'trial_wall_seconds':
            plan.trial_wall_seconds,
        'expected_trials':
            plan.expected_trials,
        'completed_trials':
            completed,
        'timed_out_trials':
            timed_out,
        'structurally_unscorable_cells': [
            list(cell)
            for cell in (
                decision
                .selection
                .structurally_unscorable_cells
            )
        ],
        'common_mode_timeout_cells': [
            list(cell)
            for cell in (
                decision
                .common_mode_timeout_cells
            )
        ],
        'unresolved_cells': [
            list(cell)
            for cell in (
                decision
                .selection
                .unresolved_cells
            )
        ],
        'eligible_candidate_ids':
            list(
                decision
                .selection
                .eligible_candidate_ids
            ),
        'excluded_candidates':
            dict(
                decision
                .selection
                .excluded_candidates
            ),
        'pareto_candidate_ids':
            list(
                decision
                .survivor_candidate_ids
            ),
        'paired_quality_cells': [
            list(cell)
            for cell in (
                decision
                .selection
                .paired_quality_cells
            )
        ],
        'active_metrics': [
            metric.name
            for metric in (
                decision
                .selection
                .active_metrics
            )
        ],
        'inactive_metrics': [
            metric.name
            for metric in (
                decision
                .selection
                .inactive_metrics
            )
        ],
        'metric_observation_counts':
            dict(
                decision
                .selection
                .metric_observation_counts
            ),
        'candidate_metric_means':
            metric_means,
        'candidates': [
            {
                'source_candidate_id':
                    link
                    .source_candidate_id,
                'label':
                    link.label,
                'semantic_fingerprint':
                    link
                    .semantic_fingerprint,
                'eligible':
                    link
                    .source_candidate_id
                    in decision
                    .selection
                    .eligible_candidate_ids,
                'pareto':
                    link
                    .source_candidate_id
                    in decision
                    .survivor_candidate_ids,
                'exclusion_reason':
                    decision
                    .selection
                    .excluded_candidates
                    .get(
                        link
                        .source_candidate_id
                    ),
                'metric_means':
                    metric_means.get(
                        link
                        .source_candidate_id,
                        {},
                    ),
            }
            for link in plan.candidate_links
        ],
    }

    report_path = (
        output_root
        / 'c8_faceoff_report.json'
    )

    write_json(
        report_path,
        report,
    )

    print()
    print('=' * 78)
    print(
        'C8 HOLDOUT FACE-OFF COMPLETE'
    )
    print('=' * 78)

    print(
        f'completed_trials={completed}'
    )

    print(
        f'timed_out_trials={timed_out}'
    )

    print(
        f'structural_cells='
        f'{len(decision.selection.structurally_unscorable_cells)}'
    )

    print(
        f'common_mode_timeout_cells='
        f'{len(decision.common_mode_timeout_cells)}'
    )

    for scenario_id, seed in (
        decision
        .common_mode_timeout_cells
    ):
        print(
            'COMMON_MODE_TIMEOUT '
            f'{scenario_id} '
            f'seed={seed}'
        )

    print(
        f'unresolved_cells='
        f'{len(decision.selection.unresolved_cells)}'
    )

    print(
        f'eligible_candidates='
        f'{len(decision.selection.eligible_candidate_ids)}'
    )

    print(
        f'excluded_candidates='
        f'{len(decision.selection.excluded_candidates)}'
    )

    for candidate_id, reason in (
        decision
        .selection
        .excluded_candidates
        .items()
    ):
        print(
            'EXCLUDED '
            f'{labels[candidate_id]} '
            f'reason={reason}'
        )

    print(
        f'pareto_candidates='
        f'{len(decision.survivor_candidate_ids)}'
    )

    for candidate_id in (
        decision
        .survivor_candidate_ids
    ):
        print(
            'PARETO '
            f'{labels[candidate_id]} '
            f'{candidate_id}'
        )

    print(
        f'paired_quality_cells='
        f'{len(decision.selection.paired_quality_cells)}'
    )

    print(
        'winner_declared=False'
    )

    print(
        f'REPORT={report_path}'
    )

    return 0


if __name__ == '__main__':
    raise SystemExit(
        main()
    )
