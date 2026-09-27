"""C7.4b incremental execution-plan and cumulative-evidence utilities."""
from __future__ import annotations

from dataclasses import replace
from math import isfinite
from pathlib import Path
from types import MappingProxyType

from arena.evaluation.performance import PerformanceVector
from arena.experiments.v1_runner import V1RunConfig

from .execution import (
    TuningCandidateSummary,
    TuningStudyResults,
    TuningTrialObservation,
)
from .racing_campaign import RacingRoundPlan
from .study import TuningStudyPlan


def build_incremental_tuning_plan(
    frozen_full_plan: TuningStudyPlan,
    round_plan: RacingRoundPlan,
    output_root: Path,
) -> TuningStudyPlan:
    """Build an executable study for only this round's new paired cells.

    Arbitrary survivor sets are represented as one rectangular V1 group per
    objective/constructor pair. This avoids resurrecting eliminated
    constructor/improver combinations while still giving the parallel V1
    runner enough cells to use its worker pool efficiently.
    """
    if not isinstance(frozen_full_plan, TuningStudyPlan):
        raise TypeError('Expected TuningStudyPlan')

    if not isinstance(round_plan, RacingRoundPlan):
        raise TypeError('Expected RacingRoundPlan')

    if not isinstance(output_root, Path):
        raise TypeError('output_root must be a Path')

    if (
        tuple(frozen_full_plan.spec.seeds)
        != tuple(round_plan.seeds)
    ):
        raise ValueError(
            'Round seeds differ from frozen candidate plan'
        )

    if (
        set(round_plan.scenario_ids)
        - set(frozen_full_plan.development_scenario_ids)
    ):
        raise ValueError(
            'Round scenarios escaped frozen development partition'
        )

    if (
        set(round_plan.incremental_scenario_ids)
        - set(round_plan.scenario_ids)
    ):
        raise ValueError(
            'Incremental scenarios must belong to cumulative round'
        )

    if (
        set(round_plan.incremental_scenario_ids)
        & set(frozen_full_plan.holdout_scenario_ids)
    ):
        raise ValueError(
            'Incremental execution attempted to access holdout'
        )

    candidate_by_id = {
        candidate.candidate_id: candidate
        for candidate in frozen_full_plan.candidates
    }

    try:
        candidates = tuple(
            candidate_by_id[candidate_id]
            for candidate_id
            in round_plan.incoming_candidate_ids
        )
    except KeyError as exc:
        raise ValueError(
            'Round references unknown frozen candidate'
        ) from exc

    if tuple(
        candidate.candidate_id
        for candidate in candidates
    ) != round_plan.incoming_candidate_ids:
        raise ValueError(
            'Frozen candidate identity/order mismatch'
        )

    grouped = {}

    for candidate in candidates:
        key = (
            candidate.objective_id,
            candidate.constructor.arm_id,
        )
        grouped.setdefault(key, []).append(candidate)

    runs = []

    for index, group_candidates in enumerate(
        grouped.values(),
        start=1,
    ):
        first = group_candidates[0]

        if any(
            candidate.objective_id != first.objective_id
            or candidate.constructor.arm_id
            != first.constructor.arm_id
            or candidate.comparison_objective
            != first.comparison_objective
            for candidate in group_candidates
        ):
            raise ValueError(
                'Invalid objective/constructor execution group'
            )

        improvers = tuple(
            candidate.improver
            for candidate in group_candidates
        )

        if len({
            improver.arm_id
            for improver in improvers
        }) != len(improvers):
            raise ValueError(
                'Duplicate improver inside execution group'
            )

        runs.append(
            V1RunConfig(
                scenario_ids=
                    round_plan.incremental_scenario_ids,
                constructors=(first.constructor,),
                improvers=improvers,
                seeds=round_plan.seeds,
                comparison_objective=
                    first.comparison_objective,
                trial_wall_seconds=
                    frozen_full_plan.spec.trial_wall_seconds,
                output_dir=(
                    output_root
                    / (
                        f'group_{index:02d}_'
                        f'{first.constructor.arm_id[:24]}'
                    )
                ),
            )
        )

    expected_trials = (
        len(candidates)
        * len(round_plan.incremental_scenario_ids)
        * len(round_plan.seeds)
    )

    if (
        expected_trials
        != round_plan.incremental_expected_trials
    ):
        raise ValueError(
            'Incremental trial cardinality differs from round plan'
        )

    represented = []

    for run in runs:
        for constructor in run.constructors:
            for improver in run.improvers:
                matches = [
                    candidate.candidate_id
                    for candidate in candidates
                    if (
                        candidate.constructor.arm_id
                        == constructor.arm_id
                        and candidate.improver.arm_id
                        == improver.arm_id
                        and candidate.comparison_objective
                        == run.comparison_objective
                    )
                ]

                if len(matches) != 1:
                    raise ValueError(
                        'Execution grouping does not map one-to-one '
                        'to frozen candidates'
                    )

                represented.extend(matches)

    if (
        tuple(represented)
        != tuple(
            candidate.candidate_id
            for run in runs
            for candidate in candidates
            if (
                candidate.constructor.arm_id
                == run.constructors[0].arm_id
                and candidate.comparison_objective
                == run.comparison_objective
            )
        )
    ):
        raise ValueError(
            'Execution group representation is unstable'
        )

    if set(represented) != set(
        round_plan.incoming_candidate_ids
    ):
        raise ValueError(
            'Execution groups do not cover exactly the incoming field'
        )

    spec = replace(
        frozen_full_plan.spec,
        output_root=output_root,
        max_candidates=len(candidates),
        max_trials=expected_trials,
    )

    return TuningStudyPlan(
        spec=spec,
        benchmark_manifest_sha256=
            frozen_full_plan.benchmark_manifest_sha256,
        development_scenario_ids=
            round_plan.incremental_scenario_ids,
        holdout_scenario_ids=
            frozen_full_plan.holdout_scenario_ids,
        candidates=candidates,
        run_configs=tuple(runs),
        expected_trials=expected_trials,
    )


