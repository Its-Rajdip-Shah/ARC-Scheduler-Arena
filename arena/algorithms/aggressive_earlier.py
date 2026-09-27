"""Proactive regret family: supply experimental timing and movement weights."""
from arena.algorithms.greedy import GreedyConstructor


class AggressiveEarlierGreedy(GreedyConstructor):
    name = 'aggressive-earlier-greedy'
