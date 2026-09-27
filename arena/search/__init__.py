"""Immutable search foundation and deterministic improvement engines."""
from .state import SearchState, SessionPlacement
from .moves import RelocateSession, SwapSessions, ShiftItem, apply_move
from .neighbourhoods import (
    NeighbourhoodConfig, relocate_session_moves, swap_session_moves,
    shift_item_moves, all_moves,
)
from .objective import PlanObjectiveConfig, PlanObjective, score_plan, score_state, objective_delta

from .hill_climbing import ImprovementStrategy, HillClimbConfig, HillClimbResult, HillClimber

__all__ = [
    'SearchState', 'SessionPlacement', 'RelocateSession', 'SwapSessions', 'ShiftItem',
    'apply_move', 'NeighbourhoodConfig', 'relocate_session_moves', 'swap_session_moves',
    'shift_item_moves', 'all_moves', 'PlanObjectiveConfig', 'PlanObjective',
    'score_plan', 'score_state', 'objective_delta',
    'ImprovementStrategy', 'HillClimbConfig', 'HillClimbResult', 'HillClimber',
]

from .variable_neighbourhood import (
    VariableNeighbourhoodMode, VariableNeighbourhoodConfig,
    VariableNeighbourhoodResult, VariableNeighbourhoodSearch,
)
from .tabu_search import TabuConfig, TabuResult, TabuSearch
from .simulated_annealing import (
    SimulatedAnnealingConfig, SimulatedAnnealingResult, SimulatedAnnealing,
)

__all__ += [
    'VariableNeighbourhoodMode', 'VariableNeighbourhoodConfig',
    'VariableNeighbourhoodResult', 'VariableNeighbourhoodSearch',
    'TabuConfig', 'TabuResult', 'TabuSearch',
    'SimulatedAnnealingConfig', 'SimulatedAnnealingResult', 'SimulatedAnnealing',
]

from .destroy_repair import DestroyOperator, RepairOperator
from .large_neighbourhood import (
    LargeNeighbourhoodConfig, LargeNeighbourhoodResult, LargeNeighbourhoodSearch,
)
from .adaptive_large_neighbourhood import (
    AdaptiveLargeNeighbourhoodConfig, AdaptiveLargeNeighbourhoodResult,
    AdaptiveLargeNeighbourhoodSearch,
)

__all__ += [
    'DestroyOperator', 'RepairOperator',
    'LargeNeighbourhoodConfig', 'LargeNeighbourhoodResult', 'LargeNeighbourhoodSearch',
    'AdaptiveLargeNeighbourhoodConfig', 'AdaptiveLargeNeighbourhoodResult',
    'AdaptiveLargeNeighbourhoodSearch',
]
