"""Controlled workload-generation specification for the ARC Arena.

This module describes generator inputs only.  It deliberately contains no
scheduler logic and no feature-space targeting logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class HierarchyDepth(StrEnum):
    FLAT = "flat"
    SHALLOW = "shallow"
    MEDIUM = "medium"
    DEEP = "deep"


class HierarchyBranching(StrEnum):
    NARROW = "narrow"
    BALANCED = "balanced"
    BROAD = "broad"


class DependencyLoad(StrEnum):
    NONE = "none"
    SPARSE = "sparse"
    MODERATE = "moderate"
    HEAVY = "heavy"


class DependencyTopology(StrEnum):
    NONE = "none"
    RANDOM_DAG = "random_dag"
    CHAIN = "chain"
    LAYERED = "layered"
    FAN_IN = "fan_in"
    FAN_OUT = "fan_out"


class DurationProfile(StrEnum):
    SHORT = "short"
    BALANCED = "balanced"
    LONG = "long"
    BIMODAL = "bimodal"
    UNIFORM = "uniform"


class PriorityAlignment(StrEnum):
    NONE = "none"
    RANDOM = "random"
    URGENCY_ALIGNED = "urgency_aligned"
    URGENCY_OPPOSED = "urgency_opposed"
    DURATION_ALIGNED = "duration_aligned"
    DURATION_OPPOSED = "duration_opposed"


class TemporalPressure(StrEnum):
    RELAXED = "relaxed"
    MIXED = "mixed"
    COMPRESSED = "compressed"
    URGENT = "urgent"
    OVERDUE_MIXED = "overdue_mixed"


class TemporalShape(StrEnum):
    """Shape of temporal constraints among temporally covered work."""

    DEADLINE_ONLY = "deadline_only"
    RELEASE_ONLY = "release_only"
    BOTH = "both"
    MIXED = "mixed"


class ExpiredAnchorHistory(StrEnum):
    """Amount of frontier work carrying previous-anchor history."""

    NONE = "none"
    SPARSE = "sparse"
    DENSE = "dense"


class ActionableParentCoverage(StrEnum):
    """How many hierarchy parents are themselves actionable work."""

    NONE = "none"
    SOME = "some"
    MANY = "many"


class AnchorRelation(StrEnum):
    NONE = "none"
    BEFORE = "before"
    SAME = "same"
    AFTER = "after"
    MIXED = "mixed"


class LifecycleProfile(StrEnum):
    FRESH = "fresh"
    EARLY = "early"
    MIXED = "mixed"
    ADVANCED = "advanced"
    COMPLETION_HEAVY = "completion_heavy"


class Heterogeneity(StrEnum):
    HOMOGENEOUS = "homogeneous"
    MIXED = "mixed"


SCALES = frozenset({16, 32, 64, 128, 256})
COVERAGE_LEVELS = frozenset({0.0, 0.25, 0.50, 0.75, 1.0})


@dataclass(frozen=True, slots=True)
class GenerationSpec:
    """Immutable, serialisable description of one controlled workload."""

    seed: int
    size: int = 32

    hierarchy_depth: HierarchyDepth = HierarchyDepth.SHALLOW
    hierarchy_branching: HierarchyBranching = HierarchyBranching.BALANCED

    dependency_load: DependencyLoad = DependencyLoad.NONE
    dependency_topology: DependencyTopology = DependencyTopology.NONE

    duration_profile: DurationProfile = DurationProfile.BALANCED

    priority_coverage: float = 0.5
    priority_alignment: PriorityAlignment = PriorityAlignment.RANDOM

    temporal_coverage: float = 0.5
    temporal_pressure: TemporalPressure = TemporalPressure.MIXED
    temporal_shape: TemporalShape = TemporalShape.BOTH

    anchor_coverage: float = 0.0
    anchor_relation: AnchorRelation = AnchorRelation.NONE
    expired_anchor_history: ExpiredAnchorHistory = ExpiredAnchorHistory.NONE

    actionable_parent_coverage: ActionableParentCoverage = (
        ActionableParentCoverage.NONE
    )

    lifecycle: LifecycleProfile = LifecycleProfile.FRESH
    heterogeneity: Heterogeneity = Heterogeneity.HOMOGENEOUS

    def validate(self) -> None:
        """Reject contradictory or unsupported V1 specifications."""
        if self.size not in SCALES:
            raise ValueError(f"unsupported V1 workload size: {self.size}")

        for name, value in (
            ("priority_coverage", self.priority_coverage),
            ("temporal_coverage", self.temporal_coverage),
            ("anchor_coverage", self.anchor_coverage),
        ):
            if value not in COVERAGE_LEVELS:
                raise ValueError(
                    f"{name} must be one of {sorted(COVERAGE_LEVELS)}; got {value}"
                )

        if self.hierarchy_depth is HierarchyDepth.FLAT:
            # Branching has no semantics when no parent edges exist.
            if self.hierarchy_branching is not HierarchyBranching.BALANCED:
                raise ValueError(
                    "flat hierarchy requires BALANCED branching as the neutral value"
                )

        if self.dependency_load is DependencyLoad.NONE:
            if self.dependency_topology is not DependencyTopology.NONE:
                raise ValueError(
                    "dependency_topology must be NONE when dependency_load is NONE"
                )
        elif self.dependency_topology is DependencyTopology.NONE:
            raise ValueError(
                "non-NONE dependency_load requires a dependency topology"
            )

        if self.priority_coverage == 0:
            if self.priority_alignment is not PriorityAlignment.NONE:
                raise ValueError(
                    "priority_alignment must be NONE when priority_coverage is zero"
                )
        elif self.priority_alignment is PriorityAlignment.NONE:
            raise ValueError(
                "positive priority_coverage requires a priority alignment"
            )

        if self.anchor_coverage == 0:
            if self.anchor_relation is not AnchorRelation.NONE:
                raise ValueError(
                    "anchor_relation must be NONE when anchor_coverage is zero"
                )
        elif self.anchor_relation is AnchorRelation.NONE:
            raise ValueError(
                "positive anchor_coverage requires an anchor relation"
            )

        if (
            self.priority_alignment
            in {
                PriorityAlignment.URGENCY_ALIGNED,
                PriorityAlignment.URGENCY_OPPOSED,
            }
            and self.temporal_coverage == 0
        ):
            raise ValueError(
                "urgency-based priority alignment requires temporal coverage"
            )

        if (
            self.anchor_coverage > 0
            and self.anchor_relation
            in {AnchorRelation.BEFORE, AnchorRelation.SAME, AnchorRelation.AFTER}
            and self.temporal_coverage == 0
        ):
            raise ValueError(
                "deadline-relative anchor relation requires temporal coverage"
            )
