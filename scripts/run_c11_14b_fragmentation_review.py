from collections import defaultdict
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


from arena.production.flavour_planner import (
    generate_flavour_schedule,
)
from arena.production.integrated_fixture import (
    build_c11_13_base_world,
)
from arena.production.production_improver import (
    ProductionImproveConfig,
    improve_production_schedule,
)


TARGETS = (6, 7, 19)


def main():
    world = build_c11_13_base_world()

    for flavour in (
        "lock-in",
        "monk",
    ):
        initial = generate_flavour_schedule(
            world.problem,
            flavour,
            explicit_total_hours=
                world.explicit_total_hours,
        )

        result = improve_production_schedule(
            world.problem,
            initial,
            ProductionImproveConfig(
                max_iterations=80,
                max_evaluations=8000,
            ),
        )

        by_item = defaultdict(list)

        for row in (
            result.final_schedule
            .work_allocations
        ):
            by_item[row.item_id].append(
                row
            )

        print()
        print("=" * 88)
        print(
            f"{flavour.upper()} C11.14b "
            "FRAGMENTATION REVIEW"
        )
        print("=" * 88)

        print(
            "peak=",
            result.final_objective
            .max_daily_hours,
        )

        print(
            "overload_excess=",
            result.final_objective
            .overloaded_excess_hours,
        )

        print(
            "priority_delay=",
            result.final_objective
            .priority_postponement_days,
        )

        print(
            "shape_penalty=",
            result.final_objective
            .session_shape_penalty,
        )

        print(
            "global_fragments=",
            result.final_objective
            .fragmentation_count,
        )

        print(
            "tiny_nonfinal=",
            result.final_objective
            .tiny_nonfinal_sessions,
        )

        print(
            "termination=",
            result.termination_reason,
        )

        print(
            "evaluations=",
            result.evaluations,
        )

        for item_id in TARGETS:
            rows = sorted(
                by_item[item_id],
                key=lambda row:
                    row.scheduled_date,
            )

            print()
            print(
                f"#{item_id} "
                f"{world.labels[item_id]}"
            )

            print(
                f"touches={len(rows)}"
            )

            for row in rows:
                print(
                    "  "
                    f"{row.scheduled_date} "
                    f"{row.hours:.3f}h"
                )


if __name__ == "__main__":
    main()
