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
    
    names = {}
    try:
        from app.data.kite_client import get_kite
        kite = get_kite()
        if kite:
            import app.data.kite_ingest as ki
            if ki._instrument_cache is None:
                ki._instrument_cache = kite.instruments("NSE")
            for inst in ki._instrument_cache:
                if inst["tradingsymbol"] in seen:
                    names[inst["tradingsymbol"]] = inst.get("name", "")
    except Exception:
        pass

    return jsonify({"tickers": sorted(seen.keys()), "names": names, "source": primary})

@tickers_bp.route('/api/tickers/<symbol>/history', methods=['GET'])
def get_ticker_history(symbol):
    """
    Returns historical data for a symbol to plot on a chart.
    Returns up to 300 bars formatted for lightweight-charts: {time, open, high, low, close}.
    """
    providers = [p for p in build_providers() if p.is_available()]
    if not providers:
        return jsonify({"error": "No data provider available"}), 503
        
    provider = providers[0] # primary provider (Mongo or Dummy)
    
    # We only have daily data stored for now, so we return daily data
    # The dataframe has Value, Volume. We mock open/high/low for lightweight-charts
    df = provider.get_history(symbol, days=300)
    if df is None or df.empty:
        return jsonify({"history": []})
        
    history = []
    # Lightweight charts expects time in 'YYYY-MM-DD' string for daily bars, or unix timestamp
    for _, row in df.iterrows():
        # Because we only have 'Value' (close) and not actual OHLC in the DB yet,
        # we will just use Value for all 4, or slightly simulate small wicks for visual.
        # But wait! We do have kite_ingest pulling "close". 
        # So it's technically a line chart, but we can plot it as OHLC with O=H=L=C.
        # However, a LineSeries might be better if we only have close.
        # But let's send O=H=L=C just in case we upgrade DB later.
        val = row["Value"]
        history.append({
            "time": row["priceDate"][:10], # format YYYY-MM-DD
            "open": val,
            "high": val,
            "low": val,
            "close": val,
            "value": val # For line series
        })
        
    return jsonify({"history": history})
