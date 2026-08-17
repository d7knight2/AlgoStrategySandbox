"""Health endpoint tests."""

from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["trading_mode"] == "paper"
    assert data["live_trading_enabled"] is False
    assert data["risk_engine"] == "active"


def test_root():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "Trading Core" in data["message"]
    assert data["dashboard"] == "/dashboard"
    assert data["safety"]["live_trading_enabled"] is False
    assert data["safety"]["trading_mode"] == "paper"
