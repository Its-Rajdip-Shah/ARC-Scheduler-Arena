from __future__ import annotations

import argparse
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
    RacingCampaignSpec,
    RacingFidelityStage,
    TuningAxis,
    build_incremental_tuning_plan,
    build_racing_round_plan,
    campaign_fingerprint,
    decide_racing_round,
    execute_tuning_study_parallel,
    load_tuning_results,
    merge_cumulative_tuning_results,
    plan_tuning_study,
    racing_campaign_artifact,
    racing_decision_artifact,
    racing_round_plan_artifact,
    subset_tuning_results,
    write_racing_campaign,
    write_racing_decision,
    write_tuning_plan,
)
from arena.tuning.design import build_c7_calibration_spec


EXPECTED_PARENT_SHA256 = (
    "dfc0b017f5f2936708d9454758a9bd95017eb085566f0d829f5505b34a1f59fe"
)

EXPECTED_PRIOR_RACE_SHA256 = (
    "f85246002b832c579282105788067445ce6c6fd4ee0f56cee586a9799123716b"
)

EXPECTED_PRIOR_ROUND2_SHA256 = (
    "697bb559e0dfc67fdfc9f9a022ffe637811a3f127aaf79b0b62892d2ec73a5e2"
)

EXPECTED_CLASSIFICATION_SHA256 = (
    "0d340fefff8b28bbbc704066c138b60d0c4456640b5546315a5d759d7d2a439d"
)

EXPECTED_MANIFEST_SHA256 = (
    "34264d1617a5c29e43c58f2383680fdfb2824df2ef999e2c4855930ed354c4b3"
)

CAMPAIGN_ID = "c7.4b-feasible-racing-v1"
WALL_SECONDS = 45.0


