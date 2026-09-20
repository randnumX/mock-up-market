"""
Mongo persistence for backtest run history, so archived runs (and their
live/interrupted state) are authoritative on the server instead of living
only in browser localStorage - a refresh, browser change, or the process
restarting no longer loses or desyncs a run's status.

Optional: backtesting itself has no MongoDB dependency (matches the rest of
this app's zero-setup story) - callers check `get_db() is not None` first
and skip persistence entirely when it's unavailable, falling back to the
old client-side-only history.
"""
import uuid
from datetime import datetime, timezone
from app.config import Config

MAX_RUNS = 50  # bounds storage/payload growth; oldest runs are pruned on each create


def _now():
    return datetime.now(timezone.utc).isoformat()


def create_run(db, tickers, strategy, config):
    run_id = str(uuid.uuid4())
    doc = {
        "_id": run_id,
        "ticker": tickers,
        "strategy": strategy,
        "config": config,
        "status": "streaming",
        "created_at": _now(),
        "updated_at": _now(),
    }
    db[Config.COLLECTION_BACKTEST_RUNS].insert_one(doc)
    _prune(db)
    return run_id


def complete_run(db, run_id, result):
    """`result` must already be JSON/BSON-safe (no numpy scalars) - the
    caller is responsible for sanitizing it the same way the SSE response is."""
    db[Config.COLLECTION_BACKTEST_RUNS].update_one(
        {"_id": run_id},
        {"$set": {**result, "status": "done", "updated_at": _now()}},
    )


def fail_run(db, run_id, error_msg, progress=None):
    """Marks a run as failed/interrupted. Guarded to never overwrite a run
    that already completed - relevant when the client disconnects in the
    small window right after the 'done' event but before the generator
    itself finishes cleanly."""
    fields = {"status": "error", "error_msg": error_msg, "updated_at": _now()}
    if progress is not None:
        fields["progress"] = progress
    db[Config.COLLECTION_BACKTEST_RUNS].update_one(
        {"_id": run_id, "status": {"$ne": "done"}}, {"$set": fields}
    )


def list_runs(db):
    return list(db[Config.COLLECTION_BACKTEST_RUNS].find().sort("created_at", -1).limit(MAX_RUNS))


def delete_run(db, run_id):
    result = db[Config.COLLECTION_BACKTEST_RUNS].delete_one({"_id": run_id})
    return result.deleted_count > 0


def _prune(db):
    coll = db[Config.COLLECTION_BACKTEST_RUNS]
    stale_ids = [d["_id"] for d in coll.find({}, {"_id": 1}).sort("created_at", -1).skip(MAX_RUNS)]
    if stale_ids:
        coll.delete_many({"_id": {"$in": stale_ids}})
