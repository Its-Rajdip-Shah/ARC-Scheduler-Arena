Yep. And I think your new examples expose two missing concepts that materially improve the model:

1. Dependency is not priority. “Implement Timeline” → “Polish frontend for submission” is a precedence constraint, not merely a preference.
2. An anchor should not silently rewrite priority. What we actually want is persistence of the user’s planning intent after an anchor expires, without corrupting what global priority means.
3. A reversible user action should be semantically reversible wherever reality hasn’t changed in a way that makes exact reversal impossible.
4. Changing whether a goal is currently structural or executable must change only what logically follows from that transition. It must not destroy priority, temporal intent, dependencies, history, or residual-work meaning.
5. Validate the complete consequence of a transition first; then commit the resulting canonical mutation atomically.
6. History preserves what the user meant; reconciliation determines what that meaning implies now.

That second one is subtle, so I would not make “anchor → priority boost” automatic. It solves one problem by creating another. Instead, ARC should remember that the user explicitly promoted something and use that as persistent planning intent until fulfilled/cancelled. More on that below.

And yes: from here onward, we keep refining the same model rather than inventing disconnected rules.

Refined ARC canonical model

                         USER INTENT
                              │
       ┌──────────────────────┼───────────────────────┐
       │                      │                       │
       ▼                      ▼                       ▼
 GLOBAL PRIORITY         HARD CONSTRAINTS       MANUAL INTENT
 "prefer sooner"         "must obey"             "I explicitly
                                               changed the plan"
       │                      │                       │
       │              ┌───────┼────────┐              │
       │              │       │        │              │
       │          dependency release deadline       anchor
       │
       └──────────────────────┬───────────────────────┘
                              ▼
                     CANONICAL ARC STATE
                              │
                    reconciliation layer
                              │
                              ▼
                         SCHEDULER
                              │
                    ┌─────────┴─────────┐
                    ▼                   ▼
              ALLOCATED DATES      EXECUTION RANK
                    │                   │
                    └─────────┬─────────┘
                              ▼
                    CANONICAL PROJECTIONS
                  ┌───────────┼───────────┐
                  ▼           ▼           ▼
               PLANNER     TIMELINE     FOCUS
                  │           │           │
                  └───────────┼───────────┘
                              ▼
                         USER ACTION
                              │
                translated into its actual
                    canonical intention
                              │
                              ▼
                     CANONICAL ARC STATE
                              │
                         reschedule


ARC automates what the user has left unspecified and preserves what the user has explicitly specified. Derived state may never masquerade as user intent, scheduler output may never masquerade as canonical truth, and UI state may never become a competing planning database: 
                         USER INTENT
                              │
             ┌────────────────┼────────────────┐
             ▼                ▼                ▼
         USER FACTS      HARD CONSTRAINTS   SOFT INTENT
             │                │                │
             └────────────────┼────────────────┘
                              ▼
                       CANONICAL STATE
                              │
                        reconciliation
                              ▼
                        DERIVED STATE
                              │
                              ▼
                          SCHEDULER
                              │
                  disposable recommendations
                              ▼
               dates / allocations / ranks
                              │
               ┌──────────────┼──────────────┐
               ▼              ▼              ▼
            PLANNER        TIMELINE        FOCUS
               │              │              │
               └──── meaningful user action ┘
                              │
                              ▼
                       DOMAIN COMMAND
                              │
                              └──────► canonical state


The killer principle is:

Views don’t own planning state. Views expose different projections and controls over the same planning state.

Planner isn’t one truth, Timeline another truth, Focus another truth.

They’re windows into ARC.

⸻

The refined contract

I would revise our list to this.

Canonical state and ownership

