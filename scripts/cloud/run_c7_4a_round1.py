from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
import json
import os
import sys

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
    TuningAxis,
    ImproverSweep,
    build_c7_calibration_spec,
    execute_tuning_study_parallel,
    load_tuning_results,
    plan_tuning_study,
    write_tuning_plan,
)


WALL_SECONDS = 45.0
MAX_WORKERS = 50
EXPECTED_CANDIDATES = 60
EXPECTED_TRIALS = 5640


def two_variant_sweep(sweep: ImproverSweep) -> ImproverSweep:
    arm = sweep.arm_id

    if arm == "none":
        return sweep

    if arm == "hc":
        axis = TuningAxis(
            "max_evaluations",
            (80, 160),
        )
    elif arm == "vnd":
        axis = TuningAxis(
            "max_evaluations",
            (80, 160),
        )
    elif arm == "vns":
        axis = TuningAxis(
            "max_evaluations",
            (80, 160),
        )
    elif arm == "tabu":
        axis = TuningAxis(
            "tabu_tenure",
            (3, 7),
        )
    elif arm == "sa":
        axis = TuningAxis(
            "max_evaluations",
            (80, 160),
        )
    elif arm == "lns":
        axis = TuningAxis(
            "max_evaluations",
            (30, 60),
        )
    elif arm == "alns":
        axis = TuningAxis(
            "max_evaluations",
            (40, 80),
        )
    else:
        raise RuntimeError(
            f"Unexpected calibration improver: {arm}"
        )

    return replace(
        sweep,
        axes=(axis,),
    )


def main() -> int:
    stamp = datetime.now(
        timezone.utc
    ).strftime("%Y%m%d_%H%M%S")

    output_root = (
        Path.home()
        / f"ARC_C7_4A_R1_{stamp}"
    )

    template = build_c7_calibration_spec(
        output_root
    )

    improvers = tuple(
        two_variant_sweep(sweep)
        for sweep in template.improvers
    )

    spec = replace(
        template,
        improvers=improvers,
        trial_wall_seconds=WALL_SECONDS,
        max_candidates=EXPECTED_CANDIDATES,
        max_trials=EXPECTED_TRIALS,
    )

    plan = plan_tuning_study(spec)

    print("=== C7.4a ROUND 1 PLAN ===")
    print(f"output_root={output_root}")
    print(
        f"development_scenarios="
        f"{len(plan.development_scenario_ids)}"
    )
    print(
        f"holdout_scenarios="
        f"{len(plan.holdout_scenario_ids)}"
    )
    print(f"candidates={len(plan.candidates)}")
    print(f"expected_trials={plan.expected_trials}")
    print(f"workers={MAX_WORKERS}")
    print(f"wall_cutoff_seconds={WALL_SECONDS}")

    assert len(plan.development_scenario_ids) == 94
    assert len(plan.holdout_scenario_ids) == 24
    assert len(plan.candidates) == EXPECTED_CANDIDATES
    assert plan.expected_trials == EXPECTED_TRIALS
    assert not (
        set(plan.development_scenario_ids)
        & set(plan.holdout_scenario_ids)
    )

    plan_path = write_tuning_plan(plan)

    print()
    print(f"registered={plan_path}")
    print()
    print("=== EXECUTE REAL C7.4a ROUND 1 ===")

    execution = execute_tuning_study_parallel(
        plan,
        max_workers=MAX_WORKERS,
        execution_environment_id=(
            "azure-f64als-v7-64vcpu-50w-c7-4a-r1"
        ),
        resume=False,
        progress_interval_seconds=10.0,
    )

    print()
    print("=== LOAD + VALIDATE EVIDENCE ===")

    results = load_tuning_results(
        execution.output_root
    )

    summaries = []

    for row in results.candidate_summaries:
        summaries.append({
            "candidate_id": row.candidate_id,
            "objective_id": row.objective_id,
            "constructor_id": row.constructor_id,
            "improver_id": row.improver_id,
            "intended_trials": row.intended_trials,
            "ok_trials": row.ok_trials,
            "timed_out_trials": row.timed_out_trials,
            "failed_trials": row.failed_trials,
            "ok_rate": row.ok_rate,
            "timeout_rate": row.timeout_rate,
            "mean_worker_wall_seconds": (
                row.mean_worker_wall_seconds
            ),
            "performance_means": dict(
                row.performance_means
            ),
            "performance_observation_counts": dict(
                row.performance_observation_counts
            ),
        })

    report = {
        "stage": "C7.4a-round1",
        "execution_environment": (
            "azure-f64als-v7-64vcpu-50w"
        ),
        "workers": MAX_WORKERS,
        "wall_cutoff_seconds": WALL_SECONDS,
        "candidate_count": len(plan.candidates),
        "development_scenario_count": len(
            plan.development_scenario_ids
        ),
        "holdout_scenario_count": len(
            plan.holdout_scenario_ids
        ),
        "expected_trials": execution.expected_trials,
        "completed_trials": execution.completed_trials,
        "timed_out_trials": execution.timed_out_trials,
        "candidate_summaries": summaries,
    }

    report_path = (
        output_root
        / "c7_4a_round1_summary.json"
    )

    report_path.write_text(
        json.dumps(
            report,
            indent=2,
            sort_keys=True,
        ) + "\n",
        encoding="utf-8",
    )

    print()
    print("=== C7.4a ROUND 1 COMPLETE ===")
    print(
        f"completed_trials="
        f"{execution.completed_trials}"
    )
    print(
        f"timed_out_trials="
        f"{execution.timed_out_trials}"
    )
    print(
        f"candidate_summaries="
        f"{len(results.candidate_summaries)}"
    )
    print(f"report={report_path}")
    print(f"RESULT_ROOT={output_root}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
