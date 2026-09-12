"""
Single source of truth for which strategies exist. Both the backtest route
and the live trading engine import from here, so adding a new strategy
(subclass Strategy, register it here) makes it available in both places
and in the frontend selector automatically via GET /api/strategies.
"""
from app.engine.macd import MACDStrategy
from app.engine.rsi import RSIStrategy
from app.engine.sma_crossover import SMACrossoverStrategy
from app.engine.bollinger import BollingerBandsStrategy

STRATEGIES = {
    "macd": MACDStrategy,
    "rsi": RSIStrategy,
    "sma_crossover": SMACrossoverStrategy,
    "bollinger": BollingerBandsStrategy,
}

STRATEGY_META = [
    {"id": "macd", "label": "MACD Crossover (12/26/9)", "description": "Trend-following: buys bullish MACD/signal crossovers below zero, sells bearish crossovers above zero."},
    {"id": "rsi", "label": "RSI Mean Reversion (14)", "description": "Buys when RSI recovers above 30 (oversold), sells when RSI drops below 70 (overbought)."},
    {"id": "sma_crossover", "label": "SMA Crossover (20/50)", "description": "Golden/death cross: buys when the fast SMA crosses above the slow SMA, sells on the reverse."},
    {"id": "bollinger", "label": "Bollinger Bands (20, 2σ)", "description": "Mean reversion: buys when price re-enters from below the lower band, sells when it re-enters from above the upper band."},
]
