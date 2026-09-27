"""C6.2 contracts, including real V1 rollback and macOS spawn transport."""
from dataclasses import fields, replace
from datetime import date
from decimal import Decimal
import hashlib
import json
import multiprocessing
import os
import pickle
import subprocess
import sys
import time
from types import MappingProxyType, SimpleNamespace
from unittest.mock import patch

import pytest

from arena.algorithms import EarliestFeasible, PressureGreedy
from arena.algorithms.tests.test_greedy import config as greedy_config
from arena.evaluation.performance import PerformanceVector
from arena.experiments import ConstructorArm, ImproverArm, V1RunConfig, WorkloadCase, run_v1_experiment
from arena.experiments import paired, v1_runner as runner
from arena.scheduling.domain import Allocation, SchedulePlan
from arena.scheduling.validation import PlanViolation, ValidationResult
from arena.search.tests.helpers import TODAY, item, problem, objective


# These definitions must remain module-level and free of Django imports: spawn
# imports this module afresh, without inheriting parent monkeypatches.
class Slow:
    def solve(self, problem):
        time.sleep(30)
        return SchedulePlan(())


class Large:
    def solve(self, problem):
        assert 'django' not in sys.modules
        assert 'arena.benchmarks.reconstruct' not in sys.modules
        plan = EarliestFeasible().solve(problem)
        return replace(plan, diagnostics=(('large', 'x' * 2_000_000),))


class ObserverFailure:
    def solve(self, problem):
        # Deliberately malformed observer input; solve succeeds, validation fails.
        return SchedulePlan((object(),))


class AlgorithmFailure:
    def solve(self, problem):
        raise ValueError('constructor failed')


class Dies:
    def solve(self, problem):
        os._exit(7)


class Invalid:
    def solve(self, problem):
        return SchedulePlan((Allocation(987654321, TODAY, Decimal('12.30'), 1),))


def config(path, **changes):
    base = V1RunConfig(('G000-R0',), (ConstructorArm('pressure', PressureGreedy(greedy_config())),),
                       (ImproverArm('none', None),), (7, 8), objective(), 15.0, path)
    return replace(base, **changes)


def read_run(path):
    return (json.loads((path / 'manifest.json').read_text()),
            [json.loads(line) for line in (path / 'records.jsonl').read_text().splitlines()])


@pytest.mark.parametrize('changes', [
    {'scenario_ids': ()}, {'scenario_ids': ['G000-R0']}, {'scenario_ids': ('',)},
    {'scenario_ids': ('G000-R0', 'G000-R0')}, {'scenario_ids': ('missing',)},
    {'seeds': (1, 1)}, {'seeds': (True,)}, {'seeds': ()},
    {'constructors': ()}, {'constructors': (ConstructorArm('', EarliestFeasible()),)},
    {'improvers': (ImproverArm('x', None), ImproverArm('x', None))},
    {'trial_wall_seconds': True}, {'trial_wall_seconds': 0}, {'trial_wall_seconds': -1},
    {'trial_wall_seconds': float('inf')}, {'trial_wall_seconds': float('nan')},
    {'comparison_objective': None}, {'output_dir': 'string'},
])
def test_static_preflight(tmp_path, changes):
    from arena.benchmarks import reconstruct
    destination = tmp_path / 'run'
    with patch.object(reconstruct, 'reconstruct_scenario') as reconstruct_mock:
        with pytest.raises((TypeError, ValueError)):
            run_v1_experiment(config(destination, **changes))
        reconstruct_mock.assert_not_called()
    assert not destination.exists()


def test_existing_directory(tmp_path):
    from arena.benchmarks import reconstruct
    with patch.object(reconstruct, 'reconstruct_scenario') as reconstruct_mock:
        with pytest.raises(FileExistsError):
            run_v1_experiment(config(tmp_path))
        reconstruct_mock.assert_not_called()
    assert not list(tmp_path.iterdir())


