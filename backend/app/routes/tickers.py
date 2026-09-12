from flask import Blueprint, jsonify, request
from app.data.providers.registry import build_providers

tickers_bp = Blueprint('tickers', __name__)


@tickers_bp.route('/api/tickers', methods=['GET'])
def get_tickers():
    """
    Merge tickers from every available provider so the dropdown always
    shows real symbols (Kite/Mongo) plus the guaranteed synthetic set,
    tagging which source is "primary" (best available) for the status badge.
    """
    source_filter = request.args.get('source')
    providers = [p for p in build_providers() if p.is_available()]

    if source_filter:
        providers = [p for p in providers if p.name == source_filter]

    seen = {}
    for p in providers:
        for t in p.get_tickers():
            seen.setdefault(t, p.name)

    primary = providers[0].name if providers else "generated"
    return jsonify({"tickers": sorted(seen.keys()), "source": primary})
