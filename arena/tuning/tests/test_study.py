"""Methodology and no-execution contract for C7.1."""
from dataclasses import replace
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

import pytest

from arena.algorithms import EarliestFeasible, GreedyObjectiveConfig, PressureGreedy
from arena.experiments.paired import _prepare, _normalize, _dump
from arena.scheduling.objectives import (
    DeadlineRisk, PriorityPostponement, OverloadCost, MovementCost, PowerCost,
)
from arena.search import (
    PlanObjectiveConfig, HillClimber, HillClimbConfig, ImprovementStrategy,
    NeighbourhoodConfig, SimulatedAnnealing, SimulatedAnnealingConfig,
)
from arena.tuning import (
    TuningAxis, ConstructorSweep, ImproverSweep, TuningStudySpec,
    plan_tuning_study, write_tuning_plan,
)
from arena.tuning import study


@pytest.fixture
def spec(tmp_path):
    objective = PlanObjectiveConfig(
        DeadlineRisk(PowerCost(1, 2), 2),
        PriorityPostponement(PowerCost(1, 1), {1: 2, 2: 1}, 0),
        OverloadCost(PowerCost(10, 2), True),
        MovementCost(0, PowerCost(0, 2)), PowerCost(0, 2),
    )
    config = GreedyObjectiveConfig(objective.deadline, objective.priority, objective.overload,
                                   objective.movement, objective.timing, 30)
    hc = HillClimber(HillClimbConfig(objective, NeighbourhoodConfig(30), ImprovementStrategy.BEST, 3, 10))
    sa = SimulatedAnnealing(SimulatedAnnealingConfig(
        objective, NeighbourhoodConfig(30), 10, .9, .1, seed=999, max_iterations=3, max_evaluations=10))
    return TuningStudySpec(objective, (), (ConstructorSweep('pressure', PressureGreedy(config), ()),),
                           (ImproverSweep('hc', hc, ()), ImproverSweep('sa', sa, ()),
                            ImproverSweep('none', None, ())),
                           (7, 8), 42, 2, 5, 1000, 100000, tmp_path / 'study')


@pytest.fixture(autouse=True)
def no_execution():
    with patch.object(PressureGreedy, 'solve', side_effect=AssertionError('constructor executed')), \
         patch.object(EarliestFeasible, 'solve', side_effect=AssertionError('constructor executed')), \
         patch.object(HillClimber, 'improve_plan', side_effect=AssertionError('search executed')), \
         patch.object(SimulatedAnnealing, 'improve_plan', side_effect=AssertionError('search executed')), \
         patch('arena.experiments.paired.evaluate_plan', side_effect=AssertionError('evaluation executed')), \
         patch('arena.experiments.paired.score_state', side_effect=AssertionError('scoring executed')), \
         patch('arena.experiments.v1_runner.run_v1_experiment', side_effect=AssertionError('runner executed')):
        yield


def test_grid_order_and_cardinality(spec):
    # O=2*2=4; C=2+1=3; I=2+1+1=4. Four scenarios, two seeds.
    spec = replace(spec, objective_axes=(TuningAxis('deadline.cost.weight', (1, 3)),
                                         TuningAxis('overload.cost.exponent', (1, 2))),
                   constructors=(replace(spec.constructors[0], axes=(TuningAxis('horizon_days', (10, 20)),)),
                                 ConstructorSweep('earliest', EarliestFeasible(), ())),
                   improvers=(replace(spec.improvers[0], axes=(TuningAxis('max_iterations', (2, 4)),)),
                              *spec.improvers[1:]))
    plan = plan_tuning_study(spec)
    assert len(plan.candidates) == 48
    assert plan.expected_trials == 384
    assert len(plan.run_configs) == 4
    assert [(r.comparison_objective.deadline.cost.weight, r.comparison_objective.overload.cost.exponent)
            for r in plan.run_configs] == [(1, 1), (1, 2), (3, 1), (3, 2)]
    expected_cells = []
    for run in plan.run_configs:
        assert len(run.constructors) == 3 and len(run.improvers) == 4
        assert [c.algorithm.config.horizon_days for c in run.constructors[:2]] == [10, 20]
        assert [i.engine.config.max_iterations for i in run.improvers[:2]] == [2, 4]
        assert run.seeds == (7, 8) and run.trial_wall_seconds == 5
        expected_cells.extend((run.comparison_objective, c.arm_id, i.arm_id)
                              for c in run.constructors for i in run.improvers)
    assert [(c.comparison_objective, c.constructor.arm_id, c.improver.arm_id)
            for c in plan.candidates] == expected_cells
    assert len({c.candidate_id for c in plan.candidates}) == 48
    assert not spec.output_root.exists()


