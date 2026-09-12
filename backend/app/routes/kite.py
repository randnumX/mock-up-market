from flask import Blueprint, jsonify, request, redirect
from app.config import Config
from app.data import kite_client
from app.data.db import get_db
from app.data.kite_ingest import fetch_and_store, DEFAULT_TICKERS

kite_bp = Blueprint('kite', __name__)


@kite_bp.route('/api/kite/status', methods=['GET'])
def kite_status():
    configured = kite_client.is_configured()
    connected = kite_client.is_connected() if configured else False
    profile = kite_client.get_profile() if connected else None
    return jsonify({
        "configured": configured,
        "connected": connected,
        "user_name": (profile or {}).get("user_name") if profile else None,
    })


@kite_bp.route('/api/kite/login-url', methods=['GET'])
def kite_login_url():
    if not kite_client.is_configured():
        return jsonify({"error": "Kite Connect is not configured. Set KITE_API_KEY and KITE_API_SECRET."}), 400
    return jsonify({"login_url": kite_client.get_login_url()})


@kite_bp.route('/api/kite/callback', methods=['GET'])
def kite_callback():
    """Zerodha redirects here after login with ?request_token=...&status=success"""
    request_token = request.args.get('request_token')
    status = request.args.get('status')

    if status != 'success' or not request_token:
        return redirect(f"{Config.KITE_FRONTEND_URL}/?kite=error")

    try:
        kite_client.complete_login(request_token)
        return redirect(f"{Config.KITE_FRONTEND_URL}/?kite=connected")
    except Exception:
        return redirect(f"{Config.KITE_FRONTEND_URL}/?kite=error")


@kite_bp.route('/api/kite/disconnect', methods=['POST'])
def kite_disconnect():
    kite_client.disconnect()
    return jsonify({"disconnected": True})


@kite_bp.route('/api/kite/sync', methods=['POST'])
def kite_sync():
    kite = kite_client.get_kite()
    if kite is None:
        return jsonify({"error": "Not connected to Zerodha. Connect first."}), 400

    db = get_db()
    if db is None:
        return jsonify({"error": "MongoDB is not reachable, cannot store synced data."}), 503

    req = request.json or {}
    tickers = req.get("tickers") or DEFAULT_TICKERS
    days = int(req.get("days", 730))

    result = fetch_and_store(kite, db, tickers=tickers, days=days)
    return jsonify(result)
