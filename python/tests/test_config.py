"""Configuration tests."""

import os
import pytest
from pydantic import ValidationError


def test_trading_mode_forced_to_paper(monkeypatch):
    monkeypatch.setenv("TRADING_MODE", "paper")
    monkeypatch.setenv("ALPACA_API_KEY", "testkey")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "testsecret")

    # Clear cached settings
    from src.config.settings import get_settings
    get_settings.cache_clear()

    from src.config import settings
    assert settings.trading_mode == "paper"
    assert settings.is_paper is True


def test_live_mode_rejected(monkeypatch):
    monkeypatch.setenv("TRADING_MODE", "live")
    monkeypatch.setenv("ALPACA_API_KEY", "testkey")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "testsecret")

    from src.config.settings import get_settings, Settings
    get_settings.cache_clear()

    with pytest.raises(ValidationError):
        Settings()
