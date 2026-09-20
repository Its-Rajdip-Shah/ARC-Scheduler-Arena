# ARC Scheduler Arena — Backend Structure Validation

## Purpose

This document records the ARC backend changes made before scheduler-algorithm experimentation and the evidence supporting the experimental boundary.

The goal is to separate **ARC feasibility/infrastructure behaviour** from **algorithm quality**. ARC owns execution-frontier derivation, lifecycle reconciliation, persistence, hierarchy semantics, and hard-invariant validation. Experimental algorithms decide how eligible work is arranged, but must not redefine what work is legally schedulable.

> **Scope:** the backend is extensively validated against the *defined scheduling contract*. Testing cannot prove arbitrary software contains no conceivable bug. A future invariant failure should be attributed to an injected algorithm only after replaying the same state through the certified A0/control path and confirming the infrastructure/oracle remain healthy.

---

# 1. Backend Changes Made

## 1.1 Execution-frontier-only eligibility

`planning/services/scheduling.py::_scheduler_eligible()` was changed from scheduling every active actionable TASK/ASSIGNMENT to scheduling only the **execution frontier**.

An unfinished actionable item is eligible only when it has **no unfinished visible child**, using an `Exists`/`OuterRef` child query.

Consequences:
- decomposed parents cannot simultaneously be executable;
- unfinished leaf/frontier work owns execution dates;
- completing the last unfinished child can expose its parent;
- reopening/adding/restoring child work can demote the parent.

Hierarchy eligibility is therefore a feasibility rule, not an algorithm preference.

## 1.2 Stale execution-state reconciliation

Lifecycle testing found that a formerly eligible parent could retain an old `scheduled_date` after becoming non-frontier.

Scheduling now reconciles eligibility before assignment:
1. derive the current eligible frontier;
2. locate active actionable scheduled items no longer eligible;
3. clear stale execution state;
4. schedule the current frontier.

This prevents stale parent dates after child addition, reopening, restoration, or reparenting.

## 1.3 Feasibility repair applies to minimal and global modes

An intermediate attempt made hierarchy mutations trigger global scheduling. Regression testing rejected this because unrelated valid work could unnecessarily move earlier.

The final design separates **repair** from **optimization**:

- **Minimal:** repairs invalid state and schedules necessary/newly exposed work while preserving valid existing dates.
- **Global:** performs the same feasibility reconciliation but may reconsider/repack automatic dates.

Thus feasibility repair does not secretly imply schedule optimization.

## 1.4 Hierarchy services retain minimal scheduling

`set_parent(...)`, `complete_subtree(...)`, and `reopen(...)` retain ARC's original/default minimal scheduling path.

Because stale-frontier reconciliation is shared by scheduling modes, these operations can immediately restore validity without globally repacking unrelated work.

## 1.5 Anchor/non-frontier reconciliation

Anchoring does not grant execution eligibility. An eligible manual anchor remains fixed under unrelated changes, but a structurally ineligible item cannot remain executable merely because it was manually scheduled.

With the current model, stale non-frontier execution state is cleared during reconciliation. A future UX version may store requested manual intent separately from executable scheduling state.

## 1.6 Regression tests updated to the frontier contract

Old tests that expected actionable parents with unfinished children to remain schedulable were replaced.

Permanent coverage now includes parent demotion/exposure, child reopening/addition, hierarchy movement, anchor interactions, and preservation of minimal no-bubbling behaviour.

---

# 2. Structural Scheduling Contract

The following are infrastructure feasibility concerns, not tunable algorithm preferences:

- **Frontier eligibility:** automatic execution scheduling is restricted to active execution-frontier work.
- **Completion:** completed work is excluded; final-child completion may expose a parent.
- **Reopening:** reopened descendant work can demote a formerly exposed parent.
- **Child addition:** adding unfinished child work demotes the parent.
- **Deletion/restoration:** deleted work is excluded; deleting/restoring children can change parent eligibility.
- **Reparenting:** both source and destination branches must reconcile.
- **Deep propagation:** frontier changes must work across arbitrary hierarchy depth represented by ARC.
- **Temporal bounds:** release/start lower bounds and due-date upper bounds are hard feasibility boundaries.
- **Anchors:** eligible anchors remain fixed; anchors cannot manufacture execution eligibility.
- **Completed/deleted state:** inactive work cannot become ordinary active execution work.
- **Determinism:** equivalent initial states should produce equivalent results.
- **Idempotence:** rescheduling unchanged state must not progressively mutate the schedule.
- **Minimal stability:** feasibility repair must not unnecessarily repack otherwise valid work.

