"""
SQLAlchemy ORM models for the trading ecosystem.
Covers trades, models, performance, allocations, portfolio, regimes, and risk events.
"""

import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    JSON,
)
from sqlalchemy.orm import relationship

from db.database import Base


# ── Enums ────────────────────────────────────────────────────────────────────

class TradeDirection(str, enum.Enum):
    LONG = "long"
    SHORT = "short"


class TradeStatus(str, enum.Enum):
    PENDING = "pending"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class TradingModeEnum(str, enum.Enum):
    BACKTEST = "backtest"
    PAPER = "paper"
    LIVE = "live"


class MarketRegime(str, enum.Enum):
    LOW_VOL_BULL = "low_vol_bull"
    HIGH_VOL_BULL = "high_vol_bull"
    LOW_VOL_BEAR = "low_vol_bear"
    HIGH_VOL_BEAR = "high_vol_bear"
    SIDEWAYS = "sideways"


class RiskEventType(str, enum.Enum):
    MAX_DRAWDOWN_BREACH = "max_drawdown_breach"
    POSITION_LIMIT_HIT = "position_limit_hit"
    EXPOSURE_LIMIT_HIT = "exposure_limit_hit"
    STOP_LOSS_TRIGGERED = "stop_loss_triggered"
    TRADE_FREQUENCY_LIMIT = "trade_frequency_limit"
    MANUAL_HALT = "manual_halt"


class BrokerType(str, enum.Enum):
    ALPACA = "alpaca"
    WEBULL = "webull"


# ── Models ───────────────────────────────────────────────────────────────────

class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, autoincrement=True)
    model_id = Column(Integer, ForeignKey("trading_models.id"), nullable=False)
    symbol = Column(String(16), nullable=False)
    direction = Column(Enum(TradeDirection), nullable=False)
    quantity = Column(Float, nullable=False)
    entry_price = Column(Float, nullable=True)
    exit_price = Column(Float, nullable=True)
    pnl = Column(Float, nullable=True)
    pnl_pct = Column(Float, nullable=True)
    status = Column(Enum(TradeStatus), default=TradeStatus.PENDING)
    mode = Column(Enum(TradingModeEnum), nullable=False)
    order_id = Column(String(128), nullable=True)
    slippage = Column(Float, default=0.0)
    commission = Column(Float, default=0.0)
    entry_time = Column(DateTime, default=datetime.utcnow)
    exit_time = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)

    model = relationship("TradingModel", back_populates="trades")

    __table_args__ = (
        Index("ix_trades_symbol_time", "symbol", "entry_time"),
        Index("ix_trades_model_status", "model_id", "status"),
    )