def file_sha256(path: Path) -> str:
    digest = sha256()

    with path.open("rb") as stream:
        for chunk in iter(
            lambda: stream.read(1024 * 1024),
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


def frozen_study_artifact(
    archive: Path,
) -> dict:
    require_sha(
        archive,
        EXPECTED_PARENT_SHA256,
        "Frozen Round-1 archive",
    )

    with tarfile.open(archive, "r:gz") as tf:
        members = [
            member
            for member in tf.getmembers()
            if member.name.endswith("/study_plan.json")
            or member.name == "study_plan.json"
        ]

        if len(members) != 1:
            raise AssertionError(
                "Expected exactly one frozen study_plan.json"
            )

        stream = tf.extractfile(members[0])

        if stream is None:
            raise AssertionError(
                "Could not read frozen study_plan.json"
            )

        return json.loads(
            stream.read().decode("utf-8")
        )


def reconstruct_frozen_round1(
    scratch_root: Path,
):
    base_spec = build_c7_calibration_spec(
        scratch_root
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
        seeds=(1701,),
        trial_wall_seconds=WALL_SECONDS,
        max_candidates=60,
        max_trials=5640,
    )

    return plan_tuning_study(spec)


def verify_frozen_identity(
    full_plan,
    frozen: dict,
) -> None:
    generated_ids = tuple(
        candidate.candidate_id
        for candidate in full_plan.candidates
    )

    frozen_ids = tuple(
        candidate["candidate_id"]
        for candidate in frozen["candidates"]
    )

    if generated_ids != frozen_ids:
        raise AssertionError(
            "Frozen candidate identities changed"
        )

    if tuple(
        full_plan.development_scenario_ids
    ) != tuple(
        frozen["development_scenario_ids"]
    ):
        raise AssertionError(
            "Frozen development partition changed"
        )

    if tuple(
        full_plan.holdout_scenario_ids
    ) != tuple(
        frozen["holdout_scenario_ids"]
    ):
        raise AssertionError(
            "Frozen holdout partition changed"
        )

    if (
        full_plan.benchmark_manifest_sha256
        != EXPECTED_MANIFEST_SHA256
    ):
        raise AssertionError(
            "Unexpected benchmark manifest"
        )


def paired_racing_order(
    development_ids: tuple[str, ...],
) -> tuple[str, ...]:
    groups = {}

    for scenario_id in development_ids:
        design_id, replicate = scenario_id.rsplit(
            "-R",
            1,
        )

        if replicate not in ("0", "1"):
            raise AssertionError(
                f"Unexpected scenario ID: {scenario_id}"
            )

        groups.setdefault(
            design_id,
            {},
        )[replicate] = scenario_id

    if len(groups) != 47:
        raise AssertionError(
            f"Expected 47 development designs, got {len(groups)}"
        )

    if any(
        set(replicates) != {"0", "1"}
        for replicates in groups.values()
    ):
        raise AssertionError(
            "Every development design must have R0/R1"
        )

    ordered_designs = sorted(
        groups,
        key=lambda design_id: (
            sha256(
                (
                    "c7.4b-racing-v1"
                    + ":"
                    + design_id
                ).encode("utf-8")
            ).digest(),
            design_id,
        ),
    )

    result = tuple(
        groups[design_id][replicate]
        for design_id in ordered_designs
        for replicate in ("0", "1")
    )

    if set(result) != set(development_ids):
        raise AssertionError(
            "Deterministic racing order changed development set"
        )

    return result


def load_classification(
    path: Path,
) -> dict[str, str]:
    require_sha(
        path,
        EXPECTED_CLASSIFICATION_SHA256,
        "Hard-feasibility classification",
    )

    payload = json.loads(
        path.read_text(encoding="utf-8")
    )

    proof = {
        row["scenario_id"]: row["proof_status"]
        for row in payload["rows"]
    }

    if len(proof) != 94:
        raise AssertionError(
            f"Expected 94 classified scenarios, got {len(proof)}"
        )

    counts = {}

    for status in proof.values():
        counts[status] = counts.get(status, 0) + 1

    expected = {
        "PROVEN_FEASIBLE": 53,
        "PROVEN_INFEASIBLE": 41,
    }

    if counts != expected:
        raise AssertionError(
            f"Unexpected feasibility proof counts: {counts}"
        )

    return proof


def build_campaign(
    full_plan,
    proof: dict[str, str],
):
    full_order = paired_racing_order(
        full_plan.development_scenario_ids
    )

    feasible_order = tuple(
        scenario_id
        for scenario_id in full_order
        if proof[scenario_id] == "PROVEN_FEASIBLE"
    )

    infeasible_order = tuple(
        scenario_id
        for scenario_id in full_order
        if proof[scenario_id] == "PROVEN_INFEASIBLE"
    )

    if len(feasible_order) != 53:
        raise AssertionError(
            "Expected 53 proven-feasible scenarios"
        )

    if len(infeasible_order) != 41:
        raise AssertionError(
            "Expected 41 proven-infeasible scenarios"
        )

    campaign = RacingCampaignSpec(
        campaign_id=CAMPAIGN_ID,
        benchmark_manifest_sha256=
            full_plan.benchmark_manifest_sha256,
        development_scenario_ids=
            feasible_order,
        holdout_scenario_ids=
            full_plan.holdout_scenario_ids,
        seeds=full_plan.spec.seeds,
        initial_candidate_ids=tuple(
            candidate.candidate_id
            for candidate in full_plan.candidates
        ),
        stages=(
            RacingFidelityStage(
                round_index=1,
                scenario_count=8,
                target_survivor_count=60,
            ),
            RacingFidelityStage(
                round_index=2,
                scenario_count=24,
                target_survivor_count=30,
            ),
            RacingFidelityStage(
                round_index=3,
                scenario_count=40,
                target_survivor_count=15,
            ),
            RacingFidelityStage(
                round_index=4,
                scenario_count=53,
                target_survivor_count=8,
            ),
        ),
        selection_policy=
            C7_V1_SELECTION_POLICY,
    )

    return campaign, infeasible_order


def extract_prior_round1(
    archive: Path,
    scratch_root: Path,
):
    require_sha(
        archive,
        EXPECTED_PRIOR_RACE_SHA256,
        "Prior C7.4b result archive",
    )

    if scratch_root.exists():
        shutil.rmtree(scratch_root)

    scratch_root.mkdir(
        parents=True,
    )

    with tarfile.open(archive, "r:gz") as tf:
        tf.extractall(scratch_root)

    roots = list(
        scratch_root.glob(
            "**/ARC_C7_4B_RACING_V1/round_01_execution"
        )
    )

    if len(roots) != 1:
        raise AssertionError(
            f"Expected one prior Round-1 execution root, got {len(roots)}"
        )

    prior = load_tuning_results(
        roots[0]
    )

    if prior.expected_trials != 1440:
        raise AssertionError(
            "Prior Round-1 evidence is not 1440 cells"
        )

    if prior.completed_trials != 1440:
        raise AssertionError(
            "Prior Round-1 evidence is incomplete"
        )

    if len(
        prior.development_scenario_ids
    ) != 24:
        raise AssertionError(
            "Prior Round-1 evidence does not contain 24 scenarios"
        )

    if len(
        prior.candidate_summaries
    ) != 60:
        raise AssertionError(
            "Prior Round-1 evidence does not contain 60 candidates"
        )

    return prior


def reusable_round1_evidence(
    prior,
    campaign,
    proof: dict[str, str],
):
    prior_feasible = tuple(
        scenario_id
        for scenario_id in prior.development_scenario_ids
        if proof[scenario_id] == "PROVEN_FEASIBLE"
    )

    expected = (
        campaign.development_scenario_ids[:8]
    )

    if prior_feasible != expected:
        raise AssertionError(
            "Existing feasible Round-1 evidence is not "
            "the feasible campaign prefix"
        )

    candidate_ids = tuple(
        summary.candidate_id
        for summary in prior.candidate_summaries
    )

    if candidate_ids != (
        campaign.initial_candidate_ids
    ):
        raise AssertionError(
            "Prior Round-1 candidate identity/order changed"
        )

    reused = subset_tuning_results(
        prior,
        candidate_ids=candidate_ids,
        scenario_ids=expected,
    )

    if reused.expected_trials != 480:
        raise AssertionError(
            f"Expected 480 reusable cells, got {reused.expected_trials}"
        )

    if any(
        observation.status != "ok"
        for observation in reused.trial_observations
    ):
        raise AssertionError(
            "Reusable feasible evidence contains a non-ok observation"
        )

    return reused


def extract_prior_round2(
    archive: Path,
    scratch_root: Path,
):
    require_sha(
        archive,
        EXPECTED_PRIOR_ROUND2_SHA256,
        "Prior C7.4b Round-2 result archive",
    )

    if scratch_root.exists():
        shutil.rmtree(scratch_root)

    scratch_root.mkdir(
        parents=True,
    )

    with tarfile.open(archive, "r:gz") as tf:
        tf.extractall(scratch_root)

    roots = list(
        scratch_root.glob(
            "**/ARC_C7_4B_FEASIBLE_RACING_V1/round_02_execution"
        )
    )

    if len(roots) != 1:
        raise AssertionError(
            f"Expected one prior Round-2 execution root, got {len(roots)}"
        )

    incremental = load_tuning_results(
        roots[0]
    )

    if incremental.expected_trials != 960:
        raise AssertionError(
            "Prior Round-2 evidence is not 960 incremental cells"
        )

    if incremental.completed_trials != 960:
        raise AssertionError(
            "Prior Round-2 evidence is incomplete"
        )

    if len(
        incremental.development_scenario_ids
    ) != 16:
        raise AssertionError(
            "Prior Round-2 evidence does not contain 16 new scenarios"
        )

    if len(
        incremental.candidate_summaries
    ) != 60:
        raise AssertionError(
            "Prior Round-2 evidence does not contain 60 candidates"
        )

    return incremental


def reconstruct_round2_state(
    *,
    reused_round1,
    round2_incremental,
    campaign,
):
    incoming = campaign.initial_candidate_ids

    round1_plan = build_racing_round_plan(
        campaign,
        1,
        incoming,
    )

    round1_decision = decide_racing_round(
        reused_round1,
        round1_plan.decision_spec,
    )

    if (
        round1_decision.survivor_candidate_ids
        != incoming
    ):
        raise AssertionError(
            "Imported Round 1 unexpectedly eliminated candidates"
        )

    round2_plan = build_racing_round_plan(
        campaign,
        2,
        incoming,
    )

    if (
        round2_incremental.development_scenario_ids
        != round2_plan.incremental_scenario_ids
    ):
        raise AssertionError(
            "Imported Round-2 scenario suffix changed"
        )

    if tuple(
        summary.candidate_id
        for summary
        in round2_incremental.candidate_summaries
    ) != incoming:
        raise AssertionError(
            "Imported Round-2 candidate identity/order changed"
        )

    cumulative = merge_cumulative_tuning_results(
        reused_round1,
        round2_incremental,
        incoming_candidate_ids=incoming,
        cumulative_scenario_ids=
            round2_plan.scenario_ids,
    )

    if cumulative.expected_trials != 1440:
        raise AssertionError(
            f"Expected 1440 imported cumulative cells, "
            f"got {cumulative.expected_trials}"
        )

    if cumulative.completed_trials != 1440:
        raise AssertionError(
            "Imported cumulative Round-2 evidence is incomplete"
        )

    round2_decision = decide_racing_round(
        cumulative,
        round2_plan.decision_spec,
    )

    expected_common_mode = (
        ("G016-R0", 1701),
        ("G016-R1", 1701),
    )

    if (
        round2_decision.common_mode_timeout_cells
        != expected_common_mode
    ):
        raise AssertionError(
            "Round-2 common-mode timeout classification changed: "
            f"{round2_decision.common_mode_timeout_cells}"
        )

    if (
        round2_decision.selection.unresolved_cells
    ):
        raise AssertionError(
            "Round-2 replay contains unresolved cells"
        )

    if len(
        round2_decision.selection.eligible_candidate_ids
    ) != 52:
        raise AssertionError(
            "Expected exactly 52 Round-2 eligible candidates"
        )

    if len(
        round2_decision.survivor_candidate_ids
    ) != 51:
        raise AssertionError(
            "Expected exactly 51 Round-2 survivors"
        )

    if len(
        round2_decision.eliminated_candidates
    ) != 9:
        raise AssertionError(
            "Expected exactly 9 Round-2 eliminations"
        )

    return (
        round1_plan,
        round1_decision,
        round2_plan,
        round2_decision,
        cumulative,
    )


def canonical_json(payload: dict) -> str:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def verify_or_write_json(
    path: Path,
    payload: dict,
) -> None:
    expected = canonical_json(payload) + "\n"

    if path.exists():
        actual = path.read_text(
            encoding="utf-8"
        )

        if actual != expected:
            raise ValueError(
                f"Existing artifact differs: {path}"
            )

        return

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        expected,
        encoding="utf-8",
    )


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
        "--feasibility-classification",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--prior-round2-results",
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
        default="c7-4b-feasible-racing-v1",
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

    parent = args.parent_round1.resolve()
    prior_archive = (
        args.prior_round1_results.resolve()
    )
    classification_path = (
        args.feasibility_classification.resolve()
    )
    prior_round2_archive = (
        args.prior_round2_results.resolve()
    )
    output_root = args.output_root.resolve()

    frozen = frozen_study_artifact(
        parent
    )

    scratch_root = output_root.with_name(
        output_root.name
        + "_PLANNING_SCRATCH"
    )

    full_plan = reconstruct_frozen_round1(
        scratch_root
    )

    verify_frozen_identity(
        full_plan,
        frozen,
    )

    proof = load_classification(
        classification_path
    )

    campaign, proven_infeasible = (
        build_campaign(
            full_plan,
            proof,
        )
    )

    prior = extract_prior_round1(
        prior_archive,
        output_root.with_name(
            output_root.name
            + "_PRIOR_ROUND1_SCRATCH"
        ),
    )

    reused_round1 = reusable_round1_evidence(
        prior,
        campaign,
        proof,
    )

    round2_incremental = extract_prior_round2(
        prior_round2_archive,
        output_root.with_name(
            output_root.name
            + "_PRIOR_ROUND2_SCRATCH"
        ),
    )

    (
        imported_round1_plan,
        imported_round1_decision,
        imported_round2_plan,
        imported_round2_decision,
        imported_cumulative,
    ) = reconstruct_round2_state(
        reused_round1=reused_round1,
        round2_incremental=round2_incremental,
        campaign=campaign,
    )

    campaign_sha = campaign_fingerprint(
        campaign
    )

    print("=" * 78)
    print("ARC C7.4B FEASIBLE-ONLY RACING")
    print("=" * 78)

    print(
        f"campaign_id={campaign.campaign_id}"
    )
    print(
        f"campaign_fingerprint={campaign_sha}"
    )
    print(
        f"parent_round1_sha256={file_sha256(parent)}"
    )
    print(
        f"prior_round1_results_sha256="
        f"{file_sha256(prior_archive)}"
    )
    print(
        f"classification_sha256="
        f"{file_sha256(classification_path)}"
    )
    print(
        f"prior_round2_results_sha256="
        f"{file_sha256(prior_round2_archive)}"
    )
    print(
        f"benchmark_manifest_sha256="
        f"{campaign.benchmark_manifest_sha256}"
    )
    print(
        f"candidates="
        f"{len(campaign.initial_candidate_ids)}"
    )
    print(
        f"proven_feasible_development="
        f"{len(campaign.development_scenario_ids)}"
    )
    print(
        f"proven_infeasible_development="
        f"{len(proven_infeasible)}"
    )
    print(
        f"holdout_scenarios="
        f"{len(campaign.holdout_scenario_ids)}"
    )
    print("holdout_accessed=False")
    print(
        f"reused_round1_quality_cells="
        f"{reused_round1.expected_trials}"
    )
    print(
        f"reused_round1_scenarios="
        f"{len(reused_round1.development_scenario_ids)}"
    )
    print(
        f"imported_round2_incremental_cells="
        f"{round2_incremental.completed_trials}"
    )
    print(
        f"imported_cumulative_cells="
        f"{imported_cumulative.completed_trials}"
    )
    print(
        f"round2_common_mode_timeout_cells="
        f"{len(imported_round2_decision.common_mode_timeout_cells)}"
    )
    print(
        f"round2_eligible_candidates="
        f"{len(imported_round2_decision.selection.eligible_candidate_ids)}"
    )
    print(
        f"round2_survivors="
        f"{len(imported_round2_decision.survivor_candidate_ids)}"
    )
    print(
        f"round2_eliminated="
        f"{len(imported_round2_decision.eliminated_candidates)}"
    )
    print()

    round3_incoming = (
        imported_round2_decision.survivor_candidate_ids
    )

    round3_plan = build_racing_round_plan(
        campaign,
        3,
        round3_incoming,
    )

    round3_new = (
        round3_plan.incremental_expected_trials
    )

    nominal_round4_incoming = min(
        len(round3_incoming),
        campaign.stages[2].target_survivor_count,
    )

    nominal_round4_ids = (
        round3_incoming[
            :nominal_round4_incoming
        ]
    )

    nominal_round4_plan = build_racing_round_plan(
        campaign,
        4,
        nominal_round4_ids,
    )

    nominal_remaining = (
        round3_new
        + nominal_round4_plan.incremental_expected_trials
    )

    worst_remaining = (
        len(round3_incoming)
        * (
            len(campaign.development_scenario_ids)
            - len(imported_round2_plan.scenario_ids)
        )
        * len(campaign.seeds)
    )

    print(
        f"round=3 "
        f"cumulative_feasible="
        f"{len(round3_plan.scenario_ids)} "
        f"new_feasible="
        f"{len(round3_plan.incremental_scenario_ids)} "
        f"incoming_actual="
        f"{len(round3_incoming)} "
        f"target={round3_plan.target_survivor_count} "
        f"new_trials={round3_new}"
    )

    print(
        f"round=4 "
        f"cumulative_feasible=53 "
        f"new_feasible=13 "
        f"incoming_nominal="
        f"{nominal_round4_incoming} "
        f"target={campaign.stages[3].target_survivor_count} "
        f"nominal_new_trials="
        f"{nominal_round4_plan.incremental_expected_trials}"
    )

    print()
    print(
        f"nominal_new_trials_after_round2="
        f"{nominal_remaining}"
    )
    print(
        f"worst_case_new_trials_after_round2="
        f"{worst_remaining}"
    )
    print(
        "selection="
        "paired_C1_strict_Pareto_no_scalar"
    )

    if args.plan_only:
        print()
        print("PLAN_ONLY=PASS")
        print("ROUND1_REUSE_VALIDATION=PASS")
        print("ROUND2_REPLAY_VALIDATION=PASS")
        print("ROUND3_START_VALIDATION=PASS")
        print("SCHEDULER_TRIALS_EXECUTED=0")
        return 0

    if output_root.exists() and not args.resume:
        raise FileExistsError(
            output_root
        )

    if not output_root.exists():
        output_root.mkdir(
            parents=True
        )

        write_racing_campaign(
            campaign,
            output_root / "campaign.json",
        )
    else:
        verify_or_write_json(
            output_root / "campaign.json",
            racing_campaign_artifact(
                campaign
            ),
        )

    provenance = {
        "schema_version": 1,
        "stage": "C7.4b",
        "campaign_id": campaign.campaign_id,
        "campaign_fingerprint": campaign_sha,
        "parent_round1_sha256":
            EXPECTED_PARENT_SHA256,
        "prior_round1_results_sha256":
            EXPECTED_PRIOR_RACE_SHA256,
        "prior_round2_results_sha256":
            EXPECTED_PRIOR_ROUND2_SHA256,
        "feasibility_classification_sha256":
            EXPECTED_CLASSIFICATION_SHA256,
        "reused_quality_cells":
            reused_round1.expected_trials,
        "imported_round2_incremental_cells":
            round2_incremental.completed_trials,
        "imported_cumulative_cells_through_round2":
            imported_cumulative.completed_trials,
        "round2_common_mode_timeout_cells": [
            [scenario_id, seed]
            for scenario_id, seed
            in imported_round2_decision.common_mode_timeout_cells
        ],
        "round2_survivor_candidate_ids":
            list(
                imported_round2_decision.survivor_candidate_ids
            ),
        "reused_scenario_ids":
            list(
                reused_round1.development_scenario_ids
            ),
        "proven_infeasible_scenario_ids":
            list(proven_infeasible),
        "holdout_accessed": False,
    }

    verify_or_write_json(
        output_root
        / "reuse_provenance.json",
        provenance,
    )

    verify_or_write_json(
        output_root / "round_01_plan.json",
        racing_round_plan_artifact(
            imported_round1_plan
        ),
    )

    if (
        output_root
        / "round_01_decision.json"
    ).exists():
        verify_or_write_json(
            output_root / "round_01_decision.json",
            racing_decision_artifact(
                imported_round1_decision
            ),
        )
    else:
        write_racing_decision(
            imported_round1_decision,
            output_root / "round_01_decision.json",
        )

    verify_or_write_json(
        output_root / "round_02_plan.json",
        racing_round_plan_artifact(
            imported_round2_plan
        ),
    )

    if (
        output_root
        / "round_02_decision.json"
    ).exists():
        verify_or_write_json(
            output_root / "round_02_decision.json",
            racing_decision_artifact(
                imported_round2_decision
            ),
        )
    else:
        write_racing_decision(
            imported_round2_decision,
            output_root / "round_02_decision.json",
        )

    imported_evidence = {
        "schema_version": 1,
        "round_1": {
            "source_archive_sha256":
                EXPECTED_PRIOR_RACE_SHA256,
            "reused_cells":
                reused_round1.completed_trials,
            "scenario_ids":
                list(
                    reused_round1.development_scenario_ids
                ),
        },
        "round_2": {
            "source_archive_sha256":
                EXPECTED_PRIOR_ROUND2_SHA256,
            "incremental_cells":
                round2_incremental.completed_trials,
            "cumulative_cells":
                imported_cumulative.completed_trials,
            "common_mode_timeout_cells": [
                [scenario_id, seed]
                for scenario_id, seed
                in imported_round2_decision.common_mode_timeout_cells
            ],
            "survivor_candidate_ids":
                list(
                    imported_round2_decision.survivor_candidate_ids
                ),
        },
    }

    verify_or_write_json(
        output_root
        / "imported_rounds_01_02.json",
        imported_evidence,
    )

    incoming = (
        imported_round2_decision.survivor_candidate_ids
    )

    cumulative = imported_cumulative

    for stage in campaign.stages[2:]:
        round_index = stage.round_index

        round_plan = build_racing_round_plan(
            campaign,
            round_index,
            incoming,
        )

        plan_path = (
            output_root
            / f"round_{round_index:02d}_plan.json"
        )

        verify_or_write_json(
            plan_path,
            racing_round_plan_artifact(
                round_plan
            ),
        )

        print()
        print("=" * 78)
        print(
            f"C7.4B ROUND {round_index}"
        )
        print("=" * 78)
        print(
            f"incoming={len(incoming)}"
        )
        print(
            f"cumulative_feasible="
            f"{len(round_plan.scenario_ids)}"
        )
        print(
            f"new_feasible="
            f"{len(round_plan.incremental_scenario_ids)}"
        )
        print(
            f"new_trials="
            f"{round_plan.incremental_expected_trials}"
        )
        print(
            f"target_survivors="
            f"{round_plan.target_survivor_count}"
        )

        round_root = (
            output_root
            / f"round_{round_index:02d}_execution"
        )

        executable = (
            build_incremental_tuning_plan(
                full_plan,
                round_plan,
                round_root,
            )
        )

        registration = (
            round_root
            / "study_plan.json"
        )

        if not registration.exists():
            if round_root.exists():
                raise ValueError(
                    "Round directory exists without study_plan.json"
                )

            write_tuning_plan(
                executable
            )

        execution = (
            execute_tuning_study_parallel(
                executable,
                max_workers=args.workers,
                execution_environment_id=(
                    args.environment_id
                    + f"-round{round_index}"
                ),
                resume=args.resume,
                progress_interval_seconds=10.0,
            )
        )

        if (
            execution.completed_trials
            != executable.expected_trials
        ):
            raise RuntimeError(
                "Round execution incomplete"
            )

        incremental = (
            load_tuning_results(
                round_root
            )
        )

        cumulative = (
            merge_cumulative_tuning_results(
                cumulative,
                incremental,
                incoming_candidate_ids=
                    incoming,
                cumulative_scenario_ids=
                    round_plan.scenario_ids,
            )
        )

        decision = decide_racing_round(
            cumulative,
            round_plan.decision_spec,
        )

        decision_path = (
            output_root
            / f"round_{round_index:02d}_decision.json"
        )

        if decision_path.exists():
            verify_or_write_json(
                decision_path,
                racing_decision_artifact(
                    decision
                ),
            )
        else:
            write_racing_decision(
                decision,
                decision_path,
            )

        print(
            f"common_mode_timeout_cells="
            f"{len(decision.common_mode_timeout_cells)}"
        )
        print(
            f"paired_quality_cells="
            f"{len(decision.selection.paired_quality_cells)}"
        )
        print(
            f"unresolved_cells="
            f"{len(decision.selection.unresolved_cells)}"
        )
        print(
            f"eligible_candidates="
            f"{len(decision.selection.eligible_candidate_ids)}"
        )
        print(
            f"survivors="
            f"{len(decision.survivor_candidate_ids)}"
        )
        print(
            f"eliminated="
            f"{len(decision.eliminated_candidates)}"
        )
        print(
            f"target_reached="
            f"{decision.target_reached}"
        )
        print(
            f"stop_reason="
            f"{decision.stop_reason}"
        )

        incoming = (
            decision.survivor_candidate_ids
        )

    final_artifact = {
        "schema_version": 1,
        "stage": "C7.4b",
        "campaign_id": campaign.campaign_id,
        "campaign_fingerprint": campaign_sha,
        "parent_round1_sha256":
            EXPECTED_PARENT_SHA256,
        "prior_round1_results_sha256":
            EXPECTED_PRIOR_RACE_SHA256,
        "prior_round2_results_sha256":
            EXPECTED_PRIOR_ROUND2_SHA256,
        "feasibility_classification_sha256":
            EXPECTED_CLASSIFICATION_SHA256,
        "holdout_accessed": False,
        "final_survivor_count":
            len(incoming),
        "final_survivor_candidate_ids":
            list(incoming),
    }

    verify_or_write_json(
        output_root
        / "final_survivors.json",
        final_artifact,
    )

    print()
    print("=" * 78)
    print(
        "C7.4B FEASIBLE-ONLY RACING COMPLETE"
    )
    print("=" * 78)
    print(
        f"final_survivors={len(incoming)}"
    )
    print(
        f"RESULT_ROOT={output_root}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
