"""C7.3: frozen development split and bounded family calibration design."""
from __future__ import annotations

from pathlib import Path

from arena.algorithms import (
    AggressiveEarlierGreedy,
    GreedyObjectiveConfig,
    HybridCostGreedy,
    PressureGreedy,
    StableRiskGreedy,
)
from arena.scheduling.objectives import (
    DeadlineRisk,
    MovementCost,
    OverloadCost,
    PowerCost,
    PriorityPostponement,
)
from arena.search import (
    AdaptiveLargeNeighbourhoodConfig,
    AdaptiveLargeNeighbourhoodSearch,
    DestroyOperator,
    HillClimbConfig,
    HillClimber,
    ImprovementStrategy,
    LargeNeighbourhoodConfig,
    LargeNeighbourhoodSearch,
    NeighbourhoodConfig,
    PlanObjectiveConfig,
    RepairOperator,
    SimulatedAnnealing,
    SimulatedAnnealingConfig,
    TabuConfig,
    TabuSearch,
    VariableNeighbourhoodConfig,
    VariableNeighbourhoodMode,
    VariableNeighbourhoodSearch,
)

from .study import (
    ConstructorSweep,
    ImproverSweep,
    TuningStudySpec,
)


C7_V1_SPLIT_SEED = 20260924
C7_V1_DEVELOPMENT_DESIGN_COUNT = 47

# Search families already have explicit deterministic iteration/evaluation
# ceilings. Future parallel C7 campaigns therefore use wall time only as a
# generous emergency fuse rather than as the algorithm's work allowance.
C7_PARALLEL_SAFETY_WALL_SECONDS = 120.0

C7_CALIBRATION_SEEDS = (1701,)
C7_CALIBRATION_TRIAL_WALL_SECONDS = 5.0

C7_CALIBRATION_CANDIDATE_COUNT = 32
C7_CALIBRATION_EXPECTED_TRIALS = 3008


def _priority_multipliers() -> dict[int, float]:
    """Cover every possible Benchmark V1 position with monotone weights."""
    maximum_position = 256
    return {
        position: (
            1.0
            + 3.0
            * (
                maximum_position - position
            )
            / (maximum_position - 1)
        )
        for position in range(
            1,
            maximum_position + 1,
        )
    }


def _priority(weight: float) -> PriorityPostponement:
    return PriorityPostponement(
        PowerCost(weight, 2.0),
        _priority_multipliers(),
        0.0,
    )


def calibration_objective() -> PlanObjectiveConfig:
    """Representative comparison objective for runtime/failure calibration.

    These are calibration parameters, not tuned production recommendations.
    The purpose is to exercise every search family on the same nondegenerate
    five-component objective before the full hyperparameter campaign.
    """
    return PlanObjectiveConfig(
        deadline=DeadlineRisk(
            PowerCost(8.0, 2.0),
            2.0,
        ),
        priority=_priority(2.0),
        overload=OverloadCost(
            PowerCost(12.0, 2.0),
            True,
        ),
        movement=MovementCost(
            2.0,
            PowerCost(1.0, 2.0),
        ),
        timing=PowerCost(1.0, 2.0),
    )


def _constructor_config(
    *,
    deadline_weight: float,
    priority_weight: float,
    overload_weight: float,
    movement_fixed: float,
    movement_distance: float,
    timing_weight: float,
) -> GreedyObjectiveConfig:
    return GreedyObjectiveConfig(
        deadline=DeadlineRisk(
            PowerCost(deadline_weight, 2.0),
            2.0,
        ),
        priority=_priority(priority_weight),
        overload=OverloadCost(
            PowerCost(overload_weight, 2.0),
            True,
        ),
        movement=MovementCost(
            movement_fixed,
            PowerCost(
                movement_distance,
                2.0,
            ),
        ),
        timing=PowerCost(
            timing_weight,
            2.0,
        ),
        horizon_days=30,
    )


