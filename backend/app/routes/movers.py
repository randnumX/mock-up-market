from flask import Blueprint, jsonify, request
from app.data.db import get_db
from app.config import Config
import pandas as pd

movers_bp = Blueprint('movers', __name__)

@movers_bp.route('/api/movers', methods=['GET'])
def get_movers():
    db = get_db()
    if db is None:
        return jsonify({"error": "Database not available"}), 503

    limit = int(request.args.get("limit", 200))
    
    collection = db[Config.COLLECTION_HISTORICAL]
    
    # 1. Find the distinct daily dates and get the latest 2
    # We only look at daily interval or documents without interval
    pipeline = [
        {"$match": {"$or": [{"interval": "day"}, {"interval": {"$exists": False}}]}},
        {"$group": {"_id": {"$substr": ["$priceDate", 0, 10]}}},
        {"$sort": {"_id": -1}},
        {"$limit": 2}
    ]
    dates_cursor = list(collection.aggregate(pipeline))
    if not dates_cursor:
        return jsonify({"top_volume": [], "top_gainers": [], "top_losers": []})
        
    dates = [d["_id"] for d in dates_cursor]
    latest_date = dates[0]
    previous_date = dates[1] if len(dates) > 1 else None
    
    # 2. Fetch all daily data for these dates
    match_query = {
        "$or": [{"interval": "day"}, {"interval": {"$exists": False}}],
        "priceDate": {"$regex": f"^({latest_date}|{previous_date})" if previous_date else f"^{latest_date}"}
    }
    
    cursor = collection.find(match_query, {"scripName": 1, "priceDate": 1, "Value": 1, "Volume": 1, "_id": 0})
    data = list(cursor)
    
    if not data:
        return jsonify({"top_volume": [], "top_gainers": [], "top_losers": []})
        
    df = pd.DataFrame(data)
    df['date'] = df['priceDate'].str[:10]
    
    # Separate into latest and previous dataframes
    latest_df = df[df['date'] == latest_date].copy()
    prev_df = df[df['date'] == previous_date].copy() if previous_date else pd.DataFrame(columns=df.columns)
    
    if prev_df.empty:
        # We don't have previous day data to calculate % change
        merged = latest_df
        merged['pct_change'] = 0
    else:
        merged = pd.merge(latest_df, prev_df, on='scripName', suffixes=('', '_prev'))
        merged['pct_change'] = ((merged['Value'] - merged['Value_prev']) / merged['Value_prev']) * 100
        
    # Also add stocks that were in latest_df but not in prev_df (new stocks)
    missing = latest_df[~latest_df['scripName'].isin(merged['scripName'])]
    if not missing.empty:
        missing = missing.copy()
        missing['pct_change'] = 0
        merged = pd.concat([merged, missing], ignore_index=True)
        
    # Format to list of dicts: { scripName, price, volume, change_pct }
    def format_row(row):
        return {
            "ticker": row['scripName'],
            "price": float(row['Value']),
            "volume": int(row['Volume']) if pd.notna(row['Volume']) else 0,
            "change_pct": round(float(row['pct_change']), 2) if pd.notna(row['pct_change']) else 0
        }
        
    top_volume = merged.sort_values(by="Volume", ascending=False).head(limit)
    top_gainers = merged.sort_values(by="pct_change", ascending=False).head(limit)
    top_losers = merged.sort_values(by="pct_change", ascending=True).head(limit)
    
    return jsonify({
        "date": latest_date,
        "top_volume": [format_row(row) for _, row in top_volume.iterrows()],
        "top_gainers": [format_row(row) for _, row in top_gainers.iterrows()],
        "top_losers": [format_row(row) for _, row in top_losers.iterrows()],
    })
