# ARC Scheduling Laboratory --- Scheduler Design & Experimentation Specification

**Status:** Pre-implementation design specification\
**Purpose:** Define the scheduling problem, non-negotiable invariants,
experimental variables, candidate algorithms, synthetic data strategy,
evaluation methodology, and production-integration plan for ARC's
scheduler.

------------------------------------------------------------------------

## 1. Purpose and philosophy

ARC's scheduler chooses execution dates for work that is currently
schedulable. The goal is not merely to fill empty capacity or sort tasks
by priority. It should produce a schedule that a student can
realistically follow while respecting temporal constraints, hierarchy,
user-fixed decisions, workload capacity, priority, deadline risk, and
schedule stability.

The scheduler laboratory will deliberately separate:

1.  **Hard invariants** --- rules no algorithm is allowed to violate.
2.  **Signals** --- information available to an algorithm.
3.  **Preferences/objectives** --- legitimate areas where algorithms may
    disagree.
4.  **Algorithms** --- alternative strategies for turning the same legal
    input into a schedule.
5.  **Evaluation** --- independent measurements and blinded preference
    comparisons used to decide which strategy is most useful.
6.  **Production integration** --- mapping the selected strategy back
    into ARC without changing the meaning of ARC's domain model.

An algorithm that violates a hard invariant does not receive a lower
score. Its output is **invalid**.

------------------------------------------------------------------------

## 2. Core scheduling model

For each execution-schedulable item (i), the scheduler chooses a
`scheduled_date` (d_i).

The scheduler consumes domain information such as:

-   hierarchy and completion state;
-   release date;
-   due date;
-   existing scheduled date;
-   user anchor/fixed-schedule state;
-   priority;
-   estimated-duration category;
-   item category/type;
-   category-specific daily capacity;
-   current date;
-   planning horizon.

The scheduler does **not** redefine these facts.

### 2.1 Output

Primary output:

-   `scheduled_date` for each movable execution-schedulable item.

Diagnostic/experimental outputs may additionally contain:

-   why a date was selected;
-   candidate dates considered;
-   objective components;
-   capacity/load state;
-   deadline/slack measures;
-   movement incurred;
-   runtime;
-   algorithm name/version;
-   deterministic seed/configuration where applicable.

These diagnostics are laboratory outputs, not necessarily production
database fields.

------------------------------------------------------------------------

## 3. Hierarchy and scheduling frontier

ARC distinguishes the planning hierarchy from the execution frontier.

### 3.1 Current invariant

-   Completed items are not scheduled.
-   An unfinished parent with unfinished descendants is not
    independently execution-schedulable.
-   An unfinished leaf is a scheduler candidate.
-   When completion causes a parent to have no remaining unfinished
    children, that parent becomes a newly exposed frontier item and
    therefore a scheduler candidate.

This is intentionally the initial rule. If real usage later shows that
non-leaf parents also need independently scheduled execution blocks,
that should be treated as a domain-model revision rather than quietly
added to an algorithm.

### 3.2 Completion behaviour

Completion must recalculate the frontier.

Two cases are distinguished:

**Frontier unchanged** - Capacity may have been freed. - Existing
unrelated work does not need to be globally rearranged immediately.

**New frontier item exposed** - The feasible scheduling problem has
changed because a new executable item now exists. - The newly exposed
item receives/derives its scheduling priority according to ARC's
priority rules. - A global rescheduling run may be triggered so the new
item can be placed coherently.

------------------------------------------------------------------------

## 4. Hard invariants

These rules are shared by every algorithm and should preferably be
enforced by common candidate-generation/domain code rather than
reimplemented separately.

### 4.1 Temporal feasibility

For a movable item with a release date:

`scheduled_date >= release_date`

For a movable item with a due date:

`scheduled_date <= due_date`

For new automatic placements:

`scheduled_date >= today`

When `release_date == due_date`, there is exactly one legal execution
date.

A missing release date means the effective lower bound is the current
scheduling date/today.

A missing due date requires a finite planning horizon supplied by
scheduler policy/configuration. The algorithm may not search
indefinitely.

### 4.2 Deadline policy

Due dates are hard upper bounds for automatic scheduling.

If nominal capacity makes the workload impossible to fit comfortably
before a deadline, ARC should prefer **controlled overload before the
deadline** rather than automatically scheduling work after the due date.

Deadline violation is therefore not an experimental preference.

