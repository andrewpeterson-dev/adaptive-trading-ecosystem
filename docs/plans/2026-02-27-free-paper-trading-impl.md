# Free Paper Trading Engine Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Give every user free real market data (yfinance) and a paper trading engine ($1M virtual capital) that works instantly on login with zero API keys.

**Architecture:** yfinance provides real market prices (stocks, ETFs, crypto). A built-in paper trading engine stores virtual portfolios, positions, and trades per user in PostgreSQL. The dashboard auto-detects whether a user has broker credentials — if not, it uses paper mode with yfinance data.

**Tech Stack:** yfinance, SQLAlchemy 2.0 (sync), PostgreSQL, Streamlit

**Design doc:** `docs/plans/2026-02-27-free-paper-trading-design.md`

---

### Task 1: Add yfinance Dependency

**Files:**
- Modify: `requirements.txt`

**Step 1: Add yfinance to requirements.txt**

After the `# Dashboard` section (after `plotly==5.18.0`), add:

```
# Free Market Data
yfinance>=0.2.36
```

**Step 2: Install**

Run: `cd /Users/andrewpeterson/adaptive-trading-ecosystem && pip install yfinance`

**Step 3: Commit**

```bash
cd /Users/andrewpeterson/adaptive-trading-ecosystem
git add requirements.txt
git commit -m "feat: add yfinance for free real market data"
```

---

### Task 2: Add Paper Trading Database Models

**Files:**
- Modify: `db/models.py` (append after BrokerCredential class, line 260)

**Step 1: Add PaperTradeStatus enum and 3 new models**

Add after the `BrokerCredential` class at the end of `db/models.py`:

```python
class PaperTradeStatus(str, enum.Enum):
    OPEN = "open"
    CLOSED = "closed"


class PaperPortfolio(Base):
    __tablename__ = "paper_portfolios"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    cash = Column(Float, nullable=False, default=1_000_000.0)
    initial_capital = Column(Float, nullable=False, default=1_000_000.0)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")
    positions = relationship("PaperPosition", back_populates="portfolio", cascade="all, delete-orphan")
    trades = relationship("PaperTrade", back_populates="portfolio", cascade="all, delete-orphan")


class PaperPosition(Base):
    __tablename__ = "paper_positions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    portfolio_id = Column(Integer, ForeignKey("paper_portfolios.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    symbol = Column(String(16), nullable=False)
    quantity = Column(Float, nullable=False)
    avg_entry_price = Column(Float, nullable=False)
    current_price = Column(Float, nullable=True)
    unrealized_pnl = Column(Float, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    portfolio = relationship("PaperPortfolio", back_populates="positions")

    __table_args__ = (
        Index("ix_paper_pos_user_symbol", "user_id", "symbol", unique=True),
    )


class PaperTrade(Base):
    __tablename__ = "paper_trades"

    id = Column(Integer, primary_key=True, autoincrement=True)
    portfolio_id = Column(Integer, ForeignKey("paper_portfolios.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    symbol = Column(String(16), nullable=False)
    direction = Column(Enum(TradeDirection), nullable=False)
    quantity = Column(Float, nullable=False)
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float, nullable=True)
    pnl = Column(Float, nullable=True)
    status = Column(Enum(PaperTradeStatus), default=PaperTradeStatus.OPEN)
    entry_time = Column(DateTime, default=datetime.utcnow)
    exit_time = Column(DateTime, nullable=True)

    portfolio = relationship("PaperPortfolio", back_populates="trades")

    __table_args__ = (
        Index("ix_paper_trade_user", "user_id"),
    )
```

**Step 2: Commit**

```bash
cd /Users/andrewpeterson/adaptive-trading-ecosystem
git add db/models.py
git commit -m "feat: add PaperPortfolio, PaperPosition, PaperTrade models"
```

---

### Task 3: Create yfinance Market Data Wrapper

**Files:**
- Create: `dashboard/market_data.py`

**Step 1: Create the market data module**

