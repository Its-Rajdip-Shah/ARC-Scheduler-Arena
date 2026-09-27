"""C7.1: pure, bounded planning and exclusive durable registration."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, fields, is_dataclass, replace
from enum import Enum
from datetime import date
from hashlib import sha256
from itertools import product
import json
from math import isfinite, prod
import os
from pathlib import Path
from types import MappingProxyType

from arena.algorithms import (EarliestFeasible, PressureGreedy, AggressiveEarlierGreedy,
                              StableRiskGreedy, HybridCostGreedy)
from arena.experiments.paired import (ConstructorArm, ImproverArm, Engine, WorkloadCase,
                                     _ENGINE_TYPES, _normalize, _dump, _config_json,
                                     _identifier, _prepare)
from arena.experiments.v1_runner import V1RunConfig
from arena.scheduling.domain import ScheduleProblem
from arena.scheduling.registry import SchedulingAlgorithm
from arena.search import PlanObjectiveConfig

_BENCHMARK = Path(__file__).resolve().parents[1] / 'benchmarks' / 'v1'
_CONSTRUCTORS = (EarliestFeasible, PressureGreedy, AggressiveEarlierGreedy,
                 StableRiskGreedy, HybridCostGreedy)


@dataclass(frozen=True, slots=True)
class TuningAxis:
    path: str
    values: tuple[object, ...]


@dataclass(frozen=True, slots=True)
class ConstructorSweep:
    arm_id: str
    algorithm: SchedulingAlgorithm
    axes: tuple[TuningAxis, ...]


@dataclass(frozen=True, slots=True)
class ImproverSweep:
    arm_id: str
    engine: Engine | None
    axes: tuple[TuningAxis, ...]


@dataclass(frozen=True, slots=True)
class TuningStudySpec:
    objective: PlanObjectiveConfig
    objective_axes: tuple[TuningAxis, ...]
    constructors: tuple[ConstructorSweep, ...]
    improvers: tuple[ImproverSweep, ...]
    seeds: tuple[int, ...]
    split_seed: int
    development_design_count: int
    trial_wall_seconds: float
    max_candidates: int
    max_trials: int
    output_root: Path


@dataclass(frozen=True, slots=True)
class TuningCandidate:
    candidate_id: str
    objective_id: str
    constructor: ConstructorArm
    improver: ImproverArm
    comparison_objective: PlanObjectiveConfig


@dataclass(frozen=True, slots=True)
class TuningStudyPlan:
    spec: TuningStudySpec
    benchmark_manifest_sha256: str
    development_scenario_ids: tuple[str, ...]
    holdout_scenario_ids: tuple[str, ...]
    candidates: tuple[TuningCandidate, ...]
    run_configs: tuple[V1RunConfig, ...]
    expected_trials: int


def _digest(payload):
    return sha256(payload.encode('utf-8')).hexdigest()


def _split(spec):
    raw = (_BENCHMARK / 'manifest.json').read_bytes()
    manifest = json.loads(raw)
    workloads = json.loads((_BENCHMARK / 'workloads.json').read_text(encoding='utf-8'))
    if manifest['benchmark_version'] != 'v1' or manifest['status'] != 'frozen':
        raise ValueError('Expected frozen Benchmark V1')
    ids = manifest['scenario_ids']
    metadata = [row['metadata'] for row in workloads]
    if ([row['scenario_id'] for row in metadata] != ids or len(ids) != 118
            or len(set(ids)) != len(ids)):
        raise ValueError('Frozen scenario IDs must match exactly, without duplicates')
    designs = {}
    for row in metadata:
        design, replicate = row['design_index'], row['replicate']
        if type(design) is not int or type(replicate) is not int:
            raise ValueError('Design and replicate identities must be exact integers')
        designs.setdefault(design, []).append(replicate)
    if len(designs) != 59 or any(len(v) != 2 or len(set(v)) != 2 for v in designs.values()):
        raise ValueError('Expected 59 designs with two distinct replicates each')
    if type(spec.split_seed) is not int:
        raise ValueError('split_seed must be an exact integer')
    count = spec.development_design_count
    if type(count) is not int or not 1 <= count < len(designs):
        raise ValueError('development_design_count must leave both partitions nonempty')
    ordered = sorted(designs, key=lambda d: (sha256(f'{spec.split_seed}:{d}'.encode()).digest(), d))
    development = set(ordered[:count])
    return (sha256(raw).hexdigest(),
            tuple(row['scenario_id'] for row in metadata if row['design_index'] in development),
            tuple(row['scenario_id'] for row in metadata if row['design_index'] not in development))


def _field(value, name):
    if (not is_dataclass(value) or isinstance(value, type)
            or not value.__dataclass_params__.frozen
            or name not in {f.name for f in fields(value)}):
        raise ValueError(f'Axis must traverse declared frozen dataclass fields: {name}')
    return getattr(value, name)  # name was checked against declared fields above


def _axes(base, axes, *, improver=False):
    if not isinstance(axes, tuple):
        raise TypeError('axes must be a tuple')
    seen = set()
    for axis in axes:
        if not isinstance(axis, TuningAxis) or not isinstance(axis.path, str):
            raise TypeError('Expected TuningAxis with a string path')
        parts = axis.path.split('.')
        if 'seed' in parts or (improver and 'objective' in parts):
            raise ValueError('Seed and improver objective axes are reserved')
        if axis.path in seen:
            raise ValueError('Duplicate axis path')
        seen.add(axis.path)
        leaf = base
        for part in parts:
            leaf = _field(leaf, part)
        if not isinstance(axis.values, tuple) or not axis.values:
            raise ValueError('Axis values must be a nonempty tuple')
        normalized = [_dump(_normalize(v)) for v in axis.values]
        if len(set(normalized)) != len(normalized):
            raise ValueError('Duplicate normalized axis values')
        # Numeric costs in C2 historically accept bool; tuning must not confuse
        # boolean switches with numeric parameters.
        if type(leaf) in (int, float) and any(type(v) is bool for v in axis.values):
            raise ValueError('Boolean is not a numeric axis value')
    return prod(len(axis.values) for axis in axes)


def _replace_path(base, parts, value):
    old = _field(base, parts[0])
    replacement = value if len(parts) == 1 else _replace_path(old, parts[1:], value)
    return replace(base, **{parts[0]: replacement})


def _snapshot_value(value):
    """Detach accepted axis values from caller-owned mutable containers."""
    _normalize(value)
    if isinstance(value, Enum):
        return value
    if is_dataclass(value) and not isinstance(value, type):
        return replace(value, **{
            field.name: _snapshot_value(getattr(value, field.name))
            for field in fields(value)
        })
    if isinstance(value, Mapping):
        return MappingProxyType({
            _snapshot_value(key): _snapshot_value(entry)
            for key, entry in value.items()
        })
    if isinstance(value, (tuple, list)):
        return tuple(_snapshot_value(entry) for entry in value)
    if isinstance(value, frozenset):
        return frozenset(_snapshot_value(entry) for entry in value)
    return value


def _snapshot_axes(axes):
    if not isinstance(axes, tuple):
        raise TypeError('axes must be a tuple')
    result = []
    for axis in axes:
        if not isinstance(axis, TuningAxis):
            raise TypeError('Expected TuningAxis')
        if not isinstance(axis.values, tuple):
            raise ValueError('Axis values must be a tuple')
        result.append(replace(
            axis, values=tuple(_snapshot_value(value) for value in axis.values)
        ))
    return tuple(result)


def _snapshot_spec(spec):
    constructors = []
    for sweep in spec.constructors:
        if not isinstance(sweep, ConstructorSweep):
            raise TypeError('Invalid constructor sweep type')
        constructors.append(replace(sweep, axes=_snapshot_axes(sweep.axes)))
    improvers = []
    for sweep in spec.improvers:
        if not isinstance(sweep, ImproverSweep):
            raise TypeError('Invalid improver sweep type')
        improvers.append(replace(sweep, axes=_snapshot_axes(sweep.axes)))
    return replace(
        spec,
        objective_axes=_snapshot_axes(spec.objective_axes),
        constructors=tuple(constructors),
        improvers=tuple(improvers),
    )


def _variants(base, axes):
    for values in product(*(axis.values for axis in axes)):
        result = base
        for axis, value in zip(axes, values):
            result = _replace_path(result, axis.path.split('.'), value)
        _normalize(result)
        yield result


def _claim(seen, identifier, payload):
    if identifier in seen:
        if seen[identifier] != payload:
            raise ValueError('SHA-256 identity collision between unequal payloads')
        raise ValueError('Duplicate effective configuration identity')
    seen[identifier] = payload


def _probe():
    return WorkloadCase('tuning-preflight', 'benchmark_v1', ScheduleProblem(date.min, (), (), {}))


def plan_tuning_study(spec: TuningStudySpec) -> TuningStudyPlan:
    """Validate and enumerate development-only grids without running scheduling."""
    if not isinstance(spec, TuningStudySpec):
        raise TypeError('Expected TuningStudySpec')
    if not isinstance(spec.output_root, Path):
        raise TypeError('output_root must be a Path')
    if os.path.lexists(spec.output_root):
        raise FileExistsError(spec.output_root)
    for name in ('constructors', 'improvers', 'seeds'):
        if not isinstance(getattr(spec, name), tuple) or not getattr(spec, name):
            raise ValueError(f'{name} must be a nonempty tuple')
    if any(type(seed) is not int for seed in spec.seeds) or len(set(spec.seeds)) != len(spec.seeds):
        raise ValueError('Seeds must be unique exact integers')
    if (type(spec.trial_wall_seconds) not in (int, float)
            or not isfinite(spec.trial_wall_seconds) or spec.trial_wall_seconds <= 0):
        raise ValueError('trial_wall_seconds must be finite and positive')
    for name in ('max_candidates', 'max_trials'):
        if type(getattr(spec, name)) is not int or getattr(spec, name) <= 0:
            raise ValueError(f'{name} must be an exact positive integer')
    if type(spec.objective) is not PlanObjectiveConfig:
        raise TypeError('Expected PlanObjectiveConfig')
    spec = _snapshot_spec(spec)
    objective_count = _axes(spec.objective, spec.objective_axes)
    counts = []
    for sweeps, cls, attribute, accepted in (
        (spec.constructors, ConstructorSweep, 'algorithm', _CONSTRUCTORS),
        (spec.improvers, ImproverSweep, 'engine', _ENGINE_TYPES),
    ):
        ids, count = set(), 0
        for sweep in sweeps:
            if not isinstance(sweep, cls):
                raise TypeError('Invalid sweep type')
            _identifier(sweep.arm_id, 'sweep arm_id')
            if sweep.arm_id in ids:
                raise ValueError('Duplicate sweep arm_id')
            ids.add(sweep.arm_id)
            template = getattr(sweep, attribute)
            if type(template) not in accepted and not (attribute == 'engine' and template is None):
                raise TypeError('Unsupported template class')
            base = None if template is None or type(template) is EarliestFeasible else template.config
            if base is None and sweep.axes:
                raise ValueError('Configless templates must have zero axes')
            count += _axes(base, sweep.axes, improver=attribute == 'engine')
        counts.append(count)
    manifest_hash, development, holdout = _split(spec)
    candidate_count = objective_count * counts[0] * counts[1]
    expected_trials = candidate_count * len(development) * len(spec.seeds)
    if candidate_count > spec.max_candidates or expected_trials > spec.max_trials:
        raise ValueError('Study cardinality exceeds explicit limits')

    constructors, constructor_ids = [], {}
    for sweep in spec.constructors:
        template = sweep.algorithm
        base = None if type(template) is EarliestFeasible else template.config
        for config in _variants(base, sweep.axes):
            algorithm = type(template)() if base is None else type(template)(config)
            payload = _config_json(algorithm)
            arm_id = sweep.arm_id + '_' + _digest(payload)
            _claim(constructor_ids, arm_id, payload)
            constructors.append(ConstructorArm(arm_id, algorithm))
    constructors = tuple(constructors)
    candidates, runs, objective_ids, candidate_ids = [], [], {}, {}
    probe = _probe()
    for objective in _variants(spec.objective, spec.objective_axes):
        payload = _dump(_normalize(objective))
        objective_id = _digest(payload)
        _claim(objective_ids, objective_id, payload)
        improvers, improver_ids = [], {}
        for sweep in spec.improvers:
            template = sweep.engine
            base = None if template is None else template.config
            for config in _variants(base, sweep.axes):
                engine = None if template is None else type(template)(replace(config, objective=objective))
                # Hash all effective per-run configurations; the unused template
                # seed must not affect an experimental identity.
                effective = [_prepare(probe, constructors[0], ImproverArm('probe', engine), seed, objective)[2]
                             for seed in spec.seeds]
                payload = _dump(effective)
                arm_id = sweep.arm_id + '_' + _digest(payload)
                _claim(improver_ids, arm_id, payload)
                improvers.append(ImproverArm(arm_id, engine))
        improvers = tuple(improvers)
        for constructor in constructors:
            for improver in improvers:
                configs = [_prepare(probe, constructor, improver, seed, objective) for seed in spec.seeds]
                payload = _dump(dict(objective_id=objective_id,
                                     constructor_id=constructor.arm_id,
                                     constructor_config_json=configs[0][1],
                                     improver_id=improver.arm_id,
                                     improver_config_json=[row[2] for row in configs]))
                candidate_id = _digest(payload)
                _claim(candidate_ids, candidate_id, payload)
                candidates.append(TuningCandidate(candidate_id, objective_id, constructor, improver, objective))
        runs.append(V1RunConfig(development, constructors, improvers, spec.seeds, objective,
                                spec.trial_wall_seconds, spec.output_root / ('objective_' + objective_id)))
    return TuningStudyPlan(spec, manifest_hash, development, holdout, tuple(candidates), tuple(runs), expected_trials)


def _artifact(plan):
    spec = plan.spec
    def axes(values):
        return [dict(path=a.path, values=[_normalize(v) for v in a.values]) for a in values]
    groups = []
    for run in plan.run_configs:
        groups.append(dict(objective_id=_digest(_dump(_normalize(run.comparison_objective))),
                           comparison_objective=_normalize(run.comparison_objective),
                           output_directory=run.output_dir.name,
                           constructors=[dict(arm_id=c.arm_id, config_json=_config_json(c.algorithm))
                                         for c in run.constructors],
                           improvers=[dict(arm_id=i.arm_id, effective_configs=[
                               dict(run_seed=seed, config_json=_prepare(_probe(), run.constructors[0], i,
                                    seed, run.comparison_objective)[2]) for seed in spec.seeds])
                                      for i in run.improvers]))
    return dict(schema_version=1, benchmark_version='v1',
                benchmark_manifest_sha256=plan.benchmark_manifest_sha256,
                split_seed=spec.split_seed, development_design_count=spec.development_design_count,
                holdout_design_count=59 - spec.development_design_count, design_count=59,
                development_scenario_ids=plan.development_scenario_ids,
                holdout_scenario_ids=plan.holdout_scenario_ids,
                objective=_normalize(spec.objective), objective_axes=axes(spec.objective_axes),
                constructors=[dict(arm_id=s.arm_id, config_json=_config_json(s.algorithm), axes=axes(s.axes))
                              for s in spec.constructors],
                improvers=[dict(arm_id=s.arm_id, config_json=None if s.engine is None else _config_json(s.engine),
                                axes=axes(s.axes)) for s in spec.improvers],
                seeds=spec.seeds, trial_wall_seconds=spec.trial_wall_seconds,
                objective_groups=groups,
                candidates=[dict(candidate_id=c.candidate_id, objective_id=c.objective_id,
                                 constructor_id=c.constructor.arm_id, improver_id=c.improver.arm_id)
                            for c in plan.candidates],
                max_candidates=spec.max_candidates, max_trials=spec.max_trials,
                candidate_count=len(plan.candidates), expected_trials=plan.expected_trials)


def write_tuning_plan(plan: TuningStudyPlan) -> Path:
    """Exclusively register a strict JSON plan; serialization precedes creation."""
    root = plan.spec.output_root
    if os.path.lexists(root):
        raise FileExistsError(root)
    encoded = _dump(_artifact(plan)) + '\n'
    root.mkdir()
    path = root / 'study_plan.json'
    try:
        with path.open('x', encoding='utf-8') as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        for directory in (root, root.parent):
            fd = os.open(directory, os.O_RDONLY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
    except BaseException:
        path.unlink(missing_ok=True)
        root.rmdir()
        raise
    return path
