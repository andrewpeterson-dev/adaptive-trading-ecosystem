# Trading Terminal UI Redesign

## Overview
Transform the bot detail dashboard from a basic info page into a professional institutional trading terminal with draggable panels, professional charts, AI decision transparency, and institutional risk metrics.

## Phases (Priority Order)

### Phase 1: Dashboard Layout (react-grid-layout)
- Modular panel components: ChartPanel, AIReasoningPanel, RiskMetricsPanel, PerformanceMetricsPanel, TradeLogPanel, OpenPositionsPanel, MarketScannerPanel
- Draggable/resizable grid with "Unlock Layout" toggle
- Persist layout to localStorage

### Phase 2: Chart Upgrade
- Already using TradingView Lightweight Charts — enhance with multi-panel (candles + RSI + volume)
- AI signal markers with hover tooltips (BUY/SELL, confidence, reason)
- Timeframe switcher already exists — ensure all work

### Phase 3: AI Reasoning Panel
- Structured decision engine: signal trigger, validation checks, confidence score
- Color coded: green=confirmed, yellow=caution, red=risk
- AI decision timeline (chronological events)

### Phase 4: Performance Metrics
- Already partially implemented — add: Profit Factor, Avg Win/Loss, Strategy Expectancy, Sortino Ratio, Trades Today
- Conditional display (Sharpe only with 30+ trades)

### Phase 5: Market Context Panel
- SPY trend, VIX level, market sentiment, upcoming events
- Data from existing bot_engine indicators + reasoning engine events

### Phase 6: AI Market Scanner
- Symbols being analyzed, signal strength, strategy match
- Pull from bot evaluation logs

### Phase 7: Trade Inspector Modal
- Click-to-inspect trade detail with entry/exit conditions, AI confidence, P&L
- Already partially exists in TradeMarkerOverlay — expand to modal

### Phase 8: Theme System
- Dark theme (current) + Light theme
- Already have useThemeMode hook — extend with custom trading terminal colors

### Phase 9: Multi-Panel Charts
- Separate candle, RSI, volume panels
- Toggle individual indicator panels

### Phase 10: UX Polish
- Rename: Manual→AI Assisted, Assets→Universe, Recent Trades→Trade Log
- Improved spacing, typography, hover animations

### Phase 11: Code Cleanup
- Consistent naming, modular components, no duplication

## Implementation Strategy
Build Phase 1 (layout system) first since everything else plugs into it. Then Phases 2-4 (highest visual impact). Phases 5-11 layer on top.

## Files Affected
- `frontend/src/app/bots/[id]/page.tsx` — main page restructure
- `frontend/src/components/bots/*` — all bot components
- New: `frontend/src/components/terminal/*` — new terminal panel components
- New: `frontend/src/hooks/useGridLayout.ts` — layout persistence
- `frontend/src/components/charts/TradingChart.tsx` — chart enhancements
