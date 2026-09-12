import json
from datetime import datetime
from flask import Blueprint, request, jsonify, Response, stream_with_context
from app.engine.broker import SimulatedBroker
from app.engine.backtester import BacktestRunner
from app.engine.registry import STRATEGIES, STRATEGY_META
from app.engine.position_sizing import build_sizer
from app.data.providers.registry import get_history_with_fallback

backtest_bp = Blueprint('backtest', __name__)


def _validate_date(value, field_name):
    if value is None:
        return None
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        raise ValueError(f"{field_name} must be in YYYY-MM-DD format")
    return value


def _prepare_run(ticker, strategy_name, capital, source, from_date=None, to_date=None, position_sizing=None):
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

    df, data_source = get_history_with_fallback(
        ticker, days=365, preferred=source, from_date=from_date, to_date=to_date
    )
    if df is None:
        return None, None, (jsonify({"error": f"No data available for ticker: {ticker}"}), 404)

    broker = SimulatedBroker(capital)
    strategy = STRATEGIES[strategy_name](broker, position_sizer=sizer)
    runner = BacktestRunner(broker, strategy)
    runner.load_data(df)
    return runner, data_source, None


@backtest_bp.route('/api/backtest', methods=['POST'])
def run_backtest():
    req = request.json or {}
    ticker = req.get("ticker", "SBIN")
    capital = float(req.get("capital", 100000))
    strategy_name = req.get("strategy", "macd")
    source = req.get("source")  # optional: force "kite" | "mongodb" | "generated"
    from_date = req.get("from_date")  # optional: "YYYY-MM-DD", inclusive
    to_date = req.get("to_date")
    position_sizing = req.get("position_sizing")  # optional: {mode, fraction?, risk_per_trade?, lookback?}

    runner, data_source, error = _prepare_run(ticker, strategy_name, capital, source, from_date, to_date, position_sizing)
    if error:
        return error

    results = runner.run()
    results["data_source"] = data_source
    results["ticker"] = ticker
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

    runner, data_source, error = _prepare_run(ticker, strategy_name, capital, source, from_date, to_date, position_sizing)
    if error:
        return error

    def generate():
        for event in runner.run_streaming():
            if event["type"] == "done":
                event["result"]["data_source"] = data_source
                event["result"]["ticker"] = ticker
                event["result"]["strategy"] = strategy_name
            yield f"data: {json.dumps(event)}\n\n"

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
