"""Paired core contracts, independent observations, and reproducibility."""
from dataclasses import FrozenInstanceError, dataclass, replace
from decimal import Decimal
import json
import os
import random
import subprocess
import sys
from types import MappingProxyType, SimpleNamespace
from unittest.mock import patch

import pytest

from arena.algorithms import EarliestFeasible, PressureGreedy
from arena.algorithms.tests.test_greedy import config
from arena.evaluation.performance import evaluate_plan
from arena.experiments import ConstructorArm, ImproverArm, WorkloadCase, run_grid, run_trial
from arena.experiments import paired
from arena.scheduling.domain import Allocation, SchedulePlan
from arena.scheduling.validation import validate_plan
from arena.search import (
    HillClimber, HillClimbConfig, ImprovementStrategy, NeighbourhoodConfig,
    VariableNeighbourhoodSearch, VariableNeighbourhoodConfig, VariableNeighbourhoodMode,
    SimulatedAnnealing, SimulatedAnnealingConfig, SearchState, score_state,
    LargeNeighbourhoodSearch, LargeNeighbourhoodConfig, DestroyOperator, RepairOperator,
    AdaptiveLargeNeighbourhoodSearch, AdaptiveLargeNeighbourhoodConfig, TabuSearch, TabuConfig,
)
from arena.search.tests.helpers import TODAY, DAY, item, problem, objective


def fixture():
    p = problem(item(1, priority_position=2, due_date=TODAY),
                item(2, priority_position=1, due_date=TODAY + 2 * DAY))
    obj = objective(priority=1, overload=10)
    ctor = ConstructorArm('pressure', PressureGreedy(config(priority=1, overload=10, horizon=2)))
    engine = HillClimber(HillClimbConfig(obj, NeighbourhoodConfig(2), ImprovementStrategy.FIRST, 10, 100))
    return WorkloadCase('two', 'hand', p, 42), ctor, ImproverArm('hc', engine), obj


class Fixed:
    name = 'fixed'

    def __init__(self, plan):
        self.plan = plan

    def solve(self, problem):
        return self.plan


def assert_no_final(record):
    assert all(getattr(record, 'final_' + field) is None
               for field in ('plan', 'validation', 'performance', 'objective'))


def test_hand_pair():
    case, ctor, arm, obj = fixture()
    records = run_grid([case], [ctor], [ImproverArm('none', None), arm], [7], obj)
    before, after = records
    assert before.status == after.status == 'ok'
    assert [r.scheduled_date for r in before.final_plan.allocations] == [TODAY, TODAY + DAY]
    assert [(r.item_id, r.scheduled_date) for r in after.final_plan.allocations] == [(2, TODAY), (1, TODAY + DAY)]
    assert before.initial_objective.total == before.final_objective.total == 3
    assert after.initial_objective.total == 3 and after.final_objective.total == 1
    assert before.final_performance.priority_inversion_count == 1
    assert after.final_performance.priority_inversion_count == 0
    assert before.final_performance.deadline_miss_count == 0
    assert after.final_performance.deadline_miss_count == 1
    assert before.final_performance.mean_start_delay_days == after.final_performance.mean_start_delay_days == .5
    assert before.final_performance.excess_session_count == after.final_performance.excess_session_count == 0
    for record in records:
        for prefix in ('initial', 'final'):
            plan = getattr(record, prefix + '_plan')
            validation = validate_plan(case.problem, plan)
            assert validation == getattr(record, prefix + '_validation')
            assert evaluate_plan(case.problem, plan, validation) == getattr(record, prefix + '_performance')
            assert score_state(SearchState.from_plan(case.problem, plan), obj) == getattr(record, prefix + '_objective')
        assert record.total_seconds >= record.constructor_seconds + record.improver_seconds >= 0
        assert not hasattr(record, '__dict__')
        with pytest.raises(FrozenInstanceError):
            record.status = 'changed'
    for field in ('plan', 'validation', 'performance', 'objective'):
        assert getattr(before, 'initial_' + field) is getattr(before, 'final_' + field)
    assert (before.iterations, before.evaluations, before.improver_seconds) == (0, 0, 0.0)
    assert before.termination_reason == 'no_improver' and before.improver_config_json is None