@pytest.mark.django_db(transaction=True)
def test_real_v1_two_seeds_and_stable_rerun(tmp_path):
    from arena.benchmarks import reconstruct
    from django.contrib.auth import get_user_model
    from planning.models import PlanningItem, PlanningDependency, ProgressSegment, SchedulerAllocation
    models = (get_user_model(), PlanningItem, PlanningDependency, ProgressSegment, SchedulerAllocation)
    before = [m.objects.count() for m in models]
    extracted_ids = []
    original = reconstruct.reconstruct_scenario

    def capture(scenario):
        result = original(scenario)  # includes the real frozen Φ89 guard
        extracted_ids.append(tuple(i.item_id for i in result.problem.items))
        return result

    with patch.object(reconstruct, 'reconstruct_scenario', side_effect=capture) as rebuild, \
         patch.object(reconstruct, 'assert_phi89_matches', wraps=reconstruct.assert_phi89_matches) as guard:
        first = run_v1_experiment(config(tmp_path / 'first'))
        assert rebuild.call_count == guard.call_count == 1
        assert [m.objects.count() for m in models] == before
        # Force a sequence change even on SQLite, where rolled-back IDs can repeat.
        user = get_user_model().objects.create_user(email='sequence@local.test', password='test')
        sentinel = PlanningItem.objects.create(user=user, title='sequence', item_type='TASK', duration_category='UNDER_1_HOUR')
        second = run_v1_experiment(config(tmp_path / 'second'))
        assert rebuild.call_count == guard.call_count == 2
        sentinel.delete()
        user.delete()
    assert [m.objects.count() for m in models] == before
    assert extracted_ids[0] != extracted_ids[1]
    manifest, records = read_run(first.output_dir)
    other_manifest, other = read_run(second.output_dir)
    assert first.expected_trials == first.completed_trials == 2
    assert first.timed_out_trials == 0
    assert manifest['status'] == 'complete'
    assert manifest['expected_trials'] == manifest['completed_trials'] == 2
    assert manifest['timed_out_trials'] == 0
    assert [r['trial_index'] for r in records] == [0, 1]
    assert [r['run_seed'] for r in records] == [7, 8]
    assert manifest['records_sha256'] == hashlib.sha256(first.records_path.read_bytes()).hexdigest()
    assert manifest['benchmark_manifest_sha256'] == hashlib.sha256(reconstruct.MANIFEST.read_bytes()).hexdigest()
    metadata = manifest['scenarios'][0]
    assert len(metadata['frozen_features']) == 89
    assert len(metadata['stable_item_keys']) == len(extracted_ids[0])
    assert metadata == other_manifest['scenarios'][0]
    for record, rerun in zip(records, other):
        trial = record['trial']
        assert record['status'] == trial['status'] == 'ok'
        assert trial['initial_plan'] == rerun['trial']['initial_plan']
        assert set(trial['initial_performance']) == {f.name for f in fields(PerformanceVector)}
        assert trial['initial_objective']['total'] == sum(v for k, v in trial['initial_objective'].items() if k != 'total')
        assert trial['constructor_config_json'] == record['constructor_config_json']
        assert record['improver_config_json'] is None
        assert record['worker_wall_seconds'] >= trial['total_seconds']
        for allocation in trial['initial_plan']['allocations']:
            assert allocation['item_key'] in metadata['stable_item_keys']
            assert date.fromisoformat(allocation['scheduled_date'])
            assert isinstance(allocation['percentage'], str)
            assert Decimal(allocation['percentage']).is_finite()
            assert 'item_id' not in allocation


@pytest.fixture
def pure_extraction(monkeypatch):
    def extract(scenario):
        case = WorkloadCase(scenario.scenario_id, 'benchmark_v1', problem(item(42)), scenario.seed)
        metadata = dict(scenario_id=case.workload_id, workload_seed=case.workload_seed,
                        family=case.family, design_index=scenario.design_index,
                        replicate_index=scenario.replicate_index,
                        frozen_features=scenario.frozen_features, stable_item_keys=['item-42'])
        return case, {42: 'item-42'}, metadata
    monkeypatch.setattr(runner, '_extract', extract)