```python
"""
Free market data via yfinance.
Provides real quotes, historical bars, and watchlist data.
No API keys required.
"""

import yfinance as yf
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta


@st.cache_data(ttl=30)
def get_quote(symbol: str) -> dict | None:
    """Get current quote for a symbol. Returns dict or None on error."""
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.fast_info
        return {
            "symbol": symbol.upper(),
            "price": info.get("lastPrice", info.get("previousClose", 0)),
            "previous_close": info.get("previousClose", 0),
            "open": info.get("open", 0),
            "day_high": info.get("dayHigh", 0),
            "day_low": info.get("dayLow", 0),
            "volume": info.get("lastVolume", 0),
            "market_cap": info.get("marketCap", 0),
        }
    except Exception:
        return None


@st.cache_data(ttl=30)
def get_watchlist_quotes(symbols: list[str]) -> pd.DataFrame:
    """Get quotes for multiple symbols. Returns DataFrame."""
    rows = []
    for sym in symbols:
        q = get_quote(sym)
        if q:
            price = q["price"]
            prev = q["previous_close"]
            change = price - prev if prev else 0
            change_pct = (change / prev * 100) if prev else 0
            rows.append({
                "Symbol": sym.upper(),
                "Price": price,
                "Change": change,
                "Change %": change_pct,
                "Volume": q["volume"],
                "Day High": q["day_high"],
                "Day Low": q["day_low"],
            })
    return pd.DataFrame(rows) if rows else pd.DataFrame()


@st.cache_data(ttl=60)
def get_historical_bars(symbol: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
    """
    Get historical OHLCV bars.
    period: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, max
    interval: 1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo
    """
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period, interval=interval)
        if df.empty:
            return pd.DataFrame()
        df = df.reset_index()
        df.columns = [c.lower().replace(" ", "_") for c in df.columns]
        # Standardize column names
        rename_map = {"date": "timestamp", "datetime": "timestamp"}
        df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
        df["symbol"] = symbol.upper()
        return df[["timestamp", "symbol", "open", "high", "low", "close", "volume"]]
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=30)
def get_current_price(symbol: str) -> float:
    """Get just the current price for a symbol. Returns 0.0 on error."""
    q = get_quote(symbol)
    return q["price"] if q else 0.0


# Default watchlist with stocks + crypto
DEFAULT_WATCHLIST = [
    "SPY", "QQQ", "AAPL", "TSLA", "NVDA", "MSFT", "AMZN", "META",
    "BTC-USD", "ETH-USD", "SOL-USD",
]
```

**Step 2: Commit**

```bash
cd /Users/andrewpeterson/adaptive-trading-ecosystem
git add dashboard/market_data.py
git commit -m "feat: add yfinance market data wrapper with quotes, bars, crypto support"
```

---

### Task 4: Create Paper Trading Engine

**Files:**
- Create: `dashboard/paper_engine.py`

**Step 1: Create the paper trading engine**

```python
"""
Built-in paper trading engine.
Tracks virtual portfolios, positions, and trades per user in PostgreSQL.
Uses real market prices from yfinance.
"""

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
```

**Step 2: Commit**

```bash
cd /Users/andrewpeterson/adaptive-trading-ecosystem
git add dashboard/paper_engine.py
git commit -m "feat: add paper trading engine with buy/sell, portfolio tracking, trade history"
```

---

### Task 5: Integrate Paper Mode into Dashboard

This is the critical integration task. The dashboard sidebar gets a "Paper Trading" panel, and a new "Paper Trading" tab is added.

**Files:**
- Modify: `dashboard/app.py`

**Step 1: Add imports**

After the existing auth imports (around line 23-29), add:

```python
try:
    from dashboard.market_data import get_watchlist_quotes, get_historical_bars, get_current_price, DEFAULT_WATCHLIST
    from dashboard.paper_engine import get_portfolio_summary, execute_buy, execute_sell, get_trade_history, get_or_create_portfolio
    _has_paper = True
except ImportError:
    _has_paper = False
```

