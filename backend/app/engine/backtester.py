import pandas as pd


class BacktestRunner:
    """
    Feeds historical data into Strategies bar-by-bar across multiple tickers, 
    collecting an equity curve + trade history for the frontend to display.
    """

    def __init__(self, broker, strategy_class, position_sizer=None, daily_loss_limit=None):
        self.broker = broker
        self.strategy_class = strategy_class
        self.position_sizer = position_sizer
        self.daily_loss_limit = daily_loss_limit
        
        self.dfs = {}
        self.strategies = {}
        self.timeline = []
        self.latest_prices = {}
        
        self.is_halted_for_day = False
        self.current_day_str = None
        self.start_of_day_equity = None

    def load_data(self, ticker, data):
        """Load a DataFrame for a specific ticker."""
        df = data.copy()
        if "priceDate" in df.columns:
            df.sort_values(by=["priceDate"], inplace=True)
        df.reset_index(drop=True, inplace=True)
        self.dfs[ticker] = df

    def _build_timeline(self):
        events = []
        for ticker, df in self.dfs.items():
            self.strategies[ticker] = self.strategy_class(self.broker, position_sizer=self.position_sizer)
            # Make sure the strategy tracks its own state
            self.strategies[ticker].bought = False 
            
            for i in range(len(df)):
                events.append((df.loc[i, "priceDate"], ticker, i))
        
        # Sort by time chronologically across all tickers
        events.sort(key=lambda x: str(x[0]))
        self.timeline = events

    def _step(self, event):
        """Advance the strategy by one bar for one ticker. Returns (equity_point, new_trades)."""
        timestamp, ticker, i = event
        df = self.dfs[ticker]
        current_price = df.loc[i, "Value"]
        self.latest_prices[ticker] = current_price
        
        day_str = str(timestamp)[:10]
        if day_str != self.current_day_str:
            self.current_day_str = day_str
            self.is_halted_for_day = False
            self.start_of_day_equity = self.broker.get_portfolio_value(self.latest_prices)

        equity = self.broker.get_portfolio_value(self.latest_prices)
        
        if self.daily_loss_limit and not self.is_halted_for_day:
            daily_pnl = equity - self.start_of_day_equity
            if daily_pnl <= -self.daily_loss_limit:
                self.is_halted_for_day = True

        trades_before = len(self.broker.history)
        if not self.is_halted_for_day:
            # Inform the strategy of its own ticker's state
            self.strategies[ticker].on_bar(df, i)
        new_trades = self.broker.history[trades_before:]

        point = {
            "time": str(timestamp),
            "equity": round(equity, 2),
            "price": round(current_price, 2),
            "ticker": ticker
        }
        return point, new_trades

    def _finalize(self, equity_curve):
        open_position_value = sum(pos["qty"] * self.latest_prices.get(sym, pos["avg_price"]) for sym, pos in self.broker.positions.items())
        open_position_cost = sum(pos["qty"] * pos["avg_price"] for sym, pos in self.broker.positions.items())
        unrealized_pnl = open_position_value - open_position_cost
        final_equity = self.broker.capital + open_position_value

        roi = ((final_equity - self.broker.initial_capital) / self.broker.initial_capital) * 100 if self.broker.initial_capital else 0

        # Calculate max drawdown from the aggregate equity curve
        peak = equity_curve[0]["equity"] if equity_curve else 0
        max_dd = 0
        for point in equity_curve:
            if point["equity"] > peak:
                peak = point["equity"]
            dd = (peak - point["equity"]) / peak * 100 if peak else 0
            if dd > max_dd:
                max_dd = dd

        # Win rate
        sells = [t for t in self.broker.history if t["type"] == "SELL"]
        wins = [t for t in sells if t.get("pnl", 0) > 0]
        win_rate = (len(wins) / len(sells) * 100) if sells else 0
        
        # Calculate individual ticker stats
        ticker_stats = {}
        for sym, df in self.dfs.items():
            sym_trades = [t for t in self.broker.history if t["symbol"] == sym]
            sym_sells = [t for t in sym_trades if t["type"] == "SELL"]
            sym_wins = [t for t in sym_sells if t.get("pnl", 0) > 0]
            
            # PnL logic for ticker
            sym_realized_pnl = sum(t.get("pnl", 0) for t in sym_sells)
            sym_win_rate = (len(sym_wins) / len(sym_sells) * 100) if sym_sells else 0
            
            # Ticker prices for plotting Price chart
            # We map the DataFrame to a list of dicts: [{"time": "2024-01-01", "price": 100.0}, ...]
            sym_prices = []
            for _, row in df.iterrows():
                sym_prices.append({
                    "time": str(row["priceDate"]),
                    "price": round(float(row["Value"]), 2)
                })
                
            ticker_stats[sym] = {
                "total_trades": len(sym_trades),
                "win_rate": round(sym_win_rate, 2),
                "realized_pnl": round(sym_realized_pnl, 2),
                "prices": sym_prices
            }

        return {
            "initial_capital": round(self.broker.initial_capital, 2),
            "final_capital": round(final_equity, 2),
            "open_position_value": round(open_position_value, 2),
            "unrealized_pnl": round(unrealized_pnl, 2),
            "total_taxes": round(self.broker.total_taxes, 2),
            "realized_pnl": round(self.broker.realized_pnl, 2),
            "roi": round(roi, 2),
            "max_drawdown": round(max_dd, 2),
            "win_rate": round(win_rate, 2),
            "total_trades": len(self.broker.history),
            "trades": self.broker.history,
            "equity_curve": equity_curve,
            "ticker_stats": ticker_stats,
        }

    def run(self):
        self._build_timeline()
        equity_curve = []
        last_timestamp = None
        
        for event in self.timeline:
            timestamp = event[0]
            point, _ = self._step(event)
            if timestamp != last_timestamp:
                equity_curve.append(point)
                last_timestamp = timestamp
            else:
                equity_curve[-1] = point
                
        return self._finalize(equity_curve)

    def run_streaming(self):
        self._build_timeline()
        equity_curve = []
        total = len(self.timeline)
        last_timestamp = None
        
        for idx, event in enumerate(self.timeline):
            timestamp = event[0]
            point, new_trades = self._step(event)
            
            if timestamp != last_timestamp:
                equity_curve.append(point)
                yield {"type": "tick", "index": idx, "total": total, "point": point, "new_trades": new_trades}
                last_timestamp = timestamp
            else:
                equity_curve[-1] = point
                if new_trades:
                    yield {"type": "tick", "index": idx, "total": total, "point": point, "new_trades": new_trades}
                    
        yield {"type": "done", "result": self._finalize(equity_curve)}