class TradingModel(Base):
    __tablename__ = "trading_models"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), unique=True, nullable=False)
    model_type = Column(String(64), nullable=False)
    version = Column(String(32), default="1.0.0")
    is_active = Column(Boolean, default=True)
    parameters = Column(JSON, default=dict)
    artifact_path = Column(String(512), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    trades = relationship("Trade", back_populates="model")
    performance_records = relationship("ModelPerformance", back_populates="model")
    allocations = relationship("CapitalAllocation", back_populates="model")


class ModelPerformance(Base):
    __tablename__ = "model_performance"

    id = Column(Integer, primary_key=True, autoincrement=True)
    model_id = Column(Integer, ForeignKey("trading_models.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    sharpe_ratio = Column(Float, nullable=True)
    sortino_ratio = Column(Float, nullable=True)
    win_rate = Column(Float, nullable=True)
    profit_factor = Column(Float, nullable=True)
    max_drawdown = Column(Float, nullable=True)
    total_return = Column(Float, nullable=True)
    num_trades = Column(Integer, default=0)
    avg_trade_pnl = Column(Float, nullable=True)
    rolling_window_days = Column(Integer, default=30)
    mode = Column(Enum(TradingModeEnum), nullable=False)

    model = relationship("TradingModel", back_populates="performance_records")

    __table_args__ = (
        Index("ix_perf_model_time", "model_id", "timestamp"),
    )


class CapitalAllocation(Base):
    __tablename__ = "capital_allocations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    model_id = Column(Integer, ForeignKey("trading_models.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    weight = Column(Float, nullable=False)
    allocated_capital = Column(Float, nullable=False)
    reason = Column(Text, nullable=True)

    model = relationship("TradingModel", back_populates="allocations")

    __table_args__ = (
        Index("ix_alloc_model_time", "model_id", "timestamp"),
    )


class PortfolioSnapshot(Base):
    __tablename__ = "portfolio_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    total_equity = Column(Float, nullable=False)
    cash = Column(Float, nullable=False)
    positions_value = Column(Float, nullable=False)
    unrealized_pnl = Column(Float, nullable=False)
    realized_pnl = Column(Float, nullable=False)
    num_open_positions = Column(Integer, default=0)
    exposure_pct = Column(Float, nullable=False)
    drawdown_pct = Column(Float, nullable=False)
    mode = Column(Enum(TradingModeEnum), nullable=False)
    positions_detail = Column(JSON, default=dict)

    __table_args__ = (
        Index("ix_portfolio_time", "timestamp"),
    )


class MarketRegimeRecord(Base):
    __tablename__ = "market_regimes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    regime = Column(Enum(MarketRegime), nullable=False)
    confidence = Column(Float, nullable=True)
    volatility_20d = Column(Float, nullable=True)
    trend_strength = Column(Float, nullable=True)
    metadata_json = Column(JSON, default=dict)

    __table_args__ = (
        Index("ix_regime_time", "timestamp"),
    )


class RiskEvent(Base):
    __tablename__ = "risk_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    event_type = Column(Enum(RiskEventType), nullable=False)
    severity = Column(String(16), default="warning")
    description = Column(Text, nullable=True)
    model_id = Column(Integer, ForeignKey("trading_models.id"), nullable=True)
    action_taken = Column(Text, nullable=True)
    metadata_json = Column(JSON, default=dict)

    __table_args__ = (
        Index("ix_risk_event_time", "timestamp"),
    )


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    display_name = Column(String(100), nullable=False)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    email_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    broker_credentials = relationship("BrokerCredential", back_populates="user", cascade="all, delete-orphan")
    email_verifications = relationship("EmailVerification", back_populates="user", cascade="all, delete-orphan")


class EmailVerification(Base):
    __tablename__ = "email_verifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    token = Column(String(255), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="email_verifications")


class BrokerCredential(Base):
    __tablename__ = "broker_credentials"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    broker_type = Column(Enum(BrokerType), nullable=False)
    encrypted_api_key = Column(Text, nullable=False)
    encrypted_api_secret = Column(Text, nullable=False)
    is_paper = Column(Boolean, default=True)
    nickname = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="broker_credentials")

    __table_args__ = (
        Index("ix_broker_cred_user", "user_id"),
    )


class PaperTradeStatus(str, enum.Enum):
    OPEN = "open"
    CLOSED = "closed"


class PaperPortfolio(Base):
    __tablename__ = "paper_portfolios"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    cash = Column(Float, nullable=False, default=1_000_000.0)
    initial_capital = Column(Float, nullable=False, default=1_000_000.0)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")
    positions = relationship("PaperPosition", back_populates="portfolio", cascade="all, delete-orphan")
    trades = relationship("PaperTrade", back_populates="portfolio", cascade="all, delete-orphan")


class PaperPosition(Base):
    __tablename__ = "paper_positions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    portfolio_id = Column(Integer, ForeignKey("paper_portfolios.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    symbol = Column(String(16), nullable=False)
    quantity = Column(Float, nullable=False)
    avg_entry_price = Column(Float, nullable=False)
    current_price = Column(Float, nullable=True)
    unrealized_pnl = Column(Float, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    portfolio = relationship("PaperPortfolio", back_populates="positions")

    __table_args__ = (
        Index("ix_paper_pos_user_symbol", "user_id", "symbol", unique=True),
    )


class PaperTrade(Base):
    __tablename__ = "paper_trades"

    id = Column(Integer, primary_key=True, autoincrement=True)
    portfolio_id = Column(Integer, ForeignKey("paper_portfolios.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    symbol = Column(String(16), nullable=False)
    direction = Column(Enum(TradeDirection), nullable=False)
    quantity = Column(Float, nullable=False)
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float, nullable=True)
    pnl = Column(Float, nullable=True)
    status = Column(Enum(PaperTradeStatus), default=PaperTradeStatus.OPEN)
    entry_time = Column(DateTime, default=datetime.utcnow)
    exit_time = Column(DateTime, nullable=True)

    portfolio = relationship("PaperPortfolio", back_populates="trades")

    __table_args__ = (
        Index("ix_paper_trade_user", "user_id"),
    )


class Strategy(Base):
    __tablename__ = "strategies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    conditions = Column(JSON, nullable=False)
    action = Column(String(16), nullable=False, default="BUY")
    stop_loss_pct = Column(Float, default=0.02)
    take_profit_pct = Column(Float, default=0.05)
    position_size_pct = Column(Float, default=0.1)
    timeframe = Column(String(16), default="1D")
    diagnostics = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_strategy_user", "user_id"),
        Index("ix_strategy_name", "name"),
    )
