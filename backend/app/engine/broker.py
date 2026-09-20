from app.utils.taxes import calculate_taxes


class SimulatedBroker:
    """
    Simulated broker for backtesting and paper trading.
    Tracks portfolio, executes mock trades, and deducts realistic taxes.
    """

    def __init__(self, initial_capital, max_capital_per_trade=None):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.max_capital_per_trade = max_capital_per_trade
        self.positions = {}  # symbol -> {"qty": int, "avg_price": float}
        self.history = []
        self.realized_pnl = 0
        self.total_taxes = 0

    def place_order(self, order_type, symbol, price, quantity, timestamp, is_intraday=False):
        if order_type == "BUY":
            if self.max_capital_per_trade:
                quantity = min(quantity, int(self.max_capital_per_trade // price))
            if quantity <= 0:
                return False

            pos = self.positions.get(symbol, {"qty": 0, "avg_price": 0})

            if pos["qty"] < 0:
                return self._cover_short(symbol, price, quantity, timestamp, is_intraday)

            cost = price * quantity
            if self.capital >= cost:
                self.capital -= cost

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
            elif pos["qty"] <= 0:
                return self._open_or_add_short(symbol, price, quantity, timestamp)
        return False

    def _open_or_add_short(self, symbol, price, quantity, timestamp):
        """Sell with no (or an existing) short position: opens or grows a short."""
        pos = self.positions.get(symbol, {"qty": 0, "avg_price": 0})
        self.capital += price * quantity

        existing_short_qty = -pos["qty"]
        total_proceeds = existing_short_qty * pos["avg_price"] + quantity * price
        new_short_qty = existing_short_qty + quantity

        self.positions[symbol] = {
            "qty": -new_short_qty,
            "avg_price": total_proceeds / new_short_qty if new_short_qty > 0 else 0,
        }

        self.history.append({
            "type": "SELL",
            "symbol": symbol,
            "price": price,
            "qty": quantity,
            "timestamp": str(timestamp),
        })
        return True

    def _cover_short(self, symbol, price, quantity, timestamp, is_intraday):
        """Buy against an existing short position: covers it (fully or partially)."""
        pos = self.positions[symbol]
        short_avg_price = pos["avg_price"]
        cover_qty = min(quantity, -pos["qty"])

        self.capital -= price * cover_qty

        tax_details = calculate_taxes(price, short_avg_price, cover_qty, is_intraday)
        self.capital -= tax_details["total_charges"]
        self.realized_pnl += tax_details["net_profit"]
        self.total_taxes += tax_details["total_charges"]

        new_qty = pos["qty"] + cover_qty
        if new_qty == 0:
            del self.positions[symbol]
        else:
            self.positions[symbol] = {"qty": new_qty, "avg_price": short_avg_price}

        self.history.append({
            "type": "BUY",
            "symbol": symbol,
            "price": price,
            "qty": cover_qty,
            "timestamp": str(timestamp),
            "pnl": round(tax_details["net_profit"], 2),
            "taxes": round(tax_details["total_charges"], 2),
        })
        return True

    def get_portfolio_value(self, current_prices):
        val = self.capital
        for sym, pos in self.positions.items():
            val += pos["qty"] * current_prices.get(sym, pos["avg_price"])
        return val
