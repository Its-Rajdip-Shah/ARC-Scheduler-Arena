# What the Scheduling Algorithm Manages

The algorithm operates *after* canonical reconciliation. It optimizes proposals; it does not define domain truth.

## Algorithm inputs

- Active reconciled executable/blocked work.
- Hierarchy context relevant to priority/residual work.
- Canonical priority.
- Explicit dependencies.
- Release/deadline constraints.
- Anchors/manual planning intent.
- Duration categories.
- Confirmed `%completed` for splittable work.
- Current date/time context.
- Existing valid manual commitments.

## Algorithm outputs

- Scheduled date(s).
- Allocation/session percentages for splittable unfinished work.
- Execution rank within each date.
- Focus candidate stream/order derived from schedule.
- Workload pressure/infeasibility assessment.

## Hard rules every algorithm must obey

1. Never schedule before a task's own release.
2. Never execute a dependant before its prerequisite is complete.
3. Respect valid active anchors/manual hard date intent or surface impossibility rather than moving them silently.
4. Never alter canonical priority, hierarchy, dependency, dates, anchors or confirmed progress.
5. Never count proposed allocation as completed work.
6. Never present physically/logically impossible constraints as a healthy feasible schedule.
7. Protect deadline safety margin: when feasible earlier capacity exists, avoid intentionally placing completion on/too near deadline merely for workload smoothness.
8. If hard constraints force overload, represent it honestly.

## Optimization dimensions algorithms MAY vary

- Deadline front-loading aggressiveness within the deadline-safety rule.
- Priority weighting.
- Slack exploitation.
- Balance vs burst scheduling.
- Back-ripple/aggressive filling when capacity becomes free.
- Continuity/momentum weighting for commenced large tasks.
- Fragmentation penalty.
- Session/allocation sizing for `<8h`, `<16h`, `>16h` categories.
- How strongly to prefer finishing a commenced large task ASAP versus globally improving other work.
- Recovery placement after missed automatic work/manual promotion.
- Workload-pressure target.
- Tie-breaking.

## Large-task objective

For splittable work, optimize a balance of:

- completing the whole task reasonably soon;
- keeping sessions reasonably close together after commencement;
- avoiding one task consuming an unnecessarily huge portion of a day;
- respecting harder constraints and global priorities;
- allowing fragmentation when it materially improves the global schedule.

Future allocations are recomputed as remaining percentage and global schedule change.

## Deadline objective

Algorithms should reserve enough feasible earlier work to prevent constrained tasks drifting into deadline-danger territory. Flexible high-priority work may precede distant healthy deadline work, but algorithms may not consume slack so aggressively that deadline safety is predictably destroyed.

## Flavours

Possible flavours include aggressive/back-ripple, deadline-sensitive, balanced/pacifist and burst-oriented. Flavours are policy configurations over the same hard domain contract; changing flavour must not change canonical facts.

## Evaluation metrics candidates

- Hard-invariant violation count (must be zero).
- Deadline miss/infeasibility handling.
- Deadline safety/slack.
- Priority satisfaction.
- Workload pressure distribution.
- Overload magnitude/frequency.
- Large-task completion latency.
- Fragmentation/continuity.
- Schedule churn/stability.
- Manual-intent preservation.
- Recovery quality after lifecycle volatility.
