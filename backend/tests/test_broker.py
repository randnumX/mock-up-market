from app.engine.broker import SimulatedBroker


def test_buy_reduces_cash_and_opens_position():
    broker = SimulatedBroker(100000)
    ok = broker.place_order("BUY", "SBIN", price=500, quantity=10, timestamp="2024-01-01")
    assert ok is True
    assert broker.capital == 100000 - 5000
    assert broker.positions["SBIN"]["qty"] == 10


def test_buy_fails_when_insufficient_capital():
    broker = SimulatedBroker(1000)
    ok = broker.place_order("BUY", "SBIN", price=500, quantity=10, timestamp="2024-01-01")
    assert ok is False
    assert broker.capital == 1000


def test_sell_closes_position_and_applies_taxes():
    broker = SimulatedBroker(100000)
    broker.place_order("BUY", "SBIN", price=500, quantity=10, timestamp="2024-01-01")
    ok = broker.place_order("SELL", "SBIN", price=550, quantity=10, timestamp="2024-01-02")
    assert ok is True
    assert "SBIN" not in broker.positions
    assert broker.total_taxes > 0
    assert broker.realized_pnl == round(broker.realized_pnl, 2)


def test_sell_fails_when_no_position():
    broker = SimulatedBroker(100000)
    ok = broker.place_order("SELL", "SBIN", price=550, quantity=10, timestamp="2024-01-02")
    assert ok is False


def test_partial_sell_keeps_remaining_position():
    broker = SimulatedBroker(100000)
    broker.place_order("BUY", "SBIN", price=500, quantity=10, timestamp="2024-01-01")
    broker.place_order("SELL", "SBIN", price=550, quantity=4, timestamp="2024-01-02")
    assert broker.positions["SBIN"]["qty"] == 6
