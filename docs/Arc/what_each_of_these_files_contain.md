1. general_rules.md — the universal rules we’ve discovered.
2. canonical_state.md — canonical vs derived vs scheduler vs UI ownership.
3. states.md — ARC’s multidimensional state space.
4. domain_commands.md — the legal mutation boundary for all views.
5. state_transitions.md — the master lifecycle catalogue, including creation, complete/reopen, hierarchy, reparenting, delete/restore, priority, dependencies, temporal edits, anchors, duration/progress, large allocations, Focus, Timeline/scheduler, compound mutations and test dimensions.
6. invariants.md — conditions that must survive every committed transition.
7. conflict_resolution.md — dependency conflicts, temporal contradictions, undo/restore conflicts, overload and infeasibility.
8. arc_guaranteed.md — everything ARC itself guarantees regardless of scheduler.
9. algorithm_manages.md — exactly what algorithms are allowed to optimize versus what they’re forbidden to touch.