# ARC Canonical State Ownership

This document defines what ARC treats as truth, what it derives, what the scheduler proposes, and what exists only for UI convenience.

## Authority layers

### 1. Canonical user/domain facts
Persisted and authoritative:

- Task identity and lifecycle record.
- Title/content metadata.
- Parent relationship / hierarchy.
- Explicit sibling/global priority representation.
- Duration category / original scope estimate.
- Completion state for atomic tasks.
- `%completed` and completed progress-segment history for splittable tasks.
- Release date stored on the task.
- Deadline stored on the task.
- Explicit dependency edges.
- Anchor/manual date intent and its history/status.
- Explicit manual planning/promotion intent that must survive disposable scheduler proposals.
- Deletion/tombstone information needed for restore/undo.
- Audit/history needed to reverse reversible operations safely.

### 2. Derived domain state
Recomputed from canonical facts + current time:

- Structural vs executable-leaf status.
- Frontier membership.
- Dependency-blocked/unblocked status.
- Released/unreleased status.
- Overdue/non-overdue status.
- Residual-parent/closure-work status.
- Large-task commenced status.
- Remaining percentage for splittable work.
- Conflict markers.
- Feasibility/infeasibility indicators.
- Anchor active/suspended/expired interpretation.

Derived state may be cached, but the cache is never more authoritative than the facts from which it is derived.

### 3. Scheduler-owned proposals
Disposable and freely recomputable:

- Scheduled date(s).
- Allocation/session percentages for unfinished splittable work.
- Execution rank within a date.
- Suggested Focus candidate ordering.
- Pressure/overload score and band.
- Suggested recovery placement after missed work.

A future allocation is not canonical progress until the user marks that allocation/progress segment complete.

### 4. View/convenience state
Does not alter planning semantics by itself:

- Current-focus selection.
- Expanded/collapsed hierarchy rows.
- Open/closed Focus queues.
- Selected card.
- Drag hover target.
- Filters/sorts that do not express canonical priority.
- Temporary form state before commit.

## Important ownership distinctions

### Hierarchy child vs allocation/progress segment
A semantic child is a real task. An allocation/progress segment is part of one large task. They may both be rendered visually beneath a task, but only semantic children participate in hierarchy, dependencies and structural frontier logic.

### Priority vs execution rank
Priority is canonical user preference. Execution rank is an algorithmic recommendation for a particular scheduled day.

### Anchor vs scheduled date
Anchor is explicit user intent. Scheduled date is a scheduler proposal. A task can lose/recompute a scheduled date without losing an anchor.

### Deadline vs urgency
Deadline is canonical. Urgency/pressure is derived/algorithmic.

### Parent temporal defaults vs inheritance
When creating a child, the form is prefilled from the parent. Once committed, the child's dates are its own canonical values and may explicitly diverge.

## Mutation authority

Only domain commands may change canonical facts. Scheduler/reconciliation code may update derived/proposal state but must not silently edit canonical priority, hierarchy, dependencies, dates, anchors or progress.
