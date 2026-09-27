"""C9.1 workload-response analysis over frozen development evidence only."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from math import sqrt
from statistics import mean
from types import MappingProxyType

from .execution import (
    TuningStudyResults,
)


@dataclass(frozen=True, slots=True)
class ScenarioResponse:
    scenario_id: str
    status: str
    active_metrics: tuple[str, ...]
    pareto_candidate_ids: tuple[str, ...]
    metric_leaders: MappingProxyType
    candidate_metric_means: MappingProxyType


def _dominates(
    left: dict[str, float],
    right: dict[str, float],
    metrics: tuple[str, ...],
) -> bool:
    return (
        all(
            left[name] <= right[name]
            for name in metrics
        )
        and any(
            left[name] < right[name]
            for name in metrics
        )
    )


def _population_std(
    values: list[float],
) -> float:
    if not values:
        return 0.0

    mu = mean(values)

    return sqrt(
        sum(
            (value - mu) ** 2
            for value in values
        )
        / len(values)
    )


def analyze_workload_responses(
    results: TuningStudyResults,
    *,
    candidate_ids: tuple[str, ...],
    active_metrics: tuple[str, ...],
) -> tuple[ScenarioResponse, ...]:
    if not candidate_ids:
        raise ValueError(
            'candidate_ids must be nonempty'
        )

    if len(set(candidate_ids)) != len(candidate_ids):
        raise ValueError(
            'candidate_ids must be unique'
        )

    if not active_metrics:
        raise ValueError(
            'active_metrics must be nonempty'
        )

    by_cell = {}

    for observation in results.trial_observations:
        key = (
            observation.candidate_id,
            observation.scenario_id,
            observation.run_seed,
        )

        if key in by_cell:
            raise ValueError(
                'Duplicate workload-analysis cell'
            )

        by_cell[key] = observation

    responses = []

    for scenario_id in (
        results.development_scenario_ids
    ):
        statuses = []

        for candidate_id in candidate_ids:
            for seed in results.seeds:
                observation = by_cell.get(
                    (
                        candidate_id,
                        scenario_id,
                        seed,
                    )
                )

                if observation is None:
                    raise ValueError(
                        'Incomplete workload-response matrix'
                    )

                statuses.append(
                    observation.status
                )

        if all(
            status == 'wall_timeout'
            for status in statuses
        ):
            responses.append(
                ScenarioResponse(
                    scenario_id=scenario_id,
                    status='common_mode_timeout',
                    active_metrics=(),
                    pareto_candidate_ids=(),
                    metric_leaders=
                        MappingProxyType({}),
                    candidate_metric_means=
                        MappingProxyType({}),
                )
            )

            continue

        if not all(
            status == 'ok'
            for status in statuses
        ):
            raise ValueError(
                f'Unresolved mixed-status development '
                f'workload: {scenario_id}'
            )

        scenario_active_metrics = tuple(
            metric
            for metric in active_metrics
            if all(
                (
                    by_cell[
                        (
                            candidate_id,
                            scenario_id,
                            seed,
                        )
                    ].performance
                    is not None
                )
                and (
                    metric
                    in by_cell[
                        (
                            candidate_id,
                            scenario_id,
                            seed,
                        )
                    ].performance
                )
                for candidate_id in candidate_ids
                for seed in results.seeds
            )
        )

        if not scenario_active_metrics:
            raise ValueError(
                f'No common active C1 metrics for '
                f'scorable workload: {scenario_id}'
            )

        candidate_means = {}

        for candidate_id in candidate_ids:
            values = {
                metric: []
                for metric
                in scenario_active_metrics
            }

            for seed in results.seeds:
                observation = by_cell[
                    (
                        candidate_id,
                        scenario_id,
                        seed,
                    )
                ]

                if observation.performance is None:
                    raise ValueError(
                        'Successful workload cell '
                        'missing C1 performance'
                    )

                for metric in scenario_active_metrics:
                    values[metric].append(
                        float(
                            observation
                            .performance[metric]
                        )
                    )

            candidate_means[
                candidate_id
            ] = {
                metric: mean(entries)
                for metric, entries
                in values.items()
            }

        pareto = []

        for candidate_id in candidate_ids:
            dominated = any(
                _dominates(
                    candidate_means[other],
                    candidate_means[
                        candidate_id
                    ],
                    scenario_active_metrics,
                )
                for other in candidate_ids
                if other != candidate_id
            )

            if not dominated:
                pareto.append(
                    candidate_id
                )

        metric_leaders = {}

        for metric in scenario_active_metrics:
            best = min(
                candidate_means[
                    candidate_id
                ][metric]
                for candidate_id
                in candidate_ids
            )

            metric_leaders[metric] = tuple(
                candidate_id
                for candidate_id
                in candidate_ids
                if candidate_means[
                    candidate_id
                ][metric] == best
            )

        responses.append(
            ScenarioResponse(
                scenario_id=scenario_id,
                status='scorable',
                active_metrics=
                    scenario_active_metrics,
                pareto_candidate_ids=
                    tuple(pareto),
                metric_leaders=
                    MappingProxyType(
                        metric_leaders
                    ),
                candidate_metric_means=
                    MappingProxyType({
                        candidate_id:
                            MappingProxyType(
                                values
                            )
                        for candidate_id, values
                        in candidate_means.items()
                    }),
            )
        )

    return tuple(responses)


def summarize_workload_responses(
    responses: tuple[ScenarioResponse, ...],
    *,
    candidate_ids: tuple[str, ...],
    labels: dict[str, str],
    features_by_scenario:
        dict[str, dict[str, float | int | None]],
    metadata_by_scenario:
        dict[str, dict],
    active_metrics: tuple[str, ...],
) -> dict:
    if set(labels) != set(candidate_ids):
        raise ValueError(
            'labels must exactly cover candidates'
        )

    scorable = tuple(
        response
        for response in responses
        if response.status == 'scorable'
    )

    coverage_gaps = tuple(
        response.scenario_id
        for response in responses
        if response.status
        == 'common_mode_timeout'
    )

    if not scorable:
        raise ValueError(
            'No scorable development workloads'
        )

    for response in scorable:
        if (
            response.scenario_id
            not in features_by_scenario
        ):
            raise ValueError(
                'Missing frozen workload features'
            )

    pareto_counts = {
        candidate_id: 0
        for candidate_id in candidate_ids
    }

    metric_leader_counts = {
        candidate_id: {
            metric: 0
            for metric in active_metrics
        }
        for candidate_id in candidate_ids
    }

    pairwise_dominance = {
        left: {
            right: 0
            for right in candidate_ids
            if right != left
        }
        for left in candidate_ids
    }

    for response in scorable:
        for candidate_id in (
            response.pareto_candidate_ids
        ):
            pareto_counts[
                candidate_id
            ] += 1

        for metric, leaders in (
            response.metric_leaders.items()
        ):
            for candidate_id in leaders:
                metric_leader_counts[
                    candidate_id
                ][metric] += 1

        for left in candidate_ids:
            for right in candidate_ids:
                if left == right:
                    continue

                if _dominates(
                    response
                    .candidate_metric_means[left],
                    response
                    .candidate_metric_means[right],
                    response.active_metrics,
                ):
                    pairwise_dominance[
                        left
                    ][right] += 1

    numeric_feature_names = sorted({
        name
        for response in scorable
        for name, value in (
            features_by_scenario[
                response.scenario_id
            ].items()
        )
        if (
            value is not None
            and type(value)
            in (int, float)
        )
    })

    feature_associations = {}

    for candidate_id in candidate_ids:
        in_pareto = {
            response.scenario_id
            for response in scorable
            if candidate_id
            in response.pareto_candidate_ids
        }

        rows = []

        for feature in numeric_feature_names:
            yes = []
            no = []

            for response in scorable:
                value = (
                    features_by_scenario[
                        response.scenario_id
                    ].get(feature)
                )

                if (
                    value is None
                    or type(value)
                    not in (int, float)
                ):
                    continue

                target = (
                    yes
                    if response.scenario_id
                    in in_pareto
                    else no
                )

                target.append(
                    float(value)
                )

            if not yes or not no:
                continue

            all_values = yes + no
            std = _population_std(
                all_values
            )

            if std == 0.0:
                continue

            effect = (
                mean(yes) - mean(no)
            ) / std

            rows.append({
                'feature': feature,
                'pareto_mean': mean(yes),
                'nonpareto_mean': mean(no),
                'standardized_difference':
                    effect,
                'pareto_n': len(yes),
                'nonpareto_n': len(no),
            })

        rows.sort(
            key=lambda row:
                (
                    -abs(
                        row[
                            'standardized_difference'
                        ]
                    ),
                    row['feature'],
                )
        )

        feature_associations[
            candidate_id
        ] = rows[:12]

    by_design = defaultdict(
        list
    )

    for response in scorable:
        design = (
            response.scenario_id
            .split('-R', 1)[0]
        )

        by_design[design].append(
            response
        )

    replicate_jaccards = []

    for design, group in sorted(
        by_design.items()
    ):
        if len(group) != 2:
            continue

        left = set(
            group[0]
            .pareto_candidate_ids
        )

        right = set(
            group[1]
            .pareto_candidate_ids
        )

        union = left | right

        score = (
            len(left & right) / len(union)
            if union
            else 1.0
        )

        replicate_jaccards.append({
            'design_id': design,
            'scenario_ids': [
                group[0].scenario_id,
                group[1].scenario_id,
            ],
            'jaccard': score,
        })

    candidate_rows = []

    for candidate_id in candidate_ids:
        candidate_rows.append({
            'candidate_id': candidate_id,
            'label': labels[
                candidate_id
            ],
            'pareto_scenario_count':
                pareto_counts[
                    candidate_id
                ],
            'pareto_scenario_fraction':
                pareto_counts[
                    candidate_id
                ] / len(scorable),
            'metric_leader_counts':
                metric_leader_counts[
                    candidate_id
                ],
            'pairwise_dominance_counts':
                pairwise_dominance[
                    candidate_id
                ],
            'top_feature_associations':
                feature_associations[
                    candidate_id
                ],
        })

    scenario_rows = []

    for response in responses:
        scenario_rows.append({
            'scenario_id':
                response.scenario_id,
            'status':
                response.status,
            'active_metrics':
                list(
                    response.active_metrics
                ),
            'pareto_candidate_ids':
                list(
                    response
                    .pareto_candidate_ids
                ),
            'pareto_labels': [
                labels[
                    candidate_id
                ]
                for candidate_id
                in response
                .pareto_candidate_ids
            ],
            'metric_leaders': {
                metric: list(
                    leaders
                )
                for metric, leaders
                in response
                .metric_leaders.items()
            },
            'candidate_metric_means': {
                candidate_id:
                    dict(values)
                for candidate_id, values
                in response
                .candidate_metric_means.items()
            },
            'features':
                features_by_scenario.get(
                    response.scenario_id,
                    {},
                ),
            'benchmark_metadata':
                metadata_by_scenario.get(
                    response.scenario_id,
                    {},
                ),
        })

    return {
        'schema_version': 1,
        'stage': 'C9.1',
        'purpose':
            'development_workload_response_analysis',
        'holdout_used_for_training':
            False,
        'holdout_result_read':
            False,
        'scalar_candidate_score_used':
            False,
        'selector_frozen':
            False,
        'candidate_count':
            len(candidate_ids),
        'development_scenario_count':
            len(responses),
        'scorable_scenario_count':
            len(scorable),
        'common_mode_coverage_gap_count':
            len(coverage_gaps),
        'common_mode_coverage_gap_scenarios':
            list(coverage_gaps),
        'active_metrics':
            list(active_metrics),
        'candidates':
            candidate_rows,
        'scenario_responses':
            scenario_rows,
        'replicate_consistency': {
            'paired_design_count':
                len(
                    replicate_jaccards
                ),
            'mean_pareto_jaccard': (
                mean(
                    row['jaccard']
                    for row
                    in replicate_jaccards
                )
                if replicate_jaccards
                else None
            ),
            'pairs':
                replicate_jaccards,
        },
    }
