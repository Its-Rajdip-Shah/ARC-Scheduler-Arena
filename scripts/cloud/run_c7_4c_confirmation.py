from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import replace
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BACKEND))

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "arc_backend.settings",
)

import django
django.setup()

from arena.tuning import (
    C7_V1_SELECTION_POLICY,
    ConfirmationCandidateLink,
    RacingRoundSpec,
    TuningAxis,
    build_confirmation_subset_plan,
    combine_seed_tuning_results,
    decide_racing_round,
    execute_tuning_study_parallel,
    load_tuning_results,
    merge_cumulative_tuning_results,
    plan_tuning_study,
    relabel_confirmation_results,
    subset_tuning_results,
    write_tuning_plan,
)
from arena.tuning.design import (
    build_c7_calibration_spec,
)


EXPECTED_PARENT_SHA256 = (
    "dfc0b017f5f2936708d9454758a9bd95017eb085566f0d829f5505b34a1f59fe"
)

EXPECTED_PRIOR_R1_SHA256 = (
    "f85246002b832c579282105788067445ce6c6fd4ee0f56cee586a9799123716b"
)

EXPECTED_PRIOR_R2_SHA256 = (
    "697bb559e0dfc67fdfc9f9a022ffe637811a3f127aaf79b0b62892d2ec73a5e2"
)

EXPECTED_FINAL_C74B_SHA256 = (
    "d47355342411569e00815cbfbcbfeb33420975af5035153de457d3641be2b676"
)

EXPECTED_CLASSIFICATION_SHA256 = (
    "0d340fefff8b28bbbc704066c138b60d0c4456640b5546315a5d759d7d2a439d"
)

EXPECTED_MANIFEST_SHA256 = (
    "34264d1617a5c29e43c58f2383680fdfb2824df2ef999e2c4855930ed354c4b3"
)

EXPECTED_C74B_CAMPAIGN_FINGERPRINT = (
    "2cc3df1cfb0b54700129ed5f4fec18fc054cc03af8af5608ac7fbb5fb1e85651"
)

FRESH_SEEDS = (
    1702,
    1703,
)

HISTORICAL_SEEDS = (
    1701,
)

TRIAL_WALL_SECONDS = 45.0
EXPECTED_SURVIVORS = 21
EXPECTED_FEASIBLE_SCENARIOS = 53
EXPECTED_INFEASIBLE_SCENARIOS = 41
EXPECTED_HOLDOUT_SCENARIOS = 24


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
            f"{label} SHA mismatch\n"
            f"expected={expected}\n"
            f"actual={actual}"
        )


def read_json_member(
    archive: Path,
    suffix: str,
) -> dict:
    with tarfile.open(
        archive,
        "r:gz",
    ) as tf:
        members = [
            member
            for member in tf.getmembers()
            if member.name.endswith(suffix)
        ]

        if len(members) != 1:
            raise AssertionError(
                f"Expected one {suffix}, "
                f"got {len(members)}"
            )

        stream = tf.extractfile(
            members[0]
        )

        if stream is None:
            raise AssertionError(
                f"Could not read {suffix}"
            )

        return json.loads(
            stream.read().decode(
                "utf-8"
            )
        )


def extract_archive(
    archive: Path,
    target: Path,
) -> None:
    if target.exists():
        shutil.rmtree(target)

    target.mkdir(
        parents=True,
    )

    with tarfile.open(
        archive,
        "r:gz",
    ) as tf:
        tf.extractall(target)


def unique_dir(
    root: Path,
    pattern: str,
) -> Path:
    matches = list(
        root.glob(pattern)
    )

    if len(matches) != 1:
        raise AssertionError(
            f"Expected one {pattern}, "
            f"got {len(matches)}"
        )

    return matches[0]


def reconstruct_source_full_plan(
    output_root: Path,
):
    base_spec = build_c7_calibration_spec(
        output_root
    )

    axes = {
        "none": (),
        "hc": (
            TuningAxis(
                "max_evaluations",
                (80, 160),
            ),
        ),
        "vnd": (
            TuningAxis(
                "max_evaluations",
                (80, 160),
            ),
        ),
        "vns": (
            TuningAxis(
                "max_evaluations",
                (80, 160),
            ),
        ),
        "tabu": (
            TuningAxis(
                "tabu_tenure",
                (3, 7),
            ),
        ),
        "sa": (
            TuningAxis(
                "max_evaluations",
                (80, 160),
            ),
        ),
        "lns": (
            TuningAxis(
                "max_evaluations",
                (30, 60),
            ),
        ),
        "alns": (
            TuningAxis(
                "max_evaluations",
                (40, 80),
            ),
        ),
    }

    improvers = tuple(
        replace(
            sweep,
            axes=axes[sweep.arm_id],
        )
        for sweep in base_spec.improvers
    )

    spec = replace(
        base_spec,
        improvers=improvers,
        seeds=HISTORICAL_SEEDS,
        trial_wall_seconds=
            TRIAL_WALL_SECONDS,
        max_candidates=60,
        max_trials=5640,
    )

    return plan_tuning_study(
        spec
    )