@pytest.mark.parametrize('path,value', [
    ('deadline.cost.weight', 4), ('overload.cost.exponent', 3),
    ('priority.multipliers', {1: 4, 2: 2}), ('deadline.buffer_days', 6),
    ('movement.fixed_weight', 2), ('movement.distance.weight', 3),
    ('timing.weight', 4), ('timing.exponent', 3),
])
def test_objective_axis_actual_configs_and_immutability(spec, path, value):
    before = _dump(_normalize(spec.objective))
    plan = plan_tuning_study(replace(spec, objective_axes=(TuningAxis(path, (value,)),)))
    objective = plan.run_configs[0].comparison_objective
    leaf = objective
    for part in path.split('.'):
        leaf = getattr(leaf, part)
    assert leaf == value
    assert _dump(_normalize(spec.objective)) == before
    for candidate in plan.candidates:
        assert candidate.constructor.algorithm.config == spec.constructors[0].algorithm.config
        if candidate.improver.engine is not None:
            assert candidate.improver.engine.config.objective == objective
            assert candidate.improver.engine is not spec.improvers[0].engine


def test_constructor_horizon_and_search_axis(spec):
    plan = plan_tuning_study(replace(spec,
        constructors=(replace(spec.constructors[0], axes=(TuningAxis('horizon_days', (12,)),)),),
        improvers=(replace(spec.improvers[1], axes=(TuningAxis('cooling_rate', (.8,)),)),)))
    assert plan.candidates[0].constructor.algorithm.config.horizon_days == 12
    assert plan.candidates[0].improver.engine.config.cooling_rate == .8
    assert spec.constructors[0].algorithm.config.horizon_days == 30
    assert spec.improvers[1].engine.config.cooling_rate == .9


def test_preparation_all_seeds_and_provenance(spec):
    with patch.object(study, '_prepare', wraps=_prepare) as prepare:
        plan = plan_tuning_study(spec)
    for candidate in plan.candidates:
        for seed in spec.seeds:
            assert any(call.args[1:4] == (candidate.constructor, candidate.improver, seed)
                       for call in prepare.call_args_list)
            engine, _, config_json = _prepare(study._probe(), candidate.constructor, candidate.improver,
                                              seed, candidate.comparison_objective)
            if engine is None:
                assert config_json is None
            else:
                assert engine.config.max_iterations == 3 and engine.config.max_evaluations == 10
                assert engine.config.objective == candidate.comparison_objective
                if isinstance(engine, SimulatedAnnealing):
                    assert engine.config.seed == seed
                    assert json.loads(config_json)['config']['fields']['seed'] == seed
    assert spec.improvers[1].engine.config.seed == 999


def test_split(spec):
    plan = plan_tuning_study(spec)
    assert plan.development_scenario_ids == plan_tuning_study(spec).development_scenario_ids
    assert plan.development_scenario_ids != plan_tuning_study(replace(spec, split_seed=43)).development_scenario_ids
    rows = json.loads((study._BENCHMARK / 'workloads.json').read_text())
    manifest = json.loads((study._BENCHMARK / 'manifest.json').read_text())
    dev, hold = set(plan.development_scenario_ids), set(plan.holdout_scenario_ids)
    assert not dev & hold and dev | hold == set(manifest['scenario_ids'])
    assert len(dev) == 4 and len(hold) == 114
    designs = {r['metadata']['design_index'] for r in rows}
    chosen = set(sorted(designs, key=lambda d: (sha256(f'42:{d}'.encode()).digest(), d))[:2])
    assert dev == {r['metadata']['scenario_id'] for r in rows if r['metadata']['design_index'] in chosen}
    for design in designs:
        ids = {r['metadata']['scenario_id'] for r in rows if r['metadata']['design_index'] == design}
        assert ids <= dev or ids <= hold
    assert plan.development_scenario_ids == tuple(i for i in manifest['scenario_ids'] if i in dev)
    assert plan.holdout_scenario_ids == tuple(i for i in manifest['scenario_ids'] if i in hold)
    assert all(r.scenario_ids == plan.development_scenario_ids for r in plan.run_configs)