---

# 3. Validation Evidence

## 3.1 Focused backend regression suite — 64/64 PASS

Covers scheduling, lifecycle and hierarchy behaviour, including newly added frontier/anchor regressions.

## 3.2 Static hard-invariant gauntlet — 12/12 PASS

Validated scenarios:
- release only;
- due only;
- release + due;
- release = due;
- no constraints;
- anchored work;
- anchor collision;
- deep frontier;
- newly exposed frontier;
- priority versus deadline;
- completion freeing capacity;
- unavoidable overload.

## 3.3 Dynamic lifecycle gauntlet — 7/7 PASS

Validates adaptation across mutations rather than frozen snapshots:
- progressive frontier exposure;
- child reopening;
- child addition beneath scheduled work;
- partial sibling completion;
- anchor survival through unrelated completion;
- idempotent rescheduling;
- repeated completion sequences.

This layer discovered the stale-parent-date bug missed by static tests.

## 3.4 Deterministic transition matrix — 18/18 PASS

Explicitly covers:
- final-child completion;
- child reopening;
- completed descendant reopening beneath an exposed node;
- sibling completion;
- child addition;
- deletion/restoration;
- reparenting;
- deep frontier propagation;
- release/due/exact-window boundaries;
- anchor preservation and unanchoring;
- completed/deleted-state behaviour;
- idempotence;
- determinism.

## 3.5 Seeded state-machine torture — 10,000/10,000 transitions PASS

Configuration:
- 100 deterministic seeds;
- 100 mutations per seed;
- generated hierarchies;
- completion/reopening;
- child addition;
- deletion/restoration;
- reparenting;
- release/due changes;
- reschedule + invariant validation after every mutation;
- second reschedule/idempotence check after every mutation.

Seeds make any generated failure reproducible.

---

# 4. Experimental Boundary

The intended pipeline is:

```text
ARC database / hierarchy / lifecycle state
                  |
                  v
       certified feasibility layer
                  |
                  v
       current execution frontier
                  |
          injected algorithm
                  |
                  v
       candidate schedule output
                  |
                  v
      independent invariant oracle
             /          \
          FAIL          PASS
           |              |
           v              v
     inadmissible     quality metrics
```

Algorithms compete **inside the feasible region**. Hard feasibility is not a tunable weight.

---

# 5. Attribution of Future Failures

A0 remains the canary/control scheduler.

For a failing experimental state:
1. retain the exact dataset/state/seed;
2. replay it through A0 and the same oracle;
3. confirm backend certification tests remain green;
4. compare other algorithms on identical fresh state.

Interpretation:

```text
A0 PASS + challenger FAIL
    -> strong evidence of algorithm-specific violation.

A0 FAIL + challenger FAIL
    -> investigate infrastructure, fixture construction or oracle first.

Multiple unrelated algorithms FAIL identically
    -> investigate shared infrastructure before attribution.

Only one algorithm FAILS
    -> its implementation/design is the primary suspect.
```

This is more defensible than claiming testing mathematically proves no backend bug can ever exist.

---

# 6. Experimental Isolation Requirements

- Every algorithm starts from equivalent fresh database state.
- Algorithms cannot redefine execution-frontier membership.
- Algorithms cannot weaken the invariant oracle.
- Hard constraints cannot become algorithm-specific weights.
- Randomized algorithms record seeds.
- Outputs record algorithm/version/configuration/scenario.
- Invariant-failing runs are excluded from quality ranking.
- A0 remains available as the control/canary.
- Any later infrastructure/contract change requires recertification.

---

# 7. Frozen vs Experimental Responsibilities

## Frozen ARC/Arena feasibility substrate

