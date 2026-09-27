# C4.3–C4.5 complete-plan search

All engines accept complete hard-legal `SearchState` inputs through
`improve_state(initial)`, or strictly convert constructor output through
`improve_plan(problem, plan)`. Results preserve the supplied initial state's
identity. Configs, results, and engines are frozen slotted dataclasses.

These algorithms optimise the explicitly configured C2-derived plan objective.
They do **not** prove that objective is the final human-preferred scheduler
quality function. Arena evaluation remains independent. Search never imports
Django or the performance evaluator, adds hidden weights, repairs states,
changes constructors/problems, or extends the configured horizon.

## Variable neighbourhood descent and search

`VariableNeighbourhoodMode` distinguishes `VND = "vnd"` and `VNS = "vns"`.
`VariableNeighbourhoodConfig`, `VariableNeighbourhoodResult`, and
`VariableNeighbourhoodSearch` are the public types. The fixed family order is
relocate, swap, shift. Frozen C4.1 `all_moves()` is unchanged.

VND completely scans one family and accepts its strictly lowest improving
neighbour. Exact ties retain the first generator occurrence. Improvement resets
the family index to relocate; otherwise the index advances. Three consecutive
unsuccessful families establish `local_optimum`. An evaluation-truncated scan
commits no tentative improvement. The objective history begins with the initial
score and strictly decreases once per accepted move; the move history replays
to the final state.

VNS uses a local `random.Random(seed)` to select exactly one uniform shake from
the current family's complete tuple. The shake and deterministic best-improvement
descent over `all_moves()` form a temporary excursion; intermediate states may
worsen. Each descent scan selects the strictly lowest improving total, retaining
the first generator occurrence on exact ties. Only a complete non-improving scan
(including an empty scan) proves the trial state locally optimal.

Only a proven local optimum strictly better than the incumbent is accepted,
resetting the family index to relocate. Equal or worse excursions are discarded
and the family index advances. Empty families advance without a shake. Reaching
the end of the family sequence terminates with `local_optimum`.

`objective_history` contains the initial total and each accepted incumbent total,
so it is strictly decreasing. `accepted_moves_history` is the flattened replay
log of every shake and descent move belonging to accepted excursions; replay
from `initial_state` reproduces `final_state`. Rejected excursions enter neither
history. `accepted_moves == len(accepted_moves_history)`, while
`accepted_excursions == len(objective_history) - 1` counts accepted basin
replacements. VNS may accept several moves per excursion. For VND each accepted
move is one excursion, so `accepted_moves == accepted_excursions`.

## Tabu Search

`TabuConfig`, `TabuResult`, and `TabuSearch` implement a deterministic walk.
Tabu attributes are canonical `SearchState.placements` tuples, never raw moves.
The initial state expires at `tabu_tenure`. After accepting a state at one-based
iteration `t`, its expiration is `t + tabu_tenure`; a state is tabu precisely
when its recorded expiration is at least the candidate iteration.

Every complete scan scores all neighbours. Tabu candidates require strict
aspiration: their objective must be below the global best-ever total. Equality
does not qualify. Admissible candidates are ordered by total then generator
index. The winner may worsen the current objective, intentionally allowing
escape from local optima. A truncated scan accepts no tentative winner.

`final_state` and `final_objective` return best-ever; `last_state` and
`last_objective` report the walk's endpoint. Walk history includes every accepted
move and may rise or tie; best history records only strict improvements.
With a static objective, a previously visited tabu state cannot strictly improve
best-ever, but the aspiration predicate remains explicitly implemented.
Unbounded Tabu Search can cycle; supply a finite budget when bounded execution
is required.

## Simulated Annealing

`SimulatedAnnealingConfig`, `SimulatedAnnealingResult`, and `SimulatedAnnealing`
use a private local `random.Random(seed)` and geometric cooling. Each attempt
uniformly selects one C4.1 move. For `delta = neighbour.total - current.total`,
nonpositive deltas are accepted without drawing a probability random number.
Positive deltas are accepted exactly when `rng.random() < exp(-delta / T)`.
There is no probability clamp or additional objective.

