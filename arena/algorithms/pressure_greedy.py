"""Pressure-led ordering with explicitly weighted date costs."""
from arena.algorithms.greedy import GreedyConstructor, ItemSelectionPolicy


class PressureGreedy(GreedyConstructor):
    name = 'pressure-greedy'
    item_policy = ItemSelectionPolicy.PRESSURE
