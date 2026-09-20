import json
import numpy as np
from datetime import datetime
from flask import Blueprint, request, jsonify, Response, stream_with_context
from app.engine.broker import SimulatedBroker
from app.engine.backtester import BacktestRunner
from app.engine.registry import STRATEGIES, STRATEGY_META
from app.engine.position_sizing import build_sizer
from app.data.providers.registry import get_history_with_fallback

backtest_bp = Blueprint('backtest', __name__)

class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super(NumpyEncoder, self).default(obj)

def _validate_date(value, field_name):
    if value is None:
        return None
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        raise ValueError(f"{field_name} must be in YYYY-MM-DD format")
    return value


def _prepare_run(tickers_str, strategy_name, capital, source, from_date=None, to_date=None, position_sizing=None, interval="day", max_capital_per_trade=None, daily_loss_limit=None):
    """Shared setup for both the plain and streaming backtest endpoints.
    Returns (runner, data_source, error_response_or_None)."""
    if strategy_name not in STRATEGIES:
        return None, None, (jsonify({"error": f"Unknown strategy: {strategy_name}"}), 400)

    try:
        from_date = _validate_date(from_date, "from_date")
        to_date = _validate_date(to_date, "to_date")
    except ValueError as e:
        return None, None, (jsonify({"error": str(e)}), 400)

    if from_date and to_date and from_date > to_date:
        return None, None, (jsonify({"error": "from_date must be on or before to_date"}), 400)

    try:
        sizer = build_sizer(position_sizing)
    except (ValueError, TypeError) as e:
        return None, None, (jsonify({"error": str(e)}), 400)

    broker = SimulatedBroker(capital, max_capital_per_trade)
    runner = BacktestRunner(broker, STRATEGIES[strategy_name], position_sizer=sizer, daily_loss_limit=daily_loss_limit)
    
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    tickers = [t.strip() for t in tickers_str.split(',') if t.strip()]
    if not tickers:
        return None, None, (jsonify({"error": "At least one ticker is required"}), 400)
        
    last_source = source
    
    def fetch_ticker(ticker):
        df, data_source = get_history_with_fallback(
            ticker, days=365, preferred=source, from_date=from_date, to_date=to_date, interval=interval
        )
        return ticker, df, data_source

    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_ticker = {executor.submit(fetch_ticker, t): t for t in tickers}
        for future in as_completed(future_to_ticker):
            ticker = future_to_ticker[future]
            try:
                t, df, data_source = future.result()
                if df is None or df.empty:
                    return None, None, (jsonify({"error": f"No {interval} data available for ticker: {ticker}"}), 404)
                last_source = data_source
                runner.load_data(ticker, df)
            except Exception as e:
                return None, None, (jsonify({"error": f"Failed to fetch data for {ticker}: {str(e)}"}), 500)

    return runner, last_source, None


@backtest_bp.route('/api/backtest', methods=['POST'])
def run_backtest():
    req = request.json or {}
    tickers_str = req.get("ticker", "")
    if not tickers_str and "tickers" in req:
        tickers_str = ",".join(req["tickers"]) if isinstance(req["tickers"], list) else req.get("tickers", "")

    strategy_name = req.get("strategy")
    capital = req.get("capital")
    source = req.get("source")  # optional: force "kite" | "mongodb" | "generated"
    from_date = req.get("from_date")  # optional: "YYYY-MM-DD", inclusive
    to_date = req.get("to_date")
    interval = req.get("interval", "day")
    position_sizing = req.get("position_sizing")  # optional: {mode, fraction?, risk_per_trade?, lookback?}
    max_capital_per_trade = req.get("max_capital_per_trade")
    daily_loss_limit = req.get("daily_loss_limit")

    if not tickers_str or not strategy_name:
        return jsonify({"error": "tickers and strategy are required"}), 400

    try:
        from_date = _validate_date(from_date, "from_date")
        to_date = _validate_date(to_date, "to_date")
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    if from_date and to_date and from_date > to_date:
        return jsonify({"error": "from_date must be on or before to_date"}), 400

    if not capital:
        return jsonify({"error": "capital is required"}), 400

    try:
        capital = float(capital)
    except ValueError:
        return jsonify({"error": "capital must be a number"}), 400

    if max_capital_per_trade is not None:
        try:
            max_capital_per_trade = float(max_capital_per_trade)
        except ValueError:
            return jsonify({"error": "max_capital_per_trade must be a number"}), 400

    if daily_loss_limit is not None:
        try:
            daily_loss_limit = float(daily_loss_limit)
        except ValueError:
            return jsonify({"error": "daily_loss_limit must be a number"}), 400

    runner, data_source, error = _prepare_run(
        tickers_str, strategy_name, capital, source, from_date, to_date, position_sizing, interval, max_capital_per_trade, daily_loss_limit
    )
    if error:
        return error

    results = runner.run()
    results["data_source"] = data_source
    results["ticker"] = tickers_str
    results["strategy"] = strategy_name

    return jsonify(results)


