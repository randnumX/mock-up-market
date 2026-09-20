import json
from flask import Blueprint, jsonify, request
from app.live.scanner import set_scanner, get_scanner_state

scanner_bp = Blueprint('scanner', __name__)

@scanner_bp.route('/api/scanner', methods=['GET'])
def get_scanner():
    return jsonify(get_scanner_state())

@scanner_bp.route('/api/scanner', methods=['POST'])
def update_scanner():
    req = request.json or {}
    active = req.get("active", False)
    strategy = req.get("strategy", "MACDStrategy")
    interval = req.get("interval", "day")
    watchlist = req.get("watchlist", [])
    
    set_scanner(active, strategy, watchlist, interval)
    
    return jsonify({"success": True, "state": get_scanner_state()})
