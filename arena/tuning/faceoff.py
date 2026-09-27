"""C8 untouched-holdout face-off infrastructure."""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from hashlib import sha256
import json
from math import isfinite
import os
from pathlib import Path
from types import MappingProxyType

from arena.evaluation.performance import PerformanceVector
from arena.experiments.paired import (
    WorkloadCase,
    _config_json,
    _normalize,
    _prepare,
)
from arena.experiments.parallel_v1_runner import (
    run_v1_experiment_parallel,
)
from arena.experiments.v1_runner import (
    V1RunConfig,
)
from arena.scheduling.domain import (
    ScheduleProblem,
)

from .contestants import (
    _semantic_fingerprint,
)
from .execution import (
    TuningCandidateSummary,
    TuningStudyResults,
    TuningTrialObservation,
    _ALLOWED_STATUSES,
)
from .study import (
    TuningStudyPlan,
)


C8_FACE_OFF_SEEDS = (
    1801,
    1802,
    1803,
)

C8_TRIAL_WALL_SECONDS = 45.0


@dataclass(frozen=True, slots=True)
class C8CandidateLink:
    source_candidate_id: str
    execution_candidate_id: str
    label: str
    semantic_fingerprint: str
    witness_metrics: tuple[str, ...]
    objective_id: str
    constructor_arm_id: str
    improver_arm_id: str


@dataclass(frozen=True, slots=True)
class C8FaceoffPlan:
    benchmark_manifest_sha256: str
    development_scenario_ids: tuple[str, ...]
    holdout_scenario_ids: tuple[str, ...]
    seeds: tuple[int, ...]
    trial_wall_seconds: float
    candidate_links: tuple[
        C8CandidateLink,
        ...
    ]
    run_configs: tuple[
        V1RunConfig,
        ...
    ]
    expected_trials: int
    output_root: Path


def _probe() -> WorkloadCase:
    return WorkloadCase(
        'c8-preflight',
        'benchmark_v1',
        ScheduleProblem(
            date.min,
            (),
            (),
            {},
        ),
    )


def _canonical_json(value) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(',', ':'),
        ensure_ascii=True,
        allow_nan=False,
    )


def _faceoff_artifact(
    plan: C8FaceoffPlan,
) -> dict:
    probe = _probe()

    groups = []

    for run in plan.run_configs:
        constructor = run.constructors[0]

        groups.append({
            'output_directory':
                run.output_dir.name,
            'scenario_ids':
                list(run.scenario_ids),
            'seeds':
                list(run.seeds),
            'comparison_objective':
                _normalize(
                    run.comparison_objective
                ),
            'constructor': {
                'arm_id':
                    constructor.arm_id,
                'config_json':
                    _config_json(
                        constructor.algorithm
                    ),
            },
            'improvers': [
                {
                    'arm_id':
                        improver.arm_id,
                    'effective_configs': [
                        {
                            'run_seed':
                                seed,
                            'config_json':
                                _prepare(
                                    probe,
                                    constructor,
                                    improver,
                                    seed,
                                    run
                                    .comparison_objective,
                                )[2],
                        }
                        for seed in run.seeds
                    ],
                }
                for improver
                in run.improvers
            ],
        })

    return {
        'schema_version': 1,
        'stage': 'C8',
        'purpose':
            'untouched_holdout_faceoff',
        'benchmark_version': 'v1',
        'benchmark_manifest_sha256':
            plan.benchmark_manifest_sha256,
        'development_scenario_ids':
            list(
                plan.development_scenario_ids
            ),
        'holdout_scenario_ids':
            list(
                plan.holdout_scenario_ids
            ),
        'holdout_scenario_count':
            len(
                plan.holdout_scenario_ids
            ),
        'holdout_execution_authorized':
            True,
        'seeds':
            list(plan.seeds),
        'trial_wall_seconds':
            plan.trial_wall_seconds,
        'candidate_count':
            len(
                plan.candidate_links
            ),
        'expected_trials':
            plan.expected_trials,
        'selection_policy':
            'paired_C1_strict_Pareto_no_scalar',
        'winner_declared_by_protocol':
            False,
        'posthoc_budget_adaptation_allowed':
            False,
        'candidate_links': [
            {
                'source_candidate_id':
                    link.source_candidate_id,
                'execution_candidate_id':
                    link.execution_candidate_id,
                'label':
                    link.label,
                'semantic_fingerprint':
                    link.semantic_fingerprint,
                'witness_metrics':
                    list(
                        link.witness_metrics
                    ),
                'objective_id':
                    link.objective_id,
                'constructor_arm_id':
                    link.constructor_arm_id,
                'improver_arm_id':
                    link.improver_arm_id,
            }
            for link in plan.candidate_links
        ],
        'execution_groups':
            groups,
    }


