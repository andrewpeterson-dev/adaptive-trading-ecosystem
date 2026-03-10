# Trade Tab Overhaul Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the Trade tab from a basic demo into a professional trading interface with symbol-linked charts, stocks/options mode switching, real order tickets, and no fake data.

**Architecture:** Zustand store (`trade-store`) holds shared state (symbol, asset mode, quote, account). All components read from this store. Chart, order ticket, and positions all react to symbol changes. Options mode reveals an options-specific workflow without cluttering the stock flow. All data comes from existing backend APIs — no mock data displayed.

**Tech Stack:** Next.js, React, Zustand, lightweight-charts, Tailwind CSS, existing backend APIs (`/api/trading/*`, `/api/paper-trading/*`)

---

## File Map

### New Files
| File | Responsibility |
|------|---------------|
| `frontend/src/stores/trade-store.ts` | Shared state: symbol, assetMode, quote, account, positions, trades |
| `frontend/src/components/trading/SymbolSearch.tsx` | Symbol autocomplete with recent symbols list |
| `frontend/src/components/trading/AssetModeSwitch.tsx` | Stocks/Options segmented control |
| `frontend/src/components/trading/StockOrderTicket.tsx` | Full stock order form (replaces OrderForm) |
| `frontend/src/components/trading/OptionsPanel.tsx` | Options trading workflow (chain + order) |
| `frontend/src/components/trading/PositionsPanel.tsx` | Positions table with close/reduce actions |
| `frontend/src/components/trading/TradeHistoryPanel.tsx` | Trade history table with filters |
| `frontend/src/components/trading/MetricsBar.tsx` | Account summary cards with loading skeletons |
| `frontend/src/components/trading/OrderPreview.tsx` | Pre-submission cost/impact preview |

### Modified Files
| File | Changes |
|------|---------|
| `frontend/src/app/trade/page.tsx` | Complete rewrite using new components + trade store |
| `frontend/src/components/charts/TradingChart.tsx` | Accept symbol from store, add indicator toggles, chart header with price |
| `frontend/src/types/trading.ts` | Add OptionContract, OptionPosition, TradeSource types |

### Preserved Files (no changes)
| File | Reason |
|------|--------|
| `api/routes/trading.py` | Backend APIs already complete |
| `api/routes/paper_trading.py` | Paper trading engine works |
| `api/routes/webull.py` | Broker integration works |
| `data/webull_client.py` | Client works |
| `hooks/useTradingMode.ts` | Mode switching works |
| `hooks/usePriceStream.ts` | WebSocket hook available |

---

## Chunk 1: Foundation (Store + Types + Layout)

### Task 1: Create trade store

**Files:**
- Create: `frontend/src/stores/trade-store.ts`

- [ ] **Step 1: Create Zustand store with shared trade state**

```typescript
// Zustand store managing: symbol, assetMode, quote, account, positions, trades, loading states
// symbol defaults to "SPY", assetMode defaults to "stocks"
// Actions: setSymbol, setAssetMode, setAccount, setPositions, setTrades, fetchAll, fetchQuote
```

- [ ] **Step 2: Verify store imports correctly**

Run: `cd ~/adaptive-trading-ecosystem/frontend && npx tsc --noEmit 2>&1 | grep trade-store || echo "OK"`

### Task 2: Extend trading types

**Files:**
- Modify: `frontend/src/types/trading.ts`

- [ ] **Step 1: Add option and trade source types**

Add: `OptionContract`, `OptionQuote`, `OptionPosition`, `TradeSource` (manual | bot_name), `AssetMode` type

- [ ] **Step 2: Type check**

### Task 3: Create MetricsBar component

**Files:**
- Create: `frontend/src/components/trading/MetricsBar.tsx`

- [ ] **Step 1: Build metrics bar with loading skeletons**

4 cards: Cash, Portfolio Value, Equity, Unrealized P&L. Show skeleton when account is null. Show real data when available. Color-code P&L. Responsive grid.

### Task 4: Create SymbolSearch component

**Files:**
- Create: `frontend/src/components/trading/SymbolSearch.tsx`

