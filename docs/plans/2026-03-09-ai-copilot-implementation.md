# AI Copilot Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add an embedded AI Copilot to the adaptive-trading-ecosystem platform — Bloomberg Terminal-style AI assistant with portfolio analysis, strategy building, bot management, document research, and safe trade proposals.

**Architecture:** New copilot subsystem layered alongside existing FastAPI backend + Next.js frontend. AI Core orchestration service handles model routing (gpt-5.4 primary, gpt-4.1 simple, claude-sonnet-4-6 fallback), typed tool system, memory (Redis + pgvector), document ingestion, and trade proposal safety flow. Frontend floating widget with 5 tabs communicates via REST + WebSocket streaming.

**Tech Stack:** FastAPI, SQLAlchemy 2.x + Alembic, Redis, PostgreSQL + pgvector, OpenAI Responses API, Anthropic native API, Perplexity Search API, Celery, Next.js 14, React 18, TypeScript, Zustand, TailwindCSS, zod, lightweight-charts, Framer Motion

**Existing Stack Notes:**
- Backend: FastAPI at `api/main.py`, SQLAlchemy models at `db/models.py`, async sessions at `db/database.py`
- Frontend: Next.js 14 at `frontend/src/`, React Context hooks at `frontend/src/hooks/`, types at `frontend/src/types/`
- Auth: JWT middleware at `api/middleware/auth.py`, token in cookies + localStorage
- Existing models use Integer PKs — new copilot tables use UUID PKs (separate subsystem, no conflict)
- State management: existing uses React Context; copilot adds Zustand for copilot-specific stores
- Project root: `/Users/andrewpeterson/adaptive-trading-ecosystem/`

---

## Phase 1: Foundation — Database Models, Settings, Shared Types

### Task 1: Add copilot settings to config

**Files:**
- Modify: `config/settings.py`
- Modify: `.env.example`

**Step 1: Add copilot settings to Settings class**

Add these fields to the `Settings` class in `config/settings.py` after the existing LLM settings block (~line 112):

```python
    # --- AI Copilot ---
    openai_primary_model: str = "gpt-5.4"
    openai_low_latency_model: str = "gpt-4.1"
    openai_embedding_model: str = "text-embedding-3-large"
    openai_expert_model: str = "gpt-5.4-pro"
    anthropic_fallback_model: str = "claude-sonnet-4-6"
    perplexity_api_key: str = ""
    perplexity_search_model: str = "sonar"
    perplexity_deep_research_model: str = "sonar-deep-research"
    broker_kms_key_id: str = ""

    # --- S3 Storage ---
    s3_bucket: str = ""
    s3_region: str = "us-east-1"
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_endpoint_url: str = ""  # For MinIO in dev

    # --- Feature Flags ---
    feature_copilot_enabled: bool = True
    feature_research_mode_enabled: bool = True
    feature_bot_mutations_enabled: bool = False
    feature_paper_trade_proposals_enabled: bool = False
    feature_live_trade_proposals_enabled: bool = False
    feature_slow_expert_mode_enabled: bool = False
    feature_experimental_rl_enabled: bool = False

    # --- Celery / Workers ---
    celery_broker_url: str = ""  # defaults to redis_url if empty

    @property
    def effective_celery_broker_url(self) -> str:
        return self.celery_broker_url or self.redis_url
```

**Step 2: Update .env.example**

Append to `.env.example`:

```env
# --- AI Copilot ---
OPENAI_API_KEY=
OPENAI_PRIMARY_MODEL=gpt-5.4
OPENAI_LOW_LATENCY_MODEL=gpt-4.1
OPENAI_EMBEDDING_MODEL=text-embedding-3-large
OPENAI_EXPERT_MODEL=gpt-5.4-pro
ANTHROPIC_FALLBACK_MODEL=claude-sonnet-4-6
PERPLEXITY_API_KEY=
BROKER_KMS_KEY_ID=

# --- S3 (MinIO for dev) ---
S3_BUCKET=trading-copilot
S3_REGION=us-east-1
S3_ACCESS_KEY=
S3_SECRET_KEY=
S3_ENDPOINT_URL=http://localhost:9000

# --- Feature Flags ---
FEATURE_COPILOT_ENABLED=true
FEATURE_RESEARCH_MODE_ENABLED=true
FEATURE_BOT_MUTATIONS_ENABLED=false
FEATURE_PAPER_TRADE_PROPOSALS_ENABLED=false
FEATURE_LIVE_TRADE_PROPOSALS_ENABLED=false
FEATURE_SLOW_EXPERT_MODE_ENABLED=false
FEATURE_EXPERIMENTAL_RL_ENABLED=false
```

**Step 3: Run to verify settings load**

```bash
cd ~/adaptive-trading-ecosystem && python3 -c "from config.settings import get_settings; s = get_settings(); print(s.openai_primary_model, s.feature_copilot_enabled)"
```

Expected: `gpt-5.4 True`

**Step 4: Commit**

```bash
git add config/settings.py .env.example
git commit -m "feat(copilot): add AI copilot settings, feature flags, S3 config"
```

---

### Task 2: Add copilot database models

**Files:**
- Create: `db/copilot_models.py`
- Modify: `db/database.py` (import new models so Alembic sees them)

**Step 1: Create copilot models file**

Create `db/copilot_models.py` with all copilot-specific tables. These use UUID PKs and are separate from existing Integer-PK models.

