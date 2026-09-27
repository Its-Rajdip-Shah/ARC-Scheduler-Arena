"""Public contract enums.

These are deliberately independent from engine-internal enums so the external
contract does not expose implementation types.
"""

from enum import StrEnum


class SchedulerFlavourV1(StrEnum):
    LOCK_IN = "lock-in"
    MONK = "monk"


class LoadStatusV1(StrEnum):
    EMPTY = "empty"
    CHILL = "chill"
    NORMAL = "normal"
    LOCKED_IN = "locked-in"
    OVERLOADED = "overloaded"
    INFEASIBLE = "infeasible"
