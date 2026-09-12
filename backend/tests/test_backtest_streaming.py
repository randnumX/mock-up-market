import json
import pytest
from app.utils.dummy_data import generate_stock_data
from app.engine.broker import SimulatedBroker
from app.engine.backtester import BacktestRunner
from app.engine.macd import MACDStrategy
from app import create_app


def test_run_streaming_yields_one_tick_per_bar_then_done():
    df = generate_stock_data("SBIN", days=100, seed=1)
    broker = SimulatedBroker(100000)
    runner = BacktestRunner(broker, MACDStrategy(broker))
    runner.load_data(df)

    events = list(runner.run_streaming())
    ticks = [e for e in events if e["type"] == "tick"]
    done = [e for e in events if e["type"] == "done"]

    assert len(ticks) == len(df)
    assert len(done) == 1
    assert ticks[0]["index"] == 0
    assert ticks[-1]["index"] == len(df) - 1
    assert all(t["total"] == len(df) for t in ticks)


def test_run_streaming_produces_identical_result_to_run():
    """The streaming path must never drift from the plain run() result."""
    df = generate_stock_data("TCS", days=200, seed=5)

    broker_a = SimulatedBroker(75000)
    runner_a = BacktestRunner(broker_a, MACDStrategy(broker_a))
    runner_a.load_data(df)
    plain_result = runner_a.run()

    broker_b = SimulatedBroker(75000)
    runner_b = BacktestRunner(broker_b, MACDStrategy(broker_b))
    runner_b.load_data(df)
    streamed_result = next(e for e in runner_b.run_streaming() if e["type"] == "done")["result"]

    assert plain_result == streamed_result


def test_streaming_ticks_carry_new_trades_when_a_signal_fires():
    df = generate_stock_data("RELIANCE", days=300, seed=7)
    broker = SimulatedBroker(100000)
    runner = BacktestRunner(broker, MACDStrategy(broker))
    runner.load_data(df)

    all_new_trades = [t for e in runner.run_streaming() if e["type"] == "tick" for t in e["new_trades"]]
    assert len(all_new_trades) == len(broker.history)


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def test_stream_endpoint_returns_sse_events(client):
    resp = client.get("/api/backtest/stream?ticker=SBIN&capital=50000&strategy=macd")
    assert resp.status_code == 200
    assert resp.mimetype == "text/event-stream"

    body = resp.get_data(as_text=True)
    lines = [line for line in body.split("\n\n") if line.startswith("data: ")]
    events = [json.loads(line[len("data: "):]) for line in lines]

    assert events[-1]["type"] == "done"
    assert events[-1]["result"]["ticker"] == "SBIN"
    assert events[-1]["result"]["strategy"] == "macd"
    assert sum(1 for e in events if e["type"] == "tick") == len(events) - 1


def test_stream_endpoint_rejects_unknown_strategy(client):
    resp = client.get("/api/backtest/stream?ticker=SBIN&strategy=not_a_real_strategy")
    assert resp.status_code == 400