@backtest_bp.route('/api/backtest/stream', methods=['GET'])
def run_backtest_stream():
    """
    Server-Sent Events version of /api/backtest: emits one 'tick' event per
    bar as the backtest runs, then a final 'done' event with the exact same
    result shape the plain endpoint returns. Lets the frontend draw the
    equity curve live instead of waiting for the whole thing to finish.
    GET + query params because browsers' EventSource only supports GET.
    """
    ticker = request.args.get("ticker", "SBIN")
    capital = float(request.args.get("capital", 100000))
    strategy_name = request.args.get("strategy", "macd")
    source = request.args.get("source")
    from_date = request.args.get("from_date")
    to_date = request.args.get("to_date")
    interval = request.args.get("interval", "day")

    sizing_mode = request.args.get("sizing_mode")
    position_sizing = None
    if sizing_mode:
        position_sizing = {"mode": sizing_mode}
        if request.args.get("sizing_fraction"):
            position_sizing["fraction"] = request.args.get("sizing_fraction")
        if request.args.get("sizing_risk_per_trade"):
            position_sizing["risk_per_trade"] = request.args.get("sizing_risk_per_trade")
        if request.args.get("sizing_lookback"):
            position_sizing["lookback"] = request.args.get("sizing_lookback")

    max_capital_per_trade = request.args.get("max_capital_per_trade")
    daily_loss_limit = request.args.get("daily_loss_limit")
    
    if max_capital_per_trade:
        max_capital_per_trade = float(max_capital_per_trade)
    if daily_loss_limit:
        daily_loss_limit = float(daily_loss_limit)

    runner, data_source, error = _prepare_run(ticker, strategy_name, capital, source, from_date, to_date, position_sizing, interval, max_capital_per_trade, daily_loss_limit)
    if error:
        return error

    def generate():
        for event in runner.run_streaming():
            if event["type"] == "done":
                event["result"]["data_source"] = data_source
                event["result"]["ticker"] = ticker
                event["result"]["strategy"] = strategy_name
            yield f"data: {json.dumps(event, cls=NumpyEncoder)}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'},
    )


@backtest_bp.route('/api/strategies', methods=['GET'])
def list_strategies():
    return jsonify({"strategies": STRATEGY_META})


@backtest_bp.route('/api/position-sizing-modes', methods=['GET'])
def list_position_sizing_modes():
    return jsonify({"modes": [
        {"id": "full", "label": "Full Capital", "description": "Bet all available cash on every trade (original behavior). Maximizes returns and risk equally."},
        {"id": "fixed_fraction", "label": "Fixed Fraction", "description": "Bet a fixed percentage of capital on every trade, regardless of signal strength.", "params": ["fraction"]},
        {"id": "volatility_target", "label": "Volatility Target", "description": "Size positions so a ~1-standard-deviation move costs a fixed % of capital - calmer stocks get bigger positions, choppier ones smaller.", "params": ["risk_per_trade", "lookback"]},
    ]})