def verify_frozen_parent(
    source_plan,
    parent_archive: Path,
) -> None:
    require_sha(
        parent_archive,
        EXPECTED_PARENT_SHA256,
        "Frozen C7.4a Round-1",
    )

    frozen = read_json_member(
        parent_archive,
        "study_plan.json",
    )

    frozen_ids = tuple(
        row["candidate_id"]
        for row in frozen["candidates"]
    )

    generated_ids = tuple(
        candidate.candidate_id
        for candidate
        in source_plan.candidates
    )

    if frozen_ids != generated_ids:
        raise AssertionError(
            "Frozen 60-candidate identity changed"
        )

    if (
        tuple(
            frozen[
                "development_scenario_ids"
            ]
        )
        != source_plan
        .development_scenario_ids
    ):
        raise AssertionError(
            "Frozen development partition changed"
        )

    if (
        tuple(
            frozen[
                "holdout_scenario_ids"
            ]
        )
        != source_plan
        .holdout_scenario_ids
    ):
        raise AssertionError(
            "Frozen holdout partition changed"
        )

    if (
        source_plan
        .benchmark_manifest_sha256
        != EXPECTED_MANIFEST_SHA256
    ):
        raise AssertionError(
            "Benchmark manifest changed"
        )


def build_fresh_full_plan(
    source_plan,
    output_root: Path,
):
    expected = (
        len(source_plan.candidates)
        * len(
            source_plan
            .development_scenario_ids
        )
        * len(FRESH_SEEDS)
    )

    spec = replace(
        source_plan.spec,
        seeds=FRESH_SEEDS,
        output_root=output_root,
        trial_wall_seconds=
            TRIAL_WALL_SECONDS,
        max_candidates=
            len(source_plan.candidates),
        max_trials=expected,
    )

    return plan_tuning_study(
        spec
    )


def load_classification(
    path: Path,
) -> dict[str, str]:
    require_sha(
        path,
        EXPECTED_CLASSIFICATION_SHA256,
        "Hard-feasibility classification",
    )

    payload = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    proof = {
        row["scenario_id"]:
            row["proof_status"]
        for row in payload["rows"]
    }

    counts = Counter(
        proof.values()
    )

    expected = {
        "PROVEN_FEASIBLE":
            EXPECTED_FEASIBLE_SCENARIOS,
        "PROVEN_INFEASIBLE":
            EXPECTED_INFEASIBLE_SCENARIOS,
    }

    if dict(counts) != expected:
        raise AssertionError(
            f"Unexpected feasibility counts: "
            f"{dict(counts)}"
        )

    return proof


def read_c74b_final_state(
    final_archive: Path,
    proof: dict[str, str],
):
    require_sha(
        final_archive,
        EXPECTED_FINAL_C74B_SHA256,
        "Frozen C7.4b final archive",
    )

    campaign = read_json_member(
        final_archive,
        "/campaign.json",
    )

    final = read_json_member(
        final_archive,
        "/final_survivors.json",
    )

    if (
        campaign.get("campaign_id")
        != "c7.4b-feasible-racing-v1"
    ):
        raise AssertionError(
            "C7.4b campaign identity changed"
        )

    if (
        final[
            "campaign_fingerprint"
        ]
        != EXPECTED_C74B_CAMPAIGN_FINGERPRINT
    ):
        raise AssertionError(
            "Final survivor campaign "
            "fingerprint changed"
        )

    if final.get(
        "holdout_accessed"
    ) is not False:
        raise AssertionError(
            "C7.4b reports holdout access"
        )

    survivors = tuple(
        final[
            "final_survivor_candidate_ids"
        ]
    )

    if (
        len(survivors)
        != EXPECTED_SURVIVORS
        or len(set(survivors))
        != EXPECTED_SURVIVORS
    ):
        raise AssertionError(
            "Expected exactly 21 frozen "
            "C7.4b survivors"
        )

    feasible_ids = tuple(
        campaign[
            "development_scenario_ids"
        ]
    )

    if (
        len(feasible_ids)
        != EXPECTED_FEASIBLE_SCENARIOS
    ):
        raise AssertionError(
            "C7.4b feasible campaign no longer "
            "contains 53 scenarios"
        )

    if any(
        proof.get(scenario_id)
        != "PROVEN_FEASIBLE"
        for scenario_id in feasible_ids
    ):
        raise AssertionError(
            "C7.4b feasible campaign contains "
            "a non-feasible scenario"
        )

    if (
        len(
            campaign[
                "holdout_scenario_ids"
            ]
        )
        != EXPECTED_HOLDOUT_SCENARIOS
    ):
        raise AssertionError(
            "Expected 24 untouched holdout "
            "scenarios"
        )

    return (
        survivors,
        feasible_ids,
        tuple(
            campaign[
                "holdout_scenario_ids"
            ]
        ),
    )