After every attempted transition, accepted or rejected, `T *= cooling_rate`
once. The floor is strict: stop when `T < minimum_temperature`.
Temperatures are finite and positive, the minimum cannot exceed the initial
value, and the finite cooling rate lies strictly between zero and one.
Booleans are rejected. Worsening acceptance deliberately enables exploration.
Best-ever and last-state outputs are separate, as in Tabu Search.

Only accepted attempts enter walk/move history. Thus
`len(walk_objective_history) == accepted_moves + 1`,
`len(accepted_moves_history) == accepted_moves`, and
`accepted_moves + rejected_moves == iterations == evaluations`.
Best history contains only strict improvements.

## Budgets, determinism, and contract failures

Budgets are `None` or exact nonnegative integers; booleans are invalid. Seeds
are exact integers, also excluding booleans. Initial scoring occurs once and
never counts as an evaluation. Each neighbour score is exactly one evaluation;
accepted candidates reuse their computed scores. No incremental caches exist.
Identical input/config/seed produces identical decisions; module-global random
state is never used or mutated.

For VND/Tabu, one iteration is an initiated scan, including an empty scan.
At scan boundaries iteration limits precede evaluation limits. Evaluation limits
also apply before each neighbour score. Consuming the last evaluation on the
last neighbour completes the scan and permits its winner; incomplete best scans
discard tentative winners. Completion may establish normal termination at an
exact budget boundary before another loop starts.

VNS counts one iteration for each initiated family attempt (including an empty
family) and each initiated local-descent scan. A shake consumes one evaluation;
descent consumes one per scored neighbour. Before every family attempt and
descent scan, iteration limits precede evaluation limits. Evaluation limits are
also enforced before scoring the shake and each descent neighbour.

If a budget prevents a required descent scan or interrupts one, the entire
excursion is discarded, including completed internal improving moves. The prior
incumbent and accepted histories remain intact; all consumed iterations and
evaluations remain counted. A complete non-improving scan finishing exactly on
the final evaluation does prove local optimality and permits normal excursion
acceptance or rejection. An improving scan finishing at that boundary still
requires another scan to prove local optimality; without budget, its whole
excursion is discarded.

SA checks iteration budget, evaluation budget, temperature floor, then
neighbourhood emptiness, in that exact order. An iteration is an attempted
neighbour; an empty neighbourhood consumes none. No move tuple is generated
after an exhausted budget. Both zero budgets therefore return `iteration_budget`.

Termination reasons:

- VND/VNS: `local_optimum`, `iteration_budget`, `evaluation_budget`.
- Tabu: `no_admissible_move`, `iteration_budget`, `evaluation_budget`.
- SA: `no_neighbour`, `temperature_floor`, `iteration_budget`, `evaluation_budget`.

A generator move rejected by `apply_move()` raises `RuntimeError` as an internal
C4.1 contract violation. Other validation/scoring errors propagate.

## Current complexity

For scan-generation costs `G_k`, move application cost `A`, whole-plan scoring
cost `Q`, and `E` evaluations, runtime is
`O(sum(G_k) + E*(A + Q) + Q)`. Application/scoring each cost roughly
`O(S log S + I + dependency_edges)`. Relocation considers `O(SH)` candidates,
swap `O(S²)`, and shift `O(IH)` before legality/deduplication. C4.1 eagerly
materialises move tuples, so evaluation limits do not bound enumeration cost.
SA scores only one candidate per tuple; VND, Tabu, and best descent scan full
tuples unless truncated. Move/objective histories require linear space in
accepted moves, plus the temporary VNS excursion replay log. Tabu additionally
stores visited placement tuples,
`O(VS)` for `V` distinct visited states; expired entries are ignored lazily.

## C4.6–C4.7 large neighbourhood search

`LargeNeighbourhoodSearch` performs bounded strict-improvement destroy/repair;
`AdaptiveLargeNeighbourhoodSearch` adapts operator weights from objective feedback
and accepts a bounded Metropolis walk while preserving its best-ever state.
Both require an initial complete plan, an explicit objective and a mandatory
iteration budget. See [Large neighbourhood search](large_neighbourhood.md) for
the private partial-state boundary, operators, date rules, budgets, adaptation,
result accounting and replacement-placement replay.