* Canonical state — every logical view reads from and mutates one shared ARC domain state; UI-specific representations never become competing planning truths.
* Views are projections — Planner, Priority, Timeline and Focus display different projections of canonical state rather than maintaining independent task hierarchies/orders/schedules.
* Single-write semantics — a meaningful user action in any view is translated into one canonical domain operation; other views update from its result.
* No repair hopping — the user must never need to visit another view merely to make the first view’s change “really count.”
* Intent preservation — automatic rescheduling must preserve explicit user intent unless satisfying it becomes impossible or the user revokes it.
* Automation without vandalism — ARC may automatically optimize unspecified parts of the plan but must not casually rewrite decisions the user explicitly made.
* Minimum-input principle — ARC infers/reconciles anything safely derivable from existing state rather than repeatedly asking the user to specify redundant information.
* Explicit exceptions are canonical too — anchors and similar overrides are not view-local hacks; they are canonical records explaining why automatic behaviour is overridden.

Hierarchy and dependencies

* Hierarchy invariant — parent/child relationships remain valid and cycle-free.
* Hierarchy means decomposition — parent/child structure represents “this work is part of this larger goal,” not automatically “child A must happen before child B.”
* Sibling order is preference, not dependency — placing A above B may express higher general priority but does not prove B is impossible before A.
* Dependencies are explicit precedence constraints — A → B means B cannot execute until A’s required predecessor condition is satisfied.
* Dependency is not priority — a prerequisite may itself have low global preference but must still precede dependent work.
* Dependency graph must be acyclic — dependency creation may never introduce impossible cycles.
* Scheduler must respect dependencies — dependent allocations before their prerequisites are invalid, not merely low-quality.
* Dependency violations are hard failures — algorithms producing them are discarded.
* Dependencies should be optional — users aren’t forced to define relationships when work genuinely can happen independently.
* Dependency input must remain lightweight — graph visualization is not required for MVP; dependencies can be added during ordinary task creation/editing.
* Potential future assistance — ARC may later suggest likely dependencies from hierarchy/order, but must not silently invent hard prerequisites.

Your actual example becomes:

Assignment 2
│
└── Frontend
    ├── Implement Planner
    ├── Implement Timeline
    ├── Implement Focus
    └── Polish + prepare submission

Hierarchy alone says they’re all part of Frontend.

Then:

Planner ──┐
Timeline ─┼──► Polish + prepare submission
Focus ────┘

expresses the actual truth.

Now no algorithm is legally capable of producing:

Monday      Polish frontend
Tuesday     Implement Timeline

regardless of priority weights.

Temporal inheritance

* Parent deadline constrains descendants — unfinished descendant work required to complete a parent cannot legally be planned beyond the parent’s deadline.
* Effective deadline may be inherited — a child with no explicit deadline receives its parent’s deadline as an effective scheduling boundary without necessarily overwriting its own explicit field.
* Nearest explicit constraint wins where appropriate — if a descendant has a stricter valid explicit deadline, that tighter constraint governs it.
* Do not destroy provenance — ARC distinguishes user-entered dates from inherited/effective dates.
* Parent release constraints propagate where logically required — descendants cannot become executable before inherited release constraints permit them.
* Temporal inheritance recalculates — moving/reparenting tasks must recompute effective constraints rather than leaving stale inherited dates.

I strongly prefer derived effective_due_date over literally copying Assignment 2’s date into every descendant. Otherwise changing the parent’s deadline becomes synchronization hell.

explicit_due_date = NULL
parent due        = Sep 30
effective_due_date = Sep 30

Clean.

Frontier and lifecycle

* Frontier invariant — only currently executable work is exposed to scheduling.
* Dependency eligibility joins frontier eligibility — structurally leaf-like work blocked by an unfinished prerequisite is not currently executable.
* Completion invariant — completion/reopening correctly changes execution eligibility without destroying information.
* Completed work retains semantic position/history — hiding completed work from active projections does not mean deleting its priority/history.
* Parent transition — leaf → structural → leaf transitions preserve meaningful state.
* Residual parent effort — an exposed decomposed parent represents closure/integration work rather than its original full scope.
* Original scope preservation — effective residual effort never overwrites original user estimation.
* Repeated transitions are stable — reopen/complete/decompose cycles cannot accumulate semantic entropy.