- [ ] **Step 1: Build symbol search with recent symbols**

Input that updates trade store symbol on Enter/blur. Store recent symbols in localStorage (max 8). Show dropdown of recent symbols on focus. Debounced search. When symbol changes, triggers quote fetch.

### Task 5: Create AssetModeSwitch component

**Files:**
- Create: `frontend/src/components/trading/AssetModeSwitch.tsx`

- [ ] **Step 1: Build segmented control for Stocks/Options**

Simple two-button toggle that updates `assetMode` in trade store. Stocks is default. Clean animated indicator.

### Task 6: Rewrite trade page layout

**Files:**
- Modify: `frontend/src/app/trade/page.tsx`

- [ ] **Step 1: Rewrite page using trade store and new components**

Layout:
- Top: MetricsBar
- Middle-left (col-span-3): SymbolSearch + Chart (reads symbol from store)
- Middle-right (col-span-2): AssetModeSwitch + OrderTicket (stocks) or OptionsPanel
- Bottom-left: TradeHistoryPanel
- Bottom-right: PositionsPanel

Uses trade store for all shared state. 30s polling via store.fetchAll().

- [ ] **Step 2: Build and verify no type errors**

Run: `cd ~/adaptive-trading-ecosystem/frontend && npm run build 2>&1 | tail -5`

- [ ] **Step 3: Commit**

```
feat: trade tab foundation — store, layout, metrics, symbol search, asset mode switch
```

---

## Chunk 2: Chart Enhancement + Stock Order Ticket

### Task 7: Enhance TradingChart

**Files:**
- Modify: `frontend/src/components/charts/TradingChart.tsx`

- [ ] **Step 1: Make chart read symbol from props (no longer hardcoded)**

Chart already accepts `symbol` prop but page hardcodes "SPY". Now page passes store symbol.

- [ ] **Step 2: Add chart header with live quote data**

Show: symbol, last price, day change $, day change %, all from trade store quote. Update on quote changes.

- [ ] **Step 3: Add indicator toggle buttons**

Toggles: SMA 20, SMA 50, EMA 9, Volume, VWAP. Each toggle shows/hides the overlay. Compute EMA and VWAP in-browser from OHLCV data. Keep existing SMA(20).

- [ ] **Step 4: Add position entry/exit markers and SL/TP lines**

For open positions matching the chart symbol: draw entry price line (dashed green). For SL/TP if they exist: draw horizontal lines. Use `createPriceLine()` from lightweight-charts.

### Task 8: Build StockOrderTicket

**Files:**
- Create: `frontend/src/components/trading/StockOrderTicket.tsx`

- [ ] **Step 1: Build complete stock order form**

Features:
- Buy/Sell toggle (green/red)
- Order type selector: Market, Limit, Stop, Stop-Limit
- Conditional price fields (limit price for Limit, stop price for Stop, both for Stop-Limit)
- Quantity input with +/- buttons
- Estimated order value (qty * current price)
- Current bid/ask/last from trade store quote (only show if data exists)
- Inline validation: invalid symbol, zero qty, missing prices, insufficient buying power
- Submit button: "Buy 10 AAPL" or "Sell 5 NVDA" (specific labels)
- Success/error/pending states
- Calls `/api/trading/execute` with `user_confirmed: true`

### Task 9: Build OrderPreview

**Files:**
- Create: `frontend/src/components/trading/OrderPreview.tsx`

- [ ] **Step 1: Build pre-submission preview**

Shows below order ticket when order is valid but not yet submitted:
- Estimated cost (qty * price)
- Estimated remaining cash (account.cash - cost)
- Position % of portfolio
- Only show when data is available — hide completely if account not loaded

- [ ] **Step 2: Build, verify, commit**

```
feat: enhanced chart with indicators + professional stock order ticket
```

---

## Chunk 3: Positions + Trade History + Bot Visibility

### Task 10: Build PositionsPanel

**Files:**
- Create: `frontend/src/components/trading/PositionsPanel.tsx`

- [ ] **Step 1: Build positions table**