```python
"""
SQLAlchemy models for the AI Copilot subsystem.
Uses UUID primary keys — separate from legacy Integer-PK trading models.
"""

import enum
import uuid
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
    Numeric,
    String,
    Text,
    JSON,
    CheckConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector

from db.database import Base


def _uuid_col(primary_key=False):
    """UUID column compatible with both SQLite (String) and PostgreSQL (native UUID)."""
    return Column(
        String(36) if True else PG_UUID(as_uuid=True),  # TODO: switch for PG
        primary_key=primary_key,
        default=lambda: str(uuid.uuid4()),
        nullable=not primary_key,
    )


def _enum(cls):
    return Enum(cls, values_callable=lambda obj: [e.value for e in obj])


# ── Enums ────────────────────────────────────────────────────────────────────

class ConversationMode(str, enum.Enum):
    CHAT = "chat"
    STRATEGY = "strategy"
    PORTFOLIO = "portfolio"
    BOT_CONTROL = "bot_control"
    RESEARCH = "research"


class MessageRole(str, enum.Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class ProposalStatus(str, enum.Enum):
    DRAFT = "draft"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    CONFIRMED = "confirmed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    EXECUTED = "executed"
    REJECTED = "rejected"


class DocumentStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    INDEXED = "indexed"
    FAILED = "failed"


class BotStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    STOPPED = "stopped"
    ARCHIVED = "archived"


class AccountMode(str, enum.Enum):
    PAPER = "paper"
    LIVE = "live"


class ToolSideEffect(str, enum.Enum):
    READ = "read"
    WRITE = "write"
    DANGEROUS = "dangerous"


# ── Brokerage Accounts (spec-aligned, extends existing) ─────────────────────

class BrokerageAccount(Base):
    __tablename__ = "copilot_brokerage_accounts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    provider = Column(String(64), nullable=False)
    account_mode = Column(String(16), nullable=False)  # paper / live
    encrypted_access_token = Column(Text, nullable=True)
    encrypted_refresh_token = Column(Text, nullable=True)
    account_mask = Column(String(32), nullable=True)
    metadata_json = Column(JSON, default=dict)
    last_synced_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        CheckConstraint("account_mode IN ('paper', 'live')", name="ck_brokerage_account_mode"),
        Index("ix_copilot_brok_user", "user_id"),
    )


# ── Portfolio & Positions (copilot-specific snapshots) ───────────────────────

class CopilotPortfolioSnapshot(Base):
    __tablename__ = "copilot_portfolio_snapshots"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    brokerage_account_id = Column(String(36), ForeignKey("copilot_brokerage_accounts.id"), nullable=True)
    snapshot_ts = Column(DateTime, default=datetime.utcnow)
    cash = Column(Numeric, nullable=True)
    equity = Column(Numeric, nullable=True)
    buying_power = Column(Numeric, nullable=True)
    margin_used = Column(Numeric, nullable=True)
    day_pnl = Column(Numeric, nullable=True)
    total_pnl = Column(Numeric, nullable=True)
    payload_json = Column(JSON, default=dict)


class CopilotPosition(Base):
    __tablename__ = "copilot_positions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    brokerage_account_id = Column(String(36), ForeignKey("copilot_brokerage_accounts.id"), nullable=True)
    symbol = Column(String(32), nullable=False)
    asset_type = Column(String(32), nullable=True)
    quantity = Column(Numeric, nullable=False)
    avg_price = Column(Numeric, nullable=True)
    mark_price = Column(Numeric, nullable=True)
    market_value = Column(Numeric, nullable=True)
    unrealized_pnl = Column(Numeric, nullable=True)
    realized_pnl = Column(Numeric, nullable=True)
    greeks_json = Column(JSON, default=dict)
    metadata_json = Column(JSON, default=dict)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_copilot_pos_user_symbol", "user_id", "symbol"),
    )


# ── Orders & Trades (copilot-tracked) ───────────────────────────────────────

class CopilotOrder(Base):
    __tablename__ = "copilot_orders"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    brokerage_account_id = Column(String(36), ForeignKey("copilot_brokerage_accounts.id"), nullable=True)
    broker_order_id = Column(String(128), nullable=True)
    symbol = Column(String(32), nullable=False)
    asset_type = Column(String(32), nullable=True)
    side = Column(String(16), nullable=False)
    order_type = Column(String(32), nullable=False)
    tif = Column(String(16), nullable=True)
    quantity = Column(Numeric, nullable=False)
    limit_price = Column(Numeric, nullable=True)
    stop_price = Column(Numeric, nullable=True)
    status = Column(String(32), nullable=False, default="pending")
    payload_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_copilot_orders_user_created", "user_id", "created_at"),
    )


class CopilotTrade(Base):
    __tablename__ = "copilot_trades"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    brokerage_account_id = Column(String(36), ForeignKey("copilot_brokerage_accounts.id"), nullable=True)
    symbol = Column(String(32), nullable=False)
    asset_type = Column(String(32), nullable=True)
    side = Column(String(16), nullable=False)
    entry_ts = Column(DateTime, nullable=True)
    exit_ts = Column(DateTime, nullable=True)
    entry_price = Column(Numeric, nullable=True)
    exit_price = Column(Numeric, nullable=True)
    quantity = Column(Numeric, nullable=False)
    gross_pnl = Column(Numeric, nullable=True)
    net_pnl = Column(Numeric, nullable=True)
    return_pct = Column(Numeric, nullable=True)
    strategy_tag = Column(String(128), nullable=True)
    bot_id = Column(String(36), nullable=True)
    notes = Column(Text, nullable=True)
    payload_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_copilot_trades_user_symbol_entry", "user_id", "symbol", "entry_ts"),
    )


# ── Bots & Versions ─────────────────────────────────────────────────────────

class CopilotBot(Base):
    __tablename__ = "copilot_bots"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(255), nullable=False)
    status = Column(String(32), default="draft")
    current_version_id = Column(String(36), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    versions = relationship("CopilotBotVersion", back_populates="bot")

    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'active', 'paused', 'stopped', 'archived')",
            name="ck_copilot_bot_status"
        ),
    )


class CopilotBotVersion(Base):
    __tablename__ = "copilot_bot_versions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    bot_id = Column(String(36), ForeignKey("copilot_bots.id"), nullable=False)
    version_number = Column(Integer, nullable=False)
    config_json = Column(JSON, nullable=False)
    diff_summary = Column(Text, nullable=True)
    created_by = Column(String(32), default="user")  # user / ai / system
    backtest_required = Column(Boolean, default=True)
    backtest_id = Column(String(36), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    bot = relationship("CopilotBot", back_populates="versions")


# ── Backtests ────────────────────────────────────────────────────────────────

class CopilotBacktest(Base):
    __tablename__ = "copilot_backtests"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    bot_id = Column(String(36), nullable=True)
    bot_version_id = Column(String(36), nullable=True)
    strategy_name = Column(String(255), nullable=True)
    params_json = Column(JSON, default=dict)
    metrics_json = Column(JSON, default=dict)
    equity_curve_json = Column(JSON, default=dict)
    trades_json = Column(JSON, default=dict)
    leakage_checks_json = Column(JSON, default=dict)
    status = Column(String(32), default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)


# ── Conversations & Messages ─────────────────────────────────────────────────

class ConversationThread(Base):
    __tablename__ = "copilot_conversation_threads"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(512), nullable=True)
    mode = Column(String(32), default="chat")
    latest_page = Column(String(128), nullable=True)
    latest_symbol = Column(String(32), nullable=True)
    summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    messages = relationship("ConversationMessage", back_populates="thread", order_by="ConversationMessage.created_at")

    __table_args__ = (
        Index("ix_copilot_thread_user", "user_id"),
    )


class ConversationMessage(Base):
    __tablename__ = "copilot_conversation_messages"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    thread_id = Column(String(36), ForeignKey("copilot_conversation_threads.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role = Column(String(16), nullable=False)  # system / user / assistant / tool
    content_md = Column(Text, nullable=True)
    structured_json = Column(JSON, nullable=True)
    model_name = Column(String(64), nullable=True)
    provider_name = Column(String(32), nullable=True)
    citations_json = Column(JSON, nullable=True)
    tool_calls_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    thread = relationship("ConversationThread", back_populates="messages")

    __table_args__ = (
        Index("ix_copilot_msg_thread_created", "thread_id", "created_at"),
    )


# ── Memory ───────────────────────────────────────────────────────────────────

class MemoryItem(Base):
    __tablename__ = "copilot_memory_items"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    kind = Column(String(64), nullable=False)  # thread_summary, strategy_note, trade_journal, etc.
    source_table = Column(String(128), nullable=True)
    source_id = Column(String(36), nullable=True)
    content = Column(Text, nullable=False)
    metadata_json = Column(JSON, default=dict)
    # embedding: Vector column — only works with pgvector on PostgreSQL
    # For SQLite dev, this column is nullable Text storing JSON array
    embedding_json = Column(Text, nullable=True)  # SQLite fallback: JSON array of floats
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_copilot_memory_user_kind", "user_id", "kind"),
    )


# ── Documents ────────────────────────────────────────────────────────────────

class DocumentFile(Base):
    __tablename__ = "copilot_document_files"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    original_filename = Column(String(512), nullable=False)
    mime_type = Column(String(128), nullable=True)
    storage_key = Column(String(1024), nullable=True)
    doc_type = Column(String(64), nullable=True)
    status = Column(String(32), default="uploaded")
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    indexed_at = Column(DateTime, nullable=True)

    chunks = relationship("DocumentChunk", back_populates="document")

    __table_args__ = (
        CheckConstraint(
            "status IN ('uploaded', 'processing', 'indexed', 'failed')",
            name="ck_copilot_doc_status"
        ),
        Index("ix_copilot_doc_user", "user_id"),
    )


class DocumentChunk(Base):
    __tablename__ = "copilot_document_chunks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String(36), ForeignKey("copilot_document_files.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    page_number = Column(Integer, nullable=True)
    heading = Column(String(512), nullable=True)
    content = Column(Text, nullable=False)
    metadata_json = Column(JSON, default=dict)
    embedding_json = Column(Text, nullable=True)  # SQLite fallback
    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("DocumentFile", back_populates="chunks")

    __table_args__ = (
        Index("ix_copilot_chunk_doc", "document_id"),
        Index("ix_copilot_chunk_user", "user_id"),
    )


# ── UI Context ───────────────────────────────────────────────────────────────

class UIContextEvent(Base):
    __tablename__ = "copilot_ui_context_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    thread_id = Column(String(36), nullable=True)
    current_page = Column(String(128), nullable=True)
    route = Column(String(256), nullable=True)
    visible_components = Column(JSON, default=list)
    focused_component = Column(String(128), nullable=True)
    selected_symbol = Column(String(32), nullable=True)
    selected_account_id = Column(String(36), nullable=True)
    selected_bot_id = Column(String(36), nullable=True)
    component_state = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)


# ── Trade Proposals & Confirmations ──────────────────────────────────────────

class TradeProposal(Base):
    __tablename__ = "copilot_trade_proposals"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    thread_id = Column(String(36), ForeignKey("copilot_conversation_threads.id"), nullable=False)
    proposal_json = Column(JSON, nullable=False)
    risk_json = Column(JSON, default=dict)
    explanation_md = Column(Text, nullable=True)
    status = Column(String(32), default="draft")
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    confirmations = relationship("TradeConfirmation", back_populates="proposal")

    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'awaiting_confirmation', 'confirmed', 'expired', 'cancelled', 'executed', 'rejected')",
            name="ck_copilot_proposal_status"
        ),
        Index("ix_copilot_proposal_user_thread", "user_id", "thread_id"),
    )


class TradeConfirmation(Base):
    __tablename__ = "copilot_trade_confirmations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    proposal_id = Column(String(36), ForeignKey("copilot_trade_proposals.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    confirmation_token_hash = Column(String(128), nullable=True)
    confirmed_at = Column(DateTime, nullable=True)
    executed_at = Column(DateTime, nullable=True)
    status = Column(String(32), default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)

    proposal = relationship("TradeProposal", back_populates="confirmations")


# ── Tool Calls & Audit ───────────────────────────────────────────────────────

class AIToolCall(Base):
    __tablename__ = "copilot_ai_tool_calls"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    thread_id = Column(String(36), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    tool_name = Column(String(128), nullable=False)
    tool_version = Column(String(32), nullable=True)
    input_json = Column(JSON, default=dict)
    output_json = Column(JSON, default=dict)
    status = Column(String(32), default="pending")
    latency_ms = Column(Integer, nullable=True)
    error_text = Column(Text, nullable=True)
    provider_request_id = Column(String(256), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_copilot_tool_call_thread", "thread_id"),
        Index("ix_copilot_tool_call_user", "user_id"),
    )


class AuditLog(Base):
    __tablename__ = "copilot_audit_log"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action_type = Column(String(128), nullable=False)
    resource_type = Column(String(128), nullable=True)
    resource_id = Column(String(36), nullable=True)
    payload_json = Column(JSON, default=dict)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(512), nullable=True)
    trace_id = Column(String(128), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_copilot_audit_user_action", "user_id", "action_type"),
        Index("ix_copilot_audit_created", "created_at"),
    )
```