def test_timeout_then_next_cell(tmp_path, pure_extraction):
    before = {p.pid for p in multiprocessing.active_children()}
    result = run_v1_experiment(config(tmp_path / 'timeout', seeds=(1,), trial_wall_seconds=2.0,
        constructors=(ConstructorArm('slow', Slow()), ConstructorArm('fast', EarliestFeasible()))))
    manifest, records = read_run(result.output_dir)
    assert result.expected_trials == result.completed_trials == 2
    assert result.timed_out_trials == 1
    assert [r['status'] for r in records] == ['wall_timeout', 'ok']
    assert records[0]['trial'] is None and records[0]['worker_wall_seconds'] >= 2.0
    assert 'constructor_seconds' not in records[0] and 'initial_performance' not in records[0]
    assert manifest['status'] == 'complete'
    assert {p.pid for p in multiprocessing.active_children()} == before


@pytest.mark.parametrize('failure', [ObserverFailure, Dies])
def test_worker_failure_preserves_large_committed_record(tmp_path, pure_extraction, failure):
    destination = tmp_path / 'failure'
    with pytest.raises(runner.V1RunnerError, match='constructor=bad'):
        run_v1_experiment(config(destination, seeds=(1,), constructors=(
            ConstructorArm('large', Large()), ConstructorArm('bad', failure()))))
    manifest, records = read_run(destination)
    assert len(records) == manifest['completed_trials'] == 1
    assert records[0]['status'] == 'ok'
    assert len(records[0]['trial']['initial_plan']['diagnostics'][0][1]) == 2_000_000
    assert manifest['status'] == 'failed' and manifest['timed_out_trials'] == 0
    assert manifest['error']['type'] == 'V1RunnerError'


def test_constructor_error_is_completed_trial(tmp_path, pure_extraction):
    run_v1_experiment(config(tmp_path / 'error', seeds=(1,), constructors=(ConstructorArm('bad', AlgorithmFailure()),)))
    manifest, records = read_run(tmp_path / 'error')
    assert manifest['status'] == 'complete'
    assert records[0]['status'] == 'constructor_error'


@pytest.mark.django_db(transaction=True)
def test_drift_propagates_before_workers(tmp_path):
    from arena.benchmarks import reconstruct
    from planning.models import PlanningItem
    original = reconstruct.characterize_workload
    before = PlanningItem.objects.count()

    def drift(*args):
        result = dict(original(*args).to_mapping())
        result['item_count_total'] += 1
        return result

    with patch.object(reconstruct, 'characterize_workload', side_effect=drift), \
         patch.object(runner, '_isolated_trial') as worker:
        with pytest.raises(reconstruct.BenchmarkDriftError):
            run_v1_experiment(config(tmp_path / 'drift'))
        worker.assert_not_called()
    manifest, records = read_run(tmp_path / 'drift')
    assert manifest['status'] == 'failed' and not records
    assert PlanningItem.objects.count() == before


def test_invalid_plan_and_all_violation_categories(tmp_path, pure_extraction):
    run_v1_experiment(config(tmp_path / 'invalid', seeds=(1,), constructors=(ConstructorArm('invalid', Invalid()),)))
    _, records = read_run(tmp_path / 'invalid')
    trial = records[0]['trial']
    assert trial['status'] == 'constructor_invalid'
    allocation = trial['initial_plan']['allocations'][0]
    assert allocation['item_key'] is None and allocation['unknown_item'] is True
    assert allocation['percentage'] == '12.30'
    assert '987654321' not in json.dumps(trial)
    violation = PlanViolation('example', 42, 99, TODAY)
    result = runner._serialize(ValidationResult((violation,), (violation,), (violation,)), {42: 'stable'})
    for category in ('violations', 'infeasibilities', 'soft_violations'):
        assert result[category] == [dict(code='example', item_key='stable', related_item_key=None,
            unknown_related_item=True, scheduled_date=TODAY.isoformat())]


