"""C7.2c parallel V1 execution contracts."""
from copy import deepcopy
from dataclasses import replace
import json

import pytest

from arena.algorithms import (
    EarliestFeasible,
    PressureGreedy,
)
from arena.algorithms.tests.test_greedy import (
    config as greedy_config,
)
from arena.experiments import (
    ConstructorArm,
    ImproverArm,
    V1RunConfig,
    WorkloadCase,
)
from arena.experiments import (
    v1_runner as serial,
)
from arena.experiments import (
    parallel_v1_runner as parallel,
)
from arena.search.tests.helpers import (
    item,
    objective,
    problem,
)


def configuration(path):
    return V1RunConfig(
        ("G000-R0",),
        (
            ConstructorArm(
                "earliest",
                EarliestFeasible(),
            ),
            ConstructorArm(
                "pressure",
                PressureGreedy(
                    greedy_config()
                ),
            ),
        ),
        (
            ImproverArm(
                "none",
                None,
            ),
        ),
        (7, 8),
        objective(),
        15.0,
        path,
    )


@pytest.fixture
def pure_extraction(monkeypatch):
    def extract(scenario):
        case = WorkloadCase(
            scenario.scenario_id,
            "benchmark_v1",
            problem(item(42)),
            scenario.seed,
        )

        metadata = dict(
            scenario_id=case.workload_id,
            workload_seed=case.workload_seed,
            family=case.family,
            design_index=(
                scenario.design_index
            ),
            replicate_index=(
                scenario.replicate_index
            ),
            frozen_features=(
                scenario.frozen_features
            ),
            stable_item_keys=[
                "item-42"
            ],
        )

        return (
            case,
            {42: "item-42"},
            metadata,
        )

    monkeypatch.setattr(
        serial,
        "_extract",
        extract,
    )

    monkeypatch.setattr(
        parallel,
        "_extract",
        extract,
    )


def read_run(path):
    manifest = json.loads(
        (
            path / "manifest.json"
        ).read_text()
    )

    records = [
        json.loads(line)
        for line in (
            path / "records.jsonl"
        ).read_text().splitlines()
    ]

    return manifest, records


def scrub_timing(record):
    value = deepcopy(record)

    value.pop(
        "worker_wall_seconds",
        None,
    )

    trial = value.get("trial")

    if isinstance(trial, dict):
        trial.pop(
            "constructor_seconds",
            None,
        )
        trial.pop(
            "improver_seconds",
            None,
        )
        trial.pop(
            "total_seconds",
            None,
        )

    return value


def test_parallel_matches_serial_non_timing_evidence(
    tmp_path,
    pure_extraction,
):
    serial_config = configuration(
        tmp_path / "serial"
    )

    parallel_config = replace(
        serial_config,
        output_dir=(
            tmp_path / "parallel"
        ),
    )

    serial.run_v1_experiment(
        serial_config
    )

    parallel.run_v1_experiment_parallel(
        parallel_config,
        max_workers=2,
        execution_environment_id=(
            "pytest-local-v1"
        ),
        progress_interval_seconds=None,
    )

    (
        serial_manifest,
        serial_records,
    ) = read_run(
        serial_config.output_dir
    )

    (
        parallel_manifest,
        parallel_records,
    ) = read_run(
        parallel_config.output_dir
    )

    assert [
        scrub_timing(row)
        for row in parallel_records
    ] == [
        scrub_timing(row)
        for row in serial_records
    ]

    assert [
        row["trial_index"]
        for row in parallel_records
    ] == list(range(4))

    assert (
        parallel_manifest["status"]
        == "complete"
    )

    assert (
        parallel_manifest[
            "execution"
        ]["max_workers"]
        == 2
    )

    assert (
        parallel_manifest[
            "execution"
        ][
            "execution_environment_id"
        ]
        == "pytest-local-v1"
    )

    for name in (
        "scenario_ids",
        "constructor_ids",
        "improver_ids",
        "seeds",
        "comparison_objective",
        "expected_trials",
        "benchmark_manifest_sha256",
    ):
        assert (
            parallel_manifest[name]
            == serial_manifest[name]
        )


