"""Durable, spawn-isolated experiments on frozen Benchmark V1 (POSIX)."""
from __future__ import annotations

import copyreg
from collections.abc import Mapping
from dataclasses import dataclass, fields, is_dataclass
from datetime import date
import hashlib
import json
import math
import multiprocessing
import os
from pathlib import Path
import pickle
import select
import struct
import tempfile
import time
import traceback
from types import MappingProxyType

from .paired import (ConstructorArm, ImproverArm, TrialRecord, WorkloadCase,
                     _identifier, _normalize, _prepare, run_trial)
from arena.evaluation.performance import PerformanceVector
from arena.scheduling.domain import Allocation, SchedulePlan, ScheduleProblem
from arena.scheduling.validation import PlanViolation, ValidationResult
from arena.search.objective import PlanObjective, PlanObjectiveConfig


@dataclass(frozen=True, slots=True)
class V1RunConfig:
    scenario_ids: tuple[str, ...]
    constructors: tuple[ConstructorArm, ...]
    improvers: tuple[ImproverArm, ...]
    seeds: tuple[int, ...]
    comparison_objective: PlanObjectiveConfig
    trial_wall_seconds: float
    output_dir: Path


@dataclass(frozen=True, slots=True)
class V1RunResult:
    output_dir: Path
    scenario_count: int
    expected_trials: int
    completed_trials: int
    timed_out_trials: int
    manifest_path: Path
    records_path: Path


class V1RunnerError(RuntimeError):
    """An isolated worker failed outside C6.1's algorithm failure contract."""


def _restore_mappingproxy(mapping):
    return MappingProxyType(dict(mapping))


def _reduce_mappingproxy(mapping):
    return _restore_mappingproxy, (dict(mapping),)


copyreg.pickle(MappingProxyType, _reduce_mappingproxy)


def _worker(case, constructor, improver, seed, objective, sender):
    """Only pure inputs; no database or reconstruction imports in this module.

    Use our own length-prefixed byte stream on the POSIX Pipe descriptor so the
    parent can enforce a deadline even during a partially transmitted message.
    A blocking Connection.recv() after poll() would only bound the first byte.
    """
    try:
        try:
            payload = ('record', run_trial(case, constructor, improver, seed, objective))
            encoded = pickle.dumps(payload, protocol=pickle.HIGHEST_PROTOCOL)
        except BaseException as exc:
            encoded = pickle.dumps(('exception', type(exc).__name__, str(exc), traceback.format_exc()))
        pending = memoryview(struct.pack('!Q', len(encoded)) + encoded)
        while pending:
            pending = pending[os.write(sender.fileno(), pending):]
    finally:
        sender.close()


def _stop(process):
    if process.is_alive():
        process.terminate()
        process.join(0.2)
    if process.is_alive():
        process.kill()
    process.join()


def _isolated_trial(case, constructor, improver, seed, objective, budget):
    context = (f'scenario={case.workload_id}, constructor={constructor.arm_id}, '
               f'improver={improver.arm_id}, seed={seed}')
    ctx = multiprocessing.get_context('spawn')
    receiver, sender = ctx.Pipe(duplex=False)
    process = ctx.Process(target=_worker, args=(case, constructor, improver, seed, objective, sender))
    started = time.monotonic()
    try:
        process.start()
        sender.close()
        os.set_blocking(receiver.fileno(), False)
        data = bytearray()
        size = None
        while True:
            remaining = budget - (time.monotonic() - started)
            if remaining <= 0:
                _stop(process)
                return None, time.monotonic() - started
            ready, _, _ = select.select([receiver.fileno()], [], [], remaining)
            if not ready:
                continue
            chunk = os.read(receiver.fileno(), 65536)
            if not chunk:
                raise V1RunnerError(f'{context}: worker exited without a complete message')
            data.extend(chunk)
            if size is None and len(data) >= 8:
                size = struct.unpack('!Q', data[:8])[0]
            if size is not None and len(data) >= size + 8:
                if time.monotonic() - started >= budget:
                    _stop(process)
                    return None, time.monotonic() - started
                wall = time.monotonic() - started
                payload = pickle.loads(data[8:])
                # Drain before join: large records must never block on a full pipe.
                process.join(0.2)
                if payload[0] == 'exception':
                    raise V1RunnerError(f'{context}: {payload[1]}: {payload[2]}\n{payload[3]}')
                if payload[0] != 'record' or not isinstance(payload[1], TrialRecord):
                    raise V1RunnerError(f'{context}: invalid worker payload')
                record = payload[1]
                expected = (case.workload_id, case.family, case.workload_seed,
                            constructor.arm_id, improver.arm_id, seed)
                actual = (record.workload_id, record.family, record.workload_seed,
                          record.constructor_id, record.improver_id, record.run_seed)
                if actual != expected:
                    raise V1RunnerError(f'{context}: worker identity mismatch')
                return record, wall
    except V1RunnerError:
        raise
    except Exception as exc:
        raise V1RunnerError(f'{context}: {type(exc).__name__}: {exc}') from exc
    finally:
        sender.close()
        receiver.close()
        if process.pid is not None:
            _stop(process)

        # Python 3.14/Linux can briefly report a spawned process as
        # not alive before Process.close() observes the child as fully
        # reaped. Never let bookkeeping cleanup invalidate an otherwise
        # completed trial. _stop() above performs the authoritative join.
        if process.exitcode is not None:
            process.close()


