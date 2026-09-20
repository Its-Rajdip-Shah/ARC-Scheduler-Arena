# ARC Conflict Resolution

ARC distinguishes domain-invalid state from valid-but-conflicting/infeasible user intent.

## Categories

### Invalid — reject transaction
Examples:
- hierarchy cycle;
- dependency cycle/self-edge;
- dangling active relation;
- malformed progress outside 0..100;
- transaction that would leave dependency semantics internally contradictory without explicit dependency removal.

### Valid but risky — warn/confirm
Examples:
- child deadline later than parent;
- child release earlier/later than parent;
- explicit anchor creating extreme overload;
- manual temporal edit creating a highly pressured plan.

### Valid but conflicting/infeasible — preserve facts and surface
Examples:
- constraints/work volume admit no feasible deadline-safe schedule;
- existing anchor later becomes impossible because a new dependency/release constraint is introduced;
- restore/undo intent conflicts with newer canonical changes.

## Resolution patterns

### Dependency contradiction
If `A -> B` and the user tries to complete B while A is incomplete:
1. Cancel completion; or
2. Explicitly remove `A -> B` and proceed.

If both are complete and the user reopens A:
1. Cancel reopen; or
2. Explicitly remove dependency and reopen A.

If product UX later supports propagating dependent reopening, it must be an explicit offered action, not silent behaviour.

### Anchor beyond deadline
Offer:
1. Change deadline to permit the requested anchor, then anchor; or
2. Cancel anchor/move.

### Anchor before release
Offer:
1. Change release to permit requested anchor, then anchor; or
2. Cancel anchor/move.

### Anchor becomes impossible after later mutation
Do not silently move/delete either fact. Surface conflict and require explicit resolution (move/remove anchor, alter dependency/release/deadline, or cancel the new mutation if still pending).

### Parent/child temporal divergence
Creation form starts from parent values. If the user explicitly changes them, preserve the chosen child value. Surface surprising/risky divergence where appropriate; do not silently resynchronize siblings/parent.

### Delete dependency endpoint
Remove/suspend incident active edges from executable graph while retaining enough history for restore. Restoring endpoint attempts relationship restoration only if valid now.

### Restore into changed hierarchy/graph
Restore original placement/relationships only when currently valid. Otherwise require resolution/destination; never invent a new parent silently.

### Undo after later mutations
Undo is a validated inverse against the current world, not database time travel. If inverse conflicts with newer decisions, require resolution.

### User-created overload/infeasibility
Warn with the reason before commit when detectable. If user confirms, preserve the canonical intent and visibly flag pressure/infeasibility.

### Constraint-created infeasibility
No confirmation is possible because no single new user action caused it. Preserve constraints, produce useful least-bad scheduling information where possible, and flag infeasibility clearly.