**Step 2: Import copilot models in database.py**

Add to `db/database.py` after `init_db` function so Alembic discovers the new tables:

```python
# Import copilot models so Base.metadata includes them
import db.copilot_models  # noqa: F401
```

**Step 3: Verify models load**

```bash
cd ~/adaptive-trading-ecosystem && python3 -c "
from db.database import Base
import db.copilot_models
tables = [t for t in Base.metadata.tables if t.startswith('copilot_')]
print(f'{len(tables)} copilot tables:', sorted(tables))
"
```

Expected: `15 copilot tables: ['copilot_ai_tool_calls', 'copilot_audit_log', ...]`

**Step 4: Commit**

```bash
git add db/copilot_models.py db/database.py
git commit -m "feat(copilot): add 15 copilot database models with UUID PKs"
```

---

### Task 3: Create shared TypeScript types

**Files:**
- Create: `frontend/src/types/copilot.ts`
- Create: `frontend/src/types/ui-commands.ts`

**Step 1: Create copilot types**

Create `frontend/src/types/copilot.ts`:

```typescript
// ── Copilot API Types ───────────────────────────────────────────────────────

export type ConversationMode = "chat" | "strategy" | "portfolio" | "bot_control" | "research";
export type MessageRole = "system" | "user" | "assistant" | "tool";

export interface PageContext {
  currentPage: string;
  route: string;
  visibleComponents: string[];
  focusedComponent: string | null;
  selectedSymbol: string | null;
  selectedAccountId: string | null;
  selectedBotId: string | null;
  componentState: Record<string, unknown>;
}

export interface ChatRequest {
  threadId?: string;
  mode: ConversationMode;
  message: string;
  pageContext: PageContext;
  attachments?: string[];
  selectedAccountId?: string;
  allowSlowExpertMode?: boolean;
}

export interface ChatResponse {
  threadId: string;
  turnId: string;
  streamChannel: string;
}

// ── Stream Events ───────────────────────────────────────────────────────────

export type StreamEventType =
  | "assistant.delta"
  | "assistant.message"
  | "tool.start"
  | "tool.result"
  | "chart.payload"
  | "ui.command"
  | "trade.proposal"
  | "warning"
  | "error"
  | "done";

export interface StreamEvent {
  type: StreamEventType;
  data: unknown;
}

export interface AssistantMessage {
  turnId: string;
  markdown: string;
  citations: Citation[];
  structuredTradeSignals: TradeSignal[];
  charts: ChartSpec[];
  uiCommands: UICommand[];
  warnings: string[];
}

// ── Trade Signals ───────────────────────────────────────────────────────────

export type StrategyType = "covered_call" | "long_call" | "iron_condor" | "stock" | "other";
export type TradeAction = "buy" | "sell" | "hold" | "review";

export interface TradeSignal {
  symbol: string;
  strategyType: StrategyType;
  action: TradeAction;
  confidence: number;
  thesis: string[];
  risks: string[];
  entry: { type: "market" | "limit"; price: number };
  exitPlan: { takeProfit: number; stopLoss: number; timeHorizon: string };
  requiresBacktest: boolean;
  requiresUserConfirmation: boolean;
}

// ── Trade Proposals ─────────────────────────────────────────────────────────

export type ProposalStatus =
  | "draft"
  | "awaiting_confirmation"
  | "confirmed"
  | "expired"
  | "cancelled"
  | "executed"
  | "rejected";

export interface TradeProposal {
  id: string;
  symbol: string;
  assetType: "option" | "stock";
  side: "buy" | "sell";
  quantity: number;
  orderType: "market" | "limit" | "stop";
  limitPrice: number | null;
  timeInForce: "day" | "gtc";
  strategyType: StrategyType;
  thesis: string[];
  risks: string[];
  requiredChecks: string[];
  paperOrLive: "paper" | "live";
  status: ProposalStatus;
  riskSummary: Record<string, unknown>;
  explanationMd: string;
  expiresAt: string | null;
}

// ── Charts ──────────────────────────────────────────────────────────────────

export type ChartType = "line" | "candlestick" | "bar" | "equity_curve" | "allocation";

export interface ChartSpec {
  chartType: ChartType;
  title: string;
  series: ChartSeries[];
  xAxis: Record<string, unknown>;
  yAxis: Record<string, unknown>;
}

export interface ChartSeries {
  name: string;
  data: Array<{ x: string | number; y: number }>;
  color?: string;
}

// ── Citations ───────────────────────────────────────────────────────────────

export interface Citation {
  source: "internal" | "external";
  title: string;
  url?: string;
  documentId?: string;
  chunkIds?: string[];
  pageNumber?: number;
  snippet?: string;
  date?: string;
}

// ── Tool Calls ──────────────────────────────────────────────────────────────

export type ToolCategory = "portfolio" | "trading" | "market" | "risk" | "research" | "analytics" | "ui";
export type ToolStatus = "pending" | "running" | "completed" | "failed";

export interface ToolCallEvent {
  toolName: string;
  category: ToolCategory;
  status: ToolStatus;
  input?: Record<string, unknown>;
  output?: Record<string, unknown>;
  latencyMs?: number;
  error?: string;
}

// ── Conversation ────────────────────────────────────────────────────────────

export interface ConversationThread {
  id: string;
  title: string | null;
  mode: ConversationMode;
  latestPage: string | null;
  latestSymbol: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface ConversationMessageItem {
  id: string;
  role: MessageRole;
  contentMd: string | null;
  structuredJson: AssistantMessage | null;
  modelName: string | null;
  citations: Citation[];
  toolCalls: ToolCallEvent[];
  createdAt: string;
}

// ── Documents ───────────────────────────────────────────────────────────────

export type DocumentStatus = "uploaded" | "processing" | "indexed" | "failed";

export interface DocumentFile {
  id: string;
  originalFilename: string;
  mimeType: string | null;
  status: DocumentStatus;
  createdAt: string;
  indexedAt: string | null;
}

// ── Bots ────────────────────────────────────────────────────────────────────

export type BotStatus = "draft" | "active" | "paused" | "stopped" | "archived";

export interface Bot {
  id: string;
  name: string;
  status: BotStatus;
  currentVersionId: string | null;
  createdAt: string;
}

export interface BotVersion {
  id: string;
  botId: string;
  versionNumber: number;
  configJson: Record<string, unknown>;
  diffSummary: string | null;
  createdBy: "user" | "ai" | "system";
  backtestRequired: boolean;
  backtestId: string | null;
}
```

