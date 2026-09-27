"""Version 1 scheduler output contract.

All values here are scheduler-owned proposals or diagnostics. Nothing in this
module represents permission to mutate canonical ARC facts.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from .enums import LoadStatusV1, SchedulerFlavourV1


@dataclass(frozen=True, slots=True)
class SchedulerAllocationOutputV1:
    item_id: int
    scheduled_date: date
    hours: Decimal
    percentage: Decimal
    execution_rank: int


@dataclass(frozen=True, slots=True)
class WorkEstimateOutputV1:
    item_id: int
    total_hours: Decimal
    source: str


@dataclass(frozen=True, slots=True)
class DayLoadOutputV1:
    scheduled_date: date
    hours: Decimal
    status: LoadStatusV1


@dataclass(frozen=True, slots=True)
class PeriodLoadOutputV1:
    period: str
    hours: Decimal
    status: LoadStatusV1


@dataclass(frozen=True, slots=True)
class ProductionObjectiveOutputV1:
    # Order intentionally mirrors the frozen C11.15.9 lexicographic objective.
    late_hours: Decimal
    infeasible_day_count: int
    infeasible_excess_hours: Decimal
    tiny_nonfinal_sessions: int
    avoidable_idle_days: int
    max_daily_hours: Decimal
    overloaded_excess_hours: Decimal
    overloaded_day_count: int
    unjustified_marathon_excess_hours: Decimal
    deadline_buffer_risk: Decimal
    priority_postponement_days: Decimal
    session_shape_penalty: Decimal
    fragmentation_count: int
    preferred_excess_squared: Decimal
    continuity_gap_days: int
    completion_day_sum: int


@dataclass(frozen=True, slots=True)
class SchedulerRunMetadataV1:
    engine_version: str
    input_contract_version: str
    output_contract_version: str

    flavour: SchedulerFlavourV1

    iterations: int
    evaluations: int
    termination_reason: str


@dataclass(frozen=True, slots=True)
class SchedulerOutputV1:
    allocations: tuple[SchedulerAllocationOutputV1, ...]
    estimates: tuple[WorkEstimateOutputV1, ...]

    daily_load: tuple[DayLoadOutputV1, ...]
    weekly_load: tuple[PeriodLoadOutputV1, ...]
    monthly_load: tuple[PeriodLoadOutputV1, ...]

    objective: ProductionObjectiveOutputV1

    conflicts: tuple[str, ...]
    diagnostics: tuple[tuple[str, str], ...]

    metadata: SchedulerRunMetadataV1