def test_invalid_constructor_and_validation_identity():
    case, _, arm, obj = fixture()
    plan = SchedulePlan(())
    with patch.object(HillClimber, 'improve_plan') as improve, \
         patch.object(paired, 'validate_plan', wraps=validate_plan) as validate, \
         patch.object(paired, 'evaluate_plan', wraps=evaluate_plan) as evaluate:
        record = run_trial(case, ConstructorArm('bad', Fixed(plan)), arm, 0, obj)
    assert record.status == 'constructor_invalid'
    assert record.initial_plan is plan
    assert record.initial_performance.hard_violation_count == 2
    assert record.initial_objective is None and record.improver_seconds is None
    assert validate.call_count == 1
    assert evaluate.call_args.args[2] is record.initial_validation
    improve.assert_not_called()
    assert_no_final(record)


@pytest.mark.parametrize('also_invalid', [False, True])
def test_infeasible_precedence(also_invalid):
    case, _, arm, obj = fixture()
    p = problem(item(1, anchor_date=TODAY), item(2, anchor_date=TODAY), edges=((1, 2),))
    plan = SchedulePlan((Allocation(1, TODAY, Decimal(100), 1),
                         Allocation(2, TODAY, Decimal(50 if also_invalid else 100), 2)))
    record = run_trial(replace(case, problem=p), ConstructorArm('fixed', Fixed(plan)), arm, 0, obj)
    assert record.status == ('constructor_invalid' if also_invalid else 'constructor_infeasible')
    assert record.initial_performance.canonical_infeasibility_count == 1
    assert_no_final(record)


def test_unsearchable():
    case, _, arm, obj = fixture()
    p = problem(item(duration_category='OVER_16_HOURS'))
    plan = SchedulePlan((Allocation(1, TODAY, Decimal(100), 1),))
    assert validate_plan(p, plan).is_valid
    record = run_trial(replace(case, problem=p), ConstructorArm('fixed', Fixed(plan)), arm, 0, obj)
    assert record.status == 'constructor_unsearchable'
    assert 'canonical session pieces' in record.error_message
    assert record.initial_performance is not None and record.initial_objective is None
    assert_no_final(record)


@pytest.mark.parametrize('mode', ['throws', 'wrong_type', 'initial', 'problem', 'objective'])
def test_improver_errors(mode):
    case, ctor, arm, obj = fixture()
    result = arm.engine.improve_plan(case.problem, ctor.algorithm.solve(case.problem))
    if mode == 'initial':
        result = replace(result, initial_state=result.final_state)
    elif mode == 'problem':
        result = replace(result, final_state=replace(result.final_state,
                         problem=replace(case.problem, overload_dates=frozenset({TODAY}))))
    elif mode == 'objective':
        result = replace(result, final_objective=replace(result.final_objective, timing=99))
    elif mode == 'wrong_type':
        result = object()
    with patch.object(HillClimber, 'improve_plan', side_effect=RuntimeError('search broke') if mode == 'throws' else None,
                      return_value=result):
        record = run_trial(case, ctor, arm, 0, obj)
    assert record.status == 'improver_error'
    assert record.error_type and record.error_message
    assert record.initial_objective.total == 3
    assert record.improver_seconds >= 0
    assert_no_final(record)


@pytest.mark.parametrize('value', [None, 3, RuntimeError('constructor broke')])
def test_constructor_errors(value):
    case, ctor, arm, obj = fixture()
    with patch.object(PressureGreedy, 'solve', side_effect=value if isinstance(value, Exception) else None,
                      return_value=value):
        record = run_trial(case, ctor, arm, 0, obj)
    assert record.status == 'constructor_error'
    assert record.initial_plan is record.initial_performance is record.initial_objective is None
    assert record.constructor_seconds >= 0 and record.total_seconds >= record.constructor_seconds
    assert_no_final(record)


def test_baseexception_propagates():
    case, ctor, arm, obj = fixture()
    with patch.object(PressureGreedy, 'solve', side_effect=KeyboardInterrupt), pytest.raises(KeyboardInterrupt):
        run_trial(case, ctor, arm, 0, obj)


def engines(obj):
    n = NeighbourhoodConfig(2)
    return [VariableNeighbourhoodSearch(VariableNeighbourhoodConfig(obj, n, mode, 20, 100, 99))
            for mode in VariableNeighbourhoodMode] + [
        SimulatedAnnealing(SimulatedAnnealingConfig(obj, n, 5, .9, .01, 99, 20, 100)),
        LargeNeighbourhoodSearch(LargeNeighbourhoodConfig(obj, 2, 1, tuple(DestroyOperator)[0],
                                 tuple(RepairOperator)[0], 20, 100, 99)),
        AdaptiveLargeNeighbourhoodSearch(AdaptiveLargeNeighbourhoodConfig(
            obj, 2, 1, 20, .5, 5, .9, .01, 3, 2, 1, 100, 99)),
        TabuSearch(TabuConfig(obj, n, 2, 20, 100))]