**Step 2: Create UI command types**

Create `frontend/src/types/ui-commands.ts`:

```typescript
// ── UI Command System ───────────────────────────────────────────────────────
// Allowlisted actions and component IDs only. No arbitrary JS/CSS.

export type UICommandAction =
  | "open_panel"
  | "switch_tab"
  | "highlight_component"
  | "populate_strategy_builder"
  | "populate_order_ticket"
  | "navigate"
  | "show_chart"
  | "show_toast"
  | "focus_symbol"
  | "select_bot"
  | "open_confirmation_modal";

export type AllowlistedComponentId =
  | "portfolio_chart"
  | "positions_table"
  | "options_chain"
  | "risk_metrics"
  | "order_ticket"
  | "strategy_builder"
  | "bot_list"
  | "bot_performance_chart"
  | "trade_history_table"
  | "research_sources_panel";

export interface UICommand {
  action: UICommandAction;
  panel?: string;
  tab?: string;
  componentId?: AllowlistedComponentId;
  durationMs?: number;
  strategy?: Record<string, unknown>;
  orderTicket?: Record<string, unknown>;
  route?: string;
  chartSpec?: Record<string, unknown>;
  message?: string;
  toastType?: "info" | "success" | "warning" | "error";
  symbol?: string;
  botId?: string;
  proposalId?: string;
}

export interface UICommandEnvelope {
  commands: UICommand[];
}

// Validation sets
export const ALLOWED_ACTIONS = new Set<UICommandAction>([
  "open_panel", "switch_tab", "highlight_component", "populate_strategy_builder",
  "populate_order_ticket", "navigate", "show_chart", "show_toast",
  "focus_symbol", "select_bot", "open_confirmation_modal",
]);

export const ALLOWED_COMPONENT_IDS = new Set<AllowlistedComponentId>([
  "portfolio_chart", "positions_table", "options_chain", "risk_metrics",
  "order_ticket", "strategy_builder", "bot_list", "bot_performance_chart",
  "trade_history_table", "research_sources_panel",
]);

export function validateUICommand(cmd: UICommand): boolean {
  if (!ALLOWED_ACTIONS.has(cmd.action)) return false;
  if (cmd.componentId && !ALLOWED_COMPONENT_IDS.has(cmd.componentId)) return false;
  if (cmd.action === "navigate" && cmd.route && !cmd.route.startsWith("/")) return false;
  return true;
}
```

