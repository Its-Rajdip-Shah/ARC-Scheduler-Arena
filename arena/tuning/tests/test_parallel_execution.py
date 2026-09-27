"""C7 parallel-study orchestration contracts."""
from pathlib import Path

import pytest

from arena.experiments import V1RunResult
from arena.tuning import (
    build_c7_budget_probe_spec,
    execute_tuning_study_parallel,
    plan_tuning_study,
    write_tuning_plan,
)
from arena.tuning import parallel_execution


def registered_plan(tmp_path: Path):
    plan = plan_tuning_study(
        build_c7_budget_probe_spec(
            tmp_path / "study"
        )
    )
    write_tuning_plan(plan)
    return plan


def test_parallel_study_delegates_registered_runs(
    tmp_path,
    monkeypatch,
):
    plan = registered_plan(tmp_path)
    calls = []

    def fake_runner(
        run,
        *,
        max_workers,
        execution_environment_id,
        resume,
        progress_interval_seconds,
    ):
        calls.append(
            (
                run.output_dir,
                max_workers,
                execution_environment_id,
                resume,
                progress_interval_seconds,
            )
        )

        expected = (
            len(run.scenario_ids)
            * len(run.constructors)
            * len(run.improvers)
            * len(run.seeds)
        )

        return V1RunResult(
            run.output_dir,
            len(run.scenario_ids),
            expected,
            expected,
            0,
            run.output_dir / "manifest.json",
            run.output_dir / "records.jsonl",
        )

    monkeypatch.setattr(
        parallel_execution,
        "run_v1_experiment_parallel",
        fake_runner,
    )

    result = execute_tuning_study_parallel(
        plan,
        max_workers=50,
        execution_environment_id=(
            "azure-64vcpu-50w-v1"
        ),
        progress_interval_seconds=17.0,
    )

    assert (
        result.completed_trials
        == plan.expected_trials
    )

    assert len(calls) == len(
        plan.run_configs
    )

    assert all(
        call[1:] == (
            50,
            "azure-64vcpu-50w-v1",
            False,
            17.0,
        )
        for call in calls
    )


def test_parallel_study_requires_explicit_resume(
    tmp_path,
):
    plan = registered_plan(tmp_path)

    run_dir = (
        plan.run_configs[0].output_dir
    )
    run_dir.mkdir()

    with pytest.raises(
        FileExistsError
    ):
        execute_tuning_study_parallel(
            plan,
            max_workers=2,
            execution_environment_id=(
                "local-test"
            ),
        )


def test_parallel_study_never_accepts_holdout_overlap(
    tmp_path,
):
    plan = registered_plan(tmp_path)

    from dataclasses import replace

    poisoned = replace(
        plan,
        holdout_scenario_ids=(
            plan.development_scenario_ids[0],
        ),
    )

    # Re-register the deliberately poisoned plan so this test reaches
    # the independent development/holdout-disjointness guard rather
    # than being rejected earlier by immutable-plan provenance.
    (
        poisoned.spec.output_root
        / "study_plan.json"
    ).write_bytes(
        parallel_execution._registered_plan_bytes(
            poisoned
        )
    )

    with pytest.raises(
        ValueError,
        match="disjoint",
    ):
        execute_tuning_study_parallel(
            poisoned,
            max_workers=2,
            execution_environment_id=(
                "local-test"
            ),
        )
