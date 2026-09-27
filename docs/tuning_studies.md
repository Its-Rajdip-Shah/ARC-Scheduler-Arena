# C7.1 tuning-study plans

`arena.tuning` plans and durably registers the specified C7 study. It does not
execute tuning, constructors, improvers, C6.2 runs, or schedule evaluation, and
it does not select finalists. Importing it needs neither Django settings nor a
database. C7.2 will execute its `run_configs` and analyze their records; C8 will
evaluate the reserved holdout. C7 must not consume holdout results for selection.

## Split and reproducibility

The planner reads only frozen V1 `manifest.json` and `workloads.json`, checks the
ordered scenario identities, and requires 59 designs with two distinct
replicates each (118 scenarios). It reads design and replicate identity from
metadata, never from scenario names. Designs are ordered by SHA-256 digest bytes
of UTF-8 `f"{split_seed}:{design_index}"`, breaking ties by design index. The
first `development_design_count` designs form development; the rest are holdout.
Both partitions retain manifest scenario order. Keeping both replicates of a
design together prevents replicate leakage between development and holdout.
The split uses design identity, never Φ89 values or scheduler results.

The caller supplies an exact integer split seed and a development count from
1 through 58. Explicit scenario lists, the seed, design counts, and the hash of
the original manifest bytes are saved in `study_plan.json`.

## Declaring axes

All public records are frozen, slotted dataclasses. Construct a `TuningStudySpec`
with an explicit `PlanObjectiveConfig`, tuples of constructor and improver
sweeps, unique integer run seeds, split controls, positive finite per-trial wall
budget, explicit positive integer limits, and a previously nonexistent `Path`.
The four named C3 greedy families and `EarliestFeasible` are accepted by exact
type. The six C4 engines accepted by C6.1 and `None` are accepted by exact type.
Configless `EarliestFeasible` and `None` must have zero axes.

For example, given explicit `objective`, `constructor`, and bounded `hc`:

```python
from pathlib import Path
from arena.tuning import (
    TuningAxis, ConstructorSweep, ImproverSweep, TuningStudySpec,
    plan_tuning_study, write_tuning_plan,
)

spec = TuningStudySpec(
    objective=objective,
    objective_axes=(
        TuningAxis('deadline.cost.weight', (1.0, 3.0)),
        TuningAxis('overload.cost.exponent', (1.0, 2.0)),
    ),
    constructors=(ConstructorSweep('pressure', constructor, (
        TuningAxis('horizon_days', (20, 30)),
    )),),
    improvers=(ImproverSweep('hc', hc, (
        TuningAxis('max_iterations', (20, 40)),
    )), ImproverSweep('none', None, ())),
    seeds=(7, 8), split_seed=42, development_design_count=2,
    trial_wall_seconds=30.0, max_candidates=24, max_trials=192,
    output_root=Path('study-example'),
)
plan = plan_tuning_study(spec)  # no filesystem writes or scheduling
path = write_tuning_plan(plan)  # register only; does not execute run_configs
```

These values illustrate declarations, not tuned or recommended parameters.
Here O=2×2=4, C=2, I=2+1=3, giving 24 candidates and
24×4 development scenarios×2 seeds=192 intended trials.

Objective axes can target `deadline.cost.weight`, `deadline.cost.exponent`,
`deadline.buffer_days`, `priority.cost.weight`, `priority.cost.exponent`,
`priority.multipliers`, `overload.cost.weight`, `overload.cost.exponent`,
`movement.fixed_weight`, `movement.distance.weight`,
`movement.distance.exponent`, `timing.weight`, and `timing.exponent`.
A whole priority mapping is one value, e.g.
`TuningAxis('priority.multipliers', ({1: 4, 2: 2}, {1: 3, 2: 1}))`.
The existing frozen configuration validates its priority semantics.
Constructor axes address the analogous `GreedyObjectiveConfig` fields and
`horizon_days`; C3 objectives remain independent of C4 comparison objectives.

Search axes address fields declared by that engine's configuration, for example
`neighbourhood.horizon_days`, `max_iterations`, `max_evaluations`, `tabu_tenure`,
`cooling_rate`, or `destroy_count`. Both search limits must resolve to explicit
nonnegative integers for every variant. Paths traverse declared frozen
dataclass fields only; mapping keys, expressions, and arbitrary attributes are
not supported. Any `seed` path and improver `objective` paths are forbidden.
Numeric axes reject booleans; genuine boolean configuration switches remain
boolean axes. Existing dataclass validation rejects invalid parameter values.

Each values tuple must be nonempty and contain no duplicate C6.1-normalized
values. Paths cannot repeat within one axes tuple. Recursive dataclass
replacement creates variants without mutating templates or their mappings.
Zero axes produce one variant. Caller axis order is retained, with the last
axis varying fastest. Candidate traversal is objective variant → constructor
sweep/variant → improver sweep/variant.

## Bounds, grouping, and effective seeds

Before generating Cartesian products, the planner calculates
`O * C * I`, where C and I are sums of variant counts across their sweeps.
Expected trials are that product times development scenario count times seed
count. Exceeding either explicit limit raises `ValueError`; nothing is sampled
or truncated and no directory is created.

Each objective variant produces one C6.2 `V1RunConfig` containing the complete
constructor × improver grid, the supplied seeds and wall budget, and only the
development scenarios. Each cell has exactly one candidate. This grouping
avoids reconstructing V1 once per candidate. The intended run directory is
`output_root / ('objective_' + objective_id)`; registration does not create it.

A fresh engine receives each comparison objective; constructors retain their
own costs. Every pair is checked with C6.1 `_prepare` on an empty pure workload
for every requested seed. For seeded engines, C6.1 replaces the template seed
with the run seed. JSON provenance and generated improver identities include
the effective configurations for all supplied run seeds. Changing an unused
template seed therefore does not change candidate identity. Deterministic
engines and `None` still participate in every requested seed cell.

Objective IDs are full SHA-256 hashes of C6.1 canonical normalized JSON.
Generated arm IDs contain the parent sweep ID and a full configuration digest;
candidate hashes contain the objective ID and both arm IDs/configuration JSON.
Duplicate effective identities and unequal-payload collisions are rejected.
IDs do not depend on output paths, wall time, Python hashes, or database IDs.

Different comparison objectives put C4 totals on different scales. Raw C4
totals cannot select a winner across objective groups. C7.2 must compare
independent C1 observations and explicitly declared runtime/robustness criteria.

## Durable registration

`write_tuning_plan` returns `output_root/study_plan.json`. Its schema version 1
includes the benchmark hash, split, normalized sweep/axis declarations,
objective groups and intended directory names, C6.1 configuration JSON,
effective seed provenance, ordered candidate references, budgets and counts.
It contains no workload materializations, database IDs, pickles, execution
results, or inferred winners.

Serialization uses strict UTF-8 JSON (`allow_nan=False`) before creating the
root. Root creation and file creation are exclusive; existing paths, including
dangling symlinks, are rejected. The file is flushed and fsynced, then the root
and its parent directory are fsynced. A caught write/fsync failure removes the
incomplete artifact. An abrupt process or machine interruption can still leave
an incomplete registration; do not treat a partial/unparseable file as a plan,
and use a fresh root instead of overwriting it.

Run checks with `.venv/bin/python -m pytest arena/tuning/tests -q` and the Arena
suite with `.venv/bin/python -m pytest arena -q`.


