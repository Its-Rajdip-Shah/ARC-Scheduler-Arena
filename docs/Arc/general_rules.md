# ARC General Rules

Status: Architecture freeze candidate

## Core principle

**ARC automates what the user leaves unspecified and preserves what the user explicitly specifies.**

1. One canonical truth: Planner, Priority, Timeline and Focus are projections over the same domain state, never independent planning databases.
2. A meaningful UI action is translated into a canonical domain command before any view changes.
3. UI convenience actions do not mutate planning truth unless they express planning intent.
4. User hard intent outranks automatic optimization. User soft intent guides optimization. Algorithmic proposals are disposable.
5. ARC must never silently rewrite an explicit user decision merely to make scheduling easier.
6. If an explicit action creates a conflict, overload or infeasibility, ARC warns before commit when detectable and lets the user cancel or explicitly accept/resolve it.
7. A valid but infeasible plan is representable. ARC reports the truth rather than falsifying constraints.
8. Reversible operations should round-trip to the previous semantic state when no intervening relevant mutation occurred.
9. Derived state must be recomputable from canonical facts and current time; it must not become a competing source of truth.
10. Scheduler output never repairs domain semantics. The scheduler receives reconciled canonical state.
11. Reconciliation is deterministic and idempotent: rerunning it without new facts must not cause semantic drift.
12. Atomic mutations validate the candidate final state, commit once, then reconcile/reschedule once.
13. History may preserve superseded facts for audit/undo, but historical state must never silently reactivate as current intent.

## Hierarchy

14. Hierarchy means decomposition: a child is part of a parent. It does not imply sibling precedence.
15. Hierarchy must remain cycle-free and internally valid.
16. Structural parents are not ordinary executable frontier work while required unfinished children exist.
17. When required children cease to block the parent, the parent may return to the frontier as closure/residual work.
18. Residual parent effort represents remaining integration/closure work, not the parent's original project scope.
19. Original scope/estimate is preserved across leaf -> structural -> residual-leaf cycles.
20. Each new structural episode produces fresh residual scheduling semantics; stale residual effort never accumulates across episodes.
21. Adding/reopening required child work may reopen/re-block ancestors as required to keep structural completion coherent.

## Priority and dependencies

22. Priority is a preference: generally favour this work sooner.
23. Priority is not a prerequisite and does not guarantee earlier scheduling.
24. Dependencies are hard precedence constraints and are independent of priority.
25. `A -> B` means B cannot execute until A is complete for the MVP dependency model.
26. Dependencies are optional, explicit, cycle-free and never silently invented from hierarchy or ordering.
27. If a user action contradicts a dependency, ARC does not silently break it: the user chooses between cancelling the action or explicitly removing the dependency and proceeding.
28. Reopening a prerequisite can re-block unfinished dependants.
29. Completing a prerequisite can expose newly executable dependants.
30. Deleting/restoring/reparenting dependency endpoints must never leave dangling or cyclic dependency state.
31. Partial/threshold dependencies are deferred from MVP.

## Temporal constraints

32. Release means "not before this date" for that task.
33. Deadline means "complete by this boundary"; having a deadline does not automatically make a task the highest-priority task today.
34. Child creation defaults its release/deadline fields from the parent for user convenience.
35. Inherited form defaults become the child's own values at creation; they are not immutable ancestor constraints.
36. Users may explicitly make a child's release earlier/later than the parent's and may make its deadline earlier/later than the parent's.
37. Divergent child/parent temporal choices are allowed when explicit; risky/incoherent-looking choices should be surfaced before commit rather than silently normalized.
38. Dependency feasibility naturally constrains execution regardless of a dependant's nominal release date.
39. Overdue means an incomplete task has crossed its own applicable deadline. Anchor expiry alone is not overdue.
40. Overdue work remains schedulable and recoverable.
41. ARC should strongly prefer completing deadline-constrained work with safety margin rather than intentionally planning it on/too near its deadline when earlier feasible capacity exists.
42. Protecting deadline safety margin is a scheduler-wide safety rule; flavours may vary aggressiveness within the remaining safe space.
43. When constrained work forces pressure, overload is preferable to deliberately consuming the deadline safety margin merely to make workload look balanced, subject to physical infeasibility being reported honestly.

## Anchors and manual planning intent

