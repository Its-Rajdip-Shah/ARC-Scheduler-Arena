# C6.2: durable Benchmark V1 runs

C6.1 (`paired.py`) runs pure paired trials on supplied `ScheduleProblem`s.
C6.2 connects that core to explicitly selected frozen V1 scenarios, isolates each
trial in a fresh spawn process, enforces a wall-clock deadline, and saves durable
artifacts. It records independent C1 observations and C4 optimization scores in
separate fields. It does not select a winner, rank algorithms, tune parameters,
or compute Pareto frontiers.

## Explicit usage

Run from an importable Python script with a main guard. Set up the backend import
path and Django settings in the caller environment. Keep Django initialization
inside the main guard: spawn imports the script in children. Constructors must
be importable module-level classes with pickleable pure state. Their modules
must not initialize Django, query the database, or reconstruct workloads.
Importing `arena.experiments` itself neither imports nor initializes Django.

```python
from pathlib import Path
from arena.algorithms import PressureGreedy, GreedyObjectiveConfig
from arena.experiments import ConstructorArm, ImproverArm, V1RunConfig, run_v1_experiment
from arena.scheduling.objectives import (
    DeadlineRisk, PriorityPostponement, OverloadCost, MovementCost, PowerCost,
)
from arena.search import PlanObjectiveConfig

if __name__ == '__main__':
    import django
    django.setup()  # DJANGO_SETTINGS_MODULE=arc_backend.settings; backend on PYTHONPATH

    objective = PlanObjectiveConfig(
        deadline=DeadlineRisk(PowerCost(1.0, 2), 2),
        priority=PriorityPostponement(PowerCost(0.0, 1), {}, 0.0),
        overload=OverloadCost(PowerCost(10.0, 2), True),
        movement=MovementCost(0, PowerCost(0.0, 2)),
        timing=PowerCost(0.0, 2),
    )
    constructor_config = GreedyObjectiveConfig(
        objective.deadline, objective.priority, objective.overload,
        objective.movement, objective.timing, horizon_days=30,
    )
    result = run_v1_experiment(V1RunConfig(
        scenario_ids=('G000-R0',),
        constructors=(ConstructorArm('pressure', PressureGreedy(constructor_config)),),
        improvers=(ImproverArm('none', None),),
        seeds=(7, 8),
        comparison_objective=objective,
        trial_wall_seconds=30.0,
        output_dir=Path('v1-example-run'),  # must not already exist
    ))
    print(result)
```

These settings illustrate explicit inputs; they are not recommended or tuned
experimental parameters. For workloads with positioned priorities, provide the
required position multipliers in the objective and constructor configurations.

All four axes must be nonempty tuples without duplicate IDs/seeds. IDs are
nonempty strings and seeds are exact integers (not booleans). The wall budget
must be finite and positive. There are no implicit axes, seeds, objectives, or
budgets. Static configuration errors and unknown scenario IDs are rejected
before creating the output directory or reconstructing a workload. The entire
scenario matrix is prepared using C6.1 `_prepare` before its first worker starts;
seed-bearing improver configurations retain C6.1's effective seed provenance.

## Reconstruction and stable identity

Only requested scenarios run, in caller order. Each is reconstructed once inside
a database transaction. The existing reconstruction function checks regenerated
Φ89 against the frozen mapping. A `BenchmarkDriftError` propagates immediately;
it is never an algorithm failure. The runner extracts the immutable problem,
frozen metadata/Φ89, and a one-to-one mapping of problem item IDs to generator
keys. Missing or duplicate mappings fail the run.

The transaction is rolled back and database connections are closed before any
child starts. Generated users, items, dependencies, and progress are not
persisted. Use a caller context where closing database connections is appropriate,
outside caller-owned transactions. Database sequences can advance despite a
rollback, so primary keys are not reproducible artifact identities. Artifacts
use stable generator keys, scoped by scenario ID. No ORM objects or materialized
workloads are transported to workers or serialized into artifacts.