Axis values are recursively detached when a study is planned. Mappings become
read-only copies and nested lists become immutable tuples. Changing an original
caller-owned dictionary or list afterward cannot change the registered axis
declaration or make it disagree with the generated candidates.


## C7.2 development execution and evidence ingestion

C7.2 begins by executing the development-only run configurations already
frozen by C7.1. `execute_tuning_study(plan)` requires the exact registered
`study_plan.json`, preflights every C6.2 run before starting the first group,
and then delegates each objective-group matrix to the frozen C6.2 runner.
It does not add scenarios, resume/overwrite prior runs, evaluate holdout,
or select a finalist.

`load_tuning_results(output_root)` independently rereads the durable C7.1/C6.2
artifacts. It verifies the benchmark hash, complete run manifests, records
hashes, development scenario order, constructor/improver/seed axes,
comparison-objective provenance, effective configurations, trial order and
candidate identities. A holdout scenario appearing in a tuning run is an error.

Each registered candidate receives exactly one paired development matrix across
the registered development scenarios and seeds. The loader reports successful,
timed-out and algorithm-failure counts, success/timeout rates, mean observed
worker wall time, and unweighted macro-means plus observation counts for
available final C1 `PerformanceVector` fields.

These summaries are descriptive evidence, not a ranking. C7.2 does not compare
raw C4 objective totals across different objective groups, does not collapse
C1 dimensions into an implicit scalar, does not choose Pareto directions
implicitly, and does not consume the reserved holdout. Selection methodology
and explicitly declared quality/runtime/robustness criteria remain a separate
tuning decision built on this validated evidence.


## C7.2b selection methodology and C7.3 calibration

C7 selection is explicitly non-scalar. `SelectionPolicy` declares the C1
dimensions and directions used for a comparison. Reliability and feasibility
gates run before quality comparison. The frozen C7 V1 policy requires every
intended development trial to complete successfully, permits no timeout or
algorithm-failure cells, and requires zero hard violations and zero canonical
infeasibilities.

The C7 V1 Pareto dimensions are deadline miss rate, mean lateness, priority
inversion rate, unapproved excess sessions, fragmentation rate, dependency wait,
movement distance and start delay. All are minimized. A metric participates only
when it has usable evidence for every eligible candidate; by default its
observation count must also be identical across eligible candidates. Missing
quality is never replaced with zero or another invented value.

Pareto dominance is exact: candidate A dominates B only when A is no worse on
every active metric and strictly better on at least one. There is no weighted
sum, epsilon, lexicographic preference, C4 objective comparison, runtime
tie-break, implicit ranking or selected winner. Candidate order is retained
only for deterministic reporting.

Before the full hyperparameter sweep, C7 runs a bounded family calibration
study. It uses the same fixed Benchmark V1 split seed with 47 of 59 designs
(94 scenarios) as development and 12 designs (24 scenarios) reserved as
holdout. Holdout scenarios are not executed by tuning.

The calibration study intentionally has no tuning axes. It contains one
representative nondegenerate configuration for each of the four C3 constructor
families and eight improver arms: none, HC, VND, VNS, Tabu, SA, LNS and ALNS.
With one calibration run seed this gives 32 candidates and exactly 3008 trials.

Calibration parameters are not production recommendations. Their purpose is to
exercise all families over the full development workload distribution under
bounded internal search limits and a five-second per-trial wall budget. The
resulting runtime, timeout, failure and C1 evidence determines which search
budgets and hyperparameter regions are practical for the subsequent full
development tuning campaign. Calibration does not consume holdout results and
does not itself select production finalists.


## Calibration finding: paired selection and timeout safety

The first C7 family calibration completed all 3008 registered development
trials, but exposed two methodological hazards before the full tuning sweep.

First, Benchmark V1 contains development cells on which every tested candidate
returns a structural constructor status. Such cells cannot be treated as a
candidate-specific failure and cannot be allowed to make every candidate
ineligible.

Second, a tight experiment wall budget can create cells on which no candidate
returns a successful schedule. These cells are unresolved, not evidence that
all algorithms are poor. The frozen selection path therefore refuses to select
finalists while any no-success cell contains a timeout or execution error.

C7 selection now retains per-candidate scenario/seed observations. A cell is:

- scorable when at least one candidate succeeds;
- structurally unscorable when every candidate reports a structural constructor
  status;
- unresolved when nobody succeeds and at least one result is a timeout or
  execution failure.

Candidate timeout/failure gates are evaluated only on scorable cells.
Quality comparison is strictly paired: eligible candidates are compared only on
scenario/seed cells where every eligible candidate succeeded, and each C1 metric
uses only the subset of those paired cells where that metric is defined for
every eligible candidate. Missing metrics are never imputed.

The first calibration also showed substantial five-second clipping, especially
for simulated annealing. C7 therefore performs a dedicated budget probe before
the full tuning campaign. The probe keeps the frozen 94-scenario development
partition, uses all four constructors, compares no improvement with SA at 80
and 160 evaluations, raises the whole-trial wall budget to 15 seconds, and
contains exactly 12 candidates / 1128 trials. The probe is diagnostic only and
does not eliminate SA or consume holdout scenarios.

## Parallel campaign resource contract

The calibration experiments showed that a tight wall-clock limit cannot serve
as the scientific work budget once many trials execute concurrently. Operating
system scheduling, cache/memory contention and machine load can change elapsed
wall time even when the candidate performs exactly the same deterministic
algorithmic work.

C7 therefore separates two concepts for future parallel campaigns:

1. **Algorithmic budget** — the explicit `max_iterations` and
   `max_evaluations` already frozen into each C4 improver configuration. These
   define the reproducible search-work ceiling and are part of configuration
   provenance.

2. **Wall-clock safety fuse** — a deliberately generous outer process timeout
   used only to stop hangs/pathological execution. It is not the candidate's
   intended amount of optimisation work.

`C7_PARALLEL_SAFETY_WALL_SECONDS` is the default safety-fuse value for the next
C7 campaign design. Completed historical 5-second and 15-second calibration
studies remain immutable evidence and are not rewritten.

`execute_tuning_study_parallel` executes only the registered development
workloads and delegates every cell to the resumable parallel C6 runner.
Worker count and execution-environment identity are execution provenance.
Candidate identity, objective identity, workloads, seeds and deterministic
algorithm budgets are unchanged.

High-concurrency campaigns must still be calibrated on the target machine.
The chosen worker regime is frozen for a campaign. Wall-clock performance
measurements used for scientific runtime comparison should be collected under
a controlled resource regime rather than interpreted from a heavily contended
bulk-throughput run.

## C7.4c full development confirmation

C7.4c begins only after C7.4b racing is frozen. It does not reopen the
60-candidate search space and it does not access holdout scenarios.

The 21 frozen C7.4b survivors are confirmed over all 53 independently
proven-feasible development scenarios with two previously unused run seeds,
1702 and 1703. The C7.4b seed 1701 matrix is retained as historical
development evidence but is not used as the fresh confirmation replication.
The 41 independently proven-infeasible development scenarios are retained as
structural evidence and are not rerun.

The confirmation retains the 45-second C7.4b wall-resource contract and the
frozen internal algorithmic budgets. In particular G016-R0 and G016-R1 are
executed again under both fresh seeds rather than pre-classified as timeout
cells; whether they remain common-mode coverage gaps is an empirical C7.4c
result.

