from flask import Blueprint, request, jsonify
from app.data.db import get_db
from app.data.kite_client import is_connected as kite_connected
from app.engine.registry import STRATEGIES
from app.engine.position_sizing import build_sizer
from app.live import store
from app.live.engine import summarize_session
from app.live.market_hours import is_market_open

live_bp = Blueprint('live', __name__)


@live_bp.route('/api/live/market-status', methods=['GET'])
def market_status():
    return jsonify({"is_open": is_market_open()})


@live_bp.route('/api/live/sessions', methods=['GET'])
def list_sessions():
    db = get_db()
    if db is None:
        return jsonify({"sessions": []})
    sessions = [summarize_session(s) for s in store.list_sessions(db)]
    return jsonify({"sessions": sessions})


@live_bp.route('/api/live/sessions/<session_id>', methods=['GET'])
def get_session(session_id):
    db = get_db()
    session = store.get_session(db, session_id) if db is not None else None
    if not session:
        return jsonify({"error": "Session not found"}), 404
    return jsonify(summarize_session(session))


@live_bp.route('/api/live/sessions', methods=['POST'])
def create_session():
    db = get_db()
    if db is None:
        return jsonify({"error": "MongoDB is required for live trading sessions (state must survive restarts)."}), 503

    req = request.json or {}
    ticker = req.get("ticker")
    strategy = req.get("strategy")
    mode = req.get("mode", "paper")
    capital = req.get("capital")
    max_capital_per_trade = req.get("max_capital_per_trade")
    daily_loss_limit = req.get("daily_loss_limit")
    position_sizing = req.get("position_sizing")
    confirm = req.get("confirm", False)

    if not ticker or not strategy:
        return jsonify({"error": "ticker and strategy are required"}), 400
    if strategy not in STRATEGIES:
        return jsonify({"error": f"Unknown strategy: {strategy}"}), 400
    if mode not in ("paper", "live"):
        return jsonify({"error": "mode must be 'paper' or 'live'"}), 400
    try:
        capital = float(capital)
        assert capital > 0
    except (TypeError, ValueError, AssertionError):
        return jsonify({"error": "capital must be a positive number"}), 400
    try:
        build_sizer(position_sizing)  # validates mode/params up front, same object discarded
    except (ValueError, TypeError) as e:
        return jsonify({"error": str(e)}), 400

    if mode == "live":
        if not kite_connected():
            return jsonify({"error": "Connect Zerodha before starting a live (real-money) session."}), 400
        if not confirm:
            return jsonify({"error": "Live sessions place real orders with real money. Set confirm=true to acknowledge and proceed."}), 400
        if not max_capital_per_trade or float(max_capital_per_trade) <= 0:
            return jsonify({"error": "max_capital_per_trade is required and must be positive for live sessions."}), 400

    if max_capital_per_trade is not None:
        max_capital_per_trade = float(max_capital_per_trade)
    if daily_loss_limit is not None:
        daily_loss_limit = float(daily_loss_limit)

    session = store.create_session(
        db, ticker, strategy, mode, capital, max_capital_per_trade, daily_loss_limit, position_sizing
    )
    return jsonify(summarize_session(session)), 201


@live_bp.route('/api/live/sessions/<session_id>/stop', methods=['POST'])
def stop_session(session_id):
    db = get_db()
    if db is None:
        return jsonify({"error": "MongoDB unavailable"}), 503
    if not store.get_session(db, session_id):
        return jsonify({"error": "Session not found"}), 404
    store.stop_session(db, session_id, reason="Stopped by user")
    return jsonify({"stopped": True})


@live_bp.route('/api/live/kill-all', methods=['POST'])
def kill_all():
    """Safety kill switch: immediately stops every running session (paper and live)."""
    db = get_db()
    if db is None:
        return jsonify({"error": "MongoDB unavailable"}), 503
    count = store.stop_all_sessions(db)
    return jsonify({"stopped": count})
