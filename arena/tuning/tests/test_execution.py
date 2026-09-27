from hashlib import sha256
import json
from unittest.mock import patch

import pytest

from arena.algorithms import GreedyObjectiveConfig, PressureGreedy
from arena.experiments.v1_runner import V1RunResult
from arena.scheduling.objectives import (
    DeadlineRisk,
    PriorityPostponement,
    OverloadCost,
    MovementCost,
    PowerCost,
)
from arena.search import PlanObjectiveConfig
from arena.tuning import (
    ConstructorSweep,
    ImproverSweep,
    TuningStudySpec,
    plan_tuning_study,
    write_tuning_plan,
)
from arena.tuning.execution import (
    execute_tuning_study,
    load_tuning_results,
)


def make_spec(tmp_path):
    objective = PlanObjectiveConfig(
        DeadlineRisk(PowerCost(1, 2), 2),
        PriorityPostponement(
            PowerCost(1, 1),
            {1: 2, 2: 1},
            0,
        ),
        OverloadCost(PowerCost(10, 2), True),
        MovementCost(0, PowerCost(0, 2)),
        PowerCost(0, 2),
    )

    constructor_config = GreedyObjectiveConfig(
        objective.deadline,
        objective.priority,
        objective.overload,
        objective.movement,
        objective.timing,
        30,
    )

    return TuningStudySpec(
        objective=objective,
        objective_axes=(),
        constructors=(
            ConstructorSweep(
                'pressure',
                PressureGreedy(constructor_config),
                (),
            ),
        ),
        improvers=(
            ImproverSweep('none', None, ()),
        ),
        seeds=(7, 8),
        split_seed=42,
        development_design_count=2,
        trial_wall_seconds=5,
        max_candidates=100,
        max_trials=1000,
        output_root=tmp_path / 'study',
    )


def test_execute_requires_exact_registration_and_runs_development_only(
    tmp_path,
):
    plan = plan_tuning_study(make_spec(tmp_path))

    with pytest.raises(ValueError, match='registered'):
        execute_tuning_study(plan)

    write_tuning_plan(plan)
    calls = []

    def fake_run(config):
        calls.append(config)
        return V1RunResult(
            config.output_dir,
            len(config.scenario_ids),
            8,
            8,
            1,
            config.output_dir / 'manifest.json',
            config.output_dir / 'records.jsonl',
        )

    with (
        patch('arena.tuning.execution._preflight'),
        patch(
            'arena.tuning.execution.run_v1_experiment',
            side_effect=fake_run,
        ),
    ):
        result = execute_tuning_study(plan)

    assert calls == list(plan.run_configs)

    assert all(
        config.scenario_ids == plan.development_scenario_ids
        for config in calls
    )

    assert result.expected_trials == result.completed_trials == 8
    assert result.timed_out_trials == 1


def test_execute_rejects_tampered_registration_before_running(tmp_path):
    plan = plan_tuning_study(make_spec(tmp_path))
    path = write_tuning_plan(plan)

    path.write_text(
        path.read_text(encoding='utf-8') + ' ',
        encoding='utf-8',
    )

    with patch(
        'arena.tuning.execution.run_v1_experiment'
    ) as runner:
        with pytest.raises(ValueError, match='does not match'):
            execute_tuning_study(plan)

    runner.assert_not_called()