**Step 2: Add paper mode detection to sidebar**

After the logout button / divider in the sidebar (around line 501), add a paper mode indicator. Find the `data_source` radio section and add BEFORE it:

```python
# Paper mode detection
_user_id = st.session_state.get("user_id")
_has_broker = False
if _has_auth and _has_paper and _user_id:
    from dashboard.auth import get_db as _get_db
    from db.models import BrokerCredential
    from sqlalchemy import select as _select
    _db = _get_db()
    try:
        _has_broker = _db.execute(
            _select(BrokerCredential).where(BrokerCredential.user_id == _user_id).limit(1)
        ).scalar_one_or_none() is not None
    finally:
        _db.close()

    if _has_broker:
        st.sidebar.success("**Live Mode** — Broker connected")
    else:
        st.sidebar.info("**Paper Mode** — $1M virtual portfolio")
        # Auto-create portfolio
        get_or_create_portfolio(_user_id)
```

**Step 3: Add "Paper Trading" tab**

In BOTH tab creation branches (webull and non-webull around lines 692-708), add `"Paper Trading"` to the `_tab_names` list — insert it before "Broker Settings".

For the webull branch (line 693), change the tab names and unpacking to include `tab_paper`.
For the non-webull branch (line 701), same thing.

The unpacking needs to include `tab_paper` in the right position.

**Step 4: Add Paper Trading tab content**

After the existing `tab_trades` with-block and before the `tab_broker` with-block (around line 2290), add:

```python
# ═══════════════════════════════════════════════════════════════════════════
# TAB: PAPER TRADING
# ═══════════════════════════════════════════════════════════════════════════

with tab_paper:
    if not _has_paper:
        st.info("Paper trading requires yfinance. Install with: pip install yfinance")
    elif not _user_id:
        st.info("Please log in to use paper trading.")
    else:
        st.subheader("Paper Trading Console")

        # Portfolio summary
        summary = get_portfolio_summary(_user_id)

        col_cash, col_positions, col_equity, col_pnl = st.columns(4)
        col_cash.metric("Cash", f"${summary['cash']:,.2f}")
        col_positions.metric("Positions Value", f"${summary['positions_value']:,.2f}")
        col_equity.metric("Total Equity", f"${summary['total_equity']:,.2f}")
        pnl_delta = f"{summary['total_pnl_pct']:+.2f}%"
        col_pnl.metric("Total P&L", f"${summary['total_pnl']:+,.2f}", delta=pnl_delta)

        st.markdown("---")

        # Trade execution
        col_trade, col_watchlist = st.columns([1, 2])

        with col_trade:
            st.markdown("#### Place Trade")
            with st.form("paper_trade_form"):
                trade_symbol = st.text_input("Symbol", value="SPY", placeholder="SPY, AAPL, BTC-USD")
                trade_qty = st.number_input("Quantity", min_value=0.01, value=10.0, step=1.0)
                col_buy, col_sell = st.columns(2)
                buy_btn = col_buy.form_submit_button("Buy", use_container_width=True)
                sell_btn = col_sell.form_submit_button("Sell", use_container_width=True)

                if buy_btn:
                    ok, msg = execute_buy(_user_id, trade_symbol, trade_qty)
                    if ok:
                        st.success(msg)
                    else:
                        st.error(msg)
                    st.rerun()
                elif sell_btn:
                    ok, msg = execute_sell(_user_id, trade_symbol, trade_qty)
                    if ok:
                        st.success(msg)
                    else:
                        st.error(msg)
                    st.rerun()

            # Current price preview
            if trade_symbol:
                live_price = get_current_price(trade_symbol)
                if live_price > 0:
                    st.markdown(f"**{trade_symbol.upper()}** current price: **${live_price:,.2f}**")
                    st.markdown(f"Estimated cost: **${live_price * trade_qty:,.2f}**")

        with col_watchlist:
            st.markdown("#### Live Watchlist")
            watchlist_input = st.text_input(
                "Symbols (comma-separated)",
                value=", ".join(DEFAULT_WATCHLIST),
                key="paper_watchlist_symbols",
            )
            symbols = [s.strip().upper() for s in watchlist_input.split(",") if s.strip()]

            if st.button("Refresh", key="refresh_paper_watchlist"):
                st.cache_data.clear()

            quotes_df = get_watchlist_quotes(symbols)
            if not quotes_df.empty:
                st.dataframe(quotes_df, use_container_width=True, hide_index=True, height=400)
            else:
                st.info("No quotes available.")

        # Open positions
        st.markdown("---")
        st.markdown("#### Open Positions")
        if summary["positions"]:
            import pandas as _pd
            pos_df = _pd.DataFrame(summary["positions"])
            pos_df = pos_df[["symbol", "quantity", "avg_entry_price", "current_price", "unrealized_pnl", "market_value"]]
            pos_df.columns = ["Symbol", "Qty", "Avg Entry", "Current", "Unrealized P&L", "Market Value"]
            st.dataframe(pos_df, use_container_width=True, hide_index=True)
        else:
            st.info("No open positions. Place a trade above.")

        # Trade history
        st.markdown("---")
        st.markdown("#### Trade History")
        trades = get_trade_history(_user_id)
        if trades:
            import pandas as _pd2
            trades_df = _pd2.DataFrame(trades)
            st.dataframe(trades_df, use_container_width=True, hide_index=True, height=300)
        else:
            st.info("No trades yet.")
```

