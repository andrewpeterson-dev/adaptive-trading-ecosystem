"""Trade proposal service — creates and manages AI-generated trade proposals."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Optional

import structlog
from sqlalchemy import select, update

from config.settings import get_settings
from db.database import get_session

logger = structlog.get_logger(__name__)

# How long a proposal stays valid before auto-expiring
_PROPOSAL_TTL_MINUTES = 5


class TradeProposalService:
    """Creates, retrieves, and manages trade proposals."""

    def __init__(self):
        self._settings = get_settings()

    async def create_proposal(
        self,
        user_id: int,
        thread_id: Optional[str],
        proposal_data: dict,
        explanation: str,
    ) -> dict:
        """Create a draft trade proposal, run risk checks, and store in DB.

        ``proposal_data`` should contain at minimum:
          - symbol: str
          - side: 'buy' | 'sell'
          - quantity: float
          - order_type: 'market' | 'limit'
          - limit_price: float (if order_type == 'limit')
        """
        from db.copilot_models import CopilotTradeProposal, ProposalStatus

        # Run risk checks
        risk_result = await self._run_risk_checks(user_id, proposal_data)
        if risk_result.get("blocked"):
            logger.warning(
                "proposal_blocked_by_risk",
                user_id=user_id,
                reason=risk_result.get("reason"),
            )
            return {
                "status": "blocked",
                "risk": risk_result,
                "explanation": explanation,
            }

        proposal_id = str(uuid.uuid4())
        expires_at = datetime.utcnow() + timedelta(minutes=_PROPOSAL_TTL_MINUTES)

        proposal = CopilotTradeProposal(
            id=proposal_id,
            user_id=user_id,
            thread_id=thread_id,
            proposal_json=proposal_data,
            risk_json=risk_result,
            explanation_md=explanation,
            status=ProposalStatus.PENDING,
            expires_at=expires_at,
        )

        async with get_session() as session:
            session.add(proposal)

        logger.info(
            "proposal_created",
            proposal_id=proposal_id,
            user_id=user_id,
            symbol=proposal_data.get("symbol"),
        )

        return {
            "proposal_id": proposal_id,
            "status": "pending",
            "proposal": proposal_data,
            "risk": risk_result,
            "explanation": explanation,
            "expires_at": expires_at.isoformat(),
        }

    async def get_proposal(self, proposal_id: str, user_id: int) -> dict:
        """Retrieve a proposal by ID, scoped to user."""
        from db.copilot_models import CopilotTradeProposal

        async with get_session() as session:
            stmt = select(CopilotTradeProposal).where(
                CopilotTradeProposal.id == proposal_id,
                CopilotTradeProposal.user_id == user_id,
            )
            result = await session.execute(stmt)
            proposal = result.scalar_one_or_none()

        if not proposal:
            raise ValueError(f"Proposal {proposal_id} not found")

        return {
            "proposal_id": proposal.id,
            "status": proposal.status.value if hasattr(proposal.status, "value") else proposal.status,
            "proposal": proposal.proposal_json,
            "risk": proposal.risk_json,
            "explanation": proposal.explanation_md,
            "expires_at": proposal.expires_at.isoformat() if proposal.expires_at else None,
            "created_at": proposal.created_at.isoformat() if proposal.created_at else None,
        }

    async def cancel_proposal(self, proposal_id: str, user_id: int) -> dict:
        """Cancel a pending proposal."""
        from db.copilot_models import CopilotTradeProposal, ProposalStatus

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
                raise ValueError(f"Cannot cancel proposal in status '{current_status}'")

            proposal.status = ProposalStatus.REJECTED

        logger.info("proposal_cancelled", proposal_id=proposal_id, user_id=user_id)
        return {"proposal_id": proposal_id, "status": "rejected"}

    async def expire_stale_proposals(self) -> int:
        """Expire all proposals older than the TTL. Returns count of expired."""
        from db.copilot_models import CopilotTradeProposal, ProposalStatus

        now = datetime.utcnow()

        async with get_session() as session:
            stmt = (
                update(CopilotTradeProposal)
                .where(
                    CopilotTradeProposal.status == ProposalStatus.PENDING,
                    CopilotTradeProposal.expires_at < now,
                )
                .values(status=ProposalStatus.EXPIRED)
            )
            result = await session.execute(stmt)
            count = result.rowcount

        if count:
            logger.info("proposals_expired", count=count)
        return count

    async def _run_risk_checks(self, user_id: int, proposal_data: dict) -> dict:
        """Run pre-trade risk checks.

        Checks:
          1. Position size vs max allowed
          2. Portfolio exposure vs max allowed
          3. Drawdown vs max allowed
          4. Proposal not expired (handled at confirmation time)
        """
        from db.copilot_models import CopilotPosition, CopilotPortfolioSnapshot
        from sqlalchemy import func

        warnings: list[str] = []
        blocked = False
        reason = None

        quantity = float(proposal_data.get("quantity", 0))
        entry_price = float(proposal_data.get("limit_price") or proposal_data.get("estimated_price", 0))
        notional = quantity * entry_price if entry_price else 0

        async with get_session() as session:
            # Get total portfolio equity
            snap_stmt = (
                select(CopilotPortfolioSnapshot)
                .where(CopilotPortfolioSnapshot.user_id == user_id)
                .order_by(CopilotPortfolioSnapshot.snapshot_ts.desc())
                .limit(1)
            )
            snap_result = await session.execute(snap_stmt)
            latest_snapshot = snap_result.scalar_one_or_none()

            equity = float(latest_snapshot.equity or 0) if latest_snapshot else 0

            # 1. Position size check
            if equity > 0 and notional > 0:
                position_pct = notional / equity
                if position_pct > self._settings.max_position_size_pct:
                    blocked = True
                    reason = (
                        f"Position size {position_pct:.1%} exceeds max "
                        f"{self._settings.max_position_size_pct:.1%}"
                    )
                elif position_pct > self._settings.max_position_size_pct * 0.8:
                    warnings.append(
                        f"Position size {position_pct:.1%} approaching limit "
                        f"({self._settings.max_position_size_pct:.1%})"
                    )

            # 2. Exposure check
            pos_stmt = select(func.sum(func.abs(CopilotPosition.market_value))).where(
                CopilotPosition.user_id == user_id,
            )
            pos_result = await session.execute(pos_stmt)
            total_exposure = float(pos_result.scalar() or 0) + notional

            if equity > 0 and total_exposure > 0:
                exposure_pct = total_exposure / equity
                if exposure_pct > self._settings.max_portfolio_exposure_pct:
                    blocked = True
                    reason = reason or (
                        f"Portfolio exposure {exposure_pct:.1%} exceeds max "
                        f"{self._settings.max_portfolio_exposure_pct:.1%}"
                    )
                elif exposure_pct > self._settings.max_portfolio_exposure_pct * 0.9:
                    warnings.append(
                        f"Exposure {exposure_pct:.1%} approaching limit "
                        f"({self._settings.max_portfolio_exposure_pct:.1%})"
                    )

            # 3. Drawdown check (simplified: compare current equity to peak)
            peak_stmt = select(func.max(CopilotPortfolioSnapshot.equity)).where(
                CopilotPortfolioSnapshot.user_id == user_id,
            )
            peak_result = await session.execute(peak_stmt)
            peak_equity = float(peak_result.scalar() or 0)

            if peak_equity > 0 and equity > 0:
                drawdown = (peak_equity - equity) / peak_equity
                if drawdown > self._settings.max_drawdown_pct:
                    blocked = True
                    reason = reason or (
                        f"Current drawdown {drawdown:.1%} exceeds max "
                        f"{self._settings.max_drawdown_pct:.1%}"
                    )
                elif drawdown > self._settings.max_drawdown_pct * 0.8:
                    warnings.append(
                        f"Drawdown {drawdown:.1%} approaching limit "
                        f"({self._settings.max_drawdown_pct:.1%})"
                    )

        return {
            "blocked": blocked,
            "reason": reason,
            "warnings": warnings,
            "checks": {
                "position_size": "fail" if blocked and "Position size" in (reason or "") else "pass",
                "exposure": "fail" if blocked and "exposure" in (reason or "").lower() else "pass",
                "drawdown": "fail" if blocked and "drawdown" in (reason or "").lower() else "pass",
            },
            "equity": equity,
            "notional": notional,
        }