**Step 3: Commit**

```bash
git add frontend/src/types/copilot.ts frontend/src/types/ui-commands.ts
git commit -m "feat(copilot): add shared TypeScript types for copilot API and UI commands"
```

---

## Phase 2: AI Core Services

### Task 4: Create provider adapters (OpenAI, Anthropic, Perplexity)

**Files:**
- Create: `services/__init__.py`
- Create: `services/ai_core/__init__.py`
- Create: `services/ai_core/providers/__init__.py`
- Create: `services/ai_core/providers/base.py`
- Create: `services/ai_core/providers/openai_provider.py`
- Create: `services/ai_core/providers/anthropic_provider.py`
- Create: `services/ai_core/providers/perplexity_provider.py`

Implement provider adapters with streaming support:
- OpenAI: Use Responses API, `store: false` for sensitive data, streaming, tool calling, structured outputs
- Anthropic: Native Claude API, structured output / tool / citations path
- Perplexity: Search API for real-time retrieval, Deep Research for explicit research jobs

Each provider must:
- Accept messages + tools + structured output schema
- Return async generator for streaming
- Log provider request IDs
- Handle timeouts and retries
- Expose `complete()` and `stream()` methods

---

### Task 5: Create model router

**Files:**
- Create: `services/ai_core/model_router.py`

Implement deterministic routing:
- `gpt-4.1` for simple help, UI explanations, low-complexity answers
- `gpt-5.4` for portfolio analysis, strategy gen, multi-tool reasoning, structured outputs
- `claude-sonnet-4-6` for fallback, research mode, long-context synthesis
- `sonar-deep-research` for explicit deep research only
- `gpt-5.4-pro` for optional slow expert mode (disabled by default)