Because existing C7 candidate and improver identities include effective seed
provenance, C7.4c first generates a normal fresh-seed full plan, matches frozen
C7.4b survivors to those fresh candidates by semantic objective/constructor/
improver configuration, and records an explicit one-to-one source-candidate
mapping. Fresh execution evidence is relabelled to the frozen C7.4b source IDs
only after durable C6/C7 evidence validation.

The primary confirmation decision uses only fresh seeds 1702 and 1703, the
same paired C1 strict-Pareto policy and the same no-hidden-scalar rule used by
C7.4b. Candidate-specific timeout/failure gates remain active; a scenario/seed
cell on which every candidate reaches the wall fuse is recorded as a
common-mode coverage gap and cannot distinguish candidates. Mixed-success
cells remain candidate-discriminating evidence.

After fresh confirmation, C7.4c also constructs a complete pooled development
matrix over seeds 1701, 1702 and 1703 for later C7.5 analysis. The fresh-only
confirmation result and pooled result are reported separately so historical
selection evidence is never misrepresented as independent confirmation.

## C7.5 development shortlist

C7.5 consumes only the frozen development evidence produced through C7.4c.
It performs no scheduler execution and does not access the reserved holdout.

The source field is the complete C7.4c-confirmed Pareto set. Historical seed
1701 and independent confirmation seeds 1702 and 1703 are pooled only after
their provenance and candidate identities have been validated. The known
G016 common-mode wall-fuse cells remain coverage gaps rather than
candidate-discriminating evidence.

Because the confirmed field is itself a strict Pareto frontier, C7.5 does not
attempt to force it to an arbitrary target size with another weighted score,
normalization, epsilon, lexicographic rule, runtime tie-break or hidden
ranking.

Instead C7.5 uses an explicit metric-witness rule. For each active frozen C1
selection metric, it reproduces the exact paired metric coverage used by the
selector, computes the unweighted pooled mean for every confirmed candidate,
and records every candidate tied for the exact best value on that metric. The
development shortlist is the union of those metric witnesses.

This shortlist should be interpreted as a compact set of empirically observed
C1 specialists, not as an overall ranking of the confirmed Pareto frontier.
Candidates not in the metric-witness shortlist remain legitimate nondominated
development compromises; they are omitted only because C7.5 requires a small,
interpretable set for the subsequent contestant-freeze decision.

C7.5 itself does not consume holdout evidence and does not declare a production
winner.

## C7.6 freeze C8 contestants

C7.6 performs no further development selection. The six candidates produced by
the frozen C7.5 metric-witness shortlist become the complete C8 contestant
field.

The freeze artifact records each contestant's frozen C7 source candidate ID,
human-readable label, C7.5 witness metrics, objective identity, constructor and
improver arm identities, normalized objective/constructor/improver
configuration, and a semantic configuration fingerprint.

The semantic fingerprint is configuration based rather than a replacement for
the frozen source candidate ID. This distinction matters because later C8
execution may use fresh run seeds while seeded improvers receive those run
seeds through the normal C6 execution contract.

C7.6 also freezes the identity of the 24 reserved holdout scenarios, but does
not execute, evaluate, inspect results from, or otherwise consume those
scenarios. C8 is the first stage permitted to execute the holdout.

C7.6 introduces no scalar ranking, epsilon rule, runtime tie-break, or new
development evidence. Its purpose is provenance: once the contestant artifact
is frozen, C8 must evaluate exactly this field unless a new explicitly versioned
campaign is created.

## C8 untouched holdout face-off

C8 is the first stage permitted to execute the 24 reserved Benchmark V1
holdout scenarios. The contestant field is immutable at entry: exactly the
six configurations frozen by C7.6 are evaluated.

The C8 protocol is frozen before holdout execution:

- holdout scenarios: all 24 frozen C7.6 holdout scenarios;
- contestants: exactly the six frozen C7.6 configurations;
- fresh run seeds: 1801, 1802 and 1803;
- resource contract: 45-second per-trial wall fuse;
- total planned cells: 6 × 24 × 3 = 432;
- comparison: independent C1 performance under the frozen paired strict
  Pareto policy;
- no weighted scalar score, normalization, epsilon, runtime tie-break or
  declared overall winner.

The C8 seeds are disjoint from C7 tuning and confirmation seeds. Seed-sensitive
improver identities are regenerated using the normal C7/C6 identity machinery
and matched back to frozen C7.6 contestants by their semantic configuration
fingerprints.

All-candidate structural constructor outcomes are recorded as structurally
unscorable holdout cells. Exact all-candidate wall-timeout cells are recorded
as common-mode runtime coverage gaps and cannot distinguish contestants.
Candidate-specific timeout/failure remains discriminatory resource evidence
under the frozen zero-timeout/zero-failure gates.

A no-success holdout cell that is neither wholly structural nor exact
all-candidate wall-timeout is unresolved. C8 does not respond by tuning the
budget, changing seeds, replacing contestants or otherwise adapting the
protocol after inspecting holdout outcomes. Such a result makes the face-off
inconclusive under this preregistered protocol and requires an explicitly new
versioned study rather than an in-place adjustment.

C8 reports the eligible field, exclusions, active paired metrics and strict
Pareto frontier. It does not declare an overall winner. Later workload-aware
analysis must preserve the fact that C8 is final holdout evidence rather than
new tuning data.

## C9.1 workload-response analysis

C9 begins with a development-only workload-response study. It does not train
from, inspect, or otherwise consume C8 holdout results.

The source field is exactly the six contestants frozen by C7.6. Their pooled
C7 development evidence over seeds 1701, 1702 and 1703 is reconstructed from
the frozen C7 artifacts.

For each proven-feasible development scenario, C9.1 averages each active C1
metric across the three development seeds and computes a scenario-local strict
Pareto frontier over the six finalists. Exact all-candidate wall-timeout
scenarios remain common-mode runtime coverage gaps and are not assigned a
quality frontier.

C9.1 records:

- local Pareto membership by workload;
- exact per-metric leaders by workload;
- pairwise dominance counts;
- Pareto coverage frequency for each finalist;
- R0/R1 replicate consistency;
- descriptive associations between canonical workload features and candidate
  Pareto membership.

Feature associations are descriptive only. They are not a candidate score,
classifier, or selector. C9.1 therefore does not yet freeze workload-routing
logic.

No scalar candidate score is introduced. C8 remains final untouched holdout
evidence rather than training data.

## C9.2 frozen workload policy

C9.2 converts the frozen C9.1 development-only workload-response study into
an explicit workload policy for C10.

C9.2 does not train a classifier or automatic routing model. The observed
local Pareto frontiers overlap too strongly for a hard workload-to-algorithm
mapping to be defensible: aggressive+LNS60 and stable+none are Pareto on all
51 scorable development workloads, all six finalists have at least 46/51
local Pareto coverage, and paired R0/R1 replicate consistency is high.

The frozen policy therefore carries all six C7.6 finalists into C10 and assigns
interpretable roles:

- robust core:
  - aggressive+LNS60
  - stable+none
- specialists:
  - pressure+LNS60
  - aggressive+ALNS80
  - stable+ALNS80
- baseline/fallback:
  - aggressive+none

