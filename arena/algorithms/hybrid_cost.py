"""General regret family for experimental trade-offs across all five costs."""
from arena.algorithms.greedy import GreedyConstructor


class HybridCostGreedy(GreedyConstructor):
    name = 'hybrid-cost-greedy'
