"""Stability/risk regret family: movement and risk are explicit cost inputs."""
from arena.algorithms.greedy import GreedyConstructor


class StableRiskGreedy(GreedyConstructor):
    name = 'stable-risk-greedy'