def write_complete_run(plan, timeout_first=False):
    root = plan.spec.output_root

    data = json.loads(
        (root / 'study_plan.json').read_text(encoding='utf-8')
    )

    for group in data['objective_groups']:
        directory = root / group['output_directory']
        directory.mkdir()

        constructors = [
            row['arm_id']
            for row in group['constructors']
        ]

        improvers = [
            row['arm_id']
            for row in group['improvers']
        ]

        constructor_configs = {
            row['arm_id']: row['config_json']
            for row in group['constructors']
        }

        improver_configs = {
            row['arm_id']: {
                entry['run_seed']: entry['config_json']
                for entry in row['effective_configs']
            }
            for row in group['improvers']
        }

        records = []
        index = 0
        ok = 0
        timeouts = 0

        for scenario in data['development_scenario_ids']:
            for constructor in constructors:
                for improver in improvers:
                    for seed in data['seeds']:
                        timeout = timeout_first and index == 0
                        status = (
                            'wall_timeout'
                            if timeout
                            else 'ok'
                        )

                        trial = (
                            None
                            if timeout
                            else {
                                'status': 'ok',
                                'final_performance': {
                                    'hard_violation_count': 0,
                                    'deadline_miss_rate': 0.25,
                                    'priority_inversion_rate': 0.5,
                                },
                            }
                        )

                        records.append({
                            'trial_index': index,
                            'scenario_id': scenario,
                            'constructor_id': constructor,
                            'improver_id': improver,
                            'run_seed': seed,
                            'constructor_config_json':
                                constructor_configs[constructor],
                            'improver_config_json':
                                improver_configs[improver][seed],
                            'comparison_objective':
                                group['comparison_objective'],
                            'status': status,
                            'worker_wall_seconds':
                                5.5 if timeout else 0.5,
                            'trial': trial,
                        })

                        ok += not timeout
                        timeouts += timeout
                        index += 1

        raw = ''.join(
            json.dumps(
                row,
                sort_keys=True,
                separators=(',', ':'),
            ) + '\n'
            for row in records
        ).encode()

        (directory / 'records.jsonl').write_bytes(raw)

        manifest = {
            'schema_version': 1,
            'benchmark_version': 'v1',
            'status': 'complete',
            'scenario_ids':
                data['development_scenario_ids'],
            'constructor_ids': constructors,
            'improver_ids': improvers,
            'seeds': data['seeds'],
            'comparison_objective':
                group['comparison_objective'],
            'expected_trials': index,
            'completed_trials': index,
            'successful_trials': ok,
            'timed_out_trials': timeouts,
            'benchmark_manifest_sha256':
                data['benchmark_manifest_sha256'],
            'records_sha256': sha256(raw).hexdigest(),
        }

        (directory / 'manifest.json').write_text(
            json.dumps(manifest),
            encoding='utf-8',
        )


def test_load_results_validates_and_aggregates_development_evidence(
    tmp_path,
):
    plan = plan_tuning_study(make_spec(tmp_path))
    write_tuning_plan(plan)
    write_complete_run(plan, timeout_first=True)

    result = load_tuning_results(plan.spec.output_root)

    assert (
        result.development_scenario_ids
        == plan.development_scenario_ids
    )
    assert (
        result.holdout_scenario_ids
        == plan.holdout_scenario_ids
    )

    assert result.expected_trials == result.completed_trials == 8

    summary = result.candidate_summaries[0]

    assert summary.intended_trials == 8
    assert summary.ok_trials == 7
    assert summary.timed_out_trials == 1
    assert summary.failed_trials == 0
    assert summary.ok_rate == 7 / 8
    assert summary.timeout_rate == 1 / 8

    assert (
        summary.performance_means['deadline_miss_rate']
        == 0.25
    )
    assert (
        summary.performance_observation_counts[
            'deadline_miss_rate'
        ]
        == 7
    )

    with pytest.raises(TypeError):
        summary.performance_means['deadline_miss_rate'] = 1


def test_load_results_rejects_holdout_or_provenance_tampering(
    tmp_path,
):
    plan = plan_tuning_study(make_spec(tmp_path))
    write_tuning_plan(plan)
    write_complete_run(plan)

    study = json.loads(
        (
            plan.spec.output_root
            / 'study_plan.json'
        ).read_text()
    )

    group = study['objective_groups'][0]
    directory = (
        plan.spec.output_root
        / group['output_directory']
    )

    rows = [
        json.loads(line)
        for line in (
            directory
            / 'records.jsonl'
        ).read_text().splitlines()
    ]

    rows[0]['scenario_id'] = plan.holdout_scenario_ids[0]

    raw = ''.join(
        json.dumps(
            row,
            sort_keys=True,
            separators=(',', ':'),
        ) + '\n'
        for row in rows
    ).encode()

    (directory / 'records.jsonl').write_bytes(raw)

    manifest_path = directory / 'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    manifest['records_sha256'] = sha256(raw).hexdigest()
    manifest_path.write_text(json.dumps(manifest))

    with pytest.raises(
        ValueError,
        match='order/identity|Holdout',
    ):
        load_tuning_results(plan.spec.output_root)