Duration and large work

* Duration categories — <20m, <1h, <4h, <8h, <16h, >16h.
* Ranges are mutually exclusive internally — friendly UI labels do not create overlapping domain values.
* Large work need not be decomposed — users aren’t punished with administrative work just to make scheduling possible.
* Multi-day allocation — one canonical task can have several scheduled work allocations.
* Allocation is not decomposition — splitting estimated effort across days does not manufacture fake child tasks.
* Variable session sizing — algorithms choose allocation sizes.
* Momentum preference — once large work begins, finishing reasonably soon is preferred.
* Continuity is soft — adjacent sessions are desirable but may yield to globally better scheduling.
* Fragmentation has a cost — excessive gaps/fragmentation should be measurable in algorithm evaluation.
* Global optimization wins — local continuity may be sacrificed where doing so materially improves the overall feasible schedule.

Priority

* Global priority expresses preference — it says what the user generally wants ARC to favour, especially among otherwise flexible choices.
* Priority does not mean prerequisite — higher priority does not make lower-priority work legally dependent upon it.
* Priority does not guarantee earlier placement — deadlines, dependencies, releases, anchors and feasibility may override preference.
* Higher flexible priority generally pulls completion earlier — absent stronger constraints, algorithms should tend to finish higher-priority work sooner.
* Priority survives completion — completion changes active eligibility, not the historical meaning/order of the item.
* Priority restoration is stable — temporary frontier departure/return doesn’t degrade position.
* Priority inheritance preserves neighbourhood — newly exposed ancestors retain meaningful context from descendants.
* Planner and Priority Panel edit the same priority state — neither has its own ordering.

Release and deadlines

* Release is feasibility, not importance — it says “not before.”
* Deadline is a completion boundary, not automatic urgency — a distant healthy deadline need not dominate flexible work today.
* Deadline pressure is contextual — remaining effort + available legal capacity + remaining time determine risk.
* Deadline health must be protected — flexible work cannot consume capacity required to keep constrained work feasible.
* Healthy slack is usable — algorithms may schedule flexible work while deadline work remains comfortably feasible.
* Deadline aggressiveness is algorithmic — some flavours may front-load; others may exploit slack.
* Overdue is due-date based — incomplete work crossing its actual/effective deadline enters overdue handling.
* Overdue work remains recoverable — overdue does not mean unschedulable.

Anchoring and persistent manual intent

Here’s where I’d refine our previous model.

* Anchor means explicit date commitment — the user says “put this here.”
* Anchor beats automatic placement — schedulers work around valid anchors rather than casually moving them.
* Anchor movement is explicit — dragging/moving an anchored task changes its canonical anchor.
* Anchor expiry is not overdue — passing an anchor date revokes the hard date commitment; overdue depends on deadline.
* Anchor expiry is logged — ARC records that the intended date was missed.
* Anchor expiry must not erase intent — ARC remembers that the user deliberately promoted this work even after the hard date expires.
* Persistent promotion is distinct from global priority — “I explicitly tried to do this yesterday” shouldn’t arbitrarily jump the item to some invented priority number.
* Missed-anchor recovery favours proximity — after anchor expiry, automatic scheduling should preferentially place the work as close after the missed date as feasibility allows.
* User can explicitly return work to normal automatic treatment — removing the manual intent clears that special recovery preference.

This solves your problem without asking:

“Does anchoring move priority #14 to #2 or #5?”

We don’t need to invent an answer.

Instead:

global_priority = 14
anchor = today
manual planning intent = promoted
TODAY PASSES
anchor = expired
global_priority = still 14
manual intent = still promoted
              ↓
scheduler:
"place this ASAP subject to harder constraints"

That’s much more semantically truthful.

Capacity and overload

