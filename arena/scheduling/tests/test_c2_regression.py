"""Full-plan regression fingerprint captured from the pre-C2 baseline."""
from dataclasses import replace
from datetime import timedelta
import hashlib
import random

from arena.algorithms.earliest_feasible import EarliestFeasible
from arena.scheduling.tests.test_mechanics import TODAY, item, problem


def regression_digest(solver):
    rng = random.Random(20260922)
    buckets = ('UNDER_20_MINUTES', 'UNDER_1_HOUR', 'UNDER_4_HOURS',
               'UNDER_8_HOURS', 'UNDER_16_HOURS', 'OVER_16_HOURS')
    results = []
    for case in range(120):
        items = tuple(item(pk, duration_category=rng.choice(buckets),
                           release_date=TODAY + timedelta(days=rng.randrange(4)),
                           due_date=None if pk % 3 else TODAY + timedelta(days=rng.randrange(7)),
                           anchor_date=None if pk % 4 else TODAY + timedelta(days=rng.randrange(5)),
                           is_residual=pk % 5 == 0)
                      for pk in range(1, 9))
        p = problem(*items, edges=((1, 3), (2, 3), (3, 6)),
                    capacity=case % 3, allowed=frozenset({TODAY + timedelta(days=2)}))
        if case % 10 == 0:
            p = replace(p, capacity_by_duration={})
        try:
            result = repr(solver.solve(p))
        except ValueError as exc:
            result = f'ValueError:{exc}'
        results.append(result)
    return hashlib.sha256('\n'.join(results).encode()).hexdigest()


def test_pre_c2_full_plan_regression():
    assert regression_digest(EarliestFeasible()) == '829cc8a2be4afbb94db150a714afca8edfec22e40611fcc7c04b118d6d87c219'
