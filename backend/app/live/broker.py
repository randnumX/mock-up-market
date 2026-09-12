"""
Two broker implementations for the live engine, sharing the exact same
place_order(...) signature the Strategy classes already call in backtests:

- PaperBroker: virtual money, real-time prices, zero financial risk.
  Reuses SimulatedBroker's tax-aware fill logic unchanged.
- KiteLiveBroker: places REAL orders on the connected Zerodha account.
  Local capital/positions are a best-effort mirror for the dashboard;
  Kite itself is the source of truth for actual fills/holdings.

Both respect an optional per-trade capital cap (risk control), clamping
order size down rather than rejecting the signal outright.
"""
from app.engine.broker import SimulatedBroker


class PaperBroker(SimulatedBroker):
    mode = "paper"

    def __init__(self, capital, max_capital_per_trade=None):
        super().__init__(capital)
        self.max_capital_per_trade = max_capital_per_trade

    def place_order(self, order_type, symbol, price, quantity, timestamp, is_intraday=False):
        if order_type == "BUY" and self.max_capital_per_trade:
            quantity = min(quantity, int(self.max_capital_per_trade // price))
            if quantity <= 0:
                return False
        return super().place_order(order_type, symbol, price, quantity, timestamp, is_intraday)


class KiteLiveBroker:
    mode = "live"

    def __init__(self, kite, capital, max_capital_per_trade=None):
        self.kite = kite
        self.initial_capital = capital
        self.capital = capital
        self.positions = {}
        self.history = []
        self.realized_pnl = 0
        self.total_taxes = 0
        self.max_capital_per_trade = max_capital_per_trade

    def place_order(self, order_type, symbol, price, quantity, timestamp, is_intraday=False):
        if order_type == "SELL":
            pos = self.positions.get(symbol, {"qty": 0})
            quantity = min(quantity, pos["qty"])
        elif self.max_capital_per_trade:
            quantity = min(quantity, int(self.max_capital_per_trade // price))

        if quantity <= 0:
            return False

        transaction_type = self.kite.TRANSACTION_TYPE_BUY if order_type == "BUY" else self.kite.TRANSACTION_TYPE_SELL
        product = self.kite.PRODUCT_MIS if is_intraday else self.kite.PRODUCT_CNC

        try:
            self.kite.place_order(
                variety=self.kite.VARIETY_REGULAR,
                exchange=self.kite.EXCHANGE_NSE,
                tradingsymbol=symbol,
                transaction_type=transaction_type,
                quantity=quantity,
                order_type=self.kite.ORDER_TYPE_MARKET,
                product=product,
            )
        except Exception as e:
            self.history.append({
                "type": order_type, "symbol": symbol, "price": price, "qty": quantity,
                "timestamp": str(timestamp), "error": str(e),
            })
            return False

        # Best-effort local mirror for the dashboard; Kite's own positions()
        # call remains the authoritative source of truth.
        if order_type == "BUY":
            cost = price * quantity
            self.capital -= cost
            pos = self.positions.get(symbol, {"qty": 0, "avg_price": 0})
            total_cost = pos["qty"] * pos["avg_price"] + cost
            new_qty = pos["qty"] + quantity
            self.positions[symbol] = {"qty": new_qty, "avg_price": total_cost / new_qty if new_qty else 0}
        else:
            pos = self.positions.get(symbol, {"qty": 0, "avg_price": 0})
            pos["qty"] = max(0, pos["qty"] - quantity)
            if pos["qty"] == 0:
                self.positions.pop(symbol, None)
            else:
                self.positions[symbol] = pos
            self.capital += price * quantity

        self.history.append({
            "type": order_type, "symbol": symbol, "price": price, "qty": quantity,
            "timestamp": str(timestamp),
        })
        return True
