import mongomock
from app.data import backtest_store


def make_db():
    return mongomock.MongoClient().db


def test_create_run_starts_in_streaming_status():
    db = make_db()
    run_id = backtest_store.create_run(db, "SBIN", "macd", {"capital": 100000})

    runs = backtest_store.list_runs(db)
    assert len(runs) == 1
    assert runs[0]["_id"] == run_id
    assert runs[0]["status"] == "streaming"
    assert runs[0]["ticker"] == "SBIN"
    assert runs[0]["config"]["capital"] == 100000


def test_complete_run_sets_status_done_and_merges_result():
    db = make_db()
    run_id = backtest_store.create_run(db, "SBIN", "macd", {"capital": 100000})

    backtest_store.complete_run(db, run_id, {"roi": 12.5, "final_capital": 112500})

    runs = backtest_store.list_runs(db)
    assert runs[0]["status"] == "done"
    assert runs[0]["roi"] == 12.5
    assert runs[0]["final_capital"] == 112500


def test_fail_run_sets_status_error_with_progress():
    db = make_db()
    run_id = backtest_store.create_run(db, "SBIN", "macd", {"capital": 100000})

    backtest_store.fail_run(db, run_id, "Interrupted before completion", progress=42)

    runs = backtest_store.list_runs(db)
    assert runs[0]["status"] == "error"
    assert runs[0]["error_msg"] == "Interrupted before completion"
    assert runs[0]["progress"] == 42


def test_fail_run_never_overwrites_an_already_completed_run():
    db = make_db()
    run_id = backtest_store.create_run(db, "SBIN", "macd", {"capital": 100000})
    backtest_store.complete_run(db, run_id, {"roi": 5.0})

    backtest_store.fail_run(db, run_id, "Interrupted before completion")

    runs = backtest_store.list_runs(db)
    assert runs[0]["status"] == "done"
    assert runs[0]["roi"] == 5.0


def test_list_runs_sorted_newest_first():
    db = make_db()
    first = backtest_store.create_run(db, "SBIN", "macd", {"capital": 100000})
    second = backtest_store.create_run(db, "TCS", "rsi", {"capital": 50000})

    runs = backtest_store.list_runs(db)

    assert [r["_id"] for r in runs] == [second, first]


def test_delete_run_removes_it():
    db = make_db()
    run_id = backtest_store.create_run(db, "SBIN", "macd", {"capital": 100000})

    assert backtest_store.delete_run(db, run_id) is True
    assert backtest_store.list_runs(db) == []


def test_delete_run_returns_false_for_unknown_id():
    db = make_db()
    assert backtest_store.delete_run(db, "does-not-exist") is False


def test_prune_keeps_only_the_most_recent_max_runs():
    db = make_db()
    original_max = backtest_store.MAX_RUNS
    backtest_store.MAX_RUNS = 3
    try:
        ids = [backtest_store.create_run(db, "SBIN", "macd", {"capital": 100000}) for _ in range(5)]
        runs = backtest_store.list_runs(db)
        assert len(runs) == 3
        # The three most recently created runs survive; the oldest two are pruned.
        assert {r["_id"] for r in runs} == set(ids[-3:])
    finally:
        backtest_store.MAX_RUNS = original_max
