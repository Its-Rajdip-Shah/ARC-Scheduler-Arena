# C1.3 — Performance metric vector (v1)

**ARC decides WHAT IS TRUE. Algorithm decides WHAT TO DO WITH IT.
Arena decides HOW WELL IT DID.**

```python
from arena.evaluation import PerformanceVector, evaluate_plan
from arena.scheduling.validation import validate_plan

plan = algorithm.solve(problem)
validation = validate_plan(problem, plan)
performance = evaluate_plan(problem, plan, validation)
```

The frozen, slotted `PerformanceVector` contains exactly the 50 fields below, preserving the original
30 C1.2 fields in order and appending 20 C1.3 fields.
Counts and maximum day spans are integers; means and ratios are floats.
Evaluation is pure Python, reads no database, mutates no input, and never repairs
plans. Validation establishes validity and canonical infeasibility; performance
observes quality. There is no scalar overall score or algorithm ranking.
Interpret metrics jointly with validation and their eligible populations.

**Comparison eligibility:** compare quality on the same canonical workload only
for complete proposals with zero hard violations. Canonical infeasibilities
must be reported separately; do not pool infeasible cases with ordinary feasible
cases. Soft violations remain comparable observations. Use the matching shared
validator result for the exact problem/plan being evaluated.

Invalid plans can numerically improve deadline rates by omitting late work,
priority rates by omitting positioned work or prerequisite completion, waits by
starting illegally early, and makespan/continuity by omitting sessions. Their
quality values are partial diagnostics, never evidence of scheduler superiority.
Do not replace excluded observations with invented misses, dates, waits or
priority comparisons. `None` means unavailable, never zero. This eligibility
rule belongs to comparison consumers; the evaluator does not rank algorithms.

## Derived values and malformed proposals

For a known item with nonempty allocations and usable calendar dates, start is
the minimum proposed date. Completion is the maximum proposed date **only when
the allocation percentage total equals its canonical remaining fraction × 100
and its item/date/rank session keys are unique**.
This conservative rule excludes incomplete or excess work from completion-based
metrics. Starts and actual session counts remain observable. No expected split
count is inferred. Duplicate item/date/rank keys cannot establish completion,
even if their percentages add to the expected total. They still contribute to
observed starts, capacity and continuity. A rank collision between different
items does not itself duplicate either item's work; validation still marks the
plan invalid. Completion here is a proposed endpoint, never confirmed canonical
progress. Validation remains authoritative.
Unknown-item allocations never enter metrics. An item with an unusable date is
excluded from date-derived metrics; its actual row count still determines split
eligibility. Capacity uses only known rows with usable dates. Inputs otherwise
follow the typed domain contract (Allocation rows with Decimal percentages and
integer ranks), rather than arbitrary untyped objects.

Readiness is `max(today, release if present, completion[p] + 1 day for every
explicit prerequisite p)`. Missing prerequisite completion makes readiness
unavailable. Anchors do not enter readiness. Negative temporal or dependency
waits are excluded, never clamped to valid zero waits. Other validation failures
do not globally suppress computable observations.

## Fields and eligible populations

