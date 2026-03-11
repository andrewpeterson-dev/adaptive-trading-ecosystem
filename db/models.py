"""
SQLAlchemy ORM models for the trading ecosystem.
Covers trades, models, performance, allocations, portfolio, regimes, and risk events.
"""

import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    Date,
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


def _enum(cls):
    """Return an Enum column type that uses enum .value strings (not .name).

    PostgreSQL native enums are created with the lowercase string values
    (e.g. "webull"), so we must pass values_callable to stop SQLAlchemy
    from using the uppercase member names ("WEBULL") instead.
    """
    return Enum(cls, values_callable=lambda obj: [e.value for e in obj])


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


class SystemEventType(str, enum.Enum):
    MODE_SWITCH = "mode_switch"
    STRATEGY_PROMOTED = "strategy_promoted"
    TRADE_EXECUTED = "trade_executed"
    TRADE_FAILED = "trade_failed"
    ACCOUNT_SYNC = "account_sync"
    RISK_LIMIT_TRIGGERED = "risk_limit_triggered"
    KILL_SWITCH_TOGGLED = "kill_switch_toggled"
    BOT_ENABLED = "bot_enabled"
    BOT_DISABLED = "bot_disabled"


# ── Models ───────────────────────────────────────────────────────────────────

class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    model_id = Column(Integer, ForeignKey("trading_models.id"), nullable=False)
    symbol = Column(String(16), nullable=False)
    direction = Column(_enum(TradeDirection), nullable=False)
    quantity = Column(Float, nullable=False)
    entry_price = Column(Float, nullable=True)
    exit_price = Column(Float, nullable=True)
    pnl = Column(Float, nullable=True)
    pnl_pct = Column(Float, nullable=True)
    status = Column(_enum(TradeStatus), default=TradeStatus.PENDING)
    mode = Column(_enum(TradingModeEnum), nullable=False)
    order_id = Column(String(128), nullable=True)
    slippage = Column(Float, default=0.0)
    commission = Column(Float, default=0.0)
    entry_time = Column(DateTime, default=datetime.utcnow)
    exit_time = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)

    user = relationship("User", back_populates="trades")
    model = relationship("TradingModel", back_populates="trades")

    __table_args__ = (
        Index("ix_trades_user_id", "user_id"),
        Index("ix_trades_user_mode_time", "user_id", "mode", "entry_time"),
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
    mode = Column(_enum(TradingModeEnum), nullable=False, default=TradingModeEnum.PAPER)
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
    mode = Column(_enum(TradingModeEnum), nullable=False)

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
    mode = Column(_enum(TradingModeEnum), nullable=False)

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
    mode = Column(_enum(TradingModeEnum), nullable=False)
    positions_detail = Column(JSON, default=dict)

    __table_args__ = (
        Index("ix_portfolio_time", "timestamp"),
    )


class MarketRegimeRecord(Base):
    __tablename__ = "market_regimes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    regime = Column(_enum(MarketRegime), nullable=False)
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
    event_type = Column(_enum(RiskEventType), nullable=False)
    severity = Column(String(16), default="warning")
    description = Column(Text, nullable=True)
    model_id = Column(Integer, ForeignKey("trading_models.id"), nullable=True)
    action_taken = Column(Text, nullable=True)
    mode = Column(_enum(TradingModeEnum), nullable=False)
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

    trades = relationship("Trade", back_populates="user")
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
    broker_type = Column(_enum(BrokerType), nullable=False)
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
    direction = Column(_enum(TradeDirection), nullable=False)
    quantity = Column(Float, nullable=False)
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float, nullable=True)
    pnl = Column(Float, nullable=True)
    status = Column(_enum(PaperTradeStatus), default=PaperTradeStatus.OPEN)
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
    condition_groups = Column(JSON, nullable=True)
    symbols = Column(JSON, nullable=True)
    commission_pct = Column(Float, default=0.001)
    slippage_pct = Column(Float, default=0.0005)
    trailing_stop_pct = Column(Float, nullable=True)
    exit_after_bars = Column(Integer, nullable=True)
    cooldown_bars = Column(Integer, default=0)
    max_trades_per_day = Column(Integer, default=0)
    max_exposure_pct = Column(Float, default=1.0)
    max_loss_pct = Column(Float, default=0.0)
    strategy_type = Column(String(32), default="manual")
    source_prompt = Column(Text, nullable=True)
    ai_context = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_strategy_user", "user_id"),
        Index("ix_strategy_name", "name"),
    )