* Capacity represents real work feasibility — Timeline can’t claim impossible workloads fit.
* Effort, not task count, drives workload.
* Pressure is continuous underneath UI labels.
* UI pressure bands — Chill / Busy / Stacked / Crunch / Infeasible.
* Exact thresholds remain unresolved.
* Infeasible is structurally meaningful — the system cannot report physically absurd allocation as healthy.
* Bursting may be intentional — Stacked/Crunch days aren’t automatically algorithm failures if feasible and consistent with scheduler flavour/user preference.

Scheduler output

* Scheduler produces allocation dates.
* Scheduler produces execution rank within dates.
* Execution rank is algorithmic — priority, pressure, slack, continuity, etc. combine to produce it.
* Execution rank is advisory — users can simply execute rank #3 first without editing anything.
* Timeline vertical order displays execution rank.
* Doing something out of order doesn’t mutate priority.
* Explicitly changing the plan does mutate canonical intent — this is distinct from merely ignoring the recommendation.

Timeline

* Timeline is a projection, not a schedule database.
* Automatic cards reflect scheduler allocations.
* Manual Timeline movement expresses planning intent.
* Moving B before A temporally can update canonical preference where the action genuinely means “I want B before A.”
* Moving work to a specific date creates/changes explicit date intent rather than a Timeline-only coordinate.
* All affected views rerender from resulting canonical state.
* User changes remain sticky — rescheduling doesn’t immediately undo deliberate manual placement unless it becomes impossible.
* Impossible intent is surfaced, not silently destroyed — ARC should explain conflicts and let the user choose where appropriate.

Focus