def test_mappingproxy_nested_roundtrip_and_effective_seed():
    # Exercise the same reducer used by multiprocessing, including nested configs.
    value = MappingProxyType({'nested': MappingProxyType({'capacity': 3}), 'objective': objective()})
    restored = pickle.loads(pickle.dumps(value))
    assert isinstance(restored, MappingProxyType)
    assert isinstance(restored['nested'], MappingProxyType)
    assert isinstance(restored['objective'].priority.multipliers, MappingProxyType)


def test_import_boundary():
    env = dict(os.environ)
    env.pop('DJANGO_SETTINGS_MODULE', None)
    subprocess.run([sys.executable, '-c', "import arena.experiments; import sys; "
                    "assert 'django' not in sys.modules; "
                    "assert 'arena.benchmarks.reconstruct' not in sys.modules"], env=env, check=True)


def test_effective_improver_provenance(tmp_path, pure_extraction):
    from arena.search import SimulatedAnnealing, SimulatedAnnealingConfig, NeighbourhoodConfig
    obj = objective()
    engine = SimulatedAnnealing(SimulatedAnnealingConfig(obj, NeighbourhoodConfig(2),
                                                       5, .9, .01, 99, 2, 10))
    configuration = config(tmp_path / 'effective', improvers=(ImproverArm('sa', engine),))
    run_v1_experiment(configuration)
    _, records = read_run(configuration.output_dir)
    assert engine.config.seed == 99
    for record in records:
        assert record['status'] == 'ok'
        effective = record['improver_config_json']
        assert effective == record['trial']['improver_config_json']
        assert json.loads(effective)['config']['fields']['seed'] == record['run_seed']


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize('mismatch', ['missing', 'duplicate'])
def test_stable_mapping_mismatch_rolls_back(tmp_path, mismatch):
    from arena.benchmarks import reconstruct
    from planning.models import PlanningItem
    original = reconstruct.reconstruct_scenario
    before = PlanningItem.objects.count()

    def mismatched(scenario):
        result = original(scenario)
        ids = {i.item_id for i in result.problem.items}
        key = next(k for k, v in result.materialized.by_key.items() if v.pk in ids)
        if mismatch == 'missing':
            del result.materialized.by_key[key]
        else:
            result.materialized.by_key['duplicate'] = result.materialized.by_key[key]
        return result

    with patch.object(reconstruct, 'reconstruct_scenario', side_effect=mismatched), \
         patch.object(runner, '_isolated_trial') as worker:
        with pytest.raises(ValueError, match='stable item mapping'):
            run_v1_experiment(config(tmp_path / mismatch))
        worker.assert_not_called()
    assert PlanningItem.objects.count() == before
    manifest, records = read_run(tmp_path / mismatch)
    assert manifest['status'] == 'failed' and records == []


def test_serialization_failure_preserves_committed_lines(tmp_path, pure_extraction):
    original = runner._serialize
    count = 0

    def corrupt(value, keys):
        nonlocal count
        if isinstance(value, paired.TrialRecord):
            count += 1
            if count == 2:
                value = replace(value, total_seconds=float('nan'))
        return original(value, keys)

    with patch.object(runner, '_serialize', side_effect=corrupt):
        with pytest.raises(ValueError, match='finite'):
            run_v1_experiment(config(tmp_path / 'serialize'))
    manifest, records = read_run(tmp_path / 'serialize')
    assert manifest['status'] == 'failed'
    assert manifest['completed_trials'] == len(records) == 1


