# ARC Invariants

These conditions must hold after every committed transaction and reconciliation pass unless explicitly identified as a valid surfaced conflict/infeasible plan rather than domain corruption.

## I1 — Single canonical truth
No view owns independent planning facts.

## I2 — Hierarchy acyclicity
The semantic parent/child graph is cycle-free.

## I3 — Dependency acyclicity
The hard precedence graph contains no self-edge or cycle.

## I4 — Referential integrity
Active hierarchy/dependency relationships reference active valid endpoints.

## I5 — Dependency precedence
A dependent cannot be executable/scheduled before its required prerequisite is complete. A user wishing to contradict this must explicitly remove the dependency first/as part of the confirmed transaction.

## I6 — Structural frontier
A structural parent with required unfinished children is not ordinary executable frontier work.

## I7 — Frontier correctness
Only work that is structurally executable, released and dependency-unblocked is exposed as currently executable frontier work.

## I8 — Completion coherence
Completion/reopening reconciles ancestors, descendants, frontier and dependency eligibility without deleting unrelated information.

## I9 — Original-scope preservation
Structural decomposition/residual-parent cycles never overwrite the user's original scope estimate.

## I10 — Fresh residual semantics
Each return of a structural parent to executable closure work uses fresh current residual semantics; stale residual estimates never accumulate.

## I11 — Priority preservation
Completion, temporary frontier departure, structural transitions and scheduler reruns do not silently corrupt canonical priority.

## I12 — Priority/dependency separation
Priority never substitutes for dependency; dependency never silently rewrites priority.

## I13 — Temporal provenance
A task's committed release/deadline values are its own canonical values. Parent values are creation defaults, not immutable hidden effective constraints.

## I14 — Explicit divergence
Risky child/parent temporal divergence is never created by silent automation; when ARC detects a potentially surprising explicit divergence, it surfaces it before commit.

## I15 — Anchor authority
Active anchors are respected by automatic scheduling unless they conflict with harder logical constraints; conflicts are surfaced rather than silently resolved by mutating canonical facts.

## I16 — Anchor/deadline/release integrity
Moving/creating an anchor across its own deadline/release cannot silently change those constraints.

## I17 — Anchor suspension through structure
When an anchored executable task becomes structural, its anchor is preserved/suspended and required new children inherit the date intent according to the frozen rule; reversal without other relevant edits restores prior semantics.

## I18 — Overdue semantics
Anchor expiry is not overdue. Overdue derives from crossing the task's deadline while incomplete.

## I19 — Progress accounting
For splittable tasks, canonical `%completed` equals the accepted completed progress represented by canonical completion records; future proposed allocations do not count.

## I20 — Progress bounds
`0 <= %completed <= 100`.

## I21 — Progress reversal locality
Reopening one completed progress segment changes only the progress represented by that segment and consequences derived from total progress; unrelated completed segments remain intact.

## I22 — Allocation identity separation
Scheduler allocations/progress segments are not semantic hierarchy children and cannot accidentally participate in task dependency/hierarchy logic.

## I23 — Duration-transition semantics
Splittable->splittable preserves percentage; splittable->atomic discards active partial-progress semantics; later atomic->splittable does not resurrect discarded percentage.

## I24 — No fabricated decomposition progress
Semantic decomposition of a partially completed large task does not silently distribute parent percentage among new child tasks.

## I25 — Scheduler non-authority
Scheduler output cannot mutate canonical hierarchy, priority, dependencies, release/deadline, anchor or confirmed progress.

## I26 — Scheduler safety
Scheduler may not return allocations that violate release or hard dependency precedence. Deadline-infeasible cases are surfaced rather than "solved" by violating constraints.

## I27 — Deadline safety preference
When a feasible alternative exists, the scheduler should avoid intentionally placing deadline-constrained completion on/too near the deadline merely to improve workload balance.

## I28 — Honest infeasibility
ARC may contain valid user facts for which no feasible schedule exists. It must surface this rather than falsifying constraints.

## I29 — Explicit impossible-plan consent
When a user mutation predictably creates overload/infeasibility, ARC requests confirmation before committing where practical.

## I30 — Idempotent reconciliation
Reconciliation with identical canonical facts and time context produces equivalent derived state.

## I31 — Round-trip robustness
A reversible transition followed by its valid inverse, with no relevant intervening mutation, restores the prior semantic state.

## I32 — Restore-current-world validation
Restore/undo never blindly reinstates relationships that are invalid in the present graph.

## I33 — Atomic transactions
Compound operations either commit a valid final canonical mutation or do not commit; intermediate invalid state is never externally visible.

## I34 — View coherence
After reconciliation/rescheduling, Planner, Priority, Timeline and Focus project the same canonical truth.

## I35 — Convenience isolation
Current-focus selection and other convenience-only state do not silently alter priority, anchors, deadlines or schedule.

## I36 — Long-run non-degradation
Repeated valid lifecycle transitions do not accumulate semantic drift or progressively degrade data quality.