def faceoff_plan_bytes(
    plan: C8FaceoffPlan,
) -> bytes:
    return (
        _canonical_json(
            _faceoff_artifact(plan)
        )
        + '\n'
    ).encode('utf-8')


def build_c8_faceoff_plan(
    source_full_plan: TuningStudyPlan,
    fresh_seed_full_plan: TuningStudyPlan,
    frozen_contestants: dict,
    *,
    output_root: Path,
) -> C8FaceoffPlan:
    if not isinstance(
        source_full_plan,
        TuningStudyPlan,
    ):
        raise TypeError(
            'source_full_plan must be TuningStudyPlan'
        )

    if not isinstance(
        fresh_seed_full_plan,
        TuningStudyPlan,
    ):
        raise TypeError(
            'fresh_seed_full_plan must be TuningStudyPlan'
        )

    if not isinstance(
        frozen_contestants,
        dict,
    ):
        raise TypeError(
            'frozen_contestants must be dict'
        )

    if not isinstance(
        output_root,
        Path,
    ):
        raise TypeError(
            'output_root must be Path'
        )

    if (
        source_full_plan
        .benchmark_manifest_sha256
        != fresh_seed_full_plan
        .benchmark_manifest_sha256
    ):
        raise ValueError(
            'Benchmark identity changed for C8'
        )

    if (
        source_full_plan
        .development_scenario_ids
        != fresh_seed_full_plan
        .development_scenario_ids
        or source_full_plan
        .holdout_scenario_ids
        != fresh_seed_full_plan
        .holdout_scenario_ids
    ):
        raise ValueError(
            'Benchmark split changed for C8'
        )

    if (
        tuple(
            fresh_seed_full_plan.spec.seeds
        )
        != C8_FACE_OFF_SEEDS
    ):
        raise ValueError(
            'C8 fresh seed set changed'
        )

    if (
        set(source_full_plan.spec.seeds)
        & set(C8_FACE_OFF_SEEDS)
    ):
        raise ValueError(
            'C8 seeds overlap C7 source seeds'
        )

    if (
        frozen_contestants.get('stage')
        != 'C7.6'
        or frozen_contestants.get(
            'purpose'
        )
        != 'freeze_C8_contestant_field'
    ):
        raise ValueError(
            'Expected frozen C7.6 contestant artifact'
        )

    if (
        frozen_contestants.get(
            'contestant_count'
        )
        != 6
    ):
        raise ValueError(
            'C8 requires exactly six '
            'frozen contestants'
        )

    if (
        frozen_contestants.get(
            'holdout_accessed'
        )
        is not False
    ):
        raise ValueError(
            'C7.6 artifact already reports '
            'holdout access'
        )

    frozen_holdout = tuple(
        frozen_contestants[
            'holdout_scenario_ids'
        ]
    )

    if (
        frozen_holdout
        != source_full_plan
        .holdout_scenario_ids
    ):
        raise ValueError(
            'Frozen C7.6 holdout identity changed'
        )

    source_by_id = {
        candidate.candidate_id:
            candidate
        for candidate
        in source_full_plan.candidates
    }

    fresh_by_fingerprint = {}

    for candidate in (
        fresh_seed_full_plan.candidates
    ):
        fingerprint = (
            _semantic_fingerprint(
                candidate
            )
        )

        if fingerprint in fresh_by_fingerprint:
            raise ValueError(
                'Fresh C8 plan contains duplicate '
                'semantic candidate configuration'
            )

        fresh_by_fingerprint[
            fingerprint
        ] = candidate

    links = []
    fresh_candidates = []

    for row in (
        frozen_contestants[
            'contestants'
        ]
    ):
        source_id = (
            row['source_candidate_id']
        )

        source = source_by_id.get(
            source_id
        )

        if source is None:
            raise ValueError(
                'Frozen C8 contestant is absent '
                'from frozen C7 source field'
            )

        fingerprint = (
            _semantic_fingerprint(
                source
            )
        )

        if (
            fingerprint
            != row[
                'semantic_fingerprint'
            ]
        ):
            raise ValueError(
                'Frozen contestant semantic '
                'fingerprint mismatch'
            )

        fresh = (
            fresh_by_fingerprint.get(
                fingerprint
            )
        )

        if fresh is None:
            raise ValueError(
                'Frozen contestant has no '
                'fresh-seed execution identity'
            )

        fresh_candidates.append(
            fresh
        )

        links.append(
            C8CandidateLink(
                source_candidate_id=
                    source_id,
                execution_candidate_id=
                    fresh.candidate_id,
                label=row['label'],
                semantic_fingerprint=
                    fingerprint,
                witness_metrics=tuple(
                    row[
                        'witness_metrics'
                    ]
                ),
                objective_id=
                    fresh.objective_id,
                constructor_arm_id=
                    fresh.constructor.arm_id,
                improver_arm_id=
                    fresh.improver.arm_id,
            )
        )

    if (
        len(links) != 6
        or len({
            link.source_candidate_id
            for link in links
        }) != 6
        or len({
            link.execution_candidate_id
            for link in links
        }) != 6
    ):
        raise ValueError(
            'C8 contestant mapping must be '
            'one-to-one over six candidates'
        )

    grouped = {}

    for candidate in fresh_candidates:
        key = (
            candidate.objective_id,
            candidate.constructor.arm_id,
        )

        grouped.setdefault(
            key,
            [],
        ).append(candidate)

    runs = []

    for index, candidates in enumerate(
        grouped.values(),
        start=1,
    ):
        first = candidates[0]

        if any(
            candidate.comparison_objective
            != first.comparison_objective
            for candidate in candidates
        ):
            raise ValueError(
                'C8 execution group objective mismatch'
            )

        runs.append(
            V1RunConfig(
                scenario_ids=
                    source_full_plan
                    .holdout_scenario_ids,
                constructors=(
                    first.constructor,
                ),
                improvers=tuple(
                    candidate.improver
                    for candidate
                    in candidates
                ),
                seeds=C8_FACE_OFF_SEEDS,
                comparison_objective=
                    first.comparison_objective,
                trial_wall_seconds=
                    C8_TRIAL_WALL_SECONDS,
                output_dir=(
                    output_root
                    / f'group_{index:02d}'
                ),
            )
        )

    expected_trials = (
        len(links)
        * len(
            source_full_plan
            .holdout_scenario_ids
        )
        * len(C8_FACE_OFF_SEEDS)
    )

    if expected_trials != 432:
        raise ValueError(
            'Frozen C8 cardinality must be 432'
        )

    represented = {
        (
            run.constructors[0].arm_id,
            improver.arm_id,
        )
        for run in runs
        for improver in run.improvers
    }

    expected_representation = {
        (
            candidate.constructor.arm_id,
            candidate.improver.arm_id,
        )
        for candidate in fresh_candidates
    }

    if represented != expected_representation:
        raise ValueError(
            'C8 execution groups do not exactly '
            'represent the frozen contestant field'
        )

    return C8FaceoffPlan(
        benchmark_manifest_sha256=
            source_full_plan
            .benchmark_manifest_sha256,
        development_scenario_ids=
            source_full_plan
            .development_scenario_ids,
        holdout_scenario_ids=
            source_full_plan
            .holdout_scenario_ids,
        seeds=C8_FACE_OFF_SEEDS,
        trial_wall_seconds=
            C8_TRIAL_WALL_SECONDS,
        candidate_links=tuple(links),
        run_configs=tuple(runs),
        expected_trials=expected_trials,
        output_root=output_root,
    )