These roles do not form a ranking. The robust-core label indicates universal
development Pareto coverage, not overall superiority. Specialists remain
legitimate nondominated alternatives with useful metric tradeoffs.
aggressive+none remains a low-complexity comparator and fallback.

C8 holdout evidence is not used to train or define the C9.2 policy. C8 remains
final validation evidence. C10 real-ARC/human-friendliness validation may
compare the six frozen candidates and their usability, but must not
retroactively rewrite C9.2 from holdout outcomes.

## C10.1 realistic ARC human-review fixture

C10 begins with a deterministic synthetic semester workload expressed through
canonical ARC state rather than a hand-built laboratory-only ScheduleProblem.

The fixture is materialized through:

`WorkloadBlueprint -> materialize_blueprint() -> problem_from_user()`

so C10 exercises the same canonical PlanningItem, hierarchy, dependency,
progress, priority, temporal and anchor semantics used by the production
adapter.

The fixture contains four human-interpretable workload groups:

- SOFT2412;
- ELEC3609 / ARC;
- mathematics;
- personal/admin work.

It mixes short atomic work, long splittable work, dependencies, priorities,
release dates, deadlines, explicit requested dates and partial progress.

The C10 fixture is synthetic and contains no personal user data.

C10 human review is observational only. Human or LLM judgements must not be
fed into the search objective, used to retune C7 candidates, or used to train
the C9 router. The six C7.6 contestants remain frozen.

C10.1 is plan-only: it validates the fixture, production adapter and exact
candidate field before any scheduler trial is executed.

## C10.2 six-finalist external human review

C10.2 executes exactly one frozen trial for each C7.6 finalist on the frozen
C10.1 realistic ARC fixture.

The trial seed is 1901 and each trial retains the 45-second isolated fuse
preregistered by C10.1. There is no adaptive rerun, parameter change, candidate
elimination or post-hoc budget increase.

Each successful trial exports:

- the final independent C1 performance vector;
- the exact proposed allocations;
- a date-grouped human-readable calendar;
- a neutral qualitative review checklist.

The qualitative review is observational only. No scalar human-friendliness
score is created, no C1 metric is replaced, and human observations must not be
used to retune C7/C8/C9 or train an automatic workload router.

C10.2 exists to detect schedule characteristics that may be legal and
quantitatively competitive but undesirable to a real user, including awkward
fragmentation, bunching, idle stretches, unnatural dependency pacing or
otherwise difficult-to-follow calendar shapes.

## C10.3 external human-friendliness diagnostics

C10.3 adds descriptive diagnostics over the already-frozen C10.2 calendars.

These diagnostics are not part of the optimization objective and do not cause
candidate reruns, retuning, ranking or elimination.

The diagnostics record observable calendar-shape characteristics including:

- first-day session count;
- maximum sessions on one day;
- busy-day counts;
- concentration in the first three active days and first calendar week;
- repeated sessions of the same item on the same day;
- daily session-distribution entropy;
- cross-group mixing.

C10.3 also detects whether multiple candidates produce the same calendar when
execution order is ignored.

Any later decision to expose these concerns as production preferences or
scheduler flavours belongs to C11 or production design, not retroactive C7-C9
tuning.

## C11.1 production flavour contracts

C11 exposes exactly two initial production scheduler flavours: Lock-in and
Monk.

Both flavours remain subordinate to the same canonical ARC and scheduling
invariants. Neither flavour changes legality, dependency semantics, anchors,
release dates, session-piece conservation, or canonical state authority.

Both flavours also share a task-continuity principle: once a splittable task
has started, the scheduler should prefer to complete it over the shortest
practical elapsed span. Calendar balance is not permission to scatter one task
through its full deadline window.

Lock-in prefers early useful work, rapid completion, fast dependency progress
and avoidance of unnecessary idle days. Higher daily load is acceptable than
under Monk, but overload remains strongly discouraged.

Monk prefers lower peak load, fewer overloaded/heavy days and a smoother use
of otherwise available calendar days. It still maintains task continuity and
does not delay started work merely for aesthetic balance.

C11.1 freezes semantics only. Numerical objective terms and weights are not
yet selected and no scheduler trial is executed.

## C11.2 production objective primitives

C11.2 introduces four optional whole-plan objective primitives required to
express the frozen Lock-in and Monk contracts:

- continuity gap cost: penalises idle calendar days between consecutive
  sessions of the same item;
- avoidable-idle cost: penalises empty days before final work when a later
  unanchored session could already have been scheduled under the frozen
  release/dependency/session-order semantics;
- same-item same-day repeat cost: penalises extra sessions of one item on one
  calendar day, distinguishing rapid completion from cramming;
- daily session concentration cost: penalises total sessions above an explicit
  soft comfort threshold and remains separate from C2 bucket capacity
  overload.

All four terms default to zero in PlanObjectiveConfig. Therefore every
pre-C11 objective configuration preserves its exact prior numerical semantics.

C11.2 does not choose production weights, comfort thresholds, constructors,
improvers or budgets. No scheduler trial is executed and no frozen C7-C10
evidence is retuned.

## C11.3 behavioural acceptance search

C11.3 tests whether the C11.2 objective vocabulary can express the frozen
Lock-in and Monk contracts.

The acceptance cases are deliberately synthetic and contract-shaped. They are
not benchmark scenarios and are not derived from C7-C10 performance evidence.

Both flavours must:

- prefer compact continuation of a started multi-session item over scattering
  its sessions through a long legal window;
- prefer adjacent-day continuation over placing all sessions of a large item
  on one day when both choices are otherwise legal.

Lock-in must additionally:

- prefer filling an avoidable idle day;
- prefer earlier useful progress in an explicit early-vs-smooth tradeoff.

Monk must additionally:

- prefer a smoother daily session distribution over a large spike;
- prefer the smoother option in the same early-vs-smooth tradeoff.

C11.3 searches a small deterministic parameter grid only to establish that
each behavioural contract has a non-empty feasible parameter region. It does
not select final production weights.

No scheduler trial is executed. No C7-C10 benchmark or holdout evidence is
used or retuned.

## C11.4 dynamic production work-mass mechanics

Inspection before C11.4 established an important distinction.

The fixed equal-sized `session_pieces()` representation is a frozen research
search representation used by C1-C10. It is not a canonical ARC requirement
for splittable work.

The independent ARC plan validator requires that allocations conserve exact
remaining percentage and that atomic duration classes are not split. It does
not require splittable work to use equal percentage pieces. The backend
scheduler allocation contract likewise defines allocation proposals as
disposable scheduler policy.

C11 production scheduling therefore introduces a separate work-mass model
rather than changing the frozen C1-C10 search state.

For production scheduling:

1. a task has an estimated total work mass in hours;
2. current canonical progress determines remaining work mass;
3. flavour policy determines how much reasonable headroom a candidate day can
   contribute to that task;
4. assigned hours are converted into percentage of total task work;
5. the final allocation absorbs decimal rounding so remaining percentage is
   conserved exactly;
6. the resulting SchedulePlan is checked by the existing independent ARC
   validator.

Therefore allocation percentages are outputs of scheduling decisions rather
than fixed inputs.

For example, a task estimated at 16 hours with daily contributions of 4.8h,
4.0h and 7.2h naturally yields allocations of 30%, 25% and 45%.

C11.4 does not yet define how Lock-in or Monk calculate daily headroom, does
not choose duration-category work estimates, and does not change C1-C10
research mechanics or evidence.

