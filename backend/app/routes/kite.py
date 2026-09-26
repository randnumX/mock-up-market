from flask import Blueprint, jsonify, request, redirect
from app.config import Config
from app.data import kite_client
from app.data.db import get_db
from app.data.kite_ingest import fetch_and_store, DEFAULT_TICKERS
from app.logging_config import get_logger

logger = get_logger("routes.kite")

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
        logger.warning("Kite login callback rejected: status=%s has_token=%s", status, bool(request_token))
        return redirect(f"{Config.KITE_FRONTEND_URL}/?kite=error")

    try:
        kite_client.complete_login(request_token)
        logger.info("Kite CONNECTED - access token exchanged and cached")
        return redirect(f"{Config.KITE_FRONTEND_URL}/?kite=connected")
    except Exception:
        logger.exception("Kite login failed while exchanging request_token")
        return redirect(f"{Config.KITE_FRONTEND_URL}/?kite=error")


@kite_bp.route('/api/kite/disconnect', methods=['POST'])
def kite_disconnect():
    kite_client.disconnect()
    logger.info("Kite DISCONNECTED - cached session cleared")
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
    intervals = req.get("intervals", ["day", "5minute", "15minute"])

    from app.live.ticker import _broadcast
    import threading

    def _sync_background():
        def on_progress(ticker, current, total):
            _broadcast({
                "type": "sync_progress",
                "ticker": ticker,
                "current": current,
                "total": total
            })
            
        logger.info("Kite sync STARTED tickers=%s days=%s intervals=%s", len(tickers), days, intervals)
        try:
            total_result = {"synced": [], "failed": [], "total_candles": 0}
            for interval in intervals:
                res = fetch_and_store(kite, db, tickers=tickers, days=days, interval=interval, progress=on_progress)
                total_result["synced"].extend(res["synced"])
                total_result["failed"].extend(res["failed"])
                total_result["total_candles"] += res["total_candles"]
            logger.info(
                "Kite sync COMPLETE synced=%s failed=%s candles=%s",
                len(total_result["synced"]), len(total_result["failed"]), total_result["total_candles"],
            )
            _broadcast({"type": "sync_complete", "result": total_result})
        except Exception as e:
            logger.exception("Kite sync FAILED")
            _broadcast({"type": "sync_error", "error": str(e)})

    thread = threading.Thread(target=_sync_background, daemon=True)
    thread.start()

    return jsonify({"message": "Sync started in background", "total": len(tickers)})
