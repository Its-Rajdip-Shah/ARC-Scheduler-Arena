# ARC Scheduler Arena — Benchmark V1

**Status:** FROZEN

Benchmark V1 is the first fixed synthetic workload benchmark used for
algorithm evaluation in ARC Scheduler Arena.

## Corpus

- Designs: 59
- Replicates per design: 2
- Workloads: 118
- Characterization: Φ89
- Candidate-supported pairwise control coverage: 100%
- Pairwise control tokens: 2602
- Characterization date: `2026-01-15`
- Constant Φ89 dimensions: 0

## Provenance

V1 was frozen from the validated Phase-2B expanded screening corpus after:

1. freezing the Φ89 characterizer;
2. implementing the controlled workload generator;
3. canonical ARC materialization;
4. generator and planning-contract regression testing;
5. pairwise control-space screening;
6. Φ89 coverage analysis;
7. targeted reachability probes;
8. deliberate temporal, anchor-history, and actionable-parent hole filling;
9. re-characterization confirming variation in all 89 dimensions.

## Files

- `manifest.json` — benchmark contract and exact scenario IDs.
- `designs.csv` — the 59 frozen generator-control designs.
- `workloads.json` — metadata, Φ89 values, and correlation support for all scenarios.
- `phi89.csv` — flat workload × feature matrix.
- `feature_variation.csv` — V1 feature-range diagnostics.
- `SHA256SUMS` — integrity hashes for the frozen artifacts.

## Immutability rule

**Do not modify Benchmark V1 in response to algorithm performance.**

Algorithms are evaluated against this workload set. If future evidence shows
that the workload benchmark itself requires a semantic change, create a new
benchmark version (`v2`, etc.) and retain V1 unchanged.

Generated workload state is deterministic from the frozen design controls and
replicate seeds. Φ89 values in this directory are the frozen characterization
of those workloads under the V1 ruler.

## Experimental boundary

Benchmark V1 freezes the **workload side** of the experiment. It does not
freeze:

- scheduling algorithms;
- algorithm hyperparameters;
- performance metrics;
- performance maps;
- hybrid-selection models.

Those are subsequent experimental layers and must consume V1 without changing
it.
