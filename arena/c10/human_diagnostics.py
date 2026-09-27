"""External C10 human-friendliness diagnostics.

These diagnostics observe frozen schedule outputs only. They are not part of
the search objective and must not be used to retune frozen C7-C9 candidates.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from math import log


@dataclass(frozen=True, slots=True)
class HumanDiagnostics:
    active_day_count: int
    total_session_count: int
    first_day_session_count: int
    max_sessions_on_day: int
    mean_sessions_per_active_day: float
    same_item_same_day_extra_session_count: int
    multi_session_same_day_item_count: int
    busy_day_count_ge_4: int
    busy_day_count_ge_6: int
    first_3_active_days_session_fraction: float
    first_week_session_fraction: float
    daily_session_entropy: float
    distinct_groups_per_active_day_mean: float
    mixed_group_day_count: int


def _entropy(counts: list[int]) -> float:
    total = sum(counts)

    if total <= 0:
        return 0.0

    value = 0.0

    for count in counts:
        if count <= 0:
            continue

        p = count / total
        value -= p * log(p)

    return value


def compute_human_diagnostics(
    rows: list[dict],
) -> HumanDiagnostics:
    if not rows:
        return HumanDiagnostics(
            active_day_count=0,
            total_session_count=0,
            first_day_session_count=0,
            max_sessions_on_day=0,
            mean_sessions_per_active_day=0.0,
            same_item_same_day_extra_session_count=0,
            multi_session_same_day_item_count=0,
            busy_day_count_ge_4=0,
            busy_day_count_ge_6=0,
            first_3_active_days_session_fraction=0.0,
            first_week_session_fraction=0.0,
            daily_session_entropy=0.0,
            distinct_groups_per_active_day_mean=0.0,
            mixed_group_day_count=0,
        )

    by_day = defaultdict(list)

    for row in rows:
        by_day[row["scheduled_date"]].append(
            row
        )

    days = sorted(by_day)

    counts = [
        len(by_day[day])
        for day in days
    ]

    total = sum(counts)

    first_day = date.fromisoformat(
        days[0]
    )

    first_week_cutoff_ordinal = (
        first_day.toordinal() + 6
    )

    first_week_count = sum(
        len(by_day[day])
        for day in days
        if date.fromisoformat(day).toordinal()
        <= first_week_cutoff_ordinal
    )

    first_3_count = sum(
        counts[:3]
    )

    same_item_day_counts = Counter(
        (
            row["scheduled_date"],
            row["item_key"],
        )
        for row in rows
    )

    multi_counts = [
        count
        for count
        in same_item_day_counts.values()
        if count > 1
    ]

    group_counts = [
        len({
            row["group"]
            for row in by_day[day]
        })
        for day in days
    ]

    return HumanDiagnostics(
        active_day_count=len(days),
        total_session_count=total,
        first_day_session_count=counts[0],
        max_sessions_on_day=max(counts),
        mean_sessions_per_active_day=(
            total / len(days)
        ),
        same_item_same_day_extra_session_count=
            sum(
                count - 1
                for count in multi_counts
            ),
        multi_session_same_day_item_count=
            len(multi_counts),
        busy_day_count_ge_4=sum(
            count >= 4
            for count in counts
        ),
        busy_day_count_ge_6=sum(
            count >= 6
            for count in counts
        ),
        first_3_active_days_session_fraction=(
            first_3_count / total
        ),
        first_week_session_fraction=(
            first_week_count / total
        ),
        daily_session_entropy=
            _entropy(counts),
        distinct_groups_per_active_day_mean=(
            sum(group_counts)
            / len(group_counts)
        ),
        mixed_group_day_count=sum(
            count > 1
            for count in group_counts
        ),
    )


def diagnostics_payload(
    diagnostics: HumanDiagnostics,
) -> dict:
    return {
        field: getattr(
            diagnostics,
            field,
        )
        for field
        in diagnostics.__dataclass_fields__
    }
