"""Confirmation service — handles the confirm-then-execute flow for trade proposals."""
from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime
from typing import Optional

import structlog
from sqlalchemy import select

from db.database import get_session

logger = structlog.get_logger(__name__)


class ConfirmationService:
    """Manages the two-step confirmation flow for executing trade proposals."""

    async def confirm_proposal(self, proposal_id: str, user_id: int) -> dict:
        """Confirm a pending proposal: re-run risk checks, generate a confirmation token.

        Returns the token (plaintext) that must be passed to ``execute_confirmed``
        to actually place the order.
        """
        from db.copilot_models import (
            CopilotTradeProposal,
            CopilotTradeConfirmation,
            ProposalStatus,
        )
        from services.ai_core.proposals.trade_proposal_service import TradeProposalService

        async with get_session() as session:
            stmt = select(CopilotTradeProposal).where(
                CopilotTradeProposal.id == proposal_id,
                CopilotTradeProposal.user_id == user_id,
            )
            result = await session.execute(stmt)
            proposal = result.scalar_one_or_none()

            if not proposal:
                raise ValueError(f"Proposal {proposal_id} not found")

            current_status = proposal.status.value if hasattr(proposal.status, "value") else proposal.status
            if current_status != "pending":
                raise ValueError(f"Proposal is not pending (status={current_status})")

            # Check expiration
            if proposal.expires_at and proposal.expires_at < datetime.utcnow():
                proposal.status = ProposalStatus.EXPIRED
                raise ValueError("Proposal has expired")

        # Re-run risk checks
        svc = TradeProposalService()
        risk_result = await svc._run_risk_checks(user_id, proposal.proposal_json)

        if risk_result.get("blocked"):
            # Update proposal status to rejected
            async with get_session() as session:
                stmt = select(CopilotTradeProposal).where(
                    CopilotTradeProposal.id == proposal_id,
                )
                result = await session.execute(stmt)
                p = result.scalar_one()
                p.status = ProposalStatus.REJECTED
                p.risk_json = risk_result

            logger.warning(
                "confirmation_blocked",
                proposal_id=proposal_id,
                reason=risk_result.get("reason"),
            )
            return {
                "proposal_id": proposal_id,
                "status": "blocked",
                "risk": risk_result,
            }

        # Generate confirmation token
        token, token_hash = self._generate_token()

        confirmation = CopilotTradeConfirmation(
            id=str(uuid.uuid4()),
            proposal_id=proposal_id,
            user_id=user_id,
            confirmation_token_hash=token_hash,
            status="pending",
        )

        async with get_session() as session:
            # Update proposal status
            stmt = select(CopilotTradeProposal).where(
                CopilotTradeProposal.id == proposal_id,
            )
            result = await session.execute(stmt)
            p = result.scalar_one()
            p.status = ProposalStatus.CONFIRMED
            p.risk_json = risk_result

            session.add(confirmation)

        logger.info("proposal_confirmed", proposal_id=proposal_id, user_id=user_id)

        return {
            "proposal_id": proposal_id,
            "confirmation_token": token,
            "status": "confirmed",
            "risk": risk_result,
        }

    async def execute_confirmed(
        self,
        proposal_id: str,
        confirmation_token: str,
        user_id: int,
    ) -> dict:
        """Execute a confirmed proposal after validating the confirmation token.

        Steps:
          1. Validate token against stored hash
          2. Execute via broker adapter
          3. Store audit log entry
          4. Update confirmation and proposal status
        """
        from db.copilot_models import (
            CopilotTradeProposal,
            CopilotTradeConfirmation,
            CopilotAuditLog,
            ProposalStatus,
        )

        # Fetch confirmation record
        async with get_session() as session:
            stmt = (
                select(CopilotTradeConfirmation)
                .where(
                    CopilotTradeConfirmation.proposal_id == proposal_id,
                    CopilotTradeConfirmation.user_id == user_id,
                    CopilotTradeConfirmation.status == "pending",
                )
                .order_by(CopilotTradeConfirmation.created_at.desc())
                .limit(1)
            )
            result = await session.execute(stmt)
            confirmation = result.scalar_one_or_none()

            if not confirmation:
                raise ValueError("No pending confirmation found for this proposal")

            # Validate token
            if not self._validate_token(confirmation_token, confirmation.confirmation_token_hash):
                raise ValueError("Invalid confirmation token")

            # Fetch proposal
            prop_stmt = select(CopilotTradeProposal).where(
                CopilotTradeProposal.id == proposal_id,
                CopilotTradeProposal.user_id == user_id,
            )
            prop_result = await session.execute(prop_stmt)
            proposal = prop_result.scalar_one_or_none()

            if not proposal:
                raise ValueError(f"Proposal {proposal_id} not found")

            # Check proposal not expired
            if proposal.expires_at and proposal.expires_at < datetime.utcnow():
                proposal.status = ProposalStatus.EXPIRED
                confirmation.status = "expired"
                raise ValueError("Proposal has expired")

        # Execute via broker adapter
        try:
            execution_result = await self._execute_order(user_id, proposal.proposal_json)
        except Exception as exc:
            # Mark as failed
            async with get_session() as session:
                stmt = select(CopilotTradeProposal).where(
                    CopilotTradeProposal.id == proposal_id,
                )
                result = await session.execute(stmt)
                p = result.scalar_one()
                p.status = ProposalStatus.FAILED

                conf_stmt = select(CopilotTradeConfirmation).where(
                    CopilotTradeConfirmation.id == confirmation.id,
                )
                conf_result = await session.execute(conf_stmt)
                c = conf_result.scalar_one()
                c.status = "failed"

            logger.exception("execution_failed", proposal_id=proposal_id)
            raise

        # Update statuses
        now = datetime.utcnow()
        async with get_session() as session:
            stmt = select(CopilotTradeProposal).where(
                CopilotTradeProposal.id == proposal_id,
            )
            result = await session.execute(stmt)
            p = result.scalar_one()
            p.status = ProposalStatus.EXECUTED

            conf_stmt = select(CopilotTradeConfirmation).where(
                CopilotTradeConfirmation.id == confirmation.id,
            )
            conf_result = await session.execute(conf_stmt)
            c = conf_result.scalar_one()
            c.status = "executed"
            c.confirmed_at = now
            c.executed_at = now

            # Audit log
            audit = CopilotAuditLog(
                id=str(uuid.uuid4()),
                user_id=user_id,
                action_type="trade_executed",
                resource_type="copilot_trade_proposals",
                resource_id=proposal_id,
                payload_json={
                    "proposal": proposal.proposal_json,
                    "execution": execution_result,
                },
            )
            session.add(audit)

        logger.info(
            "trade_executed",
            proposal_id=proposal_id,
            user_id=user_id,
            result=execution_result,
        )

        return {
            "proposal_id": proposal_id,
            "status": "executed",
            "execution": execution_result,
        }

    @staticmethod
    def _generate_token() -> tuple[str, str]:
        """Generate a secure confirmation token and its SHA-256 hash.

        Returns (token_plaintext, token_hash).
        """
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        return token, token_hash

    @staticmethod
    def _validate_token(token: str, token_hash: str) -> bool:
        """Validate a plaintext token against a stored hash."""
        computed = hashlib.sha256(token.encode()).hexdigest()
        return secrets.compare_digest(computed, token_hash)

    async def _execute_order(self, user_id: int, proposal_json: dict) -> dict:
        """Execute an order via the broker adapter.

        This is a placeholder — the actual implementation will call the
        appropriate broker adapter (Webull, Alpaca, etc.) based on the
        user's brokerage account configuration.
        """
        # TODO: Integrate with actual broker adapters
        logger.info(
            "order_execution_placeholder",
            user_id=user_id,
            symbol=proposal_json.get("symbol"),
            side=proposal_json.get("side"),
            quantity=proposal_json.get("quantity"),
        )
        return {
            "status": "submitted",
            "broker": "placeholder",
            "symbol": proposal_json.get("symbol"),
            "side": proposal_json.get("side"),
            "quantity": proposal_json.get("quantity"),
            "message": "Order submitted (broker adapter not yet connected)",
        }