def _serialize(value, keys):
    """Explicit artifact types; never traverse problems or ORM objects."""
    if isinstance(value, (Allocation, PlanViolation)):
        result = {}
        for field in fields(value):
            entry = getattr(value, field.name)
            if field.name in ('item_id', 'related_item_id'):
                name = field.name.replace('_id', '_key')
                result[name] = keys.get(entry)
                if entry is not None and entry not in keys:
                    result['unknown_item' if name == 'item_key' else 'unknown_related_item'] = True
            else:
                result[field.name] = _serialize(entry, keys)
        return result
    if isinstance(value, (TrialRecord, SchedulePlan, ValidationResult, PerformanceVector, PlanObjective)):
        result = {f.name: _serialize(getattr(value, f.name), keys) for f in fields(value)}
        if isinstance(value, PlanObjective):
            result['total'] = _normalize(value.total)
        return result
    if isinstance(value, (tuple, list)):
        return [_serialize(entry, keys) for entry in value]
    # Configuration normalization is deliberately NOT used for arbitrary dataclasses.
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise TypeError('Artifact mapping keys must be strings')
        return {key: _serialize(value[key], keys) for key in sorted(value)}
    if is_dataclass(value):
        raise TypeError('Unsupported artifact dataclass')
    return _normalize(value)


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _manifest_write(path, manifest):
    encoded = _json(manifest) + '\n'
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix='.manifest-', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        # Persist the directory entry as well as the file's contents.
        fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def _preflight(config):
    if not isinstance(config, V1RunConfig):
        raise TypeError('Expected V1RunConfig')
    for name, cls in (('scenario_ids', str), ('constructors', ConstructorArm),
                      ('improvers', ImproverArm), ('seeds', int)):
        values = getattr(config, name)
        if not isinstance(values, tuple) or not values:
            raise ValueError(f'{name} must be a nonempty tuple')
        if any((type(v) is not int if cls is int else not isinstance(v, cls)) for v in values):
            raise TypeError(f'Invalid {name} entries')
        ids = tuple(v.arm_id for v in values) if cls in (ConstructorArm, ImproverArm) else values
        if cls is not int:
            for identifier in ids:
                _identifier(identifier, name)
        if len(set(ids)) != len(ids):
            raise ValueError(f'Duplicate {name}')
    wall = config.trial_wall_seconds
    if type(wall) not in (int, float) or not math.isfinite(wall) or wall <= 0:
        raise ValueError('trial_wall_seconds must be finite and positive')
    if not isinstance(config.output_dir, Path):
        raise TypeError('output_dir must be a Path')
    if os.path.lexists(config.output_dir):
        raise FileExistsError(config.output_dir)
    # _prepare's configuration checks do not depend on workload contents.
    probe = WorkloadCase('preflight', 'benchmark_v1', ScheduleProblem(date.min, (), (), {}))
    for constructor in config.constructors:
        for improver in config.improvers:
            for seed in config.seeds:
                _prepare(probe, constructor, improver, seed, config.comparison_objective)


