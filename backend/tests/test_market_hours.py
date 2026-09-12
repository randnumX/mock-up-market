from datetime import datetime
from zoneinfo import ZoneInfo
from app.live.market_hours import is_market_open, IST


def _at(iso_datetime):
    return datetime.fromisoformat(iso_datetime).replace(tzinfo=IST)


def test_open_during_normal_trading_hours():
    assert is_market_open(_at("2026-09-14T11:00:00")) is False  # this is a holiday, see below
    assert is_market_open(_at("2026-09-15T11:00:00")) is True  # ordinary Tuesday, market hours


def test_closed_before_market_open():
    assert is_market_open(_at("2026-09-15T09:00:00")) is False


def test_closed_after_market_close():
    assert is_market_open(_at("2026-09-15T15:31:00")) is False


def test_closed_on_weekend():
    assert is_market_open(_at("2026-09-12T11:00:00")) is False  # Saturday
    assert is_market_open(_at("2026-09-13T11:00:00")) is False  # Sunday


def test_closed_on_republic_day_2026():
    assert is_market_open(_at("2026-01-26T11:00:00")) is False


def test_closed_on_christmas_2026():
    assert is_market_open(_at("2026-12-25T11:00:00")) is False


def test_open_on_ordinary_day_around_a_holiday():
    # Dussehra 2026-10-20 is a holiday; the very next trading day should not be.
    assert is_market_open(_at("2026-10-21T11:00:00")) is True


def test_closed_on_2025_holiday_diwali_balipratipada():
    assert is_market_open(_at("2025-10-22T11:00:00")) is False


def test_timezone_naive_datetime_is_treated_as_ist():
    now = datetime(2026, 9, 15, 11, 0, 0, tzinfo=ZoneInfo("UTC"))
    # 11:00 UTC = 16:30 IST -> after market close
    assert is_market_open(now) is False