def test_parallel_resume_reconstructs_canonical_prefix(
    tmp_path,
    pure_extraction,
):
    destination = (
        tmp_path / "resume"
    )

    config = configuration(
        destination
    )

    parallel.run_v1_experiment_parallel(
        config,
        max_workers=2,
        execution_environment_id=(
            "pytest-local-v1"
        ),
        progress_interval_seconds=None,
    )

    (
        complete_manifest,
        complete_records,
    ) = read_run(destination)

    kept = complete_records[:2]

    raw = "".join(
        json.dumps(
            row,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ) + "\n"
        for row in kept
    )

    (
        destination
        / "records.jsonl"
    ).write_text(
        raw,
        encoding="utf-8",
    )

    manifest = dict(
        complete_manifest
    )

    manifest.update(
        status="running",
        completed_trials=2,
        successful_trials=sum(
            row["status"] == "ok"
            for row in kept
        ),
        timed_out_trials=sum(
            row["status"]
            == "wall_timeout"
            for row in kept
        ),
    )

    manifest.pop(
        "records_sha256",
        None,
    )

    manifest.pop(
        "completed_at_utc",
        None,
    )

    (
        destination
        / "manifest.json"
    ).write_text(
        json.dumps(manifest),
        encoding="utf-8",
    )

    result = (
        parallel
        .run_v1_experiment_parallel(
            config,
            max_workers=2,
            execution_environment_id=(
                "pytest-local-v1"
            ),
            resume=True,
            progress_interval_seconds=None,
        )
    )

    assert (
        result.completed_trials
        == 4
    )

    (
        resumed_manifest,
        resumed_records,
    ) = read_run(destination)

    assert (
        resumed_manifest["status"]
        == "complete"
    )

    assert [
        row["trial_index"]
        for row in resumed_records
    ] == list(range(4))

    assert [
        scrub_timing(row)
        for row in resumed_records
    ] == [
        scrub_timing(row)
        for row in complete_records
    ]


def test_resume_rejects_changed_resource_regime(
    tmp_path,
    pure_extraction,
):
    destination = (
        tmp_path / "regime"
    )

    config = configuration(
        destination
    )

    parallel.run_v1_experiment_parallel(
        config,
        max_workers=2,
        execution_environment_id=(
            "regime-a"
        ),
        progress_interval_seconds=None,
    )

    manifest, records = read_run(
        destination
    )

    first = records[:1]

    (
        destination
        / "records.jsonl"
    ).write_text(
        json.dumps(
            first[0],
            sort_keys=True,
            separators=(",", ":"),
        ) + "\n",
        encoding="utf-8",
    )

    manifest.update(
        status="running",
        completed_trials=1,
        successful_trials=(
            first[0]["status"]
            == "ok"
        ),
        timed_out_trials=(
            first[0]["status"]
            == "wall_timeout"
        ),
    )

    manifest.pop(
        "records_sha256",
        None,
    )

    manifest.pop(
        "completed_at_utc",
        None,
    )

    (
        destination
        / "manifest.json"
    ).write_text(
        json.dumps(manifest),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match=(
            "environment/worker count "
            "mismatch"
        ),
    ):
        parallel.run_v1_experiment_parallel(
            config,
            max_workers=3,
            execution_environment_id=(
                "regime-a"
            ),
            resume=True,
            progress_interval_seconds=None,
        )

    with pytest.raises(
        ValueError,
        match=(
            "environment/worker count "
            "mismatch"
        ),
    ):
        parallel.run_v1_experiment_parallel(
            config,
            max_workers=2,
            execution_environment_id=(
                "regime-b"
            ),
            resume=True,
            progress_interval_seconds=None,
        )


def test_parallel_refuses_overwrite_without_resume(
    tmp_path,
    pure_extraction,
):
    config = configuration(
        tmp_path / "owned"
    )

    parallel.run_v1_experiment_parallel(
        config,
        max_workers=2,
        execution_environment_id=(
            "pytest-local-v1"
        ),
        progress_interval_seconds=None,
    )

    with pytest.raises(
        FileExistsError
    ):
        parallel.run_v1_experiment_parallel(
            config,
            max_workers=2,
            execution_environment_id=(
                "pytest-local-v1"
            ),
            progress_interval_seconds=None,
        )


def test_completed_parallel_run_is_verified_idempotently(
    tmp_path,
    pure_extraction,
):
    destination = (
        tmp_path / "complete-resume"
    )

    config = configuration(
        destination
    )

    first = (
        parallel
        .run_v1_experiment_parallel(
            config,
            max_workers=2,
            execution_environment_id=(
                "pytest-local-v1"
            ),
            progress_interval_seconds=None,
        )
    )

    before = (
        destination
        / "records.jsonl"
    ).read_bytes()

    second = (
        parallel
        .run_v1_experiment_parallel(
            config,
            max_workers=2,
            execution_environment_id=(
                "pytest-local-v1"
            ),
            resume=True,
            progress_interval_seconds=None,
        )
    )

    after = (
        destination
        / "records.jsonl"
    ).read_bytes()

    assert before == after
    assert (
        first.completed_trials
        == second.completed_trials
        == 4
    )


def test_parallel_manifest_declares_resource_contract(
    tmp_path,
    pure_extraction,
):
    destination = (
        tmp_path / "resource-contract"
    )

    config = configuration(
        destination
    )

    parallel.run_v1_experiment_parallel(
        config,
        max_workers=2,
        execution_environment_id=(
            "pytest-resource-contract"
        ),
        progress_interval_seconds=None,
    )

    manifest, _ = read_run(
        destination
    )

    execution = manifest["execution"]

    assert (
        execution["algorithm_budget_basis"]
        == "explicit_max_iterations_and_max_evaluations"
    )

    assert (
        execution["wall_clock_role"]
        == "safety_fuse"
    )
