"""
Paper trading routes — simulated trading for users without broker credentials.

Provides portfolio management, trade execution, position tracking, and trade
history using the PaperPortfolio / PaperPosition / PaperTrade DB models.
"""

from datetime import datetime
from typing import Optional

import structlog
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select

from db.database import get_session
from db.models import (
    PaperPortfolio,
    PaperPosition,
    PaperTrade,
    PaperTradeStatus,
    TradeDirection,
)

logger = structlog.get_logger(__name__)

router = APIRouter()


# ── Request / Response schemas ────────────────────────────────────────────


class PaperTradeRequest(BaseModel):
    symbol: str
    side: str  # "BUY" or "SELL"
    quantity: float
    user_confirmed: bool = False


class ResetRequest(BaseModel):
    initial_capital: Optional[float] = 1_000_000.0


# ── Helpers ───────────────────────────────────────────────────────────────


def _require_user(request: Request) -> int:
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user_id


async def _get_or_create_portfolio(user_id: int) -> dict:
    """Fetch or create a paper portfolio for the user. Returns dict representation."""
    async with get_session() as session:
        result = await session.execute(
            select(PaperPortfolio).where(PaperPortfolio.user_id == user_id)
        )
        portfolio = result.scalar_one_or_none()

        if not portfolio:
            portfolio = PaperPortfolio(
                user_id=user_id,
                cash=1_000_000.0,
                initial_capital=1_000_000.0,
            )
            session.add(portfolio)
            await session.flush()

        # Eagerly load positions before session closes
        pos_result = await session.execute(
            select(PaperPosition).where(PaperPosition.portfolio_id == portfolio.id)
        )
        positions = pos_result.scalars().all()

        positions_value = sum(
            (p.current_price or p.avg_entry_price) * p.quantity for p in positions
        )

        return {
            "id": portfolio.id,
            "user_id": portfolio.user_id,
            "cash": portfolio.cash,
            "initial_capital": portfolio.initial_capital,
            "positions_value": positions_value,
            "total_equity": portfolio.cash + positions_value,
            "positions": [
                {
                    "id": p.id,
                    "symbol": p.symbol,
                    "quantity": p.quantity,
                    "avg_entry_price": p.avg_entry_price,
                    "current_price": p.current_price or p.avg_entry_price,
                    "unrealized_pnl": p.unrealized_pnl or 0.0,
                    "market_value": (p.current_price or p.avg_entry_price) * p.quantity,
                }
                for p in positions
            ],
        }


async def _fetch_current_price(symbol: str) -> float:
    """Get current price for a symbol using the unofficial webull SDK."""
    try:
        from webull import webull
        wb = webull()
        quote = wb.get_quote(symbol.upper())
        if quote:
            price = float(quote.get("close", 0) or quote.get("price", 0))
            if price > 0:
                return price
    except Exception as e:
        logger.warning("paper_price_fetch_failed", symbol=symbol, error=str(e))

    raise HTTPException(
        status_code=400,
        detail=f"Could not fetch price for {symbol}. Market may be closed.",
    )


# ── Routes ────────────────────────────────────────────────────────────────


@router.get("/portfolio")
async def get_portfolio(request: Request):
    """Get or create paper portfolio for the current user."""
    user_id = _require_user(request)
    return await _get_or_create_portfolio(user_id)


@router.post("/trade")
async def execute_paper_trade(request: Request, req: PaperTradeRequest):
    """Execute a paper trade (BUY or SELL)."""
    user_id = _require_user(request)

    # Safety gate
    if not req.user_confirmed:
        return {
            "executed": False,
            "blocked": True,
            "reason": "Trade requires user_confirmed=true",
        }

    symbol = req.symbol.strip().upper()
    side = req.side.strip().upper()
    qty = req.quantity

    if side not in ("BUY", "SELL"):
        raise HTTPException(status_code=400, detail="side must be BUY or SELL")
    if qty <= 0:
        raise HTTPException(status_code=400, detail="quantity must be positive")

    # Get current price
    current_price = await _fetch_current_price(symbol)

    async with get_session() as session:
        # Load portfolio
        result = await session.execute(
            select(PaperPortfolio).where(PaperPortfolio.user_id == user_id)
        )
        portfolio = result.scalar_one_or_none()

        if not portfolio:
            portfolio = PaperPortfolio(
                user_id=user_id,
                cash=1_000_000.0,
                initial_capital=1_000_000.0,
            )
            session.add(portfolio)
            await session.flush()

        if side == "BUY":
            cost = current_price * qty
            if cost > portfolio.cash:
                raise HTTPException(
                    status_code=400,
                    detail=f"Insufficient cash. Need ${cost:,.2f}, have ${portfolio.cash:,.2f}",
                )

            # Deduct cash
            portfolio.cash -= cost

            # Check for existing position
            pos_result = await session.execute(
                select(PaperPosition).where(
                    PaperPosition.portfolio_id == portfolio.id,
                    PaperPosition.symbol == symbol,
                )
            )
            position = pos_result.scalar_one_or_none()

            if position:
                # Average into existing position
                total_cost = (position.avg_entry_price * position.quantity) + cost
                position.quantity += qty
                position.avg_entry_price = total_cost / position.quantity
                position.current_price = current_price
                position.unrealized_pnl = (
                    (current_price - position.avg_entry_price) * position.quantity
                )
            else:
                # New position
                position = PaperPosition(
                    portfolio_id=portfolio.id,
                    user_id=user_id,
                    symbol=symbol,
                    quantity=qty,
                    avg_entry_price=current_price,
                    current_price=current_price,
                    unrealized_pnl=0.0,
                )
                session.add(position)

            # Record the trade (OPEN — buy side)
            trade = PaperTrade(
                portfolio_id=portfolio.id,
                user_id=user_id,
                symbol=symbol,
                direction=TradeDirection.LONG,
                quantity=qty,
                entry_price=current_price,
                status=PaperTradeStatus.OPEN,
            )
            session.add(trade)

            return {
                "executed": True,
                "side": "BUY",
                "symbol": symbol,
                "quantity": qty,
                "price": current_price,
                "cost": cost,
                "remaining_cash": portfolio.cash,
            }

        else:  # SELL
            # Find existing position
            pos_result = await session.execute(
                select(PaperPosition).where(
                    PaperPosition.portfolio_id == portfolio.id,
                    PaperPosition.symbol == symbol,
                )
            )
            position = pos_result.scalar_one_or_none()

            if not position or position.quantity < qty:
                held = position.quantity if position else 0
                raise HTTPException(
                    status_code=400,
                    detail=f"Insufficient shares. Want to sell {qty}, hold {held}",
                )

            # Calculate P&L
            proceeds = current_price * qty
            cost_basis = position.avg_entry_price * qty
            pnl = proceeds - cost_basis

            # Add proceeds to cash
            portfolio.cash += proceeds

            # Update or remove position
            position.quantity -= qty
            if position.quantity <= 0.0001:  # effectively zero
                await session.delete(position)
            else:
                position.current_price = current_price
                position.unrealized_pnl = (
                    (current_price - position.avg_entry_price) * position.quantity
                )

            # Record the closed trade
            trade = PaperTrade(
                portfolio_id=portfolio.id,
                user_id=user_id,
                symbol=symbol,
                direction=TradeDirection.SHORT,
                quantity=qty,
                entry_price=position.avg_entry_price,
                exit_price=current_price,
                pnl=pnl,
                status=PaperTradeStatus.CLOSED,
                exit_time=datetime.utcnow(),
            )
            session.add(trade)

            return {
                "executed": True,
                "side": "SELL",
                "symbol": symbol,
                "quantity": qty,
                "price": current_price,
                "proceeds": proceeds,
                "pnl": pnl,
                "remaining_cash": portfolio.cash,
            }


