"""C7.2b: paired, development-only, non-scalar candidate selection."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType

from arena.evaluation.performance import PerformanceVector

from .execution import TuningStudyResults


_STRUCTURAL_STATUSES = frozenset({
    'constructor_invalid',
    'constructor_infeasible',
    'constructor_unsearchable',
})


class MetricDirection(str, Enum):
    MINIMIZE = 'minimize'
    MAXIMIZE = 'maximize'


@dataclass(frozen=True, slots=True)
class SelectionMetric:
    name: str
    direction: MetricDirection

    def __post_init__(self) -> None:
        if (
            not isinstance(self.name, str)
            or not self.name
            or self.name not in PerformanceVector.__dataclass_fields__
        ):
            raise ValueError(
                'Selection metrics must name a PerformanceVector field'
            )

        if not isinstance(self.direction, MetricDirection):
            raise ValueError(
                'direction must be a MetricDirection'
            )


@dataclass(frozen=True, slots=True)
class SelectionPolicy:
    metrics: tuple[SelectionMetric, ...]
    max_timeout_rate: float = 0.0
    max_failure_rate: float = 0.0
    require_zero_hard_violations: bool = True
    require_zero_canonical_infeasibilities: bool = True
    reject_unresolved_cells: bool = True

    def __post_init__(self) -> None:
        if (
            not isinstance(self.metrics, tuple)
            or not self.metrics
            or any(
                not isinstance(metric, SelectionMetric)
                for metric in self.metrics
            )
        ):
            raise ValueError(
                'metrics must be a nonempty tuple of SelectionMetric'
            )

        names = tuple(metric.name for metric in self.metrics)

        if len(set(names)) != len(names):
            raise ValueError('Duplicate selection metric')

        for name in (
            'max_timeout_rate',
            'max_failure_rate',
        ):
            value = getattr(self, name)

            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or value < 0
                or value > 1
            ):
                raise ValueError(
                    f'{name} must lie in [0, 1]'
                )

        for name in (
            'require_zero_hard_violations',
            'require_zero_canonical_infeasibilities',
            'reject_unresolved_cells',
        ):
            if type(getattr(self, name)) is not bool:
                raise ValueError(f'{name} must be boolean')


@dataclass(frozen=True, slots=True)
class ParetoSelectionResult:
    policy: SelectionPolicy
    eligible_candidate_ids: tuple[str, ...]
    excluded_candidates: MappingProxyType
    structurally_unscorable_cells: tuple[tuple[str, int], ...]
    externally_proven_structural_cells: tuple[tuple[str, int], ...]
    unresolved_cells: tuple[tuple[str, int], ...]
    paired_quality_cells: tuple[tuple[str, int], ...]
    active_metrics: tuple[SelectionMetric, ...]
    inactive_metrics: tuple[SelectionMetric, ...]
    metric_observation_counts: MappingProxyType
    pareto_candidate_ids: tuple[str, ...]


C7_V1_SELECTION_POLICY = SelectionPolicy(
    metrics=(
        SelectionMetric(
            'deadline_miss_rate',
            MetricDirection.MINIMIZE,
        ),
        SelectionMetric(
            'mean_lateness_days',
            MetricDirection.MINIMIZE,
        ),
        SelectionMetric(
            'priority_inversion_rate',
            MetricDirection.MINIMIZE,
        ),
        SelectionMetric(
            'unapproved_excess_session_count',
            MetricDirection.MINIMIZE,
        ),
        SelectionMetric(
            'fragmented_item_rate',
            MetricDirection.MINIMIZE,
        ),
        SelectionMetric(
            'mean_dependency_wait_days',
            MetricDirection.MINIMIZE,
        ),
        SelectionMetric(
            'mean_movement_days',
            MetricDirection.MINIMIZE,
        ),
        SelectionMetric(
            'mean_start_delay_days',
            MetricDirection.MINIMIZE,
        ),
    ),
    max_timeout_rate=0.0,
    max_failure_rate=0.0,
    require_zero_hard_violations=True,
    require_zero_canonical_infeasibilities=True,
    reject_unresolved_cells=True,
)


def _mean(values):
    return sum(values) / len(values)


def _dominates(
    first_id: str,
    second_id: str,
    metrics: tuple[SelectionMetric, ...],
    means: dict[str, dict[str, float]],
) -> bool:
    strictly_better = False

    for metric in metrics:
        a = means[first_id][metric.name]
        b = means[second_id][metric.name]

        if metric.direction is MetricDirection.MINIMIZE:
            if a > b:
                return False
            if a < b:
                strictly_better = True
        else:
            if a < b:
                return False
            if a > b:
                strictly_better = True

    return strictly_better


def select_pareto_candidates(
    results: TuningStudyResults,
    policy: SelectionPolicy,
    *,
    externally_proven_structural_cells: tuple[tuple[str, int], ...] = (),
) -> ParetoSelectionResult:
    """Select strict Pareto survivors from the same paired workload cells.

    Cells for which every candidate reports a structural constructor status
    are explicitly reported and excluded from quality comparison.

    A cell for which nobody succeeds but at least one candidate timed out or
    errored is unresolved. The frozen C7 policy rejects such a study rather
    than silently dropping the cell and rewarding algorithms that exceeded
    the experiment budget.

    On cells solved by at least one candidate, candidate-specific timeout or
    failure rates are eligibility gates. Quality metrics are then aggregated
    only over cells on which every eligible candidate succeeded. Each metric
    itself uses only cells where that metric is defined for every eligible
    candidate, so all Pareto comparisons are genuinely paired.

    There is no weighted score, epsilon, runtime tie-break, C4 objective
    comparison, or hidden ranking.
    """
    if not isinstance(results, TuningStudyResults):
        raise TypeError('Expected TuningStudyResults')

    if not isinstance(policy, SelectionPolicy):
        raise TypeError('Expected SelectionPolicy')

    summaries = results.candidate_summaries

    candidate_ids = tuple(
        summary.candidate_id
        for summary in summaries
    )

    if len(set(candidate_ids)) != len(candidate_ids):
        raise ValueError('Duplicate candidate ID in tuning results')

    expected_cells = tuple(
        (scenario_id, seed)
        for scenario_id in results.development_scenario_ids
        for seed in results.seeds
    )

    if not isinstance(
        externally_proven_structural_cells,
        tuple,
    ):
        raise TypeError(
            'externally_proven_structural_cells must be a tuple'
        )

    if any(
        not isinstance(cell, tuple)
        or len(cell) != 2
        or not isinstance(cell[0], str)
        or not cell[0]
        or type(cell[1]) is not int
        for cell in externally_proven_structural_cells
    ):
        raise ValueError(
            'Externally proven structural cells must be '
            '(scenario_id, seed) tuples'
        )

    if (
        len(set(externally_proven_structural_cells))
        != len(externally_proven_structural_cells)
    ):
        raise ValueError(
            'Duplicate externally proven structural cell'
        )

    expected_cell_set = set(expected_cells)

    if any(
        cell not in expected_cell_set
        for cell in externally_proven_structural_cells
    ):
        raise ValueError(
            'Externally proven structural cell is outside '
            'the development matrix'
        )

    externally_proven_set = set(
        externally_proven_structural_cells
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
                'Duplicate candidate/scenario/seed observation'
            )

        observation_map[key] = observation

    expected_observation_count = (
        len(candidate_ids)
        * len(expected_cells)
    )

    if len(observation_map) != expected_observation_count:
        raise ValueError(
            'Tuning observations do not form a complete paired matrix'
        )

    structural_cells = []
    externally_proven_cells = []
    unresolved_cells = []
    scorable_cells = []

    for scenario_id, seed in expected_cells:
        cell = [
            observation_map[
                (
                    candidate_id,
                    scenario_id,
                    seed,
                )
            ]
            for candidate_id in candidate_ids
        ]

        statuses = tuple(
            observation.status
            for observation in cell
        )

        cell_key = (scenario_id, seed)

        if cell_key in externally_proven_set:
            if 'ok' in statuses:
                raise ValueError(
                    'Independent structural-feasibility proof '
                    'contradicts a successful candidate observation'
                )

            structural_cells.append(cell_key)
            externally_proven_cells.append(cell_key)

        elif 'ok' in statuses:
            scorable_cells.append(cell_key)

        elif all(
            status in _STRUCTURAL_STATUSES
            for status in statuses
        ):
            structural_cells.append(cell_key)

        else:
            unresolved_cells.append(cell_key)

    if (
        unresolved_cells
        and policy.reject_unresolved_cells
    ):
        raise ValueError(
            'Study contains unresolved cells with no successful '
            'candidate; increase/calibrate runtime budgets or repair '
            'experiment failures before selection'
        )

    if not scorable_cells:
        raise ValueError(
            'Study contains no scorable development cells'
        )

    excluded = {}
    eligible = []

    for candidate_id in candidate_ids:
        candidate_observations = [
            observation_map[
                (
                    candidate_id,
                    scenario_id,
                    seed,
                )
            ]
            for scenario_id, seed in scorable_cells
        ]

        timeouts = sum(
            observation.status == 'wall_timeout'
            for observation in candidate_observations
        )

        failures = sum(
            observation.status != 'ok'
            and observation.status != 'wall_timeout'
            for observation in candidate_observations
        )

        denominator = len(candidate_observations)

        if (
            timeouts / denominator
            > policy.max_timeout_rate
        ):
            excluded[candidate_id] = 'timeout_rate'
            continue

        if (
            failures / denominator
            > policy.max_failure_rate
        ):
            excluded[candidate_id] = 'failure_rate'
            continue

        bad_hard = False
        bad_canonical = False

        for observation in candidate_observations:
            if observation.status != 'ok':
                continue

            performance = observation.performance

            if performance is None:
                raise ValueError(
                    'Successful observation missing C1 performance'
                )

            if (
                policy.require_zero_hard_violations
                and performance.get(
                    'hard_violation_count',
                    0.0,
                ) != 0.0
            ):
                bad_hard = True

            if (
                policy.require_zero_canonical_infeasibilities
                and performance.get(
                    'canonical_infeasibility_count',
                    0.0,
                ) != 0.0
            ):
                bad_canonical = True

        if bad_hard:
            excluded[candidate_id] = 'hard_violations'
            continue

        if bad_canonical:
            excluded[candidate_id] = 'canonical_infeasibility'
            continue

        eligible.append(candidate_id)

    eligible_ids = tuple(eligible)

    if not eligible_ids:
        return ParetoSelectionResult(
            policy=policy,
            eligible_candidate_ids=(),
            excluded_candidates=MappingProxyType(
                dict(excluded)
            ),
            structurally_unscorable_cells=tuple(
                structural_cells
            ),
            externally_proven_structural_cells=tuple(
                externally_proven_cells
            ),
            unresolved_cells=tuple(
                unresolved_cells
            ),
            paired_quality_cells=(),
            active_metrics=(),
            inactive_metrics=tuple(policy.metrics),
            metric_observation_counts=MappingProxyType({}),
            pareto_candidate_ids=(),
        )

    paired_cells = tuple(
        (scenario_id, seed)
        for scenario_id, seed in scorable_cells
        if all(
            observation_map[
                (
                    candidate_id,
                    scenario_id,
                    seed,
                )
            ].status == 'ok'
            for candidate_id in eligible_ids
        )
    )

    if not paired_cells:
        raise ValueError(
            'Eligible candidates have no common successful quality cells'
        )

    metric_means = {
        candidate_id: {}
        for candidate_id in eligible_ids
    }

    metric_counts = {}
    active = []
    inactive = []

    for metric in policy.metrics:
        metric_cells = tuple(
            (scenario_id, seed)
            for scenario_id, seed in paired_cells
            if all(
                observation_map[
                    (
                        candidate_id,
                        scenario_id,
                        seed,
                    )
                ].performance is not None
                and metric.name in observation_map[
                    (
                        candidate_id,
                        scenario_id,
                        seed,
                    )
                ].performance
                for candidate_id in eligible_ids
            )
        )

        if not metric_cells:
            inactive.append(metric)
            continue

        active.append(metric)
        metric_counts[metric.name] = len(metric_cells)

        for candidate_id in eligible_ids:
            values = [
                observation_map[
                    (
                        candidate_id,
                        scenario_id,
                        seed,
                    )
                ].performance[metric.name]
                for scenario_id, seed in metric_cells
            ]

            metric_means[candidate_id][
                metric.name
            ] = _mean(values)

    active_metrics = tuple(active)
    inactive_metrics = tuple(inactive)

    if not active_metrics:
        raise ValueError(
            'No configured metric has paired comparable coverage'
        )

    survivors = []

    for candidate_id in eligible_ids:
        dominated = any(
            other_id != candidate_id
            and _dominates(
                other_id,
                candidate_id,
                active_metrics,
                metric_means,
            )
            for other_id in eligible_ids
        )

        if not dominated:
            survivors.append(candidate_id)

    return ParetoSelectionResult(
        policy=policy,
        eligible_candidate_ids=eligible_ids,
        excluded_candidates=MappingProxyType(
            dict(excluded)
        ),
        structurally_unscorable_cells=tuple(
            structural_cells
        ),
        externally_proven_structural_cells=tuple(
            externally_proven_cells
        ),
        unresolved_cells=tuple(
            unresolved_cells
        ),
        paired_quality_cells=paired_cells,
        active_metrics=active_metrics,
        inactive_metrics=inactive_metrics,
        metric_observation_counts=MappingProxyType(
            dict(metric_counts)
        ),
        pareto_candidate_ids=tuple(survivors),
    )
