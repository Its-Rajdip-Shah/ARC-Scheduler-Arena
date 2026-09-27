"""Historical fingerprints and independent hard-legality checks."""
import hashlib
import os
import subprocess
import sys
import pytest

from arena.algorithms import EarliestFeasible, PressureGreedy, StableRiskGreedy, HybridCostGreedy
from arena.algorithms.tests.test_constructor_zoo import FAMILIES, mini_corpus
from arena.algorithms.tests.test_greedy import config as greedy_config
from arena.scheduling.tests.test_c2_regression import regression_digest
from arena.scheduling.validation import validate_plan
from arena.search import (
    HillClimber, HillClimbConfig, ImprovementStrategy, NeighbourhoodConfig,
    VariableNeighbourhoodConfig, VariableNeighbourhoodMode, VariableNeighbourhoodSearch,
    TabuConfig, TabuSearch, SimulatedAnnealingConfig, SimulatedAnnealing,
)
from .helpers import item, problem, state, objective


def engines():
    cost, neighbourhood = objective(timing=1, movement=1, risk=1), NeighbourhoodConfig(5)
    return (
        VariableNeighbourhoodSearch(VariableNeighbourhoodConfig(cost, neighbourhood,
            VariableNeighbourhoodMode.VND, max_iterations=8, max_evaluations=100)),
        TabuSearch(TabuConfig(cost, neighbourhood, 3, max_iterations=8, max_evaluations=100)),
        SimulatedAnnealing(SimulatedAnnealingConfig(cost, neighbourhood, 10, .8, .01,
            seed=4, max_iterations=8, max_evaluations=100)),
    )


@pytest.mark.parametrize('constructor', [PressureGreedy, StableRiskGreedy, HybridCostGreedy])
@pytest.mark.parametrize('engine', engines())
def test_constructor_roundtrip_and_independent_validation(constructor, engine):
    for p in mini_corpus():
        plan = constructor(greedy_config(timing=1, movement=2, risk=1)).solve(p)
        before = repr((p, plan))
        result = engine.improve_plan(p, plan)
        direct = engine.improve_state(result.initial_state)
        assert direct == result and direct.initial_state is result.initial_state
        for output in (result.final_state, getattr(result, 'last_state', result.final_state)):
            assert output.problem is p
            validation = validate_plan(p, output.to_plan())
            assert validation.violations == validation.infeasibilities == ()
        assert repr((p, plan)) == before


def test_hill_climbing_trajectory_tripwire():
    initial = state(problem(item(1), item(2)), (2,), (2,))
    for strategy in ImprovementStrategy:
        result = HillClimber(HillClimbConfig(objective(timing=1, overload=0),
            NeighbourhoodConfig(4), strategy)).improve_state(initial)
        assert result.objective_history == (8, 4, 0)
        assert result.iterations == 3 and result.accepted_moves == 2
        assert result.termination_reason == 'local_optimum'


def test_frozen_c2_digest():
    assert regression_digest(EarliestFeasible()) == '829cc8a2be4afbb94db150a714afca8edfec22e40611fcc7c04b118d6d87c219'


def test_frozen_c3_fingerprint():
    configs = (greedy_config(timing=1), greedy_config(timing=10),
               greedy_config(movement=10, risk=1), greedy_config(timing=1, movement=1, risk=1))
    rows = [repr(f(c).solve(p)) for f, c in zip(FAMILIES, configs, strict=True) for p in mini_corpus()]
    assert hashlib.sha256('\n'.join(rows).encode()).hexdigest() == '8613c8bcfd3a76994905ca18cf921ac3afd516fa0d444a3c55fd00ce4a9cfcfc'


def test_standalone_import():
    env = dict(os.environ)
    env.pop('DJANGO_SETTINGS_MODULE', None)
    subprocess.run([sys.executable, '-c',
        'from arena.search import VariableNeighbourhoodSearch, TabuSearch, SimulatedAnnealing; '
        'import sys; assert not any(k == "django" or k.startswith("django.") for k in sys.modules); '
        'assert "arena.evaluation.performance" not in sys.modules'], env=env, check=True)