def reconstruct_historical_seed1701(
    *,
    survivors,
    feasible_ids,
    prior_r1_archive,
    prior_r2_archive,
    final_archive,
    scratch_root,
):
    require_sha(
        prior_r1_archive,
        EXPECTED_PRIOR_R1_SHA256,
        "Prior C7.4b Round-1 evidence",
    )

    require_sha(
        prior_r2_archive,
        EXPECTED_PRIOR_R2_SHA256,
        "Prior C7.4b Round-2 evidence",
    )

    r1_root = (
        scratch_root / "r1"
    )

    r2_root = (
        scratch_root / "r2"
    )

    final_root = (
        scratch_root / "final"
    )

    extract_archive(
        prior_r1_archive,
        r1_root,
    )

    extract_archive(
        prior_r2_archive,
        r2_root,
    )

    extract_archive(
        final_archive,
        final_root,
    )

    r1 = load_tuning_results(
        unique_dir(
            r1_root,
            "**/ARC_C7_4B_RACING_V1/"
            "round_01_execution",
        )
    )

    r2 = load_tuning_results(
        unique_dir(
            r2_root,
            "**/ARC_C7_4B_FEASIBLE_RACING_V1/"
            "round_02_execution",
        )
    )

    r3 = load_tuning_results(
        unique_dir(
            final_root,
            "**/ARC_C7_4B_R3_RACING_V1/"
            "round_03_execution",
        )
    )

    r4 = load_tuning_results(
        unique_dir(
            final_root,
            "**/ARC_C7_4B_R3_RACING_V1/"
            "round_04_execution",
        )
    )

    parts = (
        subset_tuning_results(
            r1,
            candidate_ids=survivors,
            scenario_ids=
                feasible_ids[:8],
        ),
        subset_tuning_results(
            r2,
            candidate_ids=survivors,
            scenario_ids=
                feasible_ids[8:24],
        ),
        subset_tuning_results(
            r3,
            candidate_ids=survivors,
            scenario_ids=
                feasible_ids[24:40],
        ),
        subset_tuning_results(
            r4,
            candidate_ids=survivors,
            scenario_ids=
                feasible_ids[40:53],
        ),
    )

    cumulative = None
    cumulative_ids = ()

    for part in parts:
        cumulative_ids = (
            cumulative_ids
            + part.development_scenario_ids
        )

        cumulative = (
            merge_cumulative_tuning_results(
                cumulative,
                part,
                incoming_candidate_ids=
                    survivors,
                cumulative_scenario_ids=
                    cumulative_ids,
            )
        )

    if cumulative is None:
        raise AssertionError(
            "Historical reconstruction failed"
        )

    expected_trials = (
        EXPECTED_SURVIVORS
        * EXPECTED_FEASIBLE_SCENARIOS
    )

    if (
        cumulative.expected_trials
        != expected_trials
        or cumulative.completed_trials
        != expected_trials
        or cumulative.seeds
        != HISTORICAL_SEEDS
    ):
        raise AssertionError(
            "Historical seed-1701 matrix "
            "is incomplete"
        )

    if (
        cumulative.development_scenario_ids
        != feasible_ids
    ):
        raise AssertionError(
            "Historical scenario order changed"
        )

    return cumulative


