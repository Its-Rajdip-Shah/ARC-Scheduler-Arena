# C2 shared scheduling mechanics and objective primitives

`arena.scheduling.mechanics` and `arena.scheduling.objectives` are pure Python.
They do not import Django, persistence adapters, or PerformanceVector. The
existing domain, validator, adapter and independent evaluator are unchanged.

## Sessions and state

`effective_bucket(item)` maps residual work to UNDER_20_MINUTES. Otherwise it
uses the canonical duration category. `session_pieces(item)` guarantees exact
conservation: its strictly positive pieces sum to remaining_fraction × 100.
Zero work returns no pieces. The three atomic categories have at most one
session; UNDER_8_HOURS and UNDER_16_HOURS at most two; OVER_16_HOURS at most three.
Percentages are of total work. The historical .01 rounding, final correction,
and positive-piece filtering are retained whenever their output conserves work.
Otherwise C2 returns one exact remaining-work piece. Thus tiny residual work
may collapse to fewer sessions, never fabricate additional work. The final
remainder is not forced to .01 precision.


`ScheduleState(problem, allocations=())` freezes allocations and derives
read-only usage, completion, and next_rank_by_date indexes. Usage counts sessions
per (date, effective bucket), not percentages. The next rank defaults to 1 on an
unused date. Completion exists only after all pieces with the exact remaining
percentage total are placed. Zero-work items have no fabricated completion day.

`SessionAction(item_id, session_index, scheduled_date)` identifies the next
zero-based session. `state.place(action)` creates a new state, checking piece
identity, ranks, today/release, known prerequisite completion, and first-session
anchor. State replay requires prerequisites before dependents and an item's
sessions in nondecreasing date order. Same-day split sessions are permitted by
the validator; distinct/consecutive split dates are EarliestFeasible policy,
not a new common hard invariant. `to_plan()` returns a disposable SchedulePlan.
Search can branch from any retained state or rebuild from ordered allocations;
C2 does not implement removal, relocation, or a search algorithm.

## Readiness and candidates

`readiness(problem, state, item_id)` returns `Readiness`: the maximum of today,
release (or today), and each direct prerequisite's completion plus one day.
Missing prerequisites produce a None lower bound and explicit missing IDs.
An unrepresentable next calendar day produces None with calendar_exhausted=True,
never a sentinel date. Anchors do not enter readiness.

`session_candidates(state, item_id, horizon=None)` enumerates every next-session
date in ascending order. Each immutable `SessionCandidate` contains an action,
bucket, usage_before, capacity, overload_allowed, and derived excess_after.
There are no scores or preferred candidates. Candidates describe one session,
not a guarantee that the whole workload can be completed within the window.

- Lower bound is readiness and the last placed session date, if any.
- First anchored session has exactly the anchor date. A readiness conflict yields
  no candidate; an anchor beyond due is preserved, with lateness left visible.
  Follow-up sessions may occur on or after the first session.
- When lower ≤ due, due is an inclusive automatic upper bound, even if all
  dates are overloaded. No late alternatives are added for capacity pressure.
- When lower > due, an explicit horizon is required for a bounded late fallback.
  The validator classifies deadline lateness as soft; C2 does not invent a
  fallback horizon or repair contradictory canonical constraints.
- Undated work always requires an explicit inclusive horizon, including anchors.
  Any supplied horizon bounds enumeration; a horizon before the lower bound
  yields no candidates. No unbounded walk or date.max sentinel is used.
- Missing prerequisite completion or no remaining pieces yields no candidates.
- Every date in the window remains available despite capacity pressure. This
  permits controlled pre-deadline overload and future algorithms' own choices.
  Allowed overload dates are annotated, not given an artificial larger capacity.
  Zero capacity still permits soft overload. Missing capacity raises ValueError
  for candidate construction, matching the baseline's automatic construction
  behavior. State itself can record such usage, as the validator allows it.
  The baseline's anchored path bypasses capacity lookup and remains unchanged.

## Independent objective components

Every component is independently callable, minimized, and supplied explicit
immutable configuration. No total-cost function or default weight vector exists.
`PowerCost(weight, exponent)` requires finite nonnegative weight and positive
finite exponent. Zero weights short-circuit before costly/undefined inputs.

| Function / configuration | Definition |
|---|---|
| `deadline_risk(item, completion, DeadlineRisk(cost, buffer_days))` | weight × max(0, buffer_days − signed completion slack)^exponent; no due means zero. Buffer is finite, nonnegative and explicit. |
| `priority_postponement(item, start, ready, PriorityPostponement(cost, multipliers, unpositioned_multiplier))` | weight × position multiplier × max(0, start − ready in days)^exponent. Explicit immutable mapping must give smaller positions at least as much weight. Missing positioned keys raise KeyError; no rank scale is invented. |
| `capacity_overload(usage, capacity, allowed=..., config=OverloadCost(cost, exempt_allowed_dates))` | weight × max(0, usage − capacity)^exponent for one bucket/day. Explicit exemption policy; missing capacity raises unless disabled/exempt. Exponent > 1 supports convex experiments. |
| `movement(item, start, MovementCost(fixed_weight, distance))` | Zero without an existing date or when unchanged; otherwise fixed_weight + distance.weight × absolute day distance^distance.exponent. Earlier and later movement are symmetric. |
| `timing_preference(start, target, PowerCost)` | weight × absolute day distance from explicit target^exponent. Target=readiness expresses earlier preference; other targets express other timing preferences. |

These are configurable experimental shapes, not canonical quality definitions.
Movement/priority/timing apply once per item start; risk applies to completion;
overload applies once per bucket/day. Callers computing action deltas subtract
old cell cost from new cell cost, rather than double-counting entire cells.
Objective functions can describe bad dates but cannot authorize them. State
checks hard placement constraints; candidates additionally enforce the automatic
deadline window policy; the shared validator remains authoritative for complete
plans. PerformanceVector is independent and is never a construction score.

## Deliberate limits and baseline preservation

EarliestFeasible shares effective-bucket mechanics but retains a private legacy
decomposition helper, including its historical tiny-work rounding behavior.
C2 conservation repairs therefore do not change baseline output. Its readiness,
mutable local accounting, date selection,
anchored consecutive-day policy, conflicts and diagnostics remain untouched:
replacing these with stricter partial-state checks would change its handling of
canonical conflicts. A pre-extraction full-plan/error fingerprint covers 120
varied cases in addition to the unchanged baseline tests.

The supplied scheduling_domain_contract.md is empty. Current domain/validator/
baseline behavior and performance_metrics.md take precedence over older design
spec statements proposing different duration/split semantics. Horizon fallback,
all-overload candidate availability and configurable objective shapes above are
explicit C2 API choices, not claims of an optimal scheduling policy.

C2 does not determine the winning objective, weights, constructor, improvement
method, or production scheduler. It implements no optimizer, parameter search,
algorithm selection, experiment database, learning, or production integration.