## C11.5 first adaptive flavour schedules

C11.5 is the first human-reviewable execution of the dynamic C11 production
planner.

It generates exactly two schedules on the frozen C10 realistic fixture:

- Lock-in;
- Monk.

The production planner reasons in estimated work hours. Allocation percentages
are derived after daily work amounts are selected.

C10 does not contain explicit per-task hour estimates, so C11.5 uses transparent
duration-category work-estimate priors as a fallback. These priors are estimate
inputs, not fixed session percentages. Future ARC production data may override
them with explicit or learned task-specific estimates.

Both flavours share canonical releases, anchors, dependencies, exact work
conservation and independent validation.

Lock-in uses more ordinary daily headroom and attempts to finish available work
earlier.

Monk uses a lower ordinary daily target to reduce peaks while maintaining the
same started-task continuity rule.

C11.5 is intentionally a human-review milestone. The flavour policies are not
yet frozen. The generated calendars must be inspected for real-world
reasonability before further parameter selection.

## C11.6 first human-reasonability refinement

Human review of the first C11.5 Lock-in and Monk calendars exposed two general
planner-mechanics defects rather than flavour-definition problems.

First, anchored work was not guaranteed to consume the day's load before
flexible work was selected. This allowed flexible sessions to fill a day and a
later anchor to push the final daily total well beyond the flavour's intended
ordinary load.

C11.6 therefore gives unstarted items anchored to the current day scheduling
precedence before flexible work. This allows later flexible decisions to
observe the real remaining daily headroom.

Second, dynamic session sizing could produce very small clean-up tails such as
0.4 hours. C11.6 absorbs a sub-minimum final remainder into the current session
when doing so remains within that flavour's soft maximum daily headroom.

Neither rule encodes task-specific percentages or a fixed session count. Both
operate from the actual remaining task work and actual daily load.

C11.6 remains a provisional human-review refinement. Production flavour
parameters are not frozen.

## C11.7 adaptive session-shape control

C11.6 human review showed that valid daily totals alone are insufficient for

human reasonability.

Lock-in could devote seven or eight hours of one day to a single task, while

Monk could repeatedly make only one hour of progress on a substantial started

task.

C11.7 therefore adds two general work-mass controls:

- a flavour-specific maximum ordinary focused-session duration;

- a continuation target share that encourages meaningful progress on work

  already started when daily headroom permits.

These are hour-based human workload controls rather than task-specific

percentage rules. Percentage allocations remain derived from task work mass.

Deadline pressure may still produce different allocations because work mass,

remaining time, anchors, dependencies and available day headroom continue to

participate in the decision.


## C11.8 multi-fixture production validation

After C11.7 produced human-plausible Lock-in and Monk calendars on the frozen
C10 realistic workload, C11.8 expands validation across several deterministic
structural scenarios.

The scenarios are deliberately not tuning workloads. They test:

- parallel immediately executable work;
- fixed-anchor pressure;
- dependency chains;
- compressed deadlines;
- staggered releases;
- partial completion;
- a single very large task.

Both production flavours are generated for every scenario.

The validation records hard legality, daily peaks, active-day means, largest
single session, continuity gaps, small non-final fragments and relative
Lock-in/Monk completion behaviour.

C11.8 does not retune C7-C10, does not run the research scheduler, and does not
freeze production parameters.

## C11.9 adaptive interruption and resume

Freeze inspection identified that production task continuity was ordered ahead
of ordinary deadline pressure.

Continuity is a strong human preference, but it must remain soft. A large task
already in progress should yield when newly available work becomes sufficiently
deadline-constrained or when anchored tasks consume the day's usable workload.

C11.9 therefore introduces a deadline-feasibility pressure tier derived from:

- remaining estimated task work;
- remaining calendar days before due date;
- flavour-specific maximum reasonable focused-session size.

Deadline-feasibility pressure is evaluated before continuity preference.
Continuity remains strong between tasks in the same pressure class.

C11.9 explicitly validates interruption/resume behaviour:

- a large task progresses;
- a later day can contain zero work on that task because task constraints
  consume the day's usable workload;
- the large task resumes afterward;
- urgent newly released work can interrupt a relaxed started task;
- relaxed newly released work does not unnecessarily break continuity.

These are task-manager scenarios only. Calendar/event integration is outside
the current C11 scope.

## C11.10 unavoidable overload and workload statuses

Production flavour workload targets are not hard scheduling ceilings.

When release/deadline/anchor constraints make overload unavoidable, the
production planner must schedule the required work rather than silently create
avoidable lateness merely to preserve a flavour's comfortable daily load.

Generated workload is classified separately from scheduling legality.

Daily statuses:

- empty;
- chill;
- normal;
- locked-in;
- overloaded;
- infeasible.

The initial status model uses each flavour's preferred and soft-max workload
bands. Work beyond the soft maximum is overloaded. More than 24 estimated work
hours assigned to one calendar day is classified infeasible.

The same classification model is aggregated for ISO weeks and calendar months.

These statuses are diagnostics. They do not weaken canonical scheduling
invariants and are not hard caps on the planner.

## C11.12 dynamic production improvement

C11.11 showed that a locally reasonable greedy production constructor is not
sufficient by itself. This does not invalidate C4-C9 research.

C11.12 ports the proven search architecture to C11's dynamic work-mass
representation.

The production pipeline is now conceptually:

canonical ScheduleProblem
-> adaptive production constructor
-> dynamic production improver
-> independent validator
-> workload/risk diagnostics
-> disposable backend projection

The production improver deliberately reuses research principles:

- constructor and improver remain independent;
- deterministic neighbourhood order;
- strict improvement only;
- BEST-improvement neighbourhood scans;
- explicit iteration/evaluation budgets;
- independent legality validation for every candidate;
- objective evaluation separate from canonical state.

The old SearchState and session-index moves are not reused because they encode
the frozen C1-C10 equal-piece representation. Production moves instead relocate
estimated work-hours and regenerate canonical percentages from work mass.

The initial production objective is lexicographic:

1. late allocated work;
2. physically infeasible day count/excess;
3. overloaded day count/excess;
4. tiny non-final fragments;
5. task continuity gaps;
6. maximum daily workload;
7. workload above preferred daily intensity;
8. aggregate completion timing.

This ordering deliberately allows unavoidable overload to beat deadline
lateness while still repairing avoidable overload whenever legal earlier work
opportunities exist.

C11.12 also propagates downstream deadline/anchor urgency backward through the
dependency DAG. Effective planner deadlines are advisory only and never mutate
canonical ARC due dates.

### C11.12d deadline-buffer risk

Human review after C11.12c found a remaining pathology: a schedule could be
perfectly legal yet postpone a deadline-sensitive dependency chain until the
last possible day while unrelated relaxed work consumed earlier capacity.

Production search therefore distinguishes:

- actual lateness;
- zero/very-low deadline buffer;
- healthy deadline buffer.

Deadline-buffer risk uses planner-only effective deadlines, including deadlines
propagated backward through dependencies.

The initial short-buffer penalty is:

- zero days: 9;
- one day: 4;
- two days: 1;
- three or more days: 0.

This is an explicit production-search primitive, not a canonical invariant and
not a task-specific rule. Actual lateness remains lexicographically dominant.

### C11.12d negative effective-buffer correction