@router.get("/positions")
async def get_paper_positions(request: Request):
    """List all open paper positions with current prices."""
    user_id = _require_user(request)

    async with get_session() as session:
        result = await session.execute(
            select(PaperPortfolio).where(PaperPortfolio.user_id == user_id)
        )
        portfolio = result.scalar_one_or_none()

        if not portfolio:
            return {"positions": []}

        pos_result = await session.execute(
            select(PaperPosition).where(PaperPosition.portfolio_id == portfolio.id)
        )
        positions = pos_result.scalars().all()

        # Refresh current prices
        position_list = []
        for p in positions:
            try:
                current = await _fetch_current_price(p.symbol)
                p.current_price = current
                p.unrealized_pnl = (current - p.avg_entry_price) * p.quantity
            except Exception:
                # Keep stale price if refresh fails
                pass

            position_list.append({
                "symbol": p.symbol,
                "quantity": p.quantity,
                "avg_entry_price": p.avg_entry_price,
                "current_price": p.current_price or p.avg_entry_price,
                "market_value": (p.current_price or p.avg_entry_price) * p.quantity,
                "unrealized_pnl": p.unrealized_pnl or 0.0,
                "unrealized_pnl_pct": (
                    ((p.current_price or p.avg_entry_price) - p.avg_entry_price)
                    / p.avg_entry_price
                    * 100
                    if p.avg_entry_price
                    else 0.0
                ),
            })

        return {"positions": position_list}


@router.get("/history")
async def get_trade_history(request: Request, limit: int = 100):
    """List paper trade history (completed trades with P&L)."""
    user_id = _require_user(request)

    async with get_session() as session:
        result = await session.execute(
            select(PaperTrade)
            .where(PaperTrade.user_id == user_id)
            .order_by(PaperTrade.entry_time.desc())
            .limit(limit)
        )
        trades = result.scalars().all()

        return {
            "trades": [
                {
                    "id": t.id,
                    "symbol": t.symbol,
                    "direction": t.direction.value if t.direction else None,
                    "quantity": t.quantity,
                    "entry_price": t.entry_price,
                    "exit_price": t.exit_price,
                    "pnl": t.pnl,
                    "status": t.status.value if t.status else None,
                    "entry_time": t.entry_time.isoformat() if t.entry_time else None,
                    "exit_time": t.exit_time.isoformat() if t.exit_time else None,
                }
                for t in trades
            ]
        }


@router.post("/reset")
async def reset_portfolio(request: Request, req: Optional[ResetRequest] = None):
    """Reset paper portfolio to initial capital. Deletes all positions and trades."""
    user_id = _require_user(request)
    initial_capital = req.initial_capital if req else 1_000_000.0

    async with get_session() as session:
        result = await session.execute(
            select(PaperPortfolio).where(PaperPortfolio.user_id == user_id)
        )
        portfolio = result.scalar_one_or_none()

        if portfolio:
            # Delete all positions
            pos_result = await session.execute(
                select(PaperPosition).where(
                    PaperPosition.portfolio_id == portfolio.id
                )
            )
            for p in pos_result.scalars().all():
                await session.delete(p)

            # Delete all trades
            trade_result = await session.execute(
                select(PaperTrade).where(
                    PaperTrade.portfolio_id == portfolio.id
                )
            )
            for t in trade_result.scalars().all():
                await session.delete(t)

            # Reset cash
            portfolio.cash = initial_capital
            portfolio.initial_capital = initial_capital
        else:
            portfolio = PaperPortfolio(
                user_id=user_id,
                cash=initial_capital,
                initial_capital=initial_capital,
            )
            session.add(portfolio)

    return {
        "status": "reset",
        "cash": initial_capital,
        "initial_capital": initial_capital,
    }
