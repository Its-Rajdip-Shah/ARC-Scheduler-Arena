from arena.search import SearchState, SessionPlacement, PlanObjectiveConfig
from arena.scheduling.tests.test_mechanics import TODAY, DAY, item, problem
from arena.algorithms.tests.test_greedy import config


def state(p, *days):
    return SearchState(p, tuple(SessionPlacement(pk, k, TODAY + d * DAY)
                               for pk, offsets in enumerate(days, 1)
                               for k, d in enumerate(offsets)))


def objective(**kwargs):
    c = config(**kwargs)
    return PlanObjectiveConfig(c.deadline, c.priority, c.overload, c.movement, c.timing)