@pytest.mark.parametrize('axis', [
    TuningAxis('deadline.cost.weight', (1, 1)), TuningAxis('deadline.cost.weight', (True,)),
    TuningAxis('deadline.cost.weight', (-1,)), TuningAxis('deadline.cost.weight', (float('nan'),)),
    TuningAxis('deadline.cost.weight', (float('inf'),)), TuningAxis('deadline.cost.weight', (object(),)),
    TuningAxis('deadline.cost.weight', ()), TuningAxis('deadline.cost.weight', [1]),
    TuningAxis('deadline.__class__', (1,)), TuningAxis('priority.multipliers.1', (1,)),
    TuningAxis('priority.multipliers[1]', (1,)), TuningAxis('deadline..weight', (1,)),
    TuningAxis('seed', (1,)), TuningAxis('deadline.seed', (1,)), TuningAxis('', (1,)),
    TuningAxis('timing.exponent', (0,)), TuningAxis('priority.multipliers', ({1: 1, 2: 2},)),
    TuningAxis('priority.multipliers', ({1: 2}, {'1': 2})),
])
def test_bad_objective_axes(spec, axis):
    with pytest.raises((ValueError, TypeError)):
        plan_tuning_study(replace(spec, objective_axes=(axis,)))
    assert not spec.output_root.exists()


@pytest.mark.parametrize('changes', [
    {'seeds': ()}, {'seeds': (1, 1)}, {'seeds': (True,)}, {'seeds': [1]},
    {'constructors': ()}, {'improvers': ()}, {'objective_axes': []},
    {'split_seed': True}, {'development_design_count': True}, {'development_design_count': 0},
    {'development_design_count': 59}, {'trial_wall_seconds': True}, {'trial_wall_seconds': 0},
    {'trial_wall_seconds': -1}, {'trial_wall_seconds': float('inf')}, {'trial_wall_seconds': float('nan')},
    {'max_candidates': True}, {'max_candidates': 0}, {'max_trials': -1}, {'max_trials': 1.5},
    {'max_candidates': 2}, {'max_trials': 23}, {'output_root': 'not-a-path'},
])
def test_bad_spec(spec, changes):
    with pytest.raises((ValueError, TypeError)):
        plan_tuning_study(replace(spec, **changes))
    assert not spec.output_root.exists()


@pytest.mark.parametrize('target,path,value', [
    ('constructor', 'horizon_days', -1), ('constructor', 'horizon_days', True),
    ('improver', 'max_iterations', -1), ('improver', 'max_evaluations', None),
    ('improver', 'seed', 2), ('improver', 'objective.deadline.cost.weight', 2),
    ('improver', 'objective', None), ('improver', 'neighbourhood.horizon_days', -1),
])
def test_bad_arm_axes(spec, target, path, value):
    axis = TuningAxis(path, (value,))
    changes = ({'constructors': (replace(spec.constructors[0], axes=(axis,)),)} if target == 'constructor'
               else {'improvers': (replace(spec.improvers[0], axes=(axis,)),)})
    with pytest.raises((ValueError, TypeError)):
        plan_tuning_study(replace(spec, **changes))
    assert not spec.output_root.exists()


def test_invalid_sweeps_and_duplicates(spec):
    bad = [
        dict(constructors=spec.constructors * 2), dict(improvers=spec.improvers * 2),
        dict(constructors=(replace(spec.constructors[0], arm_id=' '),)),
        dict(improvers=(ImproverSweep('unknown', object(), ()),)),
        dict(constructors=(ConstructorSweep('unknown', object(), ()),)),
        dict(constructors=(ConstructorSweep('earliest', EarliestFeasible(), (TuningAxis('horizon_days', (1,)),)),)),
        dict(improvers=(ImproverSweep('none', None, (TuningAxis('max_iterations', (1,)),)),)),
        dict(objective_axes=(TuningAxis('timing.weight', (1,)),) * 2),
    ]
    for changes in bad:
        with pytest.raises((ValueError, TypeError)):
            plan_tuning_study(replace(spec, **changes))
    assert not spec.output_root.exists()


def test_limit_before_expansion(spec):
    huge = replace(spec, objective_axes=(TuningAxis('timing.weight', tuple(range(10000))),))
    with patch.object(study, '_variants', side_effect=AssertionError('expanded too early')):
        with pytest.raises(ValueError, match='cardinality'):
            plan_tuning_study(huge)