44. An anchor is explicit user date intent and is canonical.
45. Automatic scheduling works around valid anchors rather than casually moving them.
46. Moving an anchor changes the canonical anchor.
47. Anchoring beyond a deadline or before a release cannot silently rewrite the temporal constraint; ARC asks the user to change the conflicting constraint or cancel the anchor action.
48. Anchor expiry removes the hard date commitment but does not imply deadline overdue.
49. Missed/expired manual intent may remain relevant to recovery scheduling without being converted into global priority.
50. Removing an anchor explicitly returns placement to automatic scheduling.
51. If an anchored frontier task becomes structural, the parent's anchor is suspended/stale while non-executable and newly created required children inherit that anchor date. When the parent returns to the frontier, its preserved anchor may reactivate if still semantically/currently applicable; reconciliation handles expiry/conflicts.
52. Deleting a child or reversing a decomposition with no other relevant mutation should restore the prior anchored-parent semantics as closely as possible.

## Duration and progress

53. Duration categories are: `<20m`, `<1h`, `<4h`, `<8h`, `<16h`, `>16h`.
54. Internal ranges are mutually exclusive even if UI labels use friendly upper-bound wording.
55. `<20m`, `<1h`, and `<4h` are atomic/one-day scheduling categories.
56. `<8h`, `<16h`, and `>16h` are allocatable/splittable work categories.
57. Users are not forced to decompose large work into semantic child tasks merely to make it schedulable.
58. Splitting large work creates allocations/progress segments, not semantic hierarchy children.
59. Large tasks maintain canonical percentage-completed progress.
60. Future scheduler allocation percentages are proposals and may change on every reschedule.
61. Once a proposed allocation is marked complete, that completed percentage becomes canonical progress/history and contributes to `%completed`.
62. Completed progress segments may be individually reversed; reversing one decreases canonical completed percentage while unrelated completed segments remain complete.
63. A completed large task may be reopened by reversing completed progress segment(s), rather than inventing a new arbitrary percentage.
64. Editing one splittable duration category to another preserves `%completed`; remaining percentage is scheduled against the new category.
65. Editing a splittable task to an atomic category discards active partial-progress scheduling semantics: the resulting atomic task is simply incomplete unless fully complete.
66. Returning later from atomic to splittable work does not resurrect discarded old partial progress.
67. Large-task allocations should balance early completion, continuity/momentum, sensible session size and global schedule quality.
68. Continuity is a soft preference; fragmentation is allowed when globally beneficial.
69. Allocation session sizes are algorithmic, not hardcoded architecture.
70. When a partially completed large leaf is semantically decomposed into real child tasks, ARC must not fabricate child progress from the parent's percentage. Historical parent progress may be retained for audit, but the new semantic children begin with explicitly known completion states only.
71. Scheduler-generated progress segments may be projected beneath a large frontier task in Planner for visibility, but they are allocation/progress projections, not hierarchy children and cannot participate in dependency/hierarchy semantics as if they were tasks.

## Capacity, overload and scheduling

72. ARC does not require users to maintain a day-by-day availability/capacity calendar for MVP.
73. Workload pressure is based on allocated effort, not task count.
74. There is no user-defined hard daily capacity gate that makes excess work illegal.
75. Scheduler should prefer reasonable distribution but may overload days when constraints/manual intent leave no better schedule.
76. User-created overload is permitted only as an explicit, informed action when detectable before commit.
77. Constraint-created overload/infeasibility is surfaced, not hidden.
78. Pressure bands may eventually include Chill, Busy, Stacked, Crunch and Infeasible; exact thresholds remain algorithm/evaluation policy.
79. Scheduler output consists of dates/allocations plus execution rank/recommended order.
80. Execution rank is advisory. Doing rank #3 before rank #1 does not mutate canonical priority.
81. Algorithm flavours may vary balance/burst behaviour, back-ripple, slack use, deadline aggressiveness within safety rules, continuity, fragmentation penalties and session sizing.
82. Changing algorithm flavour cannot mutate canonical user facts.

## Views

83. Planner shows canonical hierarchy/priority plus appropriate projections such as allocation/progress visibility.
84. Priority Panel edits the same canonical priority state used everywhere else.
85. Timeline is a projection of allocations/dates/execution ranks, not a schedule database.
86. Explicit Timeline movement is translated into canonical planning intent; merely following/ignoring a recommendation is not.
87. Focus provides choices, not commands.
88. Focus groups candidates by duration category and may look ahead to future scheduled candidates without rescheduling them merely because they are displayed.
89. Focus projection orders scheduled date first, then execution rank within that date.
90. Current focus means only "I am working on this now" and is optional convenience state.
91. Current focus alone changes no priority, anchor or schedule.
92. "Do now" and "do today" are distinct intents.
93. Promoting future work to today creates explicit canonical date intent and triggers reconciliation.
94. Explicit Focus reprioritisation changes canonical priority; simply selecting/executing a different candidate does not.
95. Gesture mechanics are UX; domain intent commands are architecture.
