from app.live.broker import PaperBroker


def test_paper_broker_behaves_like_simulated_broker():
    broker = PaperBroker(100000)
    ok = broker.place_order("BUY", "SBIN", price=500, quantity=10, timestamp="t1")
    assert ok is True
    assert broker.positions["SBIN"]["qty"] == 10


def test_paper_broker_caps_buy_quantity_to_max_capital_per_trade():
    broker = PaperBroker(100000, max_capital_per_trade=1000)
    broker.place_order("BUY", "SBIN", price=500, quantity=10, timestamp="t1")
    # Requested 10 @ 500 = 5000, but capped to 1000 -> only 2 shares
    assert broker.positions["SBIN"]["qty"] == 2


def test_paper_broker_rejects_buy_when_cap_smaller_than_one_share():
    broker = PaperBroker(100000, max_capital_per_trade=100)
    ok = broker.place_order("BUY", "SBIN", price=500, quantity=10, timestamp="t1")
    assert ok is False
    assert "SBIN" not in broker.positions


def test_paper_broker_sell_is_not_capped():
    broker = PaperBroker(100000, max_capital_per_trade=1000)
    broker.place_order("BUY", "SBIN", price=500, quantity=2, timestamp="t1")
    ok = broker.place_order("SELL", "SBIN", price=550, quantity=2, timestamp="t2")
    assert ok is True
    assert "SBIN" not in broker.positions