def _rebuild_summary(
    template: TuningCandidateSummary,
    observations: tuple[TuningTrialObservation, ...],
) -> TuningCandidateSummary:
    if not observations:
        raise ValueError(
            'Cannot summarize empty candidate evidence'
        )

    ok = sum(
        observation.status == 'ok'
        for observation in observations
    )

    timeouts = sum(
        observation.status == 'wall_timeout'
        for observation in observations
    )

    failures = len(observations) - ok - timeouts

    walls = tuple(
        observation.worker_wall_seconds
        for observation in observations
    )

    if any(
        not isfinite(value) or value < 0
        for value in walls
    ):
        raise ValueError('Invalid worker wall time')

    performance_names = tuple(
        PerformanceVector.__dataclass_fields__
    )

    values = {
        name: []
        for name in performance_names
    }

    for observation in observations:
        if observation.status != 'ok':
            if observation.performance is not None:
                raise ValueError(
                    'Non-ok observation fabricated C1 performance'
                )
            continue

        if observation.performance is None:
            raise ValueError(
                'Successful observation missing C1 performance'
            )

        for name in performance_names:
            value = observation.performance.get(name)

            if value is None:
                continue

            if (
                type(value) not in (int, float)
                or not isfinite(value)
            ):
                raise ValueError(
                    'Invalid cumulative C1 performance value'
                )

            values[name].append(float(value))

    means = MappingProxyType({
        name: sum(entries) / len(entries)
        for name, entries in values.items()
        if entries
    })

    counts = MappingProxyType({
        name: len(entries)
        for name, entries in values.items()
    })

    return TuningCandidateSummary(
        candidate_id=template.candidate_id,
        objective_id=template.objective_id,
        constructor_id=template.constructor_id,
        improver_id=template.improver_id,
        intended_trials=len(observations),
        ok_trials=ok,
        timed_out_trials=timeouts,
        failed_trials=failures,
        ok_rate=ok / len(observations),
        timeout_rate=timeouts / len(observations),
        mean_worker_wall_seconds=(
            sum(walls) / len(walls)
        ),
        performance_means=means,
        performance_observation_counts=counts,
    )


