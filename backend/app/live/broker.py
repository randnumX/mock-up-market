"""
Two broker implementations for the live engine, sharing the exact same
place_order(...) signature the Strategy classes already call in backtests:

- PaperBroker: virtual money, real-time prices, zero financial risk.
  Reuses SimulatedBroker's tax-aware fill logic unchanged, including
  short-selling (a SELL with no long position open opens/grows a short).
- KiteLiveBroker: places REAL orders on the connected Zerodha account.
  Local capital/positions are a best-effort mirror for the dashboard;
  Kite itself is the source of truth for actual fills/holdings.
  Deliberately long-only: a SELL is still clamped to the existing
  position size below, so a short-side signal (e.g. ORB's breakdown
  entry) silently no-ops here instead of opening a real short. Real
  equity shorting on NSE has margin/product-type rules (MIS intraday
  only, no CNC overnight shorts) this mirror doesn't model - clamping
  to no-op is the safe default until that's deliberately built out.

Both respect an optional per-trade capital cap (risk control), clamping
order size down rather than rejecting the signal outright.
"""
from app.engine.broker import SimulatedBroker


class PaperBroker(SimulatedBroker):
    mode = "paper"

class KiteLiveBroker:
    mode = "live"

    def __init__(self, kite, capital, max_capital_per_trade=None, is_intraday=False):
        self.kite = kite
        self.initial_capital = capital
        self.capital = capital
        self.positions = {}
        self.history = []
        self.realized_pnl = 0
        self.total_taxes = 0
        self.max_capital_per_trade = max_capital_per_trade
        # Decides PRODUCT_MIS vs PRODUCT_CNC on the real order below.
        self.is_intraday = is_intraday

    def place_order(self, order_type, symbol, price, quantity, timestamp, is_intraday=None):
        if is_intraday is None:
            is_intraday = self.is_intraday
        if order_type == "SELL":
            pos = self.positions.get(symbol, {"qty": 0, "avg_price": 0})
            if not is_intraday:
                quantity = min(quantity, max(0, pos["qty"]))
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

        # Best-effort local mirror for the dashboard
        from app.utils.taxes import calculate_taxes
        pos = self.positions.get(symbol, {"qty": 0, "avg_price": 0})
        
        if order_type == "BUY":
            if pos["qty"] < 0:
                # Cover short
                cover_qty = min(quantity, -pos["qty"])
                short_avg_price = pos["avg_price"]
                self.capital -= price * cover_qty
                
                tax_details = calculate_taxes(price, short_avg_price, cover_qty, is_intraday)
                self.capital -= tax_details["total_charges"]
                self.realized_pnl += tax_details["net_profit"]
                self.total_taxes += tax_details["total_charges"]
                
                new_qty = pos["qty"] + cover_qty
                if new_qty == 0:
                    self.positions.pop(symbol, None)
                else:
                    self.positions[symbol] = {"qty": new_qty, "avg_price": short_avg_price}
                
                self.history.append({
                    "type": "BUY", "symbol": symbol, "price": price, "qty": cover_qty,
                    "timestamp": str(timestamp), "pnl": round(tax_details["net_profit"], 2),
                    "taxes": round(tax_details["total_charges"], 2)
                })
                # if there is remaining quantity, it becomes a new long (rare but handled if needed)
                if quantity > cover_qty:
                    rem_qty = quantity - cover_qty
                    cost = price * rem_qty
                    self.capital -= cost
                    self.positions[symbol] = {"qty": rem_qty, "avg_price": price}
                    self.history.append({
                        "type": "BUY", "symbol": symbol, "price": price, "qty": rem_qty,
                        "timestamp": str(timestamp)
                    })
            else:
                # Open or add to long
                cost = price * quantity
                self.capital -= cost
                total_cost = pos["qty"] * pos["avg_price"] + cost
                new_qty = pos["qty"] + quantity
                self.positions[symbol] = {"qty": new_qty, "avg_price": total_cost / new_qty}
                self.history.append({
                    "type": "BUY", "symbol": symbol, "price": price, "qty": quantity,
                    "timestamp": str(timestamp)
                })
        else:
            if pos["qty"] > 0:
                # Sell long
                sell_qty = min(quantity, pos["qty"])
                self.capital += price * sell_qty
                long_avg_price = pos["avg_price"]
                
                tax_details = calculate_taxes(long_avg_price, price, sell_qty, is_intraday)
                self.capital -= tax_details["total_charges"]
                self.realized_pnl += tax_details["net_profit"]
                self.total_taxes += tax_details["total_charges"]
                
                new_qty = pos["qty"] - sell_qty
                if new_qty == 0:
                    self.positions.pop(symbol, None)
                else:
                    self.positions[symbol] = {"qty": new_qty, "avg_price": long_avg_price}
                
                self.history.append({
                    "type": "SELL", "symbol": symbol, "price": price, "qty": sell_qty,
                    "timestamp": str(timestamp), "pnl": round(tax_details["net_profit"], 2),
                    "taxes": round(tax_details["total_charges"], 2)
                })
                
                if quantity > sell_qty and is_intraday:
                    rem_qty = quantity - sell_qty
                    self.capital += price * rem_qty
                    self.positions[symbol] = {"qty": -rem_qty, "avg_price": price}
                    self.history.append({
                        "type": "SELL", "symbol": symbol, "price": price, "qty": rem_qty,
                        "timestamp": str(timestamp)
                    })
            else:
                # Open or add to short
                self.capital += price * quantity
                existing_short_qty = -pos["qty"]
                total_proceeds = existing_short_qty * pos["avg_price"] + quantity * price
                new_short_qty = existing_short_qty + quantity
                self.positions[symbol] = {"qty": -new_short_qty, "avg_price": total_proceeds / new_short_qty}
                self.history.append({
                    "type": "SELL", "symbol": symbol, "price": price, "qty": quantity,
                    "timestamp": str(timestamp)
                })
        return True