def test_json_identity_and_effective_seed(spec):
    plan = plan_tuning_study(spec)
    equivalent = plan_tuning_study(replace(spec, output_root=spec.output_root.with_name('other')))
    assert [c.candidate_id for c in plan.candidates] == [c.candidate_id for c in equivalent.candidates]
    new_sa = replace(spec.improvers[1].engine, config=replace(spec.improvers[1].engine.config, seed=-1))
    seed_equivalent = plan_tuning_study(replace(spec, improvers=(spec.improvers[0],
        replace(spec.improvers[1], engine=new_sa), spec.improvers[2])))
    assert [c.candidate_id for c in plan.candidates] == [c.candidate_id for c in seed_equivalent.candidates]
    changed = plan_tuning_study(replace(spec, constructors=(replace(spec.constructors[0],
        axes=(TuningAxis('horizon_days', (31,)),)),)))
    assert plan.candidates[0].candidate_id != changed.candidates[0].candidate_id
    path = write_tuning_plan(plan)
    data = json.loads(path.read_text(encoding='utf-8'))
    assert data['schema_version'] == 1 and data['benchmark_version'] == 'v1'
    assert data['benchmark_manifest_sha256'] == sha256((study._BENCHMARK / 'manifest.json').read_bytes()).hexdigest()
    assert data['candidate_count'] == 3 and data['expected_trials'] == 24
    assert data['seeds'] == [7, 8] and data['split_seed'] == 42
    assert data['development_scenario_ids'] == list(plan.development_scenario_ids)
    assert data['holdout_scenario_ids'] == list(plan.holdout_scenario_ids)
    group = data['objective_groups'][0]
    assert group['objective_id'] == sha256(_dump(_normalize(spec.objective)).encode()).hexdigest()
    assert group['output_directory'] == 'objective_' + group['objective_id']
    assert [e['run_seed'] for e in group['improvers'][1]['effective_configs']] == [7, 8]
    assert json.loads(group['improvers'][1]['effective_configs'][0]['config_json'])['config']['fields']['seed'] == 7
    assert data['constructors'][0]['config_json']
    assert [c['candidate_id'] for c in data['candidates']] == [c.candidate_id for c in plan.candidates]
    with pytest.raises(FileExistsError):
        write_tuning_plan(plan)
    with pytest.raises(FileExistsError):
        plan_tuning_study(spec)
    assert list(spec.output_root.iterdir()) == [path]


def test_serialization_and_io_failures(spec):
    plan = plan_tuning_study(spec)
    with patch.object(study, '_artifact', return_value={'invalid': float('nan')}):
        with pytest.raises(ValueError):
            write_tuning_plan(plan)
    assert not spec.output_root.exists()
    with patch.object(study.os, 'fsync', side_effect=OSError('disk')):
        with pytest.raises(OSError):
            write_tuning_plan(plan)
    assert not spec.output_root.exists()


def test_durability_and_existing_paths(spec):
    plan = plan_tuning_study(spec)
    with patch.object(study.os, 'fsync', wraps=os.fsync) as sync:
        write_tuning_plan(plan)
    assert sync.call_count == 3
    root = spec.output_root.with_name('dangling')
    root.symlink_to(root.with_name('missing'))
    with pytest.raises(FileExistsError):
        plan_tuning_study(replace(spec, output_root=root))


@pytest.mark.parametrize('damage', ['status', 'order', 'duplicate', 'replicate', 'design'])
def test_corrupt_frozen_metadata(spec, tmp_path, monkeypatch, damage):
    manifest = json.loads((study._BENCHMARK / 'manifest.json').read_text())
    rows = json.loads((study._BENCHMARK / 'workloads.json').read_text())
    if damage == 'status':
        manifest['status'] = 'draft'
    elif damage == 'order':
        rows.reverse()
    elif damage == 'duplicate':
        manifest['scenario_ids'][1] = manifest['scenario_ids'][0]
        rows[1]['metadata']['scenario_id'] = rows[0]['metadata']['scenario_id']
    elif damage == 'replicate':
        rows[1]['metadata']['replicate'] = rows[0]['metadata']['replicate']
    else:
        rows[0]['metadata']['design_index'] = 999
    (tmp_path / 'manifest.json').write_text(json.dumps(manifest))
    (tmp_path / 'workloads.json').write_text(json.dumps(rows))
    monkeypatch.setattr(study, '_BENCHMARK', tmp_path)
    with pytest.raises(ValueError):
        plan_tuning_study(spec)
    assert not spec.output_root.exists()


