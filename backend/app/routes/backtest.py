from flask import Blueprint, request, jsonify
from app.engine.broker import SimulatedBroker
from app.engine.macd import MACDStrategy
from app.engine.rsi import RSIStrategy
from app.engine.sma_crossover import SMACrossoverStrategy
from app.engine.bollinger import BollingerBandsStrategy
from app.engine.backtester import BacktestRunner
from app.data.providers.registry import get_history_with_fallback

backtest_bp = Blueprint('backtest', __name__)

STRATEGIES = {
    "macd": MACDStrategy,
    "rsi": RSIStrategy,
    "sma_crossover": SMACrossoverStrategy,
    "bollinger": BollingerBandsStrategy,
}


@backtest_bp.route('/api/backtest', methods=['POST'])
def run_backtest():
    req = request.json or {}
    ticker = req.get("ticker", "SBIN")
    capital = float(req.get("capital", 100000))
    strategy_name = req.get("strategy", "macd")
    source = req.get("source")  # optional: force "kite" | "mongodb" | "generated"

    if strategy_name not in STRATEGIES:
        return jsonify({"error": f"Unknown strategy: {strategy_name}"}), 400

    df, data_source = get_history_with_fallback(ticker, days=365, preferred=source)
    if df is None:
        return jsonify({"error": f"No data available for ticker: {ticker}"}), 404

    broker = SimulatedBroker(capital)
    StrategyClass = STRATEGIES[strategy_name]
    strategy = StrategyClass(broker)
    runner = BacktestRunner(broker, strategy)
    runner.load_data(df)
    results = runner.run()
    results["data_source"] = data_source
    results["ticker"] = ticker
    results["strategy"] = strategy_name

    return jsonify(results)


@backtest_bp.route('/api/strategies', methods=['GET'])
def list_strategies():
    return jsonify({
        "strategies": [
            {"id": "macd", "label": "MACD Crossover (12/26/9)", "description": "Trend-following: buys bullish MACD/signal crossovers below zero, sells bearish crossovers above zero."},
            {"id": "rsi", "label": "RSI Mean Reversion (14)", "description": "Buys when RSI recovers above 30 (oversold), sells when RSI drops below 70 (overbought)."},
            {"id": "sma_crossover", "label": "SMA Crossover (20/50)", "description": "Golden/death cross: buys when the fast SMA crosses above the slow SMA, sells on the reverse."},
            {"id": "bollinger", "label": "Bollinger Bands (20, 2σ)", "description": "Mean reversion: buys when price re-enters from below the lower band, sells when it re-enters from above the upper band."},
        ]
    })
