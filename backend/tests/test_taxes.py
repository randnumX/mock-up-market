from app.utils.taxes import calculate_taxes


def test_profitable_delivery_trade_has_positive_net_profit():
    result = calculate_taxes(buy_price=100, sell_price=120, quantity=10, is_intraday=False)
    assert result["gross_profit"] == 200
    assert result["net_profit"] < result["gross_profit"]
    assert result["net_profit"] > 0


def test_no_brokerage_on_delivery_trades():
    result = calculate_taxes(buy_price=100, sell_price=110, quantity=5, is_intraday=False)
    assert result["brokerage"] == 0.0


def test_intraday_trade_charges_brokerage():
    result = calculate_taxes(buy_price=100, sell_price=110, quantity=5, is_intraday=True)
    assert result["brokerage"] > 0


def test_total_charges_equals_sum_of_components():
    result = calculate_taxes(buy_price=250, sell_price=240, quantity=20, is_intraday=False)
    expected_total = (
        result["brokerage"] + result["stt"] + result["exchange_charges"]
        + result["gst"] + result["sebi_charges"] + result["stamp_duty"]
    )
    assert round(expected_total, 2) == round(result["total_charges"], 2)