## Isolation and timing

Each cell uses `multiprocessing.get_context('spawn')`, including macOS. This
implementation uses POSIX pipe descriptors and supports macOS/Linux. A narrow
`copyreg` reducer transports `MappingProxyType` values and restores new immutable
mapping proxies, including nested capacity/priority mappings.

A monotonic timer starts immediately before `process.start()`. The parent drains
a length-prefixed tagged result through a one-way pipe using nonblocking reads
and a deadline, before joining the child. Even a partial or large message is
subject to that deadline. This avoids both join-before-receive deadlocks and
blocking indefinitely after only the first bytes arrive.

The budget covers spawn/startup, C6.1 configuration preparation, construction,
improvement, validation, C1 observation, C4 scoring, and result transmission.
On expiry, the parent terminates, briefly joins, escalates to kill if needed,
and reaps the worker. `worker_wall_seconds` is observed elapsed time; timeout
observations include cleanup and may exceed the nominal budget. Process launch
and OS scheduling also have overhead. C6.1's `constructor_seconds`,
`improver_seconds`, and `total_seconds` are preserved separately when available.
Reconstruction, parent serialization, and durable file writes add run overhead
outside the per-trial budget. Iteration/evaluation limits do **not** imply equal
runtime. Hard termination cannot recover a partial plan or partial metrics.

## Artifact schema (version 1)

The new directory contains UTF-8 strict JSON: unsupported values and nonfinite
numbers are errors, never `repr()` strings or NaN/Infinity tokens.

`manifest.json` contains:

- `schema_version=1`, `benchmark_version="v1"`, and run `status`;
- requested `scenario_ids`, `axis_order`, constructor/improver IDs, and seeds;
- normalized `comparison_objective`, `trial_wall_seconds`, and `expected_trials`;
- `completed_trials` (durable cells, **including timeouts**), `successful_trials`
  (C6.1 `ok` cells), and `timed_out_trials`;
- SHA-256 of the frozen benchmark manifest, `benchmark_manifest_sha256`;
- a `scenarios` array, populated once each scenario is reconstructed, containing
  scenario ID, workload seed, design/replicate indices, family `benchmark_v1`,
  the full `frozen_features` Φ89 mapping, and sorted `stable_item_keys`;
- on completion, `records_sha256`; on failure, concise `error.type/message`.

`records.jsonl` has exactly one line per completed grid cell, in scenario →
constructor → improver → seed order, with consecutive zero-based `trial_index`.
Each envelope contains scenario metadata, arm IDs, `run_seed`, C6.1's exact
`constructor_config_json` and effective `improver_config_json` strings, normalized
comparison objective, status, observed `worker_wall_seconds`, and `trial`.

For a returned worker record, `trial` preserves every declared C6.1 field:
status, configuration, timings, iteration/evaluation counts, termination and
error fields, initial/final plans, validations, C1 performance, and C4 objective.
All declared C1 fields are retained, including nulls. C4 retains every declared
component plus `total`. Dates are ISO strings; percentages/Decimals are exact
decimal strings; tuples are JSON arrays. All three validation categories retain
codes and dates. Allocations use `item_key`; violations use `item_key` and
`related_item_key`. Unknown references become null with `unknown_item=true` or
`unknown_related_item=true`, respectively. Raw unknown numeric IDs are not saved
as structured item references. Free-form C6.1 error/diagnostic text is preserved
as text and should not be interpreted as stable identity data.

Timeout envelopes have `status="wall_timeout"` and `trial=null`. They have no
fabricated plan, metrics, iterations, or constructor/improver timing. Returned
C6.1 statuses (`constructor_invalid`, `constructor_infeasible`,
`constructor_unsearchable`, `constructor_error`, `improver_error`, `ok`) remain
unchanged. An algorithm error can be a valid completed cell; a worker exception,
abrupt exit, or identity mismatch is a runner failure, not an algorithm status.

