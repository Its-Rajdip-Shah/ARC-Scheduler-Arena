from collections import defaultdict
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


from arena.production.decision_world import (
    build_c11_15_saturated_world,
)
from arena.production.flavour_planner import (
    generate_flavour_schedule,
)
from arena.production.production_improver import (
    ProductionImproveConfig,
    improve_production_schedule,
)


world = build_c11_15_saturated_world()

initial = generate_flavour_schedule(
    world.problem,
    "monk",
    explicit_total_hours=
        world.explicit_total_hours,
)

result = improve_production_schedule(
    world.problem,
    initial,
    ProductionImproveConfig(
        max_iterations=120,
        max_evaluations=12000,
    ),
)

schedule = result.final_schedule

by_item = defaultdict(list)

for row in schedule.work_allocations:
    by_item[row.item_id].append(row)

for rows in by_item.values():
    rows.sort(
        key=lambda row:
            row.scheduled_date
    )

print("=" * 88)
print("C11.15.2 MONK SATURATED-WORLD EFFICIENCY CHECK")
print("=" * 88)

print(
    "initial_late_hours=",
    result.initial_objective.late_hours,
)
print(
    "final_late_hours=",
    result.final_objective.late_hours,
)
print(
    "infeasible_days=",
    result.final_objective.infeasible_day_count,
)
print(
    "infeasible_excess=",
    result.final_objective.infeasible_excess_hours,
)
print(
    "peak=",
    result.final_objective.max_daily_hours,
)
print(
    "priority_delay=",
    result.final_objective.priority_postponement_days,
)
print(
    "tiny_nonfinal=",
    result.final_objective.tiny_nonfinal_sessions,
)
print(
    "evaluations=",
    result.evaluations,
)
print(
    "accepted_moves=",
    len(result.accepted_moves),
)
print(
    "termination=",
    result.termination_reason,
)

print()
print("TODAY")

today = world.problem.today

for row in sorted(
    (
        row
        for row in schedule.work_allocations
        if row.scheduled_date == today
    ),
    key=lambda row:
        row.item_id,
):
    print(
        f"  #{row.item_id:02d} "
        f"{world.labels[row.item_id]} "
        f"{row.hours}h"
    )

print(
    "today_total=",
    schedule.daily_hours[today],
)
print(
    "today_status=",
    schedule.daily_status[today].value,
)

print()
print("KEY CHAINS / PRIORITY PAIR")

for item_id in (
    29,
    30,
    31,
    44,
    45,
    46,
):
    item = world.problem.item_by_id[
        item_id
    ]

    print(
        f"#{item_id:02d} "
        f"{world.labels[item_id]}"
        f" priority={item.priority_position}"
        f" due={item.due_date}"
    )

    print(
        "  "
        + ", ".join(
            f"{row.scheduled_date}:{row.hours}h"
            for row in by_item[item_id]
        )
    )

print()
print(
    "C11_15_2_ZERO_LATENESS_WITHIN_12K=",
    (
        result.final_objective.late_hours
        == 0
        and result.evaluations
        <= 12000
    ),
)
