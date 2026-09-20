# ARC Master State-Transition Catalogue

This is the consolidated lifecycle catalogue from the state-transition matrix analysis. Every transition must pass invariant validation, reconciliation and (when planning-relevant) rescheduling.

Legend:
- **Canonical**: persisted user/domain fact changes.
- **Derived**: recomputed consequence.
- **Schedule**: disposable proposal recomputed.
- **Confirm**: user confirmation/resolution required before commit.

## 1. Creation

| ID | Source | Action | Destination / consequences |
|---|---|---|---|
| C1 | no task | create root task | active task; dates/priority/duration stored; reconcile frontier |
| C2 | active parent | create child | child form defaults release/deadline from parent; committed values become child's own; parent may leaf->structural |
| C3 | parent default dates | user edits child release/deadline before create | explicit divergent child dates allowed; warn when risky |
| C4 | anchored executable parent | create required child | parent anchor becomes suspended; child inherits anchor date; parent becomes structural; reschedule |
| C5 | completed parent | create unfinished required child | parent/affected structural completion reopens; dependency consequences resolved |
| C6 | partially completed splittable leaf | create semantic children/decompose | do not fabricate child progress; historical parent progress may be retained; parent becomes structural |

## 2. Completion <-> reopen

| ID | Source | Action | Destination / consequences |
|---|---|---|---|
| CR1 | incomplete atomic leaf | complete | complete; leaves active frontier; ancestors/dependants reconcile |
| CR2 | complete atomic task | reopen | incomplete; frontier/blocking/ancestors reconcile; priority preserved |
| CR3 | proposed large allocation | mark segment complete | segment becomes canonical completed progress; `%completed` rises; future allocations recompute |
| CR4 | completed progress segment | mark segment incomplete | only that segment's progress removed; `%completed` falls; remaining schedule recomputes |
| CR5 | partial large task | complete final segment | `%completed=100`; task complete; dependency/ancestor consequences reconcile |
| CR6 | 100% large task | reopen a completed segment | task becomes partial; other completed segments remain complete |
| CR7 | prerequisite incomplete | user attempts complete dependant | **Confirm:** cancel or remove dependency then complete |
| CR8 | prerequisite and dependant complete | reopen prerequisite | **Confirm:** cancel or remove dependency then reopen (future explicit propagate option may be added) |
| CR9 | accidental complete then immediate valid inverse | reopen/undo | round-trip prior semantics without unrelated drift |

## 3. Leaf <-> structural / frontier transitions

| ID | Source | Action | Destination / consequences |
|---|---|---|---|
| H1 | executable leaf | add first required child | parent -> structural/non-frontier |
| H2 | structural parent | all required children complete/removed | parent -> residual executable leaf if closure work remains |
| H3 | residual leaf | complete residual work | parent complete |
| H4 | residual leaf | add/reopen child | parent -> structural; residual executable estimate suspended; original scope preserved |
| H5 | structural episode ends again | last blocking child completes | fresh residual scheduling estimate; never accumulate stale residual estimate |
| H6 | anchored leaf -> structural | add child | anchor preserved/suspended on parent; children inherit anchor; expiry/conflicts reconcile |
| H7 | H6 reversed with no relevant other mutation | delete/complete child and parent returns | restore prior parent anchor semantics as closely as current time permits |

## 4. Hierarchy / reparenting

| ID | Source | Action | Destination / consequences |
|---|---|---|---|
| RP1 | active task/subtree | reparent to valid new parent | hierarchy changes atomically; frontier/dates/defaults do not silently rewrite; dependencies preserved unless invalid |
| RP2 | active task/subtree | reparent under self/descendant | reject hierarchy cycle |
| RP3 | reparent would invalidate dependency graph/semantics | attempt commit | reject or require explicit dependency resolution; never silently delete edge |
| RP4 | task becomes root | remove parent/reparent root | stored task dates remain own values; reconcile hierarchy/frontier |
| RP5 | task moved under new parent | reparent | new parent's dates are not silently copied over existing task dates |

## 5. Delete / restore / undo

| ID | Source | Action | Destination / consequences |
|---|---|---|---|
| D1 | active task | delete | tombstone/remove from active projections; hierarchy/dependency incident state reconciled; history retained |
| D2 | active parent/subtree | delete | no dangling active descendants/parent refs; chosen subtree semantics applied atomically |
| D3 | dependency endpoint | delete | incident active edges suspended/removed from active graph with restore history |
| D4 | deleted task | restore | validate original parent/edges against current world; restore only valid relationships |
| D5 | restore would create hierarchy cycle | restore | reject/require new valid destination |
| D6 | restore would create dependency cycle | restore | offending relationship not silently reactivated; require resolution |
| D7 | deleted anchored task restored after anchor date | restore | old anchor history does not blindly become a current hard commitment; reconcile expiry/current intent |
| D8 | deleted incomplete task restored after deadline | restore | task derives overdue |
| D9 | operation with no later conflicting mutation | undo | exact/semantic inverse restores prior state |
| D10 | undo after later relevant mutation | undo | validate inverse against current state; surface conflict rather than bulldoze newer facts |

