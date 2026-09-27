ARC decides WHAT IS TRUE.
Algorithm decides WHAT TO DO WITH IT.
Arena decides HOW WELL IT DID.


1. Build workload feature extractor → map every dataset into our multidimensional space: hierarchy, duration, priority, temporal, anchors, dependencies, lifecycle, capacity pressure + correlations.
2. Characterize the existing 49 datasets → see what regions of that space we already cover and identify gaps.
3. Generate targeted synthetic datasets → systematically fill those gaps instead of making random workloads blindly.
4. Build Arena quality metrics → deadlines, priority satisfaction, continuity/fragmentation, workload pressure, stability/churn, feasibility, etc.
5. Benchmark A0 baseline → freeze its performance across the full dataset space.
6. Build A1, A2, A3… → run every algorithm through the exact same corpus/evaluator.
7. Map algorithm performance to feature-space regions → discover which algorithm works best where.
8. Build the hybrid/meta-selector → characterize a user’s live database → select the algorithm best suited to that workload. 😈






1. You + me: define the feature vector mathematically—every feature, formula, normalization, edge case, and what it means.
2. I use the Arena ZIP you already gave me to make sure those definitions fit the actual ARC schema/datasets.
3. Codex: give it an extremely precise implementation prompt: implement these exact formulas in these exact locations; don’t invent methodology.
4. Codex writes/tests it quickly.
5. Give me the resulting ZIP → I independently audit the implementation against our specification.
6. Run it across the 49 existing datasets → we analyze the feature-space coverage together.
7. Only then design the targeted synthetic generator.


Characterizer → freeze the ruler → controlled generator → characterize generated workloads → measure meaningful coverage → deliberately fill holes → freeze benchmark → algorithms → performance mapping → hybrid selector.





PYTHONPATH="$PWD/backend:$PWD" DJANGO_SETTINGS_MODULE=arc_backend.settings python - <<'PY'
from collections import defaultdict
from statistics import mean

from arena.generation.blueprint import build_blueprint, _minimum_frontier
from arena.generation.spec import (
    GenerationSpec,
    HierarchyDepth,
    HierarchyBranching,
    PriorityAlignment,
)

sizes = [16, 32, 64, 128, 256]
depths = list(HierarchyDepth)
branchings = list(HierarchyBranching)

runs = 0
violations = []
stats = defaultdict(list)

for size in sizes:
    for depth in depths:
        valid_branchings = (
            [HierarchyBranching.BALANCED]
            if depth is HierarchyDepth.FLAT
            else branchings
        )

        for branching in valid_branchings:
            for seed in range(100):
                spec = GenerationSpec(
                    seed=seed,
                    size=size,
                    hierarchy_depth=depth,
                    hierarchy_branching=branching,
                    priority_coverage=0,
                    priority_alignment=PriorityAlignment.NONE,
                )

                bp1 = build_blueprint(spec)
                bp2 = build_blueprint(spec)
                runs += 1

                # Determinism.
                if bp1 != bp2:
                    violations.append(("nondeterministic", size, depth, branching, seed))

                # Exact population.
                if len(bp1.items) != size:
                    violations.append(("wrong_size", size, depth, branching, seed))

                # Unique keys.
                if len({x.key for x in bp1.items}) != size:
                    violations.append(("duplicate_key", size, depth, branching, seed))

                # Frontier floor.
                if len(bp1.frontier) < _minimum_frontier(size):
                    violations.append(("frontier_floor", size, depth, branching, seed))

                # Parent existence + strict backward relation.
                positions = {x.key: i for i, x in enumerate(bp1.items)}
                for i, item in enumerate(bp1.items):
                    if item.parent_key is not None:
                        if item.parent_key not in positions:
                            violations.append(
                                ("missing_parent", size, depth, branching, seed)
                            )
                        elif positions[item.parent_key] >= i:
                            violations.append(
                                ("non_backward_parent", size, depth, branching, seed)
                            )

                stats[(size, depth.value, branching.value)].append(
                    (bp1.max_depth, len(bp1.frontier))
                )

print(f"🔥 Generated and checked {runs:,} workloads")

if violations:
    print(f"❌ {len(violations)} violation(s)")
    for violation in violations[:20]:
        print(" ", violation)
    raise SystemExit(1)

print("✅ ZERO structural/determinism violations")
print()
print("Representative shape summary:")
print(
    f"{'N':>4}  {'DEPTH':<8} {'BRANCH':<8} "
    f"{'mean maxD':>10} {'min/max D':>11} "
    f"{'mean F':>8} {'min/max F':>11}"
)

for key in sorted(stats):
    size, depth, branching = key
    values = stats[key]
    ds = [x[0] for x in values]
    fs = [x[1] for x in values]

    print(
        f"{size:>4}  {depth:<8} {branching:<8} "
        f"{mean(ds):>10.2f} "
        f"{min(ds):>3}/{max(ds):<7} "
        f"{mean(fs):>8.2f} "
        f"{min(fs):>3}/{max(fs):<7}"
    )

print()
print("🎯 PASS 1B TORTURE COMPLETE")
PY