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

SCENARIOS = ("G029-R0", "G029-R1")

HORIZON_DAYS = 30
MAX_NODES = 20_000_000
WALL_TIMEOUT_SECONDS = 90


def solve_one(scenario_id: str, queue) -> None:
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

        sessions = sum(
            len(session_pieces(item))
            for item in problem.items
        )

        oracle = ExactOracle(
            ExactOracleConfig(
                objective=calibration_objective(),
                horizon_days=HORIZON_DAYS,
                max_sessions=sessions,
                max_nodes=MAX_NODES,
            )
        )

        result = oracle.solve(problem)

        queue.put({
            "scenario_id": scenario_id,
            "sessions": sessions,
            "status": str(result.status),
            "nodes_visited": result.nodes_visited,
            "leaves_evaluated": result.leaves_evaluated,
            "optimal_objective": (
                result.objective.total
                if result.objective is not None
                else None
            ),
            "elapsed_seconds": time.perf_counter() - started,
        })

    except Exception as exc:
        queue.put({
            "scenario_id": scenario_id,
            "status": "error",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "elapsed_seconds": time.perf_counter() - started,
        })


def main() -> None:
    ctx = mp.get_context("spawn")
    rows = []

    print("=" * 78)
    print("G029 DEEP EXACT FEASIBILITY PROBE")
    print("=" * 78)
    print(f"max_nodes={MAX_NODES:,}")
    print(f"wall_timeout={WALL_TIMEOUT_SECONDS}s per case")
    print()

    for scenario_id in SCENARIOS:
        print(f"{scenario_id}: starting...", flush=True)

        queue = ctx.Queue()
        process = ctx.Process(
            target=solve_one,
            args=(scenario_id, queue),
        )

        started = time.perf_counter()
        process.start()
        process.join(WALL_TIMEOUT_SECONDS)

        if process.is_alive():
            process.terminate()
            process.join()

            row = {
                "scenario_id": scenario_id,
                "status": "wall_timeout",
                "elapsed_seconds": time.perf_counter() - started,
            }

            print(
                f"  WALL TIMEOUT after "
                f"{WALL_TIMEOUT_SECONDS}s"
            )

        elif not queue.empty():
            row = queue.get()

            print(
                f"  status={row['status']} "
                f"nodes={row.get('nodes_visited', 0):,} "
                f"leaves={row.get('leaves_evaluated', 0):,} "
                f"time={row['elapsed_seconds']:.3f}s"
            )

        else:
            row = {
                "scenario_id": scenario_id,
                "status": "process_failed",
                "exitcode": process.exitcode,
                "elapsed_seconds": time.perf_counter() - started,
            }

            print(
                f"  process failed, exitcode={process.exitcode}"
            )

        rows.append(row)

        try:
            process.close()
        except Exception:
            pass

        queue.close()

    output = (
        Path.home()
        / "Desktop"
        / "ARC_C7_G029_DEEP_EXACT.json"
    )

    output.write_text(
        json.dumps(
            {
                "policy": {
                    "horizon_days": HORIZON_DAYS,
                    "max_nodes": MAX_NODES,
                    "wall_timeout_seconds": WALL_TIMEOUT_SECONDS,
                },
                "results": rows,
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

    for row in rows:
        print(
            f"{row['scenario_id']} | "
            f"{row['status']} | "
            f"nodes={row.get('nodes_visited', '-')}"
        )

    print()
    print(f"OUTPUT={output}")


if __name__ == "__main__":
    main()