def test_manifest_never_leads_durable_lines(tmp_path, pure_extraction):
    original = runner._manifest_write
    destination = tmp_path / 'durable'
    durable = []
    real_fsync = os.fsync

    def sync(fd):
        real_fsync(fd)
        records = destination / 'records.jsonl'
        if records.exists():
            durable[:] = records.read_text().splitlines()

    def write(path, manifest):
        assert manifest['completed_trials'] <= len(durable)
        return original(path, manifest)

    with patch.object(runner.os, 'fsync', side_effect=sync), \
         patch.object(runner, '_manifest_write', side_effect=write):
        run_v1_experiment(config(destination))
    assert len(durable) == 2


def test_each_scenario_preflights_all_cells_before_launch(tmp_path, pure_extraction):
    original = runner._prepare

    def prepare(case, constructor, improver, seed, objective):
        if case.workload_id != 'preflight' and seed == 8:
            raise ValueError('scenario preflight')
        return original(case, constructor, improver, seed, objective)

    with patch.object(runner, '_prepare', side_effect=prepare), \
         patch.object(runner, '_isolated_trial') as worker:
        with pytest.raises(ValueError, match='scenario preflight'):
            run_v1_experiment(config(tmp_path / 'preflight'))
        worker.assert_not_called()


def test_explicit_scenario_and_axis_order(tmp_path, pure_extraction):
    result = run_v1_experiment(config(tmp_path / 'order', scenario_ids=('G000-R1', 'G000-R0'),
        seeds=(8, 7), constructors=(ConstructorArm('a', EarliestFeasible()), ConstructorArm('b', EarliestFeasible())),
        improvers=(ImproverArm('x', None), ImproverArm('y', None))))
    manifest, records = read_run(result.output_dir)
    assert [(r['scenario_id'], r['constructor_id'], r['improver_id'], r['run_seed']) for r in records] == [
        (s, c, i, seed) for s in ('G000-R1', 'G000-R0') for c in ('a', 'b')
        for i in ('x', 'y') for seed in (8, 7)]
    assert result.completed_trials == result.expected_trials == 16
    assert [r['trial_index'] for r in records] == list(range(16))
    assert [s['scenario_id'] for s in manifest['scenarios']] == ['G000-R1', 'G000-R0']


def partial_worker(case, constructor, improver, seed, objective, sender):
    import struct
    os.write(sender.fileno(), struct.pack('!Q', 1_000_000) + b'partial')
    time.sleep(30)


def wrong_identity_worker(case, constructor, improver, seed, objective, sender):
    import struct
    record = paired.run_trial(case, constructor, improver, seed, objective)
    payload = pickle.dumps(('record', replace(record, workload_id='wrong')))
    pending = memoryview(struct.pack('!Q', len(payload)) + payload)
    while pending:
        pending = pending[os.write(sender.fileno(), pending):]
    sender.close()


def test_partial_message_deadline(tmp_path, pure_extraction, monkeypatch):
    monkeypatch.setattr(runner, '_worker', partial_worker)
    before = {p.pid for p in multiprocessing.active_children()}
    started = time.monotonic()
    result = run_v1_experiment(config(tmp_path / 'partial', seeds=(1,), trial_wall_seconds=1.0))
    assert result.timed_out_trials == 1
    assert time.monotonic() - started < 10
    assert {p.pid for p in multiprocessing.active_children()} == before


def test_worker_identity_is_checked(tmp_path, pure_extraction, monkeypatch):
    monkeypatch.setattr(runner, '_worker', wrong_identity_worker)
    with pytest.raises(runner.V1RunnerError, match='identity mismatch'):
        run_v1_experiment(config(tmp_path / 'identity', seeds=(1,)))
    manifest, records = read_run(tmp_path / 'identity')
    assert manifest['status'] == 'failed' and not records


@pytest.mark.parametrize('value', [object(), float('inf'), Decimal('NaN'), problem(item()),
                                  {'nested': problem(item())}])
def test_unsupported_artifact_values(value):
    with pytest.raises((TypeError, ValueError)):
        runner._serialize(value, {})