Router takes conversation mode, message complexity, tool requirements, and feature flags as input. Returns provider + model name. Persists which provider/model handled each turn.

---

### Task 6: Create tool registry and executor

**Files:**
- Create: `services/ai_core/tools/__init__.py`
- Create: `services/ai_core/tools/registry.py`
- Create: `services/ai_core/tools/executor.py`
- Create: `services/ai_core/tools/base.py`

Implement typed tool registry:
- `ToolDefinition` dataclass with name, version, category, side_effect, requires_confirmation, timeout_ms, cache_ttl_s, input/output schemas, permissions
- `ToolRegistry` singleton with `register()`, `get()`, `list_for_model()` methods
- `ToolExecutor` with validation, execution, caching, logging, timeout handling
- All tool inputs validated with Pydantic
- All tool outputs as structured JSON
- Read-only tools may be cached in Redis

---

### Task 7: Implement portfolio, risk, market, trading, analytics, and research tools

**Files:**
- Create: `services/ai_core/tools/portfolio_tools.py`
- Create: `services/ai_core/tools/risk_tools.py`
- Create: `services/ai_core/tools/market_tools.py`
- Create: `services/ai_core/tools/trading_tools.py`
- Create: `services/ai_core/tools/analytics_tools.py`
- Create: `services/ai_core/tools/research_tools.py`

Implement all tools from spec section 12:
- Portfolio: getPortfolio, getPositions, getOrders, getTradeHistory
- Risk: calculateVaR, calculateDrawdown, portfolioExposure, concentrationRisk, optionsGreekExposure
- Market: getPrice, getHistoricalPrices, getOptionsChain, getIndicators, getEarningsCalendar, getMacroCalendar
- Trading: createBot, modifyBot, stopBot, pauseBot, resumeBot, backtestStrategy, createTradeProposal
- Analytics: getBestTrade, getWorstTrades, getTotalTradingVolume, getStrategyPerformance, getSymbolPerformance, getHoldTimeStats, getBotPerformance
- Research: searchDocuments, getDocumentExcerpt, getMarketNews, getMacroEvents, getEarningsContext, runResearchSession

Each tool wraps existing services (risk/manager.py, engine/backtester.py, data/market_data.py, etc.) or creates new database queries. No broker credentials leave adapters. Models never see raw secrets.

---

### Task 8: Create context assembler and prompt builder

**Files:**
- Create: `services/ai_core/context_assembler.py`
- Create: `services/ai_core/prompt_builder.py`

Context assembler builds the full context object from:
- System context (feature flags, model capabilities)
- User context (user profile, permissions)
- Page context (from frontend UI context events)
- Live trading context (portfolio snapshot, positions, risk from Redis)
- Conversation context (recent messages, thread summary)
- Semantic memory context (relevant memory items from pgvector)
- Document context (relevant document chunks if research mode)
- Safety context (active risk limits, circuit breakers)

Prompt builder constructs the final prompt from assembled context:
- Primary system prompt (from spec section 20)
- Research mode addendum when applicable
- Tool definitions
- Relevant context blocks
- User message

---

### Task 9: Create safety guard

**Files:**
- Create: `services/ai_core/safety_guard.py`

Implement safety checks:
- Block direct trade execution from chat turns
- Validate all mutating actions have RBAC checks
- Redact secrets and PII before external model calls
- Validate model outputs don't contain arbitrary HTML/JS
- Check feature flags before allowing bot mutations, trade proposals, etc.
- Rate limiting per user
- Validate trade proposals pass risk checks before surfacing

---

### Task 10: Create chat controller and response streamer

**Files:**
- Create: `services/ai_core/chat_controller.py`
- Create: `services/ai_core/response_streamer.py`
- Create: `services/ai_core/citation_assembler.py`
- Create: `services/ai_core/ui_command_formatter.py`

Chat controller orchestrates:
1. Receive chat request
2. Assemble context
3. Route to model
4. Build prompt
5. Safety guard check
6. Execute model call (streaming)
7. Process tool calls
8. Assemble citations
9. Format UI commands
10. Stream response to WebSocket
11. Persist messages + tool calls

Response streamer handles WebSocket event emission:
- assistant.delta, assistant.message, tool.start, tool.result, chart.payload, ui.command, trade.proposal, warning, error, done

Citation assembler separates internal document citations from external web citations.

UI command formatter validates commands against allowlist and formats for frontend consumption.

---

## Phase 3: Memory & Documents

### Task 11: Create memory service

**Files:**
- Create: `services/ai_core/memory/__init__.py`
- Create: `services/ai_core/memory/memory_service.py`
- Create: `services/ai_core/memory/retrieval.py`
- Create: `services/ai_core/memory/summarizer.py`
- Create: `services/ai_core/memory/embeddings.py`
- Create: `services/ai_core/memory/save_policy.py`

Memory layers:
- Short-term: PostgreSQL canonical + Redis hot cache (raw messages, tool calls, thread summaries)
- Operational: Redis (portfolio snapshot, positions, risk, active bots, UI context, recent market context)
- Semantic: pgvector (document chunks, thread summaries, strategy notes, research notes)

Implement:
- `MemoryService.store()` / `.retrieve()` / `.search_semantic()`
- `summarize_thread()` — every 20 messages or token threshold
- `EmbeddingService.embed()` using OpenAI text-embedding-3-large
- `SavePolicy.should_save()` — determines if assistant-generated content should be persisted

Redis key patterns from spec section 9.

---

### Task 12: Create document ingestion pipeline

**Files:**
- Create: `services/ai_core/documents/__init__.py`
- Create: `services/ai_core/documents/upload.py`
- Create: `services/ai_core/documents/parsers.py`
- Create: `services/ai_core/documents/chunker.py`
- Create: `services/ai_core/documents/ingestion.py`

