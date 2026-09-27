# ARC Scheduler

ARC Scheduler is the production scheduling engine, certification suite, and research history for ARC.

## Repository responsibilities

1. **Production scheduler engine**
   - Pure Python scheduling contracts and optimisation logic.
   - Must not depend on Django, HTTP, database models, or frontend code.

2. **Scheduler certification**
   - Deterministic regression fixtures and behavioural certification.
   - Includes saturated-world, human-review, and lifecycle/reversibility tests.

3. **Planning-domain reference implementation**
   - The Arena Django backend contains the authoritative planning-state semantics,
     invariants, state transitions, and contract tests created during scheduler research.
   - It remains intact until those semantics are safely transplanted into ARC.

4. **Research archive**
   - Historical algorithms, exact-oracle work, tuning, experiments, datasets,
     benchmarks, and rejected approaches.

## Architecture boundary

ARC canonical state
→ ARC input adapter
→ SchedulerInputVx
→ ARC Scheduler engine
→ SchedulerOutputVx
→ ARC output/persistence adapter
→ derived schedule views

Canonical state, scheduler engine, and scheduler output are independent concerns.

The scheduler engine must not query or mutate Django models directly.

## Documentation

- `docs/arc-scheduler.md`
- `docs/canonical-state-input.md`
- `docs/arc-scheduler-output.md`
- `docs/arc-scheduler-flavours.md`
- `docs/scheduler-architecture.md`
- `docs/scheduler-versioning.md`
- `docs/scheduler-change-process.md`
- `docs/scheduler-known-limitations.md`
- `docs/database/database-schema.md`
- `docs/database/database-migrations.md`
- `docs/testing/tests.md`
- `docs/testing/tests-needed.md`
- `docs/testing/benchmark-methodology.md`
- `docs/integration/arc-scheduler-integration.md`