A reachability probe demonstrated that a legal buffered dependency schedule
was scored worse than a last-moment dependency schedule.

The cause was a scoring defect: when a task completed after its planner-only
effective deadline, deadline-buffer scoring skipped the task entirely. This
made a negative effective buffer incorrectly cheaper than zero buffer.

The deadline-buffer curve now extends continuously through negative values:

- +3 days or more: 0
- +2 days: 1
- +1 day: 4
- 0 days: 9
- -1 day: 16
- -2 days: 25
- and so on quadratically.

Negative effective buffer remains a production risk diagnostic, not canonical
lateness. Actual task due-date lateness continues to dominate through the
separate late-hours objective component.

### C11.12d human review clarification: buffer is not a hard requirement

A reachability probe compared the production search result with a manually
constructed one-day-buffer candidate.

The manual candidate was hard-legal, but was correctly scored worse:

- for Monk it purchased deadline buffer by creating an overloaded 10-hour day;
- for Lock-in it purchased deadline buffer while manufacturing an avoidable
  empty day.

The previous regression requiring the dependent to finish at least one day
before its deadline therefore over-specified a soft human preference as though
it were a hard scheduling requirement.

The regression now tests the intended production semantics:

- prerequisite work precedes dependent work;
- the downstream real deadline is met;
- relaxed unrelated work does not consume the critical chain's early capacity;
- avoidable overload/infeasibility is not introduced merely to create buffer;
- deadline buffer remains a soft objective below more important workload
  severity terms.

## C11.13 — integrated adversarial human world

C11.12 completed the first dynamic production-improver foundation and received
a provisional human pass.

C11.13 moves from isolated fixtures to a shared realistic world. The purpose
is to evaluate how heterogeneous scheduling pressures interact when all tasks
compete for the same calendar.

The first integrated world contains 22 tasks covering:

- a three-stage dependency chain;
- a second independent dependency chain;
- large interruptible work;
- partial progress;
- future releases;
- atomic anchored work;
- tiny real-world admin/household work;
- relaxed background work;
- urgent low-priority work;
- high-priority relaxed work;
- multiple explicit hour estimates.

This stage deliberately does not freeze scheduler quality from automated tests
alone. Lock-in and Monk calendars are printed in full for human inspection.

Additional adversarial tasks will be layered into this world after the first
human review so that each new scenario is evaluated in relation to the
existing workload rather than in isolation.

## C11.14 — human session shape and priority persistence

Integrated C11.13 human review found that legality and urgency handling were
strong, but large splittable tasks were excessively fragmented. Examples
included a 24-hour assignment spread over 11–13 dates and repeated one-hour
revision nibbles.

The previous production objective only distinguished sessions below one hour
from all larger sessions. Its continuity-gap term could therefore reward
touching the same task every day with token work.

C11.14 adds three explicit production-search primitives:

1. **session-shape penalty**
   - sub-hour flexible fragments are strongly undesirable;
   - roughly 1–2h is acceptable but not ideal;
   - 2–4h is the preferred human focus range;
   - 4–6h remains legal but becomes progressively less attractive;
   - very long single-task sessions become increasingly undesirable;
   - atomic/admin tasks are exempt;
   - a genuinely small final remainder is permitted.

2. **fragmentation count**
   - once higher-order safety and workload terms are equal, fewer separate
     touches of the same splittable task are preferred.

3. **priority postponement**
   - explicit user priority now survives constructor -> improver;
   - higher-priority executable work pays a larger penalty for avoidable
     postponement;
   - releases, dependencies, anchors, deadlines, infeasibility and serious
     workload severity still outrank priority.

The crude continuity-gap metric remains diagnostic but is deliberately below
session quality and fragmentation. Meaningful blocks separated by a gap may be
better than repeated token continuity.

These are search preferences only. Canonical state and hard legality are
unchanged.

### C11.14b consolidation-first and balanced exchange

A post-C11.14 probe showed that the production optimiser terminated at its
evaluation budget while leaving strict human-quality improvements unclaimed.

Examples included:

- removable sub-hour fragments in the partially completed report;
- a pointless isolated one-hour revision session;
- no direct legal whole-fragment consolidation for the heavily fragmented
  24-hour assignment without changing protected daily-load metrics.

The issue was therefore partly neighbourhood ordering/reachability rather than
only objective semantics.

C11.14b introduces two targeted neighbourhoods ahead of the broad relocation
scan:

1. **whole-fragment consolidation**
   - moves an entire splittable allocation into another existing allocation of
     the same task;
   - directly targets unnecessary task touches and tiny fragments.

2. **balanced exchange**
   - consolidates one task while moving an equal amount of another splittable
     task back to the vacated date;
   - preserves both affected daily workload totals exactly;
   - allows fragmentation improvement without first worsening peak/day-load
     objectives.

Atomic/admin work is excluded from exchange material.

These neighbourhoods remain deterministic, strict-improvement only, bounded,
and independently validated. Canonical state and hard legality are unchanged.

### C11.14c targeted human block repacking

C11.14b materially reduced fragmentation through direct consolidation and
load-preserving two-task exchange, but the integrated Monk calendar still
contained avoidable sub-hour fragments and both flavours continued to exhaust
the generic evaluation budget.

C11.14c therefore adds a bounded block-repacking neighbourhood before the
general relocation scan.

For fragmented splittable work, the operator considers several lower-touch
representations whose average session size falls in the broad 1.5–4h human
focus region. It does not prescribe a fixed session duration.

For example, a 12-hour task may propose:

- 3 x 4h;
- 4 x 3h;
- 5 x 2.4h.

A 24-hour task may propose:

- 6 x 4h;
- 7 x approximately 3.43h;
- 8 x 3h.

Candidate days are selected using the existing flavour policy and current
non-task workload. Monk strongly prefers under-preferred-load dates; Lock-in
preserves its earlier-work bias while avoiding unnecessary soft-max breaches.

Every candidate still passes the independent dynamic-plan validator and the
normal lexicographic production objective. Therefore block repacking cannot
override deadlines, dependency legality, anchors, serious workload severity,
or higher-ranked production semantics merely to make prettier sessions.

Atomic/admin work is excluded completely.

### C11.14d human-shape dominance

C11.14c successfully repaired the integrated Monk report schedule but exposed
two new shape defects:

- Lock-in could create a roughly five-minute non-final major-assignment
  allocation merely to improve higher-ranked load-shaping terms.
- Monk could retain a 7.2-hour single-task revision block because the block
  repacker only considered lower-touch representations.

C11.14d establishes two explicit production semantics.

#### Non-final token-session dominance

For splittable focused work, a non-final allocation below the minimum useful
session threshold is now ranked immediately after actual lateness and physical
infeasibility.

Therefore ordinary peak reduction, overload smoothing, idle reduction,
priority preference, fragmentation, or continuity cannot manufacture a token
focused-work session.

This is not a hard legality invariant. If a tiny fragment is genuinely
required to improve actual deadline lateness or physical infeasibility, those
higher-order terms still dominate.

Atomic/admin work remains exempt.

#### Oversized-session repacking

Block repacking may now consider:

- fewer touches;
- the same number of touches with better distribution;
- up to a small number of extra touches when the current schedule contains an
  oversized >6h focused session or a non-final sub-hour token fragment.

This allows a schedule such as:

    3.6 + 3.6 + 3.6 + 7.2