def write_c8_faceoff_plan(
    plan: C8FaceoffPlan,
) -> Path:
    root = plan.output_root

    if os.path.lexists(root):
        raise FileExistsError(root)

    encoded = faceoff_plan_bytes(
        plan
    )

    root.mkdir(
        parents=True,
    )

    path = (
        root
        / 'c8_faceoff_plan.json'
    )

    try:
        with path.open(
            'xb'
        ) as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(
                stream.fileno()
            )
    except BaseException:
        path.unlink(
            missing_ok=True
        )
        root.rmdir()
        raise

    return path


def execute_c8_faceoff(
    plan: C8FaceoffPlan,
    *,
    max_workers: int,
    execution_environment_id: str,
    resume: bool = False,
):
    registration = (
        plan.output_root
        / 'c8_faceoff_plan.json'
    )

    if (
        not registration.is_file()
        or registration.read_bytes()
        != faceoff_plan_bytes(plan)
    ):
        raise ValueError(
            'C8 face-off must match its '
            'durably registered plan'
        )

    completed = 0
    timed_out = 0
    results = []

    for index, run in enumerate(
        plan.run_configs,
        start=1,
    ):
        existing = os.path.lexists(
            run.output_dir
        )

        print(
            '[ARC C8] '
            f'group {index}/'
            f'{len(plan.run_configs)} | '
            f'trials='
            f'{len(run.scenario_ids) * len(run.improvers) * len(run.seeds)} | '
            f'workers={max_workers} | '
            f'resume={existing and resume}',
            flush=True,
        )

        result = (
            run_v1_experiment_parallel(
                run,
                max_workers=max_workers,
                execution_environment_id=
                    execution_environment_id,
                resume=
                    existing and resume,
                progress_interval_seconds=
                    10.0,
            )
        )

        if (
            result.expected_trials
            != result.completed_trials
        ):
            raise RuntimeError(
                'Incomplete C8 execution group'
            )

        completed += (
            result.completed_trials
        )

        timed_out += (
            result.timed_out_trials
        )

        results.append(result)

    if completed != plan.expected_trials:
        raise RuntimeError(
            'C8 completed trial count differs '
            'from frozen plan'
        )

    return (
        tuple(results),
        completed,
        timed_out,
    )


