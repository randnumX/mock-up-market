import pytest
from app import create_app


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def test_backtest_rejects_malformed_date(client):
    resp = client.post("/api/backtest", json={"ticker": "SBIN", "strategy": "macd", "from_date": "not-a-date"})
    assert resp.status_code == 400
    assert "from_date" in resp.get_json()["error"]


def test_backtest_rejects_from_after_to(client):
    resp = client.post("/api/backtest", json={
        "ticker": "SBIN", "strategy": "macd", "from_date": "2024-06-01", "to_date": "2024-01-01",
    })
    assert resp.status_code == 400
    assert "from_date" in resp.get_json()["error"]


def test_backtest_accepts_valid_date_range(client):
    resp = client.post("/api/backtest", json={
        "ticker": "SBIN", "strategy": "macd", "capital": 50000,
        "from_date": "2024-01-01", "to_date": "2024-03-31",
    })
    assert resp.status_code == 200
    data = resp.get_json()
    curve = data["equity_curve"]
    assert curve[0]["time"] >= "2024-01-01"
    assert curve[-1]["time"] <= "2024-03-31"


def test_stream_endpoint_accepts_date_range(client):
    resp = client.get("/api/backtest/stream?ticker=SBIN&strategy=macd&from_date=2024-01-01&to_date=2024-01-31")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert '"type": "done"' in body
