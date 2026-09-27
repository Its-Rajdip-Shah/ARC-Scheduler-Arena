"""Parallel, resumable execution over frozen C6.2 trial semantics.

This module changes only parent-side scheduling of independent V1 cells.
Every cell still executes through C6.2's fresh spawn-isolated trial function.
"""
from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import tempfile
import time

from .paired import ConstructorArm, ImproverArm, _normalize
from .v1_runner import (
    V1RunConfig,
    V1RunResult,
    V1RunnerError,
    _extract,
    _isolated_trial,
    _json,
    _manifest_write,
    _prepare,
    _preflight,
    _serialize,
)


@dataclass(frozen=True, slots=True)
class _Cell:
    trial_index: int
    scenario_id: str
    case: object
    keys: dict
    metadata: dict
    constructor: ConstructorArm
    improver: ImproverArm
    seed: int
    constructor_json: str
    improver_json: str | None


def _validate_options(
    max_workers: int,
    execution_environment_id: str,
    progress_interval_seconds: float | None,
) -> None:
    if type(max_workers) is not int or max_workers <= 0:
        raise ValueError("max_workers must be a positive integer")

    if (
        not isinstance(execution_environment_id, str)
        or not execution_environment_id
        or len(execution_environment_id) > 200
    ):
        raise ValueError(
            "execution_environment_id must be a nonempty string "
            "no longer than 200 characters"
        )

    if progress_interval_seconds is not None and (
        type(progress_interval_seconds) not in (int, float)
        or not math.isfinite(progress_interval_seconds)
        or progress_interval_seconds <= 0
    ):
        raise ValueError(
            "progress_interval_seconds must be positive or None"
        )


def _preflight_without_output_ownership(
    config: V1RunConfig,
) -> None:
    """Reuse frozen C6.2 checks without its exclusive-new-dir rule."""
    with tempfile.TemporaryDirectory(
        prefix="arc-parallel-preflight-"
    ) as directory:
        _preflight(
            replace(
                config,
                output_dir=Path(directory) / "unused",
            )
        )


def _execution_metadata(
    max_workers: int,
    execution_environment_id: str,
) -> dict:
    return {
        "mode": "parallel_spawn_isolated",
        "runner_schema_version": 1,
        "max_workers": max_workers,
        "execution_environment_id": execution_environment_id,
        "python_version": platform.python_version(),
        "platform_system": platform.system(),
        "platform_release": platform.release(),
        "platform_machine": platform.machine(),
        "logical_cpu_count": os.cpu_count(),
        "algorithm_budget_basis": (
            "explicit_max_iterations_and_max_evaluations"
        ),
        "wall_clock_role": "safety_fuse",
    }


def _build_cells(config: V1RunConfig):
    from arena.benchmarks.reconstruct import (
        MANIFEST,
        load_v1_scenarios,
    )

    scenarios = {
        scenario.scenario_id: scenario
        for scenario in load_v1_scenarios()
    }

    for scenario_id in config.scenario_ids:
        if scenario_id not in scenarios:
            raise ValueError(
                f"Unknown Benchmark V1 scenario: {scenario_id}"
            )

    cells = []
    scenario_metadata = []
    index = 0

    for scenario_id in config.scenario_ids:
        case, keys, metadata = _extract(
            scenarios[scenario_id]
        )
        scenario_metadata.append(metadata)

        for constructor in config.constructors:
            for improver in config.improvers:
                for seed in config.seeds:
                    _, constructor_json, improver_json = _prepare(
                        case,
                        constructor,
                        improver,
                        seed,
                        config.comparison_objective,
                    )

                    cells.append(
                        _Cell(
                            index,
                            scenario_id,
                            case,
                            keys,
                            metadata,
                            constructor,
                            improver,
                            seed,
                            constructor_json,
                            improver_json,
                        )
                    )
                    index += 1

    benchmark_hash = hashlib.sha256(
        MANIFEST.read_bytes()
    ).hexdigest()

    return (
        tuple(cells),
        tuple(scenario_metadata),
        benchmark_hash,
    )


