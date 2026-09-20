# What ARC Guarantees

These guarantees are backend/domain responsibilities and must hold regardless of which scheduling algorithm flavour is injected.

1. One coherent canonical task/planning state across all views.
2. Valid cycle-free hierarchy.
3. Valid cycle-free explicit dependency graph.
4. No dangling active relationships.
5. Correct frontier/executability derivation.
6. Hard dependencies are never silently violated.
7. User priority is preserved as preference rather than confused with precedence.
8. Explicit anchors/manual planning intent are not casually overwritten by automatic scheduling.
9. Release/deadline edits are never silently manufactured to make scheduler output convenient.
10. Parent/child date defaults remain editable explicit task values.
11. Completion/reopen/decompose/recompose/reparent/delete/restore operations reconcile all affected derived state.
12. Original project scope survives structural lifecycle transitions.
13. Residual-parent effort is closure work and does not progressively inflate/corrupt original estimates.
14. Splittable-task confirmed progress is preserved across reschedules.
15. Scheduler proposals cannot masquerade as confirmed progress.
16. Progress-segment reversal is local and recoverable.
17. Duration-category edits follow frozen progress semantics.
18. Large work can be scheduled over multiple days without forcing semantic task decomposition.
19. Atomic work remains one-day scheduling work.
20. Overdue state is correctly distinguished from missed anchor/manual intent.
21. Valid but infeasible user plans remain representable and are reported honestly.
22. Detectable user-created impossible/overloaded choices require informed confirmation.
23. Scheduler failure cannot partially corrupt canonical state.
24. Reconciliation is repeatable/idempotent.
25. Valid inverse transitions round-trip when no intervening relevant change occurred.
26. Restore/undo validates against the present world.
27. Compound mutations are atomic.
28. Convenience-only interactions do not unexpectedly reschedule/reprioritise work.
29. All views update from canonical results; users do not need to bounce between views repairing inconsistencies.
30. Algorithms receive clean, reconciled inputs: backend lifecycle corruption must not be the hidden cause of GIGO.

## Human-centric guarantee

ARC gives the scheduler maximum freedom over unspecified choices and progressively less freedom as the user expresses intent. Explicit human decisions remain sticky until revoked, expired by their defined semantics, or made impossible/conflicting by another explicit fact—at which point ARC surfaces the conflict rather than secretly choosing for the user.