Responsible for:
- hierarchy semantics;
- execution-frontier derivation;
- lifecycle state;
- completion/deletion visibility;
- persistence;
- hard temporal feasibility;
- anchor feasibility;
- stale-state reconciliation;
- invariant validation;
- experiment isolation;
- deterministic fixture loading.

## Experimental algorithm layer

May vary:
- task ordering signals;
- signal weights;
- normalization;
- priority influence;
- deadline/slack influence;
- release-date influence;
- duration influence;
- schedule-movement penalty;
- preferred earliness;
- capacity balancing;
- overload strategy within allowed semantics;
- tie-breaking;
- greedy/look-ahead/search/optimization strategy;
- search depth/beam width;
- candidate-date generation;
- local-search neighbourhood;
- backtracking;
- objective aggregation;
- deterministic versus randomized selection;
- hybrid combinations.

---

# 8. Certification Status

| Layer | Result |
|---|---:|
| Focused backend regression suite | 64 / 64 PASS |
| Static hard-invariant scenarios | 12 / 12 PASS |
| Dynamic lifecycle suite | 7 / 7 PASS |
| Deterministic transition matrix | 18 / 18 PASS |
| Seeded generated transitions | 10,000 / 10,000 PASS |

**Status:** ARC scheduling infrastructure is certified against the currently defined scheduling contract and is suitable as the fixed feasibility substrate for algorithm experimentation.

This status must be reconsidered if the contract or infrastructure changes.

---

# 9. Next Experimental Phase

## A. Freeze the algorithm design space

Catalogue every algorithm-controlled dimension and explicitly exclude hard invariants.

Useful dimensions include:
- ordering/scoring model;
- priority signal;
- deadline/slack signal;
- release signal;
- duration signal;
- movement/churn penalty;
- earliness preference;
- capacity balance;
- overload response;
- tie-breaking;
- look-ahead horizon;
- candidate-date strategy;
- search depth/beam width;
- backtracking/local search;
- objective aggregation;
- randomized versus deterministic choices.

Continuous weights cannot literally be exhaustively enumerated; discretize them into justified levels or use systematic search/sampling.

## B. Freeze performance metrics

Evaluate dimensions separately before combining them:
- invariant pass/fail;
- deadline/slack risk;
- priority satisfaction;
- schedule churn;
- overload magnitude/distribution;
- capacity utilization;
- excessive earliness/lateness;
- lifecycle stability;
- robustness across workload families;
- runtime;
- scaling behaviour.

Metric definitions and normalization should be frozen before the large tournament.

## C. Build an algorithm decision tree/search space

Represent candidates compositionally rather than writing unrelated algorithms:

```text
ordering strategy
|
+-- priority-first
|   +-- deadline weight
|   |   +-- weak
|   |   +-- medium
|   |   +-- strong
|   +-- movement penalty ...
|
+-- slack-first
|
+-- blended score
|
+-- look-ahead/search
    +-- depth
    +-- beam width
    +-- objective
```

This lets Arena enumerate meaningful combinations systematically.

## D. Tournament

Run candidates on identical workload families and lifecycle trajectories. Persist:
- configuration;
- schedule;
- per-metric results;
- runtime;
- invariant result;
- scenario;
- lifecycle step;
- random seed.

## E. Explain winners and losers

Keep strong, mediocre, specialist and deliberately poor candidates.

Analyse *why* they differ:
- which signals improve quality;
- which weights become harmful;
- useful/harmful interactions;
- failure modes of weak algorithms;
- robustness versus dataset overfitting;
- quality/runtime trade-offs;
- lifecycle behaviour.

The objective is not merely to find configuration #482 with the highest aggregate score, but to understand which scheduling principles actually produce good ARC behaviour.

---

# 10. Transferability to ARC

Arena mirrors ARC's backend structures and scheduling contract. Winning algorithms should therefore operate against the same `PlanningItem` state, execution-frontier semantics, temporal constraints, anchors, preferences and lifecycle behaviour.

Integration back into ARC should replace or extend the **algorithmic decision component**, not redesign the database or weaken feasibility rules.

That keeps experimental findings directly transferable to the production ARC repository.
