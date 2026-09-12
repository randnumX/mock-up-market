import pymongo
from app.config import Config

_client = None
_db = None


def get_db():
    """Get a MongoDB database connection. Returns None if connection fails."""
    global _client, _db
    if _db is not None:
        return _db
    try:
        _client = pymongo.MongoClient(
            Config.MONGO_URI,
            serverSelectionTimeoutMS=3000,
            connectTimeoutMS=3000
        )
        # Force a connection check
        _client.admin.command('ping')
        _db = _client[Config.DB_NAME]
        print("✅ Connected to MongoDB")
        return _db
    except Exception as e:
        print(f"⚠️  MongoDB unavailable ({e}). Using generated dummy data.")
        _client = None
        _db = None
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