to consider a humane five-block representation without making five blocks a
fixed rule.

The independent validator and existing higher-order production objective remain
authoritative.

### C11.14e multi-task load-preserving window repack

C11.14d eliminated non-final token sessions and allowed oversized sessions to
be reconsidered. Human review accepted Lock-in's long revision blocks when
they purchase genuine deadline buffer, but the integrated 24-hour major
assignment still contained an approximately 8.37-hour block.

A direct repack of that task produced materially higher daily peaks and
overload. The remaining problem was therefore not the single-task shape
objective but the inability to rearrange neighbouring flexible tasks together.

C11.14e introduces a bounded multi-task load-preserving repack.

For a poor focused-work allocation, the operator may move part or all of that
work to another nearby legal active date and move an equal amount of one or
more other splittable tasks back to the source date.

Both affected daily totals are preserved exactly.

This allows human block quality to improve without first worsening:

- daily peak;
- overload count;
- overload excess.

The candidate still passes the full independent dynamic-plan validator and the
ordinary production objective. Therefore deadline buffer, priority,
dependencies, releases, and all other production semantics remain visible.

Atomic/admin tasks and anchored allocations are never used as donor material.

Lock-in's previously accepted long revision blocks remain permissible where
their earlier completion buys meaningful deadline buffer; this neighbourhood
does not introduce a blanket six-hour ceiling.

### C11.14f donor-shape safety

C11.14e successfully repaired the integrated Lock-in major assignment through
multi-task load-preserving repacking. The final Lock-in assignment became eight
three-hour blocks without introducing tiny fragments.

Human review exposed one collateral defect in Monk: the same neighbourhood
could preserve total daily workload while concentrating counterbalancing donor
work into an eight-hour report session.

The neighbourhood already bounded the focus task's resulting block, but did not
bound newly-created donor concentration.

C11.14f therefore caps each donor transfer by the flavour's ordinary remaining
focused-session room on the destination date.

This is a neighbourhood safety rule, not a global session ceiling:

- existing long sessions remain legal;
- Lock-in may still deliberately accept long focused work when deadline buffer
  or other higher-order semantics justify it;
- this repair operator simply may not improve one task by manufacturing a new
  oversized donor block in another.

Atomic and anchored donor exclusions remain unchanged.

## C11.15 — static saturated decision coverage

C11.14 froze the dynamic human-session-shape foundation after independent
inspection and full regression validation.

C11.15 deliberately separates two validation concepts:

1. **static saturated decision coverage**, performed now;
2. **progressive grow -> maximum complexity -> shrink lifecycle validation**,
   reserved for final certification.

The static stage starts from the existing integrated C11.13 world and extends
it into one shared calendar containing explicit conflicts for:

- urgency vs relaxed explicit priority;
- pure priority sensitivity under comparable constraints;
- multi-hop dependencies;
- diamond dependencies;
- one prerequisite unlocking multiple dependents;
- a two-day future anchor wall;
- urgent releases into known congestion;
- started work vs newly urgent work;
- partial-progress conservation;
- no-deadline flexible backlog;
- equal-deadline priority competition;
- deliberately impossible >24h due-today workload;
- future-congestion lookahead;
- session-shape quality under saturation;
- release collisions;
- atomic work around focused work;
- deadline-buffer vs long Lock-in sessions;
- Lock-in vs Monk behavioural distinction.

Decision cases are explicitly catalogued.

Automated audits only mark objective structural principles PASS/FAIL.
Subjective trade-offs are printed as OBSERVE and remain subject to human review.

The later lifecycle certification will reuse this decision vocabulary while
adding and then removing pressure incrementally, allowing schedule deltas and
adaptation quality to be inspected at every world state.

## C11.15.2 — deadline-recovery fast path

The C11.15 saturated static world exposed a production-search scalability
problem rather than an unattainable schedule-quality problem.

For Monk:

- the constructor began with 107 late work-hours;
- the normal 12,000-evaluation search reduced this to 12 late hours but
  exhausted its evaluation budget;
- a single 30,000-evaluation run reached zero lateness while also correctly
  isolating the unavoidable 25-hour due-today workload on its infeasible day.

Only 24 additional accepted improvements separated the 12k and 30k outcomes,
indicating that candidate discovery/order was the bottleneck.

Inspection showed that the improver still ran human-shape and broad relocation
neighbourhoods while actual due-date lateness remained present, despite
lateness being the first lexicographic objective.

C11.15.2 adds a deterministic bounded deadline-recovery fast path.

While actual lateness exists it searches first over:

- allocations that are themselves after a canonical due date;
- prerequisite ancestors of those late tasks;
- earlier legal dates;
- propagated planner-only effective deadlines for prerequisite recovery.

Every candidate remains independently validated and strict-improvement only.
If the focused recovery set cannot improve the plan, the existing complete
production neighbourhood stack remains available.

No canonical due dates, dependency semantics, flavour contracts, or human
session-shape objectives are changed.

## C11.15.3 — saturated-world test-budget alignment

Post-C11.15.2 regression exposed a test-harness mismatch rather than a new
scheduler defect.

The C11.15 saturated-world tests still used the historical helper defaults:

- 25 iterations;
- 3,000 evaluations.

C11.15.2 established the current saturated-world acceptance configuration as:

- 120 iterations;
- 12,000 evaluations.

At 3,000 evaluations the deterministic search can still be in an unfinished
state and may retain priority inversions that are repaired within the accepted
12,000-evaluation production run.

The behavioural priority assertions remain unchanged.

The shared test helper now evaluates the accepted 12k configuration and caches
the deterministic result by flavour/configuration so multiple assertions do
not repeatedly rerun the same expensive optimisation.

This changes test infrastructure only. Production scheduling semantics and
search behaviour are unchanged.

## C11.15.5 — anchored-congestion recovery fast path

C11.15.4 neighbourhood forensics separated search-ordering defects from
objective-semantic defects.

In the saturated Monk schedule, the two known anchor-wall dates contained:

- 2026-10-20: 10 anchored hours + 14 movable hours = 24 hours;
- 2026-10-21: 10 anchored hours + 8.9167 movable hours = 18.9167 hours.

The ordinary relocation neighbourhood already contained 49 legal moves away
from these dates, 11 of which strictly improved the existing production
objective. The 12,000-evaluation search nevertheless terminated before
applying them.

Lock-in, under the same world, had already reduced both anchor-wall dates to
the unavoidable 10 anchored hours only.

This established a search-ordering problem rather than an objective-ordering
problem.

C11.15.5 therefore adds an anchored-congestion recovery fast path after actual
lateness recovery and before human-shape/general search.

When a date:

- contains anchored work;
- also contains movable work; and
- exceeds the flavour soft daily maximum,

legal relocations of movable work away from that anchored date are examined
first.

Candidate acceptance still uses the unchanged production objective and
independent schedule validation. No hard daily ceiling is introduced.

The long-session issue remains intentionally unresolved pending re-evaluation
after anchor congestion has been repaired, because existing humane repacks were
currently rejected by higher-ranked overloaded-day counts.

## C11.15.6 — first-improvement anchored-congestion recovery

C11.15.5 proved the anchored-congestion recovery neighbourhood was semantically
correct but still too evaluation-expensive.

In the saturated world:

