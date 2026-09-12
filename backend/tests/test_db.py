from unittest.mock import patch, MagicMock
import app.data.db as db_module


def _reset_db_module_state():
    db_module._client = None
    db_module._db = None
    db_module._last_failed_at = None


def test_failed_connection_is_cached_not_retried_immediately():
    """A failed Mongo connection must not re-attempt (with its ~3s timeout)
    on every single call within the cooldown window."""
    _reset_db_module_state()
    try:
        with patch("pymongo.MongoClient", side_effect=Exception("connection refused")) as mock_client:
            assert db_module.get_db() is None
            assert db_module.get_db() is None
            assert db_module.get_db() is None
            assert mock_client.call_count == 1
    finally:
        _reset_db_module_state()


def test_retries_after_cooldown_expires():
    _reset_db_module_state()
    try:
        with patch("pymongo.MongoClient", side_effect=Exception("connection refused")) as mock_client:
            assert db_module.get_db() is None
            assert mock_client.call_count == 1

            # Simulate the cooldown window having passed.
            db_module._last_failed_at -= (db_module.RETRY_COOLDOWN_SECONDS + 1)

            assert db_module.get_db() is None
            assert mock_client.call_count == 2
    finally:
        _reset_db_module_state()


def test_successful_connection_is_cached_and_reused():
    _reset_db_module_state()
    try:
        fake_client = MagicMock()
        fake_client.admin.command.return_value = {"ok": 1}
        with patch("pymongo.MongoClient", return_value=fake_client) as mock_client:
            db1 = db_module.get_db()
            db2 = db_module.get_db()
            assert db1 is db2
            assert mock_client.call_count == 1
    finally:
        _reset_db_module_state()