**Step 5: Commit**

```bash
cd /Users/andrewpeterson/adaptive-trading-ecosystem
git add dashboard/app.py
git commit -m "feat: integrate paper trading tab with live watchlist, trade execution, and portfolio view"
```

---

### Task 6: Update DB Init Script

**Files:**
- Modify: `scripts/create_admin.py`

**Step 1: Add paper model imports**

In `scripts/create_admin.py`, update the model imports line to also register the new paper models:

Change:
```python
from db.models import User, EmailVerification, BrokerCredential  # noqa: F401 — registers models
```
To:
```python
from db.models import User, EmailVerification, BrokerCredential, PaperPortfolio, PaperPosition, PaperTrade  # noqa: F401
```

**Step 2: Commit**

```bash
cd /Users/andrewpeterson/adaptive-trading-ecosystem
git add scripts/create_admin.py
git commit -m "feat: register paper trading models in DB init script"
```

---

### Task 7: Write Tests

**Files:**
- Create: `tests/test_market_data.py`
- Create: `tests/test_paper_engine.py`

**Step 1: Create tests/test_market_data.py**

```python
"""Tests for yfinance market data wrapper."""

import pytest
from unittest.mock import patch, MagicMock


def test_default_watchlist_includes_crypto():
    from dashboard.market_data import DEFAULT_WATCHLIST
    assert "BTC-USD" in DEFAULT_WATCHLIST
    assert "ETH-USD" in DEFAULT_WATCHLIST


def test_default_watchlist_includes_stocks():
    from dashboard.market_data import DEFAULT_WATCHLIST
    assert "SPY" in DEFAULT_WATCHLIST
    assert "AAPL" in DEFAULT_WATCHLIST
```

**Step 2: Create tests/test_paper_engine.py**

```python
"""Tests for paper trading engine constants."""

import pytest


def test_initial_capital_is_one_million():
    from dashboard.paper_engine import INITIAL_CAPITAL
    assert INITIAL_CAPITAL == 1_000_000.0
```

**Step 3: Run tests**

Run: `cd /Users/andrewpeterson/adaptive-trading-ecosystem && python -m pytest tests/test_market_data.py tests/test_paper_engine.py -v`

**Step 4: Commit**

```bash
cd /Users/andrewpeterson/adaptive-trading-ecosystem
git add tests/test_market_data.py tests/test_paper_engine.py
git commit -m "test: add market data and paper engine tests"
```
