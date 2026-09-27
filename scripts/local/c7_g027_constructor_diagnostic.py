from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BACKEND))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "arc_backend.settings")

import django
django.setup()

from arena.benchmarks.reconstruct import reconstruct_v1_scenario
from arena.scheduling.mechanics import (
    ScheduleState,
    readiness,
    session_candidates,
    session_pieces,
)
from arena.scheduling.validation import validate_plan
from arena.search.state import SearchState, SessionPlacement
from arena.tuning.design import _constructors


SCENARIOS = ("G027-R0", "G027-R1")
HORIZON_DAYS = 30


def earliest_witness(problem):
    upper = problem.today + timedelta(days=HORIZON_DAYS)

    pieces_by_id = {
        item.item_id: session_pieces(item)
        for item in problem.items
    }

    completion = {}
    placements = []

    for item_id in problem.topological_order():
        item = problem.item_by_id[item_id]
        pieces = pieces_by_id[item_id]

        if not pieces:
            continue

        lower = max(
            problem.today,
            item.release_date or problem.today,
        )

        for prerequisite_id in sorted(
            problem.direct_prerequisites(item_id)
        ):
            if not pieces_by_id[prerequisite_id]:
                continue

            lower = max(
                lower,
                completion[prerequisite_id] + timedelta(days=1),
            )

        if item.anchor_date is not None:
            if item.anchor_date < lower:
                raise AssertionError(
                    f"Unexpected infeasible witness: "
                    f"item={item_id} "
                    f"anchor={item.anchor_date} "
                    f"lower={lower}"
                )

            if item.anchor_date > upper:
                raise AssertionError(
                    f"Unexpected anchor beyond horizon: "
                    f"item={item_id} "
                    f"anchor={item.anchor_date} "
                    f"horizon={upper}"
                )

            start = item.anchor_date

        else:
            if lower > upper:
                raise AssertionError(
                    f"Unexpected horizon failure: "
                    f"item={item_id} lower={lower}"
                )

            start = lower

        for index in range(len(pieces)):
            placements.append(
                SessionPlacement(
                    item_id=item_id,
                    session_index=index,
                    scheduled_date=start,
                )
            )

        completion[item_id] = start

    state = SearchState(
        problem=problem,
        placements=tuple(placements),
    )

    plan = state.to_plan()
    validation = validate_plan(problem, plan)

    if validation.violations or validation.infeasibilities:
        raise AssertionError(
            "Earliest witness failed validation: "
            f"violations={validation.violations}, "
            f"infeasibilities={validation.infeasibilities}"
        )

    return plan


def plan_map(plan):
    grouped = defaultdict(list)

    # Plans contain Allocation rows, not SessionPlacement rows.
    per_item_index = defaultdict(int)

    for allocation in plan.allocations:
        index = per_item_index[allocation.item_id]
        per_item_index[allocation.item_id] += 1

        grouped[allocation.item_id].append(
            {
                "session_index": index,
                "date": allocation.scheduled_date.isoformat(),
                "percentage": str(allocation.percentage),
                "execution_rank": allocation.execution_rank,
            }
        )

    return {
        str(item_id): values
        for item_id, values in sorted(grouped.items())
    }


def item_facts(problem, item_id):
    item = problem.item_by_id[item_id]

    return {
        "item_id": item_id,
        "release_date": (
            item.release_date.isoformat()
            if item.release_date
            else None
        ),
        "due_date": (
            item.due_date.isoformat()
            if item.due_date
            else None
        ),
        "anchor_date": (
            item.anchor_date.isoformat()
            if item.anchor_date
            else None
        ),
        "priority_position": item.priority_position,
        "session_count": len(session_pieces(item)),
        "prerequisites": sorted(
            problem.direct_prerequisites(item_id)
        ),
        "dependents": sorted(
            problem.direct_dependents(item_id)
        ),
    }


def first_difference(problem, witness_plan, constructor_plan):
    witness = plan_map(witness_plan)
    actual = plan_map(constructor_plan)

    all_ids = sorted(
        {int(k) for k in witness}
        | {int(k) for k in actual}
    )

    for item_id in all_ids:
        w = witness.get(str(item_id))
        a = actual.get(str(item_id))

        if w != a:
            return {
                "item": item_facts(problem, item_id),
                "witness": w,
                "constructor": a,
            }

    return None


