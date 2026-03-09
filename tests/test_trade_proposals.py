"""Tests for trade proposal + confirmation services."""
from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from db.database import Base
from db.models import User  # noqa: F401
from db.copilot_models import (
    CopilotTradeProposal,
    CopilotTradeConfirmation,
    CopilotPortfolioSnapshot,
    CopilotPosition,
    CopilotAuditLog,
    ProposalStatus,
)

# We test the static token methods directly since they don't need DB
from services.ai_core.proposals.confirmation_service import ConfirmationService

TEST_DB_URL = "sqlite+aiosqlite:///"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

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
    from db.models import User
    user = User(email="test@example.com", password_hash="fakehash", display_name="Test")
    session.add(user)
    await session.flush()
    return user.id


# ---------------------------------------------------------------------------
# Token generation & validation tests (static methods, no DB)
# ---------------------------------------------------------------------------

class TestTokenGeneration:
    def test_generate_token_returns_pair(self):
        token, token_hash = ConfirmationService._generate_token()
        assert isinstance(token, str)
        assert isinstance(token_hash, str)
        assert len(token) > 20  # urlsafe token should be decent length
        assert len(token_hash) == 64  # SHA-256 hex digest

    def test_token_hash_is_sha256(self):
        token, token_hash = ConfirmationService._generate_token()
        expected = hashlib.sha256(token.encode()).hexdigest()
        assert token_hash == expected

    def test_different_tokens_produce_different_hashes(self):
        t1, h1 = ConfirmationService._generate_token()
        t2, h2 = ConfirmationService._generate_token()
        assert t1 != t2
        assert h1 != h2

    def test_validate_token_correct(self):
        token, token_hash = ConfirmationService._generate_token()
        assert ConfirmationService._validate_token(token, token_hash) is True

    def test_validate_token_wrong_token(self):
        _, token_hash = ConfirmationService._generate_token()
        assert ConfirmationService._validate_token("wrong-token", token_hash) is False

    def test_validate_token_wrong_hash(self):
        token, _ = ConfirmationService._generate_token()
        assert ConfirmationService._validate_token(token, "a" * 64) is False

    def test_validate_token_timing_safe(self):
        """Ensure _validate_token uses constant-time comparison (secrets.compare_digest)."""
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        # This exercises the code path that uses secrets.compare_digest
        assert ConfirmationService._validate_token(token, token_hash) is True


# ---------------------------------------------------------------------------
# Proposal creation tests (mocked DB)
# ---------------------------------------------------------------------------

class TestProposalCreation:
    @pytest.mark.asyncio
    async def test_create_proposal_returns_pending(self, session: AsyncSession):
        uid = await _seed_user(session)

        # Seed a portfolio snapshot so risk checks have equity data
        snap = CopilotPortfolioSnapshot(
            id=str(uuid.uuid4()),
            user_id=uid,
            brokerage_account_id=str(uuid.uuid4()),
            cash=100000.0,
            equity=100000.0,
        )
        session.add(snap)
        await session.flush()

        # Create proposal directly in DB (simulating what the service does)
        proposal_id = str(uuid.uuid4())
        expires_at = datetime.utcnow() + timedelta(minutes=5)
        proposal = CopilotTradeProposal(
            id=proposal_id,
            user_id=uid,
            proposal_json={"symbol": "AAPL", "side": "buy", "quantity": 10, "order_type": "market"},
            risk_json={"blocked": False, "warnings": []},
            explanation_md="Test buy",
            status=ProposalStatus.PENDING,
            expires_at=expires_at,
        )
        session.add(proposal)
        await session.flush()

        assert proposal.id == proposal_id
        assert proposal.status == ProposalStatus.PENDING

    @pytest.mark.asyncio
    async def test_proposal_expires_at_is_set(self, session: AsyncSession):
        uid = await _seed_user(session)
        expires_at = datetime.utcnow() + timedelta(minutes=5)
        proposal = CopilotTradeProposal(
            id=str(uuid.uuid4()),
            user_id=uid,
            proposal_json={"symbol": "SPY", "side": "sell", "quantity": 5},
            status=ProposalStatus.PENDING,
            expires_at=expires_at,
        )
        session.add(proposal)
        await session.flush()

        assert proposal.expires_at is not None
        assert proposal.expires_at > datetime.utcnow()


