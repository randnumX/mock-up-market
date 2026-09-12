from flask import Blueprint, request, jsonify
from app.engine.broker import SimulatedBroker
from app.engine.backtester import BacktestRunner
from app.engine.registry import STRATEGIES, STRATEGY_META
from app.data.providers.registry import get_history_with_fallback

backtest_bp = Blueprint('backtest', __name__)


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
    return jsonify({"strategies": STRATEGY_META})