@pytest.mark.parametrize('index', range(6))
def test_seeded_repeat_and_immutable_arm(index):
    case, ctor, _, obj = fixture()
    engine = engines(obj)[index]
    arm = ImproverArm('search', engine)
    original = engine.config
    rng_before = random.getstate()
    a, b = [run_trial(case, ctor, arm, 4, obj) for _ in range(2)]
    c = run_trial(case, ctor, arm, 5, obj)
    assert a.status == b.status == c.status == 'ok'
    assert (a.final_plan, a.iterations, a.evaluations) == (b.final_plan, b.iterations, b.evaluations)
    assert engine.config is original and random.getstate() == rng_before
    if hasattr(original, 'seed'):
        assert original.seed == 99
        assert a.improver_config_json != c.improver_config_json
        assert json.loads(a.improver_config_json)['config']['fields']['seed'] == 4
    else:
        assert a.improver_config_json == c.improver_config_json


def test_grid_order_and_failed_cells():
    case, ctor, arm, obj = fixture()
    workloads = [case, replace(case, workload_id='other')]
    constructors = [ctor, ConstructorArm('bad', Fixed(None))]
    improvers = [arm, ImproverArm('none', None)]
    result = run_grid(workloads, constructors, improvers, [9, -1], obj)
    assert len(result) == 16
    assert [(r.workload_id, r.constructor_id, r.improver_id, r.run_seed) for r in result] == [
        (w.workload_id, c.arm_id, i.arm_id, s)
        for w in workloads for c in constructors for i in improvers for s in [9, -1]]
    assert sum(r.status == 'constructor_error' for r in result) == 8


@pytest.mark.parametrize('category', range(4))
@pytest.mark.parametrize('failure', ['empty', 'duplicate'])
def test_grid_rejects_before_running(category, failure):
    case, ctor, arm, obj = fixture()
    groups = [[case], [ctor], [arm], [0]]
    groups[category] = [] if failure == 'empty' else groups[category] * 2
    with patch.object(PressureGreedy, 'solve') as solve, pytest.raises(ValueError):
        run_grid(*groups, obj)
    solve.assert_not_called()


@pytest.mark.parametrize('failure', ['objective', 'iterations', 'evaluations', 'seed', 'workload_seed', 'id', 'family', 'engine', 'config'])
def test_entire_grid_preflight(failure):
    case, ctor, arm, obj = fixture()
    seeds = [0]
    if failure == 'objective':
        arm = replace(arm, engine=HillClimber(replace(arm.engine.config, objective=objective(timing=1))))
    elif failure in ('iterations', 'evaluations'):
        arm = replace(arm, engine=HillClimber(replace(arm.engine.config, **{'max_' + failure: None})))
    elif failure == 'seed':
        seeds.append(True)
    elif failure == 'workload_seed':
        case = replace(case, workload_seed=True)
    elif failure == 'id':
        case = replace(case, workload_id='')
    elif failure == 'family':
        case = replace(case, family='')
    elif failure == 'engine':
        arm = replace(arm, engine=SimpleNamespace(config=arm.engine.config))
    else:
        ctor = ConstructorArm('bad', SimpleNamespace(solve=lambda p: None, config=float('inf')))
    with patch.object(PressureGreedy, 'solve') as solve, pytest.raises((TypeError, ValueError)):
        run_grid([replace(fixture()[0], workload_id='first'), case], [ctor], [ImproverArm('none', None), arm], seeds, obj)
    solve.assert_not_called()


@pytest.mark.parametrize('target', ['evaluate_plan', 'score_state'])
def test_observer_error_surfaces_with_context(target):
    case, ctor, arm, obj = fixture()
    with patch.object(paired, target, side_effect=ValueError('bad weights')), pytest.raises(ValueError) as error:
        run_trial(case, ctor, arm, 0, obj)
    assert 'workload=two' in error.value.__notes__[0]
    assert 'constructor=pressure' in error.value.__notes__[0]


