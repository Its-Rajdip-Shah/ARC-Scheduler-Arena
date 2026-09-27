"""C7.2: execute registered development-only tuning studies and read their evidence."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from math import isfinite
import os
from pathlib import Path
from types import MappingProxyType

from arena.experiments.v1_runner import V1RunResult, _preflight, run_v1_experiment
from arena.evaluation.performance import PerformanceVector

from .study import TuningStudyPlan, _artifact, _dump


_ALLOWED_STATUSES = {
    'ok', 'wall_timeout', 'constructor_invalid', 'constructor_infeasible',
    'constructor_unsearchable', 'constructor_error', 'improver_error',
}


@dataclass(frozen=True, slots=True)
class TuningExecutionResult:
    output_root: Path
    run_results: tuple[V1RunResult, ...]
    expected_trials: int
    completed_trials: int
    timed_out_trials: int


@dataclass(frozen=True, slots=True)
class TuningCandidateSummary:
    candidate_id: str
    objective_id: str
    constructor_id: str
    improver_id: str
    intended_trials: int
    ok_trials: int
    timed_out_trials: int
    failed_trials: int
    ok_rate: float
    timeout_rate: float
    mean_worker_wall_seconds: float
    performance_means: MappingProxyType
    performance_observation_counts: MappingProxyType


@dataclass(frozen=True, slots=True)
class TuningTrialObservation:
    candidate_id: str
    scenario_id: str
    run_seed: int
    status: str
    worker_wall_seconds: float
    performance: MappingProxyType | None


@dataclass(frozen=True, slots=True)
class TuningStudyResults:
    output_root: Path
    benchmark_manifest_sha256: str
    development_scenario_ids: tuple[str, ...]
    holdout_scenario_ids: tuple[str, ...]
    seeds: tuple[int, ...]
    candidate_summaries: tuple[TuningCandidateSummary, ...]
    trial_observations: tuple[TuningTrialObservation, ...]
    expected_trials: int
    completed_trials: int


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f'Invalid JSON artifact: {path}') from exc


def _registered_plan_bytes(plan: TuningStudyPlan) -> bytes:
    return (_dump(_artifact(plan)) + '\n').encode('utf-8')


def execute_tuning_study(plan: TuningStudyPlan) -> TuningExecutionResult:
    """Execute every C6.2 run in a previously registered C7.1 plan.

    This is orchestration only: C6.2 owns trial isolation and durable run
    artifacts. No holdout scenarios are added and no winner is selected here.
    """
    if not isinstance(plan, TuningStudyPlan):
        raise TypeError('Expected TuningStudyPlan')

    root = plan.spec.output_root
    registration = root / 'study_plan.json'

    if not root.is_dir() or not registration.is_file():
        raise ValueError('Tuning study must be durably registered before execution')

    try:
        actual = registration.read_bytes()
    except OSError as exc:
        raise ValueError('Could not read registered tuning plan') from exc

    if actual != _registered_plan_bytes(plan):
        raise ValueError('Registered tuning plan does not match supplied plan')

    if any(
        run.scenario_ids != plan.development_scenario_ids
        for run in plan.run_configs
    ):
        raise ValueError('Tuning execution may use development scenarios only')

    if set(plan.development_scenario_ids) & set(plan.holdout_scenario_ids):
        raise ValueError('Development and holdout scenarios must be disjoint')

    expected_dirs = [run.output_dir for run in plan.run_configs]
    if len(set(expected_dirs)) != len(expected_dirs):
        raise ValueError('Tuning run output directories must be unique')

    # Preflight everything before starting the first expensive group so a
    # static error in a later group cannot create an avoidable partial study.
    for run in plan.run_configs:
        if run.output_dir.parent != root:
            raise ValueError('Tuning run output directory escaped study root')
        if os.path.lexists(run.output_dir):
            raise FileExistsError(run.output_dir)
        _preflight(run)

    results = []
    for run in plan.run_configs:
        result = run_v1_experiment(run)
        if (
            result.output_dir != run.output_dir
            or result.expected_trials != result.completed_trials
        ):
            raise RuntimeError(
                'C6.2 returned an incomplete or mismatched tuning run'
            )
        results.append(result)

    completed = sum(result.completed_trials for result in results)
    timed_out = sum(result.timed_out_trials for result in results)

    if completed != plan.expected_trials:
        raise RuntimeError(
            'Completed tuning trial count differs from registered plan'
        )

    return TuningExecutionResult(
        root,
        tuple(results),
        plan.expected_trials,
        completed,
        timed_out,
    )


def _safe_group_directory(root: Path, value: object) -> Path:
    if (
        not isinstance(value, str)
        or not value
        or Path(value).name != value
    ):
        raise ValueError('Invalid objective group output directory')
    return root / value


def _mean(values):
    return sum(values) / len(values)


def load_tuning_results(output_root: Path) -> TuningStudyResults:
    """Validate complete C7/C6 artifacts and aggregate development observations.

    Performance means are unweighted macro-means of available per-trial C1
    fields. They are descriptive only. This function performs no scalar
    ranking, objective-total comparison, Pareto selection, or holdout
    evaluation.
    """
    if not isinstance(output_root, Path):
        raise TypeError('output_root must be a Path')

    plan_path = output_root / 'study_plan.json'
    plan = _read_json(plan_path)

    if (
        plan.get('schema_version') != 1
        or plan.get('benchmark_version') != 'v1'
    ):
        raise ValueError('Unsupported tuning plan schema')

    development = tuple(plan.get('development_scenario_ids', ()))
    holdout = tuple(plan.get('holdout_scenario_ids', ()))
    seeds = tuple(plan.get('seeds', ()))

    if (
        not development
        or not holdout
        or set(development) & set(holdout)
        or any(type(seed) is not int for seed in seeds)
        or not seeds
    ):
        raise ValueError(
            'Invalid registered development/holdout split or seeds'
        )

    benchmark_hash = plan.get('benchmark_manifest_sha256')
    if (
        not isinstance(benchmark_hash, str)
        or len(benchmark_hash) != 64
    ):
        raise ValueError('Invalid benchmark manifest hash')

    candidate_rows = plan.get('candidates')
    groups = plan.get('objective_groups')

    if (
        not isinstance(candidate_rows, list)
        or not candidate_rows
        or not isinstance(groups, list)
        or not groups
    ):
        raise ValueError(
            'Registered study contains no candidates/objective groups'
        )

    candidate_by_key = {}
    ordered_candidates = []

    for row in candidate_rows:
        try:
            key = (
                row['objective_id'],
                row['constructor_id'],
                row['improver_id'],
            )
            candidate_id = row['candidate_id']
        except (TypeError, KeyError) as exc:
            raise ValueError('Malformed candidate declaration') from exc

        if (
            key in candidate_by_key
            or not all(
                isinstance(value, str) and value
                for value in (*key, candidate_id)
            )
        ):
            raise ValueError(
                'Duplicate or malformed candidate declaration'
            )

        candidate_by_key[key] = candidate_id
        ordered_candidates.append((candidate_id, *key))

    observed = {
        candidate_id: []
        for candidate_id, *_ in ordered_candidates
    }

    total_records = 0

    for group in groups:
        try:
            objective_id = group['objective_id']
            comparison_objective = group['comparison_objective']
            constructors = group['constructors']
            improvers = group['improvers']
            directory = _safe_group_directory(
                output_root,
                group['output_directory'],
            )
        except (TypeError, KeyError) as exc:
            raise ValueError('Malformed objective group') from exc

        constructor_configs = {
            row['arm_id']: row['config_json']
            for row in constructors
        }

        improver_configs = {
            row['arm_id']: {
                entry['run_seed']: entry['config_json']
                for entry in row['effective_configs']
            }
            for row in improvers
        }

        constructor_ids = tuple(constructor_configs)
        improver_ids = tuple(improver_configs)

        if (
            len(constructor_ids) != len(set(constructor_ids))
            or len(improver_ids) != len(set(improver_ids))
        ):
            raise ValueError('Duplicate arm IDs in objective group')

        manifest_path = directory / 'manifest.json'
        records_path = directory / 'records.jsonl'

        manifest = _read_json(manifest_path)

        if (
            manifest.get('status') != 'complete'
            or manifest.get('schema_version') != 1
        ):
            raise ValueError(
                f'Incomplete tuning run: {directory.name}'
            )

        if (
            manifest.get('benchmark_version') != 'v1'
            or manifest.get('benchmark_manifest_sha256')
            != benchmark_hash
        ):
            raise ValueError(
                'Benchmark provenance mismatch in tuning run'
            )

        if tuple(manifest.get('scenario_ids', ())) != development:
            raise ValueError(
                'Tuning run does not match registered development scenarios'
            )

        if (
            tuple(manifest.get('constructor_ids', ()))
            != constructor_ids
        ):
            raise ValueError(
                'Constructor axis mismatch in tuning run'
            )

        if (
            tuple(manifest.get('improver_ids', ()))
            != improver_ids
            or tuple(manifest.get('seeds', ())) != seeds
        ):
            raise ValueError(
                'Improver/seed axis mismatch in tuning run'
            )

        if manifest.get('comparison_objective') != comparison_objective:
            raise ValueError(
                'Comparison objective mismatch in tuning run'
            )

        try:
            raw = records_path.read_bytes()
        except OSError as exc:
            raise ValueError(
                'Missing tuning records artifact'
            ) from exc

        if manifest.get('records_sha256') != sha256(raw).hexdigest():
            raise ValueError('Tuning records hash mismatch')

        try:
            lines = raw.decode('utf-8').splitlines()
        except UnicodeError as exc:
            raise ValueError('Invalid UTF-8 tuning records') from exc

        expected = (
            len(development)
            * len(constructor_ids)
            * len(improver_ids)
            * len(seeds)
        )

        if (
            manifest.get('expected_trials') != expected
            or manifest.get('completed_trials') != expected
            or len(lines) != expected
        ):
            raise ValueError(
                'Tuning run trial cardinality mismatch'
            )

        index = 0
        run_ok = 0
        run_timeouts = 0

        for scenario_id in development:
            for constructor_id in constructor_ids:
                for improver_id in improver_ids:
                    for seed in seeds:
                        try:
                            row = json.loads(lines[index])
                        except json.JSONDecodeError as exc:
                            raise ValueError(
                                'Invalid tuning record JSONL'
                            ) from exc

                        expected_identity = (
                            scenario_id,
                            constructor_id,
                            improver_id,
                            seed,
                        )
                        actual_identity = (
                            row.get('scenario_id'),
                            row.get('constructor_id'),
                            row.get('improver_id'),
                            row.get('run_seed'),
                        )

                        if (
                            row.get('trial_index') != index
                            or actual_identity != expected_identity
                        ):
                            raise ValueError(
                                'Tuning record order/identity mismatch'
                            )

                        if scenario_id in holdout:
                            raise ValueError(
                                'Holdout scenario leaked into tuning execution'
                            )

                        if (
                            row.get('comparison_objective')
                            != comparison_objective
                        ):
                            raise ValueError(
                                'Record comparison objective mismatch'
                            )

                        if (
                            row.get('constructor_config_json')
                            != constructor_configs[constructor_id]
                        ):
                            raise ValueError(
                                'Record constructor provenance mismatch'
                            )

                        if (
                            row.get('improver_config_json')
                            != improver_configs[improver_id].get(seed)
                        ):
                            raise ValueError(
                                'Record improver provenance mismatch'
                            )

                        status = row.get('status')
                        if status not in _ALLOWED_STATUSES:
                            raise ValueError(
                                'Unknown tuning trial status'
                            )

                        wall = row.get('worker_wall_seconds')
                        if (
                            type(wall) not in (int, float)
                            or not isfinite(wall)
                            or wall < 0
                        ):
                            raise ValueError(
                                'Invalid worker wall time'
                            )

                        trial = row.get('trial')

                        if status == 'wall_timeout':
                            if trial is not None:
                                raise ValueError(
                                    'Timeout record must not fabricate a trial'
                                )
                        elif (
                            not isinstance(trial, dict)
                            or trial.get('status') != status
                        ):
                            raise ValueError(
                                'Returned trial status mismatch'
                            )

                        key = (
                            objective_id,
                            constructor_id,
                            improver_id,
                        )

                        candidate_id = candidate_by_key.get(key)
                        if candidate_id is None:
                            raise ValueError(
                                'Run cell has no registered tuning candidate'
                            )

                        observed[candidate_id].append(
                            (
                                scenario_id,
                                seed,
                                status,
                                float(wall),
                                trial,
                            )
                        )

                        run_ok += status == 'ok'
                        run_timeouts += status == 'wall_timeout'
                        index += 1

        if (
            manifest.get('successful_trials') != run_ok
            or manifest.get('timed_out_trials') != run_timeouts
        ):
            raise ValueError(
                'Tuning run status counts do not match durable records'
            )

        total_records += index

    performance_names = tuple(
        PerformanceVector.__dataclass_fields__
    )

    intended_per_candidate = len(development) * len(seeds)
    summaries = []
    trial_observations = []

    for (
        candidate_id,
        objective_id,
        constructor_id,
        improver_id,
    ) in ordered_candidates:
        rows = observed[candidate_id]

        if len(rows) != intended_per_candidate:
            raise ValueError(
                'Candidate does not have exactly one full paired '
                'development matrix'
            )

        ok = sum(
            status == 'ok'
            for _, _, status, _, _ in rows
        )
        timeouts = sum(
            status == 'wall_timeout'
            for _, _, status, _, _ in rows
        )
        failures = len(rows) - ok - timeouts
        walls = [
            wall
            for _, _, _, wall, _ in rows
        ]

        values = {
            name: []
            for name in performance_names
        }

        for scenario_id, seed, status, wall, trial in rows:
            frozen_performance = None

            if status == 'ok':
                performance = trial.get('final_performance')
                if not isinstance(performance, dict):
                    raise ValueError(
                        'Successful trial is missing final C1 performance'
                    )

                normalized_performance = {}

                for name in performance_names:
                    value = performance.get(name)

                    if value is None:
                        continue

                    if (
                        type(value) not in (int, float)
                        or not isfinite(value)
                    ):
                        raise ValueError(
                            'Invalid final C1 performance value'
                        )

                    numeric = float(value)
                    normalized_performance[name] = numeric
                    values[name].append(numeric)

                frozen_performance = MappingProxyType(
                    normalized_performance
                )

            trial_observations.append(
                TuningTrialObservation(
                    candidate_id=candidate_id,
                    scenario_id=scenario_id,
                    run_seed=seed,
                    status=status,
                    worker_wall_seconds=wall,
                    performance=frozen_performance,
                )
            )

        means = MappingProxyType({
            name: _mean(entries)
            for name, entries in values.items()
            if entries
        })

        counts = MappingProxyType({
            name: len(entries)
            for name, entries in values.items()
        })

        summaries.append(
            TuningCandidateSummary(
                candidate_id=candidate_id,
                objective_id=objective_id,
                constructor_id=constructor_id,
                improver_id=improver_id,
                intended_trials=len(rows),
                ok_trials=ok,
                timed_out_trials=timeouts,
                failed_trials=failures,
                ok_rate=ok / len(rows),
                timeout_rate=timeouts / len(rows),
                mean_worker_wall_seconds=_mean(walls),
                performance_means=means,
                performance_observation_counts=counts,
            )
        )

    if total_records != plan.get('expected_trials'):
        raise ValueError(
            'Study completed record count differs from registered '
            'expected_trials'
        )

    if len(summaries) != plan.get('candidate_count'):
        raise ValueError(
            'Candidate count differs from registered study'
        )

    return TuningStudyResults(
        output_root=output_root,
        benchmark_manifest_sha256=benchmark_hash,
        development_scenario_ids=development,
        holdout_scenario_ids=holdout,
        seeds=seeds,
        candidate_summaries=tuple(summaries),
        trial_observations=tuple(trial_observations),
        expected_trials=plan['expected_trials'],
        completed_trials=total_records,
    )
