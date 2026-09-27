from __future__ import annotations

import json
import multiprocessing as mp
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BACKEND))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "arc_backend.settings")

SCENARIOS = [
    ("G022-R0", 12),
    ("G022-R1", 13),
    ("G029-R0", 15),
    ("G029-R1", 17),
    ("G000-R1", 18),
]

HORIZON_DAYS = 30
MAX_NODES = 1_000_000
WALL_TIMEOUT = 90


def run_one(scenario_id: str, expected_sessions: int, queue) -> None:
    import django
    django.setup()

    from arena.benchmarks.reconstruct import reconstruct_v1_scenario
    from arena.oracle import ExactOracle, ExactOracleConfig
    from arena.scheduling.mechanics import session_pieces
    from arena.tuning.design import calibration_objective

    started = time.perf_counter()

    try:
        reconstructed = reconstruct_v1_scenario(scenario_id)
        problem = reconstructed.problem

        actual_sessions = sum(
            len(session_pieces(item))
            for item in problem.items
        )

        config = ExactOracleConfig(
            objective=calibration_objective(),
            horizon_days=HORIZON_DAYS,
            max_sessions=max(expected_sessions, actual_sessions),
            max_nodes=MAX_NODES,
        )

        result = ExactOracle(config).solve(problem)

        queue.put({
            "scenario_id": scenario_id,
            "session_count": actual_sessions,
            "status": str(result.status),
            "nodes_visited": result.nodes_visited,
            "leaves_evaluated": result.leaves_evaluated,
            "elapsed_seconds": time.perf_counter() - started,
            "optimal_objective": (
                result.objective.total
                if result.objective is not None
                else None
            ),
        })

    except Exception as exc:
        queue.put({
            "scenario_id": scenario_id,
            "session_count": expected_sessions,
            "status": "error",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "elapsed_seconds": time.perf_counter() - started,
        })


def main() -> None:
    ctx = mp.get_context("spawn")
    results = []

    print("=" * 78)
    print("C7 EXACT FEASIBILITY — CONTROLLED SMALL-CASE PROBE")
    print("=" * 78)
    print(f"node_limit={MAX_NODES:,}")
    print(f"wall_timeout_per_case={WALL_TIMEOUT}s")
    print()

    for i, (scenario_id, sessions) in enumerate(SCENARIOS, 1):
        print(
            f"[{i}/{len(SCENARIOS)}] {scenario_id} "
            f"(~{sessions} sessions)",
            flush=True,
        )

        queue = ctx.Queue()
        process = ctx.Process(
            target=run_one,
            args=(scenario_id, sessions, queue),
        )

        started = time.perf_counter()
        process.start()
        process.join(WALL_TIMEOUT)

        if process.is_alive():
            process.terminate()
            process.join()

            row = {
                "scenario_id": scenario_id,
                "session_count": sessions,
                "status": "wall_timeout",
                "elapsed_seconds": time.perf_counter() - started,
            }

            print(
                f"    WALL TIMEOUT after {WALL_TIMEOUT}s"
            )

        else:
            if not queue.empty():
                row = queue.get()
            else:
                row = {
                    "scenario_id": scenario_id,
                    "session_count": sessions,
                    "status": "process_failed",
                    "exitcode": process.exitcode,
                    "elapsed_seconds": time.perf_counter() - started,
                }

            print(
                f"    status={row['status']} "
                f"nodes={row.get('nodes_visited')} "
                f"time={row.get('elapsed_seconds', 0):.3f}s"
            )

        results.append(row)

        try:
            process.close()
        except Exception:
            pass

        queue.close()

    out = Path.home() / "Desktop" / "ARC_C7_EXACT_SMALL_PROBE.json"

    out.write_text(
        json.dumps(
            {
                "policy": {
                    "horizon_days": HORIZON_DAYS,
                    "max_nodes": MAX_NODES,
                    "wall_timeout_seconds": WALL_TIMEOUT,
                },
                "results": results,
            },
            indent=2,
            sort_keys=True,
        ) + "\n",
        encoding="utf-8",
    )

    print()
    print("=" * 78)
    print("SUMMARY")
    print("=" * 78)

    for row in results:
        print(
            f"{row['scenario_id']:8s} | "
            f"sessions={row['session_count']:2d} | "
            f"{row['status']}"
        )

    print()
    print(f"OUTPUT={out}")


if __name__ == "__main__":
    main()
