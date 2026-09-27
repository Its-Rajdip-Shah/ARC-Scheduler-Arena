from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import replace
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BACKEND))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "arc_backend.settings")

import django
django.setup()

from arena.experiments.parallel_v1_runner import run_v1_experiment_parallel
from arena.tuning.design import build_c7_calibration_spec
from arena.tuning.study import TuningAxis, plan_tuning_study


EXPECTED_PARENT_SHA256 = (
    "dfc0b017f5f2936708d9454758a9bd95017eb085566f0d829f5505b34a1f59fe"
)

EXPECTED_SCENARIOS = (
    "G000-R0",
    "G005-R0",
    "G005-R1",
    "G016-R0",
    "G016-R1",
    "G021-R0",
    "G021-R1",
    "G027-R0",
    "G027-R1",
    "G040-R0",
    "G040-R1",
    "G044-R0",
    "G054-R0",
    "G054-R1",
)


def file_sha256(path: Path) -> str:
    h = sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def find_parent_archive() -> Path:
    candidates = (
        Path.home()
        / "Desktop"
        / "ARC_CLOUD_RESULTS"
        / "ARC_C7_4A_R1_20260925_160029.tar.gz",
        Path.home()
        / "Desktop"
        / "ARC_C7_4A_R1_20260925_160029.tar.gz",
    )

    for path in candidates:
        if path.exists():
            return path

    raise FileNotFoundError(
        "Could not find frozen Round-1 archive."
    )


def find_classification() -> Path:
    path = (
        Path.home()
        / "Desktop"
        / "ARC_C7_HARD_FEASIBILITY_CLASSIFICATION.json"
    )

    if not path.exists():
        raise FileNotFoundError(
            "Missing hard-feasibility classification JSON."
        )

    return path


def derive_confirmation_ids(
    full_development_ids: tuple[str, ...],
    classification_path: Path,
) -> tuple[str, ...]:
    payload = json.loads(
        classification_path.read_text(encoding="utf-8")
    )

    rows = {
        row["scenario_id"]: row
        for row in payload["rows"]
    }

    missing = [
        scenario_id
        for scenario_id in full_development_ids
        if scenario_id not in rows
    ]

    if missing:
        raise AssertionError(
            f"Classification missing development scenarios: {missing}"
        )

    selected = tuple(
        scenario_id
        for scenario_id in full_development_ids
        if (
            rows[scenario_id]["proof_status"]
            == "PROVEN_FEASIBLE"
            and rows[scenario_id]["anchor_count"] > 0
            and rows[scenario_id]["dependency_edge_count"] > 0
        )
    )

    if selected != EXPECTED_SCENARIOS:
        raise AssertionError(
            "Derived post-fix confirmation set changed.\n"
            f"expected={EXPECTED_SCENARIOS}\n"
            f"actual={selected}"
        )

    return selected


