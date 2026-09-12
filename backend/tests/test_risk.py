from app.live import risk


def test_daily_loss_limit_not_breached_under_limit():
    session = {"daily_loss_limit": 1000, "daily_realized_pnl": -500}
    breached, reason = risk.check_daily_loss_limit(session)
    assert breached is False
    assert reason is None


def test_daily_loss_limit_breached_at_exact_threshold():
    session = {"daily_loss_limit": 1000, "daily_realized_pnl": -1000}
    breached, reason = risk.check_daily_loss_limit(session)
    assert breached is True
    assert "1000" in reason


def test_no_daily_loss_limit_never_breaches():
    session = {"daily_loss_limit": None, "daily_realized_pnl": -999999}
    breached, _ = risk.check_daily_loss_limit(session)
    assert breached is False


def test_capital_exhausted_with_no_position():
    session = {"cash": 0.5, "positions": {}}
    breached, reason = risk.check_capital_exhausted(session)
    assert breached is True
    assert "exhausted" in reason.lower()


def test_capital_low_but_holding_position_not_exhausted():
    session = {"cash": 0.0, "positions": {"SBIN": {"qty": 10, "avg_price": 500}}}
    breached, _ = risk.check_capital_exhausted(session)
    assert breached is False


def test_rollover_resets_on_new_day():
    session = {"daily_date": "2020-01-01", "daily_realized_pnl": -500}
    risk.rollover_daily_pnl(session)
    assert session["daily_date"] != "2020-01-01"
    assert session["daily_realized_pnl"] == 0.0


def test_rollover_keeps_same_day_pnl():
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).date().isoformat()
    session = {"daily_date": today, "daily_realized_pnl": -500}
    risk.rollover_daily_pnl(session)
    assert session["daily_realized_pnl"] == -500
