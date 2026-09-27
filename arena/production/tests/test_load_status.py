from datetime import date
from decimal import Decimal

from arena.production.load_status import (
    LoadStatus,
    classify_day,
    monthly_statuses,
    weekly_statuses,
)


D = Decimal


def test_lock_in_day_status_bands():
    args = {
        "preferred_daily_hours": D("8"),
        "soft_max_daily_hours": D("10"),
    }

    assert classify_day(D("0"), **args) == LoadStatus.EMPTY
    assert classify_day(D("4"), **args) == LoadStatus.CHILL
    assert classify_day(D("6"), **args) == LoadStatus.NORMAL
    assert classify_day(D("9"), **args) == LoadStatus.LOCKED_IN
    assert classify_day(D("12"), **args) == LoadStatus.OVERLOADED
    assert classify_day(D("30"), **args) == LoadStatus.INFEASIBLE


def test_monk_day_status_bands():
    args = {
        "preferred_daily_hours": D("6"),
        "soft_max_daily_hours": D("8"),
    }

    assert classify_day(D("0"), **args) == LoadStatus.EMPTY
    assert classify_day(D("3"), **args) == LoadStatus.CHILL
    assert classify_day(D("5"), **args) == LoadStatus.NORMAL
    assert classify_day(D("7"), **args) == LoadStatus.LOCKED_IN
    assert classify_day(D("10"), **args) == LoadStatus.OVERLOADED
    assert classify_day(D("25"), **args) == LoadStatus.INFEASIBLE


def test_week_and_month_statuses_use_same_scaled_model():
    daily = {
        date(2026, 10, 12): D("10"),
        date(2026, 10, 13): D("10"),
        date(2026, 10, 14): D("10"),
        date(2026, 10, 15): D("10"),
        date(2026, 10, 16): D("10"),
    }

    weeks = weekly_statuses(
        daily,
        preferred_daily_hours=D("6"),
        soft_max_daily_hours=D("8"),
    )

    months = monthly_statuses(
        daily,
        preferred_daily_hours=D("6"),
        soft_max_daily_hours=D("8"),
    )

    assert "2026-W42" in weeks
    assert "2026-10" in months