def test_provenance_normalization():
    @dataclass(frozen=True)
    class Settings:
        values: object
    values = {'date': TODAY, 'decimal': Decimal('1.20'), 'enum': ImprovementStrategy.FIRST,
              'set': frozenset({'b', 'a'}), 'seq': (None, True, 1, 1.5)}
    a = SimpleNamespace(config=Settings(MappingProxyType(values)))
    b = SimpleNamespace(config=Settings(dict(reversed(list(values.items())))))
    assert paired._config_json(a) == paired._config_json(b)
    data = json.loads(paired._config_json(a))
    assert data['config']['class'].endswith('Settings')
    assert data['config']['fields']['values']['decimal'] == '1.20'
    assert data['config']['fields']['values']['set'] == ['a', 'b']
    assert json.loads(paired._config_json(EarliestFeasible())) == {'class': 'arena.algorithms.earliest_feasible.EarliestFeasible'}
    case, ctor, _, obj = fixture()
    other = replace(ctor, algorithm=PressureGreedy(config(timing=4)))
    record = run_trial(case, other, ImproverArm('none', None), 0, obj)
    assert record.constructor_config_json == paired._config_json(other.algorithm)
    assert json.loads(record.constructor_config_json)['config']['fields']['timing']['fields']['weight'] == 4


@pytest.mark.parametrize('value', [float('nan'), float('inf'), Decimal('NaN'), Decimal('Infinity'), object(), {(1, 2): 'unsupported key'}, {1, 2}])
def test_bad_config_values(value):
    with pytest.raises((TypeError, ValueError)):
        paired._config_json(SimpleNamespace(config=value))


def test_import_boundaries():
    env = dict(os.environ)
    env.pop('DJANGO_SETTINGS_MODULE', None)
    subprocess.run([sys.executable, '-c', '''
import arena.search
import sys
assert 'arena.evaluation.performance' not in sys.modules
import arena.experiments
assert not any(k == 'django' or k.startswith('django.') for k in sys.modules)
assert 'arena.benchmarks.reconstruct' not in sys.modules
for name, module in list(sys.modules.items()):
    if name.startswith('arena.search'):
        assert 'evaluate_plan' not in vars(module)
        assert 'PerformanceVector' not in vars(module)
'''], env=env, check=True)


def test_mapping_integer_keys_and_collision():
    a = SimpleNamespace(config=MappingProxyType({2: 1, 1: 3}))
    b = SimpleNamespace(config={1: 3, 2: 1})
    assert paired._config_json(a) == paired._config_json(b)
    assert json.loads(paired._config_json(a))['config'] == {'1': 3, '2': 1}
    with pytest.raises(ValueError, match='collide'):
        paired._config_json(SimpleNamespace(config={1: 3, '1': 4}))


@pytest.mark.parametrize('field', ['max_iterations', 'max_evaluations'])
@pytest.mark.parametrize('value', [True, -1, 1.0, float('inf')])
def test_runner_rechecks_exact_limits(field, value):
    case, ctor, arm, obj = fixture()
    # Deliberately corrupt a frozen config to check the runner's own boundary.
    object.__setattr__(arm.engine.config, field, value)
    with patch.object(PressureGreedy, 'solve') as solve, pytest.raises(ValueError, match=field):
        run_trial(case, ctor, arm, 0, obj)
    solve.assert_not_called()


def test_zero_limits_are_explicit_and_valid():
    case, ctor, arm, obj = fixture()
    arm = replace(arm, engine=HillClimber(replace(arm.engine.config, max_iterations=0, max_evaluations=0)))
    record = run_trial(case, ctor, arm, -3, obj)
    assert record.status == 'ok' and record.iterations == record.evaluations == 0
    assert record.initial_objective == record.final_objective


def test_final_observer_error_is_not_an_algorithm_failure():
    case, ctor, arm, obj = fixture()
    initial_metrics = evaluate_plan(case.problem, ctor.algorithm.solve(case.problem),
                                    validate_plan(case.problem, ctor.algorithm.solve(case.problem)))
    with patch.object(paired, 'evaluate_plan', side_effect=[initial_metrics, ValueError('observer failed')]), \
         pytest.raises(ValueError, match='observer failed') as error:
        run_trial(case, ctor, arm, 0, obj)
    assert 'improver=hc' in error.value.__notes__[0]


def test_total_includes_observation_time():
    case, ctor, _, obj = fixture()
    with patch.object(paired, 'perf_counter', side_effect=[0.0, 1.0, 3.0, 10.0]):
        record = run_trial(case, ctor, ImproverArm('none', None), 0, obj)
    assert record.constructor_seconds == 2.0 and record.total_seconds == 10.0
