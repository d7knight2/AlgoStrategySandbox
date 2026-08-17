"""MCP tooling: structured failures and diagnostics (no live network)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import httpx
import pytest

from src.mcp.tooling import (
    api_request,
    clear_failures,
    diagnostics,
    error_payload,
    hint_for,
    recent_failures,
    safe_tool,
)


@pytest.fixture(autouse=True)
def _reset_failures():
    clear_failures()
    yield
    clear_failures()


def test_safe_tool_success_returns_json():
    raw = safe_tool("demo", lambda: {"status": "ok", "n": 1})
    data = json.loads(raw)
    assert data["status"] == "ok"
    assert data["n"] == 1
    assert "ok" not in data or data.get("status") == "ok"
    assert recent_failures() == []


def test_safe_tool_failure_is_structured():
    def _boom():
        raise ConnectionError("connection refused")

    raw = safe_tool("api_health", _boom)
    data = json.loads(raw)
    assert data["ok"] is False
    assert data["tool"] == "api_health"
    assert data["error_type"] == "ConnectionError"
    assert "connection refused" in data["error"]
    assert data["request_id"]
    assert data["hint"]
    assert data["log_file"]
    assert recent_failures()[0]["tool"] == "api_health"


def test_hint_for_connect_error():
    exc = httpx.ConnectError("failed")
    hint = hint_for(exc)
    assert "8080" in hint
    assert "trading-api" in hint


def test_hint_for_http_status():
    request = httpx.Request("GET", "http://127.0.0.1:8080/health")
    response = httpx.Response(503, request=request, text="backend down")
    exc = httpx.HTTPStatusError("boom", request=request, response=response)
    payload = error_payload("api_health", exc, request_id="abc123")
    assert payload["status_code"] == 503
    assert "backend down" in payload["response_body"]
    assert "HTTP 503" in payload["hint"]


def test_api_request_logs_http_error(monkeypatch):
    request = httpx.Request("GET", "http://127.0.0.1:8080/health")
    response = httpx.Response(500, request=request, text="nope")

    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = False
    mock_client.request.return_value = response

    monkeypatch.setattr("src.mcp.tooling.httpx.Client", lambda **_k: mock_client)

    with pytest.raises(httpx.HTTPStatusError):
        api_request("GET", "/health")


def test_diagnostics_when_api_down(monkeypatch):
    def _raise(*_a, **_k):
        raise httpx.ConnectError("failed")

    monkeypatch.setattr("src.mcp.tooling.api_request", _raise)
    snap = diagnostics()
    assert snap["ok"] is False
    assert snap["api"]["reachable"] is False
    assert snap["api"]["error_type"] == "ConnectError"
    assert "telegram_configured" in snap
    assert "alpaca_keys_set" in snap
    assert snap["recent_failures"] == []