Flow: Upload to S3 → Parse (PDF/DOCX/CSV/XLSX/TXT/MD) → Chunk (800 tokens, 150 overlap) → Embed → Store in pgvector

Parsers: pypdf for PDF, python-docx for DOCX, pandas+openpyxl for CSV/XLSX, native for TXT/MD

Chunk metadata: user_id, document_id, filename, page_number, heading, detected symbols, detected dates

---

## Phase 4: Trade Proposals & Analytics

### Task 13: Create trade proposal and confirmation service

**Files:**
- Create: `services/ai_core/proposals/__init__.py`
- Create: `services/ai_core/proposals/trade_proposal_service.py`
- Create: `services/ai_core/proposals/confirmation_service.py`

Implement the full confirmation flow from spec section 13:
1. Model creates structured trade proposal
2. Backend stores proposal in DB
3. Frontend shows proposal card + risk summary + confirmation modal
4. User confirms → backend creates short-lived confirmation token
5. Backend reruns risk checks
6. `executeTrade` injected and executed
7. Persist order result, audit event

Rules: live requires confirmation, paper requires by default, risk checks rerun at confirm, expired proposals cannot execute.

---

### Task 14: Create trade analytics service

**Files:**
- Create: `services/ai_core/analytics/__init__.py`
- Create: `services/ai_core/analytics/trade_analytics.py`

SQL-backed deterministic analytics:
- `get_best_trade()`, `get_worst_trades()`, `get_total_volume()`
- `get_strategy_performance()`, `get_symbol_performance()`
- `get_hold_time_stats()`, `get_bot_performance()`

Create materialized view SQL for:
- mv_trade_stats_by_symbol
- mv_trade_stats_by_strategy
- mv_trade_stats_by_day
- mv_bot_performance

---

## Phase 5: API Layer

### Task 15: Create copilot API routes

**Files:**
- Create: `api/routes/ai_chat.py`
- Create: `api/routes/ai_tools.py`
- Create: `api/routes/documents.py`
- Modify: `api/main.py` (register new routers)

Endpoints:
- `POST /api/ai/chat` — initiate chat turn
- `WS /api/ai/stream/{thread_id}` — WebSocket streaming
- `GET /api/ai/threads` — list conversation threads
- `GET /api/ai/threads/{thread_id}/messages` — get thread messages
- `POST /api/ai/tools/confirm-trade` — confirm trade proposal
- `POST /api/ai/tools/execute-trade` — execute confirmed trade
- `POST /api/documents/upload` — request presigned upload URL
- `POST /api/documents/{document_id}/finalize` — trigger ingestion
- `GET /api/documents/{document_id}/status` — check ingestion status
- `POST /api/documents/search` — vector search documents

Register in `api/main.py`:
```python
from api.routes import ai_chat, ai_tools, documents as documents_routes
app.include_router(ai_chat.router, prefix="/api/ai", tags=["AI Copilot"])
app.include_router(ai_tools.router, prefix="/api/ai/tools", tags=["AI Tools"])
app.include_router(documents_routes.router, prefix="/api/documents", tags=["Documents"])
```

---

## Phase 6: Frontend Copilot Widget

### Task 16: Install frontend dependencies

**Files:**
- Modify: `frontend/package.json`

Install:
```bash
cd ~/adaptive-trading-ecosystem/frontend
npm install zustand framer-motion zod react-markdown remark-gfm rehype-highlight
```

---

### Task 17: Create copilot stores

**Files:**
- Create: `frontend/src/stores/copilot-store.ts`
- Create: `frontend/src/stores/ui-context-store.ts`

`useCopilotStore` (Zustand):
- threads, activeThread, messages, isOpen, activeTab, isStreaming, toolCalls, proposals
- actions: openCopilot, closeCopilot, setActiveTab, sendMessage, setStreamingState

`useUIContextStore` (Zustand):
- pageContext (current page, route, visible components, focused component, selected symbol/account/bot)
- actions: updatePageContext, updateSelectedSymbol

---

### Task 18: Create copilot API client and WebSocket handler

**Files:**
- Create: `frontend/src/lib/copilot-api.ts`
- Create: `frontend/src/lib/copilot-websocket.ts`
- Create: `frontend/src/lib/ui-command-executor.ts`

API client wraps `apiFetch` for copilot endpoints.
WebSocket handler connects to `/api/ai/stream/{threadId}`, processes stream events, updates Zustand store.
UI command executor validates commands via zod, dispatches to safe UI methods.

---

### Task 19: Create AIWidget and ChatPanel components

**Files:**
- Create: `frontend/src/components/copilot/AIWidget.tsx`
- Create: `frontend/src/components/copilot/ChatPanel.tsx`
- Create: `frontend/src/components/copilot/MessageList.tsx`
- Create: `frontend/src/components/copilot/MessageInput.tsx`

AIWidget: Floating 56x56 bubble, bottom-right, glassmorphism, draggable, expands to 420px slide-out panel. Tabs: Chat, Strategy Builder, Portfolio Analysis, Bot Control, Research.

ChatPanel: Message list + input. Renders markdown, code blocks, charts, citations, tool status, trade signals.

MessageList: Scrollable message container with auto-scroll, grouped by role.

MessageInput: Textarea with send button, attachment support, mode selector.

---

### Task 20: Create specialized panel components

**Files:**
- Create: `frontend/src/components/copilot/StrategyBuilder.tsx`
- Create: `frontend/src/components/copilot/PortfolioAnalysis.tsx`
- Create: `frontend/src/components/copilot/BotControlPanel.tsx`
- Create: `frontend/src/components/copilot/ResearchPanel.tsx`

