# C5 finite-horizon exact oracle

`arena.oracle` exports `ExactOracleConfig`, `ExactOracleResult`, `ExactOracle`,
`OptimalityGap`, and `gap_to_optimum`. It uses no external solver. All four
dataclasses are frozen and slotted. Supply an explicit C4 `PlanObjectiveConfig`
and nonnegative integer `horizon_days`, `max_sessions`, and `max_nodes` (booleans
and floats are rejected).

```python
from arena.oracle import ExactOracle, ExactOracleConfig, gap_to_optimum

# problem and objective_config are the frozen scheduling input and C4 weights.
oracle = ExactOracle(ExactOracleConfig(objective_config, 2, 6, 10000))
result = oracle.solve(problem)
if result.status == 'optimal':
    gap = gap_to_optimum(result, heuristic_plan)
```

## Domain and exactness

The domain is inclusive `[problem.today, problem.today + horizon_days]`.
Calendar overflow raises `ValueError` at solve entry, including for empty
problems and zero node budgets. Canonical positive session pieces are calculated
once for enumeration. If their total exceeds `max_sessions`, solving raises
`ValueError("Instance exceeds max_sessions")`: this is an unsupported-size
request, never evidence of infeasibility.

Decisions follow deterministic item topological order, then session index.
Depth-first recursion assigns every legal candidate date in ascending order:

- Every session is on or after today and the item's release date.
- Sessions within an item have nondecreasing dates; same-day pieces are legal.
- The first session matches an anchor when present. Later sessions remain free.
- A dependent starts strictly after the final session of every direct
  prerequisite that has pieces. Edges with zero-work endpoints impose no
  placement constraint, matching C4 and the validator.
- Every canonical `(item_id, session_index)` is assigned exactly once.

No other pruning occurs. Due dates and capacity never bound the candidates.
Late dates, overload, and capacity zero remain hard-legal; C4 scores their soft
costs. Allowed overload dates use the configured C4 exemption semantics.
Missing capacity errors propagate whenever scoring requires capacity; disabled
or exempt overload retains C4's short circuit. The enumeration deliberately
does not use C2 `session_candidates`, which can exclude dates after a reachable
due date. Integer day offsets safely include `date.max`; a prerequisite ending
on `date.max` leaves no child date for a dependent.

Every complete assignment becomes a `SearchState` and is evaluated only through
`score_state`. Smaller total wins; exactly equal floating-point totals use the
lexicographically smallest dates in canonical `(item_id, session_index)` order.
No tolerance, surrogate objective, C3 candidate cost, or independent C1 evaluator
enters optimization. Before returning an incumbent, its exported plan must pass
`validate_plan` with neither violations nor infeasibilities and round-trip via
`SearchState.from_plan`. Soft violations are permitted.

## Node budget and proof

Each visited partial assignment counts as one node, including the root and
complete leaves. `leaves_evaluated` counts complete assignments scored. A visit
attempt when the node count already equals `max_nodes` truncates traversal.
Merely reaching the limit does not truncate if traversal is already complete.

- `optimal`: exhaustive traversal found a feasible state. Its objective total
  is the `proven_lower_bound`, and `plan` exports the best state.
- `infeasible`: exhaustive traversal found no feasible leaf. State, objective,
  plan, and bound are `None`. This proves infeasibility **within this explicit
  horizon**, not global or canonical infeasibility.
- `node_limit`: an additional visit was needed. The best feasible incumbent is
  returned if found; otherwise state/objective/plan are `None`. The bound is
  always `None`, even when the incumbent happens to be optimal.

`max_nodes=0` returns `node_limit` with zero visits. An empty problem (or all
zero-work items) has one empty feasible leaf of cost zero when the budget is at
least one. `elapsed_seconds` uses `perf_counter` and includes final validation;
elapsed time never acts as a cutoff. Scoring exceptions propagate as errors.

## Hand-computed examples

For two atomic items, two dates (days 0 and 1), capacity 1, quadratic timing
weight 1, quadratic overload weight 10, and other weights zero:

| Item 1 day | Item 2 day | Timing | Overload | Total |
| --- | --- | --- | --- | --- |
| 0 | 0 | 0 | 10 | 10 |
| 0 | 1 | 1 | 0 | 1 |
| 1 | 0 | 1 | 0 | 1 |
| 1 | 1 | 2 | 10 | 12 |

The optimum is 1 at `(0, 1)` after the canonical tie-break, regardless of item
input order. Exhaustion visits 7 nodes and evaluates 4 leaves. Budget 3 returns
`node_limit` with the first leaf's cost 10; budget 7 proves cost 1 optimal.

A single item due on day 0 but previously scheduled on day 2, with squared
lateness weight 1 (zero buffer) and squared movement weight 10, costs 40, 11,
and 4 on days 0, 1, and 2. Day 2 is the optimum when the horizon includes it,
despite the existence of an on-time choice.

## Certified gaps and scope

`gap_to_optimum(result, heuristic_plan)` requires status `optimal` and a state
and objective. It strictly converts the heuristic through `SearchState.from_plan`,
rejects dates beyond the same horizon, and scores with the same C4 configuration.
The absolute gap is `heuristic.total - optimum.total`; a negative result raises
`ValueError` without clamping. The relative gap divides the absolute gap by the
**optimum**, not the heuristic cost. With zero optimum it is `0.0` for zero
absolute gap and `None` for a positive absolute gap. Infeasible and truncated
results cannot certify gaps, including truncated results with incumbents.

With S sessions and H inclusive dates, there are up to H^S leaves and
`1 + H + ... + H^S` visited nodes before considering hard constraints. Every
leaf additionally pays C4 state-validation and whole-plan-scoring costs. Search
keeps only the current assignment, completion bookkeeping, and best state; its
recursion depth is S. Worst-case time is exponential, and Python's recursion
and memory limits still apply. This is a tiny-instance oracle, not a production
scheduler. Session and node limits are explicit safeguards, not a scalability
claim.

The certificate concerns only the frozen C4 objective, weights, and finite
domain. Independent C1 schedule-quality measurements remain separate and may
rank schedules differently. This module neither changes C1–C4 or production ARC
nor implements the C6 paired experiment runner.