def _new_manifest(
    config: V1RunConfig,
    scenario_metadata,
    benchmark_hash: str,
    max_workers: int,
    execution_environment_id: str,
) -> dict:
    expected = (
        len(config.scenario_ids)
        * len(config.constructors)
        * len(config.improvers)
        * len(config.seeds)
    )

    return {
        "schema_version": 1,
        "benchmark_version": "v1",
        "status": "running",
        "scenario_ids": list(config.scenario_ids),
        "axis_order": [
            "scenario",
            "constructor",
            "improver",
            "seed",
        ],
        "constructor_ids": [
            arm.arm_id for arm in config.constructors
        ],
        "improver_ids": [
            arm.arm_id for arm in config.improvers
        ],
        "seeds": list(config.seeds),
        "comparison_objective": _normalize(
            config.comparison_objective
        ),
        "trial_wall_seconds": config.trial_wall_seconds,
        "expected_trials": expected,
        "completed_trials": 0,
        "successful_trials": 0,
        "timed_out_trials": 0,
        "benchmark_manifest_sha256": benchmark_hash,
        "scenarios": list(scenario_metadata),
        "execution": _execution_metadata(
            max_workers,
            execution_environment_id,
        ),
        "started_at_utc": datetime.now(
            timezone.utc
        ).isoformat(),
    }


_STATIC_FIELDS = (
    "schema_version",
    "benchmark_version",
    "scenario_ids",
    "axis_order",
    "constructor_ids",
    "improver_ids",
    "seeds",
    "comparison_objective",
    "trial_wall_seconds",
    "expected_trials",
    "benchmark_manifest_sha256",
    "scenarios",
)


def _static_manifest_fields(manifest: dict) -> dict:
    return {
        name: manifest.get(name)
        for name in _STATIC_FIELDS
    }


def _read_manifest(path: Path) -> dict:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8")
        )
    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
    ) as exc:
        raise ValueError(
            f"Invalid parallel-run manifest: {path}"
        ) from exc

    if not isinstance(value, dict):
        raise ValueError(
            "Parallel-run manifest must be a JSON object"
        )

    return value


def _repair_trailing_partial_record(
    path: Path,
) -> None:
    """Discard only an unterminated crash tail."""
    raw = path.read_bytes()

    if not raw or raw.endswith(b"\n"):
        return

    end = raw.rfind(b"\n")
    repaired = raw[: end + 1] if end >= 0 else b""

    with path.open("wb") as stream:
        stream.write(repaired)
        stream.flush()
        os.fsync(stream.fileno())


def _cell_identity(cell: _Cell):
    return (
        cell.scenario_id,
        cell.constructor.arm_id,
        cell.improver.arm_id,
        cell.seed,
    )


def _record_identity(row: dict):
    return (
        row.get("scenario_id"),
        row.get("constructor_id"),
        row.get("improver_id"),
        row.get("run_seed"),
    )


def _load_committed_prefix(
    records_path: Path,
    cells,
    comparison_objective,
):
    _repair_trailing_partial_record(
        records_path
    )

    lines = records_path.read_text(
        encoding="utf-8"
    ).splitlines()

    if len(lines) > len(cells):
        raise ValueError(
            "Resumable records exceed expected matrix size"
        )

    successful = 0
    timed_out = 0

    for index, line in enumerate(lines):
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(
                "Corrupt complete JSONL record in resumable run"
            ) from exc

        cell = cells[index]

        if (
            row.get("trial_index") != index
            or _record_identity(row)
            != _cell_identity(cell)
        ):
            raise ValueError(
                "Resumable records are not a canonical trial prefix"
            )

        if (
            row.get("constructor_config_json")
            != cell.constructor_json
            or row.get("improver_config_json")
            != cell.improver_json
            or row.get("comparison_objective")
            != comparison_objective
        ):
            raise ValueError(
                "Resumable record provenance mismatch"
            )

        successful += row.get("status") == "ok"
        timed_out += (
            row.get("status")
            == "wall_timeout"
        )

    return len(lines), successful, timed_out


def _run_cell(
    cell: _Cell,
    config: V1RunConfig,
):
    record, wall = _isolated_trial(
        cell.case,
        cell.constructor,
        cell.improver,
        cell.seed,
        config.comparison_objective,
        config.trial_wall_seconds,
    )

    envelope = {
        key: value
        for key, value in cell.metadata.items()
        if key not in (
            "frozen_features",
            "stable_item_keys",
        )
    }

    envelope.update(
        trial_index=cell.trial_index,
        constructor_id=cell.constructor.arm_id,
        improver_id=cell.improver.arm_id,
        run_seed=cell.seed,
        constructor_config_json=cell.constructor_json,
        improver_config_json=cell.improver_json,
        comparison_objective=_normalize(
            config.comparison_objective
        ),
        status=(
            "wall_timeout"
            if record is None
            else record.status
        ),
        worker_wall_seconds=wall,
        trial=_serialize(
            record,
            cell.keys,
        ),
    )

    return cell.trial_index, envelope