Each panel is a tab within the copilot widget:
- StrategyBuilder: Visual strategy configuration, AI-assisted generation, backtest trigger
- PortfolioAnalysis: Risk metrics, allocation chart, exposure breakdown
- BotControlPanel: Bot list, status controls, performance charts
- ResearchPanel: Document upload, search, research session results

---

### Task 21: Create trade and chart rendering components

**Files:**
- Create: `frontend/src/components/copilot/TradeSignalCard.tsx`
- Create: `frontend/src/components/copilot/ChartRenderer.tsx`
- Create: `frontend/src/components/copilot/CitationList.tsx`
- Create: `frontend/src/components/copilot/ConfirmationModal.tsx`
- Create: `frontend/src/components/copilot/ToolStatusPill.tsx`

TradeSignalCard: Renders structured trade signals with symbol, action, confidence, thesis, risks, entry/exit.
ChartRenderer: Renders ChartSpec using lightweight-charts (candlestick, line) or Recharts (bar, allocation).
CitationList: Separates internal vs external citations, links to documents/URLs.
ConfirmationModal: Trade proposal review + risk summary + confirm/cancel buttons.
ToolStatusPill: Shows tool execution status (pending → running → completed/failed).

---

### Task 22: Integrate copilot widget into layout

**Files:**
- Modify: `frontend/src/app/layout.tsx`
- Modify: `frontend/src/components/layout/Providers.tsx`

Add `<AIWidget />` to layout (renders on all authenticated pages).
Add UI context provider to Providers composition.
Wire up page context tracking on route changes.

---

## Phase 7: Integration, Workers, Testing

### Task 23: Create Celery worker configuration

**Files:**
- Create: `services/workers/__init__.py`
- Create: `services/workers/celery_app.py`
- Create: `services/workers/tasks.py`

Celery tasks for:
- Document ingestion (parse, chunk, embed, index)
- Backtest execution
- Analytics rollup (materialized view refresh)
- Thread summarization
- Long research jobs

---

### Task 24: Update docker-compose for new services

**Files:**
- Modify: `docker-compose.yml`

Add:
- minio (S3-compatible storage for dev)
- worker-doc (Celery worker for document tasks)
- worker-backtest (Celery worker for backtest tasks)

---

### Task 25: Update requirements.txt

**Files:**
- Modify: `requirements.txt`

Add new dependencies:
```
openai>=1.50.0
anthropic>=0.39.0
pgvector>=0.3.0
celery>=5.3.0
boto3>=1.34.0
pypdf>=4.0.0
python-docx>=1.0.0
openpyxl>=3.1.0
tiktoken>=0.7.0
```

---

### Task 26: Create tests

**Files:**
- Create: `tests/test_copilot_models.py`
- Create: `tests/test_model_router.py`
- Create: `tests/test_tool_registry.py`
- Create: `tests/test_safety_guard.py`
- Create: `tests/test_trade_proposals.py`
- Create: `tests/test_trade_analytics.py`
- Create: `tests/test_ui_commands.py`
- Create: `tests/test_chat_api.py`

Test categories:
- Unit: tool validation, model routing, risk gates, UI command validation
- Integration: chat orchestration, tool execution, proposal flow
- Mock provider tests (mock OpenAI/Anthropic responses)
- WebSocket streaming tests

---

## Phase 8: Documentation & Deployment

### Task 27: Update README and env documentation

**Files:**
- Modify: `README.md`
- Modify: `CLAUDE.md`

Add sections for:
- AI Copilot architecture overview
- Setup instructions for copilot (env vars, S3, pgvector)
- Running workers
- Feature flag descriptions
- API endpoint documentation

---

### Task 28: Create Alembic migration for copilot tables

**Files:**
- Create new Alembic migration

```bash
cd ~/adaptive-trading-ecosystem
alembic revision --autogenerate -m "add copilot tables"
```

Review and commit the generated migration.

---

## Execution Order & Dependencies

```
Task 1 (settings) ──┐
Task 2 (models) ────┼── Task 4 (providers) ─── Task 5 (router) ──┐
Task 3 (TS types) ──┘   Task 6 (tool reg) ──── Task 7 (tools) ───┤
                                                                    ├── Task 10 (chat controller)
                         Task 8 (context) ─────────────────────────┤
                         Task 9 (safety) ──────────────────────────┘
                                                                    │
Task 11 (memory) ──────────────────────────────────────────────────┤
Task 12 (documents) ───────────────────────────────────────────────┤
Task 13 (proposals) ───────────────────────────────────────────────┤
Task 14 (analytics) ───────────────────────────────────────────────┘
                                                                    │
                         Task 15 (API routes) ─────────────────────┘
                                                                    │
Task 16 (npm deps) ────── Task 17 (stores) ─── Task 18 (api/ws) ──┤
                                                                    ├── Task 22 (layout integration)
                          Task 19 (widget/chat) ───────────────────┤
                          Task 20 (panels) ────────────────────────┤
                          Task 21 (cards/charts) ──────────────────┘
                                                                    │
Task 23 (workers) ─────────────────────────────────────────────────┤
Task 24 (docker) ──────────────────────────────────────────────────┤
Task 25 (requirements) ────────────────────────────────────────────┤
Task 26 (tests) ───────────────────────────────────────────────────┤
Task 27 (docs) ────────────────────────────────────────────────────┤
Task 28 (migration) ───────────────────────────────────────────────┘
```

**Parallelizable groups:**
- Group A: Tasks 1, 2, 3 (foundation — all independent)
- Group B: Tasks 4, 5, 6, 7, 8, 9 (AI core — sequential but some parallel)
- Group C: Tasks 11, 12, 13, 14 (memory/documents/proposals — mostly independent)
- Group D: Tasks 16, 17, 18, 19, 20, 21 (frontend — sequential within, parallel with backend)
- Group E: Tasks 23, 24, 25 (infrastructure — independent)
- Group F: Tasks 26, 27, 28 (finalization — after all implementation)
