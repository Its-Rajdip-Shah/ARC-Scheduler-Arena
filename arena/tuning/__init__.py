"""C7 tuning-study planning, execution, and development-result inspection."""
from .study import (
    TuningAxis, ConstructorSweep, ImproverSweep, TuningStudySpec,
    TuningCandidate, TuningStudyPlan, plan_tuning_study, write_tuning_plan,
)

__all__ = [
    'TuningAxis', 'ConstructorSweep', 'ImproverSweep', 'TuningStudySpec',
    'TuningCandidate', 'TuningStudyPlan', 'plan_tuning_study', 'write_tuning_plan',
]

from .execution import (
    TuningExecutionResult,
    TuningCandidateSummary,
    TuningTrialObservation,
    TuningStudyResults,
    execute_tuning_study,
    load_tuning_results,
)

__all__ += [
    'TuningExecutionResult',
    'TuningCandidateSummary',
    'TuningTrialObservation',
    'TuningStudyResults',
    'execute_tuning_study',
    'load_tuning_results',
]

from .selection import (
    MetricDirection,
    SelectionMetric,
    SelectionPolicy,
    ParetoSelectionResult,
    C7_V1_SELECTION_POLICY,
    select_pareto_candidates,
)
from .design import (
    C7_V1_SPLIT_SEED,
    C7_V1_DEVELOPMENT_DESIGN_COUNT,
    C7_PARALLEL_SAFETY_WALL_SECONDS,
    C7_CALIBRATION_SEEDS,
    C7_CALIBRATION_TRIAL_WALL_SECONDS,
    C7_CALIBRATION_CANDIDATE_COUNT,
    C7_CALIBRATION_EXPECTED_TRIALS,
    calibration_objective,
    build_c7_calibration_spec,
    C7_BUDGET_PROBE_SEEDS,
    C7_BUDGET_PROBE_TRIAL_WALL_SECONDS,
    C7_BUDGET_PROBE_CANDIDATE_COUNT,
    C7_BUDGET_PROBE_EXPECTED_TRIALS,
    build_c7_budget_probe_spec,
)

__all__ += [
    'MetricDirection',
    'SelectionMetric',
    'SelectionPolicy',
    'ParetoSelectionResult',
    'C7_V1_SELECTION_POLICY',
    'select_pareto_candidates',
    'C7_V1_SPLIT_SEED',
    'C7_V1_DEVELOPMENT_DESIGN_COUNT',
    'C7_PARALLEL_SAFETY_WALL_SECONDS',
    'C7_CALIBRATION_SEEDS',
    'C7_CALIBRATION_TRIAL_WALL_SECONDS',
    'C7_CALIBRATION_CANDIDATE_COUNT',
    'C7_CALIBRATION_EXPECTED_TRIALS',
    'calibration_objective',
    'build_c7_calibration_spec',
    'C7_BUDGET_PROBE_SEEDS',
    'C7_BUDGET_PROBE_TRIAL_WALL_SECONDS',
    'C7_BUDGET_PROBE_CANDIDATE_COUNT',
    'C7_BUDGET_PROBE_EXPECTED_TRIALS',
    'build_c7_budget_probe_spec',
]

from .parallel_execution import execute_tuning_study_parallel

__all__ += [
    'execute_tuning_study_parallel',
]

from .racing import (
    RacingRoundSpec,
    RacingRoundDecision,
    tuning_results_fingerprint,
    decide_racing_round,
    racing_decision_artifact,
    write_racing_decision,
)

__all__ += [
    'RacingRoundSpec',
    'RacingRoundDecision',
    'tuning_results_fingerprint',
    'decide_racing_round',
    'racing_decision_artifact',
    'write_racing_decision',
]

from .racing_campaign import (
    RacingFidelityStage,
    RacingCampaignSpec,
    RacingRoundPlan,
    campaign_fingerprint,
    build_racing_round_plan,
    next_round_plan,
    racing_campaign_artifact,
    racing_round_plan_artifact,
    write_racing_campaign,
    write_racing_round_plan,
)

__all__ += [
    'RacingFidelityStage',
    'RacingCampaignSpec',
    'RacingRoundPlan',
    'campaign_fingerprint',
    'build_racing_round_plan',
    'next_round_plan',
    'racing_campaign_artifact',
    'racing_round_plan_artifact',
    'write_racing_campaign',
    'write_racing_round_plan',
]

from .racing_execution import (
    build_incremental_tuning_plan,
    merge_cumulative_tuning_results,
    subset_tuning_results,
)

__all__ += [
    'build_incremental_tuning_plan',
    'merge_cumulative_tuning_results',
    'subset_tuning_results',
]

from .confirmation import (
    ConfirmationCandidateLink,
    ConfirmationExecutionPlan,
    build_confirmation_subset_plan,
    relabel_confirmation_results,
    combine_seed_tuning_results,
)

__all__ += [
    'ConfirmationCandidateLink',
    'ConfirmationExecutionPlan',
    'build_confirmation_subset_plan',
    'relabel_confirmation_results',
    'combine_seed_tuning_results',
]

from .shortlist import (
    MetricWitness,
    DevelopmentShortlist,
    build_metric_witness_shortlist,
    shortlist_artifact,
)

__all__ += [
    'MetricWitness',
    'DevelopmentShortlist',
    'build_metric_witness_shortlist',
    'shortlist_artifact',
]

from .contestants import (
    FrozenContestant,
    C8ContestantField,
    freeze_c8_contestants,
    c8_contestant_artifact,
)

__all__ += [
    'FrozenContestant',
    'C8ContestantField',
    'freeze_c8_contestants',
    'c8_contestant_artifact',
]

from .faceoff import (
    C8_FACE_OFF_SEEDS,
    C8_TRIAL_WALL_SECONDS,
    C8CandidateLink,
    C8FaceoffPlan,
    build_c8_faceoff_plan,
    write_c8_faceoff_plan,
    execute_c8_faceoff,
    load_c8_faceoff_results,
    c8_metric_means,
)

__all__ += [
    'C8_FACE_OFF_SEEDS',
    'C8_TRIAL_WALL_SECONDS',
    'C8CandidateLink',
    'C8FaceoffPlan',
    'build_c8_faceoff_plan',
    'write_c8_faceoff_plan',
    'execute_c8_faceoff',
    'load_c8_faceoff_results',
    'c8_metric_means',
]

from .workload_analysis import (
    ScenarioResponse,
    analyze_workload_responses,
    summarize_workload_responses,
)

__all__ += [
    'ScenarioResponse',
    'analyze_workload_responses',
    'summarize_workload_responses',
]

from .workload_policy import (
    WorkloadPolicyRole,
    FrozenWorkloadPolicy,
    freeze_workload_policy,
    workload_policy_artifact,
)

__all__ += [
    'WorkloadPolicyRole',
    'FrozenWorkloadPolicy',
    'freeze_workload_policy',
    'workload_policy_artifact',
]