def _constructors() -> tuple[ConstructorSweep, ...]:
    """One representative nondegenerate configuration per C3 family."""
    return (
        ConstructorSweep(
            'pressure',
            PressureGreedy(
                _constructor_config(
                    deadline_weight=8.0,
                    priority_weight=2.0,
                    overload_weight=12.0,
                    movement_fixed=1.0,
                    movement_distance=1.0,
                    timing_weight=1.0,
                )
            ),
            (),
        ),
        ConstructorSweep(
            'aggressive',
            AggressiveEarlierGreedy(
                _constructor_config(
                    deadline_weight=6.0,
                    priority_weight=3.0,
                    overload_weight=8.0,
                    movement_fixed=0.0,
                    movement_distance=0.0,
                    timing_weight=4.0,
                )
            ),
            (),
        ),
        ConstructorSweep(
            'stable',
            StableRiskGreedy(
                _constructor_config(
                    deadline_weight=8.0,
                    priority_weight=2.0,
                    overload_weight=10.0,
                    movement_fixed=8.0,
                    movement_distance=2.0,
                    timing_weight=0.5,
                )
            ),
            (),
        ),
        ConstructorSweep(
            'hybrid',
            HybridCostGreedy(
                _constructor_config(
                    deadline_weight=8.0,
                    priority_weight=3.0,
                    overload_weight=12.0,
                    movement_fixed=3.0,
                    movement_distance=1.0,
                    timing_weight=2.0,
                )
            ),
            (),
        ),
    )


def _improvers(
    objective: PlanObjectiveConfig,
) -> tuple[ImproverSweep, ...]:
    neighbourhood = NeighbourhoodConfig(
        horizon_days=30,
        max_relocation_distance_days=7,
    )

    return (
        ImproverSweep(
            'none',
            None,
            (),
        ),
        ImproverSweep(
            'hc',
            HillClimber(
                HillClimbConfig(
                    objective=objective,
                    neighbourhood=neighbourhood,
                    strategy=ImprovementStrategy.BEST,
                    max_iterations=12,
                    max_evaluations=160,
                )
            ),
            (),
        ),
        ImproverSweep(
            'vnd',
            VariableNeighbourhoodSearch(
                VariableNeighbourhoodConfig(
                    objective=objective,
                    neighbourhood=neighbourhood,
                    mode=VariableNeighbourhoodMode.VND,
                    max_iterations=12,
                    max_evaluations=160,
                    seed=0,
                )
            ),
            (),
        ),
        ImproverSweep(
            'vns',
            VariableNeighbourhoodSearch(
                VariableNeighbourhoodConfig(
                    objective=objective,
                    neighbourhood=neighbourhood,
                    mode=VariableNeighbourhoodMode.VNS,
                    max_iterations=18,
                    max_evaluations=160,
                    seed=0,
                )
            ),
            (),
        ),
        ImproverSweep(
            'tabu',
            TabuSearch(
                TabuConfig(
                    objective=objective,
                    neighbourhood=neighbourhood,
                    tabu_tenure=5,
                    max_iterations=12,
                    max_evaluations=160,
                )
            ),
            (),
        ),
        ImproverSweep(
            'sa',
            SimulatedAnnealing(
                SimulatedAnnealingConfig(
                    objective=objective,
                    neighbourhood=neighbourhood,
                    initial_temperature=5.0,
                    cooling_rate=0.97,
                    minimum_temperature=0.05,
                    seed=0,
                    max_iterations=160,
                    max_evaluations=160,
                )
            ),
            (),
        ),
        ImproverSweep(
            'lns',
            LargeNeighbourhoodSearch(
                LargeNeighbourhoodConfig(
                    objective=objective,
                    horizon_days=30,
                    destroy_count=2,
                    destroy_operator=DestroyOperator.RANDOM,
                    repair_operator=RepairOperator.EARLIEST,
                    max_iterations=60,
                    max_evaluations=60,
                    seed=0,
                )
            ),
            (),
        ),
        ImproverSweep(
            'alns',
            AdaptiveLargeNeighbourhoodSearch(
                AdaptiveLargeNeighbourhoodConfig(
                    objective=objective,
                    horizon_days=30,
                    destroy_count=2,
                    max_iterations=80,
                    reaction_factor=0.2,
                    initial_temperature=5.0,
                    cooling_rate=0.97,
                    minimum_temperature=0.05,
                    reward_best=8.0,
                    reward_accepted=4.0,
                    reward_rejected=1.0,
                    max_evaluations=80,
                    seed=0,
                )
            ),
            (),
        ),
    )


