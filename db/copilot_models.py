"""
SQLAlchemy ORM models for the AI Copilot subsystem.

All tables are prefixed with ``copilot_`` to avoid conflicts with the core
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


class ConversationMode(str, enum.Enum):
    CHAT = "chat"
    ANALYSIS = "analysis"
    TRADE = "trade"
    BACKTEST = "backtest"
    BUILD = "build"


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

class CopilotBrokerageAccount(Base):
    """Provider connections — links a user to a brokerage provider."""
    __tablename__ = "copilot_brokerage_accounts"

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

    portfolio_snapshots = relationship("CopilotPortfolioSnapshot", back_populates="brokerage_account")
    positions = relationship("CopilotPosition", back_populates="brokerage_account")
    orders = relationship("CopilotOrder", back_populates="brokerage_account")
    trades = relationship("CopilotTrade", back_populates="brokerage_account")

    __table_args__ = (
        Index("ix_copilot_brkacct_user", "user_id"),
        Index("ix_copilot_brkacct_provider", "provider"),
    )


class CopilotPortfolioSnapshot(Base):
    """Point-in-time portfolio snapshots."""
    __tablename__ = "copilot_portfolio_snapshots"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    brokerage_account_id = Column(String(36), ForeignKey("copilot_brokerage_accounts.id"), nullable=False)
    snapshot_ts = Column(DateTime, nullable=False, default=datetime.utcnow)
    cash = Column(Float, nullable=True)
    equity = Column(Float, nullable=True)
    buying_power = Column(Float, nullable=True)
    margin_used = Column(Float, nullable=True)
    day_pnl = Column(Float, nullable=True)
    total_pnl = Column(Float, nullable=True)
    payload_json = Column(JSON, default=dict)

    brokerage_account = relationship("CopilotBrokerageAccount", back_populates="portfolio_snapshots")

    __table_args__ = (
        Index("ix_copilot_snap_user", "user_id"),
        Index("ix_copilot_snap_acct_ts", "brokerage_account_id", "snapshot_ts"),
    )


class CopilotPosition(Base):
    """Current positions."""
    __tablename__ = "copilot_positions"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    brokerage_account_id = Column(String(36), ForeignKey("copilot_brokerage_accounts.id"), nullable=False)
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

    brokerage_account = relationship("CopilotBrokerageAccount", back_populates="positions")

    __table_args__ = (
        Index("ix_copilot_pos_user", "user_id"),
        Index("ix_copilot_pos_acct_symbol", "brokerage_account_id", "symbol"),
    )


class CopilotOrder(Base):
    """Order records."""
    __tablename__ = "copilot_orders"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    brokerage_account_id = Column(String(36), ForeignKey("copilot_brokerage_accounts.id"), nullable=False)
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

    brokerage_account = relationship("CopilotBrokerageAccount", back_populates="orders")

    __table_args__ = (
        Index("ix_copilot_ord_user", "user_id"),
        Index("ix_copilot_ord_acct", "brokerage_account_id"),
        Index("ix_copilot_ord_symbol_status", "symbol", "status"),
    )


class CopilotTrade(Base):
    """Trade records — completed trade lifecycle."""
    __tablename__ = "copilot_trades"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    brokerage_account_id = Column(String(36), ForeignKey("copilot_brokerage_accounts.id"), nullable=True)
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

    brokerage_account = relationship("CopilotBrokerageAccount", back_populates="trades")

    __table_args__ = (
        Index("ix_copilot_trd_user", "user_id"),
        Index("ix_copilot_trd_symbol", "symbol"),
        Index("ix_copilot_trd_strategy", "strategy_tag"),
        Index("ix_copilot_trd_bot", "bot_id"),
    )


class CopilotBot(Base):
    """Bot definitions."""
    __tablename__ = "copilot_bots"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(128), nullable=False)
    status = Column(
        _enum(BotStatus),
        nullable=False,
        default=BotStatus.DRAFT,
    )
    current_version_id = Column(String(36), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    versions = relationship("CopilotBotVersion", back_populates="bot", order_by="CopilotBotVersion.version_number")

    __table_args__ = (
        Index("ix_copilot_bot_user", "user_id"),
        CheckConstraint(
            "status IN ('draft','running','paused','stopped','error')",
            name="ck_copilot_bot_status",
        ),
    )


class CopilotBotVersion(Base):
    """Bot version history."""
    __tablename__ = "copilot_bot_versions"

    id = Column(String(36), primary_key=True, default=_uuid)
    bot_id = Column(String(36), ForeignKey("copilot_bots.id"), nullable=False)
    version_number = Column(Integer, nullable=False)
    config_json = Column(JSON, default=dict)
    diff_summary = Column(Text, nullable=True)
    created_by = Column(String(64), nullable=True)
    backtest_required = Column(Boolean, default=False)
    backtest_id = Column(String(36), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    bot = relationship("CopilotBot", back_populates="versions")

    __table_args__ = (
        Index("ix_copilot_botver_bot", "bot_id"),
        Index("ix_copilot_botver_bot_num", "bot_id", "version_number", unique=True),
    )


class CopilotBacktest(Base):
    """Backtest records."""
    __tablename__ = "copilot_backtests"

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
        Index("ix_copilot_bt_user", "user_id"),
        Index("ix_copilot_bt_bot", "bot_id"),
    )


class CopilotConversationThread(Base):
    """Chat threads."""
    __tablename__ = "copilot_conversation_threads"

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
        "CopilotConversationMessage",
        back_populates="thread",
        order_by="CopilotConversationMessage.created_at",
    )

    __table_args__ = (
        Index("ix_copilot_thread_user", "user_id"),
        Index("ix_copilot_thread_updated", "updated_at"),
    )


class CopilotConversationMessage(Base):
    """Chat messages."""
    __tablename__ = "copilot_conversation_messages"

    id = Column(String(36), primary_key=True, default=_uuid)
    thread_id = Column(String(36), ForeignKey("copilot_conversation_threads.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role = Column(_enum(MessageRole), nullable=False)
    content_md = Column(Text, nullable=True)
    structured_json = Column(JSON, default=dict)
    model_name = Column(String(64), nullable=True)
    provider_name = Column(String(64), nullable=True)
    citations_json = Column(JSON, default=dict)
    tool_calls_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

    thread = relationship("CopilotConversationThread", back_populates="messages")

    __table_args__ = (
        Index("ix_copilot_msg_thread", "thread_id"),
        Index("ix_copilot_msg_user", "user_id"),
        Index("ix_copilot_msg_thread_ts", "thread_id", "created_at"),
    )


class CopilotMemoryItem(Base):
    """Semantic memory items."""
    __tablename__ = "copilot_memory_items"

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
        Index("ix_copilot_mem_user", "user_id"),
        Index("ix_copilot_mem_kind", "kind"),
        Index("ix_copilot_mem_source", "source_table", "source_id"),
    )


class CopilotDocumentFile(Base):
    """Uploaded documents."""
    __tablename__ = "copilot_document_files"

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

    chunks = relationship("CopilotDocumentChunk", back_populates="document", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_copilot_docfile_user", "user_id"),
        Index("ix_copilot_docfile_status", "status"),
        CheckConstraint(
            "status IN ('pending','processing','indexed','failed')",
            name="ck_copilot_docfile_status",
        ),
    )


class CopilotDocumentChunk(Base):
    """Document chunks for vector search."""
    __tablename__ = "copilot_document_chunks"

    id = Column(String(36), primary_key=True, default=_uuid)
    document_id = Column(String(36), ForeignKey("copilot_document_files.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    page_number = Column(Integer, nullable=True)
    heading = Column(String(512), nullable=True)
    content = Column(Text, nullable=False)
    metadata_json = Column(JSON, default=dict)
    embedding_json = Column(Text, nullable=True)  # TEXT for SQLite compatibility
    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("CopilotDocumentFile", back_populates="chunks")

    __table_args__ = (
        Index("ix_copilot_chunk_doc", "document_id"),
        Index("ix_copilot_chunk_user", "user_id"),
        Index("ix_copilot_chunk_doc_idx", "document_id", "chunk_index"),
    )


class CopilotUIContextEvent(Base):
    """UI page context events — tracks what the user is looking at."""
    __tablename__ = "copilot_ui_context_events"

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
        Index("ix_copilot_uictx_user", "user_id"),
        Index("ix_copilot_uictx_thread", "thread_id"),
    )


class CopilotTradeProposal(Base):
    """Trade proposals generated by the AI."""
    __tablename__ = "copilot_trade_proposals"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    thread_id = Column(String(36), ForeignKey("copilot_conversation_threads.id"), nullable=True)
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

    confirmations = relationship("CopilotTradeConfirmation", back_populates="proposal")

    __table_args__ = (
        Index("ix_copilot_proposal_user", "user_id"),
        Index("ix_copilot_proposal_thread", "thread_id"),
        Index("ix_copilot_proposal_status", "status"),
        CheckConstraint(
            "status IN ('pending','confirmed','rejected','expired','executed','failed')",
            name="ck_copilot_proposal_status",
        ),
    )


class CopilotTradeConfirmation(Base):
    """Confirmation tokens for trade proposals."""
    __tablename__ = "copilot_trade_confirmations"

    id = Column(String(36), primary_key=True, default=_uuid)
    proposal_id = Column(String(36), ForeignKey("copilot_trade_proposals.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    confirmation_token_hash = Column(String(256), nullable=False)
    confirmed_at = Column(DateTime, nullable=True)
    executed_at = Column(DateTime, nullable=True)
    status = Column(String(32), nullable=False, default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)

    proposal = relationship("CopilotTradeProposal", back_populates="confirmations")

    __table_args__ = (
        Index("ix_copilot_confirm_proposal", "proposal_id"),
        Index("ix_copilot_confirm_user", "user_id"),
    )


class CopilotAIToolCall(Base):
    """Tool call logs — audit every tool invocation."""
    __tablename__ = "copilot_ai_tool_calls"

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
        Index("ix_copilot_toolcall_thread", "thread_id"),
        Index("ix_copilot_toolcall_user", "user_id"),
        Index("ix_copilot_toolcall_name", "tool_name"),
    )


class CopilotAuditLog(Base):
    """Audit trail — tracks all significant user/system actions."""
    __tablename__ = "copilot_audit_log"

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
        Index("ix_copilot_audit_user", "user_id"),
        Index("ix_copilot_audit_action", "action_type"),
        Index("ix_copilot_audit_resource", "resource_type", "resource_id"),
        Index("ix_copilot_audit_trace", "trace_id"),
    )