| Field | Definition |
|---|---|
| `hard_violation_count` | Length of `validation.violations`. |
| `canonical_infeasibility_count` | Length of `validation.infeasibilities`. |
| `soft_violation_count` | Length of `validation.soft_violations`. No code reinterpretation. |
| `deadline_item_count` | All canonical items with a due date, including missing/uncomputable work. |
| `deadline_miss_count` | Computable deadline items whose final completion exceeds their due date. |
| `deadline_miss_rate` | Miss count / computable deadline item count. |
| `mean_lateness_days` | Mean `max(0, completion − due)` in calendar days over computable deadline items, including on-time zeros. |
| `max_lateness_days` | Maximum of those latenesses. |
| `priority_item_count` | All canonical items with a non-None priority position. |
| `priority_comparison_count` | Number of distinct ordered high/low pairs with smaller high position, both starts computable, and high readiness ≤ low start. |
| `priority_inversion_count` | Comparable pairs with high start > low start. Same-day starts never invert, regardless of execution rank. |
| `priority_inversion_rate` | Inversions / comparisons. Unpositioned items and equal positions form no pairs. |
| `peak_capacity_ratio` | Maximum usage / capacity over observed bucket/date cells with positive defined capacity. |
| `overloaded_bucket_day_count` | Observed cells with usage > defined capacity, including allowed overload dates. |
| `excess_session_count` | Sum `max(0, usage − capacity)` over observed cells with defined capacity. |
| `unapproved_overloaded_bucket_day_count` | Overloaded cells excluding dates in `problem.overload_dates`. |
| `unapproved_excess_session_count` | Excess sessions excluding those allowed dates. |
| `mean_start_delay_days` | Mean nonnegative `start − readiness` over items with computable start and readiness. |
| `max_start_delay_days` | Maximum of those valid waits. |
| `zero_wait_rate` | Zero waits / valid computable item waits. |
| `makespan_days` | Latest completion − earliest start + 1 over items with computable completion. Inclusive calendar span. |
| `split_item_count` | Known canonical items with at least two proposed allocation rows, regardless of expected split policy. |
| `fragmented_item_count` | Split items with computable dates and a positive total consecutive-session idle gap. |
| `fragmented_item_rate` | Fragmented count / split count; None if any split item has uncomputable dates. |
| `mean_session_gap_days` | Mean gap over all computable consecutive session pairs from split items (pair-weighted, not item-weighted). |
| `max_session_gap_days` | Maximum of those gaps. |
| `dependency_edge_count` | Length of canonical explicit `problem.dependencies`, even when some edges are uncomputable. |
| `mean_dependency_wait_days` | Mean nonnegative `dependent start − prerequisite completion − 1` over computable explicit edges. |
| `max_dependency_wait_days` | Maximum of those valid edge waits. |
| `immediate_dependency_transition_rate` | Zero edge waits / valid computable edge waits. |
| `previously_scheduled_item_count` | Known items with non-None `existing_scheduled_date` and computable proposed start. |
| `moved_item_count` | Eligible items whose proposed start differs from their existing scheduled date. |
| `moved_item_rate` | Moved count / previously scheduled eligible count. |
| `total_movement_days` | Sum of absolute calendar-day movement across eligible items, including unchanged zeros. |
| `mean_movement_days` | Mean absolute movement across that same population, including zeros. |
| `max_movement_days` | Maximum absolute movement. |
| `moved_earlier_item_count` | Eligible items with proposed start before their existing scheduled date. |
| `moved_later_item_count` | Eligible items with proposed start after their existing scheduled date. |
| `unchanged_item_count` | Eligible items with proposed start equal to their existing scheduled date. |
| `deadline_slack_item_count` | Deadline items with computable completion. |
| `mean_completion_slack_days` | Mean signed `due_date − completion_date` in calendar days over that population. |
| `min_completion_slack_days` | Minimum signed completion slack. |
| `schedulable_window_item_count` | Items with computable start, readiness, and nonnegative due-minus-readiness window; zero-width windows require start equal to readiness. |
| `mean_relative_window_position` | Mean `(start − readiness) / (due_date − readiness)`; qualifying zero-width windows contribute 0.0. |
| `front_loaded_item_count` | Eligible window observations with relative position strictly less than 0.5. |
| `front_loaded_item_rate` | Front-loaded count / schedulable window item count. |
| `active_day_count` | Distinct dates among known allocations with usable dates, across all duration buckets. |
| `mean_sessions_per_active_day` | Total observed sessions / active day count. |
| `max_sessions_on_day` | Maximum total observed sessions on one active date. |
| `daily_session_load_variance` | Population variance of total session counts across active dates only. |


Continuity rows sort by `(scheduled_date, execution_rank)`; each gap is
`max(0, next date − previous date − 1)` days. Consecutive days and same-day
sessions have zero idle gap. Fan-in edges are independent observations;
transitive edges are never manufactured. Edge wait deliberately includes time
spent waiting for other prerequisites, a release, or an anchor. Item start delay
instead measures time after the latest prerequisite and release readiness. Thus
an immediate-ready dependent can have zero start delay but positive wait on an
earlier-finishing incoming edge.

Capacity usage counts sessions, not percentages. Residual work always uses
`UNDER_20_MINUTES`; other work uses its canonical duration category. Zero
capacity yields no numeric ratio, but every observed session is excess and the
cell is overloaded. A missing capacity definition is excluded from all capacity
aggregates, never assumed zero or unlimited. Existing EarliestFeasible rejects
missing definitions; the shared validator currently skips them. C1.2 preserves
both behaviours and adds no validation codes. Capacity comparison requires the
same complete capacity definitions for all observed buckets: a skipped cell is
unknown pressure, not evidence of zero overload, even when validation passes.
Canonical capacities are assumed
nonnegative, as in production.