def _print_progress(
    *,
    completed: int,
    expected: int,
    successful: int,
    timed_out: int,
    resumed_from: int,
    session_started: float,
    max_workers: int,
) -> None:
    elapsed = max(
        time.monotonic() - session_started,
        1e-9,
    )

    session_completed = max(
        completed - resumed_from,
        0,
    )

    rate = (
        session_completed / elapsed
        if session_completed
        else 0.0
    )

    remaining = max(
        expected - completed,
        0,
    )

    eta = (
        remaining / rate
        if rate > 0
        else None
    )

    percent = (
        100.0 * completed / expected
        if expected
        else 100.0
    )

    eta_text = (
        f"{eta / 60.0:.1f} min"
        if eta is not None
        else "calculating"
    )

    print(
        "[ARC parallel] "
        f"{completed}/{expected} "
        f"({percent:.1f}%) | "
        f"remaining={remaining} | "
        f"ok={successful} | "
        f"timeouts={timed_out} | "
        f"workers={max_workers} | "
        f"rate={rate * 60.0:.2f}/min | "
        f"ETA={eta_text}",
        flush=True,
    )


def run_v1_experiment_parallel(
    config: V1RunConfig,
    *,
    max_workers: int,
    execution_environment_id: str,
    resume: bool = False,
    progress_interval_seconds: float | None = 30.0,
) -> V1RunResult:
    """Execute independent V1 cells concurrently.

    C6.2 still owns each actual isolated trial.

    Results may finish out of order, but records are fsynced strictly in
    canonical trial-index order. Resume trusts only that durable prefix.

    Resume requires the same declared execution environment and max_workers,
    preventing different contention regimes from being silently mixed.
    """
    _validate_options(
        max_workers,
        execution_environment_id,
        progress_interval_seconds,
    )

    _preflight_without_output_ownership(
        config
    )

    cells, metadata, benchmark_hash = (
        _build_cells(config)
    )

    expected = len(cells)

    if not expected:
        raise ValueError(
            "Parallel run contains no trials"
        )

    fresh_manifest = _new_manifest(
        config,
        metadata,
        benchmark_hash,
        max_workers,
        execution_environment_id,
    )

    manifest_path = (
        config.output_dir / "manifest.json"
    )
    records_path = (
        config.output_dir / "records.jsonl"
    )

    if os.path.lexists(config.output_dir):
        if not resume:
            raise FileExistsError(
                config.output_dir
            )

        if (
            not config.output_dir.is_dir()
            or not manifest_path.is_file()
            or not records_path.is_file()
        ):
            raise ValueError(
                "Resume requires manifest.json and records.jsonl"
            )

        manifest = _read_manifest(
            manifest_path
        )

        if (
            _static_manifest_fields(manifest)
            != _static_manifest_fields(
                fresh_manifest
            )
        ):
            raise ValueError(
                "Resume configuration/provenance mismatch"
            )

        execution = manifest.get(
            "execution"
        )

        if (
            not isinstance(execution, dict)
            or execution.get("mode")
            != "parallel_spawn_isolated"
            or execution.get(
                "runner_schema_version"
            )
            != 1
            or execution.get(
                "max_workers"
            )
            != max_workers
            or execution.get(
                "execution_environment_id"
            )
            != execution_environment_id
        ):
            raise ValueError(
                "Resume execution environment/worker count mismatch"
            )

        completed, successful, timed_out = (
            _load_committed_prefix(
                records_path,
                cells,
                fresh_manifest[
                    "comparison_objective"
                ],
            )
        )

        if manifest.get("status") == "complete":
            expected_hash = manifest.get(
                "records_sha256"
            )
            actual_hash = hashlib.sha256(
                records_path.read_bytes()
            ).hexdigest()

            if (
                completed != expected
                or manifest.get(
                    "completed_trials"
                ) != completed
                or manifest.get(
                    "successful_trials"
                ) != successful
                or manifest.get(
                    "timed_out_trials"
                ) != timed_out
                or expected_hash != actual_hash
            ):
                raise ValueError(
                    "Completed resumable run failed "
                    "integrity validation"
                )

            return V1RunResult(
                config.output_dir,
                len(config.scenario_ids),
                expected,
                completed,
                timed_out,
                manifest_path,
                records_path,
            )

        manifest.pop("error", None)
        manifest.pop(
            "records_sha256",
            None,
        )

        manifest.update(
            status="running",
            completed_trials=completed,
            successful_trials=successful,
            timed_out_trials=timed_out,
            resumed_at_utc=datetime.now(
                timezone.utc
            ).isoformat(),
        )

        _manifest_write(
            manifest_path,
            manifest,
        )

    else:
        config.output_dir.mkdir()

        manifest = fresh_manifest
        completed = 0
        successful = 0
        timed_out = 0

        _manifest_write(
            manifest_path,
            manifest,
        )

        with records_path.open(
            "x",
            encoding="utf-8",
        ) as stream:
            stream.flush()
            os.fsync(
                stream.fileno()
            )

    resumed_from = completed
    next_commit = completed
    next_submit = completed

    result_buffer = {}
    in_flight = {}

    session_started = time.monotonic()
    last_progress = session_started

    if progress_interval_seconds is not None:
        _print_progress(
            completed=completed,
            expected=expected,
            successful=successful,
            timed_out=timed_out,
            resumed_from=resumed_from,
            session_started=session_started,
            max_workers=max_workers,
        )

    executor = ThreadPoolExecutor(
        max_workers=max_workers,
        thread_name_prefix="arc-v1",
    )

    try:
        with records_path.open(
            "a",
            encoding="utf-8",
        ) as stream:

            while next_commit < expected:

                while (
                    next_submit < expected
                    and len(in_flight)
                    < max_workers * 2
                ):
                    cell = cells[
                        next_submit
                    ]

                    future = executor.submit(
                        _run_cell,
                        cell,
                        config,
                    )

                    in_flight[future] = (
                        cell.trial_index
                    )

                    next_submit += 1

                if not in_flight:
                    raise V1RunnerError(
                        "Parallel runner stalled"
                    )

                done, _ = wait(
                    tuple(in_flight),
                    return_when=FIRST_COMPLETED,
                )

                for future in done:
                    expected_index = (
                        in_flight.pop(
                            future
                        )
                    )

                    (
                        result_index,
                        envelope,
                    ) = future.result()

                    if (
                        result_index
                        != expected_index
                    ):
                        raise V1RunnerError(
                            "Parallel result index mismatch"
                        )

                    if (
                        result_index
                        in result_buffer
                    ):
                        raise V1RunnerError(
                            "Duplicate parallel result"
                        )

                    result_buffer[
                        result_index
                    ] = envelope

                while (
                    next_commit
                    in result_buffer
                ):
                    envelope = (
                        result_buffer.pop(
                            next_commit
                        )
                    )

                    stream.write(
                        _json(envelope)
                        + "\n"
                    )
                    stream.flush()
                    os.fsync(
                        stream.fileno()
                    )

                    completed += 1
                    successful += (
                        envelope["status"]
                        == "ok"
                    )
                    timed_out += (
                        envelope["status"]
                        == "wall_timeout"
                    )
                    next_commit += 1

                    manifest.update(
                        completed_trials=completed,
                        successful_trials=successful,
                        timed_out_trials=timed_out,
                    )

                    _manifest_write(
                        manifest_path,
                        manifest,
                    )

                now = time.monotonic()

                if (
                    progress_interval_seconds
                    is not None
                    and (
                        now - last_progress
                        >= progress_interval_seconds
                        or completed
                        == expected
                    )
                ):
                    _print_progress(
                        completed=completed,
                        expected=expected,
                        successful=successful,
                        timed_out=timed_out,
                        resumed_from=resumed_from,
                        session_started=session_started,
                        max_workers=max_workers,
                    )

                    last_progress = now

        if completed != expected:
            raise V1RunnerError(
                "Completed parallel matrix size mismatch"
            )

        manifest.update(
            status="complete",
            completed_at_utc=datetime.now(
                timezone.utc
            ).isoformat(),
            records_sha256=hashlib.sha256(
                records_path.read_bytes()
            ).hexdigest(),
        )

        _manifest_write(
            manifest_path,
            manifest,
        )

    except BaseException as exc:
        manifest.update(
            status="failed",
            error={
                "type": type(exc).__name__,
                "message": str(exc)[:2000],
            },
        )

        try:
            _manifest_write(
                manifest_path,
                manifest,
            )
        except BaseException:
            pass

        raise

    finally:
        executor.shutdown(
            wait=True,
            cancel_futures=True,
        )

    return V1RunResult(
        config.output_dir,
        len(config.scenario_ids),
        expected,
        completed,
        timed_out,
        manifest_path,
        records_path,
    )