# ── API Connection Management ─────────────────────────────────────────────────

class ApiProviderType(str, enum.Enum):
    BROKERAGE = "brokerage"
    MARKET_DATA = "market_data"
    OPTIONS_DATA = "options_data"
    NEWS = "news"
    FUNDAMENTALS = "fundamentals"
    MACRO = "macro"
    CRYPTO_BROKER = "crypto_broker"


class ApiProvider(Base):
    __tablename__ = "api_providers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    slug = Column(String(64), unique=True, nullable=False)
    name = Column(String(128), nullable=False)
    api_type = Column(_enum(ApiProviderType), nullable=False)
    supports_trading = Column(Boolean, default=False)
    supports_paper = Column(Boolean, default=False)
    supports_market_data = Column(Boolean, default=False)
    supports_options = Column(Boolean, default=False)
    supports_crypto = Column(Boolean, default=False)
    supports_stocks = Column(Boolean, default=False)
    supports_order_placement = Column(Boolean, default=False)
    supports_positions_streaming = Column(Boolean, default=False)
    requires_secret = Column(Boolean, default=True)
    # unified_mode: one credential set covers all modes (paper, live) and data.
    # When True the UI hides the paper/live toggle — mode is selected at trade time.
    unified_mode = Column(Boolean, default=False)
    credential_note = Column(String(512), nullable=True)  # shown in connect modal
    credential_fields = Column(JSON, nullable=False)
    docs_url = Column(String(512), nullable=True)
    is_available = Column(Boolean, default=True)


class UserApiConnection(Base):
    __tablename__ = "user_api_connections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    provider_id = Column(Integer, ForeignKey("api_providers.id"), nullable=False)
    encrypted_credentials = Column(Text, nullable=False)
    status = Column(String(32), default="disconnected")
    error_message = Column(String(512), nullable=True)
    is_paper = Column(Boolean, default=True)
    nickname = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_tested_at = Column(DateTime, nullable=True)

    provider = relationship("ApiProvider")

    __table_args__ = (
        Index("ix_user_api_conn_user", "user_id"),
        Index("ix_user_api_conn_provider", "provider_id"),
    )


