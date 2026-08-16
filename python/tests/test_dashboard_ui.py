"""UI / page-level tests for the trading dashboard.

These do not require a live Alpaca connection for the HTML shell.
Endpoints that call Alpaca are tested for route presence and error shape.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


def test_dashboard_returns_html():
    r = client.get("/dashboard")
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")
    body = r.text
    assert "Paper Portfolio" in body
    assert "candleHost" in body
    assert "lightweight-charts" in body
    assert "symbolSelect" in body
    assert "eqChart" in body
    assert "STOP" in body
    assert "Scan signals" in body


def test_dashboard_has_strategy_catalog_markers():
    r = client.get("/dashboard")
    assert r.status_code == 200
    # JS catalog embeds strategy names
    assert "Signal scorer" in r.text
    assert "SMA regime" in r.text or "sma_regime" in r.text
    assert "ORB" in r.text or "Opening range" in r.text


def test_dashboard_has_range_controls():
    r = client.get("/dashboard")
    body = r.text
    assert "setRange(30" in body
    assert "setRange(60" in body
    assert "setRange(120" in body
    assert "setRange(250" in body


def test_dashboard_has_pwa_hooks():
    r = client.get("/dashboard")
    body = r.text
    assert "apple-mobile-web-app-capable" in body
    assert "manifest.json" in body
    assert "serviceWorker" in body


def test_static_manifest_available():
    r = client.get("/static/manifest.json")
    assert r.status_code == 200
    data = r.json()
    assert data.get("name")
    assert data.get("display") == "standalone"
    assert data.get("start_url") == "/dashboard"


def test_static_icons_available():
    for name in ("icon-180.png", "icon-192.png", "icon-512.png"):
        r = client.get(f"/static/{name}")
        assert r.status_code == 200, name
        assert r.headers.get("content-type", "").startswith("image/") or len(r.content) > 100


def test_health_json_shape():
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["trading_mode"] == "paper"
    assert data["live_trading_enabled"] is False
    assert "risk_engine" in data


def test_root_points_to_dashboard():
    r = client.get("/")
    assert r.status_code == 200
    data = r.json()
    assert data.get("dashboard") == "/dashboard"


def test_template_file_exists():
    path = Path(__file__).resolve().parents[1] / "src" / "monitoring" / "templates" / "dashboard.html"
    assert path.is_file()
    text = path.read_text()
    assert "addCandlestickSeries" in text or "Candlestick" in text or "candleSeries" in text
    assert "LightweightCharts" in text


@pytest.mark.parametrize("path", [
    "/health",
    "/dashboard",
    "/static/manifest.json",
    "/",
])
def test_critical_routes_not_404(path):
    r = client.get(path)
    assert r.status_code != 404
    assert r.status_code in (200, 307, 308)
