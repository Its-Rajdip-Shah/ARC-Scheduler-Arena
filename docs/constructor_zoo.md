# C3 configurable greedy constructors

C3 is construction only. It adds no search, experiment runner, evaluator ranking,
parameter optimisation, or canonical-state changes. EarliestFeasible remains a
separate frozen historical baseline. C3 does **not** establish winning weights.

## Public API and configuration

Import `PressureGreedy`, `AggressiveEarlierGreedy`, `StableRiskGreedy`,
`HybridCostGreedy`, `GreedyObjectiveConfig`, `GreedyConstructor`, and
`ItemSelectionPolicy` from `arena.algorithms`. Instantiate a family with a required
`GreedyObjectiveConfig`, then call `solve(problem)` to obtain a `SchedulePlan`.
All imports are pure Python and independent of Django and evaluation.

The frozen config requires C2's `DeadlineRisk`, `PriorityPostponement`,
`OverloadCost`, `MovementCost`, `PowerCost` (timing), and integer `horizon_days`.
No weight defaults are supplied. All C2 parameters remain exposed: each power
weight/exponent, deadline buffer days, priority-position multiplier mapping and
unpositioned multiplier, allowed-overload exemption, fixed movement weight and
movement distance weight/exponent. Use `dataclasses.replace` for experiments.

## Shared loop and family distinctions

Start with `ScheduleState(problem)`. In stable item-ID order, inspect unfinished
positive-piece items, check C2 readiness, enumerate C2 next-session candidates,
and score and sort their dates. Select one item by its explicit policy, commit
exactly one candidate using `state.place(action)`, and repeat from scratch.
Dependencies become ready only through C2 completion. No selected item receives
its remaining sessions wholesale. Finish with `state.to_plan()` plus diagnostics.

| Family | Item policy | Intended explicit configuration |
| --- | --- | --- |
| PressureGreedy | Pressure/flexibility | Early placement with overload/risk penalties as desired |
| AggressiveEarlierGreedy | Regret | Proactive timing, potentially weak or zero movement |
| StableRiskGreedy | Regret | Movement, completion risk, and overload; timing as desired |
| HybridCostGreedy | Regret | General trade-off across all five dimensions |

The three cost families deliberately share mechanics and accept identical config
shapes. Their class identities describe experimental policy families, not hidden
coefficients: identical configs yield identical allocations. Different explicit
configs supply the behavioural distinction. The tested single-item example has
an existing date at today + 4: timing/movement weights 10/0 choose today; 0/10
preserve day 4; 1/1 choose day 2 (both distance powers are 2).
`GreedyConstructor` exposes the common engine; its class-level `item_policy`
selects the reusable `ItemSelectionPolicy` enum (regret by default). Named
families set the policy at class level rather than duplicating solve loops.

## Exact ordering

For an eligible item let `n` be the number of C2 next-session date candidates,
`r` the remaining piece count, `h` the inclusive horizon, and `ready` C2's
readiness lower bound. Minimise the pressure tuple:

`(n - r, min(due or h, h), ready, (priority is None, priority or 0), item_id)`.

This is an approximate opportunity deficit, not a hard claim that each piece
needs its own date. It accounts for anchors and previous sessions through the
candidate count. Same-day pieces and overload remain C2-legal. Later releases
can reduce opportunity; readiness also breaks equal-window ties. Smaller
priority positions win after the temporal dimensions; unpositioned items follow.

Regret first sorts each item's candidates by the candidate key below. With two
or more candidates, `regret = second.total - best.total`; with one candidate,
`forced = True` and the numeric regret placeholder is zero. Minimise:

`(not forced, -regret, *pressure_tuple)`.

Thus all forced decisions precede unforced decisions, then high regret precedes
low regret. No infinity or NaN sentinel is used. Scores must be finite.

Candidate order is:

`(total, deadline_component, movement_component, date, priority_tuple, item_id)`.

## Objective and completion estimate

`total = deadline_risk(item, predicted_completion) + priority_postponement(item,
start, readiness) + overload_delta + movement(item, start) +
timing_preference(start, readiness)`.

Priority, movement, and timing are item-start costs: they are charged only for
session index zero. Readiness is the explicit timing target; anchors do not
change that target. Deadline risk is the current conditional completion estimate
at every decision, not a sum over already committed session risks or a final-plan
aggregate objective. Zero-weight primitives short-circuit their unused inputs.
Missing capacity definitions remain C2 errors even if overload scoring is off.

For enabled risk on a dated item, place the candidate in a temporary persistent
C2 state. For each remaining piece, enumerate C2 candidates and select earliest
normal-capacity or allowed-overload date; when none exists select earliest soft
overload. Continue until C2 records item completion. No tentative placements are
committed or reserved in the real state. This capacity-first earliest continuation
can complete later than the first session. It is an optimistic estimate conditional
on current usage, not a guarantee against future contention and not an exact
optimiser. Because capacity is soft and C2 permits same-day splits, a full window
may still complete through overload. It never invents distinct-day feasibility.

`overload_delta = capacity_overload(usage_before + 1, capacity, allowed)
- capacity_overload(usage_before, capacity, allowed)`.

Both calls use the same configured power and exemption. For example, weight 5,
exponent 2, capacity zero: the first session costs 5 and the second increment
costs 15, rather than charging the total cell cost 20 again.

## Horizon, diagnostics, and limits

`horizon = problem.today + timedelta(days=horizon_days)` is inclusive and bounds
all C2 enumeration, including anchors and dated work. Noninteger/negative days
and calendar overflow raise ValueError; no silent horizon extension occurs.
C2 retains its due-date upper bound when readiness is not already late, and uses
the explicit horizon for undated work and late fallback.

When no legal progress remains, return the partial proposal, with stable item-ID
conflicts distinguishing `no_candidate_within_horizon`, `blocked_prerequisites`,
`anchor_before_readiness`, and `readiness_exceeds_calendar`. Diagnostics identify
constructor, item policy, horizon days, and complete/partial status. Missing work
remains validator-invalid; diagnostics do not waive completeness requirements.
Zero-piece items require no allocation and receive no fabricated completion date.

The tests include an anchored three-piece A and a later-released constrained B:
A's first session is forced, then regret selects B before A's continuation. A
wholesale A placement would consume B's normal-capacity dates. Tests also freeze
a deterministic four-problem/four-family corpus without asserting quality ranks.

This straightforward implementation repeatedly enumerates dates and replays
persistent state for completion estimates. Large horizons/workloads may be
expensive; runtime optimisation and richer traces remain later work.