- Lock-in reached the desired 10h / 10h anchor-only wall;
- Monk improved from 24h / 18.9167h to 19.6429h / 13h;
- Monk still terminated at the 12,000-evaluation budget with movable work
  remaining on both anchor days.

The recovery candidate set is already deterministically ranked by:

1. most congested anchored source date;
2. calmer destination;
3. priority;
4. deterministic item/date/hour tie-breaks.

C11.15.6 therefore changes only this specialised recovery pass from exhaustive
best-improvement scanning to first strict improvement.

Every accepted candidate still:

- passes independent rebuild validation;
- must strictly improve the unchanged production objective;
- preserves canonical legality;
- introduces no hard daily ceiling.

The general improver and other neighbourhoods remain unchanged.

## C11.15.8 — justified vs unjustified focused marathons

C11.15.7 isolated a semantic defect in the production objective.

In the saturated world, humane repacks existed for several tasks but were
rejected because small deadline-buffer improvements lexicographically outranked
large human-session-shape improvements.

Examples included:

- Monk major assignment: a 9.75h focused block with only short deadline buffer;
- Monk started high-priority work: a single 8h block where approximately
  4h + 4h alternatives existed;
- Lock-in large revision: 9h + 9h finishing on the effective due date.

The previous design decision remained valid: long Lock-in sessions are not
globally forbidden when they genuinely purchase meaningful deadline buffer.

Therefore C11.15.8 does **not** promote the entire session-shape objective above
deadline-buffer risk.

Instead it introduces a narrow severe defect:

`unjustified_marathon_excess_hours`

For splittable focused work:

- the severe threshold is one hour beyond the flavour's ordinary focused
  session cap;
- Lock-in severe threshold: >7h;
- Monk severe threshold: >6h;
- sessions above that threshold are penalised lexicographically before ordinary
  deadline-buffer risk only when the task has less than two days of effective
  deadline buffer;
- at least two days of effective buffer exempts the long session from this
  severe metric;
- ordinary session-shape preferences remain lower in the objective;
- atomic tasks are excluded;
- planner-only effective deadlines are used so dependency urgency is preserved.

This keeps long Lock-in sessions legal and potentially desirable when they
actually buy early completion, while preventing deadline-buffer preference from
justifying 8–10h marathons that finish at or near the effective deadline.

## C11.15.9 — repairable-marathon semantics

C11.15.8 forensics showed that the new severe-marathon metric correctly
identified several genuine human-shape defects, but also counted the deliberate
25-hour due-today task.

That task has only one legal scheduling date: today. Moving any of its work to
another date would create actual lateness.

Therefore its same-day concentration is an infeasibility fact, not a
human-session-shape decision.

C11.15.9 refines `unjustified_marathon_excess_hours`:

A severe focused session contributes only when:

- the task is splittable;
- the task lacks meaningful effective deadline buffer;
- the session exceeds the severe flavour threshold; and
- the task has at least one alternative legal scheduling date between the
  current date/release date and its effective deadline.

Tasks with only one legal execution date remain represented through the
existing infeasible/overload semantics and do not pollute the human-shape
metric.

The same forensic run also showed that an older dependency test encoded an
obsolete exclusivity rule: it required relaxed work to begin only after an
urgent prerequisite completed.

Lock-in produced a valid schedule in which relaxed work coexisted with
prerequisite work on otherwise usable capacity while:

- prerequisite completion still preceded dependent start;
- the dependent still completed by its deadline.

The stale exclusivity assertion was therefore replaced by the actual
production invariants: completion-based precedence and deadline safety.
No scheduler behaviour was changed for this test correction.

## C11.15 residual marathon limitation

The final bounded post-search marathon-finisher experiment was rejected.

It preserved the accepted C11.15.9 behaviour but did not materially improve
the remaining genuine severe-session concentration in the saturated world.

Known residual under extreme saturation is therefore accepted as a soft
human-shape limitation:

- Lock-in genuine marathon excess remains approximately 6 hours;
- Monk genuine marathon excess remains approximately 4 hours;
- the forced 25-hour due-today workload is not counted as a repairable
  marathon defect.

This residual is not a legality, dependency, release, anchor, lateness, or
work-mass correctness defect.

Per the C11.15 cutoff, no further broad or specialised marathon neighbourhood
will be introduced before freeze.

## C11.16 grow → maximum complexity → shrink lifecycle certification

C11.15 froze the production scheduler semantics after the saturated static-world
review.

C11.16 does not introduce another optimisation rule. It is a lifecycle
certification layer around the frozen production scheduler.

The certification derives every world from the frozen C11.15 46-task master
fixture and changes only which canonical tasks/dependencies are present.

The grow sequence introduces one pressure dimension at a time:

1. simple relaxed work;
2. urgency versus relaxed priority;
3. multi-hop dependency urgency;
4. fixed-date anchors;
5. future releases;
6. partial progress;
7. competing large work;
8. a second independent dependency chain;
9. comparable priority pairs;
10. diamond/shared-prerequisite structures;
11. the two-day anchor wall plus urgent released work;
12. started work, new urgency, and no-deadline backlog;
13. tiny atomic/admin work;
14. deliberately impossible due-today pressure.

The final grow step is exactly the frozen C11.15 saturated world.

The shrink sequence then removes those pressure dimensions in reverse order
until the original simple baseline remains.

At every step both Lock-in and Monk are regenerated from canonical state and
improved from scratch. The audit records:

- independent dynamic-plan validation;
- lateness and infeasibility;
- peak and overload behaviour;
- tiny-session and marathon diagnostics;
- which canonical items were added or removed;
- which surviving items kept exactly the same schedule;
- which surviving items were rescheduled.

The final relaxed state must reproduce the same deterministic schedule as the
initial baseline state. This verifies that pressure introduced in the middle of
the lifecycle does not leave hidden scheduler state behind after that pressure
is removed.

This stage certifies behaviour only. It must not change the frozen C11.15
production objective, neighbourhoods, work-mass model, flavour contracts, or
canonical scheduling semantics.


## C11.16 search-efficiency observation

The lifecycle certification distinguishes an ugly calendar from an incorrect
scheduler decision.

Overload is intentionally soft. The scheduler may overload a day when doing so
protects higher-ranked outcomes such as actual lateness, hard feasibility,
dependency correctness, anchors, releases, or work conservation.

A separate feasibility review found that heavy saturation from the anchor-wall
stage onward genuinely requires some overload if all hard semantics and zero
lateness are preserved. The deliberately impossible 25-hour due-today task is
also correctly surfaced as an infeasible day rather than moved late.

However, two earlier lifecycle states demonstrated search headroom:

- Monk G08 produced overload even though a zero-lateness arrangement within
  Monk's soft daily target was feasible.
- Lock-in G09 produced overload even though a zero-lateness arrangement within
  Lock-in's soft daily target was feasible.

These are recorded as search-efficiency / search-reachability limitations, not
flavour-contract or objective-semantics failures.

The frozen C11.15 production semantics are therefore not reopened. Runtime,
evaluation-budget efficiency, and real-user reaction to rescheduling churn will
be measured after backend integration using realistic ARC workloads.

C11.16 also requires exact reversibility for deterministic canonical state:
if a canonical change is introduced and later completely reverted with no
other state change, rebuilding that same canonical world must reproduce the
same schedule. The full grow/shrink audit checks every mirrored lifecycle state,
not only the initial/final baseline.
