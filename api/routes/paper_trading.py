"""
Paper trading routes — simulated trading for users without broker credentials.

Provides portfolio management, trade execution, position tracking, and trade
history using the PaperPortfolio / PaperPosition / PaperTrade DB models.
"""
from __future__ import annotations

import math
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
from services.options_data import fetch_option_snapshot, parse_occ_contract_symbol

logger = structlog.get_logger(__name__)

router = APIRouter()
INITIAL_CAPITAL = 100_000.0


# ── Request / Response schemas ────────────────────────────────────────────


class PaperTradeRequest(BaseModel):
    symbol: str
    side: Optional[str] = None      # "BUY" or "SELL"
    direction: Optional[str] = None  # alias for side (frontend uses this name)
    quantity: float
    notional: Optional[float] = None
    price: Optional[float] = None   # ignored — server fetches live price
    user_confirmed: bool = True     # default true; UI submit is the gate
    # Options fields (only needed for options orders)
    instrument_type: str = "stock"      # "stock" | "option"
    contract_symbol: Optional[str] = None
    option_type: Optional[str] = None   # "call" | "put"
    strike: Optional[float] = None
    expiry: Optional[str] = None        # "YYYY-MM-DD"


class ResetRequest(BaseModel):
    initial_capital: Optional[float] = INITIAL_CAPITAL


# ── Helpers ───────────────────────────────────────────────────────────────


def _require_user(request: Request) -> int:
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user_id


def _position_multiplier(symbol: str) -> int:
    return 100 if parse_occ_contract_symbol(symbol) else 1


def _position_market_value(symbol: str, price: float, quantity: float) -> float:
    return price * quantity * _position_multiplier(symbol)


def _position_unrealized_pnl(symbol: str, entry_price: float, current_price: float, quantity: float) -> float:
    return (current_price - entry_price) * quantity * _position_multiplier(symbol)


def _position_unrealized_pnl_pct(symbol: str, entry_price: float, current_price: float, quantity: float) -> float:
    basis = abs(entry_price * quantity * _position_multiplier(symbol))
    if basis <= 0:
        return 0.0
    pnl = _position_unrealized_pnl(symbol, entry_price, current_price, quantity)
    return pnl / basis


def _option_mark(snapshot: dict) -> float | None:
    bid = snapshot.get("bid")
    ask = snapshot.get("ask")
    last = snapshot.get("last")
    if bid is not None and ask is not None and bid > 0 and ask > 0:
        return (bid + ask) / 2
    if last is not None and last > 0:
        return float(last)
    if ask is not None and ask > 0:
        return float(ask)
    if bid is not None and bid > 0:
        return float(bid)
    return None