## 6. Priority

| ID | Source | Action | Destination / consequences |
|---|---|---|---|
| P1 | active tasks | reprioritise A/B | canonical priority changes; reschedule |
| P2 | task completes | completion | canonical priority/history preserved; task simply leaves active projection as appropriate |
| P3 | task reopens | reopen | returns with preserved meaningful priority context |
| P4 | leaf becomes structural | add child | parent priority not destroyed |
| P5 | descendant departure exposes ancestor | frontier change | ancestor obtains/restores meaningful neighbourhood without cumulative priority drift |
| P6 | Timeline/Focus explicit "B should generally precede A" | reprioritise | canonical priority changes, all views reproject |
| P7 | user merely executes lower-ranked item first | execution | no priority mutation |

## 7. Dependency lifecycle

| ID | Source | Action | Destination / consequences |
|---|---|---|---|
| DP1 | independent A,B | add A->B | validate no self/cycle; B blocked until A complete |
| DP2 | edge A->B | remove dependency | B eligibility recomputed |
| DP3 | A incomplete, B blocked | complete A | B may become unblocked/frontier |
| DP4 | A complete, B unfinished | reopen A | B becomes blocked unless user resolves contradiction by removing edge where completed-state conflict exists |
| DP5 | dependency creation would cycle | add edge | reject |
| DP6 | hierarchy order differs from dependency | schedule | dependency wins as hard legality; priority remains preference |
| DP7 | B nominal release earlier than prerequisite A availability | schedule | B still cannot execute before A completes; no extra hidden ancestor-release rule required |
| DP8 | delete/restore/reparent endpoint | lifecycle mutation | graph revalidated; no dangling/cyclic edge |

## 8. Release / deadline edits and time passage

| ID | Source | Action | Destination / consequences |
|---|---|---|---|
| T1 | task | set/change release | own canonical release changes; eligibility/schedule recompute |
| T2 | task | clear release | eligibility/schedule recompute |
| T3 | task | set/change deadline | own canonical deadline changes; overdue/pressure/schedule recompute |
| T4 | task | clear deadline | overdue constraint removed; reschedule |
| T5 | parent -> child creation | open form | child form prefilled with parent release/deadline |
| T6 | child form | user chooses earlier/later release/deadline | explicit child value committed; divergence allowed with warning where appropriate |
| T7 | parent deadline edited around existing children | edit parent | children retain own stored dates; no silent bulk rewrite |
| T8 | current time crosses task release | time reconciliation | unreleased -> released; eligibility recompute |
| T9 | current time crosses deadline incomplete | time reconciliation | -> overdue |
| T10 | overdue task completed | complete | no longer active overdue work; history remains |
| T11 | overdue task deadline extended | edit deadline | may return to non-overdue; schedule recompute |
| T12 | app unused across many days | reconcile(now) | derive current release/overdue/anchor states directly; stale old schedule discarded/recomputed |

## 9. Anchor/manual date intent

| ID | Source | Action | Destination / consequences |
|---|---|---|---|
| A1 | automatic task | set valid anchor | active anchor; scheduler works around it |
| A2 | anchored task | move anchor valid date | anchor date changes; reschedule |
| A3 | anchored task | remove anchor | return to automatic placement |
| A4 | requested anchor after deadline | set/move | **Confirm:** extend deadline appropriately then anchor, or cancel |
| A5 | requested anchor before release | set/move | **Confirm:** move release appropriately then anchor, or cancel |
| A6 | anchor date passes incomplete | time reconciliation | hard anchor expires; not automatically overdue; recovery intent/history retained as defined |
| A7 | future task | promote to today | create explicit today anchor/manual intent; reschedule |
| A8 | promoted task missed | next-day reconcile | anchor expiry/recovery semantics; do not silently revert to old automatic position |
| A9 | automatic scheduled task missed | next-day reconcile | no persistent manual intent; simply reschedule remaining work |
| A10 | valid anchor later made impossible by dependency/release edit | later mutation | preserve facts only if user confirms/resolve conflict; never silently move/delete anchor |
| A11 | anchor causes overload/infeasibility | user action | warn/confirm; if accepted preserve intent + flag pressure |

## 10. Duration / estimate transitions