### 4.3 User anchoring / fixed scheduling

ARC should support an explicit user anchor on an execution card.

Conceptual UI:

`⚓ inactive → click → ⚓ anchored`

Recommended semantic backend field:

`is_schedule_fixed` (or equivalently clear domain terminology)

An anchored item:

-   retains its chosen `scheduled_date`;
-   is excluded from automatic movement;
-   still consumes workload capacity on its date;
-   influences placement of movable work around it.

Anchoring is a hard constraint, not merely a large movement penalty.

### 4.4 Hierarchy

-   Completed items are excluded.
-   Non-frontier parents are excluded from independent execution
    scheduling.
-   Every eligible movable frontier item must receive a legal placement
    within the configured planning horizon if the domain constraints
    permit one.

### 4.5 Determinism

For algorithms declared deterministic, identical:

-   items;
-   hierarchy;
-   constraints;
-   priorities;
-   duration classes;
-   capacities;
-   anchors;
-   existing schedule;
-   current date;
-   planning horizon;
-   algorithm configuration

must produce the same schedule.

Database query ordering, hash/set iteration, or incidental insertion
ordering must never determine the result.

------------------------------------------------------------------------

## 5. Timeline card context requirement

Timeline cards need immediate hierarchical context without requiring
hover.

Preferred title structure:

`SOFT2412 | Assignment 2 | Group Project |` **`Initialize Git`**

Design requirements:

-   ancestry/context appears above the leaf title;
-   leaf title is visually dominant/bold;
-   breadcrumb is constrained to a sensible width and may ellipsize;
-   cards have explicit minimum and maximum widths;
-   cards must not expand horizontally according to arbitrarily long
    ancestry;
-   expanded/hover states may expose the complete untruncated ancestry.

The scheduler does not depend on this presentation rule, but the feature
should accompany scheduler work because scheduling tiny leaf tasks is
only understandable if their parent context is visible.

------------------------------------------------------------------------

## 6. Estimated-duration representation

ARC intentionally avoids asking users for false precision such as exact
minute estimates.

Proposed experimental five-class representation:

  Class    Meaning
  -------- -------------
  1 dot    `<20 min`
  2 dots   `20–60 min`
  3 dots   `1–4 h`
  4 dots   `4–12 h`
  5 dots   `>12 h`

This should itself be experimentally validated. A four-class model can
be compared with the five-class model to determine whether separating
very large work materially improves schedule quality.

### 6.1 Capacity weights

Duration classes should map to deterministic **capacity units**, not
pretend to be exact minutes.

Candidate mappings are experimental parameters, for example:

-   `<20m` → 1 unit
-   `20–60m` → 2 units
-   `1–4h` → 4 units
-   `4–12h` → 8 units
-   `>12h` → 12 or 16 units

The exact mapping is deliberately not frozen yet.

### 6.2 Large tasks

The initial scheduler still assigns one `scheduled_date` per item. It
does not automatically split a `>12h` task over multiple days.

ARC's hierarchy provides the preferred way to decompose genuinely large
work into smaller executable children. Multi-day execution blocks can be
investigated later as a separate domain capability.

------------------------------------------------------------------------

## 7. Capacity

Capacity remains category-specific according to ARC's domain model.

For category (c) and date (d):

`load(c,d) = sum(capacity_weight(item))`

for work assigned to that category/date.

Nominal overload is:

`overload(c,d) = max(0, load(c,d) - capacity(c,d))`

Capacity is a **soft limit**, because hard deadlines may make overload
necessary.

### 7.1 Distributed overload

When overload is unavoidable, ARC should avoid concentrating all excess
work onto one day if equivalent/legal distributions exist.

A convex overload penalty naturally encourages this:

`P_overload(d) = w_o * max(0, load(d) - capacity(d))^p`, with `p > 1`

For example, a squared penalty makes four days overloaded by one unit
cheaper than one day overloaded by four units.

This is a preference/objective, not a hard rule: hard constraints still
dominate.

------------------------------------------------------------------------

## 8. Scheduling opportunity, slack and deadline risk

Urgency should not primarily be based on elapsed time since release or a
simplistic rule such as "due within three days."

The key question is:

> If this work is not executed now, how much safe scheduling opportunity
> remains before its deadline?

Relevant signals may include:

-   days remaining;
-   legal candidate dates remaining;
-   remaining category-specific capacity before due;
-   competing workload before due;
-   task capacity weight;
-   anchored work consuming future capacity;
-   priority of competing work.

### 8.1 Nonlinear deadline-risk preference

As remaining slack disappears, postponement should become
disproportionately expensive.

Conceptually:

-   abundant slack → very small risk;
-   moderate slack → noticeable risk;
-   little slack → expensive;
-   almost no slack → extremely expensive.

A family of candidate functions can be tested, for example
reciprocal/power, exponential, or piecewise convex functions.

The exact formula and weights are experimental preferences, not
invariants.

------------------------------------------------------------------------

## 9. Priority

Priority determines competition for desirable scarce capacity.

All else equal, postponing a higher-priority item should be more
expensive than postponing a lower-priority item.

Priority must not override feasibility. A distant high-priority item
must not force an imminent-deadline item into an illegal date.

Candidate objective form:

`P_priority(item,date) = f(priority) * postponement_or_risk_signal`

Alternative priority formulations should be benchmarked.

------------------------------------------------------------------------

## 10. Earlier execution: competing hypotheses

ARC should explicitly experiment with different planning philosophies
rather than assuming one is correct.

### 10.1 Aggressive-earlier hypothesis

Earlier legal execution is intrinsically valuable.

Expected behaviour: - aggressively uses earlier free capacity; - tends
to create deadline buffer; - may front-load the student's workload; -
may move previously acceptable tasks frequently.

### 10.2 Stable/risk-based hypothesis

Earlier is not automatically better.

A safe existing placement should remain unless moving it meaningfully
improves deadline risk, capacity balance, priority treatment, or another
objective.

Expected behaviour: - lower schedule churn; - calmer distribution; - may
leave work later than an aggressively proactive student prefers.

### 10.3 Hybrid hypothesis

Moderate proactive pressure plus schedule inertia.

The laboratory should test these philosophies rather than deciding their
winner in advance.

------------------------------------------------------------------------

## 11. Movement / schedule stability

Rescheduling should not rearrange a good schedule for negligible
benefit.

For an existing scheduled item, movement can incur:

-   a fixed cost for moving at all;
-   an additional cost proportional or nonlinear in number of days
    moved.

Conceptual form:

`P_movement = 0` when unchanged.

Otherwise:

`P_movement = M0 + M1 * distance(old_date, new_date)`

Alternative functions and weights are experimental.

Anchored items are different: movement is impossible, not expensive.

------------------------------------------------------------------------

## 12. Backward bubbling

ARC does not need a special hardcoded "bubble backward" procedure.

When earlier capacity becomes available, an eligible future item may
move earlier if the chosen algorithm determines that the improvement
outweighs movement/stability costs.

Therefore backward bubbling can emerge naturally from optimization.

Likewise, ARC is not required to fill every available earlier slot.

------------------------------------------------------------------------

## 13. Candidate objective model

A useful conceptual family is:

`TotalCost = deadline_risk + priority_cost + overload_cost + movement_cost + timing_preference`

subject to all hard invariants.

More explicitly:

`min Σ_i [P_risk(i,d_i) + P_priority(i,d_i) + P_movement(i,d_i) + P_timing(i,d_i)] + Σ_(category,date) P_overload(load(category,date))`

The laboratory must not treat this exact equation as final. Individual
algorithms may implement different objective structures while sharing
the same hard feasible domain.

------------------------------------------------------------------------

## 14. Algorithm families to experiment with

### 14.1 Earliest-feasible baseline

A deliberately simple baseline: - order work deterministically; - choose
the earliest legal placement.

Useful as a lower-complexity reference.

### 14.2 Pressure/priority greedy

Order items by scheduling pressure/flexibility, then priority, then
deterministic tie-breakers.

Choose a legal date according to a relatively simple capacity/risk
policy.

### 14.3 Aggressive-earlier cost greedy

Score all legal candidate dates with a strong preference for earlier
execution.

Useful for testing the hypothesis that front-loading work produces
better student schedules.

### 14.4 Stable/risk cost greedy

Score legal candidate dates using deadline/slack risk, overload,
priority, and meaningful movement penalties.

Earlier placement is only mildly preferred unless it improves safety.

### 14.5 Hybrid cost greedy

Intermediate timing and movement weights.

### 14.6 Greedy plus local improvement

Generate an initial schedule, then repeatedly test deterministic local
modifications such as:

-   moving one item;
-   swapping placements;
-   moving an item into newly free earlier capacity.

Accept only changes that improve the selected objective while preserving
invariants.

### 14.7 Beam search

Maintain the best (K) partial schedules rather than committing to only
one partial future.

This explores more of the decision space while controlling combinatorial
growth.

### 14.8 Exact/exhaustive tree search

An experimental reference algorithm may enumerate scheduling decisions
as a tree:

-   each node represents a partial legal schedule;
-   branches represent legal next placement choices;
-   branches terminate immediately when no legal completion is possible
    or a hard invariant would be violated;
-   complete leaves represent valid schedules;
-   branch-and-bound can prune any partial schedule whose lower-bound
    cost cannot beat the best complete schedule found.

Naive exhaustive complexity can be enormous. With (N) items and many
candidate dates, the search space can grow
exponentially/combinatorially.

This makes exhaustive search inappropriate as the default production
scheduler for large datasets, but potentially valuable for:

-   small micro-scenarios;
-   generating known-optimal reference schedules;
-   measuring heuristic optimality gaps;
-   validating greedy/local-search algorithms.

Cloud computing is not automatically required. First benchmark locally
on small scenarios and add pruning/memoization/branch-and-bound. Cloud
compute becomes useful only if experiments that genuinely require larger
exact searches exceed reasonable local runtime.

### 14.9 Global mathematical/constraint optimizer

A formal optimization implementation (e.g. integer/constraint
programming) can serve as another oracle/reference on manageable
instances.

The purpose is not necessarily to ship it. It can answer:

> How close is the fast production heuristic to a much more expensive
> solution?

------------------------------------------------------------------------

## 15. Deterministic tie-breaking

Every deterministic algorithm needs an explicit ordering for ties.

Candidate tie-break dimensions include:

1.  objective/cost;
2.  deadline risk;
3.  movement amount;
4.  execution date;
5.  priority;
6.  stable item identifier.

The final ordering should be documented per algorithm.

------------------------------------------------------------------------

## 16. Scheduling laboratory architecture

The experimentation environment should live in a separate
repository/package rather than contaminating ARC's production scheduling
services.

Suggested conceptual layout:

``` text
arc-scheduling-lab/
├── README.md
├── docs/
│   └── scheduler-spec.md
├── src/
│   ├── domain/
│   │   ├── models.*
│   │   ├── candidates.*
│   │   └── invariants.*
│   ├── algorithms/
│   │   ├── earliest_feasible.*
│   │   ├── pressure_greedy.*
│   │   ├── aggressive_early.*
│   │   ├── stable_cost.*
│   │   ├── hybrid_cost.*
│   │   ├── local_search.*
│   │   ├── beam_search.*
│   │   └── exact_or_oracle.*
│   ├── scenarios/
│   ├── evaluation/
│   │   ├── metrics.*
│   │   ├── compare.*
│   │   └── reports.*
│   └── adapters/
│       └── arc_schema.*
├── tests/
└── data/
    ├── fixtures/
    ├── generated/
    └── results/
```

Exact language/framework should be selected after inspecting ARC's
current backend so the laboratory can replicate/adapt its database
schema cleanly.

------------------------------------------------------------------------

## 17. Shared invariant layer

Algorithms should not independently implement legality.

Preferred pipeline:

``` text
ARC-compatible domain input
        ↓
frontier resolver
        ↓
hard-invariant/candidate generator
        ↓
legal candidate space
        ↓
algorithm A / B / C / ...
        ↓
shared validator
        ↓
shared evaluator
```

This reduces the chance that one experimental algorithm accidentally
changes the meaning of release dates, deadlines, anchoring, or
hierarchy.

------------------------------------------------------------------------

## 18. Experimental databases and scenario strategy

A single large database is not sufficient.

Use multiple complementary datasets with the **same ARC-compatible
structure**.

### 18.1 Micro-scenario databases/fixtures

Small, interpretable scenarios (roughly 5--20 items) designed to isolate
one behaviour.

Examples:

-   release-only;
-   due-only;
-   release + due;
-   release = due;
-   no temporal constraints;
-   parent with one child;
-   parent with many children;
-   deep ancestry;
-   siblings with mixed completion;
-   newly exposed parent;
-   huge slack;
-   almost-zero slack;
-   equal constraints with unequal priority;
-   distant high priority vs imminent lower priority;
-   anchored item;
-   anchored overloaded date;
-   unavoidable overload;
-   free earlier slot after completion.