## Durability and interruptions

After each full JSONL line, the runner flushes and fsyncs the records file before
incrementing the manifest count. Manifest replacement uses a temporary file in
the same directory, flush/fsync, atomic `os.replace`, and directory fsync. Its
completed count cannot lead durable lines. After the full matrix, the runner
checks the cell count, hashes the records, and marks the manifest `complete`.

Reconstruction, worker, serialization, and filesystem errors preserve prior
committed lines, attempt to mark the manifest `failed`, and re-raise. An abrupt
crash or failure to write the failure manifest can leave `running`, a lagging
count, or a partial final line. Such a run is incomplete; a consumer must not
interpret it as complete. No resume, overwrite, implicit deletion of existing
runs, or benchmark/report mutation is supported. Start a new directory instead.

C7 still needs its prescribed configuration/selection methodology; C8 still
needs the algorithm face-off and comparison analysis; C9 still needs downstream
workload/performance mapping and selection work. These artifacts provide stable
scenario/key joins, frozen workload characteristics, independent observations,
and optimization scores without making those later methodological decisions.

## Parallel resumable execution

C7 and later stages may execute frozen C6.2 cells through
`run_v1_experiment_parallel`. This does not change the trial contract:
each cell still uses C6.2's fresh spawn-isolated `_isolated_trial` with the
same workload, constructor, improver, seed, comparison objective and
per-trial wall-clock budget.

Parallelism is parent-side orchestration only. Several independent cells may
be in flight simultaneously, but durable `records.jsonl` entries are committed
strictly in canonical scenario -> constructor -> improver -> seed order.
Completion order therefore cannot alter trial identity or artifact order.

The parallel manifest records the worker count, a caller-declared execution
environment identifier, Python/platform metadata and logical CPU count.
`max_workers` is execution provenance, not candidate identity.

Runs are prefix-resumable. Only complete fsynced JSONL records in canonical
order are trusted. An unterminated crash tail is discarded and rerun. Complete
corrupt lines are never hidden. Resume requires the same worker count and
execution-environment identifier so different CPU-contention regimes cannot
silently share timeout evidence.

Wall-clock timings are expected to differ from serial execution. Scientific
equivalence therefore means identical identities, configs, statuses when not
budget-clipped, schedules, validation results, C1 performance vectors,
objectives, iterations/evaluations and termination reasons; timing fields are
not expected to be numerically equal.

Before a worker count is used for a C7/C8 campaign it must be validated against
serial/low-concurrency execution on a representative sample. If increased
concurrency materially changes timeout classification or non-timing results,
that worker count is not valid for that campaign resource regime.

### Deterministic work budget versus wall safety fuse

Parallel execution records
`algorithm_budget_basis=explicit_max_iterations_and_max_evaluations` and
`wall_clock_role=safety_fuse` in execution provenance.

The improver work allowance is therefore defined by its explicit deterministic
iteration/evaluation limits. The outer wall timeout remains necessary for
process safety, but future high-concurrency campaigns must choose it generously
enough that ordinary CPU contention does not determine candidate eligibility.

A completed parallel directory may be opened with `resume=True`. It is not
modified: the runner validates its canonical records, counts and SHA-256 and
returns the existing result. This allows whole tuning campaigns to resume
safely after interruption without rerunning already-complete objective groups.

## Disposable cloud execution protocol

Paid cloud workers are disposable execution nodes, never canonical repositories.

Cloud deployment uses `scripts/cloud/make_bundle.sh`.
The bundle excludes Git internals, virtual environments, local databases, `.env` files, private keys and caches.

Fresh Linux nodes are initialised with:

```text
./scripts/cloud/bootstrap.sh
```

Before paid experiments, run:

```text
./scripts/cloud/verify.sh
```

Cloud nodes must not contain production credentials or production databases.
Experiment results must be copied off before node destruction.
