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
    assert data["paper_automation_enabled"] is False


def test_root():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "Trading Core" in data["message"]
    assert data["dashboard"] == "/dashboard"
    assert data["safety"]["live_trading_enabled"] is False
    assert data["safety"]["trading_mode"] == "paper"


def test_order_submission_requires_explicit_paper_automation(monkeypatch):
    from src.main import settings

    monkeypatch.setattr(settings, "paper_automation_enabled", False)

    proposal = client.post(
        "/propose_trade",
        json={"symbol": "SPY", "side": "buy", "notional": 50, "execute": True},
    )
    scan = client.post("/research/scan?execute=true")
    copytrade = client.post("/copytrade/run?execute=true")

    assert proposal.status_code == 403
    assert scan.status_code == 403
    assert copytrade.status_code == 403
    assert "PAPER_AUTOMATION_ENABLED=true" in proposal.json()["detail"]