def _read_json(
    path: Path,
) -> dict:
    try:
        return json.loads(
            path.read_text(
                encoding='utf-8'
            )
        )
    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
    ) as exc:
        raise ValueError(
            f'Invalid JSON artifact: {path}'
        ) from exc


def _mean(values):
    return sum(values) / len(values)


def load_c8_faceoff_results(
    plan: C8FaceoffPlan,
) -> TuningStudyResults:
    """Validate C8 artifacts and return an in-memory selection adapter.

    TuningStudyResults is reused only as the established paired-C1 selection
    container. Its development_scenario_ids field contains the C8 holdout
    scenarios in memory; no C8 artifact relabels holdout as development.
    """
    registration = (
        plan.output_root
        / 'c8_faceoff_plan.json'
    )

    if (
        not registration.is_file()
        or registration.read_bytes()
        != faceoff_plan_bytes(plan)
    ):
        raise ValueError(
            'C8 registration differs from supplied plan'
        )

    link_by_execution_key = {
        (
            link.objective_id,
            link.constructor_arm_id,
            link.improver_arm_id,
        ):
            link
        for link in plan.candidate_links
    }

    observed = {
        link.source_candidate_id: []
        for link in plan.candidate_links
    }

    total_records = 0

    for run in plan.run_configs:
        manifest = _read_json(
            run.output_dir
            / 'manifest.json'
        )

        records_path = (
            run.output_dir
            / 'records.jsonl'
        )

        try:
            raw = records_path.read_bytes()
        except OSError as exc:
            raise ValueError(
                'Missing C8 records'
            ) from exc

        if (
            manifest.get('status')
            != 'complete'
            or manifest.get(
                'schema_version'
            )
            != 1
            or manifest.get(
                'benchmark_version'
            )
            != 'v1'
        ):
            raise ValueError(
                'Incomplete/unsupported C8 group'
            )

        if (
            manifest.get(
                'benchmark_manifest_sha256'
            )
            != plan
            .benchmark_manifest_sha256
        ):
            raise ValueError(
                'C8 benchmark provenance mismatch'
            )

        if (
            tuple(
                manifest.get(
                    'scenario_ids',
                    (),
                )
            )
            != plan.holdout_scenario_ids
        ):
            raise ValueError(
                'C8 execution escaped frozen holdout'
            )

        if (
            tuple(
                manifest.get(
                    'seeds',
                    (),
                )
            )
            != plan.seeds
        ):
            raise ValueError(
                'C8 seed provenance mismatch'
            )

        if (
            manifest.get(
                'trial_wall_seconds'
            )
            != plan.trial_wall_seconds
        ):
            raise ValueError(
                'C8 wall contract changed'
            )

        if (
            manifest.get(
                'records_sha256'
            )
            != sha256(raw).hexdigest()
        ):
            raise ValueError(
                'C8 records hash mismatch'
            )

        constructor_ids = tuple(
            manifest.get(
                'constructor_ids',
                (),
            )
        )

        improver_ids = tuple(
            manifest.get(
                'improver_ids',
                (),
            )
        )

        if (
            constructor_ids
            != tuple(
                constructor.arm_id
                for constructor
                in run.constructors
            )
            or improver_ids
            != tuple(
                improver.arm_id
                for improver
                in run.improvers
            )
        ):
            raise ValueError(
                'C8 execution axis mismatch'
            )

        expected = (
            len(plan.holdout_scenario_ids)
            * len(run.constructors)
            * len(run.improvers)
            * len(plan.seeds)
        )

        try:
            lines = (
                raw.decode('utf-8')
                .splitlines()
            )
        except UnicodeError as exc:
            raise ValueError(
                'Invalid C8 records UTF-8'
            ) from exc

        if (
            manifest.get(
                'expected_trials'
            )
            != expected
            or manifest.get(
                'completed_trials'
            )
            != expected
            or len(lines)
            != expected
        ):
            raise ValueError(
                'C8 group cardinality mismatch'
            )

        index = 0
        run_ok = 0
        run_timeouts = 0

        for scenario_id in (
            plan.holdout_scenario_ids
        ):
            if (
                scenario_id
                in plan
                .development_scenario_ids
            ):
                raise ValueError(
                    'Development scenario leaked into C8'
                )

            for constructor in (
                run.constructors
            ):
                for improver in (
                    run.improvers
                ):
                    for seed in plan.seeds:
                        try:
                            row = json.loads(
                                lines[index]
                            )
                        except (
                            json.JSONDecodeError
                        ) as exc:
                            raise ValueError(
                                'Invalid C8 JSONL'
                            ) from exc

                        actual = (
                            row.get(
                                'scenario_id'
                            ),
                            row.get(
                                'constructor_id'
                            ),
                            row.get(
                                'improver_id'
                            ),
                            row.get(
                                'run_seed'
                            ),
                        )

                        expected_identity = (
                            scenario_id,
                            constructor.arm_id,
                            improver.arm_id,
                            seed,
                        )

                        if (
                            row.get(
                                'trial_index'
                            )
                            != index
                            or actual
                            != expected_identity
                        ):
                            raise ValueError(
                                'C8 record order/'
                                'identity mismatch'
                            )

                        if (
                            row.get(
                                'comparison_objective'
                            )
                            != _normalize(
                                run
                                .comparison_objective
                            )
                        ):
                            raise ValueError(
                                'C8 objective provenance mismatch'
                            )

                        status = row.get(
                            'status'
                        )

                        if (
                            status
                            not in _ALLOWED_STATUSES
                        ):
                            raise ValueError(
                                'Unknown C8 trial status'
                            )

                        wall = row.get(
                            'worker_wall_seconds'
                        )

                        if (
                            type(wall)
                            not in (int, float)
                            or not isfinite(wall)
                            or wall < 0
                        ):
                            raise ValueError(
                                'Invalid C8 wall time'
                            )

                        trial = row.get(
                            'trial'
                        )

                        if (
                            status
                            == 'wall_timeout'
                        ):
                            if trial is not None:
                                raise ValueError(
                                    'C8 timeout fabricated trial'
                                )
                        elif (
                            not isinstance(
                                trial,
                                dict,
                            )
                            or trial.get(
                                'status'
                            )
                            != status
                        ):
                            raise ValueError(
                                'C8 returned trial/status mismatch'
                            )

                        objective_id = next(
                            link.objective_id
                            for link
                            in plan.candidate_links
                            if (
                                link.constructor_arm_id
                                == constructor.arm_id
                                and link.improver_arm_id
                                == improver.arm_id
                            )
                        )

                        link = (
                            link_by_execution_key.get(
                                (
                                    objective_id,
                                    constructor.arm_id,
                                    improver.arm_id,
                                )
                            )
                        )

                        if link is None:
                            raise ValueError(
                                'C8 cell has no frozen contestant'
                            )

                        frozen_performance = None

                        if status == 'ok':
                            performance = (
                                trial.get(
                                    'final_performance'
                                )
                            )

                            if not isinstance(
                                performance,
                                dict,
                            ):
                                raise ValueError(
                                    'Successful C8 trial '
                                    'missing C1 performance'
                                )

                            normalized = {}

                            for name in (
                                PerformanceVector
                                .__dataclass_fields__
                            ):
                                value = (
                                    performance.get(
                                        name
                                    )
                                )

                                if value is None:
                                    continue

                                if (
                                    type(value)
                                    not in (
                                        int,
                                        float,
                                    )
                                    or not isfinite(
                                        value
                                    )
                                ):
                                    raise ValueError(
                                        'Invalid C8 C1 performance'
                                    )

                                normalized[
                                    name
                                ] = float(
                                    value
                                )

                            frozen_performance = (
                                MappingProxyType(
                                    normalized
                                )
                            )

                        observed[
                            link.source_candidate_id
                        ].append(
                            (
                                scenario_id,
                                seed,
                                status,
                                float(wall),
                                frozen_performance,
                            )
                        )

                        run_ok += (
                            status == 'ok'
                        )

                        run_timeouts += (
                            status
                            == 'wall_timeout'
                        )

                        index += 1

        if (
            manifest.get(
                'successful_trials'
            )
            != run_ok
            or manifest.get(
                'timed_out_trials'
            )
            != run_timeouts
        ):
            raise ValueError(
                'C8 manifest status counts mismatch'
            )

        total_records += index

    intended = (
        len(plan.holdout_scenario_ids)
        * len(plan.seeds)
    )

    summaries = []
    observations = []

    link_by_source = {
        link.source_candidate_id:
            link
        for link in plan.candidate_links
    }

    performance_names = tuple(
        PerformanceVector
        .__dataclass_fields__
    )

    for link in plan.candidate_links:
        rows = observed[
            link.source_candidate_id
        ]

        if len(rows) != intended:
            raise ValueError(
                'C8 contestant does not have '
                'a complete paired holdout matrix'
            )

        ok = sum(
            status == 'ok'
            for _, _, status, _, _
            in rows
        )

        timeouts = sum(
            status == 'wall_timeout'
            for _, _, status, _, _
            in rows
        )

        failures = (
            len(rows)
            - ok
            - timeouts
        )

        values = {
            name: []
            for name
            in performance_names
        }

        walls = []

        for (
            scenario_id,
            seed,
            status,
            wall,
            performance,
        ) in rows:
            walls.append(wall)

            if performance is not None:
                for (
                    name,
                    value,
                ) in performance.items():
                    values[name].append(
                        value
                    )

            observations.append(
                TuningTrialObservation(
                    candidate_id=
                        link.source_candidate_id,
                    scenario_id=
                        scenario_id,
                    run_seed=seed,
                    status=status,
                    worker_wall_seconds=
                        wall,
                    performance=
                        performance,
                )
            )

        summaries.append(
            TuningCandidateSummary(
                candidate_id=
                    link.source_candidate_id,
                objective_id=
                    link.objective_id,
                constructor_id=
                    link.constructor_arm_id,
                improver_id=
                    link.improver_arm_id,
                intended_trials=
                    intended,
                ok_trials=ok,
                timed_out_trials=
                    timeouts,
                failed_trials=
                    failures,
                ok_rate=
                    ok / intended,
                timeout_rate=
                    timeouts
                    / intended,
                mean_worker_wall_seconds=
                    _mean(walls),
                performance_means=
                    MappingProxyType({
                        name: _mean(entries)
                        for name, entries
                        in values.items()
                        if entries
                    }),
                performance_observation_counts=
                    MappingProxyType({
                        name: len(entries)
                        for name, entries
                        in values.items()
                    }),
            )
        )

    if (
        total_records
        != plan.expected_trials
    ):
        raise ValueError(
            'C8 total record cardinality mismatch'
        )

    return TuningStudyResults(
        output_root=
            plan.output_root,
        benchmark_manifest_sha256=
            plan.benchmark_manifest_sha256,
        development_scenario_ids=
            plan.holdout_scenario_ids,
        holdout_scenario_ids=
            plan.development_scenario_ids,
        seeds=plan.seeds,
        candidate_summaries=
            tuple(summaries),
        trial_observations=
            tuple(observations),
        expected_trials=
            plan.expected_trials,
        completed_trials=
            total_records,
    )


