"""Scheduling-algorithm protocol and explicit registry."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from arena.scheduling.domain import (
    SchedulePlan,
    ScheduleProblem,
)


@runtime_checkable
class SchedulingAlgorithm(Protocol):
    """Pure algorithm boundary."""

    name: str

    def solve(
        self,
        problem: ScheduleProblem,
    ) -> SchedulePlan:
        ...


_REGISTRY: dict[str, SchedulingAlgorithm] = {}


def algorithm(instance: SchedulingAlgorithm) -> SchedulingAlgorithm:
    """Register one algorithm instance by unique stable name."""

    if not isinstance(instance, SchedulingAlgorithm):
        raise TypeError(
            "Registered object does not satisfy SchedulingAlgorithm."
        )

    if not instance.name:
        raise ValueError("Algorithm name cannot be empty.")

    if instance.name in _REGISTRY:
        raise ValueError(
            f"Algorithm already registered: {instance.name}"
        )

    _REGISTRY[instance.name] = instance
    return instance


def get_algorithm(name: str) -> SchedulingAlgorithm:
    try:
        return _REGISTRY[name]
    except KeyError as exc:
        raise KeyError(
            f"Unknown scheduling algorithm: {name}"
        ) from exc


def registered_algorithms() -> tuple[str, ...]:
    return tuple(sorted(_REGISTRY))
