"""
Pluggable position sizing for Strategy classes. Every strategy previously
computed `quantity = math.floor(capital / price)` inline - always betting
100% of available capital on every trade. That's still the default
(FullCapitalSizer), but strategies now delegate to a PositionSizer so a
backtest or live session can choose a safer sizing mode instead, without
touching strategy code.
"""
import math


class PositionSizer:
    name = "base"

    def size(self, capital, price, df, i):
        """Return an integer share quantity to buy, given available cash,
        the current bar's price, and the full price history so far (df,
        up to and including index i) for sizers that need recent volatility."""
        raise NotImplementedError


class FullCapitalSizer(PositionSizer):
    """Original behavior: bet everything available. Maximizes returns and
    risk equally - the default so existing behavior is unchanged."""
    name = "full"

    def size(self, capital, price, df, i):
        if price <= 0:
            return 0
        return math.floor(capital / price)


class FixedFractionSizer(PositionSizer):
    """Bet a fixed percentage of current capital on every trade, e.g. 20%
    per trade regardless of how confident the signal looks. Simple, popular
    risk control - caps the damage any single bad trade can do."""
    name = "fixed_fraction"

    def __init__(self, fraction=0.2):
        self.fraction = max(0.0, min(1.0, fraction))

    def size(self, capital, price, df, i):
        if price <= 0:
            return 0
        return math.floor((capital * self.fraction) / price)


class VolatilityTargetSizer(PositionSizer):
    """
    Sizes the position so a ~1-standard-deviation adverse move costs
    approximately `risk_per_trade` of capital, using recent daily-return
    volatility (over `lookback` bars) as the risk proxy. Calmer stocks get
    bigger positions, choppier stocks get smaller ones, for a more
    consistent risk profile across different tickers/strategies than
    either fixed sizing mode gives.
    """
    name = "volatility_target"

    def __init__(self, risk_per_trade=0.01, lookback=14):
        self.risk_per_trade = max(0.0001, risk_per_trade)
        self.lookback = max(2, lookback)

    def size(self, capital, price, df, i):
        if price <= 0:
            return 0

        window = df["Value"].iloc[max(0, i - self.lookback + 1): i + 1]
        if len(window) < 2:
            return math.floor(capital / price)

        returns = window.pct_change().dropna()
        volatility = returns.std()
        if not volatility or volatility != volatility:  # NaN guard
            return math.floor(capital / price)

        risk_amount = capital * self.risk_per_trade
        position_value = risk_amount / volatility
        position_value = min(position_value, capital)  # never leverage beyond available cash
        return math.floor(position_value / price)


SIZERS = {
    "full": FullCapitalSizer,
    "fixed_fraction": FixedFractionSizer,
    "volatility_target": VolatilityTargetSizer,
}


def build_sizer(config):
    """
    config: {"mode": "full" | "fixed_fraction" | "volatility_target", ...params}
    or None for the default (FullCapitalSizer). Unknown mode raises ValueError
    so callers (routes) can turn it into a clean 400 instead of silently
    falling back to a different risk profile than the user asked for.
    """
    if not config:
        return FullCapitalSizer()

    mode = config.get("mode", "full")
    if mode not in SIZERS:
        raise ValueError(f"Unknown position sizing mode: {mode}")

    if mode == "full":
        return FullCapitalSizer()
    if mode == "fixed_fraction":
        return FixedFractionSizer(fraction=float(config.get("fraction", 0.2)))
    if mode == "volatility_target":
        return VolatilityTargetSizer(
            risk_per_trade=float(config.get("risk_per_trade", 0.01)),
            lookback=int(config.get("lookback", 14)),
        )