def inspect_partial_state(problem, plan):
    """
    Constructor plans are emitted in legal construction order, so the
    partial ScheduleState can be reconstructed directly from allocations.
    """
    state = ScheduleState(
        problem=problem,
        allocations=plan.allocations,
    )

    horizon = problem.today + timedelta(days=HORIZON_DAYS)

    unresolved = []

    for item in sorted(
        problem.items,
        key=lambda x: x.item_id,
    ):
        pieces = session_pieces(item)

        if not pieces:
            continue

        completed_sessions = sum(
            allocation.item_id == item.item_id
            for allocation in state.allocations
        )

        if completed_sessions == len(pieces):
            continue

        ready = readiness(
            problem,
            state,
            item.item_id,
        )

        candidates = ()

        if ready.lower_bound is not None:
            candidates = session_candidates(
                state,
                item.item_id,
                horizon=horizon,
            )

        unresolved.append({
            **item_facts(problem, item.item_id),
            "completed_sessions": completed_sessions,
            "remaining_sessions": (
                len(pieces) - completed_sessions
            ),
            "readiness_lower_bound": (
                ready.lower_bound.isoformat()
                if ready.lower_bound
                else None
            ),
            "missing_prerequisites": sorted(
                ready.missing_prerequisites
            ),
            "calendar_exhausted": (
                ready.calendar_exhausted
            ),
            "candidate_count": len(candidates),
            "candidate_dates": [
                candidate.action.scheduled_date.isoformat()
                for candidate in candidates[:20]
            ],
        })

    return unresolved


def summarize_divergence(problem, witness, plan):
    witness_map = plan_map(witness)
    actual_map = plan_map(plan)

    missing_items = sorted(
        int(item_id)
        for item_id in witness_map
        if item_id not in actual_map
    )

    changed_items = []

    for item_id in sorted(
        set(witness_map) & set(actual_map),
        key=int,
    ):
        if witness_map[item_id] != actual_map[item_id]:
            changed_items.append(int(item_id))

    return {
        "missing_item_ids": missing_items,
        "changed_item_ids": changed_items,
        "missing_item_facts": [
            item_facts(problem, item_id)
            for item_id in missing_items
        ],
    }


def main():
    rows = []
    constructors = _constructors()

    print("=" * 100)
    print("G027 CONSTRUCTOR FAILURE DIAGNOSTIC")
    print("=" * 100)

    for scenario_id in SCENARIOS:
        reconstructed = reconstruct_v1_scenario(
            scenario_id
        )

        problem = reconstructed.problem
        witness = earliest_witness(problem)

        print()
        print("#" * 100)
        print(f"SCENARIO {scenario_id}")
        print("#" * 100)

        print(
            f"items={len(problem.items)} | "
            f"sessions="
            f"{sum(len(session_pieces(i)) for i in problem.items)} | "
            f"today={problem.today}"
        )

        print(
            f"witness_allocations="
            f"{len(witness.allocations)}"
        )

        for sweep in constructors:
            constructor = sweep.algorithm
            family_id = sweep.arm_id

            plan = constructor.solve(problem)
            validation = validate_plan(problem, plan)

            diff = first_difference(
                problem,
                witness,
                plan,
            )

            unresolved = inspect_partial_state(
                problem,
                plan,
            )

            divergence = summarize_divergence(
                problem,
                witness,
                plan,
            )

            print()
            print("-" * 100)
            print(
                f"{family_id.upper()} "
                f"({constructor.name})"
            )
            print("-" * 100)

            print(
                f"allocations={len(plan.allocations)} | "
                f"conflicts={len(plan.conflicts)} | "
                f"violations={len(validation.violations)} | "
                f"infeasibilities="
                f"{len(validation.infeasibilities)}"
            )

            print()
            print("CONFLICTS")

            if plan.conflicts:
                for conflict in plan.conflicts:
                    print(f"  {conflict}")
            else:
                print("  NONE")

            print()
            print("FIRST DIFFERENCE FROM FEASIBLE WITNESS")
            print(
                json.dumps(
                    diff,
                    indent=2,
                    sort_keys=True,
                )
            )

            print()
            print("DIVERGENCE SUMMARY")
            print(
                json.dumps(
                    divergence,
                    indent=2,
                    sort_keys=True,
                )
            )

            print()
            print("UNRESOLVED ITEMS AT CONSTRUCTOR STOP")
            print(
                json.dumps(
                    unresolved,
                    indent=2,
                    sort_keys=True,
                )
            )

            rows.append({
                "scenario_id": scenario_id,
                "constructor_family": family_id,
                "constructor_name": constructor.name,
                "diagnostics": dict(plan.diagnostics),
                "conflicts": list(plan.conflicts),
                "validation_violations": [
                    str(x)
                    for x in validation.violations
                ],
                "validation_infeasibilities": [
                    str(x)
                    for x in validation.infeasibilities
                ],
                "first_difference": diff,
                "divergence": divergence,
                "unresolved_items": unresolved,
                "constructor_allocations": plan_map(plan),
                "witness_allocations": plan_map(witness),
            })

    output = (
        Path.home()
        / "Desktop"
        / "ARC_C7_G027_CONSTRUCTOR_DIAGNOSTIC.json"
    )

    output.write_text(
        json.dumps(
            {
                "scenarios": list(SCENARIOS),
                "rows": rows,
            },
            indent=2,
            sort_keys=True,
        ) + "\n",
        encoding="utf-8",
    )

    print()
    print("=" * 100)
    print("DONE")
    print("=" * 100)
    print(f"OUTPUT={output}")


if __name__ == "__main__":
    main()
