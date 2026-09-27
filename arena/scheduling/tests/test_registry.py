from arena.scheduling.domain import (
    SchedulePlan,
)
from arena.scheduling.registry import (
    algorithm,
    get_algorithm,
    registered_algorithms,
)


class TestAlgorithm:
    name = "c0-test-algorithm"

    def solve(self, problem):
        return SchedulePlan(allocations=())


def test_algorithm_registry():
    instance = TestAlgorithm()

    if instance.name not in registered_algorithms():
        algorithm(instance)

    assert get_algorithm(instance.name) is instance
    assert instance.name in registered_algorithms()
