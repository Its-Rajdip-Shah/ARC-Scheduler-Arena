"""C7.5 development shortlist from explicit C1 metric witnesses.

This module deliberately does not create an aggregate score or ranking.
A confirmed development candidate is shortlisted iff it attains the exact
best pooled paired mean on at least one active C1 selection metric.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType

from .execution import TuningStudyResults
from .selection import (
    MetricDirection,
    ParetoSelectionResult,
)


@dataclass(frozen=True, slots=True)
class MetricWitness:
    metric_name: str
    direction: MetricDirection
    best_value: float
    candidate_ids: tuple[str, ...]
    observation_count: int


@dataclass(frozen=True, slots=True)
class DevelopmentShortlist:
    source_candidate_ids: tuple[str, ...]
    shortlisted_candidate_ids: tuple[str, ...]
    metric_witnesses: tuple[MetricWitness, ...]
    candidate_metric_means: MappingProxyType
    paired_quality_cells: tuple[
        tuple[str, int],
        ...
    ]


def build_metric_witness_shortlist(
    results: TuningStudyResults,
    selection: ParetoSelectionResult,
    *,
    expected_candidate_ids: tuple[str, ...],
) -> DevelopmentShortlist:
    """Return exact metric leaders from a confirmed Pareto field.

    The rule is intentionally non-scalar:

    * use only the already-paired cells admitted by the frozen C1 selector;
    * reproduce the selector's metric-specific observation coverage;
    * compute one unweighted mean per candidate/metric;
    * retain every candidate tied for the exact best mean on any active metric.

    No cross-metric arithmetic, weights, normalization, epsilon, lexicographic
    order, runtime tie-break, or hidden ranking is used.
    """
    if not isinstance(
        results,
        TuningStudyResults,
    ):
        raise TypeError(
            'results must be TuningStudyResults'
        )

    if not isinstance(
        selection,
        ParetoSelectionResult,
    ):
        raise TypeError(
            'selection must be ParetoSelectionResult'
        )

    if (
        not isinstance(
            expected_candidate_ids,
            tuple,
        )
        or not expected_candidate_ids
        or len(set(expected_candidate_ids))
        != len(expected_candidate_ids)
    ):
        raise ValueError(
            'expected_candidate_ids must be '
            'a unique nonempty tuple'
        )

    if selection.unresolved_cells:
        raise ValueError(
            'Cannot shortlist with unresolved cells'
        )

    if (
        selection.eligible_candidate_ids
        != expected_candidate_ids
    ):
        raise ValueError(
            'Shortlist candidates must exactly match '
            'the eligible confirmed field'
        )

    if (
        selection.pareto_candidate_ids
        != expected_candidate_ids
    ):
        raise ValueError(
            'Shortlist source must be the complete '
            'confirmed Pareto field'
        )

    if not selection.active_metrics:
        raise ValueError(
            'No active C1 metrics for shortlist'
        )

    observation_map = {}

    for observation in (
        results.trial_observations
    ):
        key = (
            observation.candidate_id,
            observation.scenario_id,
            observation.run_seed,
        )

        if key in observation_map:
            raise ValueError(
                'Duplicate shortlist observation'
            )

        observation_map[key] = observation

    paired_cells = (
        selection.paired_quality_cells
    )

    means = {
        candidate_id: {}
        for candidate_id
        in expected_candidate_ids
    }

    witnesses = []

    for metric in selection.active_metrics:
        metric_cells = tuple(
            cell
            for cell in paired_cells
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
                in expected_candidate_ids
            )
        )

        expected_count = (
            selection
            .metric_observation_counts[
                metric.name
            ]
        )

        if (
            len(metric_cells)
            != expected_count
        ):
            raise ValueError(
                'Metric witness coverage differs '
                'from frozen selector coverage'
            )

        candidate_values = {}

        for candidate_id in (
            expected_candidate_ids
        ):
            values = tuple(
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
                in metric_cells
            )

            mean = sum(values) / len(values)

            means[candidate_id][
                metric.name
            ] = mean

            candidate_values[
                candidate_id
            ] = mean

        if (
            metric.direction
            is MetricDirection.MINIMIZE
        ):
            best = min(
                candidate_values.values()
            )
        else:
            best = max(
                candidate_values.values()
            )

        winners = tuple(
            candidate_id
            for candidate_id
            in expected_candidate_ids
            if candidate_values[
                candidate_id
            ] == best
        )

        if not winners:
            raise RuntimeError(
                'Metric witness produced no winner'
            )

        witnesses.append(
            MetricWitness(
                metric_name=metric.name,
                direction=metric.direction,
                best_value=best,
                candidate_ids=winners,
                observation_count=
                    len(metric_cells),
            )
        )

    shortlisted = {
        candidate_id
        for witness in witnesses
        for candidate_id
        in witness.candidate_ids
    }

    shortlisted_ids = tuple(
        candidate_id
        for candidate_id
        in expected_candidate_ids
        if candidate_id in shortlisted
    )

    if not shortlisted_ids:
        raise RuntimeError(
            'Metric-witness shortlist is empty'
        )

    frozen_means = MappingProxyType({
        candidate_id:
            MappingProxyType(
                dict(
                    means[candidate_id]
                )
            )
        for candidate_id
        in expected_candidate_ids
    })

    return DevelopmentShortlist(
        source_candidate_ids=
            expected_candidate_ids,
        shortlisted_candidate_ids=
            shortlisted_ids,
        metric_witnesses=
            tuple(witnesses),
        candidate_metric_means=
            frozen_means,
        paired_quality_cells=
            paired_cells,
    )


def shortlist_artifact(
    shortlist: DevelopmentShortlist,
    *,
    candidate_labels: dict[str, str],
) -> dict:
    if not isinstance(
        shortlist,
        DevelopmentShortlist,
    ):
        raise TypeError(
            'shortlist must be DevelopmentShortlist'
        )

    if (
        set(candidate_labels)
        != set(
            shortlist
            .source_candidate_ids
        )
    ):
        raise ValueError(
            'candidate_labels must exactly cover '
            'the shortlist source field'
        )

    witnesses_by_candidate = {
        candidate_id: []
        for candidate_id
        in shortlist
        .source_candidate_ids
    }

    for witness in (
        shortlist.metric_witnesses
    ):
        for candidate_id in (
            witness.candidate_ids
        ):
            witnesses_by_candidate[
                candidate_id
            ].append(
                witness.metric_name
            )

    return {
        'schema_version': 1,
        'stage': 'C7.5',
        'method':
            'exact_pooled_C1_metric_witnesses',
        'scalar_ranking_used': False,
        'epsilon_used': False,
        'runtime_tiebreak_used': False,
        'source_candidate_count':
            len(
                shortlist
                .source_candidate_ids
            ),
        'shortlist_candidate_count':
            len(
                shortlist
                .shortlisted_candidate_ids
            ),
        'paired_quality_cell_count':
            len(
                shortlist
                .paired_quality_cells
            ),
        'source_candidate_ids':
            list(
                shortlist
                .source_candidate_ids
            ),
        'shortlisted_candidate_ids':
            list(
                shortlist
                .shortlisted_candidate_ids
            ),
        'metric_witnesses': [
            {
                'metric_name':
                    witness.metric_name,
                'direction':
                    witness.direction.value,
                'best_value':
                    witness.best_value,
                'candidate_ids':
                    list(
                        witness
                        .candidate_ids
                    ),
                'candidate_labels': [
                    candidate_labels[
                        candidate_id
                    ]
                    for candidate_id
                    in witness
                    .candidate_ids
                ],
                'observation_count':
                    witness
                    .observation_count,
            }
            for witness
            in shortlist.metric_witnesses
        ],
        'candidates': [
            {
                'candidate_id':
                    candidate_id,
                'label':
                    candidate_labels[
                        candidate_id
                    ],
                'shortlisted':
                    candidate_id
                    in set(
                        shortlist
                        .shortlisted_candidate_ids
                    ),
                'witness_metrics':
                    witnesses_by_candidate[
                        candidate_id
                    ],
                'metric_means':
                    dict(
                        shortlist
                        .candidate_metric_means[
                            candidate_id
                        ]
                    ),
            }
            for candidate_id
            in shortlist
            .source_candidate_ids
        ],
    }