Purpose: prove behaviour and diagnose failures.

### 18.2 Semester-shaped realistic datasets

Synthetic but realistic university workloads:

-   multiple courses/roots;
-   assignments;
-   weekly quizzes;
-   labs/tutorials;
-   projects;
-   nested subtasks;
-   breaks and teaching weeks;
-   mixed priorities;
-   realistic releases/deadlines;
-   existing schedules;
-   completion history;
-   anchors;
-   all duration classes.

Purpose: determine whether a schedule feels usable across an actual
semester.

### 18.3 Pathological/stress datasets

Examples:

-   50 tasks sharing a deadline;
-   many tasks released late;
-   extremely dense two-week workload;
-   sparse three-month workload;
-   many tied priorities;
-   many equivalent candidate dates;
-   impossible nominal capacity;
-   many anchors;
-   deep hierarchies;
-   large item counts.

Purpose: performance, determinism, overload behaviour, and algorithmic
robustness.

### 18.4 Multiple database instances

Multiple databases or fixture snapshots are useful for experimental
variance, provided they share the same schema and are reproducibly
generated.

Recommended approach: - deterministic scenario generators with explicit
seeds; - named fixed benchmark snapshots; - separate result storage from
input datasets; - never mutate the canonical benchmark fixture during an
algorithm run.

This provides variance without losing reproducibility.

------------------------------------------------------------------------

## 19. Database compatibility with ARC

The laboratory database should replicate the relevant ARC schema closely
enough that experimental results can map back into production.

However, avoid blindly copying unrelated application tables.

Replicate the scheduling-relevant domain: - planning items; -
hierarchy/parent relationships; - completion state; - item
type/category; - release date; - due date; - scheduled date; -
priority; - duration class; - root/course ownership; - capacity
settings; - schedule anchor/fixed flag once introduced; - any scheduler
metadata that is truly domain-relevant.

Use an adapter layer if the lab's internal representation needs to
differ from Django/production representation.

The eventual production scheduler should be able to consume equivalent
inputs without semantic translation surprises.

------------------------------------------------------------------------

## 20. Evaluation: validity first

Every generated schedule passes the shared validator.

Examples:

-   no automatic execution before release;
-   no automatic execution after due;
-   no anchored movement;
-   no completed items scheduled;
-   no non-frontier parent independently scheduled;
-   all required frontier work legally placed where a legal placement
    exists;
-   deterministic algorithms reproduce identical output.

Any failure marks the schedule/algorithm run **invalid**.

Hard-invariant violations are not averaged into a quality score.

------------------------------------------------------------------------

## 21. Objective performance metrics

For valid schedules, record descriptive metrics rather than immediately
collapsing everything into one magic score.

### 21.1 Deadline/slack safety

-   mean deadline risk;
-   median deadline risk;
-   95th percentile deadline risk;
-   maximum deadline risk;
-   distribution of remaining slack at execution;
-   number/proportion of tasks executed with dangerously low slack.

### 21.2 Capacity and overload

-   total overload units;
-   maximum single-day overload;
-   number of overloaded days;
-   overload variance/concentration;
-   overload by category;
-   peak load relative to capacity.

### 21.3 Priority treatment

-   priority-weighted postponement;
-   high-priority displacement;
-   relative treatment of competing priorities under equivalent
    constraints.

### 21.4 Stability

-   number of previously scheduled items moved;
-   proportion moved;
-   total movement distance in days;
-   maximum movement distance;
-   unnecessary movement under unchanged conditions.

### 21.5 Timing behaviour

-   average relative placement within feasible window;
-   degree of front-loading;
-   unused earlier opportunities;
-   proximity-to-deadline distribution.

### 21.6 Load balance

-   mean daily load;
-   variance;
-   peak;
-   concentration indices.

### 21.7 Computational performance

-   wall-clock runtime;
-   memory where useful;
-   number of candidate evaluations;
-   search nodes explored/pruned for search algorithms;
-   scaling with item count and horizon size.

### 21.8 Determinism

-   repeated-run schedule equality;
-   result hashes for benchmark fixtures.

------------------------------------------------------------------------

## 22. Avoiding circular evaluation

Do not judge algorithms solely using the same weighted objective
function they optimize.

If an algorithm minimizes:

`risk + 4*movement + 2*overload`

and the benchmark defines "best" as exactly that same equation, the
experiment merely proves that the optimizer optimizes its own objective.

Therefore evaluation should combine:

-   hard validity;
-   independent descriptive metrics;
-   algorithm runtime/complexity;
-   blinded qualitative preference.

------------------------------------------------------------------------

## 23. Blinded human-style preference evaluation

Schedules can be rendered anonymously as Schedule A, B, C, etc., with
algorithm identities hidden and ordering randomized.

Pairwise comparison is preferable to arbitrary `/100` scoring.

Example evaluation questions:

-   Which schedule would a student more reasonably want to follow?
-   Is workload unnecessarily front-loaded?
-   Is work left unnecessarily close to deadlines?
-   Is overload distributed sensibly?
-   Are existing plans moved without meaningful benefit?
-   Are important tasks treated appropriately?
-   Does the schedule feel executable rather than mathematically tidy?
-   Is there no meaningful preference between the two?

The user's own blinded preferences should be included for representative
scenarios.

Model-assisted qualitative review can supplement this, but should not be
treated as sole ground truth.

Disagreement between evaluators is useful: it may reveal a genuine
configurable planning preference such as proactive versus stable
scheduling.

------------------------------------------------------------------------

## 24. Pairwise experimental analysis

For algorithms A, B, C, etc.:

-   compare A vs B;
-   A vs C;
-   B vs C;
-   randomize display order;
-   permit "no meaningful preference";
-   aggregate preferences across scenario families.

Always report pairwise preference alongside objective metrics and
runtime.

A very fast algorithm that is almost never distinguishable from an
expensive oracle may be the stronger production engineering choice.

------------------------------------------------------------------------

## 25. Algorithm configuration experiments

The lab should support parameter sweeps over:

-   deadline-risk function family;
-   deadline-risk weight;
-   priority transformation/weight;
-   overload exponent and weight;
-   movement fixed penalty;
-   movement distance penalty;
-   aggressive-earlier timing weight;
-   duration-class capacity weights;
-   four vs five duration classes;
-   beam width;
-   local-search iteration budget;
-   planning horizon;
-   tie-break policies where semantically acceptable.

Configurations must be versioned/stored with results.

------------------------------------------------------------------------

## 26. Planning horizon

Tasks without due dates require a finite upper search bound.

This remains an explicit product/experimental policy decision.

Candidate approaches: - fixed rolling horizon; - academic/semester
horizon; - later of a fixed horizon and known academic horizon; -
adaptive horizon based on workload.

The laboratory should make this configurable and measure sensitivity
before production policy is frozen.

------------------------------------------------------------------------

## 27. Exhaustive tree search: practical role

The proposed decision-tree algorithm is useful, but primarily as an
**oracle on small instances**.

### Tree structure

At depth (k), the node contains placements for the first (k) decision
items.

For the next item, branch over each legal candidate date.

Immediately prune when: - a hard invariant would be violated; -
remaining unassigned items can no longer be legally completed; - a
branch-and-bound lower bound proves the branch cannot beat the best
known complete solution.

Potential enhancements: - schedule most constrained items first; -
memoize equivalent states; - symmetry breaking; - branch-and-bound; -
lower-bound heuristics; - parallelize independent top-level branches.

### Why not production by default?

Even if each of (N) items had only (D) candidate dates, naive
enumeration can approach (D\^N) combinations before pruning.

It is nevertheless extremely valuable for small benchmark scenarios
because it can tell us how much quality a fast heuristic sacrifices.

------------------------------------------------------------------------

## 28. Suggested experimental sequence

### Phase B0 --- domain prerequisites

-   finalize duration classes;
-   add fixed/anchor field to ARC-compatible schema;
-   define hierarchy/frontier semantics;
-   improve Timeline card ancestry presentation.

### Phase B1 --- laboratory foundation

-   create separate repository;
-   document design;
-   reproduce relevant ARC scheduling schema;
-   implement common domain model;
-   implement invariant/candidate layer;
-   implement validator;
-   implement scenario generators and fixed fixtures;
-   implement metrics/reporting.

### Phase B2 --- baselines

-   earliest-feasible;
-   pressure/priority greedy;
-   aggressive-earlier greedy;
-   stable/risk greedy;
-   hybrid greedy.

### Phase B3 --- advanced strategies

