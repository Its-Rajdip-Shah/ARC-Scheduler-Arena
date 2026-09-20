Let’s do it. 🔬

We should treat this as an adversarial requirements audit, not implementation yet. For every plausible thing a human might mean, we ask:

Can ARC express this intent exactly once in canonical state, preserve it through lifecycle changes, and make every view agree without forcing the user to repair the plan elsewhere?

Adversarial user-intent matrix — Pass 1

#	User intention	Canonical meaning	Expected ripple	Status
1	“A is more important than B.”	priority(A) > priority(B)	Scheduler considers it; all priority projections agree	✅
2	“B cannot happen until A is finished.”	Hard dependency A → B	B blocked from executable frontier until A completes	✅
3	“I prefer A before B, but B may happen first if necessary.”	Priority, not dependency	Scheduler may override ordering for constraints	✅
4	“A must happen on Tuesday.”	Anchor/manual date intent	Scheduler preserves Tuesday and plans around it	✅
5	“A cannot happen before Tuesday.”	Release date	No allocation before Tuesday	✅
6	“A must be completed by Friday.”	Deadline	Scheduler protects sufficient capacity before Friday	✅
7	“A may start Tuesday and must finish Friday.”	Release + deadline	Allocations restricted to legal interval	✅
8	“I’m doing A right now.”	current_focus=A	No priority/date mutation	✅
9	“I want to do A today.”	Anchor/promote-to-today	Today becomes explicit manual planning intent	✅
10	“I changed my mind; ARC can decide when A happens.”	Remove manual date intent	Automatic scheduler regains placement authority	✅
11	“A was meant for yesterday but I didn’t do it.”	Expired anchor + retained promotion intent	Reschedule ASAP-ish; not overdue unless deadline passed	✅
12	“I want A Friday instead of Tuesday.”	Move anchor	One canonical anchor changes; all views follow	✅
13	“I don’t care about the order today; I’ll do #3 first.”	Execution choice only	Nothing structural changes	✅
14	“From now on I generally want B before A.”	Canonical reprioritisation	Planner/Priority change; scheduler reruns	✅
15	“Move B earlier in my actual plan.”	Explicit scheduling/manual intent	Timeline + Focus regenerate	✅
16	“Show me more short things I could do.”	Projection/query only	No scheduling mutation	✅
17	“None of these Focus choices appeal to me.”	Browse queue	No canonical planning mutation	✅
18	“Pull this future queue item into today.”	Promote/anchor today	Timeline changes; Focus regenerates	✅
19	“Show future work in Focus, but don’t move it.”	Look-ahead projection	Display only	✅
20	“This is a 20-hour task; don’t make me decompose it.”	One PlanningItem + multi-day allocations	Scheduler distributes effort	✅
21	“Keep working on this big task once I’ve started.”	Continuity preference/algorithm objective	Penalise excessive fragmentation	✅
22	“Interrupt this big task if that’s globally better.”	Soft continuity, not invariant	Scheduler may fragment when justified	✅
23	“Do more of this big task Wednesday than Tuesday.”	Unequal allocations	Supported by variable allocation sizing	✅
24	“Assignment due Friday means its required report can’t be Saturday.”	Derived effective descendant deadline	Descendant scheduling constrained	✅
25	“This child actually needs to finish Wednesday.”	Earlier explicit descendant deadline	Tighter child constraint applies	✅
26	“I finished A.”	Completion lifecycle transition	Frontier/dependencies/parent state/schedule reconcile	✅
27	“Actually A isn’t finished.”	Reopen	Eligibility/dependents/frontier/schedule reconcile	✅
28	“I decomposed A after already scheduling it.”	Leaf → structural transition	A leaves executable frontier; descendants take over	✅
29	“All A’s child work is done but A needs cleanup/submission.”	Residual parent effort	A returns as small executable closure work	✅
30	“Delete this child.”	Structural mutation	Parent/frontier/effective effort reconciled	✅
31	“Move this child under another parent.”	Reparent	Hierarchy + inherited constraints recomputed	✅
32	“A depends on B and B depends on A.”	Invalid dependency cycle	Reject mutation	✅
33	“A depends on itself.”	Invalid self-edge	Reject	✅
34	“Deadline requires violating dependency.”	Infeasible canonical problem	Surface conflict; never fake a solution	✅
35	“I deliberately want a very busy Tuesday.”	User capacity/planning preference	Allow feasible Stack/Crunch depending policy	🟡
36	“Do not put more work on Tuesday.”	Protected-day/capacity override	Scheduler must preserve requested headroom	🔴
37	“Tuesday I only have two hours available.”	Per-day capacity override	Scheduler uses Tuesday-specific capacity	🔴
38	“I don’t work Sundays.”	Recurring availability	Scheduler excludes/limits Sundays	🔴
39	“Normally I can work 6h/day.”	Baseline capacity preference	Scheduler feasibility uses user capacity	🔴
40	“This week is unusual; I have exams/work shifts.”	Temporary capacity overrides	Date-specific availability supersedes normal	🔴

Aha. We found our first real remaining hole.

ARC needs user availability/capacity as canonical input, not merely an algorithmic assumption.