| ID | Source | Action | Destination / consequences |
|---|---|---|---|
| E1 | atomic category | edit to another atomic category | incomplete/complete semantics preserved; reschedule if incomplete |
| E2 | splittable category at p% | edit to another splittable category | preserve p%; schedule remaining `100-p` against new category |
| E3 | splittable partial | edit to atomic category | discard active partial-progress scheduling semantics; resulting task is ordinary incomplete atomic work |
| E4 | E3 task | later edit atomic -> splittable | start splittable progress from 0 unless task is already complete; old discarded p% not resurrected |
| E5 | atomic incomplete | edit to splittable | `%completed=0`; allocate unfinished work |
| E6 | atomic complete | edit duration | remains complete unless explicitly reopened |
| E7 | duration crosses atomic/splittable boundary | edit | allocation/progress projections rebuilt; semantic hierarchy untouched |

## 11. Splittable large-work allocation lifecycle

| ID | Source | Action | Destination / consequences |
|---|---|---|---|
| L1 | unfinished splittable leaf | schedule | create disposable allocation percentages/dates summing to remaining work conceptually |
| L2 | proposed allocation | reschedule before completion | percentage/date may change freely; no canonical progress lost |
| L3 | proposed allocation | complete | freezes that completed percentage as canonical progress segment; task becomes/remains commenced |
| L4 | commenced task | reschedule | allocate only remaining percentage; favour momentum/nearby completion subject to global quality |
| L5 | completed segment | reopen | remove that segment from completed accounting; reschedule added remaining percentage |
| L6 | all segments/progress reach 100% | reconcile | task complete |
| L7 | partial large leaf | semantic decomposition | allocation pseudo-children disappear/reproject; no child receives fabricated percentage |
| L8 | planner projection | show allocations beneath task | visual pseudo-children only; no hierarchy/dependency identity |

## 12. Focus View

| ID | Source | Action | Destination / consequences |
|---|---|---|---|
| F1 | scheduled stream | render Focus | group by duration; date first then execution rank |
| F2 | insufficient today candidates | look ahead | show future candidates without rescheduling them |
| F3 | candidate | set current focus | convenience state only; no planning mutation |
| F4 | current focus | select another | convenience state changes only |
| F5 | future queued candidate | explicit do-today/promote | anchor/manual today intent + reschedule |
| F6 | promoted candidate | return to automatic | remove explicit date commitment; reschedule |
| F7 | queued candidate | explicit reprioritise | canonical priority mutation + reschedule |
| F8 | drag/drop into wrong visual bucket | committed do-today intent | system uses canonical duration to place in correct bucket; gesture location doesn't corrupt duration |
| F9 | task becomes non-executable while current focus | reconcile | clear/disable current-focus convenience state; explain block; planning facts unchanged |

## 13. Timeline / scheduler proposal lifecycle

| ID | Source | Action | Destination / consequences |
|---|---|---|---|
| S1 | canonical reconciled state | scheduler run | dates/allocations/ranks generated |
| S2 | same facts | scheduler rerun | canonical facts unchanged; deterministic/idempotent semantics expected subject to algorithm tie policy |
| S3 | user ignores rank/order | executes another task | no canonical mutation |
| S4 | user explicitly moves task to date | planning action | translate to anchor/manual date intent, validate, reschedule |
| S5 | user explicitly expresses general precedence preference | planning action | translate to priority mutation, not Timeline-only order |
| S6 | algorithm flavour changed | rerun | proposals may change; canonical state unchanged |
| S7 | scheduler fails mid-run | failure | canonical state unchanged; no partial proposal becomes truth |
| S8 | valid facts have no feasible schedule | run | flag infeasible/pressure; preserve facts; do not violate hard constraints |
| S9 | deadlines force heavy day | run | overload if necessary rather than deliberately push completion into dangerous deadline proximity merely for balance |

## 14. Compound / transactional transitions

| ID | Source | Action | Destination / consequences |
|---|---|---|---|
| X1 | valid state | multi-field edit | validate prospective final state atomically; commit once; reconcile once |
| X2 | multi-field edit creates cycle | commit attempt | reject transaction |
| X3 | edit creates user-visible risky overload | commit attempt | confirm before commit |
| X4 | edit creates anchor/dependency/release conflict | commit attempt | explicit resolution/cancel; no silent canonical rewrite |
| X5 | reversible sequence | inverse sequence with no intervening relevant change | semantic round trip |
| X6 | repeated/random valid operations | long-run | all invariants continue to hold; no semantic drift |

## 15. Required state-machine test families

Every transition above must be tested from every relevant orthogonal state combination, especially:

- active/deleted;
- atomic/splittable;
- 0%/partial/100%;
- leaf/structural/residual;
- blocked/unblocked;
- unreleased/released;
- overdue/non-overdue;
- anchored/unanchored/suspended/expired;
- dependency endpoint/non-endpoint;
- root/child/parent;
- automatically scheduled/manually anchored;
- feasible/overloaded/infeasible.

Property tests must repeatedly generate valid command sequences and assert all invariants after every commit and reconciliation pass.