def merge_cumulative_tuning_results(
    previous: TuningStudyResults | None,
    incremental: TuningStudyResults,
    *,
    incoming_candidate_ids: tuple[str, ...],
    cumulative_scenario_ids: tuple[str, ...],
) -> TuningStudyResults:
    """Merge this round's suffix with survivors' earlier paired evidence."""
    if (
        previous is not None
        and not isinstance(previous, TuningStudyResults)
    ):
        raise TypeError(
            'previous must be TuningStudyResults or None'
        )

    if not isinstance(incremental, TuningStudyResults):
        raise TypeError(
            'incremental must be TuningStudyResults'
        )

    if (
        not isinstance(incoming_candidate_ids, tuple)
        or not incoming_candidate_ids
        or len(set(incoming_candidate_ids))
        != len(incoming_candidate_ids)
    ):
        raise ValueError(
            'incoming_candidate_ids must be unique and nonempty'
        )

    if (
        not isinstance(cumulative_scenario_ids, tuple)
        or not cumulative_scenario_ids
        or len(set(cumulative_scenario_ids))
        != len(cumulative_scenario_ids)
    ):
        raise ValueError(
            'cumulative_scenario_ids must be unique and nonempty'
        )

    incremental_ids = tuple(
        summary.candidate_id
        for summary in incremental.candidate_summaries
    )

    if incremental_ids != incoming_candidate_ids:
        raise ValueError(
            'Incremental evidence candidate order differs '
            'from incoming survivor order'
        )

    if (
        set(incremental.development_scenario_ids)
        & set(incremental.holdout_scenario_ids)
    ):
        raise ValueError(
            'Incremental development/holdout overlap'
        )

    previous_scenarios = ()

    if previous is not None:
        if (
            previous.benchmark_manifest_sha256
            != incremental.benchmark_manifest_sha256
        ):
            raise ValueError(
                'Benchmark provenance changed between racing rounds'
            )

        if previous.holdout_scenario_ids != (
            incremental.holdout_scenario_ids
        ):
            raise ValueError(
                'Holdout partition changed between racing rounds'
            )

        if previous.seeds != incremental.seeds:
            raise ValueError(
                'Seeds changed between racing rounds'
            )

        previous_scenarios = (
            previous.development_scenario_ids
        )

        if (
            set(previous_scenarios)
            & set(incremental.development_scenario_ids)
        ):
            raise ValueError(
                'Incremental racing evidence reran an earlier scenario'
            )

    expected_cumulative = (
        previous_scenarios
        + incremental.development_scenario_ids
    )

    if expected_cumulative != cumulative_scenario_ids:
        raise ValueError(
            'Cumulative scenario order differs from racing plan'
        )

    previous_observation_map = {}

    if previous is not None:
        for observation in previous.trial_observations:
            if (
                observation.candidate_id
                not in incoming_candidate_ids
            ):
                continue

            key = (
                observation.candidate_id,
                observation.scenario_id,
                observation.run_seed,
            )

            if key in previous_observation_map:
                raise ValueError(
                    'Duplicate previous racing observation'
                )

            previous_observation_map[key] = observation

    incremental_observation_map = {}

    for observation in incremental.trial_observations:
        key = (
            observation.candidate_id,
            observation.scenario_id,
            observation.run_seed,
        )

        if key in incremental_observation_map:
            raise ValueError(
                'Duplicate incremental racing observation'
            )

        incremental_observation_map[key] = observation

    merged_observations = []

    for candidate_id in incoming_candidate_ids:
        for scenario_id in cumulative_scenario_ids:
            for seed in incremental.seeds:
                key = (
                    candidate_id,
                    scenario_id,
                    seed,
                )

                source = (
                    incremental_observation_map
                    if scenario_id
                    in incremental.development_scenario_ids
                    else previous_observation_map
                )

                observation = source.get(key)

                if observation is None:
                    raise ValueError(
                        'Cumulative racing evidence is not a '
                        'complete paired matrix'
                    )

                merged_observations.append(observation)

    templates = {
        summary.candidate_id: summary
        for summary in incremental.candidate_summaries
    }

    summaries = []

    per_candidate = (
        len(cumulative_scenario_ids)
        * len(incremental.seeds)
    )

    for candidate_id in incoming_candidate_ids:
        candidate_observations = tuple(
            observation
            for observation in merged_observations
            if observation.candidate_id == candidate_id
        )

        if len(candidate_observations) != per_candidate:
            raise ValueError(
                'Candidate cumulative cardinality mismatch'
            )

        summaries.append(
            _rebuild_summary(
                templates[candidate_id],
                candidate_observations,
            )
        )

    expected_trials = (
        len(incoming_candidate_ids)
        * len(cumulative_scenario_ids)
        * len(incremental.seeds)
    )

    if len(merged_observations) != expected_trials:
        raise ValueError(
            'Merged racing trial cardinality mismatch'
        )

    return TuningStudyResults(
        output_root=incremental.output_root,
        benchmark_manifest_sha256=
            incremental.benchmark_manifest_sha256,
        development_scenario_ids=
            cumulative_scenario_ids,
        holdout_scenario_ids=
            incremental.holdout_scenario_ids,
        seeds=incremental.seeds,
        candidate_summaries=tuple(summaries),
        trial_observations=tuple(merged_observations),
        expected_trials=expected_trials,
        completed_trials=expected_trials,
    )


