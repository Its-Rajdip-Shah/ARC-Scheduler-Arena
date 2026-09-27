"""Fast in-memory calibration sweep for dependency-generation geometry."""

from __future__ import annotations

import os
from collections import defaultdict, deque
from statistics import mean
from time import perf_counter

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "arc_backend.settings")

import django
django.setup()

from arena.generation.blueprint import build_blueprint
from arena.generation.spec import (
    DependencyLoad,
    DependencyTopology,
    GenerationSpec,
    PriorityAlignment,
)

SIZES = [32, 128, 256]
SEEDS = range(20)

LOADS = [
    DependencyLoad.SPARSE,
    DependencyLoad.MODERATE,
    DependencyLoad.HEAVY,
]

TOPOLOGIES = [
    DependencyTopology.RANDOM_DAG,
    DependencyTopology.CHAIN,
    DependencyTopology.LAYERED,
    DependencyTopology.FAN_IN,
    DependencyTopology.FAN_OUT,
]


def metrics(bp):
    nodes = [item.key for item in bp.frontier]
    n = len(nodes)

    incoming = {key: [] for key in nodes}
    outgoing = {key: [] for key in nodes}

    edges = [
        (edge.prerequisite_key, edge.dependent_key)
        for edge in bp.dependencies
    ]

    for source, target in edges:
        incoming[target].append(source)
        outgoing[source].append(target)

    indegree = {key: len(incoming[key]) for key in nodes}
    queue = deque(key for key in nodes if indegree[key] == 0)
    topo = []

    while queue:
        node = queue.popleft()
        topo.append(node)

        for target in outgoing[node]:
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)

    longest = {key: 0 for key in nodes}

    for node in topo:
        for target in outgoing[node]:
            longest[target] = max(
                longest[target],
                longest[node] + 1,
            )

    ins = [len(incoming[key]) for key in nodes]
    outs = [len(outgoing[key]) for key in nodes]

    return {
        "F": n,
        "E": len(edges),
        "density": len(edges) / (n * (n - 1)) if n > 1 else 0.0,
        "blocked": sum(value > 0 for value in ins) / n if n else 0.0,
        "maxIn": max(ins, default=0),
        "maxOut": max(outs, default=0),
        "chain": max(longest.values(), default=0),
        "roots": sum(value == 0 for value in ins) / n if n else 0.0,
        "sinks": sum(value == 0 for value in outs) / n if n else 0.0,
        "acyclic": len(topo) == n,
        "edges": edges,
    }


def main():
    stats = defaultdict(list)
    counts = {}
    violations = []
    runs = 0
    start = perf_counter()

    for size in SIZES:
        print(f"\n⚙️  N={size}", flush=True)

        for topology in TOPOLOGIES:
            print(f"   {topology.value:<10}", end="", flush=True)

            for load in LOADS:
                for seed in SEEDS:
                    spec = GenerationSpec(
                        seed=seed,
                        size=size,
                        dependency_load=load,
                        dependency_topology=topology,
                        priority_coverage=0,
                        priority_alignment=PriorityAlignment.NONE,
                    )

                    bp = build_blueprint(spec)
                    result = metrics(bp)

                    key = (size, topology.value, load.value, seed)
                    counts[key] = result["E"]
                    stats[(size, topology.value, load.value)].append(result)
                    runs += 1

                    if not result["acyclic"]:
                        violations.append(("cycle", key))

                    if len(result["edges"]) != len(set(result["edges"])):
                        violations.append(("duplicate", key))

                print(".", end="", flush=True)

            print(" done", flush=True)

    for size in SIZES:
        for topology in TOPOLOGIES:
            for seed in SEEDS:
                edge_counts = [
                    counts[(size, topology.value, load.value, seed)]
                    for load in LOADS
                ]

                if not (
                    edge_counts[0]
                    < edge_counts[1]
                    < edge_counts[2]
                ):
                    violations.append(
                        (
                            "non_monotonic_load",
                            size,
                            topology.value,
                            seed,
                            edge_counts,
                        )
                    )

    elapsed = perf_counter() - start

    print(f"\n🔥 Checked {runs:,} workloads in {elapsed:.2f}s")

    if violations:
        print(f"❌ {len(violations)} violations")
        for violation in violations[:20]:
            print(violation)
        raise SystemExit(1)

    print("✅ DAG validity clean")
    print("✅ No duplicate edges")
    print("✅ Load monotonicity clean")

    print("\n=== N=128 / MODERATE TOPOLOGY GEOMETRY ===")

    for topology in TOPOLOGIES:
        values = stats[
            (128, topology.value, DependencyLoad.MODERATE.value)
        ]

        print(
            f"{topology.value:<10} | "
            f"F={mean(x['F'] for x in values):5.1f} | "
            f"E={mean(x['E'] for x in values):5.1f} | "
            f"dens={mean(x['density'] for x in values):.4f} | "
            f"blocked={mean(x['blocked'] for x in values):.3f} | "
            f"maxIn={mean(x['maxIn'] for x in values):5.2f} | "
            f"maxOut={mean(x['maxOut'] for x in values):5.2f} | "
            f"chain={mean(x['chain'] for x in values):5.2f} | "
            f"roots={mean(x['roots'] for x in values):.3f} | "
            f"sinks={mean(x['sinks'] for x in values):.3f}"
        )

    print("\n=== N=128 / RANDOM_DAG LOAD GEOMETRY ===")

    for load in LOADS:
        values = stats[
            (128, DependencyTopology.RANDOM_DAG.value, load.value)
        ]

        print(
            f"{load.value:<9} | "
            f"E={mean(x['E'] for x in values):5.1f} | "
            f"dens={mean(x['density'] for x in values):.4f} | "
            f"blocked={mean(x['blocked'] for x in values):.3f} | "
            f"chain={mean(x['chain'] for x in values):.2f}"
        )

    print("\n=== SCALE CHECK / MODERATE ===")

    for size in SIZES:
        print(f"\nN={size}")

        for topology in TOPOLOGIES:
            values = stats[
                (size, topology.value, DependencyLoad.MODERATE.value)
            ]

            print(
                f"  {topology.value:<10} "
                f"F={mean(x['F'] for x in values):6.1f} "
                f"E={mean(x['E'] for x in values):6.1f} "
                f"maxIn={mean(x['maxIn'] for x in values):6.2f} "
                f"maxOut={mean(x['maxOut'] for x in values):6.2f} "
                f"chain={mean(x['chain'] for x in values):6.2f}"
            )

    print("\n🧪 FAST DEPENDENCY CALIBRATION COMPLETE")


if __name__ == "__main__":
    main()
