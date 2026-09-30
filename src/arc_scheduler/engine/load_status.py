"""Human-facing workload status classification for C11 production schedules.

Statuses describe a generated schedule. They are not hard scheduling limits.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum
from calendar import monthrange


D = Decimal


class LoadStatus(StrEnum):
    EMPTY = "empty"
    CHILL = "chill"
    NORMAL = "normal"
    LOCKED_IN = "locked-in"
    OVERLOADED = "overloaded"
    INFEASIBLE = "infeasible"


@dataclass(frozen=True, slots=True)
class LoadBand:
    hours: Decimal
    status: LoadStatus


def classify_load(
    hours: Decimal,
    *,
    preferred_hours: Decimal,
    soft_max_hours: Decimal,
    physical_hours: Decimal,
) -> LoadStatus:
    hours = D(hours)

    if hours <= 0:
        return LoadStatus.EMPTY

    if hours > physical_hours:
        return LoadStatus.INFEASIBLE

    if hours <= preferred_hours * D("0.50"):
        return LoadStatus.CHILL

    if hours <= preferred_hours:
        return LoadStatus.NORMAL

    if hours <= soft_max_hours:
        return LoadStatus.LOCKED_IN

    return LoadStatus.OVERLOADED


def classify_day(
    hours: Decimal,
    *,
    preferred_daily_hours: Decimal,
    soft_max_daily_hours: Decimal,
) -> LoadStatus:
    return classify_load(
        hours,
        preferred_hours=preferred_daily_hours,
        soft_max_hours=soft_max_daily_hours,
        physical_hours=D("24"),
    )


def weekly_statuses(
    daily_hours: dict[date, Decimal],
    *,
    preferred_daily_hours: Decimal,
    soft_max_daily_hours: Decimal,
) -> dict[str, LoadBand]:
    by_week: dict[str, Decimal] = {}

    for day, hours in daily_hours.items():
        iso_year, iso_week, _ = day.isocalendar()
        key = f"{iso_year}-W{iso_week:02d}"

        by_week[key] = (
            by_week.get(key, D("0"))
            + hours
        )

    result = {}

    for key, hours in sorted(by_week.items()):
        result[key] = LoadBand(
            hours=hours,
            status=classify_load(
                hours,
                preferred_hours=preferred_daily_hours * D("7"),
                soft_max_hours=soft_max_daily_hours * D("7"),
                physical_hours=D("24") * D("7"),
            ),
        )

    return result


def monthly_statuses(
    daily_hours: dict[date, Decimal],
    *,
    preferred_daily_hours: Decimal,
    soft_max_daily_hours: Decimal,
) -> dict[str, LoadBand]:
    by_month: dict[tuple[int, int], Decimal] = {}

    for day, hours in daily_hours.items():
        key = (
            day.year,
            day.month,
        )

        by_month[key] = (
            by_month.get(key, D("0"))
            + hours
        )

    result = {}

    for (year, month), hours in sorted(
        by_month.items()
    ):
        days = D(
            monthrange(
                year,
                month,
            )[1]
        )

        key = f"{year:04d}-{month:02d}"

        result[key] = LoadBand(
            hours=hours,
            status=classify_load(
                hours,
                preferred_hours=preferred_daily_hours * days,
                soft_max_hours=soft_max_daily_hours * days,
                physical_hours=D("24") * days,
            ),
        )

    return result