* Focus is for actionable choice, especially today.
* Focus groups candidates by duration category.
* Focus candidates come from the canonical scheduled stream.
* Focus projection sorts by scheduled date first, execution rank second.
* Therefore A(today #1), C(today #2), B(tomorrow #1) → A,C,B.
* Focus may look ahead to populate choice buckets without rescheduling future work merely because it is displayed.
* Queue is continuation of the same projection, not another priority database.
* Current focus means only “I’m working on this now.”
* Current focus is optional convenience state.
* Current focus alone changes no priority, anchor or schedule.
* Selecting another current focus changes no planning commitment.
* “Do now” and “do today” remain distinct.
* Dragging/promoting a queued future task into active Focus means “I want this today” if that is the interaction we ultimately choose.
* Promote-to-today creates canonical date intent/anchor.
* Promoted work enters the correct duration bucket automatically regardless of where the user happened to drop it.
* Returning promoted work to automatic planning removes that explicit date commitment.
* Missed promoted work follows missed-anchor recovery rather than teleporting back to its old schedule.
* Explicit Focus reprioritisation changes canonical priority.
* Simply choosing a different task to execute does not.
* Gesture design remains unresolved — semantic commands come before drag/drop mechanics.

Dependencies

This is now important enough to become its own hard-invariant family.

* Dependency edge means required precedence.
* No self-dependencies.
* No dependency cycles.
* No scheduling a dependent before its prerequisite can be completed.
* Reopening a prerequisite re-blocks its unfinished dependents where applicable.
* Completing a prerequisite may expose newly executable work.
* Deleting/restoring prerequisite relationships must reconcile eligibility.
* Reparenting doesn’t silently destroy dependency relationships unless explicitly defined otherwise.
* Inherited deadlines must remain compatible with dependency order.
* Impossible dependency/deadline combinations must be detected, not “solved” with impossible scheduling.

That last one matters:

A → B
A requires 8h
B requires 4h
B deadline tomorrow
capacity remaining = 5h

There is no valid schedule.

A good scheduler reports infeasibility.

It doesn’t violate the dependency because the deadline looked scary.

⸻

The human-centric guarantee

I’d actually put this near the top of the eventual contract as an architectural principle:

ARC automates unspecified decisions and preserves specified decisions.

That’s the cleanest formulation we’ve found.

Think of planning state as having different authority levels:

USER HARD INTENT
dependency / explicit anchor / explicit constraint
            │
            │ preserve unless impossible/revoked
            ▼
USER SOFT INTENT
global priority / manual promotion / continuity preferences
            │
            │ optimize around
            ▼
ALGORITHMIC DECISIONS
automatic dates / allocations / execution ranks
            │
            │ freely recomputable
            ▼
VIEW PROJECTIONS
Planner / Priority / Timeline / Focus

That prevents automatic fuck-around.

The scheduler has enormous freedom over things the user never specified.

It has progressively less freedom as the user expresses intent.

And when the user explicitly takes control, ARC remembers it.

⸻

The ripple rule

Every interaction should eventually fit this template:

USER ACTION
     ↓
What did the human actually mean?
     ↓
CANONICAL DOMAIN COMMAND
     ↓
VALIDATE HARD INVARIANTS
     ↓
UPDATE CANONICAL STATE
     ↓
RECONCILE DERIVED STATE
     ↓
SCHEDULER RUNS if planning-relevant
     ↓
ALL VIEWS REPROJECT

Never:

Timeline drag
 ↓
change Timeline JSON
Priority drag
 ↓
change Priority JSON
Focus drag
 ↓
change Focus JSON

That would be three universes waiting to explode.

⸻

And the reverse is equally important

Not every UI interaction deserves a canonical planning mutation:

Open queue
→ UI only
Collapse hierarchy
→ UI only
Select current focus
→ execution convenience only
Do rank #3 before rank #1
→ no mutation
Look at tomorrow's candidates
→ no mutation

Whereas:

Change global priority
→ canonical mutation + reschedule
Change deadline
→ canonical mutation + reschedule
Add dependency
→ canonical mutation + eligibility reconciliation + reschedule
Move task to Friday
→ canonical manual intent + reschedule
Promote future task to today
→ canonical anchor/manual intent + reschedule
Remove anchor
→ canonical mutation + reschedule
Complete task
→ canonical lifecycle mutation + reconcile + reschedule

That’s how we automate aggressively without the app feeling possessed. 😂

⸻

One thing I would specifically NOT do

I wouldn’t automatically infer:

Assignment 2 above Assignment 3
        ↓
Assignment 2 MUST finish before Assignment 3

Your instinct there is exactly right.

Priority means:

prefer A before B.

Dependency means:

B is invalid/impossible until A.

Those must remain separate.

Likewise, I wouldn’t automatically create dependencies from sibling ordering such as:

Implement Timeline
Polish frontend

because sometimes those genuinely could overlap.

We can make adding dependencies very cheap, and perhaps later offer:

“Does ‘Polish frontend’ depend on these implementation tasks?”

But the user remains in control.

⸻

The one unresolved question you’ve uncovered

Should parent deadlines automatically become hard effective deadlines for every descendant?

For the normal decomposition case, yes, logically:

Assignment due Friday
└── Write report
Write report cannot meaningfully be scheduled Saturday.

But there may eventually be children representing post-completion work or optional work.

For MVP, I’d use:

Every unfinished descendant required for parent completion inherits the nearest ancestor deadline unless it has an earlier explicit deadline.

That gives us sensible semantics now without physically copying dates.

⸻

And yep, we should now actually create the living contract rather than leaving this monster in chat history.

Since you’re sitting at the repo root and already created about.md, I’d leave about.md alone and create:

docs/scheduling_domain_contract.md

But before I give you the command that writes it, I want the document to include everything above plus our earlier decisions, with explicit sections for:

LOCKED
PROVISIONAL
UNRESOLVED

so we don’t accidentally treat brainstorming—like exact overload thresholds or allocation session sizes—as frozen architecture.

Then every subsequent design turn we update that same file first. Once it stabilizes, implementation becomes almost mechanical, and then we can absolutely terrorize it with lifecycle tests. 🔒🧈