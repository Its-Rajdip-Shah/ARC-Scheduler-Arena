"""Policy fixtures: explicit experimental settings, never quality rankings."""
from dataclasses import replace
import hashlib
import os
import subprocess
import sys

import pytest

from arena.algorithms import (
    AggressiveEarlierGreedy, HybridCostGreedy, PressureGreedy, StableRiskGreedy,
)
from arena.algorithms.tests.test_greedy import config
from arena.scheduling.tests.test_mechanics import TODAY, DAY, item, problem
from arena.scheduling.validation import validate_plan

FAMILIES = (PressureGreedy, AggressiveEarlierGreedy, StableRiskGreedy, HybridCostGreedy)


def mini_corpus():
    return (
        problem(item(1, duration_category='UNDER_8_HOURS', release_date=TODAY + DAY),
                item(2, anchor_date=TODAY + 3 * DAY), item(3), edges=((1, 3),)),
        problem(item(1, due_date=TODAY), item(2, due_date=TODAY), capacity=0),
        problem(item(1, existing_scheduled_date=TODAY + 4 * DAY)),
        problem(item(1, duration_category='OVER_16_HOURS', anchor_date=TODAY,
                     due_date=TODAY + 3 * DAY),
                item(2, duration_category='OVER_16_HOURS', release_date=TODAY + DAY,
                     due_date=TODAY + 2 * DAY)),
    )


@pytest.mark.parametrize('family', FAMILIES)
def test_valid_repeated_runs_dependencies_release_anchors(family):
    solver = family(config(timing=1, movement=2, risk=1))
    for p in mini_corpus():
        plan = solver.solve(p)
        assert validate_plan(p, plan).is_valid
        assert repr(plan) == repr(solver.solve(p))
        assert plan.conflicts == ()
        # Stable IDs, not input collection iteration order, determine decisions.
        assert plan == solver.solve(replace(p, items=tuple(reversed(p.items))))
    p = mini_corpus()[0]
    plan = solver.solve(p)
    assert min(a.scheduled_date for a in plan.allocations_for(1)) >= TODAY + DAY
    assert plan.allocations_for(2)[0].scheduled_date == TODAY + 3 * DAY
    assert plan.allocations_for(3)[0].scheduled_date >= max(a.scheduled_date for a in plan.allocations_for(1)) + DAY


def test_explicit_family_settings_produce_three_distinct_valid_plans():
    p = problem(item(existing_scheduled_date=TODAY + 4 * DAY))
    solvers = (
        AggressiveEarlierGreedy(config(timing=10, movement=0)),
        StableRiskGreedy(config(timing=0, movement=10)),
        HybridCostGreedy(config(timing=1, movement=1)),
    )
    plans = [solver.solve(p) for solver in solvers]
    assert [plan.allocations[0].scheduled_date for plan in plans] == [TODAY, TODAY + 4 * DAY, TODAY + 2 * DAY]
    assert all(validate_plan(p, plan).is_valid for plan in plans)
    # Identical weights intentionally mean identical mechanics in cost families.
    # Labels do not secretly inject supposedly optimal coefficients.
    cfg = config(timing=1, movement=1)
    assert len({repr(f(cfg).solve(p).allocations) for f in FAMILIES[1:]}) == 1


def test_hybrid_weights_alone_change_plan_and_movement_can_be_disabled():
    p = problem(item(existing_scheduled_date=TODAY + 4 * DAY))
    stable = config(movement=10, timing=1)
    assert HybridCostGreedy(stable).solve(p).allocations[0].scheduled_date == TODAY + 4 * DAY
    proactive = replace(stable, movement=config(movement=0).movement)
    assert HybridCostGreedy(proactive).solve(p).allocations[0].scheduled_date == TODAY


@pytest.mark.parametrize('family', FAMILIES)
def test_all_families_expose_horizon_and_partial_proposals(family):
    p = problem(item(release_date=TODAY + DAY))
    plan = family(config(horizon=0)).solve(p)
    assert plan.allocations == ()
    assert plan.conflicts == ('1:no_candidate_within_horizon',)
    assert dict(plan.diagnostics)['constructor'] == family.name
    assert dict(plan.diagnostics)['horizon_days'] == '0'
    assert family(config(horizon=1)).solve(p).allocations[0].scheduled_date == TODAY + DAY


def test_public_imports_are_django_and_evaluator_free():
    env = dict(os.environ)
    env.pop('DJANGO_SETTINGS_MODULE', None)
    subprocess.run([sys.executable, '-c',
                    'from arena.algorithms import EarliestFeasible, PressureGreedy, '
                    'AggressiveEarlierGreedy, StableRiskGreedy, HybridCostGreedy, '
                    'GreedyConstructor, GreedyObjectiveConfig, ItemSelectionPolicy; '
                    'import sys; assert not any(m == "django" or m.startswith("django.") for m in sys.modules); '
                    'assert "arena.evaluation.performance" not in sys.modules'], check=True, env=env)


def test_constructor_family_regression():
    settings = (config(timing=1), config(timing=10), config(movement=10, risk=1),
                config(timing=1, movement=1, risk=1))
    results = [repr(f(cfg).solve(p)) for f, cfg in zip(FAMILIES, settings, strict=True)
               for p in mini_corpus()]
    assert hashlib.sha256('\n'.join(results).encode()).hexdigest() == '8613c8bcfd3a76994905ca18cf921ac3afd516fa0d444a3c55fd00ce4a9cfcfc'