-   local improvement;
-   beam search;
-   exact tree search on small cases;
-   mathematical/constraint optimizer where useful.

### Phase B4 --- experiments

-   run algorithms over micro, realistic and pathological suites;
-   run parameter sweeps;
-   record metrics;
-   perform blinded pairwise schedule comparisons;
-   compare heuristic results with oracle results on tractable
    scenarios.

### Phase B5 --- production selection

Select based on: - invariant correctness; - schedule quality across
independent metrics; - human preference; - robustness; - runtime; -
implementation/maintenance complexity.

### Phase B6 --- ARC integration

-   port/adapt chosen scheduler;
-   wire Reschedule;
-   preserve anchors;
-   trigger frontier-aware rescheduling;
-   validate production results with the same invariant suite;
-   perform final Timeline UI integration tests.

------------------------------------------------------------------------

## 29. Key hypotheses to test

1.  Aggressive earlier scheduling may perform well under light workloads
    but front-load dense workloads excessively.
2.  Stable/risk-based scheduling may reduce churn but sometimes leave
    work later than users prefer.
3.  A hybrid may offer a better balance, but this must not be assumed
    before benchmarking.
4.  Convex overload penalties should distribute unavoidable overload
    more naturally than linear penalties.
5.  Remaining scheduling opportunity/slack should predict urgency better
    than simple days-to-deadline thresholds.
6.  A fast greedy/local-improvement algorithm may approach oracle
    quality closely enough to make expensive global optimization
    unnecessary in production.
7.  A fifth `>12h` duration class may improve major-work handling enough
    to justify additional UI complexity.
8.  Movement inertia should improve perceived schedule quality when
    Reschedule is repeatedly used.
9.  Exact tree/global optimization is likely most valuable as an
    experimental oracle rather than the production scheduler.

------------------------------------------------------------------------

## 30. Decisions currently frozen

-   Non-leaf unfinished parents are not independently
    execution-schedulable for the initial model.
-   Leaves/newly exposed frontier items are scheduler candidates.
-   Frontier changes caused by completion are explicitly detected.
-   Release and due dates are hard automatic-scheduling bounds.
-   Capacity is soft and controlled overload is preferable to automatic
    deadline violation.
-   User anchors are hard immobility constraints.
-   Priority affects competition but cannot override feasibility.
-   Deadline risk should be based substantially on remaining scheduling
    opportunity and should increase nonlinearly as slack disappears.
-   Overload should be discouraged nonlinearly so unavoidable overload
    tends to distribute.
-   Existing schedule movement should be a preference/cost for movable
    work, not a hard prohibition.
-   Algorithms may disagree about whether earlier execution is
    intrinsically better.
-   All algorithms share one invariant/validation layer.
-   Evaluation will not reduce correctness and schedule quality to one
    opaque score.
-   Synthetic micro, semester-scale, and pathological datasets are all
    required.
-   Experimental datasets should be reproducible.
-   The laboratory should be kept separate from ARC production code
    while remaining schema-compatible.

------------------------------------------------------------------------

## 31. Decisions still open to experimentation

-   Final repository/project name.
-   Exact duration-class capacity weights.
-   Whether four or five duration classes are preferable.
-   Planning horizon for undated work.
-   Exact deadline-risk function.
-   Priority weighting/transformation.
-   Overload exponent/weight.
-   Movement penalty shape/weight.
-   Strength of proactive/earlier preference.
-   Best greedy ordering.
-   Whether local search materially improves greedy schedules.
-   Useful beam width.
-   Practical size limit for exhaustive search.
-   Whether a mathematical optimizer is worth maintaining.
-   Final production algorithm or hybrid.
-   Whether planning style should eventually become user-configurable.

------------------------------------------------------------------------

## 32. Production success criterion

The final production scheduler should not merely obtain the lowest
experimental objective value.

It should:

-   always obey ARC's hard scheduling semantics;
-   generate schedules that remain safe around deadlines;
-   treat priority sensibly;
-   tolerate unavoidable overload without concentrating it
    unnecessarily;
-   avoid gratuitous reshuffling;
-   exploit useful newly available capacity when appropriate;
-   respect explicit user decisions;
-   behave deterministically;
-   remain computationally practical for normal student workloads;
-   produce schedules that users actually prefer to follow.

The scheduling laboratory exists to discover that strategy empirically
rather than assume it in advance.