Otherwise “real daily capacity” is meaningless.

⸻

Pass 2 — hierarchy/dependency nastiness

User intention / situation	Required behaviour	Status
A depends on B; B completes	A becomes eligible if everything else permits	✅
A depends on B and C	A waits for both	✅
A depends on B; B reopened	A becomes blocked again if unfinished	✅
A depends on B; B deleted	Must not leave dangling dependency	🟡 needs deletion policy
A depends on B; dependency removed	A immediately re-evaluated	✅
Parent P depends on X	Need precise semantics: does that block all descendants or only P’s residual completion?	🔴
X depends on parent P	What constitutes “P complete” when P is structural?	🟡
Child inherits parent deadline	Derived, not copied	✅
Child moves to different parent	Effective deadline recalculated	✅
Child has later explicit deadline than parent	Required child cannot make parent impossible	🔴 conflict semantics needed
Parent deadline changes earlier	Descendants recalc + scheduler detects infeasibility	✅
Parent deadline removed	Inherited constraint disappears without deleting child’s explicit dates	✅

The important unresolved one is dependencies involving structural parents.

I think the clean rule is:

A dependency references completion of a goal, regardless of whether that goal is currently a leaf.

Therefore:

Assignment 3 depends on Assignment 2

means Assignment 3 remains blocked until Assignment 2 itself is complete, including all required descendants and residual closure.

That’s intuitive and survives decomposition.

But:

Assignment 2 depends on Research Approval

should probably mean Assignment 2 itself cannot become executable, which raises the question whether its descendants should also be blocked.

I think yes:

If a goal is blocked by an external prerequisite, its required descendant work is blocked too.

Otherwise ARC could schedule “write implementation” before the prerequisite governing the whole project.

That’s a candidate to lock.

⸻

Pass 3 — “don’t fuck with my plan” scenarios

This is where human-centric design really gets tested.

User manually anchors A Tuesday; scheduler reruns

Must remain Tuesday. ✅

User changes priority elsewhere

The scheduler may rearrange automatic work around A, but not move A. ✅

User adds a deadline that conflicts with A’s anchor

Example:

A anchored Friday
A deadline Wednesday

ARC must not silently move either one.

It should create a canonical conflict:

⚠ Anchor occurs after deadline.

and let the user decide which explicit intent to modify.

That gives us another principle:

ARC never resolves conflicts between two explicit user decisions by secretly deleting one of them.

🔥 That belongs near the top of the contract.

User reduces Tuesday capacity below already anchored work

Again:

Tuesday capacity = 2h
anchored work = 4h

Don’t silently move the anchor.

Report:

Tuesday
capacity: 2h
manual commitments: ~4h
⚠ User-defined plan exceeds stated capacity.

The user is allowed to intentionally create an overloaded day.

So we need a distinction:

ALGORITHM CREATED INFEASIBILITY
→ invalid / algorithm failure
USER EXPLICITLY CREATED OVERLOAD
→ preserve + warn

That’s very important for Arena testing.

⸻

Pass 4 — priority ambiguity

Consider siblings:

1. A
2. B
3. C

User manually schedules C today.

Does that automatically mean:

1. C
2. A
3. B

I now think no.

Because:

“I want C today”

doesn’t necessarily mean:

“C is generally more important than A for the entire goal.”

This confirms our previous decision to keep manual scheduling intent separate from global priority.

Instead:

priority:
A > B > C
manual intent:
C → today
scheduler:
C today because explicit placement
A/B otherwise retain their priority relationship

If C isn’t completed:

anchor expires
        ↓
persistent promotion intent
        ↓
scheduler attempts C soon

No arbitrary priority-number mutation required.

That is cleaner than the anchor-changing-priority idea.

⸻

Pass 5 — another missing user intent: “prefer, don’t force”

We currently have:

automatic scheduling
        vs
hard anchor

But humans may absolutely mean:

“I’d prefer to do A Tuesday, but move it if Tuesday becomes ridiculous.”

That’s neither ordinary priority nor anchor.

Potential concept:

preferred_date

Semantics:

anchor_date
= hard manual placement
preferred_date
= soft placement intent
automatic
= no manual date preference

Then:

“Do not move this.”

→ anchor.

“I’d like this Tuesday.”

→ preferred date.

“Whatever works.”

→ automatic.

🔴 This is a genuine uncovered intent.

Whether MVP needs it is a product decision, but our audit has to record it.

⸻

Pass 6 — another one: “protect this time/day”

Humans may say:

“Keep Friday light because I’m going out.”

This isn’t a task operation at all.

It’s a capacity constraint.

So canonical availability probably needs something conceptually like:

AvailabilityProfile
    normal_daily_capacity
DateCapacityOverride
    date
    available_effort
RecurringAvailability
    weekday
    available_effort

Then algorithms receive capacity as input rather than inventing it.

This also makes scheduler flavours fair in Arena:

same goals
same constraints
same availability
same lifecycle
algorithm A vs algorithm B

Beautiful experimental isolation.

⸻

Pass 7 — large-work intentions

More attacks:

User means…	Model
“Spread this out.”	fragmentation/continuity preference
“Get this monster over with ASAP.”	high continuity/completion urgency
“Don’t let it consume my entire day.”	max allocation/day preference
“I’m happy spending all Saturday on it.”	date-specific capacity/manual allocation
“I did way more than ARC expected today.”	actual progress mutation + remaining-effort reconciliation
“I only did half today’s planned chunk.”	partial progress
“Turns out this task is much bigger than expected.”	revise remaining scope
“Turns out it’s nearly finished.”	revise remaining scope

Partial progress is another important hole.

If ARC supports a 16h task distributed:

Mon 25%
Tue 25%
Wed 25%
Thu 25%

then binary completed=False isn’t enough to know that Monday’s work happened.

We need to distinguish:

original estimated scope
remaining estimated effort
scheduled allocation
actual progress

Otherwise Tuesday’s scheduler still thinks the whole 16h remains.

So large-task allocation implies some form of progress accounting.

It doesn’t have to be obnoxious. Maybe completing a scheduled work session automatically records its allocated portion, and the user can adjust if necessary.

But the domain model needs the concept.

⸻

Pass 8 — dependencies + partial progress

Suppose:

A = 16h
B depends on A

A is 95% done.

Can B start?

Hard dependency says no until A reaches completion.

But sometimes users mean:

“B can start once A reaches roughly halfway.”

That’s a different relationship:

start-to-start / partial dependency

For MVP I would not implement that.

Lock dependency semantics as:

A → B means B becomes executable only when A is completed.

If users can actually overlap them, don’t create the hard dependency.

Later ARC could support richer dependency types if justified.

⸻

Pass 9 — deletion, undo and historical intent

More nasty ones:

A → B

Delete A.

We cannot leave B permanently blocked by a ghost.

Possible behaviours:

1. delete dependency automatically;
2. prevent deletion until relationship resolved;
3. soft-delete A so relationship remains interpretable.

Given ARC already cares about restore/history, I strongly favour soft deletion + reconciliation, but we’d need to inspect our current backend semantics before locking that.

Likewise:

anchor A
→ complete A
→ undo completion

What happens to the expired/old anchor?

We should not resurrect stale temporal intent blindly.

Undo should restore the semantic state appropriate to the operation, but time itself may have advanced.

That belongs in lifecycle certification.

⸻

What the audit has discovered

So no — thank fuck we did this before declaring victory. 😂

We found several things our previous model hadn’t fully captured:

1. Dependencies as first-class hard precedence.
2. Inherited effective temporal constraints.
3. Canonical user availability/capacity.
4. Per-date/recurring capacity overrides.
5. User-created overload vs algorithm-created infeasibility.
6. Conflict preservation when two explicit user decisions contradict.
7. Soft preferred dates as distinct from hard anchors — candidate/MVP decision.
8. Partial progress / remaining effort for multi-day large tasks.
9. Structural-parent dependency semantics.
10. Dependency deletion/reparent/restore semantics.
11. Explicit vs inherited deadline conflicts.
12. Potential richer dependency types, which I recommend deferring.

And our architecture evolves to:

                         HUMAN INTENT
                              │
          ┌───────────────────┼──────────────────┐
          ▼                   ▼                  ▼
     HARD INTENT          SOFT INTENT      EXECUTION STATE
 dependencies             priority         current focus
 anchors                  preferred date   actual progress
 release/deadline         continuity prefs
 availability
          │                   │                  │
          └───────────────────┼──────────────────┘
                              ▼
                       CANONICAL STATE
                              │
                    SEMANTIC RECONCILER
                              │
             ┌────────────────┴────────────────┐
             ▼                                 ▼
      EFFECTIVE CONSTRAINTS               CONFLICTS
 hierarchy/frontier                       infeasibility
 dependencies                             contradictory
 inherited dates                          explicit intent
 remaining effort
 availability
             │
             └────────────────┬────────────────┘
                              ▼
                          SCHEDULER
                              │
                ┌─────────────┴─────────────┐
                ▼                           ▼
             DATES /                    EXECUTION
            ALLOCATIONS                    RANK
                │                           │
                └─────────────┬─────────────┘
                              ▼
                 PLANNER / PRIORITY /
                  TIMELINE / FOCUS
                              │
                         USER ACTION
                              │
                              └──────► CANONICAL STATE

The human-centric law gets sharper

I think we can now formulate the thing you’re trying to build almost formally:

ARC should require the minimum user input necessary to represent intent, automatically derive everything that follows logically from that input, preserve explicit user decisions across automatic rescheduling, never silently reinterpret one kind of intent as another, and surface conflicts rather than secretly “fixing” the user’s plan.

Or, in our language:

Automate the unspecified. Derive the implied. Preserve the explicit. Warn about the impossible.

That should probably be the first line of scheduling_domain_contract.md. 🔥

We’re not done with the matrix yet, though. The next pass should specifically attack every state-changing action × every lifecycle state—e.g. anchor a completed task, add dependency to overdue work, reparent an anchored descendant, change a parent deadline while a child has manual allocation, reopen something whose dependents have since completed, etc. That’s where the truly cursed edge cases live.
