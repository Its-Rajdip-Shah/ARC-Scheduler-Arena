# C4.6 LNS and C4.7 ALNS

Both engines improve an initial **complete, hard-legal plan**. They are not
standalone `SchedulingAlgorithm` constructors. They preserve `ScheduleProblem`,
canonical facts and C4.1–C4.5 implementations. Configurations, results and engines
are frozen slotted dataclasses; no objective or preferred operator pair is
supplied implicitly.

## Public API

`arena.search` additionally exports:

```python
DestroyOperator                 # RANDOM, TEMPORAL, DEPENDENCY
RepairOperator                  # EARLIEST, RANDOM
LargeNeighbourhoodConfig
LargeNeighbourhoodResult
LargeNeighbourhoodSearch
AdaptiveLargeNeighbourhoodConfig
AdaptiveLargeNeighbourhoodResult
AdaptiveLargeNeighbourhoodSearch
```

Enum string values are lowercase member names. Both engines expose
`improve_state(initial: SearchState)` and `improve_plan(problem, plan)`, the latter
using the existing strict `SearchState.from_plan` conversion. Results preserve
`initial_state` identity and expose `improved` and `total_improvement` properties.

LNS configuration requires `objective: PlanObjectiveConfig`, `horizon_days`,
`destroy_count`, `destroy_operator: DestroyOperator`,
`repair_operator: RepairOperator`, and `max_iterations`. Optional fields are
`max_evaluations=None` and `seed=0`.

ALNS configuration requires `objective`, `horizon_days`, `destroy_count`,
`max_iterations`, `reaction_factor`, `initial_temperature`, `cooling_rate`,
`minimum_temperature`, `reward_best`, `reward_accepted`, and `reward_rejected`.
Optional fields are `max_evaluations=None` and `seed=0`. All three destroy and both
repair operators participate, initially with unit weight.

Integers are exact Python integers, excluding booleans. Destroy count is positive;
horizon and budgets are nonnegative. Iteration budgets are mandatory and cannot
be `None`; seeds may be any integer. Configurations reject inherently impossible
calendar spans; engine entry checks `today + horizon_days <= date.max`, including
for empty inputs and zero budgets. ALNS numeric parameters must be finite,
positive, non-boolean numbers, with `reaction_factor <= 1`, `cooling_rate <= 1`,
`minimum_temperature <= initial_temperature`, and
`reward_best > reward_accepted > reward_rejected > 0`.

## Private destruction boundary and exact operator order

`SearchState` is always complete and immutable. The private frozen
`_PartialSchedule` stores the original state, sorted unique removed **item IDs**,
and the exact retained `SessionPlacement` objects. Destruction removes every
session of a selected item. Neither incomplete `SearchState` objects nor modified
problems are ever constructed. Shared functions live in `destroy_repair.py` and
are internal implementation details, not additional public API.

Eligible items have at least one session. The count is
`min(destroy_count, eligible_count)`. Input population order is ascending item ID.
All randomness uses the caller's local `random.Random`, seeded by the engine;
module-global RNG state is untouched.

- **RANDOM:** uniform `sample` without replacement from the eligible population.
- **TEMPORAL:** uniformly choose a seed item, select it first, then order other
  items by `(absolute difference from seed's original start date, item ID)`.
  Thus the seed remains first even if a smaller ID shares its start date.
- **DEPENDENCY:** uniformly choose a seed, then breadth-first traverse explicit
  dependency edges as an undirected graph. Visit sorted neighbours, marking them
  when enqueued; the seed is first. Stop at the requested count. If the connected
  component is too small, fill by the same seed-relative temporal order, skipping
  selected items. Edges with a zero-session endpoint are ignored. No transitive
  or inferred canonical edges are added.

Selection order determines membership at the count boundary; the private partial
object canonicalizes those selected IDs into sorted order.

## One forward repair attempt

Repair keeps a private identity-to-placement map, initialized with retained rows.
Removed items are processed in `ScheduleProblem.topological_order()`, sessions in
increasing session-index order. For each session, legal calendar dates satisfy:

1. Today and the item's release date, whichever is later.
2. The previously placed session date of that item (same-day sessions are legal).
3. Every explicit prerequisite's placed completion plus **one calendar day**.
4. Strictly before the first session of each **retained immediate dependent**.
5. The exact anchor for session 0, if present.

Dependency edges with a zero-session endpoint impose no repair constraint,
matching C4.1. Removed dependents are checked when they are subsequently repaired;
there is no anchor lookahead or backtracking. Consequently a random prerequisite
choice can block a later removed anchor. This attempt returns `None`, leaving
the accepted state unchanged. Retained dependents impose their upper bounds
before a prerequisite date is chosen.

Dates are enumerated in ascending order within the inclusive calendar interval
`[today, today + horizon_days]`, filtered by those hard constraints. If the
session's **own original date** lies outside that interval and satisfies all
other constraints, it is appended as an unchanged fallback. This never permits
another out-of-horizon destination, extends the horizon, or moves an anchored
first session. An anchor beyond the horizon remains at its unchanged original
date. Ordinal arithmetic handles bounds and dependency increments without
constructing `date.max + 1`.

**EARLIEST** chooses the first legal date. **RANDOM** uniformly chooses one legal
date using `randrange(number_of_legal_dates)`. The ordered enumeration is
represented as an ordinal interval plus at most one fallback, so a wide calendar
does not require allocating a list of dates. No legal date means a clean failed
attempt. Deadline and capacity costs never filter destinations: late work and
overload remain soft in C4.1.

Only after all session identities are present is a complete `SearchState`
constructed. Unexpected rejection at that boundary raises `RuntimeError` as an
implementation-contract error. Failed and identical repairs return `None` and
are never scored. Successful distinct states preserve all retained objects and
canonical session identities. Export derives exact remaining percentages through
C4.1 `to_plan`; no work is dropped or fabricated.