def links_artifact(
    links: tuple[
        ConfirmationCandidateLink,
        ...
    ],
) -> dict:
    return {
        "schema_version": 1,
        "source_stage": "C7.4b",
        "confirmation_stage": "C7.4c",
        "fresh_seeds": list(
            FRESH_SEEDS
        ),
        "candidate_links": [
            {
                "source_candidate_id":
                    link.source_candidate_id,
                "confirmation_candidate_id":
                    link.confirmation_candidate_id,
            }
            for link in links
        ],
    }


def write_json(
    path: Path,
    payload: dict,
) -> None:
    encoded = (
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
        + "\n"
    )

    if path.exists():
        actual = path.read_text(
            encoding="utf-8"
        )

        if actual != encoded:
            raise ValueError(
                f"Existing artifact differs: "
                f"{path}"
            )

        return

    path.write_text(
        encoded,
        encoding="utf-8",
    )


def decision_summary(
    decision,
) -> dict:
    return {
        "candidate_count":
            len(
                decision.spec
                .expected_candidate_ids
            ),
        "eligible_candidate_count":
            len(
                decision.selection
                .eligible_candidate_ids
            ),
        "pareto_candidate_count":
            len(
                decision.survivor_candidate_ids
            ),
        "pareto_candidate_ids":
            list(
                decision
                .survivor_candidate_ids
            ),
        "eliminated_candidates":
            dict(
                decision
                .eliminated_candidates
            ),
        "common_mode_timeout_cells": [
            [
                scenario_id,
                seed,
            ]
            for scenario_id, seed
            in decision
            .common_mode_timeout_cells
        ],
        "paired_quality_cell_count":
            len(
                decision.selection
                .paired_quality_cells
            ),
        "unresolved_cells": [
            [
                scenario_id,
                seed,
            ]
            for scenario_id, seed
            in decision.selection
            .unresolved_cells
        ],
        "active_metrics": [
            metric.name
            for metric
            in decision.selection
            .active_metrics
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--parent-round1",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--prior-round1-results",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--prior-round2-results",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--final-c74b-results",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--feasibility-classification",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--output-root",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--workers",
        type=int,
        default=50,
    )

    parser.add_argument(
        "--environment-id",
        default="c7-4c-confirmation",
    )

    parser.add_argument(
        "--plan-only",
        action="store_true",
    )

    parser.add_argument(
        "--resume",
        action="store_true",
    )

    args = parser.parse_args()

    if args.workers <= 0:
        raise ValueError(
            "workers must be positive"
        )

    parent = (
        args.parent_round1.resolve()
    )

    prior_r1 = (
        args.prior_round1_results.resolve()
    )

    prior_r2 = (
        args.prior_round2_results.resolve()
    )

    final_c74b = (
        args.final_c74b_results.resolve()
    )

    classification_path = (
        args
        .feasibility_classification
        .resolve()
    )

    output_root = (
        args.output_root.resolve()
    )

    planning_root = (
        output_root.with_name(
            output_root.name
            + "_PLANNING_SCRATCH"
        )
    )

    historical_root = (
        output_root.with_name(
            output_root.name
            + "_HISTORICAL_SCRATCH"
        )
    )

    if planning_root.exists():
        shutil.rmtree(
            planning_root
        )

    planning_root.mkdir(
        parents=True
    )

    source_plan = (
        reconstruct_source_full_plan(
            planning_root
            / "source-full"
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
        survivors,
        feasible_ids,
        holdout_ids,
    ) = read_c74b_final_state(
        final_c74b,
        proof,
    )

    source_ids = {
        candidate.candidate_id
        for candidate
        in source_plan.candidates
    }

    if any(
        candidate_id not in source_ids
        for candidate_id in survivors
    ):
        raise AssertionError(
            "Frozen survivor is not in "
            "the frozen 60-candidate field"
        )

    historical = (
        reconstruct_historical_seed1701(
            survivors=survivors,
            feasible_ids=feasible_ids,
            prior_r1_archive=prior_r1,
            prior_r2_archive=prior_r2,
            final_archive=final_c74b,
            scratch_root=
                historical_root,
        )
    )

    fresh_full = (
        build_fresh_full_plan(
            source_plan,
            planning_root
            / "fresh-full",
        )
    )

    confirmation = (
        build_confirmation_subset_plan(
            source_plan,
            fresh_full,
            source_candidate_ids=
                survivors,
            scenario_ids=
                feasible_ids,
            output_root=
                output_root,
            trial_wall_seconds=
                TRIAL_WALL_SECONDS,
        )
    )

    fresh_plan = (
        confirmation.tuning_plan
    )

    expected_fresh_trials = (
        EXPECTED_SURVIVORS
        * EXPECTED_FEASIBLE_SCENARIOS
        * len(FRESH_SEEDS)
    )

    if (
        fresh_plan.expected_trials
        != expected_fresh_trials
    ):
        raise AssertionError(
            "Fresh confirmation trial "
            "cardinality changed"
        )

    if (
        fresh_plan.holdout_scenario_ids
        != holdout_ids
    ):
        raise AssertionError(
            "Holdout identity changed"
        )

    if (
        set(fresh_plan.development_scenario_ids)
        & set(fresh_plan.holdout_scenario_ids)
    ):
        raise AssertionError(
            "Fresh confirmation leaks holdout"
        )

    pooled_expected = (
        historical.expected_trials
        + expected_fresh_trials
    )

    print("=" * 78)
    print(
        "ARC C7.4C FULL DEVELOPMENT "
        "CONFIRMATION"
    )
    print("=" * 78)

    print(
        f"source_candidates="
        f"{len(survivors)}"
    )

    print(
        f"feasible_development_scenarios="
        f"{len(feasible_ids)}"
    )

    print(
        f"certified_infeasible_scenarios="
        f"{EXPECTED_INFEASIBLE_SCENARIOS}"
    )

    print(
        f"holdout_scenarios="
        f"{len(holdout_ids)}"
    )

    print("holdout_accessed=False")

    print(
        f"historical_seeds="
        f"{HISTORICAL_SEEDS}"
    )

    print(
        f"fresh_confirmation_seeds="
        f"{FRESH_SEEDS}"
    )

    print(
        f"trial_wall_seconds="
        f"{TRIAL_WALL_SECONDS}"
    )

    print(
        f"historical_trials_reused="
        f"{historical.expected_trials}"
    )

    print(
        f"fresh_trials_planned="
        f"{fresh_plan.expected_trials}"
    )

    print(
        f"pooled_trials_after_completion="
        f"{pooled_expected}"
    )

    print(
        "known_G016_retested=True"
    )

    print(
        "fresh_confirmation_selection="
        "paired_C1_strict_Pareto_no_scalar"
    )

    if args.plan_only:
        print()
        print(
            "C7_4C_PLAN_ONLY=PASS"
        )
        print(
            "HISTORICAL_RECONSTRUCTION=PASS"
        )
        print(
            "FRESH_IDENTITY_MAPPING=PASS"
        )
        print(
            "HOLDOUT_ISOLATION=PASS"
        )
        print(
            "SCHEDULER_TRIALS_EXECUTED=0"
        )
        return 0

    if output_root.exists():
        if not args.resume:
            raise FileExistsError(
                output_root
            )
    else:
        write_tuning_plan(
            fresh_plan
        )

        write_json(
            output_root
            / "source_candidate_map.json",
            links_artifact(
                confirmation.candidate_links
            ),
        )

        write_json(
            output_root
            / "c7_4c_provenance.json",
            {
                "schema_version": 1,
                "stage": "C7.4c",
                "source_stage": "C7.4b",
                "parent_round1_sha256":
                    EXPECTED_PARENT_SHA256,
                "prior_round1_results_sha256":
                    EXPECTED_PRIOR_R1_SHA256,
                "prior_round2_results_sha256":
                    EXPECTED_PRIOR_R2_SHA256,
                "final_c74b_results_sha256":
                    EXPECTED_FINAL_C74B_SHA256,
                "feasibility_classification_sha256":
                    EXPECTED_CLASSIFICATION_SHA256,
                "c74b_campaign_fingerprint":
                    EXPECTED_C74B_CAMPAIGN_FINGERPRINT,
                "historical_seeds":
                    list(HISTORICAL_SEEDS),
                "fresh_confirmation_seeds":
                    list(FRESH_SEEDS),
                "source_candidate_count":
                    len(survivors),
                "feasible_development_scenarios":
                    list(feasible_ids),
                "certified_infeasible_count":
                    EXPECTED_INFEASIBLE_SCENARIOS,
                "holdout_scenario_ids":
                    list(holdout_ids),
                "holdout_accessed": False,
                "historical_trials_reused":
                    historical.expected_trials,
                "fresh_trials_planned":
                    fresh_plan.expected_trials,
                "trial_wall_seconds":
                    TRIAL_WALL_SECONDS,
            },
        )

    execution = (
        execute_tuning_study_parallel(
            fresh_plan,
            max_workers=args.workers,
            execution_environment_id=
                args.environment_id,
            resume=args.resume,
            progress_interval_seconds=
                10.0,
        )
    )

    if (
        execution.completed_trials
        != fresh_plan.expected_trials
    ):
        raise RuntimeError(
            "Fresh confirmation execution "
            "is incomplete"
        )

    fresh_raw = load_tuning_results(
        output_root
    )

    fresh = (
        relabel_confirmation_results(
            fresh_raw,
            confirmation.candidate_links,
        )
    )

    fresh_spec = RacingRoundSpec(
        round_index=1,
        expected_candidate_ids=
            survivors,
        target_survivor_count=
            len(survivors),
        selection_policy=
            C7_V1_SELECTION_POLICY,
    )

    fresh_decision = (
        decide_racing_round(
            fresh,
            fresh_spec,
        )
    )

    if (
        fresh_decision
        .selection
        .unresolved_cells
    ):
        raise RuntimeError(
            "Fresh confirmation contains "
            "unresolved cells"
        )

    pooled = combine_seed_tuning_results(
        historical,
        fresh,
        candidate_ids=survivors,
    )

    if (
        pooled.expected_trials
        != pooled_expected
    ):
        raise RuntimeError(
            "Pooled confirmation matrix "
            "cardinality mismatch"
        )

    pooled_spec = RacingRoundSpec(
        round_index=1,
        expected_candidate_ids=
            survivors,
        target_survivor_count=
            len(survivors),
        selection_policy=
            C7_V1_SELECTION_POLICY,
    )

    pooled_decision = (
        decide_racing_round(
            pooled,
            pooled_spec,
        )
    )

    if (
        pooled_decision
        .selection
        .unresolved_cells
    ):
        raise RuntimeError(
            "Pooled confirmation contains "
            "unresolved cells"
        )

    report = {
        "schema_version": 1,
        "stage": "C7.4c",
        "status": "complete",
        "holdout_accessed": False,
        "source_candidate_count":
            len(survivors),
        "source_candidate_ids":
            list(survivors),
        "historical_seed":
            HISTORICAL_SEEDS[0],
        "fresh_confirmation_seeds":
            list(FRESH_SEEDS),
        "feasible_scenario_count":
            len(feasible_ids),
        "certified_infeasible_count":
            EXPECTED_INFEASIBLE_SCENARIOS,
        "historical_trials_reused":
            historical.expected_trials,
        "fresh_trials_completed":
            fresh.completed_trials,
        "pooled_trials":
            pooled.completed_trials,
        "fresh_confirmation":
            decision_summary(
                fresh_decision
            ),
        "pooled_development":
            decision_summary(
                pooled_decision
            ),
        "confirmed_candidate_ids":
            list(
                fresh_decision
                .survivor_candidate_ids
            ),
        "confirmed_candidate_count":
            len(
                fresh_decision
                .survivor_candidate_ids
            ),
    }

    write_json(
        output_root
        / "confirmation_report.json",
        report,
    )

    print()
    print("=" * 78)
    print(
        "C7.4C CONFIRMATION COMPLETE"
    )
    print("=" * 78)

    print(
        f"fresh_trials="
        f"{fresh.completed_trials}"
    )

    print(
        f"fresh_common_mode_timeout_cells="
        f"{len(fresh_decision.common_mode_timeout_cells)}"
    )

    for (
        scenario_id,
        seed,
    ) in (
        fresh_decision
        .common_mode_timeout_cells
    ):
        print(
            "FRESH_COMMON_MODE_TIMEOUT="
            f"{scenario_id} seed={seed}"
        )

    print(
        f"fresh_eligible_candidates="
        f"{len(fresh_decision.selection.eligible_candidate_ids)}"
    )

    print(
        f"fresh_confirmed_candidates="
        f"{len(fresh_decision.survivor_candidate_ids)}"
    )

    print(
        f"fresh_eliminated="
        f"{len(fresh_decision.eliminated_candidates)}"
    )

    print(
        f"fresh_paired_quality_cells="
        f"{len(fresh_decision.selection.paired_quality_cells)}"
    )

    print(
        f"pooled_trials="
        f"{pooled.completed_trials}"
    )

    print(
        f"pooled_pareto_candidates="
        f"{len(pooled_decision.survivor_candidate_ids)}"
    )

    print(
        f"RESULT_ROOT={output_root}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
