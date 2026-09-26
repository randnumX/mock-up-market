import time
import pymongo
from app.config import Config
from app.logging_config import get_logger

logger = get_logger("data.db")

_client = None
_db = None
_last_failed_at = None
RETRY_COOLDOWN_SECONDS = 15


def get_db():
    """
    Get a MongoDB database connection. Returns None if unreachable.

    A failed attempt is cached for RETRY_COOLDOWN_SECONDS so callers (every
    request touches this via the provider registry) don't each pay the
    ~3s connection timeout when Mongo simply isn't running - the app's
    "zero-setup" synthetic-data fallback would otherwise be slow, not fast.
    """
    global _client, _db, _last_failed_at
    if _db is not None:
        return _db
    if _last_failed_at is not None and (time.time() - _last_failed_at) < RETRY_COOLDOWN_SECONDS:
        return None
    try:
        _client = pymongo.MongoClient(
            Config.MONGO_URI,
            serverSelectionTimeoutMS=3000,
            connectTimeoutMS=3000
        )
        # Force a connection check
        _client.admin.command('ping')
        _db = _client[Config.DB_NAME]
        _last_failed_at = None
        logger.info("Connected to MongoDB (%s)", Config.DB_NAME)
        return _db
    except Exception as e:
        logger.warning("MongoDB unavailable (%s) - falling back to generated data", e)
        _client = None
        _db = None
        _last_failed_at = time.time()
        return None


def is_db_connected():
    """Check if MongoDB is reachable."""
    try:
        db = get_db()
        if db is None:
            return False
        db.client.admin.command('ping')
        return True
    except Exception:
        return False
