# C4.1 local-search foundation

C4.1 performs **NO search/acceptance/improvement itself**. It supplies complete
states, generic transformations, finite neighbourhoods and objective scoring.
The append-only C2 `ScheduleState.place()` remains unchanged: construction and
complete-plan editing have different invariants.

## State and normalization

`SessionPlacement(item_id: int, session_index: int, scheduled_date: date)` and
`SearchState(problem: ScheduleProblem, placements: tuple[SessionPlacement, ...])`
are frozen, slotted dataclasses. The problem is shared. Placements are normalized
by `(item_id, session_index)`, with each positive `session_pieces(item)` represented
exactly once. Percentages and execution ranks are not decision variables.

`SearchState.from_plan(problem, plan)` first checks the frozen validator, then
sorts each item's rows by `(scheduled_date, execution_rank)`. Row k must have
exactly the percentage of canonical piece k. Input tuple order is irrelevant.
`to_plan()` derives percentages afresh, orders by
`(scheduled_date, item_id, session_index)`, and assigns ranks 1..N on each date.
Constructor conflicts/diagnostics are not copied into this new disposable plan.
Equivalent valid rank permutations normalize to the same state, provided they
preserve the canonical piece order within an item on a date.

Construction rejects unknown, duplicate, missing or extra identities, dates
before today/release, decreasing within-item dates, first-session anchor mismatch,
and violated completion-based dependency precedence. Same-day sessions of one
item are legal. Every explicit edge with sessions on both ends requires
`completion(prerequisite) < start(dependent)`; checking explicit edges covers
chains and fan-in without inventing edges. Zero-work items have no placements,
no start/completion, and no item objective contribution; edges without sessions
on both ends are ignored, matching the validator's empty-row semantics.

Entry into search requires feasible hard constraints. `from_plan` rejects both
validator violations and canonical infeasibilities, with distinct error messages.
This deliberately restricts the search domain; it does **not** reclassify canonical
infeasibilities as validator violations or attempt repair. In particular, an
anchor-related precedence conflict remains an infeasibility in the frozen
validator, but is not an eligible search input.

Lateness and capacity overload (including allowed overload) remain legal. Missing
capacity does not invalidate a state. Exported states have no validator violations.
Equality includes the problem and normalized placements. Hashing includes the
problem's immutable contents, with sorted capacity/date entries; hashes follow
Python's usual process-local hash convention, not a persistent cross-process ID.
`placements_by_item` returns a fresh read-only mapping of tuples. `start`,
`completion`, `session_date`, and `usage(day, bucket)` are derived helpers with
no mutable caches. Missing start/completion/session lookups raise `KeyError`.

## Moves and finite enumeration

- `RelocateSession(item_id, session_index, to_date)` changes one date.
- `SwapSessions(first_item_id, first_session_index, second_item_id,
  second_session_index)` exchanges two dates, preserving identities.
- `ShiftItem(item_id, delta_days)` shifts all item sessions by an integral signed
  calendar-day offset, preserving every gap.

`apply_move(state, move)` returns a new state or `None` for illegal, unknown,
calendar-overflow, or no-op transformations. It never repairs or mutates inputs.
An anchor fixes only session 0: later sessions can move. Nonzero shifts of an
anchored item are therefore illegal. Swaps must preserve every hard constraint.

`NeighbourhoodConfig(horizon_days: int,
max_relocation_distance_days: int | None = None)` is frozen. The horizon is
mandatory and nonnegative; the optional relocation distance is also nonnegative.
The inclusive upper bound is `today + horizon_days`; calendar overflow raises
`ValueError`, even for an empty neighbourhood. There is no silent extension.
Source dates may exceed the horizon. Only changed destination dates are bounded.

- Relocate: session identities ascending, then destination ascending in
  `[today, horizon]`, intersected with `[current-distance, current+distance]`
  when distance is set. Hard-illegal results are filtered through `apply_move`.
- Swap: lexicographic unordered identity pairs, each considered once. Both dates
  must be within the horizon, so neither generated destination exceeds it.
- Shift: item ID ascending, then signed delta ascending in
  `[today-start(item), horizon-completion(item)]`; zero is omitted. The relocation
  distance parameter applies only to relocation, not shift or swap.
- `all_moves`: relocate, then swap, then shift, with no objective filtering.

Each generator returns a tuple. Normalized placement tuples identify resulting
states within the shared problem; a membership set removes no-ops and duplicates,
but its iteration order is never exposed. The first move reaching a state wins,
including across move families in `all_moves`. Atomic shifts often duplicate
relocations and are removed there.

## Whole-plan objective

`PlanObjectiveConfig(deadline, priority, overload, movement, timing)` requires all
five existing C2 primitive configurations explicitly. No preferred weights exist.
`PlanObjective` has these five component fields and a computed `total`.

For every item with sessions, actual readiness is:

```
max(today, release_date or today,
    completion(p) + 1 day for each direct prerequisite p with sessions)
```

The whole-plan cost is:

```
deadline = sum(deadline_risk(item, actual_completion, config.deadline))
priority = sum(priority_postponement(item, actual_start, actual_readiness, config.priority))
movement = sum(movement(item, actual_start, config.movement))
timing   = sum(timing_preference(actual_start, actual_readiness, config.timing))
overload = sum(capacity_overload(final_cell_usage, cell_capacity,
               allowed=day in overload_dates, config=config.overload))
total    = deadline + priority + overload + movement + timing
```

Item costs occur once per item; overload occurs once per occupied
`(day, effective_bucket(item))` cell, counting sessions rather than percentages.
Allowed-date exemption and zero-weight short circuits come directly from C2.
Undefined capacity raises when the overload primitive requires it; disabled or
exempt overload does not introduce a capacity requirement. All components and the
total must be finite; arithmetic overflow raises `ValueError`.

`score_state(state, config)` accepts a validated complete SearchState.
`score_plan(problem, plan, config)` first performs strict state conversion.
`objective_delta(state, neighbour, config)` requires equal problems and returns
`score(neighbour).total - score(state).total`: negative improves, zero ties,
positive worsens. It currently recomputes both whole-plan scores.

C3 `candidate_cost` estimates consequences during construction, including predicted
completion and incremental overload. C4 scores actual complete plans and total
cell overload. C1 `PerformanceVector` independently evaluates algorithms. Search
imports neither C3 candidate scoring nor the performance evaluator or Django.

## Complexity and public API

Let S be sessions, I items, E dependency edges, H inclusive horizon length,
B capacity buckets, and M emitted neighbours. State validation is
O(S log S + I + E); conversion/export includes sorting and the frozen validator.
Hashing also visits the problem contents (including sorted capacities/overload
dates). Helpers rebuild indexes in O(S + I) at worst rather than caching them.

A trial move costs O(S log S + I + E). Relocation considers O(SH) candidates;
swap considers O(S²) pairs; shift considers at most O(IH) candidates. Multiply
these candidate counts by trial cost for current worst-case enumeration time.
Deduplication can use O(MS) memory. `all_moves` reapplies legal moves for global
deduplication, adding the same per-trial order of work. Whole-plan scoring is
O(I + E + S log S), including sorted occupied cells. Delta costs two such scores.
No trial deep-copies ScheduleProblem. Later pruning or incremental scoring can
replace internals without changing these APIs.

`arena.search` exports exactly:

```
SearchState, SessionPlacement,
RelocateSession, SwapSessions, ShiftItem, apply_move,
NeighbourhoodConfig, relocate_session_moves, swap_session_moves,
shift_item_moves, all_moves,
PlanObjectiveConfig, PlanObjective, score_plan, score_state, objective_delta
```
