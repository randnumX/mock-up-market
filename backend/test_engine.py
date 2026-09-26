import os
import sys
import pandas as pd
from app.config import Config
from app.data.db import get_db
from app.live.engine import _backfill_session, run_tick
from app.engine.ema_scalp import EMAScalpStrategy

db = get_db()
session = {
    "_id": "51d9b338-c647-4a27-8720-def623621ac0",
    "tickers": ["RELIANCE"],
    "strategy": "ema_scalp",
    "interval": "5minute",
    "mode": "paper",
    "capital": 100000,
    "cash": 100000,
    "positions": {},
    "history": [],
    "realized_pnl": 0,
    "total_taxes": 0,
    "bars": {}
}
class MockKite: pass

_backfill_session(db, session, MockKite())
print("Backfill complete.")
if session["bars"].get("RELIANCE"):
    print("Bars keys after backfill:", list(session["bars"]["RELIANCE"][0].keys()))
else:
    print("Bars for RELIANCE is empty!")

try:
    # Need to put something in provider for run_tick, but we mocked Kite.
    # We will just patch get_latest_price
    import app.live.engine as engine_module
    engine_module.get_latest_price = lambda x, y=None: 2500
    run_tick(db, session, MockKite())
    print("Tick 1 complete.")
    print("Bars keys after tick 1:", list(session["bars"]["RELIANCE"][0].keys()))
except Exception as e:
    import traceback
    traceback.print_exc()
