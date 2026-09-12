from app.utils.taxes import calculate_taxes


class SimulatedBroker:
    """
    Simulated broker for backtesting and paper trading.
    Tracks portfolio, executes mock trades, and deducts realistic taxes.
    """

    def __init__(self, initial_capital):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.positions = {}  # symbol -> {"qty": int, "avg_price": float}
        self.history = []
        self.realized_pnl = 0
        self.total_taxes = 0

    def place_order(self, order_type, symbol, price, quantity, timestamp, is_intraday=False):
        if order_type == "BUY":
            cost = price * quantity
            if self.capital >= cost:
                self.capital -= cost

                pos = self.positions.get(symbol, {"qty": 0, "avg_price": 0})
                total_cost = (pos["qty"] * pos["avg_price"]) + cost
                new_qty = pos["qty"] + quantity

                self.positions[symbol] = {
                    "qty": new_qty,
                    "avg_price": total_cost / new_qty if new_qty > 0 else 0,
                }

                self.history.append({
                    "type": "BUY",
                    "symbol": symbol,
                    "price": price,
                    "qty": quantity,
                    "timestamp": str(timestamp),
                })
                return True

        elif order_type == "SELL":
            pos = self.positions.get(symbol, {"qty": 0, "avg_price": 0})
            if pos["qty"] >= quantity:
                avg_buy_price = pos["avg_price"]

                # Update position
                pos["qty"] -= quantity
                if pos["qty"] == 0:
                    del self.positions[symbol]
                else:
                    self.positions[symbol] = pos

                revenue = price * quantity
                self.capital += revenue

                # Calculate taxes and realized PnL
                tax_details = calculate_taxes(avg_buy_price, price, quantity, is_intraday)
                self.capital -= tax_details["total_charges"]
                self.realized_pnl += tax_details["net_profit"]
                self.total_taxes += tax_details["total_charges"]

                self.history.append({
                    "type": "SELL",
                    "symbol": symbol,
                    "price": price,
                    "qty": quantity,
                    "timestamp": str(timestamp),
                    "pnl": round(tax_details["net_profit"], 2),
                    "taxes": round(tax_details["total_charges"], 2),
                })
                return True
        return False

    def get_portfolio_value(self, current_prices):
        val = self.capital
        for sym, pos in self.positions.items():
            val += pos["qty"] * current_prices.get(sym, pos["avg_price"])
        return val