def main() -> int:
    parser = argparse.ArgumentParser()

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
        default="c7-postfix-confirmation",
    )

    parser.add_argument(
        "--plan-only",
        action="store_true",
    )

    args = parser.parse_args()

    if args.workers <= 0:
        raise ValueError("workers must be positive")

    output_root = args.output_root.resolve()

    if output_root.exists():
        raise FileExistsError(output_root)

    parent_archive = find_parent_archive()

    parent_hash = file_sha256(parent_archive)

    if parent_hash != EXPECTED_PARENT_SHA256:
        raise AssertionError(
            "Frozen Round-1 archive hash mismatch:\n"
            f"expected={EXPECTED_PARENT_SHA256}\n"
            f"actual={parent_hash}"
        )

    classification_path = find_classification()

    scratch_root = output_root.with_name(
        output_root.name + "_PLANNING_SCRATCH"
    )

    if scratch_root.exists():
        raise FileExistsError(scratch_root)

    base_spec = build_c7_calibration_spec(scratch_root)

    round1_axes = {
        "none": (),
        "hc": (
            TuningAxis("max_evaluations", (80, 160)),
        ),
        "vnd": (
            TuningAxis("max_evaluations", (80, 160)),
        ),
        "vns": (
            TuningAxis("max_evaluations", (80, 160)),
        ),
        "tabu": (
            TuningAxis("tabu_tenure", (3, 7)),
        ),
        "sa": (
            TuningAxis("max_evaluations", (80, 160)),
        ),
        "lns": (
            TuningAxis("max_evaluations", (30, 60)),
        ),
        "alns": (
            TuningAxis("max_evaluations", (40, 80)),
        ),
    }

    improvers = tuple(
        replace(
            sweep,
            axes=round1_axes[sweep.arm_id],
        )
        for sweep in base_spec.improvers
    )

    spec = replace(
        base_spec,
        improvers=improvers,
        seeds=(1701,),
        trial_wall_seconds=45.0,
        max_candidates=60,
        max_trials=5640,
    )

    full_plan = plan_tuning_study(spec)

    if len(full_plan.development_scenario_ids) != 94:
        raise AssertionError(
            "Expected frozen 94-scenario development partition"
        )

    if len(full_plan.holdout_scenario_ids) != 24:
        raise AssertionError(
            "Expected frozen 24-scenario holdout partition"
        )

    if len(full_plan.candidates) != 60:
        raise AssertionError(
            f"Expected frozen 60-candidate Round-1 grid, "
            f"got {len(full_plan.candidates)}"
        )

    import tarfile

    with tarfile.open(parent_archive, "r:gz") as tf:
        study_members = [
            member
            for member in tf.getmembers()
            if member.name.endswith("/study_plan.json")
        ]

        if len(study_members) != 1:
            raise AssertionError(
                "Expected exactly one frozen study_plan.json"
            )

        stream = tf.extractfile(study_members[0])

        if stream is None:
            raise AssertionError(
                "Could not read frozen study_plan.json"
            )

        frozen_study = json.loads(
            stream.read().decode("utf-8")
        )

    if frozen_study["candidate_count"] != 60:
        raise AssertionError(
            "Frozen Round-1 artifact no longer reports 60 candidates"
        )

    generated_candidate_ids = tuple(
        candidate.candidate_id
        for candidate in full_plan.candidates
    )

    frozen_candidate_ids = tuple(
        candidate["candidate_id"]
        for candidate in frozen_study["candidates"]
    )

    if generated_candidate_ids != frozen_candidate_ids:
        generated = set(generated_candidate_ids)
        frozen = set(frozen_candidate_ids)

        raise AssertionError(
            "Reconstructed Round-1 candidate identities do not match "
            "the frozen study artifact.\n"
            f"missing_from_generated={sorted(frozen - generated)}\n"
            f"unexpected_generated={sorted(generated - frozen)}"
        )

    if tuple(full_plan.development_scenario_ids) != tuple(
        frozen_study["development_scenario_ids"]
    ):
        raise AssertionError(
            "Development partition differs from frozen Round 1"
        )

    if tuple(full_plan.holdout_scenario_ids) != tuple(
        frozen_study["holdout_scenario_ids"]
    ):
        raise AssertionError(
            "Holdout partition differs from frozen Round 1"
        )

    if full_plan.benchmark_manifest_sha256 != frozen_study[
        "benchmark_manifest_sha256"
    ]:
        raise AssertionError(
            "Benchmark manifest differs from frozen Round 1"
        )

    if full_plan.spec.seeds != (1701,):
        raise AssertionError(
            f"Unexpected tuning seeds: {full_plan.spec.seeds}"
        )

    scenario_ids = derive_confirmation_ids(
        full_plan.development_scenario_ids,
        classification_path,
    )

    run = full_plan.run_configs[0]

    confirmation_run = replace(
        run,
        scenario_ids=scenario_ids,
        output_dir=output_root / run.output_dir.name,
    )

    expected_trials = (
        len(scenario_ids)
        * len(confirmation_run.constructors)
        * len(confirmation_run.improvers)
        * len(confirmation_run.seeds)
    )

    if expected_trials != 840:
        raise AssertionError(
            f"Expected 840 confirmation trials, got {expected_trials}"
        )

    plan_artifact = {
        "schema_version": 1,
        "purpose": "C7.4a post-forward-check confirmation",
        "parent_round1_archive": parent_archive.name,
        "parent_round1_sha256": parent_hash,
        "benchmark_manifest_sha256": full_plan.benchmark_manifest_sha256,
        "development_partition_size": len(
            full_plan.development_scenario_ids
        ),
        "holdout_partition_size": len(
            full_plan.holdout_scenario_ids
        ),
        "holdout_accessed": False,
        "selection_rule": {
            "proof_status": "PROVEN_FEASIBLE",
            "anchor_count_gt": 0,
            "dependency_edge_count_gt": 0,
        },
        "scenario_ids": list(scenario_ids),
        "candidate_count": len(full_plan.candidates),
        "constructor_count": len(confirmation_run.constructors),
        "improver_count": len(confirmation_run.improvers),
        "seeds": list(confirmation_run.seeds),
        "trial_wall_seconds": confirmation_run.trial_wall_seconds,
        "expected_trials": expected_trials,
        "workers_requested": args.workers,
        "execution_environment_id": args.environment_id,
    }

    print("=" * 78)
    print("C7.4A POST-FIX CONFIRMATION PLAN")
    print("=" * 78)
    print(f"parent_sha256={parent_hash}")
    print(
        f"benchmark_manifest_sha256="
        f"{full_plan.benchmark_manifest_sha256}"
    )
    print(
        f"development_partition="
        f"{len(full_plan.development_scenario_ids)}"
    )
    print(
        f"holdout_partition="
        f"{len(full_plan.holdout_scenario_ids)}"
    )
    print(f"confirmation_scenarios={len(scenario_ids)}")
    print(f"candidates={len(full_plan.candidates)}")
    print("frozen_candidate_identity_match=PASS")
    print("frozen_development_partition_match=PASS")
    print("frozen_holdout_partition_match=PASS")
    print("frozen_benchmark_manifest_match=PASS")
    print(f"expected_trials={expected_trials}")
    print(f"trial_wall_seconds={confirmation_run.trial_wall_seconds}")
    print(f"workers={args.workers}")
    print()

    for scenario_id in scenario_ids:
        print(f"  {scenario_id}")

    if args.plan_only:
        print()
        print("PLAN ONLY: no scheduling trials executed.")
        return 0

    output_root.mkdir(parents=True)

    plan_path = output_root / "confirmation_plan.json"

    plan_path.write_text(
        json.dumps(
            plan_artifact,
            indent=2,
            sort_keys=True,
        ) + "\n",
        encoding="utf-8",
    )

    result = run_v1_experiment_parallel(
        confirmation_run,
        max_workers=args.workers,
        execution_environment_id=args.environment_id,
        progress_interval_seconds=15.0,
    )

    if result.expected_trials != 840:
        raise RuntimeError(
            f"Runner expected {result.expected_trials}, not 840"
        )

    if result.completed_trials != 840:
        raise RuntimeError(
            f"Only {result.completed_trials}/840 trials completed"
        )

    summary = {
        "expected_trials": result.expected_trials,
        "completed_trials": result.completed_trials,
        "timed_out_trials": result.timed_out_trials,
        "manifest_path": str(result.manifest_path),
        "records_path": str(result.records_path),
    }

    summary_path = output_root / "confirmation_summary.json"

    summary_path.write_text(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
        ) + "\n",
        encoding="utf-8",
    )

    print()
    print("=" * 78)
    print("CONFIRMATION COMPLETE")
    print("=" * 78)
    print(
        f"completed={result.completed_trials}/"
        f"{result.expected_trials}"
    )
    print(f"timeouts={result.timed_out_trials}")
    print(f"output={output_root}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
