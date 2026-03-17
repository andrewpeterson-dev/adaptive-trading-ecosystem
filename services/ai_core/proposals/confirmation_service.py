"""Confirmation service — handles the confirm-then-execute flow for trade proposals."""
from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime

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
        from db.cerberus_models import (
            CerberusTradeProposal,
            CerberusTradeConfirmation,
            ProposalStatus,
        )
        from services.ai_core.proposals.trade_proposal_service import TradeProposalService

        async with get_session() as session:
            stmt = select(CerberusTradeProposal).where(
                CerberusTradeProposal.id == proposal_id,
                CerberusTradeProposal.user_id == user_id,
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
                stmt = select(CerberusTradeProposal).where(
                    CerberusTradeProposal.id == proposal_id,
                    CerberusTradeProposal.user_id == user_id,
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

        confirmation = CerberusTradeConfirmation(
            id=str(uuid.uuid4()),
            proposal_id=proposal_id,
            user_id=user_id,
            confirmation_token_hash=token_hash,
            status="pending",
        )

        async with get_session() as session:
            # Update proposal status
            stmt = select(CerberusTradeProposal).where(
                CerberusTradeProposal.id == proposal_id,
                CerberusTradeProposal.user_id == user_id,
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
        from db.cerberus_models import (
            CerberusTradeProposal,
            CerberusTradeConfirmation,
            CerberusAuditLog,
            ProposalStatus,
        )

        # Fetch confirmation record
        async with get_session() as session:
            stmt = (
                select(CerberusTradeConfirmation)
                .where(
                    CerberusTradeConfirmation.proposal_id == proposal_id,
                    CerberusTradeConfirmation.user_id == user_id,
                    CerberusTradeConfirmation.status == "pending",
                )
                .order_by(CerberusTradeConfirmation.created_at.desc())
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
            prop_stmt = select(CerberusTradeProposal).where(
                CerberusTradeProposal.id == proposal_id,
                CerberusTradeProposal.user_id == user_id,
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
        except Exception:
            # Mark as failed
            async with get_session() as session:
                stmt = select(CerberusTradeProposal).where(
                    CerberusTradeProposal.id == proposal_id,
                    CerberusTradeProposal.user_id == user_id,
                )
                result = await session.execute(stmt)
                p = result.scalar_one()
                p.status = ProposalStatus.FAILED

                conf_stmt = select(CerberusTradeConfirmation).where(
                    CerberusTradeConfirmation.id == confirmation.id,
                    CerberusTradeConfirmation.user_id == user_id,
                )
                conf_result = await session.execute(conf_stmt)
                c = conf_result.scalar_one()
                c.status = "failed"

            logger.exception("execution_failed", proposal_id=proposal_id)
            raise

        # Update statuses
        now = datetime.utcnow()
        async with get_session() as session:
            stmt = select(CerberusTradeProposal).where(
                CerberusTradeProposal.id == proposal_id,
                CerberusTradeProposal.user_id == user_id,
            )
            result = await session.execute(stmt)
            p = result.scalar_one()
            p.status = ProposalStatus.EXECUTED

            conf_stmt = select(CerberusTradeConfirmation).where(
                CerberusTradeConfirmation.id == confirmation.id,
                CerberusTradeConfirmation.user_id == user_id,
            )
            conf_result = await session.execute(conf_stmt)
            c = conf_result.scalar_one()
            c.status = "executed"
            c.confirmed_at = now
            c.executed_at = now

            # Audit log
            audit = CerberusAuditLog(
                id=str(uuid.uuid4()),
                user_id=user_id,
                action_type="trade_executed",
                resource_type="cerberus_trade_proposals",
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
        """Execute an order via paper trading or Webull depending on user's mode.

        Routes:
          - Paper mode (default): executes via PaperPortfolio system
          - Live mode: routes to Webull if user has credentials
        """
        from db.models import UserTradingSession, TradingModeEnum
        from sqlalchemy import select

        symbol = (proposal_json.get("symbol") or "").upper()
        raw_side = (proposal_json.get("side") or "buy").upper()
        quantity = float(proposal_json.get("quantity") or 0)
        order_type = proposal_json.get("order_type", "market")
        limit_price = proposal_json.get("limit_price")

        side = "BUY" if raw_side in ("BUY", "LONG") else "SELL"

        if not symbol or quantity <= 0:
            raise ValueError(f"Invalid order: symbol={symbol}, quantity={quantity}")

        # Check user's trading mode
        mode = TradingModeEnum.PAPER
        async with get_session() as session:
            result = await session.execute(
                select(UserTradingSession).where(UserTradingSession.user_id == user_id)
            )
            session_row = result.scalar_one_or_none()
            if session_row:
                mode = session_row.active_mode

        if mode == TradingModeEnum.LIVE:
            return await self._execute_live_order(
                user_id, symbol, side, int(quantity), order_type, limit_price
            )

        # Paper mode
        return await self._execute_paper_order(user_id, symbol, side, quantity)

    async def _execute_paper_order(
        self, user_id: int, symbol: str, side: str, quantity: float
    ) -> dict:
        """Execute via paper trading system."""
        from db.models import (
            PaperPortfolio, PaperPosition, PaperTrade,
            PaperTradeStatus, TradeDirection,
        )
        from api.routes.paper_trading import _fetch_current_price

        current_price = await _fetch_current_price(symbol)

        async with get_session() as session:
            result = await session.execute(
                select(PaperPortfolio).where(PaperPortfolio.user_id == user_id)
            )
            portfolio = result.scalar_one_or_none()
            if not portfolio:
                portfolio = PaperPortfolio(
                    user_id=user_id, cash=1_000_000.0, initial_capital=1_000_000.0
                )
                session.add(portfolio)
                await session.flush()

            if side == "BUY":
                cost = current_price * quantity
                if cost > portfolio.cash:
                    raise ValueError(
                        f"Insufficient cash: need ${cost:,.2f}, have ${portfolio.cash:,.2f}"
                    )
                portfolio.cash -= cost

                pos_result = await session.execute(
                    select(PaperPosition).where(
                        PaperPosition.portfolio_id == portfolio.id,
                        PaperPosition.symbol == symbol,
                    )
                )
                position = pos_result.scalar_one_or_none()

                if position:
                    total_cost = (position.avg_entry_price * position.quantity) + cost
                    position.quantity += quantity
                    if abs(position.quantity) <= 0.0001:
                        await session.delete(position)
                    else:
                        position.avg_entry_price = total_cost / position.quantity
                        position.current_price = current_price
                elif not position:
                    position = PaperPosition(
                        portfolio_id=portfolio.id, user_id=user_id,
                        symbol=symbol, quantity=quantity,
                        avg_entry_price=current_price, current_price=current_price,
                    )
                    session.add(position)

                trade = PaperTrade(
                    portfolio_id=portfolio.id, user_id=user_id, symbol=symbol,
                    direction=TradeDirection.LONG, quantity=quantity,
                    entry_price=current_price, status=PaperTradeStatus.OPEN,
                )
                session.add(trade)
            else:
                pos_result = await session.execute(
                    select(PaperPosition).where(
                        PaperPosition.portfolio_id == portfolio.id,
                        PaperPosition.symbol == symbol,
                    )
                )
                position = pos_result.scalar_one_or_none()
                if not position or position.quantity < quantity:
                    held = position.quantity if position else 0
                    raise ValueError(f"Insufficient shares: want {quantity}, hold {held}")

                proceeds = current_price * quantity
                pnl = proceeds - (position.avg_entry_price * quantity)
                portfolio.cash += proceeds
                position.quantity -= quantity
                if abs(position.quantity) <= 0.0001:
                    await session.delete(position)

                trade = PaperTrade(
                    portfolio_id=portfolio.id, user_id=user_id, symbol=symbol,
                    direction=TradeDirection.SHORT, quantity=quantity,
                    entry_price=position.avg_entry_price, exit_price=current_price,
                    pnl=pnl, status=PaperTradeStatus.CLOSED,
                    exit_time=datetime.utcnow(),
                )
                session.add(trade)

        logger.info(
            "paper_order_executed", user_id=user_id,
            symbol=symbol, side=side, quantity=quantity, price=current_price,
        )
        return {
            "status": "executed",
            "broker": "paper",
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "price": current_price,
        }

    async def _execute_live_order(
        self, user_id: int, symbol: str, side: str, quantity: int,
        order_type: str = "market", limit_price: float = None,
    ) -> dict:
        """Execute via Webull live trading."""
        from api.routes.webull import _get_user_clients
        from data.webull.trading import OrderRequest as WBOrderRequest

        wb = await _get_user_clients(user_id, "real")
        if not wb:
            raise ValueError("No Webull credentials configured for live trading")

        wb_order_type = "MKT" if order_type == "market" else "LMT"
        req = WBOrderRequest(
            symbol=symbol, side=side, qty=quantity,
            order_type=wb_order_type, limit_price=limit_price,
        )
        result = wb.trading.place_order(req, user_confirmed=True)

        if not result.success:
            raise ValueError(f"Webull order failed: {result.error or 'unknown'}")

        logger.info(
            "live_order_executed", user_id=user_id,
            symbol=symbol, side=side, quantity=quantity,
            order_id=result.order_id,
        )
        return {
            "status": "executed",
            "broker": "webull",
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "order_id": result.order_id,
        }
