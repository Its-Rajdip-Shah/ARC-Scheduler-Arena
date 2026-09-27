from dataclasses import replace
from pathlib import Path
from types import MappingProxyType

from arena.tuning.confirmation import (
    ConfirmationCandidateLink,
    build_confirmation_subset_plan,
    combine_seed_tuning_results,
    relabel_confirmation_results,
)
from arena.tuning.design import (
    build_c7_calibration_spec,
)
from arena.tuning.execution import (
    TuningCandidateSummary,
    TuningStudyResults,
    TuningTrialObservation,
)
from arena.tuning.study import (
    plan_tuning_study,
)


def _summary(
    candidate_id,
    intended,
):
    return TuningCandidateSummary(
        candidate_id=candidate_id,
        objective_id='objective',
        constructor_id='constructor',
        improver_id=candidate_id,
        intended_trials=intended,
        ok_trials=intended,
        timed_out_trials=0,
        failed_trials=0,
        ok_rate=1.0,
        timeout_rate=0.0,
        mean_worker_wall_seconds=1.0,
        performance_means=MappingProxyType({
            'deadline_miss_rate': 0.1,
        }),
        performance_observation_counts=
            MappingProxyType({
                'deadline_miss_rate': intended,
            }),
    )


def _results(
    candidate_ids,
    scenarios,
    seeds,
):
    observations = tuple(
        TuningTrialObservation(
            candidate_id=candidate_id,
            scenario_id=scenario_id,
            run_seed=seed,
            status='ok',
            worker_wall_seconds=1.0,
            performance=MappingProxyType({
                'hard_violation_count': 0.0,
                'canonical_infeasibility_count':
                    0.0,
                'deadline_miss_rate':
                    float(index) / 100,
            }),
        )
        for index, candidate_id
        in enumerate(candidate_ids)
        for scenario_id in scenarios
        for seed in seeds
    )

    intended = (
        len(scenarios)
        * len(seeds)
    )

    return TuningStudyResults(
        output_root=Path('evidence'),
        benchmark_manifest_sha256='a' * 64,
        development_scenario_ids=scenarios,
        holdout_scenario_ids=('H1',),
        seeds=seeds,
        candidate_summaries=tuple(
            _summary(
                candidate_id,
                intended,
            )
            for candidate_id
            in candidate_ids
        ),
        trial_observations=observations,
        expected_trials=len(observations),
        completed_trials=len(observations),
    )


def test_confirmation_plan_uses_fresh_seed_identities(
    tmp_path,
):
    source = plan_tuning_study(
        build_c7_calibration_spec(
            tmp_path / 'source'
        )
    )

    fresh_spec = replace(
        source.spec,
        seeds=(1702, 1703),
        output_root=
            tmp_path / 'fresh-full',
        max_trials=
            source.expected_trials * 2,
    )

    fresh = plan_tuning_study(
        fresh_spec
    )

    source_ids = tuple(
        candidate.candidate_id
        for candidate
        in source.candidates[:3]
    )

    scenarios = (
        source.development_scenario_ids[:4]
    )

    confirmation = (
        build_confirmation_subset_plan(
            source,
            fresh,
            source_candidate_ids=
                source_ids,
            scenario_ids=scenarios,
            output_root=
                tmp_path / 'confirmation',
            trial_wall_seconds=45.0,
        )
    )

    plan = confirmation.tuning_plan

    assert plan.spec.seeds == (
        1702,
        1703,
    )

    assert (
        plan.development_scenario_ids
        == scenarios
    )

    assert plan.expected_trials == 24

    assert tuple(
        link.source_candidate_id
        for link
        in confirmation.candidate_links
    ) == source_ids

    assert len({
        link.confirmation_candidate_id
        for link
        in confirmation.candidate_links
    }) == 3

    assert all(
        link.source_candidate_id
        != link.confirmation_candidate_id
        for link
        in confirmation.candidate_links
    )

    assert all(
        set(run.seeds)
        == {1702, 1703}
        for run in plan.run_configs
    )


def test_relabel_confirmation_results():
    fresh = _results(
        ('fresh-a', 'fresh-b'),
        ('S1', 'S2'),
        (1702, 1703),
    )

    relabelled = (
        relabel_confirmation_results(
            fresh,
            (
                ConfirmationCandidateLink(
                    'source-a',
                    'fresh-a',
                ),
                ConfirmationCandidateLink(
                    'source-b',
                    'fresh-b',
                ),
            ),
        )
    )

    assert tuple(
        summary.candidate_id
        for summary
        in relabelled.candidate_summaries
    ) == (
        'source-a',
        'source-b',
    )

    assert {
        observation.candidate_id
        for observation
        in relabelled.trial_observations
    } == {
        'source-a',
        'source-b',
    }

    assert relabelled.seeds == (
        1702,
        1703,
    )


def test_combine_seed_tuning_results():
    historical = _results(
        ('a', 'b'),
        ('S1', 'S2'),
        (1701,),
    )

    fresh = _results(
        ('a', 'b'),
        ('S1', 'S2'),
        (1702, 1703),
    )

    pooled = combine_seed_tuning_results(
        historical,
        fresh,
        candidate_ids=('a', 'b'),
    )

    assert pooled.seeds == (
        1701,
        1702,
        1703,
    )

    assert pooled.expected_trials == 12
    assert pooled.completed_trials == 12

    assert all(
        summary.intended_trials == 6
        for summary
        in pooled.candidate_summaries
    )
