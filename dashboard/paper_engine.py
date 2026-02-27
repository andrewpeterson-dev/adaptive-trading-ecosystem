"""
Built-in paper trading engine.
Tracks virtual portfolios, positions, and trades per user in PostgreSQL.
Uses real market prices from yfinance.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select, update

from dashboard.auth import get_db
from dashboard.market_data import get_current_price
from db.models import (
    PaperPortfolio,
    PaperPosition,
    PaperTrade,
    PaperTradeStatus,
    TradeDirection,
)

INITIAL_CAPITAL = 1_000_000.0


def get_or_create_portfolio(user_id: int) -> dict:
    """Get user's paper portfolio, creating one if it doesn't exist."""
    db = get_db()
    try:
        portfolio = db.execute(
            select(PaperPortfolio).where(PaperPortfolio.user_id == user_id)
        ).scalar_one_or_none()

        if not portfolio:
            portfolio = PaperPortfolio(
                user_id=user_id,
                cash=INITIAL_CAPITAL,
                initial_capital=INITIAL_CAPITAL,
            )
            db.add(portfolio)
            db.commit()
            db.refresh(portfolio)

        return {
            "id": portfolio.id,
            "cash": portfolio.cash,
            "initial_capital": portfolio.initial_capital,
            "created_at": portfolio.created_at,
        }
    finally:
        db.close()


def get_positions(user_id: int) -> list[dict]:
    """Get all open positions for a user with updated prices."""
    db = get_db()
    try:
        positions = db.execute(
            select(PaperPosition).where(PaperPosition.user_id == user_id)
        ).scalars().all()

        result = []
        for pos in positions:
            current_price = get_current_price(pos.symbol)
            unrealized = (current_price - pos.avg_entry_price) * pos.quantity

            # Update stored price
            pos.current_price = current_price
            pos.unrealized_pnl = unrealized
            db.commit()

            result.append({
                "id": pos.id,
                "symbol": pos.symbol,
                "quantity": pos.quantity,
                "avg_entry_price": pos.avg_entry_price,
                "current_price": current_price,
                "unrealized_pnl": unrealized,
                "market_value": current_price * pos.quantity,
            })
        return result
    finally:
        db.close()


def get_portfolio_summary(user_id: int) -> dict:
    """Get full portfolio summary: cash, positions, total equity."""
    portfolio = get_or_create_portfolio(user_id)
    positions = get_positions(user_id)

    positions_value = sum(p["market_value"] for p in positions)
    total_equity = portfolio["cash"] + positions_value
    total_pnl = total_equity - portfolio["initial_capital"]
    total_pnl_pct = (total_pnl / portfolio["initial_capital"]) * 100

    return {
        "cash": portfolio["cash"],
        "positions_value": positions_value,
        "total_equity": total_equity,
        "total_pnl": total_pnl,
        "total_pnl_pct": total_pnl_pct,
        "initial_capital": portfolio["initial_capital"],
        "num_positions": len(positions),
        "positions": positions,
    }


def execute_buy(user_id: int, symbol: str, quantity: float) -> tuple[bool, str]:
    """
    Buy shares of a symbol at current market price.
    Returns (success, message).
    """
    if quantity <= 0:
        return False, "Quantity must be positive."

    price = get_current_price(symbol)
    if price <= 0:
        return False, f"Could not get price for {symbol}."

    cost = price * quantity

    db = get_db()
    try:
        portfolio = db.execute(
            select(PaperPortfolio).where(PaperPortfolio.user_id == user_id)
        ).scalar_one_or_none()

        if not portfolio:
            portfolio = PaperPortfolio(
                user_id=user_id, cash=INITIAL_CAPITAL, initial_capital=INITIAL_CAPITAL
            )
            db.add(portfolio)
            db.flush()

        if cost > portfolio.cash:
            return False, f"Insufficient cash. Need ${cost:,.2f}, have ${portfolio.cash:,.2f}."

        # Deduct cash
        portfolio.cash -= cost

        # Update or create position
        position = db.execute(
            select(PaperPosition).where(
                PaperPosition.user_id == user_id,
                PaperPosition.symbol == symbol.upper(),
            )
        ).scalar_one_or_none()

        if position:
            # Average in
            total_qty = position.quantity + quantity
            position.avg_entry_price = (
                (position.avg_entry_price * position.quantity) + (price * quantity)
            ) / total_qty
            position.quantity = total_qty
            position.current_price = price
        else:
            position = PaperPosition(
                portfolio_id=portfolio.id,
                user_id=user_id,
                symbol=symbol.upper(),
                quantity=quantity,
                avg_entry_price=price,
                current_price=price,
            )
            db.add(position)

        # Record trade
        trade = PaperTrade(
            portfolio_id=portfolio.id,
            user_id=user_id,
            symbol=symbol.upper(),
            direction=TradeDirection.LONG,
            quantity=quantity,
            entry_price=price,
            status=PaperTradeStatus.OPEN,
        )
        db.add(trade)
        db.commit()

        return True, f"Bought {quantity} {symbol.upper()} @ ${price:,.2f} (${cost:,.2f})"
    except Exception as e:
        db.rollback()
        return False, f"Trade failed: {str(e)}"
    finally:
        db.close()


def execute_sell(user_id: int, symbol: str, quantity: float) -> tuple[bool, str]:
    """
    Sell shares of a symbol at current market price.
    Returns (success, message).
    """
    if quantity <= 0:
        return False, "Quantity must be positive."

    price = get_current_price(symbol)
    if price <= 0:
        return False, f"Could not get price for {symbol}."

    db = get_db()
    try:
        portfolio = db.execute(
            select(PaperPortfolio).where(PaperPortfolio.user_id == user_id)
        ).scalar_one_or_none()

        if not portfolio:
            return False, "No portfolio found."

        position = db.execute(
            select(PaperPosition).where(
                PaperPosition.user_id == user_id,
                PaperPosition.symbol == symbol.upper(),
            )
        ).scalar_one_or_none()

        if not position or position.quantity < quantity:
            available = position.quantity if position else 0
            return False, f"Insufficient shares. Have {available}, trying to sell {quantity}."

        # Calculate PnL
        pnl = (price - position.avg_entry_price) * quantity
        proceeds = price * quantity

        # Credit cash
        portfolio.cash += proceeds

        # Update position
        position.quantity -= quantity
        if position.quantity <= 0:
            db.delete(position)

        # Record trade
        trade = PaperTrade(
            portfolio_id=portfolio.id,
            user_id=user_id,
            symbol=symbol.upper(),
            direction=TradeDirection.SHORT,
            quantity=quantity,
            entry_price=position.avg_entry_price,
            exit_price=price,
            pnl=pnl,
            status=PaperTradeStatus.CLOSED,
            exit_time=datetime.utcnow(),
        )
        db.add(trade)
        db.commit()

        return True, f"Sold {quantity} {symbol.upper()} @ ${price:,.2f} (PnL: ${pnl:+,.2f})"
    except Exception as e:
        db.rollback()
        return False, f"Trade failed: {str(e)}"
    finally:
        db.close()


def get_trade_history(user_id: int, limit: int = 50) -> list[dict]:
    """Get recent trade history for a user."""
    db = get_db()
    try:
        trades = db.execute(
            select(PaperTrade)
            .where(PaperTrade.user_id == user_id)
            .order_by(PaperTrade.entry_time.desc())
            .limit(limit)
        ).scalars().all()

        return [
            {
                "symbol": t.symbol,
                "direction": t.direction.value,
                "quantity": t.quantity,
                "entry_price": t.entry_price,
                "exit_price": t.exit_price,
                "pnl": t.pnl,
                "status": t.status.value,
                "entry_time": t.entry_time,
                "exit_time": t.exit_time,
            }
            for t in trades
        ]
    finally:
        db.close()
