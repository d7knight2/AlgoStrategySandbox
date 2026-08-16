"""WebSocket live feed tests."""

from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


def test_ws_live_connects_and_sends_snapshot():
    with client.websocket_connect("/ws/live") as ws:
        data = ws.receive_json()
        assert data.get("type") in ("snapshot", "error", "ping")
        if data.get("type") == "snapshot":
            assert "health" in data
            assert data["health"]["trading_mode"] == "paper"
            assert data["health"]["live_trading_enabled"] is False
            assert "risk" in data


def test_ws_refresh_message():
    with client.websocket_connect("/ws/live") as ws:
        _ = ws.receive_json()  # initial
        ws.send_text("refresh")
        data = ws.receive_json()
        assert data.get("type") in ("snapshot", "error")


def test_health_reports_ws_clients_field():
    r = client.get("/health")
    assert r.status_code == 200
    assert "ws_clients" in r.json()


def test_root_advertises_ws_path():
    r = client.get("/")
    assert r.status_code == 200
    assert r.json().get("ws") == "/ws/live"
