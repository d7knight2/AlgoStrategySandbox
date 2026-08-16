"""SQLite models for audit trail and performance tracking."""

from datetime import datetime
from typing import Optional

from sqlalchemy import String, Float, DateTime, Integer, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from src.database.session import Base


class SystemEvent(Base):
    """Generic system / health / audit event."""

    __tablename__ = "system_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AccountSnapshot(Base):
    """Periodic account snapshot for performance tracking."""

    __tablename__ = "account_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    equity: Mapped[float] = mapped_column(Float)
    cash: Mapped[float] = mapped_column(Float)
    buying_power: Mapped[float] = mapped_column(Float)
    portfolio_value: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SignalRecord(Base):
    """Record of every generated signal for auditability."""

    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(16), index=True)
    signal_score: Mapped[float] = mapped_column(Float)
    decision: Mapped[str] = mapped_column(String(8))  # BUY / SELL / HOLD
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    indicators_json: Mapped[str] = mapped_column(Text)  # serialized indicators
    strategy_version: Mapped[str] = mapped_column(String(32), default="v001")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class TradeProposal(Base):
    """Proposed trade that went through the risk engine (accepted or rejected)."""

    __tablename__ = "trade_proposals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(16), index=True)
    side: Mapped[str] = mapped_column(String(8))
    qty: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    notional: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    risk_decision: Mapped[str] = mapped_column(String(16))  # ALLOW / REJECT
    risk_reasons: Mapped[str] = mapped_column(Text, default="")
    executed: Mapped[bool] = mapped_column(Boolean, default=False)
    strategy_version: Mapped[str] = mapped_column(String(32), default="v001")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class TradeFill(Base):
    """Actual fills (paper or live) for audit / tax ledger."""

    __tablename__ = "trade_fills"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(16), index=True)
    side: Mapped[str] = mapped_column(String(8))
    qty: Mapped[float] = mapped_column(Float)
    price: Mapped[float] = mapped_column(Float)
    notional: Mapped[float] = mapped_column(Float)
    order_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    fill_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    fees: Mapped[float] = mapped_column(Float, default=0.0)
    strategy_version: Mapped[str] = mapped_column(String(32), default="v001")
    mode: Mapped[str] = mapped_column(String(16), default="paper")  # paper | live
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
