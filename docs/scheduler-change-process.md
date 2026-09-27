# Scheduler Change Process

> Status: productionisation scaffold.

When undesirable scheduler behaviour is discovered:

1. Capture the exact canonical input state.
2. Reproduce it as a deterministic fixture.
3. Classify the cause:
   - canonical-input issue
   - objective/engine issue
   - search/reachability issue
   - flavour-policy issue
   - integration/output issue
4. Add a failing regression test.
5. Make the smallest necessary change.
6. Run focused tests.
7. Run the full scheduler suite.
8. Run saturated-world certification.
9. Run grow → maximum-complexity → shrink certification.
10. Perform human behavioural review where appropriate.
11. Benchmark performance.
12. Version contracts/engine as required.
13. Integrate through ARC adapters.
14. Preserve an immediate rollback path.