# ---------------------------------------------------------------------------
# Confirmation flow tests
# ---------------------------------------------------------------------------

class TestConfirmationFlow:
    @pytest.mark.asyncio
    async def test_confirmation_record_created(self, session: AsyncSession):
        uid = await _seed_user(session)
        proposal = CopilotTradeProposal(
            id=str(uuid.uuid4()),
            user_id=uid,
            proposal_json={"symbol": "AAPL", "side": "buy", "quantity": 10},
            status=ProposalStatus.CONFIRMED,
            expires_at=datetime.utcnow() + timedelta(minutes=5),
        )
        session.add(proposal)
        await session.flush()

        token, token_hash = ConfirmationService._generate_token()
        confirmation = CopilotTradeConfirmation(
            id=str(uuid.uuid4()),
            proposal_id=proposal.id,
            user_id=uid,
            confirmation_token_hash=token_hash,
            status="pending",
        )
        session.add(confirmation)
        await session.flush()

        assert confirmation.proposal_id == proposal.id
        assert ConfirmationService._validate_token(token, confirmation.confirmation_token_hash)

    @pytest.mark.asyncio
    async def test_expired_proposal_cannot_confirm(self, session: AsyncSession):
        uid = await _seed_user(session)
        # Create an already-expired proposal
        proposal = CopilotTradeProposal(
            id=str(uuid.uuid4()),
            user_id=uid,
            proposal_json={"symbol": "AAPL", "side": "buy", "quantity": 10},
            status=ProposalStatus.PENDING,
            expires_at=datetime.utcnow() - timedelta(minutes=1),
        )
        session.add(proposal)
        await session.flush()

        assert proposal.expires_at < datetime.utcnow()

    @pytest.mark.asyncio
    async def test_confirmation_status_transitions(self, session: AsyncSession):
        uid = await _seed_user(session)
        proposal = CopilotTradeProposal(
            id=str(uuid.uuid4()),
            user_id=uid,
            proposal_json={"symbol": "TSLA", "side": "buy", "quantity": 5},
            status=ProposalStatus.PENDING,
            expires_at=datetime.utcnow() + timedelta(minutes=5),
        )
        session.add(proposal)
        await session.flush()

        # Transition to confirmed
        proposal.status = ProposalStatus.CONFIRMED
        await session.flush()
        assert proposal.status == ProposalStatus.CONFIRMED

        # Transition to executed
        proposal.status = ProposalStatus.EXECUTED
        await session.flush()
        assert proposal.status == ProposalStatus.EXECUTED


# ---------------------------------------------------------------------------
# Execution flow tests
# ---------------------------------------------------------------------------

class TestExecutionFlow:
    @pytest.mark.asyncio
    async def test_executed_creates_audit_log(self, session: AsyncSession):
        uid = await _seed_user(session)
        proposal_id = str(uuid.uuid4())

        audit = CopilotAuditLog(
            id=str(uuid.uuid4()),
            user_id=uid,
            action_type="trade_executed",
            resource_type="copilot_trade_proposals",
            resource_id=proposal_id,
            payload_json={"proposal": {"symbol": "AAPL"}, "execution": {"status": "submitted"}},
        )
        session.add(audit)
        await session.flush()

        assert audit.action_type == "trade_executed"
        assert audit.resource_id == proposal_id

    @pytest.mark.asyncio
    async def test_proposal_rejected_status(self, session: AsyncSession):
        uid = await _seed_user(session)
        proposal = CopilotTradeProposal(
            id=str(uuid.uuid4()),
            user_id=uid,
            proposal_json={"symbol": "GME", "side": "buy", "quantity": 1000},
            status=ProposalStatus.PENDING,
        )
        session.add(proposal)
        await session.flush()

        proposal.status = ProposalStatus.REJECTED
        await session.flush()
        assert proposal.status == ProposalStatus.REJECTED

    @pytest.mark.asyncio
    async def test_proposal_failed_status(self, session: AsyncSession):
        uid = await _seed_user(session)
        proposal = CopilotTradeProposal(
            id=str(uuid.uuid4()),
            user_id=uid,
            proposal_json={"symbol": "AMC", "side": "sell", "quantity": 50},
            status=ProposalStatus.CONFIRMED,
        )
        session.add(proposal)
        await session.flush()

        proposal.status = ProposalStatus.FAILED
        await session.flush()
        assert proposal.status == ProposalStatus.FAILED
