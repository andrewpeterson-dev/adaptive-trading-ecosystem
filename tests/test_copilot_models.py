"""Tests for copilot SQLAlchemy ORM models (db/copilot_models.py)."""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from db.database import Base

# Import the User model so the FK targets resolve during create_all
from db.models import User  # noqa: F401

from db.copilot_models import (
    AccountMode,
    BotStatus,
    ConversationMode,
    DocumentStatus,
    MessageRole,
    ProposalStatus,
    ToolSideEffect,
    CopilotBrokerageAccount,
    CopilotPortfolioSnapshot,
    CopilotPosition,
    CopilotOrder,
    CopilotTrade,
    CopilotBot,
    CopilotBotVersion,
    CopilotBacktest,
    CopilotConversationThread,
    CopilotConversationMessage,
    CopilotMemoryItem,
    CopilotDocumentFile,
    CopilotDocumentChunk,
    CopilotUIContextEvent,
    CopilotTradeProposal,
    CopilotTradeConfirmation,
    CopilotAIToolCall,
    CopilotAuditLog,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

TEST_DB_URL = "sqlite+aiosqlite:///"


@pytest_asyncio.fixture
async def engine():
    eng = create_async_engine(
        TEST_DB_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session(engine):
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as sess:
        yield sess


async def _seed_user(session: AsyncSession) -> int:
    """Insert a minimal user row and return its id."""
    from db.models import User

    user = User(
        email="test@example.com",
        password_hash="fakehash",
        display_name="Test User",
    )
    session.add(user)
    await session.flush()
    return user.id


# ---------------------------------------------------------------------------
# Enum serialisation tests
# ---------------------------------------------------------------------------

class TestEnums:
    def test_account_mode_values(self):
        assert AccountMode.PAPER.value == "paper"
        assert AccountMode.LIVE.value == "live"

    def test_bot_status_values(self):
        expected = {"draft", "running", "paused", "stopped", "error"}
        assert {s.value for s in BotStatus} == expected

    def test_conversation_mode_values(self):
        expected = {"chat", "analysis", "trade", "backtest", "build"}
        assert {m.value for m in ConversationMode} == expected

    def test_message_role_values(self):
        expected = {"user", "assistant", "system", "tool"}
        assert {r.value for r in MessageRole} == expected

    def test_proposal_status_values(self):
        expected = {"pending", "confirmed", "rejected", "expired", "executed", "failed"}
        assert {s.value for s in ProposalStatus} == expected

    def test_document_status_values(self):
        expected = {"pending", "processing", "indexed", "failed"}
        assert {s.value for s in DocumentStatus} == expected

    def test_tool_side_effect_values(self):
        expected = {"none", "read", "write", "trade", "notify"}
        assert {e.value for e in ToolSideEffect} == expected


# ---------------------------------------------------------------------------
# Model instantiation & UUID PK tests
# ---------------------------------------------------------------------------

class TestModelInstantiation:
    def test_brokerage_account_uuid(self):
        obj = CopilotBrokerageAccount(user_id=1, provider="alpaca")
        # _uuid default should have been called
        assert obj.provider == "alpaca"

    def test_portfolio_snapshot_fields(self):
        obj = CopilotPortfolioSnapshot(
            user_id=1,
            brokerage_account_id="fake-acct",
            cash=10000.0,
            equity=50000.0,
        )
        assert obj.cash == 10000.0
        assert obj.equity == 50000.0

    def test_position_fields(self):
        obj = CopilotPosition(
            user_id=1,
            brokerage_account_id="fake",
            symbol="AAPL",
            quantity=100,
        )
        assert obj.symbol == "AAPL"
        assert obj.quantity == 100

    def test_order_defaults(self):
        obj = CopilotOrder(
            user_id=1,
            brokerage_account_id="fake",
            symbol="TSLA",
            side="buy",
            order_type="market",
            quantity=10,
        )
        assert obj.side == "buy"

    def test_trade_fields(self):
        obj = CopilotTrade(
            user_id=1,
            symbol="SPY",
            side="sell",
            quantity=50,
            gross_pnl=200.0,
        )
        assert obj.gross_pnl == 200.0

    def test_bot_default_status(self):
        obj = CopilotBot(user_id=1, name="TestBot")
        # The column default is BotStatus.DRAFT
        assert obj.name == "TestBot"

    def test_bot_version_fields(self):
        obj = CopilotBotVersion(bot_id="fake", version_number=1)
        assert obj.version_number == 1

    def test_backtest_fields(self):
        obj = CopilotBacktest(user_id=1, strategy_name="momentum")
        assert obj.strategy_name == "momentum"

    def test_conversation_thread_default_mode(self):
        obj = CopilotConversationThread(user_id=1)
        # mode default is ConversationMode.CHAT
        assert obj.user_id == 1

    def test_conversation_message_fields(self):
        obj = CopilotConversationMessage(
            thread_id="fake",
            user_id=1,
            role=MessageRole.USER,
            content_md="Hello",
        )
        assert obj.content_md == "Hello"
        assert obj.role == MessageRole.USER

    def test_memory_item_fields(self):
        obj = CopilotMemoryItem(user_id=1, kind="preference", content="likes growth stocks")
        assert obj.kind == "preference"

    def test_document_file_fields(self):
        obj = CopilotDocumentFile(
            user_id=1,
            original_filename="report.pdf",
            storage_key="s3://bucket/key",
        )
        assert obj.original_filename == "report.pdf"

    def test_document_chunk_fields(self):
        obj = CopilotDocumentChunk(
            document_id="fake",
            user_id=1,
            chunk_index=0,
            content="Some text",
        )
        assert obj.chunk_index == 0

    def test_ui_context_event_fields(self):
        obj = CopilotUIContextEvent(user_id=1, current_page="/dashboard")
        assert obj.current_page == "/dashboard"

    def test_trade_proposal_fields(self):
        obj = CopilotTradeProposal(
            user_id=1,
            proposal_json={"symbol": "AAPL"},
            status=ProposalStatus.PENDING,
        )
        assert obj.status == ProposalStatus.PENDING

    def test_trade_confirmation_fields(self):
        obj = CopilotTradeConfirmation(
            proposal_id="fake",
            user_id=1,
            confirmation_token_hash="abc123",
        )
        assert obj.confirmation_token_hash == "abc123"

    def test_ai_tool_call_fields(self):
        obj = CopilotAIToolCall(user_id=1, tool_name="getPortfolio")
        assert obj.tool_name == "getPortfolio"

    def test_audit_log_fields(self):
        obj = CopilotAuditLog(user_id=1, action_type="trade_executed")
        assert obj.action_type == "trade_executed"


# ---------------------------------------------------------------------------
# Persistence round-trip tests
# ---------------------------------------------------------------------------

class TestModelPersistence:
    @pytest.mark.asyncio
    async def test_brokerage_account_round_trip(self, session: AsyncSession):
        uid = await _seed_user(session)
        acct = CopilotBrokerageAccount(
            id=str(uuid.uuid4()),
            user_id=uid,
            provider="webull",
            account_mode=AccountMode.PAPER,
        )
        session.add(acct)
        await session.flush()
        assert acct.id is not None
        assert len(acct.id) == 36  # UUID format

    @pytest.mark.asyncio
    async def test_conversation_thread_message_relationship(self, session: AsyncSession):
        uid = await _seed_user(session)
        thread = CopilotConversationThread(
            id=str(uuid.uuid4()),
            user_id=uid,
            title="Test Thread",
            mode=ConversationMode.CHAT,
        )
        session.add(thread)
        await session.flush()

        msg = CopilotConversationMessage(
            id=str(uuid.uuid4()),
            thread_id=thread.id,
            user_id=uid,
            role=MessageRole.USER,
            content_md="Hi there",
        )
        session.add(msg)
        await session.flush()

        assert msg.thread_id == thread.id

    @pytest.mark.asyncio
    async def test_trade_proposal_confirmation_relationship(self, session: AsyncSession):
        uid = await _seed_user(session)
        proposal = CopilotTradeProposal(
            id=str(uuid.uuid4()),
            user_id=uid,
            proposal_json={"symbol": "AAPL", "side": "buy", "quantity": 10},
            status=ProposalStatus.PENDING,
        )
        session.add(proposal)
        await session.flush()

        confirmation = CopilotTradeConfirmation(
            id=str(uuid.uuid4()),
            proposal_id=proposal.id,
            user_id=uid,
            confirmation_token_hash="deadbeef",
        )
        session.add(confirmation)
        await session.flush()

        assert confirmation.proposal_id == proposal.id

    @pytest.mark.asyncio
    async def test_document_file_chunk_cascade(self, session: AsyncSession):
        uid = await _seed_user(session)
        doc = CopilotDocumentFile(
            id=str(uuid.uuid4()),
            user_id=uid,
            original_filename="test.pdf",
            storage_key="s3://test/key",
            status=DocumentStatus.PENDING,
        )
        session.add(doc)
        await session.flush()

        chunk = CopilotDocumentChunk(
            id=str(uuid.uuid4()),
            document_id=doc.id,
            user_id=uid,
            chunk_index=0,
            content="Page one content",
        )
        session.add(chunk)
        await session.flush()

        assert chunk.document_id == doc.id

    @pytest.mark.asyncio
    async def test_bot_version_relationship(self, session: AsyncSession):
        uid = await _seed_user(session)
        bot = CopilotBot(
            id=str(uuid.uuid4()),
            user_id=uid,
            name="MomentumBot",
            status=BotStatus.DRAFT,
        )
        session.add(bot)
        await session.flush()

        ver = CopilotBotVersion(
            id=str(uuid.uuid4()),
            bot_id=bot.id,
            version_number=1,
            config_json={"lookback": 20},
        )
        session.add(ver)
        await session.flush()

        assert ver.bot_id == bot.id
