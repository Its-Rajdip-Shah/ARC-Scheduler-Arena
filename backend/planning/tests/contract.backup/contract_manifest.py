\
"""Machine-readable index of the frozen ARC backend contract.

The manifest gives every contract test a stable requirement ID.  The IDs are
about behaviour, not implementation details, so the backend may be refactored
without rewriting the architecture contract.

A requirement is "covered" when at least one test declares its ID with
@covers(...).  test_00_contract_coverage.py fails if a frozen requirement has
no executable test.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True, slots=True)
class ContractRequirement:
    id: str
    area: str
    statement: str


def _r(id: str, area: str, statement: str) -> ContractRequirement:
    return ContractRequirement(id=id, area=area, statement=statement)


REQUIREMENTS: Final[tuple[ContractRequirement, ...]] = (
    # Canonical ownership / authority
    _r("CAN-001", "canonical_state", "All planning views project one canonical ARC domain state."),
    _r("CAN-002", "canonical_state", "Meaningful user actions mutate canonical domain state, not view-local planning truth."),
    _r("CAN-003", "canonical_state", "Scheduler proposals never silently rewrite canonical user facts."),
    _r("CAN-004", "canonical_state", "Scheduled dates and execution ranks are disposable scheduler-owned proposals unless explicitly anchored."),
    _r("CAN-005", "canonical_state", "Current-focus and other convenience UI state do not mutate planning semantics."),
    _r("CAN-006", "canonical_state", "Semantic hierarchy children are distinct from scheduler allocation/progress segments."),
    _r("CAN-007", "canonical_state", "Priority is canonical user preference; execution rank is algorithmic advice."),
    _r("CAN-008", "canonical_state", "Anchor/manual date intent is distinct from an automatic scheduled date."),
    _r("CAN-009", "canonical_state", "Release/deadline values stored on a child are canonical after creation; parent dates are creation defaults, not permanent inheritance."),
    _r("CAN-010", "canonical_state", "Only domain commands may change canonical planning facts."),

    # Hierarchy / frontier
    _r("HIE-001", "invariants", "Parent/child hierarchy is cycle-free."),
    _r("HIE-002", "invariants", "Items cannot be parented across users."),
    _r("HIE-003", "structural_frontier", "An unfinished actionable item with unfinished semantic children is structural, not execution-frontier work."),
    _r("HIE-004", "structural_frontier", "An unfinished actionable leaf may enter the execution frontier when otherwise eligible."),
    _r("HIE-005", "structural_frontier", "Completing/deleting the final unfinished child may expose its parent to the frontier."),
    _r("HIE-006", "structural_frontier", "Adding/reopening/restoring an unfinished child may remove its parent from the frontier."),
    _r("HIE-007", "structural_frontier", "Frontier transitions preserve meaningful priority/restoration context."),
    _r("HIE-008", "structural_frontier", "A decomposed parent returning to the frontier represents fresh residual closure work, not accumulated stale residual effort."),

    # Creation / temporal defaults
    _r("CRE-001", "creation", "Creating an actionable frontier item gives it a valid canonical priority position."),
    _r("CRE-002", "creation", "Creating a semantic child makes structural/frontier state reconcile atomically."),
    _r("CRE-003", "creation", "Nested-task creation defaults release date from its parent."),
    _r("CRE-004", "creation", "Nested-task creation defaults due date from its parent."),
    _r("CRE-005", "creation", "A user may explicitly choose a child release date different from its parent's."),
    _r("CRE-006", "creation", "A user may explicitly choose a child due date different from its parent's, including later, through explicit conflict handling."),
    _r("CRE-007", "creation", "Creation never silently invents a dependency from hierarchy or sibling order."),

    # Completion / reopen
    _r("CMP-001", "completion_reopen", "Completing work removes it from active scheduling/frontier projections without destroying semantic history."),
    _r("CMP-002", "completion_reopen", "Reopening work restores eligibility coherently."),
    _r("CMP-003", "completion_reopen", "Accidental complete->reopen round trips do not cause semantic drift."),
    _r("CMP-004", "completion_reopen", "Completing a prerequisite may unblock dependants."),
    _r("CMP-005", "completion_reopen", "Reopening a prerequisite of an already-completed dependant requires explicit dependency conflict resolution."),
    _r("CMP-006", "completion_reopen", "Completion/reopen never silently deletes a dependency."),

    # Reparenting
    _r("REP-001", "reparenting", "Reparenting cannot create hierarchy cycles."),
    _r("REP-002", "reparenting", "Reparenting reconciles old-parent and new-parent frontier state."),
    _r("REP-003", "reparenting", "Reparenting does not silently destroy dependency edges."),
    _r("REP-004", "reparenting", "Reparenting preserves explicitly chosen child dates rather than re-inheriting new-parent dates."),
    _r("REP-005", "reparenting", "Reparenting is atomic with priority/frontier/schedule reconciliation."),

    # Delete / restore / undo
    _r("DEL-001", "delete_restore_undo", "Deletion is reversible while undo history is retained."),
    _r("DEL-002", "delete_restore_undo", "Deleting/restoring work reconciles frontier eligibility."),
    _r("DEL-003", "delete_restore_undo", "Delete/restore preserves dependency semantics or requires explicit conflict resolution."),
    _r("DEL-004", "delete_restore_undo", "Undo restores canonical state, not stale scheduler proposals as authoritative truth."),
    _r("DEL-005", "delete_restore_undo", "Time-sensitive undo revalidates dates/anchors against the current date."),
    _r("DEL-006", "delete_restore_undo", "Reversible mutation round trips do not accumulate semantic drift."),

    # Priority
    _r("PRI-001", "priority", "Eligible actionable work has one dense global priority order with no ties."),
    _r("PRI-002", "priority", "Priority expresses preference, not dependency."),
    _r("PRI-003", "priority", "Priority alone does not make lower-priority work illegal to execute first."),
    _r("PRI-004", "priority", "Priority survives temporary frontier departure and returns near meaningful prior neighbours."),
    _r("PRI-005", "priority", "Completion/reopen does not progressively corrupt priority ordering."),
    _r("PRI-006", "priority", "Planner and Priority views edit the same canonical priority state."),
    _r("PRI-007", "priority", "Scheduler execution rank does not silently mutate canonical priority."),
    _r("PRI-008", "priority", "Explicit user reprioritisation triggers coherent rescheduling/projection."),

    # Dependencies
    _r("DEP-001", "dependencies", "Dependencies are explicit hard precedence constraints, separate from hierarchy and priority."),
    _r("DEP-002", "dependencies", "Dependency graph rejects self-dependencies."),
    _r("DEP-003", "dependencies", "Dependency graph rejects cycles."),
    _r("DEP-004", "dependencies", "A dependant cannot execute before required prerequisite completion."),
    _r("DEP-005", "dependencies", "A dependency on a structural parent semantically waits for the required parent subtree/parent completion."),
    _r("DEP-006", "dependencies", "Dependency constraints propagate execution blocking through required parent/child work."),
    _r("DEP-007", "dependencies", "Dependency edits are tenant-isolated."),
    _r("DEP-008", "dependencies", "Actions that would contradict an existing dependency require explicit cancel-or-remove-dependency resolution."),
    _r("DEP-009", "dependencies", "Scheduler algorithms that violate dependency precedence are invalid."),
    _r("DEP-010", "dependencies", "Partial/progress-threshold dependencies are deferred for MVP; MVP dependency satisfaction is completion-based."),

    # Temporal facts
    _r("TMP-001", "temporal", "Automatic scheduling never places work before its own release date."),
    _r("TMP-002", "temporal", "Automatic scheduling never places work after its own due date."),
    _r("TMP-003", "temporal", "Automatic scheduling does not place new work in the past."),
    _r("TMP-004", "temporal", "Release date is feasibility, not an automatic importance boost."),
    _r("TMP-005", "temporal", "A distant deadline does not automatically outrank healthy higher-priority flexible work."),
    _r("TMP-006", "temporal", "Deadline-constrained work must retain enough legal capacity to remain feasible where possible."),
    _r("TMP-007", "temporal", "Controlled overload before a deadline is preferred to automatic deadline violation."),
    _r("TMP-008", "temporal", "All scheduler flavours avoid risky deadline-day/too-close-to-deadline placement when safer earlier placement is feasible."),
    _r("TMP-009", "temporal", "Overdue means incomplete work has crossed its due date, not merely an anchor date."),
    _r("TMP-010", "temporal", "Overdue work remains represented and recoverable rather than becoming unschedulable garbage."),
    _r("TMP-011", "temporal", "Contradictory or infeasible temporal state is surfaced rather than silently rewriting user dates."),

    # Anchors / manual intent
    _r("ANC-001", "anchors", "An anchor is canonical explicit user date intent."),
    _r("ANC-002", "anchors", "Valid active anchors are not moved by automatic scheduling."),
    _r("ANC-003", "anchors", "Moving an anchor explicitly changes the canonical anchored date."),
    _r("ANC-004", "anchors", "Anchoring after a due date requires explicit deadline-change-or-cancel conflict resolution."),
    _r("ANC-005", "anchors", "Anchoring before a release date requires explicit release-change-or-cancel conflict resolution."),
    _r("ANC-006", "anchors", "Passing an anchor date does not itself make work overdue."),
    _r("ANC-007", "anchors", "Expired/missed anchors return placement to automatic scheduling without silently changing factual due date."),
    _r("ANC-008", "anchors", "Missed explicit planning intent is not silently forgotten; recovery intent/history remains available."),
    _r("ANC-009", "anchors", "Decomposing an anchored parent suspends/stales parent execution anchoring while children carry the relevant planning intent."),
    _r("ANC-010", "anchors", "If the structural episode reverses without other meaningful change, the parent's anchor can coherently reactivate."),
    _r("ANC-011", "anchors", "Removing an anchor returns the item to automatic scheduling without rewriting priority."),
    _r("ANC-012", "anchors", "User-created infeasible/overloaded anchored plans require explicit acknowledgement rather than silent acceptance."),

    # Duration / progress
    _r("DUR-001", "duration_progress", "Duration categories are <20m, <1h, <4h, <8h, <16h, >16h with mutually exclusive internal boundaries."),
    _r("DUR-002", "duration_progress", "<20m, <1h and <4h are atomic one-day scheduling categories."),
    _r("DUR-003", "duration_progress", "<8h, <16h and >16h are splittable allocation categories."),
    _r("DUR-004", "duration_progress", "Users are not forced to manually decompose large work merely for scheduling."),
    _r("DUR-005", "duration_progress", "Splittable tasks canonically maintain percent completed."),
    _r("DUR-006", "duration_progress", "Changing between splittable duration categories preserves percent completed."),
    _r("DUR-007", "duration_progress", "Changing a splittable task to an atomic category discards partial-progress scheduling semantics; the atomic task is simply incomplete unless fully completed."),
    _r("DUR-008", "duration_progress", "Completed progress segments are durable canonical progress; future allocation percentages are disposable proposals."),
    _r("DUR-009", "duration_progress", "Undoing a completed progress segment reduces percent completed coherently without disturbing unrelated completed segments."),
    _r("DUR-010", "duration_progress", "A splittable task reaching 100 percent becomes completed; reopening can restore unfinished progress semantics."),
    _r("DUR-011", "duration_progress", "Allocation/progress segments are not semantic children and never affect hierarchy/dependency frontier logic."),

    # Large allocations
    _r("ALL-001", "large_allocations", "One splittable canonical task may receive multiple allocation sessions across dates."),
    _r("ALL-002", "large_allocations", "Allocation percentages for unfinished work sum to the remaining work for the current proposal."),
    _r("ALL-003", "large_allocations", "Scheduler may change future allocation session sizes on later reschedules."),
    _r("ALL-004", "large_allocations", "Once large work commences, scheduler prefers reasonably prompt completion."),
    _r("ALL-005", "large_allocations", "Continuity is soft: fragmentation is allowed when it materially improves the global schedule."),
    _r("ALL-006", "large_allocations", "Session sizing is algorithmic rather than a hard-coded two-hour decomposition."),
    _r("ALL-007", "large_allocations", "Large-task allocations consume workload/pressure capacity."),
    _r("ALL-008", "large_allocations", "Large-task progress history remains stable across rescheduling."),

    # Focus
    _r("FOC-001", "focus", "Focus is a projection of canonical/scheduler state, not an independent planning database."),
    _r("FOC-002", "focus", "Focus groups candidates by the six duration categories."),
    _r("FOC-003", "focus", "Focus projection orders candidates by scheduled date then execution rank."),
    _r("FOC-004", "focus", "Focus may look ahead to future scheduled work to fill choice buckets without rescheduling it."),
    _r("FOC-005", "focus", "Current focus means only 'I am working on this now'."),
    _r("FOC-006", "focus", "Changing current focus alone changes no priority, anchor, dependency, deadline or scheduler placement."),
    _r("FOC-007", "focus", "Promote-to-today is distinct from current-focus selection and creates explicit canonical date intent."),
    _r("FOC-008", "focus", "Returning promoted work to automatic scheduling removes that explicit date commitment."),
    _r("FOC-009", "focus", "Wrong-bucket UI drops are normalized to the task's canonical duration category."),
    _r("FOC-010", "focus", "Explicit Focus reprioritisation mutates the same canonical global priority used elsewhere."),

    # Scheduler / Timeline / capacity
    _r("SCH-001", "scheduler_timeline", "Scheduler consumes reconciled canonical ARC state rather than repairing domain semantics itself."),
    _r("SCH-002", "scheduler_timeline", "Scheduler produces date allocation and an execution rank for work sharing a date."),
    _r("SCH-003", "scheduler_timeline", "Execution rank is advisory and does not force the user to execute in that order."),
    _r("SCH-004", "scheduler_timeline", "Doing rank 3 before rank 1 does not itself mutate canonical priority."),
    _r("SCH-005", "scheduler_timeline", "Timeline is a projection, not a separate schedule database."),
    _r("SCH-006", "scheduler_timeline", "Explicit Timeline movement is translated into canonical user intent and remains sticky across rescheduling."),
    _r("SCH-007", "scheduler_timeline", "Scheduler may optimize unspecified decisions but preserves specified user decisions."),
    _r("SCH-008", "scheduler_timeline", "Workload/overload is effort-based, not task-count-based."),
    _r("SCH-009", "scheduler_timeline", "ARC has no user-maintained weekday availability/capacity calendar in the frozen MVP contract."),
    _r("SCH-010", "scheduler_timeline", "Scheduler prefers balanced workload but may overload when constrained work makes it necessary."),
    _r("SCH-011", "scheduler_timeline", "Logically valid but temporally infeasible schedules are representable and surfaced as conflicts/infeasibility."),
    _r("SCH-012", "scheduler_timeline", "Pressure bands may project Chill/Busy/Stacked/Crunch/Infeasible; exact thresholds are not frozen domain invariants."),
    _r("SCH-013", "scheduler_timeline", "Deterministic scheduler configurations produce deterministic output for identical inputs."),

    # Transactions / coherence / authority
    _r("TRX-001", "transactions", "Each meaningful domain command is atomic across canonical mutation and required reconciliation."),
    _r("TRX-002", "transactions", "A failed validation/conflict leaves canonical state unchanged unless the user explicitly confirms an alternative."),
    _r("TRX-003", "transactions", "Concurrent/compound mutations cannot leave duplicate priority positions or half-applied hierarchy state."),
    _r("VIEW-001", "view_coherence", "Planner, Priority, Timeline and Focus reproject from the same canonical mutation."),
    _r("VIEW-002", "view_coherence", "The user never needs repair-hopping between views to make one explicit change count everywhere."),
    _r("VIEW-003", "view_coherence", "Convenience-only UI actions do not trigger unnecessary global replanning."),
    _r("AUTH-001", "scheduler_authority", "Hard user intent constrains the scheduler; soft intent guides it; unspecified decisions remain algorithmic."),
    _r("AUTH-002", "scheduler_authority", "Scheduler cannot create/delete dependencies or silently alter hierarchy, priority, dates, anchors or progress."),
    _r("AUTH-003", "scheduler_authority", "Algorithms violating hard invariants are rejected/discarded."),
    _r("AUTH-004", "scheduler_authority", "Algorithm flavours may vary soft optimization behaviour without weakening ARC hard guarantees."),

    # Round trip / torture
    _r("RT-001", "round_trip", "Create/delete/restore and equivalent reversible cycles preserve semantic state."),
    _r("RT-002", "round_trip", "Complete/reopen cycles preserve semantic state except the explicitly toggled lifecycle fact."),
    _r("RT-003", "round_trip", "Decompose/reverse-decompose cycles preserve unaffected canonical intent."),
    _r("RT-004", "round_trip", "Anchor/unanchor/re-anchor cycles do not corrupt priority/deadline/release facts."),
    _r("RT-005", "round_trip", "Repeated random valid state transitions preserve every hard invariant."),
    _r("RT-006", "round_trip", "Invalid random transitions fail atomically and do not degrade subsequent state."),
)

REQUIREMENT_BY_ID: Final[dict[str, ContractRequirement]] = {
    requirement.id: requirement for requirement in REQUIREMENTS
}

if len(REQUIREMENT_BY_ID) != len(REQUIREMENTS):
    raise RuntimeError("Duplicate ARC contract requirement ID in contract_manifest.py")


# File -> contract areas expected to be exercised there.
TEST_FILE_AREAS: Final[dict[str, tuple[str, ...]]] = {
    "test_01_canonical_state.py": ("canonical_state",),
    "test_02_invariants.py": ("invariants",),
    "test_03_creation.py": ("creation",),
    "test_04_completion_reopen.py": ("completion_reopen",),
    "test_05_structural_frontier.py": ("structural_frontier",),
    "test_06_reparenting.py": ("reparenting",),
    "test_07_delete_restore_undo.py": ("delete_restore_undo",),
    "test_08_priority.py": ("priority",),
    "test_09_dependencies.py": ("dependencies",),
    "test_10_temporal.py": ("temporal",),
    "test_11_anchors.py": ("anchors",),
    "test_12_duration_progress.py": ("duration_progress",),
    "test_13_large_allocations.py": ("large_allocations",),
    "test_14_focus.py": ("focus",),
    "test_15_scheduler_timeline.py": ("scheduler_timeline",),
    "test_16_transactions.py": ("transactions",),
    "test_17_view_coherence.py": ("view_coherence",),
    "test_18_scheduler_authority.py": ("scheduler_authority",),
    "test_19_round_trip.py": ("round_trip",),
    "test_20_state_machine_torture.py": ("round_trip",),
}


def ids_for_area(area: str) -> set[str]:
    return {r.id for r in REQUIREMENTS if r.area == area}