Stock positions show: Symbol, Qty, Avg Entry, Current Price, Market Value, Unrealized P&L ($, %), Side, Source (Manual or Bot name — show if field exists in data, hide if not).

Actions: Close position button (calls execute with reverse direction).

Empty state: compact message with CTA to place a trade.

Loading state: skeleton rows.

### Task 11: Build TradeHistoryPanel

**Files:**
- Create: `frontend/src/components/trading/TradeHistoryPanel.tsx`

- [ ] **Step 1: Build trade history table with filters**

Columns: Date/Time, Symbol, Side, Order Type, Qty, Price, Status, P&L (if closed), Source.

Filters: All, Buys, Sells (simple tab bar).

Newest first. Color-coded P&L. Clickable rows (highlight trade on chart if marker exists).

Loading: skeleton rows. Empty: "No trades yet."

### Task 12: Wire bot execution visibility

- [ ] **Step 1: Add `source` field display**

If trade data includes `bot_name` or `source` field, display it. If not, show "Manual." This is future-proof — when bot trades flow through, they auto-display.

- [ ] **Step 2: Build, verify, commit**

```
feat: positions panel, trade history with filters, bot trade visibility
```

---

## Chunk 4: Options Trading UI

### Task 13: Build OptionsPanel

**Files:**
- Create: `frontend/src/components/trading/OptionsPanel.tsx`

- [ ] **Step 1: Build options trading interface**

Structure:
- Underlying symbol (shared from trade store)
- Expiration date selector (fetch from API if available, else show "Options data not connected" state)
- Strike selector
- Call/Put toggle
- Direction: Buy to Open / Sell to Close
- Contract quantity input
- Premium/Mark/Bid/Ask display (only when data exists)
- Greeks display (only when data exists): delta, gamma, theta, vega, IV
- Contract summary card
- Breakeven calculation
- Submit button

CRITICAL: If no options data API exists, show a clean "Options market data not yet connected" state — never fake data.

- [ ] **Step 2: Wire to chart — show underlying chart in options mode**

When in options mode, chart still shows underlying stock. Add small label "Showing underlying: AAPL" above chart.

- [ ] **Step 3: Build, verify, commit**

```
feat: options trading panel with clean no-data states
```

---

## Chunk 5: Final Polish

### Task 14: Layout and visual density

- [ ] **Step 1: Tighten layout**

- Better horizontal space usage
- Chart takes more width
- Order ticket is compact but complete
- Responsive breakpoints for mobile
- Consistent spacing with rest of app

### Task 15: Loading and error states

- [ ] **Step 1: Add skeletons everywhere**

MetricsBar, Chart, PositionsPanel, TradeHistory all show animated skeleton rows/cards while loading.

- [ ] **Step 2: Ensure no fake data ever appears**

Audit every component: if data is null/undefined/empty, show loading or empty state. Never show "$0.00" as placeholder for real data.

### Task 16: Final build and push

- [ ] **Step 1: Full build**

Run: `cd ~/adaptive-trading-ecosystem/frontend && npm run build`

- [ ] **Step 2: Commit and push**

```
feat: complete trade tab overhaul — professional trading interface

- Symbol-linked chart with indicator toggles
- Stocks/Options mode switch
- Professional order ticket with validation
- Options trading panel (data-ready, no fakes)
- Rebuilt positions and trade history panels
- Loading skeletons, no fake data
- Bot trade source visibility
```

---

## Backend Dependencies (NOT implemented in this plan)

These backend additions are needed for full feature completeness:

1. **Options chain API** (`GET /api/trading/options-chain?symbol=AAPL&expiration=2026-04-17`) — needed for real options data
2. **Options execution** (`POST /api/trading/execute-option`) — needed for options trading
3. **Symbol search API** (`GET /api/trading/symbol-search?q=APP`) — currently symbol search is client-side only
4. **Trade `source` field** — add `source` column to Trade model (values: "manual", bot name)
5. **Options positions** — add option position fields to Position model

The frontend is built to gracefully handle missing APIs — showing clean empty/loading states until backends are connected.
