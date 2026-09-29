"""Shared Focus ordering semantics.

This module contains no ARC database or UI dependency.

``anchor_order`` is a relative position within:
    (anchor date, Focus duration bucket)

It is NOT a requested global execution_rank.

The scheduler remains free to interleave Quick Wins, Side Quests and
Boss Fights while preserving explicit ordering inside each bucket.
"""

from __future__ import annotations


QUICK_WIN = "quick"
SIDE_QUEST = "side"
BOSS_FIGHT = "boss"


_DURATION_BUCKETS = {
    "UNDER_20_MINUTES":
        QUICK_WIN,
    "UNDER_1_HOUR":
        SIDE_QUEST,
    "UNDER_4_HOURS":
        BOSS_FIGHT,
    "UNDER_8_HOURS":
        BOSS_FIGHT,
    "UNDER_16_HOURS":
        BOSS_FIGHT,
    "OVER_16_HOURS":
        BOSS_FIGHT,
}


def focus_bucket_key(
    duration_category: str,
    *,
    is_residual: bool = False,
) -> str:
    """Return the scheduler-visible Focus presentation bucket.

    Residual closure work follows ARC's effective short-work semantics and
    therefore belongs to Quick Wins.
    """

    if is_residual:
        return QUICK_WIN

    try:
        return _DURATION_BUCKETS[
            duration_category
        ]
    except KeyError as exc:
        raise ValueError(
            "Unknown duration category for Focus ordering: "
            f"{duration_category!r}"
        ) from exc
