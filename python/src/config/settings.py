"""Application configuration.

Secrets from /etc/alpaca/env or environment.
TRADING_MODE forced to paper in this phase.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _load_system_env() -> None:
    import os

    system_env = Path("/etc/alpaca/env")
    if system_env.is_file():
        for line in system_env.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


_load_system_env()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    trading_mode: Literal["paper"] = Field(default="paper", alias="TRADING_MODE")

    alpaca_api_key: str = Field(default="", alias="ALPACA_API_KEY")
    alpaca_secret_key: str = Field(default="", alias="ALPACA_SECRET_KEY")
    alpaca_base_url: str = Field(
        default="https://paper-api.alpaca.markets",
        alias="ALPACA_BASE_URL",
    )

    database_url: str = Field(
        default="sqlite:///./data/trading.db",
        alias="DATABASE_URL",
    )

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # Progress report email (optional)
    report_email_to: str = Field(default="", alias="REPORT_EMAIL_TO")
    smtp_host: str = Field(default="", alias="SMTP_HOST")
    smtp_port: int = Field(default=587, alias="SMTP_PORT")
    smtp_user: str = Field(default="", alias="SMTP_USER")
    smtp_password: str = Field(default="", alias="SMTP_PASSWORD")
    smtp_from: str = Field(default="", alias="SMTP_FROM")

    @field_validator("trading_mode")
    @classmethod
    def force_paper(cls, v: str) -> str:
        if v.lower() != "paper":
            raise ValueError(
                "TRADING_MODE must be 'paper'. Live trading is deliberately disabled."
            )
        return "paper"

    @property
    def is_paper(self) -> bool:
        return self.trading_mode == "paper"

    def validate_credentials(self) -> None:
        if not self.alpaca_api_key or not self.alpaca_secret_key:
            raise ValueError(
                "ALPACA_API_KEY and ALPACA_SECRET_KEY must be set "
                "(via /etc/alpaca/env or environment variables)."
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