def c8_metric_means(
    results: TuningStudyResults,
    selection,
) -> dict[str, dict[str, float]]:
    observation_map = {
        (
            observation.candidate_id,
            observation.scenario_id,
            observation.run_seed,
        ):
            observation
        for observation
        in results.trial_observations
    }

    output = {
        candidate_id: {}
        for candidate_id
        in selection
        .eligible_candidate_ids
    }

    for metric in (
        selection.active_metrics
    ):
        cells = tuple(
            cell
            for cell in (
                selection
                .paired_quality_cells
            )
            if all(
                (
                    observation_map[
                        (
                            candidate_id,
                            cell[0],
                            cell[1],
                        )
                    ].performance
                    is not None
                )
                and (
                    metric.name
                    in observation_map[
                        (
                            candidate_id,
                            cell[0],
                            cell[1],
                        )
                    ].performance
                )
                for candidate_id
                in selection
                .eligible_candidate_ids
            )
        )

        if (
            len(cells)
            != selection
            .metric_observation_counts[
                metric.name
            ]
        ):
            raise ValueError(
                'C8 metric coverage differs from '
                'paired selector coverage'
            )

        for candidate_id in (
            selection
            .eligible_candidate_ids
        ):
            output[
                candidate_id
            ][metric.name] = _mean([
                observation_map[
                    (
                        candidate_id,
                        scenario_id,
                        seed,
                    )
                ].performance[
                    metric.name
                ]
                for scenario_id, seed
                in cells
            ])

    return output