def _extract(scenario):
    from django.db import connections, transaction
    from arena.benchmarks.reconstruct import reconstruct_scenario

    try:
        with transaction.atomic():
            reconstructed = reconstruct_scenario(scenario)
            problem = reconstructed.problem
            ids = {item.item_id for item in problem.items}
            keys = {}
            for key, item in reconstructed.materialized.by_key.items():
                if item.pk in ids:
                    _identifier(key, 'stable item key')
                    if item.pk in keys or key in keys.values():
                        raise ValueError('Duplicate stable item mapping')
                    keys[item.pk] = key
            if set(keys) != ids:
                raise ValueError('Missing stable item mapping')
            metadata = dict(scenario_id=scenario.scenario_id, workload_seed=scenario.seed,
                            design_index=scenario.design_index, replicate_index=scenario.replicate_index,
                            family='benchmark_v1', frozen_features=_normalize(scenario.frozen_features),
                            stable_item_keys=sorted(keys.values()))
            transaction.set_rollback(True)
        return WorkloadCase(scenario.scenario_id, 'benchmark_v1', problem, scenario.seed), keys, metadata
    finally:
        connections.close_all()


def run_v1_experiment(config: V1RunConfig) -> V1RunResult:
    """Run an explicit V1 matrix; caller must initialize Django first."""
    _preflight(config)
    from arena.benchmarks.reconstruct import MANIFEST, load_v1_scenarios

    scenarios = {s.scenario_id: s for s in load_v1_scenarios()}
    for identifier in config.scenario_ids:
        if identifier not in scenarios:
            raise ValueError(f'Unknown Benchmark V1 scenario: {identifier}')
    expected = len(config.scenario_ids) * len(config.constructors) * len(config.improvers) * len(config.seeds)
    manifest = dict(schema_version=1, benchmark_version='v1', status='running',
                    scenario_ids=list(config.scenario_ids),
                    axis_order=['scenario', 'constructor', 'improver', 'seed'],
                    constructor_ids=[c.arm_id for c in config.constructors],
                    improver_ids=[i.arm_id for i in config.improvers], seeds=list(config.seeds),
                    comparison_objective=_normalize(config.comparison_objective),
                    trial_wall_seconds=config.trial_wall_seconds, expected_trials=expected,
                    completed_trials=0, successful_trials=0, timed_out_trials=0,
                    benchmark_manifest_sha256=hashlib.sha256(MANIFEST.read_bytes()).hexdigest(), scenarios=[])
    manifest_path = config.output_dir / 'manifest.json'
    records_path = config.output_dir / 'records.jsonl'
    config.output_dir.mkdir()  # exclusive ownership: never overwrite or resume
    try:
        _manifest_write(manifest_path, manifest)
        with records_path.open('x', encoding='utf-8') as stream:
            for identifier in config.scenario_ids:
                case, keys, metadata = _extract(scenarios[identifier])
                manifest['scenarios'].append(metadata)
                cells = []
                for constructor in config.constructors:
                    for improver in config.improvers:
                        for seed in config.seeds:
                            _, constructor_json, improver_json = _prepare(
                                case, constructor, improver, seed, config.comparison_objective)
                            cells.append((constructor, improver, seed, constructor_json, improver_json))
                _manifest_write(manifest_path, manifest)
                for constructor, improver, seed, constructor_json, improver_json in cells:
                    record, wall = _isolated_trial(case, constructor, improver, seed,
                                                  config.comparison_objective, config.trial_wall_seconds)
                    envelope = {k: v for k, v in metadata.items() if k not in ('frozen_features', 'stable_item_keys')}
                    envelope.update(trial_index=manifest['completed_trials'], constructor_id=constructor.arm_id,
                                    improver_id=improver.arm_id, run_seed=seed,
                                    constructor_config_json=constructor_json, improver_config_json=improver_json,
                                    comparison_objective=manifest['comparison_objective'],
                                    status='wall_timeout' if record is None else record.status,
                                    worker_wall_seconds=wall, trial=_serialize(record, keys))
                    stream.write(_json(envelope) + '\n')
                    stream.flush()
                    os.fsync(stream.fileno())
                    manifest['completed_trials'] += 1
                    manifest['timed_out_trials'] += record is None
                    manifest['successful_trials'] += record is not None and record.status == 'ok'
                    _manifest_write(manifest_path, manifest)
        if manifest['completed_trials'] != expected:
            raise V1RunnerError('Completed matrix size mismatch')
        manifest.update(status='complete', records_sha256=hashlib.sha256(records_path.read_bytes()).hexdigest())
        _manifest_write(manifest_path, manifest)
    except BaseException as exc:
        manifest.update(status='failed', error={'type': type(exc).__name__, 'message': str(exc)[:2000]})
        try:
            _manifest_write(manifest_path, manifest)
        except BaseException:
            pass  # preserve the original failure, including filesystem failures
        raise
    return V1RunResult(config.output_dir, len(config.scenario_ids), expected,
                       manifest['completed_trials'], manifest['timed_out_trials'], manifest_path, records_path)