def subset_tuning_results(
    results: TuningStudyResults,
    *,
    candidate_ids: tuple[str, ...],
    scenario_ids: tuple[str, ...],
) -> TuningStudyResults:
    """Create a complete paired evidence subset with rebuilt summaries."""
    if not isinstance(results, TuningStudyResults):
        raise TypeError('Expected TuningStudyResults')

    if (
        not isinstance(candidate_ids, tuple)
        or not candidate_ids
        or len(set(candidate_ids)) != len(candidate_ids)
    ):
        raise ValueError(
            'candidate_ids must be a unique nonempty tuple'
        )

    if (
        not isinstance(scenario_ids, tuple)
        or not scenario_ids
        or len(set(scenario_ids)) != len(scenario_ids)
    ):
        raise ValueError(
            'scenario_ids must be a unique nonempty tuple'
        )

    available_candidates = tuple(
        summary.candidate_id
        for summary in results.candidate_summaries
    )

    if any(
        candidate_id not in available_candidates
        for candidate_id in candidate_ids
    ):
        raise ValueError('Unknown candidate in evidence subset')

    if any(
        scenario_id not in results.development_scenario_ids
        for scenario_id in scenario_ids
    ):
        raise ValueError('Unknown development scenario in evidence subset')

    candidate_order = {
        candidate_id: index
        for index, candidate_id
        in enumerate(available_candidates)
    }

    if tuple(
        sorted(
            candidate_ids,
            key=candidate_order.__getitem__,
        )
    ) != candidate_ids:
        raise ValueError(
            'Candidate subset must preserve frozen order'
        )

    scenario_order = {
        scenario_id: index
        for index, scenario_id
        in enumerate(results.development_scenario_ids)
    }

    if tuple(
        sorted(
            scenario_ids,
            key=scenario_order.__getitem__,
        )
    ) != scenario_ids:
        raise ValueError(
            'Scenario subset must preserve source evidence order'
        )

    observation_map = {}

    for observation in results.trial_observations:
        key = (
            observation.candidate_id,
            observation.scenario_id,
            observation.run_seed,
        )

        if key in observation_map:
            raise ValueError(
                'Duplicate observation in source evidence'
            )

        observation_map[key] = observation

    observations = []

    for candidate_id in candidate_ids:
        for scenario_id in scenario_ids:
            for seed in results.seeds:
                key = (
                    candidate_id,
                    scenario_id,
                    seed,
                )

                observation = observation_map.get(key)

                if observation is None:
                    raise ValueError(
                        'Evidence subset is not a complete paired matrix'
                    )

                observations.append(observation)

    templates = {
        summary.candidate_id: summary
        for summary in results.candidate_summaries
    }

    summaries = []

    for candidate_id in candidate_ids:
        candidate_observations = tuple(
            observation
            for observation in observations
            if observation.candidate_id == candidate_id
        )

        summaries.append(
            _rebuild_summary(
                templates[candidate_id],
                candidate_observations,
            )
        )

    expected_trials = (
        len(candidate_ids)
        * len(scenario_ids)
        * len(results.seeds)
    )

    if len(observations) != expected_trials:
        raise ValueError(
            'Evidence subset trial cardinality mismatch'
        )

    return TuningStudyResults(
        output_root=results.output_root,
        benchmark_manifest_sha256=
            results.benchmark_manifest_sha256,
        development_scenario_ids=scenario_ids,
        holdout_scenario_ids=
            results.holdout_scenario_ids,
        seeds=results.seeds,
        candidate_summaries=tuple(summaries),
        trial_observations=tuple(observations),
        expected_trials=expected_trials,
        completed_trials=expected_trials,
    )