async def _fetch_option_price(
    *,
    contract_symbol: str | None,
    underlying: str,
    expiry: str,
    strike: float,
    option_type: str,
) -> tuple[str, float]:
    snapshot = await fetch_option_snapshot(
        underlying=underlying,
        expiration=expiry,
        strike=strike,
        option_type=option_type,
        contract_symbol=contract_symbol,
    )
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Option contract not found")

    mark = _option_mark(snapshot)
    if mark is None:
        raise HTTPException(
            status_code=400,
            detail=f"Could not price option contract {snapshot.get('symbol') or contract_symbol or underlying}",
        )

    return str(snapshot["symbol"]), float(mark)


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
                cash=INITIAL_CAPITAL,
                initial_capital=INITIAL_CAPITAL,
            )
            session.add(portfolio)
            await session.flush()

        # Eagerly load positions before session closes
        pos_result = await session.execute(
            select(PaperPosition).where(PaperPosition.portfolio_id == portfolio.id)
        )
        positions = pos_result.scalars().all()

        positions_value = sum(
            _position_market_value(
                p.symbol,
                p.current_price or p.avg_entry_price,
                p.quantity,
            )
            for p in positions
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
                    "market_value": _position_market_value(
                        p.symbol,
                        p.current_price or p.avg_entry_price,
                        p.quantity,
                    ),
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

    symbol = req.symbol.strip().upper()
    raw_side = (req.side or req.direction or "").strip().upper()
    qty = req.quantity

    side = raw_side
    if side not in ("BUY", "SELL"):
        raise HTTPException(status_code=400, detail="side must be BUY or SELL")
    is_option_trade = req.instrument_type == "option"

    if is_option_trade:
        contract_symbol = (req.contract_symbol or "").strip().upper() or None
        parsed_contract = parse_occ_contract_symbol(contract_symbol) if contract_symbol else None
        underlying = symbol
        expiry = req.expiry or (parsed_contract or {}).get("expiration")
        option_type = req.option_type or (parsed_contract or {}).get("option_type")
        strike = req.strike if req.strike is not None else (parsed_contract or {}).get("strike")
        if not expiry or not option_type or strike is None:
            raise HTTPException(
                status_code=400,
                detail="Option trades require contract_symbol or expiration, strike, and option_type",
            )

        symbol, current_price = await _fetch_option_price(
            contract_symbol=contract_symbol,
            underlying=underlying,
            expiry=expiry,
            strike=float(strike),
            option_type=option_type,
        )
    else:
        current_price = await _fetch_current_price(symbol)
        if req.notional is not None:
            qty = math.floor(req.notional / current_price)

    if qty <= 0:
        raise HTTPException(status_code=400, detail="quantity must be positive")

    async with get_session() as session:
        # Load portfolio with row-level lock to prevent concurrent trades
        # from reading the same cash balance (double-spend race condition).
        result = await session.execute(
            select(PaperPortfolio)
            .where(PaperPortfolio.user_id == user_id)
            .with_for_update()
        )
        portfolio = result.scalar_one_or_none()

        if not portfolio:
            portfolio = PaperPortfolio(
                user_id=user_id,
                cash=INITIAL_CAPITAL,
                initial_capital=INITIAL_CAPITAL,
            )
            session.add(portfolio)
            await session.flush()

        multiplier = _position_multiplier(symbol)
        trade_value = current_price * qty * multiplier

        pos_result = await session.execute(
            select(PaperPosition).where(
                PaperPosition.portfolio_id == portfolio.id,
                PaperPosition.symbol == symbol,
            )
        )
        position = pos_result.scalar_one_or_none()

        if side == "BUY":
            if trade_value > portfolio.cash:
                raise HTTPException(
                    status_code=400,
                    detail=f"Insufficient cash. Need ${trade_value:,.2f}, have ${portfolio.cash:,.2f}",
                )

            portfolio.cash -= trade_value

            if position and position.quantity < 0:
                held_short = abs(position.quantity)
                if held_short < qty:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Insufficient short position. Want to buy {qty}, short {held_short}",
                    )

                avg_credit = position.avg_entry_price
                pnl = (avg_credit - current_price) * qty * multiplier
                position.quantity += qty
                if abs(position.quantity) <= 0.0001:
                    await session.delete(position)
                else:
                    position.current_price = current_price
                    position.unrealized_pnl = _position_unrealized_pnl(
                        symbol,
                        position.avg_entry_price,
                        current_price,
                        position.quantity,
                    )

                trade = PaperTrade(
                    portfolio_id=portfolio.id,
                    user_id=user_id,
                    symbol=symbol,
                    direction=TradeDirection.LONG,
                    quantity=qty,
                    entry_price=avg_credit,
                    exit_price=current_price,
                    pnl=pnl,
                    status=PaperTradeStatus.CLOSED,
                    exit_time=datetime.utcnow(),
                )
                session.add(trade)

                await session.flush()
                await session.refresh(trade)
                return {
                    "executed": True,
                    "id": trade.id,
                    "symbol": symbol,
                    "direction": "BUY",
                    "quantity": qty,
                    "price": current_price,
                    "timestamp": trade.exit_time.isoformat() if trade.exit_time else datetime.utcnow().isoformat(),
                    "pnl": pnl,
                    "cost": trade_value,
                    "remaining_cash": portfolio.cash,
                }

            if position and position.quantity > 0:
                total_cost = (position.avg_entry_price * position.quantity) + (current_price * qty)
                position.quantity += qty
                position.avg_entry_price = total_cost / position.quantity
                position.current_price = current_price
                position.unrealized_pnl = _position_unrealized_pnl(
                    symbol,
                    position.avg_entry_price,
                    current_price,
                    position.quantity,
                )
            else:
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

            await session.flush()
            await session.refresh(trade)
            return {
                "executed": True,
                "id": trade.id,
                "symbol": symbol,
                "direction": "BUY",
                "quantity": qty,
                "price": current_price,
                "timestamp": trade.entry_time.isoformat() if trade.entry_time else datetime.utcnow().isoformat(),
                "pnl": None,
                "cost": trade_value,
                "remaining_cash": portfolio.cash,
            }

        else:  # SELL
            if position and position.quantity > 0:
                if position.quantity < qty:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Insufficient shares. Want to sell {qty}, hold {position.quantity}",
                    )

                avg_cost = position.avg_entry_price
                pnl = (current_price - avg_cost) * qty * multiplier
                portfolio.cash += trade_value
                position.quantity -= qty
                if abs(position.quantity) <= 0.0001:
                    await session.delete(position)
                else:
                    position.current_price = current_price
                    position.unrealized_pnl = _position_unrealized_pnl(
                        symbol,
                        position.avg_entry_price,
                        current_price,
                        position.quantity,
                    )

                trade = PaperTrade(
                    portfolio_id=portfolio.id,
                    user_id=user_id,
                    symbol=symbol,
                    direction=TradeDirection.SHORT,
                    quantity=qty,
                    entry_price=avg_cost,
                    exit_price=current_price,
                    pnl=pnl,
                    status=PaperTradeStatus.CLOSED,
                    exit_time=datetime.utcnow(),
                )
                session.add(trade)

                await session.flush()
                await session.refresh(trade)
                return {
                    "executed": True,
                    "id": trade.id,
                    "symbol": symbol,
                    "direction": "SELL",
                    "quantity": qty,
                    "price": current_price,
                    "timestamp": trade.exit_time.isoformat() if trade.exit_time else datetime.utcnow().isoformat(),
                    "pnl": pnl,
                    "proceeds": trade_value,
                    "remaining_cash": portfolio.cash,
                }

            portfolio.cash += trade_value

            if position and position.quantity < 0:
                total_credit = (position.avg_entry_price * abs(position.quantity)) + (current_price * qty)
                new_short_qty = abs(position.quantity) + qty
                position.quantity = -new_short_qty
                position.avg_entry_price = total_credit / new_short_qty
                position.current_price = current_price
                position.unrealized_pnl = _position_unrealized_pnl(
                    symbol,
                    position.avg_entry_price,
                    current_price,
                    position.quantity,
                )
            else:
                position = PaperPosition(
                    portfolio_id=portfolio.id,
                    user_id=user_id,
                    symbol=symbol,
                    quantity=-qty,
                    avg_entry_price=current_price,
                    current_price=current_price,
                    unrealized_pnl=0.0,
                )
                session.add(position)

            trade = PaperTrade(
                portfolio_id=portfolio.id,
                user_id=user_id,
                symbol=symbol,
                direction=TradeDirection.SHORT,
                quantity=qty,
                entry_price=current_price,
                status=PaperTradeStatus.OPEN,
            )
            session.add(trade)

            await session.flush()
            await session.refresh(trade)
            return {
                "executed": True,
                "id": trade.id,
                "symbol": symbol,
                "direction": "SELL",
                "quantity": qty,
                "price": current_price,
                "timestamp": trade.entry_time.isoformat() if trade.entry_time else datetime.utcnow().isoformat(),
                "pnl": None,
                "proceeds": trade_value,
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
            contract_meta = parse_occ_contract_symbol(p.symbol)
            try:
                if contract_meta:
                    snapshot = await fetch_option_snapshot(
                        underlying=contract_meta["underlying"],
                        expiration=contract_meta["expiration"],
                        strike=float(contract_meta["strike"]),
                        option_type=contract_meta["option_type"],
                        contract_symbol=p.symbol,
                    )
                    current = _option_mark(snapshot or {})
                    if current is None:
                        raise ValueError("option mark unavailable")
                else:
                    current = await _fetch_current_price(p.symbol)
                p.current_price = current
                p.unrealized_pnl = _position_unrealized_pnl(
                    p.symbol,
                    p.avg_entry_price,
                    current,
                    p.quantity,
                )
            except Exception as exc:
                # Keep stale price if refresh fails, but log for visibility
                logger.debug("paper_position_price_refresh_failed", symbol=p.symbol, error=str(exc))

            current_price = p.current_price or p.avg_entry_price
            payload = {
                "symbol": contract_meta["underlying"] if contract_meta else p.symbol,
                "quantity": p.quantity,
                "avg_entry_price": p.avg_entry_price,
                "current_price": current_price,
                "market_value": _position_market_value(p.symbol, current_price, p.quantity),
                "unrealized_pnl": p.unrealized_pnl or 0.0,
                "unrealized_pnl_pct": _position_unrealized_pnl_pct(
                    p.symbol,
                    p.avg_entry_price,
                    current_price,
                    p.quantity,
                ),
                "side": "short" if p.quantity < 0 else "long",
            }

            if contract_meta:
                payload.update(
                    {
                        "asset_type": "option",
                        "contract_symbol": p.symbol,
                        "underlying": contract_meta["underlying"],
                        "expiration": contract_meta["expiration"],
                        "strike": contract_meta["strike"],
                        "option_type": contract_meta["option_type"],
                        "avg_premium": p.avg_entry_price,
                        "current_mark": current_price,
                    }
                )
            else:
                payload["asset_type"] = "stock"

            position_list.append(payload)

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
    initial_capital = req.initial_capital if req else INITIAL_CAPITAL

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