def build_c7_calibration_spec(
    output_root: Path,
) -> TuningStudySpec:
    """Build the fixed C7 runtime/failure calibration study.

    This intentionally contains no tuning axes. It gives every C3 family and
    every C4 family one representative bounded configuration over the full
    C7 development partition. Its results calibrate budgets/search-space
    design; they are not production parameter recommendations.
    """
    if not isinstance(output_root, Path):
        raise TypeError('output_root must be a Path')

    objective = calibration_objective()

    return TuningStudySpec(
        objective=objective,
        objective_axes=(),
        constructors=_constructors(),
        improvers=_improvers(objective),
        seeds=C7_CALIBRATION_SEEDS,
        split_seed=C7_V1_SPLIT_SEED,
        development_design_count=C7_V1_DEVELOPMENT_DESIGN_COUNT,
        trial_wall_seconds=C7_CALIBRATION_TRIAL_WALL_SECONDS,
        max_candidates=C7_CALIBRATION_CANDIDATE_COUNT,
        max_trials=C7_CALIBRATION_EXPECTED_TRIALS,
        output_root=output_root,
    )


C7_BUDGET_PROBE_SEEDS = (1701,)
C7_BUDGET_PROBE_TRIAL_WALL_SECONDS = 15.0
C7_BUDGET_PROBE_CANDIDATE_COUNT = 12
C7_BUDGET_PROBE_EXPECTED_TRIALS = 1128


def _budget_probe_improvers(
    objective: PlanObjectiveConfig,
) -> tuple[ImproverSweep, ...]:
    neighbourhood = NeighbourhoodConfig(
        horizon_days=30,
        max_relocation_distance_days=7,
    )

    def sa(
        arm_id: str,
        evaluations: int,
    ) -> ImproverSweep:
        return ImproverSweep(
            arm_id,
            SimulatedAnnealing(
                SimulatedAnnealingConfig(
                    objective=objective,
                    neighbourhood=neighbourhood,
                    initial_temperature=5.0,
                    cooling_rate=0.97,
                    minimum_temperature=0.05,
                    seed=0,
                    max_iterations=evaluations,
                    max_evaluations=evaluations,
                )
            ),
            (),
        )

    return (
        ImproverSweep(
            'none',
            None,
            (),
        ),
        sa('sa80', 80),
        sa('sa160', 160),
    )


def build_c7_budget_probe_spec(
    output_root: Path,
) -> TuningStudySpec:
    """Probe whether the 5-second calibration clipped baseline/SA quality.

    The probe deliberately keeps the same development split and constructors,
    raises the whole-trial wall budget to 15 seconds, and compares no
    improvement with SA at 80 and 160 evaluations.

    This is budget calibration only. It does not consume holdout scenarios
    and does not eliminate an algorithm family.
    """
    if not isinstance(output_root, Path):
        raise TypeError('output_root must be a Path')

    objective = calibration_objective()

    return TuningStudySpec(
        objective=objective,
        objective_axes=(),
        constructors=_constructors(),
        improvers=_budget_probe_improvers(
            objective
        ),
        seeds=C7_BUDGET_PROBE_SEEDS,
        split_seed=C7_V1_SPLIT_SEED,
        development_design_count=(
            C7_V1_DEVELOPMENT_DESIGN_COUNT
        ),
        trial_wall_seconds=(
            C7_BUDGET_PROBE_TRIAL_WALL_SECONDS
        ),
        max_candidates=(
            C7_BUDGET_PROBE_CANDIDATE_COUNT
        ),
        max_trials=(
            C7_BUDGET_PROBE_EXPECTED_TRIALS
        ),
        output_root=output_root,
    )
