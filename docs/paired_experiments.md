# C6.1 pure paired experiment core

`arena.experiments` exports frozen, slotted `WorkloadCase`, `ConstructorArm`,
`ImproverArm`, and `TrialRecord`, plus `run_trial` and `run_grid`. It operates on
supplied immutable `ScheduleProblem` objects, with no Django, database,
reconstruction, persistence, or global random-number-generator access.

```python
from arena.experiments import (
    WorkloadCase, ConstructorArm, ImproverArm, run_grid,
)

# Supply problem, constructor, bounded C4 engine, and explicit objective.
records = run_grid(
    [WorkloadCase('example', 'supplied', problem, workload_seed=42)],
    [ConstructorArm('constructor', constructor)],
    [ImproverArm('none', None), ImproverArm('search', engine)],
    [7, 8],
    comparison_objective=objective,
)
```

The caller chooses workloads, arms, seeds, and the comparison objective. The core
chooses no methodology, scalar winner, ranking, or Pareto frontier. Grid nesting
is exactly workload → constructor → improver → seed, preserving caller order.
Each combination invokes the constructor once, including no-improver cells.
Algorithm failures still occupy their intended cells. The whole grid, including
configuration serialization, is validated before its first trial.

IDs and family must be nonempty strings; seeds are exact integers, excluding
booleans. Each grid axis is a nonempty sequence; workload IDs, constructor IDs,
improver IDs, and seeds are unique within their respective categories. Only the
six existing C4 engine classes (HC, VNS/VND, tabu, SA, LNS, ALNS) or `None` are
accepted. Both `max_iterations` and `max_evaluations` must be explicit,
nonnegative integers. Each engine's objective must equal the explicitly supplied
`comparison_objective`. C3 constructor costs may differ and are never rewritten.

Seed-bearing configurations are copied with `dataclasses.replace(seed=run_seed)`
and used to construct a new engine of the same class. Deterministic engines are
used as supplied. The recorded seed exists even for deterministic arms; supplied
arms remain unchanged. Provenance records the effective configuration.

## Records and failures

The constructor must return a `SchedulePlan`. Exceptions deriving from
`Exception` and wrong return types yield `constructor_error`. A returned plan is
validated and the same validation object is passed to C1 evaluation. Hard
violations yield `constructor_invalid`; canonical infeasibilities yield
`constructor_infeasible`, with hard invalidity taking precedence. Both retain
the initial plan and C1 diagnostics and skip improvement. Soft violations remain
permitted.

Strict `SearchState.from_plan` conversion may reject a validator-accepted plan
with noncanonical session pieces. This yields `constructor_unsearchable` with
the exception type/message and initial C1 diagnostics intact. The frozen C4
conversion performs its own internal validation; the runner does not alter it.
A searchable initial state is scored with the comparison objective.

No-improver records reuse the initial plan, validation, performance, and objective
as final values, with zero iterations/evaluations, `improver_seconds=0.0`, and
`termination_reason='no_improver'`.

For improvement, the result must retain the converted initial state and the
supplied problem. The final state is exported, independently validated and
observed through C1, and scored through C4. Its recomputed objective must equal
the engine's reported final objective. Engine exceptions or result contract
failures yield `improver_error`: initial diagnostics remain, while all final
fields remain empty. No failure fabricates a final metric. Evaluation/objective
configuration errors propagate with workload and arm context in exception notes;
they are never relabeled as infeasibility. `BaseException` is not swallowed.

C1 metrics are observations; the C4 objective is recorded separately. The C1
vector is never search feedback. Constructor and improvement calls are timed
separately with `perf_counter`; total elapsed time includes conversion,
validation, and C1 evaluation, after argument/provenance preparation. A skipped
improver has `None` time; the explicit no-improver arm has zero time.

## Provenance format

JSON uses sorted keys, compact separators, and rejects nonfinite numbers.
Algorithm envelopes contain their qualified `class` and their `config` when
present. Frozen dataclasses contain qualified `class` and declared `fields`.
Mapping scalar keys become sorted strings (including C3/C4 integer priority
positions); collisions after normalization are rejected; tuples/lists become arrays; frozensets use
canonical JSON order. Enums use their values, dates ISO format, and finite
Decimals their exact strings. Null, bool, string, integer, and finite float are
supported. Unsupported objects and mutable dataclasses are rejected; there is
no repr or arbitrary object-attribute serialization. Workload/problem objects
and their database item IDs are not traversed for algorithm provenance.

## Paired hand-check

Two atomic items share capacity one. Item 1 has priority position 2 and is due
today; item 2 has position 1 and is due on day 2. Priority multipliers are 1 and
3 respectively. Priority weight is 1, quadratic overload weight 10, and other
weights zero. PressureGreedy (horizon 2) schedules item 1 today and item 2 on
day 1. HC (FIRST, horizon 2, limits 10 iterations/100 evaluations) swaps them.

| Observation | Constructor only | Constructor + HC |
| --- | --- | --- |
| Item 1 / item 2 day | 0 / 1 | 1 / 0 |
| C4 priority cost / total | 3 / 3 | 1 / 1 |
| C1 priority inversions | 1 | 0 |
| C1 deadline misses | 0 | 1 |
| C1 mean start delay | 0.5 days | 0.5 days |
| C1 excess sessions | 0 | 0 |
| Hard violations / canonical infeasibilities | 0 / 0 | 0 / 0 |

This is a recorded tradeoff, not a winner criterion.

## Scope boundary

An evaluation-count limit is **not an equal runtime budget**. Declared iteration
and evaluation limits do not guarantee equal wall-clock runtime; measured times
are observations, never retrospective claims that a time budget was enforced.
Frozen V1 reconstruction, stable per-item keys in saved artifacts, durable run
manifests, and actual wall-time enforcement are the **next C6 slice**. This core
does not implement C7/C8 or change frozen modules or Benchmark V1.
