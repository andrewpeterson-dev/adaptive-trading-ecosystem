# Builder + Strategies Feature Design
**Date:** 2026-03-10
**Approach:** Surgical Enhancement (Approach 1)

---

## Problem Summary

Six gaps in the current Builder and Strategies feature set:

1. Conditions are flat AND-only; no OR grouping, no parameters exposed (partially fixed but not grouped)
2. Remove condition enabled even when 0 active conditions exist
3. Diagnostics and AI Analyze never render — `fetch()` calls omit auth token → 401 → silent failure
4. No universe/symbol selection, exit conditions beyond SL/TP, fees/slippage, or risk controls
5. Backtest only accessible from edit mode; no commission/slippage applied; no drawdown chart
6. Strategies list lacks metadata (timeframe, updated_at, description) and a clone action

---

## Data Model Changes

### New fields added to `Strategy` (DB + backend schema + frontend type)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `condition_groups` | JSON | `[]` | Array of `ConditionGroup` — replaces flat `conditions[]` |
| `symbols` | JSON | `["SPY"]` | Universe of symbols for the strategy |
| `commission_pct` | float | `0.001` | Per-trade commission (0.1%) |
| `slippage_pct` | float | `0.0005` | Per-trade slippage estimate |
| `trailing_stop_pct` | float\|null | `null` | Trailing stop, null = disabled |
| `exit_after_bars` | int\|null | `null` | Time-based exit, null = disabled |
| `cooldown_bars` | int | `0` | Min bars between re-entries |
| `max_trades_per_day` | int | `0` | 0 = unlimited |
| `max_exposure_pct` | float | `1.0` | Max capital fraction per trade |
| `max_loss_pct` | float | `0.0` | Daily loss limit, 0 = no limit |

**Backward compatibility:** Existing strategies with `conditions[]` and no `condition_groups` are migrated on read — the flat array is wrapped into a single group automatically.

### `ConditionGroup` type

```typescript
interface ConditionGroup {
  id: string;
  label?: string;       // auto-assigned: "Group A", "Group B", …
  conditions: StrategyCondition[];
}
```

AND logic within a group. OR logic between groups.

---

## Condition Group Builder (UI)

### `ConditionGroup.tsx` (new component)

Renders a bordered card per group:
- Header: group label chip + `[× Remove group]` button (disabled when only 1 group)
- Body: `ConditionRow` components, with "AND" badge between rows (existing behavior)
- Footer: `+ Add Condition` dashed button

Between groups: an **OR** connector pill (centered, non-interactive label).

Below all groups: `+ Add Group` dashed button.

### Remove-condition logic fix

| State | Remove button |
|-------|---------------|
| 1 group, 1 condition | Disabled (tooltip: "At least one condition required") |
| 1 group, >1 conditions | Enabled |
| >1 groups, any count | Enabled; removing last condition in a group removes the group |

Empty conditions (no indicator selected) are filtered from validation and API calls — they don't count as "active."

### Logic preview string format

```
IF (RSI(14) < 30 AND MACD(12,26,9) > 0)
OR (BB_lower crosses_below close)
THEN BUY
```

---

## Builder Accordion Sections

Four collapsible sections below the condition groups. Each uses a consistent `<AccordionSection>` wrapper with chevron toggle and animated expand.

### Exit Conditions (default: open)
- Stop Loss % (existing)
- Take Profit % (existing)
- Trailing Stop % — toggle to enable, then number input
- Exit After N Bars — toggle to enable, then integer input

### Symbol Universe (default: collapsed)
- Tag-input: type symbol + Enter/comma to add chips
- Remove individual symbol chips
- Shows primary symbol (first in list) with a "Primary" badge
- Used as default symbol in backtest runner

### Execution Settings (default: collapsed)
- Commission % (default 0.10%)
- Slippage % (default 0.05%)

### Risk Controls (default: collapsed)
- Cooldown bars (0 = no cooldown)
- Max trades per day (0 = unlimited)
- Max exposure % (100% = no limit)
- Daily loss limit % (0 = disabled)

---

## Diagnostics / Analyze Fix

**Root cause:** All three async calls in `StrategyBuilder.tsx` use raw `fetch()` without auth headers.

**Fix:** Replace all three with `apiFetch` from `@/lib/api/client`:

1. Auto-diagnose effect (POST `/api/strategies/diagnose`)
2. Indicator preview effect (POST `/api/strategies/compute-indicator`)
3. `runExplainer` function (POST `/api/explain/strategy`)

No endpoint changes needed — this is purely a frontend auth header fix.

---

## Strategies List Enhancements

### Updated row layout

```
[Score] Strategy Name    [TIMEFRAME] [ACTION]    Updated 2d ago
        RSI(14) < 30 AND MACD > 0                2 conditions · 1 issue
        Brief description if set
                                    [▶] [✎] [⧉] [🗑]
```

### New metadata shown
- Timeframe badge (e.g., `1D`)
- `updated_at` formatted as relative time ("2d ago")
- Condition count across all groups
- Clone button (⧉) — duplicates strategy with " (copy)" suffix, optimistic insert at top of list

### Clone flow
1. Click clone → POST `/api/strategies/create` with existing strategy data, name appended with " (copy)"
2. Optimistically prepend to list
3. On success: update row with real ID; on failure: remove from list

---

## Backtest Enhancements

### Access from create mode
Current: Backtest button only shown in edit mode.
Fix: In create mode, "Run Backtest" saves the strategy first, then navigates to `/backtest/[id]`.

### Commission + slippage applied
`BacktestRequest` gains `commission_pct` and `slippage_pct` fields. Backend applies round-trip cost to each trade's P&L.

### Drawdown chart
New tab `"Drawdown"` on the backtest results tab bar. Renders a filled area chart of running drawdown (%) over time using `EquityCurveChart` in a variant mode.

### Buy-and-hold comparison
`BacktestResult` gains `benchmark_equity_curve: number[]`. Backend computes buy-and-hold return for the same symbol/period. Equity curve chart renders it as a secondary dashed line.

---

## Files Changed

### Frontend
| File | Change |
|------|--------|
| `types/strategy.ts` | Add `ConditionGroup`, new fields to `Strategy` |
| `types/backtest.ts` | Add `commission_pct`, `slippage_pct` to request; `benchmark_equity_curve` to result |
| `components/strategy-builder/ConditionGroup.tsx` | New component |
| `components/strategy-builder/StrategyBuilder.tsx` | Use groups, add accordions, fix auth on fetch calls |
| `components/strategy-builder/AccordionSection.tsx` | New reusable accordion wrapper |
| `app/strategies/page.tsx` | Add metadata, clone button |
| `app/backtest/[id]/page.tsx` | Add drawdown tab, benchmark line, apply commission/slippage |

### Backend
| File | Change |
|------|--------|
| `db/models.py` | Add 10 new columns to `Strategy` |
| `api/routes/strategies.py` | Update schemas, backtest to apply costs + benchmark |
| `alembic/versions/xxxx_strategy_groups_and_settings.py` | Migration for new columns |

---

## Out of Scope (this iteration)

- Live trading integration with saved strategies
- Real market data in backtest (still uses synthetic OHLCV)
- Strategy versioning / history
- Multi-symbol backtesting (single primary symbol only)
- Drag-and-drop reordering of condition groups