def test_import_without_django():
    env = dict(os.environ)
    env.pop('DJANGO_SETTINGS_MODULE', None)
    result = subprocess.run([sys.executable, '-c',
        "import sys; import arena.tuning; assert not any(n == 'django' or n.startswith('django.') "
        "for n in sys.modules); assert 'arena.benchmarks.reconstruct' not in sys.modules"],
        env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_all_exact_supported_families(spec):
    from arena.algorithms import AggressiveEarlierGreedy, StableRiskGreedy, HybridCostGreedy
    from arena.search import (
        VariableNeighbourhoodSearch, VariableNeighbourhoodConfig, VariableNeighbourhoodMode,
        TabuSearch, TabuConfig, LargeNeighbourhoodSearch, LargeNeighbourhoodConfig,
        AdaptiveLargeNeighbourhoodSearch, AdaptiveLargeNeighbourhoodConfig,
        DestroyOperator, RepairOperator,
    )
    objective, neighbourhood = spec.objective, NeighbourhoodConfig(10)
    other_engines = (
        VariableNeighbourhoodSearch(VariableNeighbourhoodConfig(
            objective, neighbourhood, VariableNeighbourhoodMode.VNS, 2, 5)),
        TabuSearch(TabuConfig(objective, neighbourhood, 2, 2, 5)),
        LargeNeighbourhoodSearch(LargeNeighbourhoodConfig(
            objective, 10, 1, DestroyOperator.RANDOM, RepairOperator.EARLIEST, 2, 5)),
        AdaptiveLargeNeighbourhoodSearch(AdaptiveLargeNeighbourhoodConfig(
            objective, 10, 1, 2, .5, 10, .9, .1, 3, 2, 1, 5)),
    )
    constructors = (*spec.constructors, *(ConstructorSweep(cls.__name__,
        cls(spec.constructors[0].algorithm.config), ()) for cls in
        (AggressiveEarlierGreedy, StableRiskGreedy, HybridCostGreedy)),
        ConstructorSweep('earliest', EarliestFeasible(), ()))
    improvers = (*spec.improvers, *(ImproverSweep(type(e).__name__, e, ()) for e in other_engines))
    plan = plan_tuning_study(replace(spec, constructors=constructors, improvers=improvers,
                                    objective_axes=(TuningAxis('timing.weight', (5,)),)))
    assert len(plan.candidates) == 5 * 7
    for candidate in plan.candidates:
        if candidate.improver.engine is not None:
            assert candidate.improver.engine.config.objective.timing.weight == 5


def test_exact_class_rejects_subclasses_and_generic_constructor(spec):
    from arena.algorithms import GreedyConstructor
    class CustomHC(HillClimber):
        pass
    class CustomPressure(PressureGreedy):
        pass
    for algorithm in (GreedyConstructor(spec.constructors[0].algorithm.config),
                      CustomPressure(spec.constructors[0].algorithm.config)):
        with pytest.raises(TypeError):
            plan_tuning_study(replace(spec, constructors=(ConstructorSweep('custom', algorithm, ()),)))
    with pytest.raises(TypeError):
        plan_tuning_study(replace(spec, improvers=(ImproverSweep('custom', CustomHC(spec.improvers[0].engine.config), ()),)))


def test_scenario_names_are_opaque(spec, tmp_path, monkeypatch):
    manifest = json.loads((study._BENCHMARK / 'manifest.json').read_text())
    rows = json.loads((study._BENCHMARK / 'workloads.json').read_text())
    original = plan_tuning_study(spec)
    rename = {name: f'opaque-{118-index}' for index, name in enumerate(manifest['scenario_ids'])}
    manifest['scenario_ids'] = [rename[name] for name in manifest['scenario_ids']]
    for row in rows:
        row['metadata']['scenario_id'] = rename[row['metadata']['scenario_id']]
        row.pop('features')  # The split neither uses nor requires characterization.
    (tmp_path / 'manifest.json').write_text(json.dumps(manifest))
    (tmp_path / 'workloads.json').write_text(json.dumps(rows))
    monkeypatch.setattr(study, '_BENCHMARK', tmp_path)
    plan = plan_tuning_study(spec)
    assert plan.development_scenario_ids == tuple(rename[name] for name in original.development_scenario_ids)


def test_collision_rejected(spec):
    with patch.object(study, '_digest', return_value='0' * 64):
        with pytest.raises(ValueError, match='collision'):
            plan_tuning_study(spec)
    assert not spec.output_root.exists()


def test_explicit_bounds_may_be_supplied_by_axes(spec):
    hc = HillClimber(replace(spec.improvers[0].engine.config, max_iterations=None, max_evaluations=None))
    unbounded = replace(spec, improvers=(ImproverSweep('hc', hc, ()),))
    with pytest.raises(ValueError, match='explicit'):
        plan_tuning_study(unbounded)
    bounded = replace(unbounded, improvers=(ImproverSweep('hc', hc, (
        TuningAxis('max_iterations', (0,)), TuningAxis('max_evaluations', (0,)))),))
    plan = plan_tuning_study(bounded)
    assert plan.candidates[0].improver.engine.config.max_iterations == 0
    assert plan.candidates[0].improver.engine.config.max_evaluations == 0


def test_axis_provenance_and_boolean_switch(spec):
    axis = TuningAxis('priority.multipliers', ({1: 5, 2: 1},))
    plan = plan_tuning_study(replace(spec, objective_axes=(axis,), constructors=(replace(
        spec.constructors[0], axes=(TuningAxis('overload.exempt_allowed_dates', (False,)),)),)))
    data = json.loads(write_tuning_plan(plan).read_text())
    assert data['objective_axes'] == [{'path': axis.path, 'values': [{'1': 5, '2': 1}]}]
    assert plan.candidates[0].constructor.algorithm.config.overload.exempt_allowed_dates is False
    assert spec.constructors[0].algorithm.config.overload.exempt_allowed_dates is True



def test_axis_snapshot_survives_caller_mutation(spec):
    multipliers = {1: 4, 2: 1}
    configured = replace(
        spec,
        objective_axes=(TuningAxis('priority.multipliers', (multipliers,)),),
    )
    plan = plan_tuning_study(configured)
    original_ids = tuple(candidate.candidate_id for candidate in plan.candidates)

    multipliers[1] = 999
    saved = json.loads(write_tuning_plan(plan).read_text(encoding='utf-8'))

    assert multipliers[1] == 999
    assert plan.spec.objective_axes[0].values[0][1] == 4
    assert saved['objective_axes'][0]['values'][0] == {'1': 4, '2': 1}
    effective = saved['objective_groups'][0]['comparison_objective']
    assert effective['fields']['priority']['fields']['multipliers'] == {'1': 4, '2': 1}
    assert tuple(candidate.candidate_id for candidate in plan.candidates) == original_ids
    with pytest.raises(TypeError):
        plan.spec.objective_axes[0].values[0][1] = 100


def test_constructor_axis_snapshot_survives_caller_mutation(spec):
    multipliers = {1: 5, 2: 1}
    constructor = replace(
        spec.constructors[0],
        axes=(TuningAxis('priority.multipliers', (multipliers,)),),
    )
    plan = plan_tuning_study(replace(spec, constructors=(constructor,)))
    multipliers[1] = 777

    saved = json.loads(write_tuning_plan(plan).read_text(encoding='utf-8'))
    assert saved['constructors'][0]['axes'][0]['values'][0] == {'1': 5, '2': 1}
    effective = json.loads(saved['objective_groups'][0]['constructors'][0]['config_json'])
    assert effective['config']['fields']['priority']['fields']['multipliers'] == {
        '1': 5, '2': 1
    }
    assert plan.spec.constructors[0].axes[0].values[0][1] == 5


def test_nested_axis_snapshot_and_improver_provenance(spec):
    caller_owned = {'outer': [{'weights': [1, 2]}]}
    detached = study._snapshot_value(caller_owned)
    caller_owned['outer'][0]['weights'][0] = 99
    assert detached['outer'][0]['weights'] == (1, 2)
    with pytest.raises(TypeError):
        detached['outer'] = ()

    hc = replace(
        spec.improvers[0],
        axes=(TuningAxis('neighbourhood', (NeighbourhoodConfig(5),)),),
    )
    plan = plan_tuning_study(replace(spec, improvers=(hc,)))
    saved = json.loads(write_tuning_plan(plan).read_text(encoding='utf-8'))
    assert plan.spec.improvers[0].axes[0].values[0].horizon_days == 5
    effective = json.loads(
        saved['objective_groups'][0]['improvers'][0]['effective_configs'][0]['config_json']
    )
    assert effective['config']['fields']['neighbourhood']['fields']['horizon_days'] == 5
