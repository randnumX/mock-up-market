import pandas as pd


class BacktestRunner:
    """
    Feeds historical data into a Strategy bar-by-bar and collects
    an equity curve + trade history for the frontend to display.
    """

    def __init__(self, broker, strategy):
        self.broker = broker
        self.strategy = strategy
        self.data = pd.DataFrame()

    def load_data(self, data):
        """Load a DataFrame. Must have 'priceDate', 'Value', and 'scripName' columns."""
        self.data = data.copy()
        if "priceDate" in self.data.columns:
            self.data.sort_values(by=["priceDate"], inplace=True)
        self.data.reset_index(drop=True, inplace=True)

    def run(self):
        equity_curve = []

        for i in range(len(self.data)):
            self.strategy.on_bar(self.data, i)

            timestamp = self.data.loc[i, "priceDate"]
            current_price = self.data.loc[i, "Value"]
            symbol = self.data.loc[i].get("scripName", self.data.loc[i].get("Security Id", "UNKNOWN"))

            # Calculate total portfolio equity (cash + holdings at current price)
            equity = self.broker.capital
            pos = self.broker.positions.get(symbol, {"qty": 0})
            equity += pos["qty"] * current_price

            equity_curve.append({
                "time": str(timestamp),
                "equity": round(equity, 2),
                "price": round(current_price, 2),
            })

        # Mark any still-open position to the last traded price so a strategy
        # that ends the backtest mid-trade isn't scored as if those shares
        # evaporated - final equity is cash + market value of open holdings.
        last_price = self.data.iloc[-1]["Value"] if len(self.data) else 0
        open_position_value = sum(pos["qty"] * last_price for pos in self.broker.positions.values())
        final_equity = self.broker.capital + open_position_value

        roi = ((final_equity - self.broker.initial_capital) / self.broker.initial_capital) * 100

        # Calculate max drawdown
        peak = equity_curve[0]["equity"]
        max_dd = 0
        for point in equity_curve:
            if point["equity"] > peak:
                peak = point["equity"]
            dd = (peak - point["equity"]) / peak * 100
            if dd > max_dd:
                max_dd = dd

        # Win rate
        sells = [t for t in self.broker.history if t["type"] == "SELL"]
        wins = [t for t in sells if t.get("pnl", 0) > 0]
        win_rate = (len(wins) / len(sells) * 100) if sells else 0

        return {
            "initial_capital": round(self.broker.initial_capital, 2),
            "final_capital": round(final_equity, 2),
            "open_position_value": round(open_position_value, 2),
            "total_taxes": round(self.broker.total_taxes, 2),
            "realized_pnl": round(self.broker.realized_pnl, 2),
            "roi": round(roi, 2),
            "max_drawdown": round(max_dd, 2),
            "win_rate": round(win_rate, 2),
            "total_trades": len(self.broker.history),
            "trades": self.broker.history,
            "equity_curve": equity_curve,
        }
