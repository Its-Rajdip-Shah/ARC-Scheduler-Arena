"""Parallel/resumable execution of registered C7 tuning studies.

C7 candidate identity, workload selection, seeds, deterministic algorithm
budgets, objective definitions and durable evidence remain owned by the
existing frozen planning/C6 layers.

This module only changes how independent registered cells are dispatched.
"""
from __future__ import annotations

import os

from arena.experiments.parallel_v1_runner import (
    run_v1_experiment_parallel,
)

from .execution import (
    TuningExecutionResult,
    _registered_plan_bytes,
)
from .study import TuningStudyPlan


def execute_tuning_study_parallel(
    plan: TuningStudyPlan,
    *,
    max_workers: int,
    execution_environment_id: str,
    resume: bool = False,
    progress_interval_seconds: float | None = 30.0,
) -> TuningExecutionResult:
    """Execute a registered C7 development study with bounded concurrency.

    The registered study remains scientifically authoritative. Parallelism is
    purely execution orchestration.

    Existing objective-group directories may be resumed only when ``resume``
    is true. The underlying parallel V1 runner verifies canonical prefix
    provenance, worker-count/environment identity, and completed-run hashes.
    """
    if not isinstance(plan, TuningStudyPlan):
        raise TypeError(
            "Expected TuningStudyPlan"
        )

    if type(resume) is not bool:
        raise TypeError(
            "resume must be boolean"
        )

    root = plan.spec.output_root
    registration = root / "study_plan.json"

    if (
        not root.is_dir()
        or not registration.is_file()
    ):
        raise ValueError(
            "Tuning study must be durably registered "
            "before execution"
        )

    try:
        actual = registration.read_bytes()
    except OSError as exc:
        raise ValueError(
            "Could not read registered tuning plan"
        ) from exc

    if actual != _registered_plan_bytes(plan):
        raise ValueError(
            "Registered tuning plan does not match "
            "supplied plan"
        )

    if any(
        run.scenario_ids
        != plan.development_scenario_ids
        for run in plan.run_configs
    ):
        raise ValueError(
            "Tuning execution may use development "
            "scenarios only"
        )

    if (
        set(plan.development_scenario_ids)
        & set(plan.holdout_scenario_ids)
    ):
        raise ValueError(
            "Development and holdout scenarios must "
            "be disjoint"
        )

    expected_dirs = [
        run.output_dir
        for run in plan.run_configs
    ]

    if (
        len(set(expected_dirs))
        != len(expected_dirs)
    ):
        raise ValueError(
            "Tuning run output directories must be unique"
        )

    for run in plan.run_configs:
        if run.output_dir.parent != root:
            raise ValueError(
                "Tuning run output directory escaped "
                "study root"
            )

        if (
            os.path.lexists(run.output_dir)
            and not resume
        ):
            raise FileExistsError(
                run.output_dir
            )

    results = []

    for index, run in enumerate(
        plan.run_configs,
        start=1,
    ):
        existing = os.path.lexists(
            run.output_dir
        )

        print(
            "[ARC tuning] "
            f"objective group "
            f"{index}/{len(plan.run_configs)} | "
            f"workers={max_workers} | "
            f"resume={existing and resume}",
            flush=True,
        )

        result = run_v1_experiment_parallel(
            run,
            max_workers=max_workers,
            execution_environment_id=(
                execution_environment_id
            ),
            resume=existing and resume,
            progress_interval_seconds=(
                progress_interval_seconds
            ),
        )

        if (
            result.output_dir
            != run.output_dir
            or result.expected_trials
            != result.completed_trials
        ):
            raise RuntimeError(
                "Parallel C6 runner returned an "
                "incomplete or mismatched tuning run"
            )

        results.append(result)

    completed = sum(
        result.completed_trials
        for result in results
    )

    timed_out = sum(
        result.timed_out_trials
        for result in results
    )

    if completed != plan.expected_trials:
        raise RuntimeError(
            "Completed tuning trial count differs "
            "from registered plan"
        )

    return TuningExecutionResult(
        root,
        tuple(results),
        plan.expected_trials,
        completed,
        timed_out,
    )
