# ARC State Space

ARC state is multidimensional. Do not implement one giant mutually-exclusive `TaskState` enum.

## Task state dimensions

### Lifecycle
- `ACTIVE`
- `DELETED` (tombstoned/restorable where supported)

### Structural role
- `EXECUTABLE_LEAF` — no required unfinished semantic children prevent direct execution.
- `STRUCTURAL` — decomposed into required unfinished semantic children; not ordinary frontier work.
- `RESIDUAL_LEAF` — previously structural parent returned to executable frontier for closure/integration work.

### Completion
For atomic work:
- `INCOMPLETE`
- `COMPLETE`

For splittable work:
- `NOT_STARTED` (`0%`)
- `PARTIAL` (`0 < %completed < 100`)
- `COMPLETE` (`100%`)

### Frontier/executability
- `FRONTIER_ELIGIBLE`
- `NON_FRONTIER_STRUCTURAL`
- `BLOCKED_DEPENDENCY`
- `UNRELEASED`
- combinations may apply to explain why something is not executable.

### Dependency
- `UNBLOCKED`
- `BLOCKED`

### Release
- `UNRELEASED`
- `RELEASED`

### Deadline
- `NOT_OVERDUE`
- `OVERDUE`

A task may be overdue and blocked simultaneously.

### Anchor/manual date intent
- `NO_ANCHOR`
- `ACTIVE_ANCHOR`
- `SUSPENDED_ANCHOR` — preserved while the task is structural/non-executable.
- `EXPIRED_ANCHOR_HISTORY` — no longer a hard date commitment but retained for audit/recovery semantics.

### Manual planning intent
- `AUTOMATIC`
- `EXPLICIT_DATE_INTENT`
- `PROMOTED_RECOVERY_INTENT` where a missed explicit promotion remains relevant after hard anchor expiry.

### Large-work commencement
- `NOT_COMMENCED`
- `COMMENCED`
- `FINISHED`

### Scheduling proposal
- `UNALLOCATED`
- `ALLOCATED_SINGLE_DAY`
- `ALLOCATED_MULTI_DAY`
- `CONFLICTING`
- `INFEASIBLE`

### Current focus
- `NOT_CURRENT_FOCUS`
- `CURRENT_FOCUS`

This is convenience/execution state, not planning authority.

## Duration state

Atomic one-day scheduling:
- `<20m`
- `<1h`
- `<4h`

Splittable/allocatable scheduling:
- `<8h`
- `<16h`
- `>16h`

The underlying domain representation must define non-overlapping boundaries even though labels are shorthand.

## Dependency graph state

For each explicit edge `A -> B`:
- valid active edge;
- suspended/historical due to deletion where restore semantics require history;
- removed.

Illegal graph states:
- self-edge;
- dependency cycle;
- dangling active endpoint.

## Hierarchy graph state

Legal:
- rooted/forest hierarchy with at most one semantic parent per task (assuming current ARC model);
- no hierarchy cycles.

Illegal:
- task parented to itself;
- descendant reparented beneath itself;
- dangling active parent reference.

## Progress-segment state for splittable tasks

A progress segment/allocation may be:
- `PROPOSED` — scheduler-owned, disposable;
- `COMPLETED` — user-confirmed and contributes to canonical `%completed`;
- `REVERSED`/removed from active completion accounting after user marks it incomplete.

Proposed segments can be replaced on reschedule. Completed segments cannot silently change percentage.

## Composite states explicitly supported

Examples that are legal and important:

- active + incomplete + executable leaf + blocked + released + overdue;
- active + partial + executable leaf + unblocked + released + overdue;
- active + structural + suspended anchor;
- active + residual leaf + incomplete + unblocked;
- active + complete + historical anchor information;
- active + incomplete + valid canonical constraints + infeasible scheduler state;
- deleted + historical hierarchy/dependency/anchor information retained for possible restore.

## States that must not exist after a committed/reconciled transaction

- active hierarchy cycle;
- active dependency cycle;
- active dangling dependency edge;
- active dangling parent reference;
- scheduler treating a structural parent as ordinary frontier work;
- dependent executable while its hard prerequisite is incomplete;
- proposed allocation counted as completed progress without user confirmation;
- view-local priority/order contradicting canonical state because the view persisted its own truth;
- half-applied compound mutation.