## Budgets and LNS acceptance

One iteration selects an item set and attempts **one** repair. At every attempt
boundary, check iteration budget, then evaluation budget, then absence of
schedulable items. Termination reasons are respectively `iteration_budget`,
`evaluation_budget`, and `no_schedulable_items`; sampled attempts cannot prove a
local optimum. Initial scoring does not count against evaluations. Every complete
distinct candidate is scored exactly once with the explicit objective; failed or
identical proposals consume zero evaluations. A proposal using the last available
evaluation can still be accepted before the next boundary check.

LNS accepts exactly when `candidate.total < incumbent.total`. Rejected, failed and
identical attempts leave the incumbent and both histories unchanged. Result
fields are `initial_state`, `final_state`, `initial_objective`, `final_objective`,
`iterations`, `evaluations`, `accepted_repairs`, `termination_reason`,
`objective_history`, and `accepted_changes_history`. Objective history includes
the initial total and strictly decreases on each acceptance.

## ALNS acceptance, adaptation and accounting

Every iteration independently roulette-selects one destroy and one repair
operator in enum declaration order. A draw belongs to the first interval whose
cumulative weight strictly exceeds `rng.random() * sum(weights)`; implementation
scales weights by their maximum to avoid sum overflow. Selection precedes item
selection and repair draws. All weights remain strictly positive.

Keep separate current and best-ever states. With
`delta = candidate.total - current.total`, accept all nonpositive deltas without
an acceptance RNG draw. Otherwise accept exactly when
`rng.random() < exp(-delta / temperature)`. Best-ever changes only on strict
improvement. The per-iteration outcome and reward are:

| Outcome string | Meaning | Reward |
|---|---|---|
| `best` | Accepted strict new global best | `reward_best` |
| `accepted` | Accepted, but not a new best (including equal totals) | `reward_accepted` |
| `rejected` | Scored proposal rejected | `reward_rejected` |
| `failed` | Repair failed or produced the identical state; no score | `reward_rejected` |

Only the selected destroy and repair weights are updated:

```text
new_weight = (1 - reaction_factor) * old_weight + reaction_factor * outcome_reward
```

For example, reaction `.5`, initial weight `1`, and successive rewards `8, 4, 2,
2` produce `4.5, 4.25, 3.125, 2.5625`. Unselected weights stay unchanged. A lower
bound of `min(old_weight, reward)` protects the convex-combination invariant from
floating-point underflow at subnormal positive values. Adaptation uses objective
feedback, never Arena evaluator feedback.

After **every initiated iteration**, including failed/identical repair, update
`temperature = max(minimum_temperature, temperature * cooling_rate)`. The floor
does not terminate search; the mandatory iteration budget guarantees boundedness.

ALNS results contain initial state/objective, `final_state`/`final_objective`
(best-ever), and `last_state`/`last_objective` (current endpoint), plus:

- `iterations`, `evaluations`, `accepted_repairs`, `rejected_repairs`,
  `failed_repairs`, `termination_reason`, `final_temperature`;
- `best_objective_history`: initial total plus strict new best totals;
- `walk_objective_history`: initial total plus every accepted current total;
- `accepted_changes_history`: one tuple of replacement placements per acceptance;
- `operator_history`: `(DestroyOperator, RepairOperator, outcome_string)` triples;
- `destroy_weights` and `repair_weights`: immutable `(enum_member, weight)` tuples
  in fixed enum declaration order.

`accepted_repairs + rejected_repairs + failed_repairs == iterations`,
`accepted_repairs + rejected_repairs == evaluations`, and operator-history length
is iterations. Walk-history length is accepted repairs plus one. The final best
score is the minimum on the accepted walk; last state may be worse than best.

## Replay and controlled examples

Change tuples are sorted changed `SessionPlacement` rows between complete states,
**not C4.1 Moves**. Replay each tuple atomically: replace its `(item_id,
session_index)` identities in the previous accepted state's map, then construct a
complete state. LNS replay ends at `final_state`; ALNS replay ends at `last_state`.
Rows within one tuple need not define legal intermediate individual moves.

A controlled two-item example has `A -> B`, original dates `(today+1, today+2)`,
and only unit quadratic timing cost relative to actual readiness. The total is
`1`. Moving A alone to today leaves total `1` because B now waits a day; B cannot
move earlier while A stays. All enumerated C4.1 relocate/swap/shift neighbours are
tied, worse, or illegal. Destroying both and repairing earliest yields
`(today, today+1)` with total `0`, a genuine joint improvement.

For a controlled failure, start with `A -> B` at `(today, today+1)` and B anchored
to `today+1`. Destroy both. Randomly placing A at `today+2` leaves no legal date
for B, so the attempt fails without returning or scoring a partial state. If B
were retained, its start would instead bound A's candidates strictly below it.

Tests also drive a real ALNS walk with timing totals `4 -> 0 -> 1`, followed by a
rejected proposal of `4` and an identical failed proposal. The final best is `0`,
last is `1`, and the selected weights follow the arithmetic example above.

## Independent quality assessment

Search scores only complete states using C4.1 `score_state` and the caller's
`PlanObjectiveConfig`. It never uses C3 construction estimates or the independent
`PerformanceVector` as its objective. Independent `validate_plan` checks and
constructor-produced plans from PressureGreedy and HybridCostGreedy appear in the
tests. Standalone API imports require neither Django nor the performance module.
Frozen C2/C3 fingerprints and C4.1–C4.5 tests remain unchanged. These engines do
not establish winning weights, operators, or scheduler quality rankings.
