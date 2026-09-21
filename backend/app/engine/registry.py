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
from app.engine.vwap import VWAPStrategy
from app.engine.orb import ORBStrategy
from app.engine.rsi_scalp import RSIScalpStrategy
from app.engine.ema_scalp import EMAScalpStrategy
from app.engine.data_collector import DataCollectionStrategy

STRATEGIES = {
    "macd": MACDStrategy,
    "rsi": RSIStrategy,
    "sma_crossover": SMACrossoverStrategy,
    "bollinger": BollingerBandsStrategy,
    "vwap": VWAPStrategy,
    "orb": ORBStrategy,
    "rsi_scalp": RSIScalpStrategy,
    "ema_scalp": EMAScalpStrategy,
    "data_collection": DataCollectionStrategy,
}

STRATEGY_META = [
    {"id": "macd", "label": "MACD Crossover (12/26/9)", "description": "Trend-following: buys bullish MACD/signal crossovers below zero, sells bearish crossovers above zero."},
    {"id": "rsi", "label": "RSI Mean Reversion (14)", "description": "Buys when RSI recovers above 30 (oversold), sells when RSI drops below 70 (overbought)."},
    {"id": "sma_crossover", "label": "SMA Crossover (20/50)", "description": "Golden/death cross: buys when the fast SMA crosses above the slow SMA, sells on the reverse."},
    {"id": "bollinger", "label": "Bollinger Bands (20, 2σ)", "description": "Mean reversion: buys when price re-enters from below the lower band, sells when it re-enters from above the upper band."},
    {"id": "vwap", "label": "VWAP Intraday", "description": "Intraday: buys when price crosses above VWAP, sells when price crosses below. Auto-closes at EOD."},
    {"id": "orb", "label": "15-Min ORB (Breakout)", "description": "Intraday: buys if price breaks 15-min high, shorts if price breaks 15-min low. Auto-closes at EOD."},
    {"id": "rsi_scalp", "label": "RSI Scalper (5-Min)", "description": "Intraday: buys when RSI < 20 (oversold) and sells on mean reversion (RSI > 50)."},
    {"id": "ema_scalp", "label": "EMA Momentum (9/21)", "description": "Intraday: buys when 9 EMA crosses above 21 EMA. Sells instantly when price closes below 9 EMA."},
    {"id": "data_collection", "label": "Data Collection Only", "description": "Null strategy. Does not trade. Used purely to harvest live ticks and save bars to MongoDB."},
]
