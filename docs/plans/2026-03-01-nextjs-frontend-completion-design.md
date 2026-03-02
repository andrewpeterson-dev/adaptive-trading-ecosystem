# Next.js Frontend Completion Design

## Goal
Replace Streamlit dashboard entirely with a production-grade Next.js frontend. All features ported with live data, auth flows, and polished UI.

## Current State
- 5 pages exist: Home (Strategy Builder), Strategies List, Dashboard, Portfolio, Backtest
- Strategy Builder is the most complete (549 LOC) with full API integration
- All backend endpoints are connected via Next.js rewrites to localhost:8000
- Dark mode with Tailwind + Radix UI, Recharts for charts
- No auth, no API client layer, no real-time updates

## Team Structure (4 agents in isolated worktrees)

### Agent 1: foundation
**Scope:** API client layer, auth system, shared UI primitives
**Files:**
- `frontend/src/lib/api/client.ts` — Centralized fetch wrapper with error handling
- `frontend/src/lib/api/auth.ts` — Auth API methods
- `frontend/src/lib/api/trading.ts` — Trading API methods
- `frontend/src/lib/api/models.ts` — Models/analytics API methods
- `frontend/src/lib/api/strategies.ts` — Strategy API methods
- `frontend/src/app/login/page.tsx` — Login page
- `frontend/src/app/register/page.tsx` — Register page
- `frontend/src/middleware.ts` — Route protection
- `frontend/src/components/ui/toast.tsx` — Toast notification system
- `frontend/src/components/ui/skeleton.tsx` — Loading skeletons
- `frontend/src/components/ui/error-boundary.tsx` — Error boundary
- `frontend/src/hooks/useAuth.ts` — Auth context/hook
- `frontend/src/types/auth.ts` — Auth types

### Agent 2: trading
**Scope:** Paper trading UI, market data, watchlist
**Files:**
- `frontend/src/app/trade/page.tsx` — Paper trading page (buy/sell, positions, history)
- `frontend/src/app/watchlist/page.tsx` — Market data watchlist
- `frontend/src/components/trading/OrderForm.tsx` — Buy/sell order form
- `frontend/src/components/trading/PositionCard.tsx` — Position display card
- `frontend/src/components/trading/TradeHistory.tsx` — Trade history table
- `frontend/src/components/trading/QuoteCard.tsx` — Live quote display
- `frontend/src/components/trading/WatchlistRow.tsx` — Watchlist row item
- `frontend/src/hooks/usePolling.ts` — Data polling hook
- `frontend/src/types/paper-trading.ts` — Paper trading types
- Update NavHeader to add Trade and Watchlist links

### Agent 3: analytics
**Scope:** Enhanced model performance, risk monitoring, portfolio analytics
**Files:**
- `frontend/src/app/models/page.tsx` — Model performance dashboard
- `frontend/src/app/risk/page.tsx` — Risk event monitoring
- `frontend/src/components/analytics/ModelCard.tsx` — Per-model metrics card
- `frontend/src/components/analytics/RegimeIndicator.tsx` — Market regime badge
- `frontend/src/components/analytics/RiskGauge.tsx` — Risk metric gauge
- `frontend/src/components/analytics/RiskEventLog.tsx` — Risk breach log
- `frontend/src/components/analytics/AllocationChart.tsx` — Capital allocation pie
- `frontend/src/types/risk.ts` — Risk event types
- Enhance existing dashboard/page.tsx with regime and risk data
- Enhance existing portfolio/page.tsx with more detailed metrics

### Agent 4: admin
**Scope:** Admin panel, broker settings, user preferences
**Files:**
- `frontend/src/app/admin/page.tsx` — Admin panel (users, stats)
- `frontend/src/app/settings/page.tsx` — User settings
- `frontend/src/app/settings/broker/page.tsx` — Broker credential config
- `frontend/src/components/admin/UserTable.tsx` — User management table
- `frontend/src/components/admin/PlatformStats.tsx` — Platform statistics
- `frontend/src/components/settings/BrokerForm.tsx` — Broker API key form
- `frontend/src/components/settings/PreferencesForm.tsx` — User preferences
- `frontend/src/types/admin.ts` — Admin types

## Technical Decisions
- API client uses centralized fetch wrapper with typed responses
- Auth via JWT stored in httpOnly cookie (backend already supports this)
- Real-time data via polling (60s intervals), not WebSocket (matches orchestrator cycle)
- Existing Tailwind dark theme + Radix UI patterns maintained
- All new pages follow existing component patterns
- Types defined per domain in `types/` directory

## Dependencies
- foundation must complete API client before others can use it (but others can use direct fetch as fallback)
- All agents work in isolated git worktrees
- Merge order: foundation first, then trading/analytics/admin in any order
