import pandas as pd
from app.engine.broker import SimulatedBroker
from app.engine.backtester import BacktestRunner


def _df(prices):
    return pd.DataFrame({
        "scripName": "TEST",
        "priceDate": pd.date_range("2024-01-01", periods=len(prices), freq="D"),
        "Value": prices,
        "Volume": [1000] * len(prices),
    })


class BuyAndHoldOnce:
    """Buys on bar 1 and never sells - used to test open-position valuation."""
    def __init__(self, broker):
        self.broker = broker
        self.bought = False

    def on_bar(self, df, i):
        if i == 1 and not self.bought:
            price = df.loc[i, "Value"]
            qty = int(self.broker.capital // price)
            self.broker.place_order("BUY", "TEST", price, qty, df.loc[i, "priceDate"])
            self.bought = True


def test_final_capital_includes_value_of_open_position():
    df = _df([100, 100, 110, 120, 130])  # price rises after the buy
    broker = SimulatedBroker(10000)
    runner = BacktestRunner(broker, BuyAndHoldOnce(broker))
    runner.load_data(df)
    results = runner.run()

    # All cash was spent buying at 100; shares are worth more at the final price of 130.
    assert results["open_position_value"] > 0
    assert results["final_capital"] > results["initial_capital"]
    assert results["roi"] > 0


def test_final_capital_matches_cash_when_no_open_position():
    df = _df([100, 105, 103, 108])
    broker = SimulatedBroker(10000)

    class NoOp:
        def on_bar(self, df, i):
            pass

    runner = BacktestRunner(broker, NoOp())
    runner.load_data(df)
    results = runner.run()

    assert results["open_position_value"] == 0
    assert results["final_capital"] == results["initial_capital"]
