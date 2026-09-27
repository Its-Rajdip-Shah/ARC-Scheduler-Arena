# C4.2 deterministic hill climbing

C4.2 is the first complete-plan improvement engine. It composes with any
constructor that supplies a complete input accepted by frozen C4.1:

```python
from arena.search import HillClimber, HillClimbConfig, ImprovementStrategy

plan = constructor.solve(problem)
config = HillClimbConfig(
    objective=objective_config,
    neighbourhood=neighbourhood_config,
    strategy=ImprovementStrategy.BEST,
    max_iterations=None,
    max_evaluations=None,
)
result = HillClimber(config).improve_plan(problem, plan)
improved_plan = result.final_state.to_plan()
```

The caller supplies both objective and neighbourhood configurations explicitly.
HillClimber neither imports nor owns a constructor. `improve_state(initial)`
accepts a complete SearchState directly; `improve_plan(problem, plan)` first
performs strict `SearchState.from_plan` conversion. Frozen C4.1 hard-legality,
canonical-infeasibility rejection, normalization, horizon, and soft-cost semantics
remain unchanged. Lateness and capacity overload can remain in accepted plans.

## Strategies and deterministic decisions

`ImprovementStrategy.FIRST = "first"` and `BEST = "best"` both minimize
`PlanObjective.total`, accepting only `neighbour.total < current.total`.
There is no epsilon, sideways move, or worsening acceptance.

Each scan obtains `all_moves(current, neighbourhood)` in its exact C4.1 order.
Every considered move is applied with frozen `apply_move`, then its neighbour is
scored once with `score_state`. FIRST accepts the first strict improvement and
immediately ends the scan. BEST completes the scan and selects the lowest total
among strict improvements. Equal best totals retain the first encountered move;
objective components introduce no tie breakers. After acceptance, the next scan
regenerates the neighbourhood from the new state.

## Budgets and counting

`HillClimbConfig(objective, neighbourhood, strategy, max_iterations=None,
max_evaluations=None)` is frozen and slotted. Strategy must be an enum instance;
strings are not coerced. Each limit must be None or an exact nonnegative int;
bools are rejected. None means unlimited by that measure. Both may be None:
the finite reachable schedule space and strict decrease ensure termination.

One iteration is one neighbourhood scan initiated, including an empty scan.
One evaluation is one neighbour scored by the engine. Initial scoring occurs
exactly once and does not consume evaluation budget. The accepted candidate's
already-computed objective becomes current; it is not immediately rescored.
`objective_delta` is not used in the loop.

- Zero iterations: initial score only; no scan; `iteration_budget`.
- Zero evaluations: initial score only; no scan; `evaluation_budget`.
- Limits are checked before a new scan, iteration first. If both are exhausted
  simultaneously, including both zero, `iteration_budget` takes precedence.
- FIRST stops evaluating immediately upon acceptance. It may accept with the
  final available evaluation. A prefix with no improvement ends in
  `evaluation_budget` if more candidates remain.
- BEST never accepts a candidate from a truncated scan. Earlier accepted states
  are retained, but the tentative prefix winner is discarded.
- If the last permitted evaluation scores the final neighbour, the scan is
  complete: BEST may accept its winner. Either strategy reports `local_optimum`
  if a complete scan finds no strict improvement, even at an exact budget limit.
- After an accepted move exhausts a limit, the engine returns the appropriate
  budget reason without generating a speculative next neighbourhood.
- An empty neighbourhood reached by an initiated scan is `local_optimum`.

Normal termination strings are exactly `local_optimum`, `iteration_budget`, and
`evaluation_budget`. Input/scoring/calendar errors propagate; they are not
reported as a normal termination. An unexpected illegal move from `all_moves`
raises RuntimeError as a frozen-contract tripwire.

C4.1 eagerly constructs its move tuple, including legality and deduplication
work. Evaluation budgets bound neighbour objective calls, not that construction
cost. FIRST avoids later scoring but still pays for the eager tuple.

## Result and history

Frozen, slotted `HillClimbResult` holds `initial_state`, `final_state`,
`initial_objective`, `final_objective`, `iterations`, `evaluations`,
`accepted_moves`, `termination_reason`, `objective_history`, and
`accepted_moves_history`. Direct state input is preserved by object identity.

`objective_history` is an immutable tuple containing the initial total followed
by every accepted total, strictly decreasing after index zero. Its length is
`accepted_moves + 1`; the move-history tuple has length `accepted_moves`.
Each successful iteration accepts exactly one move, so `accepted_moves <=
iterations`. Rejected neighbours and candidate scores are not retained in the
result. `improved` compares final total strictly below initial total;
`total_improvement = initial total - final total`, positive for improvement.
The output plan is obtained through `result.final_state.to_plan()`.

## Cost, independence, and reuse

For K scans, E neighbour evaluations, C4.1 neighbourhood-generation costs G_k,
move-application cost A, and whole-plan scoring cost Q, runtime is
`O(sum(G_k) + E*(A + Q) + Q)`. A and Q are each roughly
`O(S log S + I + dependency_edges)` for S sessions and I items. BEST scores the
whole neighbourhood per complete scan; FIRST may score a shorter prefix.
Beyond C4.1's eager enumeration/deduplication memory, the engine keeps a constant
number of states/objectives and O(accepted_moves) history. It shares the immutable
problem and adds no incremental caches or parallel/random search.

The engine optimizes the explicit C4 objective and never imports the independent
performance evaluator or Django. Constructor choice, objective choice, and search
policy remain independently composable. The immutable states, generic moves,
scoring, and result accounting provide reusable infrastructure for later
metaheuristics; none are implemented here. Hill climbing can stop at a local
optimum and is not claimed to be the winning ARC algorithm.
