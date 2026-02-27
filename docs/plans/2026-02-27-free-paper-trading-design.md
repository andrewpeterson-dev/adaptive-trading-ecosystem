# Free Market Data + Paper Trading Engine Design

**Date:** 2026-02-27
**Status:** Approved

## Problem

Users who sign up don't have broker API keys yet. They see synthetic data or nothing. We need real market data and a working paper trading experience from the moment they log in — zero setup, zero API keys.

## Solution

Use **yfinance** for free real market data (stocks, ETFs, crypto) and a **built-in paper trading engine** that tracks virtual portfolios per user in PostgreSQL.

## Key Decisions

- Starting capital: **$1,000,000** virtual cash per user
- Market data: yfinance (real prices, ~15min delay for free tier)
- Crypto support: Yes — yfinance supports BTC-USD, ETH-USD, etc.
- Paper portfolio persists across sessions
- When user connects real broker, dashboard switches to live mode
- Paper portfolio stays available as sandbox even after connecting real broker

## Database Models

### PaperPortfolio

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER | PK |
| user_id | INTEGER | FK -> users, unique |
| cash | FLOAT | Current cash balance |
| initial_capital | FLOAT | Default $1,000,000 |
| created_at | TIMESTAMP | Auto |

### PaperTrade

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER | PK |
| user_id | INTEGER | FK -> users |
| symbol | VARCHAR(16) | e.g. SPY, BTC-USD |
| direction | ENUM | LONG, SHORT |
| quantity | FLOAT | |
| entry_price | FLOAT | Price at open |
| exit_price | FLOAT | Price at close, nullable |
| pnl | FLOAT | Realized PnL, nullable |
| status | ENUM | OPEN, CLOSED |
| entry_time | TIMESTAMP | Auto |
| exit_time | TIMESTAMP | Nullable |

### PaperPosition

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER | PK |
| user_id | INTEGER | FK -> users |
| symbol | VARCHAR(16) | |
| quantity | FLOAT | |
| avg_entry_price | FLOAT | |
| current_price | FLOAT | Last updated price |
| unrealized_pnl | FLOAT | |
| updated_at | TIMESTAMP | Auto |

## New Files

| File | Purpose |
|------|---------|
| dashboard/market_data.py | yfinance wrapper: quotes, bars, watchlist, crypto |
| dashboard/paper_engine.py | Paper trading engine: buy/sell/close, portfolio CRUD |
| db/models.py (edit) | Add PaperPortfolio, PaperTrade, PaperPosition |
| dashboard/app.py (edit) | Auto-detect no broker -> paper mode + yfinance |
| requirements.txt (edit) | Add yfinance |

## Dashboard Behavior

- Sidebar shows "Paper Mode ($1M)" badge when no broker connected
- Sidebar shows "Live Mode" when real broker connected
- Watchlist uses yfinance for any symbol (stocks, ETFs, crypto)
- Trade panel: Buy/Sell with quantity input, executes at current yfinance price
- Portfolio: cash, positions, unrealized PnL, total equity
- Auto-creates PaperPortfolio on first login if none exists