class UserApiSettings(Base):
    __tablename__ = "user_api_settings"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    active_equity_broker_id = Column(Integer, ForeignKey("user_api_connections.id"), nullable=True)
    active_crypto_broker_id = Column(Integer, ForeignKey("user_api_connections.id"), nullable=True)
    primary_market_data_id = Column(Integer, ForeignKey("user_api_connections.id"), nullable=True)
    fallback_market_data_ids = Column(JSON, default=list)
    primary_options_data_id = Column(Integer, ForeignKey("user_api_connections.id"), nullable=True)
    options_fallback_enabled = Column(Boolean, default=False)
    options_provider_connection_id = Column(Integer, ForeignKey("user_api_connections.id"), nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ── Paper / Live Mode Separation Models ──────────────────────────────────────


class UserTradingSession(Base):
    __tablename__ = "user_trading_sessions"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    active_mode = Column(_enum(TradingModeEnum), nullable=False, default=TradingModeEnum.PAPER)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class StrategyTemplate(Base):
    __tablename__ = "strategy_templates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    conditions = Column(JSON, nullable=False)
    condition_groups = Column(JSON, nullable=True)
    action = Column(String(16), nullable=False, default="BUY")
    stop_loss_pct = Column(Float, default=0.02)
    take_profit_pct = Column(Float, default=0.05)
    timeframe = Column(String(16), default="1D")
    diagnostics = Column(JSON, nullable=True)
    symbols = Column(JSON, nullable=True)
    commission_pct = Column(Float, default=0.001)
    slippage_pct = Column(Float, default=0.0005)
    trailing_stop_pct = Column(Float, nullable=True)
    exit_after_bars = Column(Integer, nullable=True)
    cooldown_bars = Column(Integer, default=0)
    max_trades_per_day = Column(Integer, default=0)
    max_exposure_pct = Column(Float, default=1.0)
    max_loss_pct = Column(Float, default=0.0)
    strategy_type = Column(String(32), default="manual")
    source_prompt = Column(Text, nullable=True)
    ai_context = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    instances = relationship("StrategyInstance", back_populates="template")

    __table_args__ = (
        Index("ix_strategy_template_user", "user_id"),
    )


class StrategyInstance(Base):
    __tablename__ = "strategy_instances"

    id = Column(Integer, primary_key=True, autoincrement=True)
    template_id = Column(Integer, ForeignKey("strategy_templates.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    mode = Column(_enum(TradingModeEnum), nullable=False)
    is_active = Column(Boolean, default=True)
    position_size_pct = Column(Float, default=0.1)
    max_position_value = Column(Float, nullable=True)
    nickname = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    promoted_from_id = Column(Integer, ForeignKey("strategy_instances.id"), nullable=True)

    template = relationship("StrategyTemplate", back_populates="instances")

    __table_args__ = (
        Index("ix_strategy_instance_user_mode", "user_id", "mode"),
    )


class UserBrokerAccount(Base):
    __tablename__ = "user_broker_accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    connection_id = Column(Integer, ForeignKey("user_api_connections.id"), nullable=False)
    broker_account_id = Column(String(128), nullable=False)
    account_type = Column(String(32), nullable=False)
    nickname = Column(String(100), nullable=True)
    discovered_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_user_broker_acct_user_type", "user_id", "account_type"),
    )


class UserRiskLimits(Base):
    __tablename__ = "user_risk_limits"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    mode = Column(_enum(TradingModeEnum), primary_key=True)
    daily_loss_limit = Column(Float, nullable=True)
    max_position_size_pct = Column(Float, default=0.25)
    max_open_positions = Column(Integer, default=10)
    kill_switch_active = Column(Boolean, default=False)
    live_bot_trading_confirmed = Column(Boolean, default=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SystemEvent(Base):
    __tablename__ = "system_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    event_type = Column(_enum(SystemEventType), nullable=False)
    mode = Column(_enum(TradingModeEnum), nullable=False)
    severity = Column(String(16), default="info")
    description = Column(Text, nullable=True)
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_system_events_user_time", "user_id", "created_at"),
        Index("ix_system_events_type", "event_type"),
    )


class TradeEvent(Base):
    """Individual trade with AI decision metadata — signals, confidence, regime, reasoning."""
    __tablename__ = "trade_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    strategy_id = Column(Integer, nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    symbol = Column(String(16), nullable=False)
    direction = Column(String(8), nullable=False)  # long / short
    entry_price = Column(Float, nullable=True)
    exit_price = Column(Float, nullable=True)
    entry_time = Column(DateTime, nullable=True)
    exit_time = Column(DateTime, nullable=True)
    pnl = Column(Float, nullable=True)
    pnl_pct = Column(Float, nullable=True)
    confidence = Column(Float, nullable=True)
    regime = Column(String(32), nullable=True)
    signals_json = Column(JSON, default=list)    # list of signal description strings
    approved = Column(Boolean, default=True)
    rejection_reason = Column(Text, nullable=True)
    reasoning_text = Column(Text, nullable=True)
    model_name = Column(String(64), nullable=True)

    __table_args__ = (
        Index("ix_trade_events_strategy_time", "strategy_id", "timestamp"),
    )


class StrategySnapshot(Base):
    """Periodic performance snapshot for a strategy — drives equity curve & rolling metrics."""
    __tablename__ = "strategy_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    strategy_id = Column(Integer, nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    equity = Column(Float, nullable=False)
    realized_pnl = Column(Float, nullable=True)
    num_trades = Column(Integer, default=0)
    win_rate = Column(Float, nullable=True)
    sharpe = Column(Float, nullable=True)
    max_drawdown = Column(Float, nullable=True)
    regime = Column(String(32), nullable=True)
    metrics_json = Column(JSON, default=dict)

    __table_args__ = (
        Index("ix_strategy_snapshot_strategy_time", "strategy_id", "timestamp"),
    )


class OptionSimTrade(Base):
    """
    Tracks real Tradier paper options orders routed through the options fallback system.
    P&L here feeds ledgerOptionsSim. Never mix with ledgerBroker.
    """
    __tablename__ = "option_sim_trades"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    connection_id = Column(Integer, ForeignKey("user_api_connections.id"), nullable=False)
    tradier_order_id = Column(String(64), nullable=True)
    symbol = Column(String(32), nullable=False)
    option_symbol = Column(String(32), nullable=True)
    option_type = Column(String(4), nullable=False)
    strike = Column(Float, nullable=False)
    expiry = Column(Date, nullable=False)
    qty = Column(Integer, nullable=False)
    fill_price = Column(Float, nullable=True)
    realized_pnl = Column(Float, nullable=True)
    status = Column(String(16), default="pending")
    opened_at = Column(DateTime, default=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_option_sim_user", "user_id"),
        Index("ix_option_sim_status", "status"),
    )