## Empty populations and interpretation

Counts are zero when their populations are empty. Deadline rate/mean/max are
`None` without computable deadline items. Priority rate is `None` without
comparisons. Peak capacity ratio is `None` without positive-capacity observed
cells. Temporal mean/max/rate are `None` without valid computable waits.
Makespan is `None` without a computable completion. Fragmentation rate is `None`
without split items or if any split item has uncomputable dates; session gap
mean/max are `None` without computable pairs.
Dependency mean/max/rate are `None` without valid computable explicit edges.
Canonical population counts remain visible even when malformed proposals
prevent quality computations; thus invalid plans must not be compared as if
omitted work had achieved good quality.

Lower lateness, inversions, excess usage, idle gaps and waits generally indicate
less observed delay or pressure for comparable workloads; higher zero-wait and
immediate-transition rates indicate less waiting. Capacity utilization and
makespan have no universally preferred direction. Anchors, releases, dependency
structure and allowed overloads provide essential context. Validation counts
classify proposals and are not optimization scores.


## C1.3 snapshot and single-plan contract

`ScheduleItem.existing_scheduled_date` is an immutable adapter-time snapshot of
canonical `PlanningItem.scheduled_date`, defaulting to `None`. It introduces no
new canonical truth or database field. The adapter copies it exactly, including
past dates and `None`, without mutation or repair. A later canonical change is
visible in the next snapshot and cannot alter an existing problem.
`anchor_date` remains independent explicit manual date intent and retains its
existing hard validator constraint. The existing automatic schedule is only
observational context; algorithms may move unanchored items freely.

Movement compares the existing date with the **first proposed calendar session**
once per eligible item, regardless of execution rank or number of split rows.
Unknown items, missing work, and items with any unusable allocation date cannot
supply a movement observation. Partial work with a computable start can still
supply one. The denominator is the computable eligible population, not all
items with historical dates. Anchor movement remains visible even when the
validator marks the candidate hard-invalid; all such quality observations
remain diagnostic only.

Signed completion slack is positive before the deadline, zero on it, and
negative after it. It uses the existing conservative completion rule: missing,
incomplete, excess, or duplicate-session work cannot establish completion.
Relative window position uses existing readiness (including completion of every
explicit prerequisite) and a due date at or after readiness. Own completion is
not required for a computable start. Missing prerequisites are never invented.
For zero-width windows only start equal to readiness contributes 0.0; other
starts are excluded. For positive-width windows negative or greater-than-one
positions remain observable without clamping. Front-loading means strictly
`position < 0.5` and is descriptive, not a universal preference.

Daily load counts the same known, usable-date allocation rows as capacity usage,
including duplicate or partial sessions and buckets without defined capacity.
All duration buckets aggregate into one total per date. A usable row still
contributes even if another row for its item has an unusable date. Load is session
count, not work percentage or capacity-normalized pressure. Population variance
is `sum((daily_count − mean_daily_count) ** 2) / active_day_count`. No zero-load
horizon dates are inserted; a single active day has variance 0.0.

All appended counts and total movement are zero on empty populations. Movement
rate/mean/max, slack mean/min, window mean/rate, and daily load mean/max/variance
are `None` when their respective eligible population is empty. Eligible unchanged
movement contributes zero to distance statistics, including a maximum of zero.

`dangerously_low_slack_count` and `dangerously_low_slack_rate` are intentionally
deferred: design-spec §21.1 names the concept but freezes no threshold. No
arbitrary day cutoff or duplicate late/on-deadline threshold is introduced.
“Unnecessary movement” needs transition/repeated-run or counterfactual experiment
context; one problem/plan pair cannot establish necessity. “Unused earlier
opportunities” likewise requires capacity/counterfactual placement reasoning and
is deferred to later machinery. Runtime, memory, candidate/search-node counts
belong to experiment runners or algorithm instrumentation (§21.7); determinism
requires repeated-run evidence (§21.8). None are single-plan PerformanceVector
fields. C1.3 adds no weighted objective, ranking, or C2 scheduling machinery.
