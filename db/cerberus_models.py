"""
SQLAlchemy ORM models for the Cerberus subsystem.

All tables are prefixed with ``cerberus_`` to avoid conflicts with the core
trading models.  Primary keys use UUID strings (String(36)) instead of
auto-incrementing integers so that IDs can be generated client-side and
remain globally unique across services.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
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


def _uuid() -> str:
    return str(uuid.uuid4())


def _enum(cls):
    """Return an Enum column type that uses enum .value strings (not .name)."""
    from sqlalchemy import Enum

    return Enum(cls, values_callable=lambda obj: [e.value for e in obj])


# ── Enums ────────────────────────────────────────────────────────────────────

class AccountMode(str, enum.Enum):
    PAPER = "paper"
    LIVE = "live"


class BotStatus(str, enum.Enum):
    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"
    DELETED = "deleted"


class ConversationMode(str, enum.Enum):
    CHAT = "chat"
    ANALYSIS = "analysis"
    TRADE = "trade"
    BACKTEST = "backtest"
    BUILD = "build"
    PORTFOLIO = "portfolio"
    RESEARCH = "research"
    STRATEGY = "strategy"


class MessageRole(str, enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class ProposalStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    EXPIRED = "expired"
    EXECUTED = "executed"
    FAILED = "failed"


class DocumentStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    INDEXED = "indexed"
    FAILED = "failed"


class ToolSideEffect(str, enum.Enum):
    NONE = "none"
    READ = "read"
    WRITE = "write"
    TRADE = "trade"
    NOTIFY = "notify"


# ── Models ───────────────────────────────────────────────────────────────────

class CerberusBrokerageAccount(Base):
    """Provider connections — links a user to a brokerage provider."""
    __tablename__ = "cerberus_brokerage_accounts"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    provider = Column(String(64), nullable=False)
    account_mode = Column(_enum(AccountMode), nullable=False, default=AccountMode.PAPER)
    encrypted_access_token = Column(Text, nullable=True)
    encrypted_refresh_token = Column(Text, nullable=True)
    metadata_json = Column(JSON, default=dict)
    last_synced_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    portfolio_snapshots = relationship("CerberusPortfolioSnapshot", back_populates="brokerage_account")
    positions = relationship("CerberusPosition", back_populates="brokerage_account")
    orders = relationship("CerberusOrder", back_populates="brokerage_account")
    trades = relationship("CerberusTrade", back_populates="brokerage_account")

    __table_args__ = (
        Index("ix_cerberus_brkacct_user", "user_id"),
        Index("ix_cerberus_brkacct_provider", "provider"),
    )


class CerberusPortfolioSnapshot(Base):
    """Point-in-time portfolio snapshots."""
    __tablename__ = "cerberus_portfolio_snapshots"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    brokerage_account_id = Column(String(36), ForeignKey("cerberus_brokerage_accounts.id"), nullable=False)
    snapshot_ts = Column(DateTime, nullable=False, default=datetime.utcnow)
    cash = Column(Float, nullable=True)
    equity = Column(Float, nullable=True)
    buying_power = Column(Float, nullable=True)
    margin_used = Column(Float, nullable=True)
    day_pnl = Column(Float, nullable=True)
    total_pnl = Column(Float, nullable=True)
    payload_json = Column(JSON, default=dict)

    brokerage_account = relationship("CerberusBrokerageAccount", back_populates="portfolio_snapshots")

    __table_args__ = (
        Index("ix_cerberus_snap_user", "user_id"),
        Index("ix_cerberus_snap_acct_ts", "brokerage_account_id", "snapshot_ts"),
    )


class CerberusPosition(Base):
    """Current positions."""
    __tablename__ = "cerberus_positions"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    brokerage_account_id = Column(String(36), ForeignKey("cerberus_brokerage_accounts.id"), nullable=False)
    symbol = Column(String(32), nullable=False)
    asset_type = Column(String(32), nullable=True)
    quantity = Column(Float, nullable=False)
    avg_price = Column(Float, nullable=True)
    mark_price = Column(Float, nullable=True)
    market_value = Column(Float, nullable=True)
    unrealized_pnl = Column(Float, nullable=True)
    realized_pnl = Column(Float, nullable=True)
    greeks_json = Column(JSON, default=dict)
    metadata_json = Column(JSON, default=dict)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    brokerage_account = relationship("CerberusBrokerageAccount", back_populates="positions")

    __table_args__ = (
        Index("ix_cerberus_pos_user", "user_id"),
        Index("ix_cerberus_pos_acct_symbol", "brokerage_account_id", "symbol"),
    )


class CerberusOrder(Base):
    """Order records."""
    __tablename__ = "cerberus_orders"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    brokerage_account_id = Column(String(36), ForeignKey("cerberus_brokerage_accounts.id"), nullable=False)
    broker_order_id = Column(String(128), nullable=True)
    symbol = Column(String(32), nullable=False)
    asset_type = Column(String(32), nullable=True)
    side = Column(String(16), nullable=False)
    order_type = Column(String(32), nullable=False)
    tif = Column(String(16), nullable=True)
    quantity = Column(Float, nullable=False)
    limit_price = Column(Float, nullable=True)
    stop_price = Column(Float, nullable=True)
    status = Column(String(32), nullable=False, default="pending")
    payload_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    brokerage_account = relationship("CerberusBrokerageAccount", back_populates="orders")

    __table_args__ = (
        Index("ix_cerberus_ord_user", "user_id"),
        Index("ix_cerberus_ord_acct", "brokerage_account_id"),
        Index("ix_cerberus_ord_symbol_status", "symbol", "status"),
    )


class CerberusTrade(Base):
    """Trade records — completed trade lifecycle."""
    __tablename__ = "cerberus_trades"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    brokerage_account_id = Column(String(36), ForeignKey("cerberus_brokerage_accounts.id"), nullable=True)
    symbol = Column(String(32), nullable=False)
    asset_type = Column(String(32), nullable=True)
    side = Column(String(16), nullable=False)
    entry_ts = Column(DateTime, nullable=True)
    exit_ts = Column(DateTime, nullable=True)
    entry_price = Column(Float, nullable=True)
    exit_price = Column(Float, nullable=True)
    quantity = Column(Float, nullable=False)
    gross_pnl = Column(Float, nullable=True)
    net_pnl = Column(Float, nullable=True)
    return_pct = Column(Float, nullable=True)
    strategy_tag = Column(String(64), nullable=True)
    bot_id = Column(String(36), nullable=True)
    notes = Column(Text, nullable=True)
    payload_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

    brokerage_account = relationship("CerberusBrokerageAccount", back_populates="trades")

    __table_args__ = (
        Index("ix_cerberus_trd_user", "user_id"),
        Index("ix_cerberus_trd_symbol", "symbol"),
        Index("ix_cerberus_trd_strategy", "strategy_tag"),
        Index("ix_cerberus_trd_bot", "bot_id"),
    )


class CerberusBot(Base):
    """Bot definitions."""
    __tablename__ = "cerberus_bots"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(128), nullable=False)
    status = Column(
        _enum(BotStatus),
        nullable=False,
        default=BotStatus.DRAFT,
    )
    current_version_id = Column(String(36), nullable=True)
    learning_enabled = Column(Boolean, default=True)
    learning_status_json = Column(JSON, default=dict)
    last_optimization_at = Column(DateTime, nullable=True)
    allocated_capital = Column(Float, nullable=True, default=None)
    reasoning_model_config = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    versions = relationship("CerberusBotVersion", back_populates="bot", order_by="CerberusBotVersion.version_number")
    optimization_runs = relationship("CerberusBotOptimizationRun", back_populates="bot", order_by="CerberusBotOptimizationRun.created_at")

    __table_args__ = (
        Index("ix_cerberus_bot_user", "user_id"),
        CheckConstraint(
            "status IN ('draft','running','paused','stopped','error')",
            name="ck_cerberus_bot_status",
        ),
    )


class CerberusBotVersion(Base):
    """Bot version history."""
    __tablename__ = "cerberus_bot_versions"

    id = Column(String(36), primary_key=True, default=_uuid)
    bot_id = Column(String(36), ForeignKey("cerberus_bots.id"), nullable=False)
    version_number = Column(Integer, nullable=False)
    config_json = Column(JSON, default=dict)
    diff_summary = Column(Text, nullable=True)
    created_by = Column(String(64), nullable=True)
    backtest_required = Column(Boolean, default=False)
    backtest_id = Column(String(36), nullable=True)
    universe_config = Column(JSON, default=dict)
    override_level = Column(String(16), default="soft")
    created_at = Column(DateTime, default=datetime.utcnow)

    bot = relationship("CerberusBot", back_populates="versions")

    __table_args__ = (
        Index("ix_cerberus_botver_bot", "bot_id"),
        Index("ix_cerberus_botver_bot_num", "bot_id", "version_number", unique=True),
    )


class CerberusBotOptimizationRun(Base):
    """Optimization and learning history for autonomous bot tuning."""
    __tablename__ = "cerberus_bot_optimization_runs"

    id = Column(String(36), primary_key=True, default=_uuid)
    bot_id = Column(String(36), ForeignKey("cerberus_bots.id"), nullable=False)
    source_version_id = Column(String(36), ForeignKey("cerberus_bot_versions.id"), nullable=True)
    result_version_id = Column(String(36), ForeignKey("cerberus_bot_versions.id"), nullable=True)
    method = Column(String(64), nullable=False, default="parameter_optimization")
    status = Column(String(32), nullable=False, default="completed")
    metrics_json = Column(JSON, default=dict)
    adjustments_json = Column(JSON, default=dict)
    summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    bot = relationship("CerberusBot", back_populates="optimization_runs")

    __table_args__ = (
        Index("ix_cerberus_botopt_bot", "bot_id"),
        Index("ix_cerberus_botopt_created", "created_at"),
    )


class CerberusBacktest(Base):
    """Backtest records."""
    __tablename__ = "cerberus_backtests"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    bot_id = Column(String(36), nullable=True)
    bot_version_id = Column(String(36), nullable=True)
    strategy_name = Column(String(128), nullable=True)
    params_json = Column(JSON, default=dict)
    metrics_json = Column(JSON, default=dict)
    equity_curve_json = Column(JSON, default=dict)
    trades_json = Column(JSON, default=dict)
    leakage_checks_json = Column(JSON, default=dict)
    status = Column(String(32), nullable=False, default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_cerberus_bt_user", "user_id"),
        Index("ix_cerberus_bt_bot", "bot_id"),
    )


class CerberusConversationThread(Base):
    """Chat threads."""
    __tablename__ = "cerberus_conversation_threads"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(256), nullable=True)
    mode = Column(_enum(ConversationMode), nullable=False, default=ConversationMode.CHAT)
    latest_page = Column(String(128), nullable=True)
    latest_symbol = Column(String(32), nullable=True)
    summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    messages = relationship(
        "CerberusConversationMessage",
        back_populates="thread",
        order_by="CerberusConversationMessage.created_at",
    )

    __table_args__ = (
        Index("ix_cerberus_thread_user", "user_id"),
        Index("ix_cerberus_thread_updated", "updated_at"),
    )


class CerberusConversationMessage(Base):
    """Chat messages."""
    __tablename__ = "cerberus_conversation_messages"

    id = Column(String(36), primary_key=True, default=_uuid)
    thread_id = Column(String(36), ForeignKey("cerberus_conversation_threads.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role = Column(_enum(MessageRole), nullable=False)
    content_md = Column(Text, nullable=True)
    structured_json = Column(JSON, default=dict)
    model_name = Column(String(64), nullable=True)
    provider_name = Column(String(64), nullable=True)
    citations_json = Column(JSON, default=dict)
    tool_calls_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

    thread = relationship("CerberusConversationThread", back_populates="messages")

    __table_args__ = (
        Index("ix_cerberus_msg_thread", "thread_id"),
        Index("ix_cerberus_msg_user", "user_id"),
        Index("ix_cerberus_msg_thread_ts", "thread_id", "created_at"),
    )


class CerberusMemoryItem(Base):
    """Semantic memory items."""
    __tablename__ = "cerberus_memory_items"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    kind = Column(String(64), nullable=False)
    source_table = Column(String(128), nullable=True)
    source_id = Column(String(36), nullable=True)
    content = Column(Text, nullable=False)
    metadata_json = Column(JSON, default=dict)
    embedding_json = Column(Text, nullable=True)  # TEXT for SQLite compatibility
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_cerberus_mem_user", "user_id"),
        Index("ix_cerberus_mem_kind", "kind"),
        Index("ix_cerberus_mem_source", "source_table", "source_id"),
    )


class CerberusDocumentFile(Base):
    """Uploaded documents."""
    __tablename__ = "cerberus_document_files"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    original_filename = Column(String(512), nullable=False)
    mime_type = Column(String(128), nullable=True)
    storage_key = Column(String(512), nullable=False)
    doc_type = Column(String(64), nullable=True)
    status = Column(
        _enum(DocumentStatus),
        nullable=False,
        default=DocumentStatus.PENDING,
    )
    metadata_json = Column(JSON, default=dict)
    indexed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    chunks = relationship("CerberusDocumentChunk", back_populates="document", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_cerberus_docfile_user", "user_id"),
        Index("ix_cerberus_docfile_status", "status"),
        CheckConstraint(
            "status IN ('pending','processing','indexed','failed')",
            name="ck_cerberus_docfile_status",
        ),
    )


class CerberusDocumentChunk(Base):
    """Document chunks for vector search."""
    __tablename__ = "cerberus_document_chunks"

    id = Column(String(36), primary_key=True, default=_uuid)
    document_id = Column(String(36), ForeignKey("cerberus_document_files.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    page_number = Column(Integer, nullable=True)
    heading = Column(String(512), nullable=True)
    content = Column(Text, nullable=False)
    metadata_json = Column(JSON, default=dict)
    embedding_json = Column(Text, nullable=True)  # TEXT for SQLite compatibility
    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("CerberusDocumentFile", back_populates="chunks")

    __table_args__ = (
        Index("ix_cerberus_chunk_doc", "document_id"),
        Index("ix_cerberus_chunk_user", "user_id"),
        Index("ix_cerberus_chunk_doc_idx", "document_id", "chunk_index"),
    )


class CerberusUIContextEvent(Base):
    """UI page context events — tracks what the user is looking at."""
    __tablename__ = "cerberus_ui_context_events"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    thread_id = Column(String(36), nullable=True)
    current_page = Column(String(128), nullable=True)
    route = Column(String(256), nullable=True)
    visible_components = Column(JSON, default=dict)
    focused_component = Column(String(128), nullable=True)
    selected_symbol = Column(String(32), nullable=True)
    selected_account_id = Column(String(36), nullable=True)
    selected_bot_id = Column(String(36), nullable=True)
    component_state = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_cerberus_uictx_user", "user_id"),
        Index("ix_cerberus_uictx_thread", "thread_id"),
    )


class CerberusTradeProposal(Base):
    """Trade proposals generated by the AI."""
    __tablename__ = "cerberus_trade_proposals"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    thread_id = Column(String(36), ForeignKey("cerberus_conversation_threads.id"), nullable=True)
    proposal_json = Column(JSON, default=dict)
    risk_json = Column(JSON, default=dict)
    explanation_md = Column(Text, nullable=True)
    status = Column(
        _enum(ProposalStatus),
        nullable=False,
        default=ProposalStatus.PENDING,
    )
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    confirmations = relationship("CerberusTradeConfirmation", back_populates="proposal")

    __table_args__ = (
        Index("ix_cerberus_proposal_user", "user_id"),
        Index("ix_cerberus_proposal_thread", "thread_id"),
        Index("ix_cerberus_proposal_status", "status"),
        CheckConstraint(
            "status IN ('pending','confirmed','rejected','expired','executed','failed')",
            name="ck_cerberus_proposal_status",
        ),
    )


class CerberusTradeConfirmation(Base):
    """Confirmation tokens for trade proposals."""
    __tablename__ = "cerberus_trade_confirmations"

    id = Column(String(36), primary_key=True, default=_uuid)
    proposal_id = Column(String(36), ForeignKey("cerberus_trade_proposals.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    confirmation_token_hash = Column(String(256), nullable=False)
    confirmed_at = Column(DateTime, nullable=True)
    executed_at = Column(DateTime, nullable=True)
    status = Column(String(32), nullable=False, default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)

    proposal = relationship("CerberusTradeProposal", back_populates="confirmations")

    __table_args__ = (
        Index("ix_cerberus_confirm_proposal", "proposal_id"),
        Index("ix_cerberus_confirm_user", "user_id"),
    )


class CerberusAIToolCall(Base):
    """Tool call logs — audit every tool invocation."""
    __tablename__ = "cerberus_ai_tool_calls"

    id = Column(String(36), primary_key=True, default=_uuid)
    thread_id = Column(String(36), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    tool_name = Column(String(128), nullable=False)
    tool_version = Column(String(32), nullable=True)
    input_json = Column(JSON, default=dict)
    output_json = Column(JSON, default=dict)
    status = Column(String(32), nullable=False, default="pending")
    latency_ms = Column(Integer, nullable=True)
    error_text = Column(Text, nullable=True)
    provider_request_id = Column(String(128), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_cerberus_toolcall_thread", "thread_id"),
        Index("ix_cerberus_toolcall_user", "user_id"),
        Index("ix_cerberus_toolcall_name", "tool_name"),
    )


class CerberusAuditLog(Base):
    """Audit trail — tracks all significant user/system actions."""
    __tablename__ = "cerberus_audit_log"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action_type = Column(String(64), nullable=False)
    resource_type = Column(String(64), nullable=True)
    resource_id = Column(String(36), nullable=True)
    payload_json = Column(JSON, default=dict)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(512), nullable=True)
    trace_id = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_cerberus_audit_user", "user_id"),
        Index("ix_cerberus_audit_action", "action_type"),
        Index("ix_cerberus_audit_resource", "resource_type", "resource_id"),
        Index("ix_cerberus_audit_trace", "trace_id"),
    )


# ── AI Reasoning Layer Models ───────────────────────────────────────────────

class MarketEvent(Base):
    """Context Monitor output — real-time market intelligence events."""
    __tablename__ = "market_events"

    id = Column(String(36), primary_key=True, default=_uuid)
    event_type = Column(String(32), nullable=False)
    impact = Column(String(16), nullable=False)
    symbols = Column(JSON, default=list)
    sectors = Column(JSON, default=list)
    headline = Column(String(512), nullable=False)
    raw_data = Column(JSON, default=dict)
    source = Column(String(64), nullable=False)
    source_id = Column(String(128), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    detected_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_market_event_type", "event_type"),
        Index("ix_market_event_source_id", "source_id"),
        Index("ix_market_event_detected", "detected_at"),
        Index("ix_market_event_user", "user_id"),
    )


class UniverseCandidate(Base):
    """Universe Scanner output — ranked symbol candidates per bot."""
    __tablename__ = "universe_candidates"

    id = Column(String(36), primary_key=True, default=_uuid)
    bot_id = Column(String(36), ForeignKey("cerberus_bots.id"), nullable=False)
    symbol = Column(String(16), nullable=False)
    score = Column(Float, nullable=False)
    reason = Column(String(512), nullable=True)
    scanned_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_universe_cand_bot", "bot_id"),
        Index("ix_universe_cand_bot_scanned", "bot_id", "scanned_at"),
    )


class TradeDecision(Base):
    """Reasoning Engine output — persisted for UI decision timeline."""
    __tablename__ = "trade_decisions"

    id = Column(String(36), primary_key=True, default=_uuid)
    bot_id = Column(String(36), ForeignKey("cerberus_bots.id"), nullable=False)
    symbol = Column(String(16), nullable=False)
    strategy_signal = Column(String(16), nullable=False)
    context_risk_level = Column(String(16), nullable=False)
    ai_confidence = Column(Float, nullable=False)
    decision = Column(String(32), nullable=False)
    reasoning = Column(Text, nullable=True)
    size_adjustment = Column(Float, default=1.0)
    delay_seconds = Column(Integer, default=0)
    events_considered = Column(JSON, default=list)
    model_used = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_trade_decision_bot", "bot_id"),
        Index("ix_trade_decision_bot_created", "bot_id", "created_at"),
    )


class BotTradeJournal(Base):
    """Enriched trade records with full AI context for bot learning."""
    __tablename__ = "bot_trade_journal"

    id = Column(String(36), primary_key=True, default=_uuid)
    bot_id = Column(String(36), ForeignKey("cerberus_bots.id"), nullable=False)
    trade_id = Column(String(36), nullable=False)
    symbol = Column(String(16), nullable=False)
    side = Column(String(16), nullable=False)
    entry_price = Column(Float, nullable=True)
    exit_price = Column(Float, nullable=True)
    entry_at = Column(DateTime, nullable=True)
    exit_at = Column(DateTime, nullable=True)
    hold_duration_seconds = Column(Integer, nullable=True)
    pnl = Column(Float, nullable=True)
    pnl_pct = Column(Float, nullable=True)
    market_events = Column(JSON, default=list)
    vix_at_entry = Column(Float, nullable=True)
    sector_momentum_at_entry = Column(Float, nullable=True)
    ai_confidence_at_entry = Column(Float, nullable=True)
    ai_decision = Column(String(32), nullable=True)
    ai_reasoning = Column(Text, nullable=True)
    regime_at_entry = Column(String(32), nullable=True)
    outcome_tag = Column(String(64), nullable=True)
    lesson_learned = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_bot_journal_bot", "bot_id"),
        Index("ix_bot_journal_bot_created", "bot_id", "created_at"),
        Index("ix_bot_journal_trade", "trade_id"),
    )


class BotRegimeStats(Base):
    """Per-regime performance tracking for each bot."""
    __tablename__ = "bot_regime_stats"

    id = Column(String(36), primary_key=True, default=_uuid)
    bot_id = Column(String(36), ForeignKey("cerberus_bots.id"), nullable=False)
    regime = Column(String(32), nullable=False)
    total_trades = Column(Integer, default=0)
    win_rate = Column(Float, default=0.0)
    avg_pnl = Column(Float, default=0.0)
    avg_confidence = Column(Float, default=0.0)
    sharpe = Column(Float, default=0.0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_regime_stats_bot", "bot_id"),
        Index("ix_regime_stats_bot_regime", "bot_id", "regime", unique=True),
    )


class BotAdaptation(Base):
    """Learning adjustments log — parameter changes with reasoning."""
    __tablename__ = "bot_adaptations"

    id = Column(String(36), primary_key=True, default=_uuid)
    bot_id = Column(String(36), ForeignKey("cerberus_bots.id"), nullable=False)
    adaptation_type = Column(String(64), nullable=False)
    old_value = Column(JSON, default=dict)
    new_value = Column(JSON, default=dict)
    reasoning = Column(Text, nullable=True)
    confidence = Column(Float, nullable=True)
    auto_applied = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_bot_adaptation_bot", "bot_id"),
        Index("ix_bot_adaptation_bot_created", "bot_id", "created_at"),
    )


# ── Multi-Agent Trade Analysis ───────────────────────────────────────────────

class TradeAnalysis(Base):
    """Persisted multi-agent trade analysis results."""
    __tablename__ = "cerberus_trade_analyses"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    symbol = Column(String(32), nullable=False)
    action = Column(String(16), nullable=False)
    proposed_size = Column(Float, nullable=True)
    current_price = Column(Float, nullable=True)
    technical_report = Column(Text, nullable=True)
    fundamental_report = Column(Text, nullable=True)
    sentiment_report = Column(Text, nullable=True)
    bull_case = Column(Text, nullable=True)
    bear_case = Column(Text, nullable=True)
    risk_assessment = Column(Text, nullable=True)
    recommendation = Column(String(32), nullable=True)
    confidence = Column(Float, nullable=True)
    reasoning = Column(Text, nullable=True)
    node_trace = Column(JSON, default=list)
    errors = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_trade_analysis_user", "user_id"),
        Index("ix_trade_analysis_symbol", "symbol"),
        Index("ix_trade_analysis_created", "created_at"),
    )
