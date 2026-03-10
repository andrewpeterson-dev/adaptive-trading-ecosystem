# Builder + Strategies Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extend the strategy builder with AND/OR condition groups, strategy settings (universe, fees, risk controls), working diagnostics, a richer strategies list, and improved backtest.

**Architecture:** Surgical enhancement — extend existing types, components, and routes in-place. New `ConditionGroup` type wraps the flat `conditions[]` array. Eight tasks executed sequentially, each committed independently.

**Tech Stack:** Next.js 14 (App Router), TypeScript strict, Tailwind CSS, FastAPI, SQLAlchemy async, Alembic, Pydantic v2.

---

## Task 1: Alembic migration — add 10 new columns to `strategies` table

**Files:**
- Create: `alembic/versions/004_strategy_groups_and_settings.py`

**Step 1: Create the migration file**

```python
# alembic/versions/004_strategy_groups_and_settings.py
"""strategy groups and settings

Revision ID: 004
Revises: 003
Create Date: 2026-03-10
"""
from alembic import op
import sqlalchemy as sa

revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('strategies', sa.Column('condition_groups', sa.JSON(), nullable=True))
    op.add_column('strategies', sa.Column('symbols', sa.JSON(), nullable=True))
    op.add_column('strategies', sa.Column('commission_pct', sa.Float(), nullable=True, server_default='0.001'))
    op.add_column('strategies', sa.Column('slippage_pct', sa.Float(), nullable=True, server_default='0.0005'))
    op.add_column('strategies', sa.Column('trailing_stop_pct', sa.Float(), nullable=True))
    op.add_column('strategies', sa.Column('exit_after_bars', sa.Integer(), nullable=True))
    op.add_column('strategies', sa.Column('cooldown_bars', sa.Integer(), nullable=True, server_default='0'))
    op.add_column('strategies', sa.Column('max_trades_per_day', sa.Integer(), nullable=True, server_default='0'))
    op.add_column('strategies', sa.Column('max_exposure_pct', sa.Float(), nullable=True, server_default='1.0'))
    op.add_column('strategies', sa.Column('max_loss_pct', sa.Float(), nullable=True, server_default='0.0'))


def downgrade() -> None:
    for col in [
        'condition_groups', 'symbols', 'commission_pct', 'slippage_pct',
        'trailing_stop_pct', 'exit_after_bars', 'cooldown_bars',
        'max_trades_per_day', 'max_exposure_pct', 'max_loss_pct',
    ]:
        op.drop_column('strategies', col)
```

**Step 2: Verify the previous migration revision ID**

```bash
ls alembic/versions/003_paper_live_mode_separation.py
grep "^revision" alembic/versions/003_paper_live_mode_separation.py
```

Expected: shows the revision string. If it differs from `'003'`, update `down_revision` in the new file to match the exact string.

**Step 3: Run migration against Docker Postgres**

```bash
cd ~/adaptive-trading-ecosystem
docker compose exec api alembic upgrade head
```

Expected output ends with: `Running upgrade ... -> 004, strategy groups and settings`

**Step 4: Verify columns exist**

```bash
docker compose exec postgres psql -U trader -d trading_ecosystem \
  -c "\d strategies" | grep -E "condition_groups|symbols|commission"
```

Expected: three matching rows.

**Step 5: Commit**

```bash
git add alembic/versions/004_strategy_groups_and_settings.py
git commit -m "feat: migration for strategy groups and settings columns"
```

---

## Task 2: Update `db/models.py` — add new columns to Strategy model

**Files:**
- Modify: `db/models.py` (Strategy class, lines ~350–370)

**Step 1: Add columns to the Strategy class**

In `db/models.py`, find the `Strategy` class and add after `diagnostics`:

```python
# New fields — condition groups replace flat conditions[] for multi-OR strategies
condition_groups = Column(JSON, nullable=True)   # ConditionGroup[]
symbols = Column(JSON, nullable=True)            # ["SPY", "QQQ"]
commission_pct = Column(Float, default=0.001)
slippage_pct = Column(Float, default=0.0005)
trailing_stop_pct = Column(Float, nullable=True)
exit_after_bars = Column(Integer, nullable=True)
cooldown_bars = Column(Integer, default=0)
max_trades_per_day = Column(Integer, default=0)
max_exposure_pct = Column(Float, default=1.0)
max_loss_pct = Column(Float, default=0.0)
```

**Step 2: Verify the API container still starts**

```bash
cd ~/adaptive-trading-ecosystem
docker compose up -d --build --force-recreate api 2>&1 | tail -6
sleep 5 && docker compose logs api --tail=5
```

Expected: `Application startup complete.`

**Step 3: Commit**

```bash
git add db/models.py
git commit -m "feat: add condition_groups and settings columns to Strategy model"
```

---

## Task 3: Update backend schemas and `_strategy_to_dict`

**Files:**
- Modify: `api/routes/strategies.py`

**Step 1: Expand `StrategySchema` (add new fields after `timeframe`)**

Find the `StrategySchema` class and add:

```python
class StrategySchema(BaseModel):
    name: str
    description: str = ""
    conditions: list[ConditionSchema] = Field(default_factory=list)
    condition_groups: list[dict] = Field(default_factory=list)  # NEW
    action: str = "BUY"
    stop_loss_pct: float = 0.02
    take_profit_pct: float = 0.05
    position_size_pct: float = 0.1
    timeframe: str = "1D"
    # NEW settings
    symbols: list[str] = Field(default_factory=lambda: ["SPY"])
    commission_pct: float = 0.001
    slippage_pct: float = 0.0005
    trailing_stop_pct: Optional[float] = None
    exit_after_bars: Optional[int] = None
    cooldown_bars: int = 0
    max_trades_per_day: int = 0
    max_exposure_pct: float = 1.0
    max_loss_pct: float = 0.0
```

**Step 2: Expand `StrategyUpdateSchema` the same way**

Add the same 10 new fields as `Optional[...]` defaulting to `None` in `StrategyUpdateSchema`.

**Step 3: Update `_strategy_to_dict` to include new fields**

Replace the existing `_strategy_to_dict` function with:

```python
def _strategy_to_dict(s) -> dict:
    return {
        "id": s.id,
        "name": s.name,
        "description": s.description or "",
        "conditions": s.conditions or [],
        "condition_groups": s.condition_groups or [],
        "action": s.action,
        "stop_loss_pct": s.stop_loss_pct,
        "take_profit_pct": s.take_profit_pct,
        "position_size_pct": s.position_size_pct,
        "timeframe": s.timeframe,
        "diagnostics": s.diagnostics or {},
        "created_at": s.created_at.isoformat() if s.created_at else "",
        "updated_at": s.updated_at.isoformat() if s.updated_at else "",
        # settings
        "symbols": s.symbols or ["SPY"],
        "commission_pct": s.commission_pct or 0.001,
        "slippage_pct": s.slippage_pct or 0.0005,
        "trailing_stop_pct": s.trailing_stop_pct,
        "exit_after_bars": s.exit_after_bars,
        "cooldown_bars": s.cooldown_bars or 0,
        "max_trades_per_day": s.max_trades_per_day or 0,
        "max_exposure_pct": s.max_exposure_pct or 1.0,
        "max_loss_pct": s.max_loss_pct or 0.0,
    }
```

**Step 4: Update `create_strategy` to persist new fields**

In `create_strategy`, after `conditions_dicts = [c.model_dump() for c in strategy.conditions]`, add:

```python
# Flatten condition_groups to conditions for diagnostics (all conditions across all groups)
if strategy.condition_groups:
    flat = [c for g in strategy.condition_groups for c in g.get("conditions", [])]
    conditions_dicts = flat
```

Then in the `Strategy(...)` constructor call, add:

```python
condition_groups=strategy.condition_groups or [],
symbols=strategy.symbols,
commission_pct=strategy.commission_pct,
slippage_pct=strategy.slippage_pct,
trailing_stop_pct=strategy.trailing_stop_pct,
exit_after_bars=strategy.exit_after_bars,
cooldown_bars=strategy.cooldown_bars,
max_trades_per_day=strategy.max_trades_per_day,
max_exposure_pct=strategy.max_exposure_pct,
max_loss_pct=strategy.max_loss_pct,
```

**Step 5: Update `update_strategy` to persist new fields**

In `update_strategy`, inside the `for field, value in update_data.items():` loop, add a branch for `condition_groups`:

```python
if field == "condition_groups":
    # Also flatten groups → conditions for diagnostics re-run
    flat = [c for g in value for c in g.get("conditions", [])]
    s.conditions = flat
    conditions_changed = True
```

**Step 6: Smoke test**

```bash
docker compose up -d --build --force-recreate api 2>&1 | tail -3
sleep 5 && curl -s http://localhost:8000/health
```

Expected: `{"status":"ok"}`

**Step 7: Commit**

```bash
git add api/routes/strategies.py
git commit -m "feat: expand strategy schemas and serialization for groups + settings"
```

---

## Task 4: Update backtest route — condition groups, commission/slippage, benchmark

**Files:**
- Modify: `api/routes/strategies.py` (the `run_backtest` function, ~lines 256–555)

**Step 1: Expand `BacktestRequest`**

```python
class BacktestRequest(BaseModel):
    strategy_id: Optional[int] = None
    conditions: Optional[list[ConditionSchema]] = None
    condition_groups: Optional[list[dict]] = None   # NEW
    symbol: str = "SPY"
    lookback_days: int = 252
    initial_capital: float = 100_000.0
    commission_pct: float = 0.001   # NEW — overridden by strategy settings if strategy_id given
    slippage_pct: float = 0.0005    # NEW
```

**Step 2: Load commission/slippage + condition_groups from DB strategy**

In `run_backtest`, replace the DB-load block:

```python
if req.strategy_id is not None:
    async with get_session() as session:
        s = await session.get(Strategy, req.strategy_id)
        if not s:
            raise HTTPException(404, f"Strategy {req.strategy_id} not found")
        # Prefer condition_groups if present, else fall back to flat conditions
        if s.condition_groups:
            groups = s.condition_groups
            conditions = [c for g in groups for c in g.get("conditions", [])]
        else:
            groups = [{"conditions": s.conditions}]
            conditions = s.conditions or []
        stop_loss_pct = s.stop_loss_pct
        take_profit_pct = s.take_profit_pct
        commission_pct = s.commission_pct or req.commission_pct
        slippage_pct = s.slippage_pct or req.slippage_pct
elif req.condition_groups:
    groups = req.condition_groups
    conditions = [c for g in groups for c in g.get("conditions", [])]
    stop_loss_pct = 0.02
    take_profit_pct = 0.05
    commission_pct = req.commission_pct
    slippage_pct = req.slippage_pct
elif req.conditions:
    groups = [{"conditions": [c.model_dump() for c in req.conditions]}]
    conditions = [c.model_dump() for c in req.conditions]
    stop_loss_pct = 0.02
    take_profit_pct = 0.05
    commission_pct = req.commission_pct
    slippage_pct = req.slippage_pct
else:
    raise HTTPException(400, "Provide strategy_id, condition_groups, or conditions")
```

**Step 3: Update signal evaluation to use OR-between-groups logic**

Replace the existing signal-evaluation loop (`for i in range(n_bars): all_met = True ...`) with:

```python
def _eval_group(group_conditions, indicator_cache, i, close):
    """Returns True if ALL conditions in a group are met at bar i."""
    for cond in group_conditions:
        ind_name = cond["indicator"] if isinstance(cond, dict) else cond.indicator
        op = cond["operator"] if isinstance(cond, dict) else cond.operator
        val = cond["value"] if isinstance(cond, dict) else cond.value
        result = indicator_cache.get(ind_name)
        if result is None:
            return False
        if isinstance(result, pd.Series):
            ind_val = result.iloc[i]
        elif isinstance(result, dict):
            first_key = next(iter(result))
            s = result[first_key]
            ind_val = s.iloc[i] if isinstance(s, pd.Series) else np.nan
        else:
            ind_val = np.nan
        if pd.isna(ind_val):
            return False
        threshold = float(val) if not isinstance(val, (int, float)) else val
        if op == ">":
            met = ind_val > threshold
        elif op == "<":
            met = ind_val < threshold
        elif op == ">=":
            met = ind_val >= threshold
        elif op == "<=":
            met = ind_val <= threshold
        elif op == "==":
            met = abs(ind_val - threshold) < 0.001
        elif op in ("crosses_above", "crosses_below"):
            if i == 0:
                met = False
            else:
                prev_result = indicator_cache[ind_name]
                if isinstance(prev_result, pd.Series):
                    prev_val = prev_result.iloc[i - 1]
                elif isinstance(prev_result, dict):
                    fk = next(iter(prev_result))
                    sv = prev_result[fk]
                    prev_val = sv.iloc[i - 1] if isinstance(sv, pd.Series) else np.nan
                else:
                    prev_val = np.nan
                if pd.isna(prev_val):
                    met = False
                elif op == "crosses_above":
                    met = prev_val <= threshold and ind_val > threshold
                else:
                    met = prev_val >= threshold and ind_val < threshold
        else:
            met = False
        if not met:
            return False
    return True

signals = np.zeros(n_bars)
for i in range(n_bars):
    # OR between groups — signal fires if ANY group is fully met
    for g in groups:
        group_conditions = g.get("conditions", [])
        if group_conditions and _eval_group(group_conditions, indicator_cache, i, close):
            signals[i] = 1
            break
```

**Step 4: Apply round-trip commission + slippage to each trade**

In the trade simulation, after computing `pnl`, subtract friction cost. Find every place a trade is appended and add before the `trades.append(...)`:

```python
# Round-trip friction: entry + exit, each side has commission + slippage
friction = (commission_pct + slippage_pct) * 2
friction_amount = capital * friction
pnl -= friction_amount
capital += pnl
```

Do this consistently for stop-loss exit, take-profit exit, and end-of-period close.

**Step 5: Compute buy-and-hold benchmark equity curve**

After the trade simulation loop, before computing metrics, add:

```python
# Buy-and-hold benchmark: invest all capital at bar 0, hold to end
bh_start = close[0]
benchmark_equity = [req.initial_capital * (close[i] / bh_start) for i in range(n_bars + 1)]
```

**Step 6: Add benchmark to return value**

In the `return` dict at the end of `run_backtest`, add:

```python
"benchmark_equity_curve": [
    {"date": dates[min(i, n_bars - 1)].strftime("%Y-%m-%d"), "value": round(v, 2)}
    for i, v in enumerate(benchmark_equity)
],
"commission_pct": commission_pct,
"slippage_pct": slippage_pct,
```

**Step 7: Test the backtest endpoint**

```bash
# Get a valid strategy id first
docker compose exec postgres psql -U trader -d trading_ecosystem \
  -c "SELECT id FROM strategies LIMIT 1;"

# Run backtest (replace 1 with actual id)
TOKEN=$(python3 -c "
import urllib.request, json
data = json.dumps({'email': 'apetersongroup@gmail.com', 'password': 'AnDrEw12345!'}).encode()
req = urllib.request.Request('http://localhost:8000/api/auth/login', data=data, headers={'Content-Type': 'application/json'})
with urllib.request.urlopen(req) as r:
    print(json.load(r)['token'])
")
curl -s -X POST http://localhost:8000/api/strategies/backtest \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"strategy_id": 1, "symbol": "SPY", "lookback_days": 100, "initial_capital": 10000}' \
  | python3 -m json.tool | grep -E "benchmark|commission|total_return" | head -10
```

Expected: JSON with `benchmark_equity_curve`, `commission_pct`, `total_return`.

**Step 8: Commit**

```bash
git add api/routes/strategies.py
git commit -m "feat: backtest supports condition groups, commission/slippage, benchmark curve"
```

---

## Task 5: Update frontend types

**Files:**
- Modify: `frontend/src/types/strategy.ts`
- Modify: `frontend/src/types/backtest.ts`

**Step 1: Rewrite `types/strategy.ts`**

```typescript
export type Operator = ">" | "<" | ">=" | "<=" | "==" | "crosses_above" | "crosses_below";
export type Action = "BUY" | "SELL";

export interface StrategyCondition {
  id: string;
  indicator: string;
  operator: Operator;
  value: number | string;
  compare_to?: string;
  params: Record<string, number>;
  action: Action;
}

export interface ConditionGroup {
  id: string;
  label?: string;
  conditions: StrategyCondition[];
}

export interface Strategy {
  id?: string;
  name: string;
  description: string;
  conditions?: StrategyCondition[];        // legacy — kept for backward compat
  condition_groups: ConditionGroup[];       // primary representation
  action: Action;
  stop_loss_pct: number;
  take_profit_pct: number;
  position_size_pct: number;
  timeframe: string;
  // Universe
  symbols: string[];
  // Execution
  commission_pct: number;
  slippage_pct: number;
  // Exit
  trailing_stop_pct: number | null;
  exit_after_bars: number | null;
  // Risk
  cooldown_bars: number;
  max_trades_per_day: number;
  max_exposure_pct: number;
  max_loss_pct: number;
}

export interface Diagnostic {
  code: string;
  severity: "info" | "warning" | "critical";
  title: string;
  message: string;
  suggestion: string;
}

export interface DiagnosticReport {
  score: number;
  has_critical: boolean;
  total_issues: number;
  diagnostics: Diagnostic[];
}

export interface StrategyExplanation {
  summary: string;
  market_regime: string;
  strengths: string[];
  weaknesses: string[];
  risk_profile: string;
  overfitting_warning: boolean;
}

export interface StrategyRecord {
  id: number;
  name: string;
  description: string;
  conditions: Array<{
    indicator: string;
    operator: string;
    value: number | string;
    compare_to?: string;
    params: Record<string, number>;
    action: string;
  }>;
  condition_groups: Array<{
    id: string;
    label?: string;
    conditions: StrategyRecord["conditions"];
  }>;
  action: string;
  stop_loss_pct: number;
  take_profit_pct: number;
  position_size_pct: number;
  timeframe: string;
  diagnostics: {
    score: number;
    total_issues: number;
    has_critical: boolean;
    diagnostics: Array<{
      code: string;
      severity: string;
      title: string;
      message: string;
      suggestion: string;
    }>;
  };
  created_at: string;
  updated_at: string;
  // settings
  symbols: string[];
  commission_pct: number;
  slippage_pct: number;
  trailing_stop_pct: number | null;
  exit_after_bars: number | null;
  cooldown_bars: number;
  max_trades_per_day: number;
  max_exposure_pct: number;
  max_loss_pct: number;
}
```

**Step 2: Update `types/backtest.ts` — add benchmark and commission to types**

```typescript
export interface BacktestMetrics {
  sharpe_ratio: number;
  sortino_ratio: number;
  win_rate: number;
  max_drawdown: number;
  total_return: number;
  num_trades: number;
  avg_trade_pnl: number;
  profit_factor: number;
}

export interface BacktestTrade {
  entry_date: string;
  exit_date: string;
  direction: string;
  entry_price: number;
  exit_price: number;
  pnl: number;
  pnl_pct: number;
  bars_held: number;
}

export interface BacktestResult {
  metrics: BacktestMetrics;
  equity_curve: { date: string; value: number }[];
  benchmark_equity_curve: { date: string; value: number }[];
  trades: BacktestTrade[];
  commission_pct: number;
  slippage_pct: number;
  synthetic_data?: boolean;
  data_warning?: string;
}

export interface BacktestRequest {
  strategy_id?: number;
  conditions?: Array<{
    indicator: string;
    operator: string;
    value: number | string;
    params: Record<string, number>;
    action: string;
  }>;
  condition_groups?: Array<{
    id: string;
    conditions: BacktestRequest["conditions"];
  }>;
  symbol: string;
  lookback_days: number;
  initial_capital: number;
  commission_pct?: number;
  slippage_pct?: number;
}
```

**Step 3: Verify TypeScript compiles**

```bash
cd ~/adaptive-trading-ecosystem/frontend
npx tsc --noEmit 2>&1 | head -30
```

Expected: no errors related to `strategy.ts` or `backtest.ts`. Other unrelated errors are acceptable.

**Step 4: Commit**

```bash
git add frontend/src/types/strategy.ts frontend/src/types/backtest.ts
git commit -m "feat: add ConditionGroup type and strategy settings types"
```

---

## Task 6: New `AccordionSection` and `ConditionGroup` components

**Files:**
- Create: `frontend/src/components/strategy-builder/AccordionSection.tsx`
- Create: `frontend/src/components/strategy-builder/ConditionGroup.tsx`

**Step 1: Create `AccordionSection.tsx`**

```tsx
"use client";

import React, { useState } from "react";
import { ChevronDown } from "lucide-react";

interface AccordionSectionProps {
  title: string;
  defaultOpen?: boolean;
  badge?: string;
  children: React.ReactNode;
}

export function AccordionSection({
  title,
  defaultOpen = false,
  badge,
  children,
}: AccordionSectionProps) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className="rounded-lg border border-border/50 overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-4 py-2.5 bg-muted/30 hover:bg-muted/50 transition-colors text-left"
      >
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            {title}
          </span>
          {badge && (
            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-primary/10 text-primary border border-primary/20">
              {badge}
            </span>
          )}
        </div>
        <ChevronDown
          className={`h-3.5 w-3.5 text-muted-foreground transition-transform duration-150 ${
            open ? "rotate-180" : ""
          }`}
        />
      </button>
      {open && <div className="px-4 py-3 space-y-3">{children}</div>}
    </div>
  );
}
```

**Step 2: Create `ConditionGroup.tsx`**

```tsx
"use client";

import React from "react";
import { Plus, X } from "lucide-react";
import { ConditionRow } from "./ConditionRow";
import type { ConditionGroup as ConditionGroupType, StrategyCondition } from "@/types/strategy";

interface ConditionGroupProps {
  group: ConditionGroupType;
  groupIndex: number;
  totalGroups: number;
  onAddCondition: (groupIndex: number) => void;
  onRemoveCondition: (groupIndex: number, condIndex: number) => void;
  onUpdateCondition: (
    groupIndex: number,
    condIndex: number,
    updated: Partial<StrategyCondition>
  ) => void;
  onRemoveGroup: (groupIndex: number) => void;
}

export function ConditionGroup({
  group,
  groupIndex,
  totalGroups,
  onAddCondition,
  onRemoveCondition,
  onUpdateCondition,
  onRemoveGroup,
}: ConditionGroupProps) {
  const label = String.fromCharCode(65 + groupIndex); // A, B, C…
  const canRemoveGroup = totalGroups > 1;
  const isLastConditionInLastGroup =
    group.conditions.length === 1 && totalGroups === 1;

  return (
    <div className="rounded-lg border border-border/50 bg-card/50 overflow-hidden">
      {/* Group header */}
      <div className="flex items-center justify-between px-3 py-1.5 bg-muted/20 border-b border-border/40">
        <span className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">
          Group {label}
        </span>
        <button
          type="button"
          onClick={() => onRemoveGroup(groupIndex)}
          disabled={!canRemoveGroup}
          title="Remove group"
          className="p-0.5 rounded text-muted-foreground/40 hover:text-red-400 hover:bg-red-400/10 transition-colors disabled:opacity-0 disabled:cursor-default"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>

      {/* Conditions */}
      <div className="p-2 space-y-2">
        {group.conditions.map((condition, condIndex) => (
          <ConditionRow
            key={condition.id}
            condition={condition}
            index={condIndex}
            isOnly={isLastConditionInLastGroup}
            onChange={(_idx, updated) =>
              onUpdateCondition(groupIndex, condIndex, updated)
            }
            onRemove={() => onRemoveCondition(groupIndex, condIndex)}
          />
        ))}

        <button
          type="button"
          onClick={() => onAddCondition(groupIndex)}
          className="w-full flex items-center justify-center gap-1 py-1.5 rounded border border-dashed border-border/40 text-xs text-muted-foreground hover:text-foreground hover:border-primary/30 hover:bg-primary/5 transition-colors"
        >
          <Plus className="h-3 w-3" />
          Add Condition
        </button>
      </div>
    </div>
  );
}
```

**Step 3: Verify TypeScript compiles**

```bash
cd ~/adaptive-trading-ecosystem/frontend
npx tsc --noEmit 2>&1 | grep -E "ConditionGroup|AccordionSection" | head -10
```

Expected: no errors for the new files.

**Step 4: Commit**

```bash
git add frontend/src/components/strategy-builder/AccordionSection.tsx \
        frontend/src/components/strategy-builder/ConditionGroup.tsx
git commit -m "feat: add AccordionSection and ConditionGroup components"
```

---

## Task 7: Rewrite `StrategyBuilder.tsx`

**Files:**
- Modify: `frontend/src/components/strategy-builder/StrategyBuilder.tsx`

This is the largest task. Replace the entire file with the updated version below.

**Key changes vs current:**
- `conditions[]` state replaced by `conditionGroups[]`
- Group add/remove/update handlers
- Four accordion sections (Exit, Universe, Execution, Risk)
- All `fetch()` calls replaced with `apiFetch()`
- `buildLogicString` updated for groups
- `saveStrategy` sends all new fields

**Step 1: Replace `StrategyBuilder.tsx` completely**

```tsx
"use client";

import React, { useState, useCallback, useEffect } from "react";
import { Plus, Play, Save, RotateCcw, Zap } from "lucide-react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api/client";
import { ConditionGroup as ConditionGroupComponent } from "./ConditionGroup";
import { AccordionSection } from "./AccordionSection";
import { DiagnosticPanel } from "./DiagnosticPanel";
import { ExplainerPanel } from "./ExplainerPanel";
import { IndicatorChart } from "@/components/charts/IndicatorChart";
import type {
  ConditionGroup,
  StrategyCondition,
  Strategy,
  StrategyRecord,
  DiagnosticReport,
  StrategyExplanation,
  Action,
} from "@/types/strategy";

// ── Helpers ────────────────────────────────────────────────────────────────

function genId(): string {
  return `id_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
}

function emptyCondition(): StrategyCondition {
  return { id: genId(), indicator: "", operator: "<", value: 30, params: {}, action: "BUY" };
}

function emptyGroup(index = 0): ConditionGroup {
  return {
    id: genId(),
    label: `Group ${String.fromCharCode(65 + index)}`,
    conditions: [emptyCondition()],
  };
}

function buildLogicString(groups: ConditionGroup[], action: Action): string {
  const groupParts = groups
    .map((g) => {
      const condParts = g.conditions
        .filter((c) => c.indicator)
        .map((c) => {
          const paramStr = Object.values(c.params).join(",");
          const ind = c.indicator.toUpperCase().replace(/_/g, " ");
          const indFmt = paramStr ? `${ind}(${paramStr})` : ind;
          return `${indFmt} ${c.operator} ${c.value}`;
        });
      if (condParts.length === 0) return null;
      return condParts.length === 1 ? condParts[0] : `(${condParts.join(" AND ")})`;
    })
    .filter(Boolean);
  if (groupParts.length === 0) return "";
  return `IF ${groupParts.join(" OR ")} THEN ${action}`;
}

// ── Props ──────────────────────────────────────────────────────────────────

interface StrategyBuilderProps {
  initialStrategy?: StrategyRecord;
  mode?: "create" | "edit";
}

// ── Component ──────────────────────────────────────────────────────────────

export function StrategyBuilder({ initialStrategy, mode = "create" }: StrategyBuilderProps) {
  const router = useRouter();

  // Core identity
  const [name, setName] = useState("My Strategy");
  const [description, setDescription] = useState("");
  const [action, setAction] = useState<Action>("BUY");
  const [timeframe, setTimeframe] = useState("1D");

  // Condition groups (primary state — replaces flat conditions[])
  const [conditionGroups, setConditionGroups] = useState<ConditionGroup[]>([emptyGroup(0)]);

  // Exit conditions
  const [stopLoss, setStopLoss] = useState(2);
  const [takeProfit, setTakeProfit] = useState(5);
  const [positionSize, setPositionSize] = useState(10);
  const [trailingStopEnabled, setTrailingStopEnabled] = useState(false);
  const [trailingStop, setTrailingStop] = useState(1.5);
  const [exitAfterBarsEnabled, setExitAfterBarsEnabled] = useState(false);
  const [exitAfterBars, setExitAfterBars] = useState(10);

  // Universe
  const [symbols, setSymbols] = useState<string[]>(["SPY"]);
  const [symbolInput, setSymbolInput] = useState("");

  // Execution
  const [commissionPct, setCommissionPct] = useState(0.1);  // display as %
  const [slippagePct, setSlippagePct] = useState(0.05);

  // Risk
  const [cooldownBars, setCooldownBars] = useState(0);
  const [maxTradesPerDay, setMaxTradesPerDay] = useState(0);
  const [maxExposurePct, setMaxExposurePct] = useState(100);
  const [maxLossPct, setMaxLossPct] = useState(0);

  // UI state
  const [diagnostics, setDiagnostics] = useState<DiagnosticReport | null>(null);
  const [diagLoading, setDiagLoading] = useState(false);
  const [explanation, setExplanation] = useState<StrategyExplanation | null>(null);
  const [explainLoading, setExplainLoading] = useState(false);
  const [saveStatus, setSaveStatus] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [indicatorPreviews, setIndicatorPreviews] = useState<
    Record<string, { values?: number[]; components?: Record<string, number[]> }>
  >({});

  // ── Populate from initialStrategy (edit mode) ──────────────────────────

  useEffect(() => {
    if (!initialStrategy) return;
    setName(initialStrategy.name);
    setDescription(initialStrategy.description || "");
    setAction(initialStrategy.action as Action);
    setStopLoss((initialStrategy.stop_loss_pct || 0.02) * 100);
    setTakeProfit((initialStrategy.take_profit_pct || 0.05) * 100);
    setPositionSize((initialStrategy.position_size_pct || 0.1) * 100);
    setTimeframe(initialStrategy.timeframe || "1D");
    setSymbols(initialStrategy.symbols?.length ? initialStrategy.symbols : ["SPY"]);
    setCommissionPct((initialStrategy.commission_pct ?? 0.001) * 100);
    setSlippagePct((initialStrategy.slippage_pct ?? 0.0005) * 100);
    if (initialStrategy.trailing_stop_pct != null) {
      setTrailingStopEnabled(true);
      setTrailingStop(initialStrategy.trailing_stop_pct * 100);
    }
    if (initialStrategy.exit_after_bars != null) {
      setExitAfterBarsEnabled(true);
      setExitAfterBars(initialStrategy.exit_after_bars);
    }
    setCooldownBars(initialStrategy.cooldown_bars ?? 0);
    setMaxTradesPerDay(initialStrategy.max_trades_per_day ?? 0);
    setMaxExposurePct((initialStrategy.max_exposure_pct ?? 1.0) * 100);
    setMaxLossPct((initialStrategy.max_loss_pct ?? 0) * 100);

    // Prefer condition_groups; fall back to wrapping flat conditions in one group
    if (initialStrategy.condition_groups?.length) {
      setConditionGroups(
        initialStrategy.condition_groups.map((g, gi) => ({
          id: genId(),
          label: g.label ?? `Group ${String.fromCharCode(65 + gi)}`,
          conditions: g.conditions.map((c) => ({
            id: genId(),
            indicator: c.indicator,
            operator: c.operator as StrategyCondition["operator"],
            value: c.value,
            compare_to: c.compare_to,
            params: c.params || {},
            action: (c.action as Action) || (initialStrategy.action as Action),
          })),
        }))
      );
    } else if (initialStrategy.conditions?.length) {
      setConditionGroups([
        {
          id: genId(),
          label: "Group A",
          conditions: initialStrategy.conditions.map((c) => ({
            id: genId(),
            indicator: c.indicator,
            operator: c.operator as StrategyCondition["operator"],
            value: c.value,
            compare_to: c.compare_to,
            params: c.params || {},
            action: (c.action as Action) || (initialStrategy.action as Action),
          })),
        },
      ]);
    }
    if (initialStrategy.diagnostics) {
      setDiagnostics(initialStrategy.diagnostics as DiagnosticReport);
    }
  }, [initialStrategy]);

  // ── Group / condition handlers ─────────────────────────────────────────

  const addGroup = useCallback(() => {
    setConditionGroups((prev) => [...prev, emptyGroup(prev.length)]);
  }, []);

  const removeGroup = useCallback((groupIndex: number) => {
    setConditionGroups((prev) => prev.filter((_, i) => i !== groupIndex));
  }, []);

  const addCondition = useCallback((groupIndex: number) => {
    setConditionGroups((prev) =>
      prev.map((g, gi) =>
        gi === groupIndex
          ? { ...g, conditions: [...g.conditions, emptyCondition()] }
          : g
      )
    );
  }, []);

  const removeCondition = useCallback((groupIndex: number, condIndex: number) => {
    setConditionGroups((prev) =>
      prev
        .map((g, gi) => {
          if (gi !== groupIndex) return g;
          const newConds = g.conditions.filter((_, ci) => ci !== condIndex);
          return { ...g, conditions: newConds };
        })
        .filter((g) => g.conditions.length > 0) // auto-remove empty groups
    );
  }, []);

  const updateCondition = useCallback(
    (groupIndex: number, condIndex: number, updated: Partial<StrategyCondition>) => {
      setConditionGroups((prev) =>
        prev.map((g, gi) =>
          gi === groupIndex
            ? {
                ...g,
                conditions: g.conditions.map((c, ci) =>
                  ci === condIndex ? { ...c, ...updated } : c
                ),
              }
            : g
        )
      );
    },
    []
  );

  const resetBuilder = useCallback(() => {
    setConditionGroups([emptyGroup(0)]);
    setDiagnostics(null);
    setExplanation(null);
    setName("My Strategy");
    setDescription("");
    setSaveStatus("idle");
    setIndicatorPreviews({});
    setSymbols(["SPY"]);
    setTrailingStopEnabled(false);
    setExitAfterBarsEnabled(false);
  }, []);

  // ── Symbol tag input ────────────────────────────────────────────────────

  const addSymbol = useCallback((raw: string) => {
    const sym = raw.trim().toUpperCase().replace(/[^A-Z]/g, "");
    if (sym && !symbols.includes(sym)) setSymbols((prev) => [...prev, sym]);
    setSymbolInput("");
  }, [symbols]);

  // ── All valid (filled) conditions across all groups ────────────────────

  const allValidConditions = conditionGroups
    .flatMap((g) => g.conditions)
    .filter((c) => c.indicator);

  // ── Auto-diagnostics (debounced, uses apiFetch for auth) ───────────────

  const conditionKey = conditionGroups
    .flatMap((g) => g.conditions)
    .map((c) => `${c.indicator}:${c.operator}:${c.value}:${JSON.stringify(c.params)}`)
    .join("|");

  useEffect(() => {
    if (allValidConditions.length === 0) {
      setDiagnostics(null);
      return;
    }
    const timeout = setTimeout(async () => {
      setDiagLoading(true);
      try {
        const params: Record<string, Record<string, number>> = {};
        for (const c of allValidConditions) params[c.indicator] = c.params;
        const data = await apiFetch<DiagnosticReport>("/api/strategies/diagnose", {
          method: "POST",
          body: JSON.stringify({
            conditions: allValidConditions.map((c) => ({
              indicator: c.indicator,
              operator: c.operator,
              value: c.value,
              params: c.params,
              action: c.action,
            })),
            parameters: params,
          }),
        });
        setDiagnostics(data);
      } catch {
        // network error — silently ignore
      } finally {
        setDiagLoading(false);
      }
    }, 500);
    return () => clearTimeout(timeout);
  }, [conditionKey]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Indicator previews (debounced, uses apiFetch for auth) ────────────

  useEffect(() => {
    if (allValidConditions.length === 0) {
      setIndicatorPreviews({});
      return;
    }
    const timeout = setTimeout(async () => {
      const previews: typeof indicatorPreviews = {};
      await Promise.all(
        allValidConditions.map(async (c) => {
          try {
            const data = await apiFetch<{
              values?: number[];
              components?: Record<string, number[]>;
            }>("/api/strategies/compute-indicator", {
              method: "POST",
              body: JSON.stringify({ indicator: c.indicator, params: c.params }),
            });
            previews[c.indicator] = data;
          } catch {
            // ignore
          }
        })
      );
      setIndicatorPreviews(previews);
    }, 800);
    return () => clearTimeout(timeout);
  }, [conditionKey]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── AI Explainer ────────────────────────────────────────────────────────

  const runExplainer = async () => {
    const logic = buildLogicString(conditionGroups, action);
    if (!logic) return;
    setExplainLoading(true);
    try {
      const data = await apiFetch<StrategyExplanation>("/api/explain/strategy", {
        method: "POST",
        body: JSON.stringify({ strategy_logic: logic }),
      });
      setExplanation(data);
    } catch {
      // ignore
    } finally {
      setExplainLoading(false);
    }
  };

  // ── Save / Update ────────────────────────────────────────────────────────

  const saveStrategy = async () => {
    setSaveStatus("saving");
    const payload: Strategy = {
      name,
      description,
      condition_groups: conditionGroups,
      conditions: allValidConditions,   // flat array kept for diagnostics on backend
      action,
      stop_loss_pct: stopLoss / 100,
      take_profit_pct: takeProfit / 100,
      position_size_pct: positionSize / 100,
      timeframe,
      symbols,
      commission_pct: commissionPct / 100,
      slippage_pct: slippagePct / 100,
      trailing_stop_pct: trailingStopEnabled ? trailingStop / 100 : null,
      exit_after_bars: exitAfterBarsEnabled ? exitAfterBars : null,
      cooldown_bars: cooldownBars,
      max_trades_per_day: maxTradesPerDay,
      max_exposure_pct: maxExposurePct / 100,
      max_loss_pct: maxLossPct / 100,
    };

    try {
      if (mode === "edit" && initialStrategy) {
        await apiFetch(`/api/strategies/${initialStrategy.id}`, {
          method: "PATCH",
          body: JSON.stringify(payload),
        });
      } else {
        const created = await apiFetch<{ id: number }>("/api/strategies/create", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        // In create mode, redirect to edit after save so Backtest button becomes available
        setSaveStatus("saved");
        setTimeout(() => router.push(`/edit/${created.id}`), 1200);
        return;
      }
      setSaveStatus("saved");
      setTimeout(() => setSaveStatus("idle"), 3000);
    } catch {
      setSaveStatus("error");
    }
  };

  // ── Derived state ────────────────────────────────────────────────────────

  const logicString = buildLogicString(conditionGroups, action);

  const getCategory = (indicator: string) => {
    const cats: Record<string, string> = {
      rsi: "Momentum", stochastic: "Momentum", macd: "Momentum",
      sma: "Trend", ema: "Trend",
      bollinger_bands: "Volatility", atr: "Volatility",
      vwap: "Volume", obv: "Volume",
    };
    return cats[indicator] || "Momentum";
  };

  const getThresholds = (indicator: string) => {
    const t: Record<string, { overbought?: number; oversold?: number }> = {
      rsi: { overbought: 70, oversold: 30 },
      stochastic: { overbought: 80, oversold: 20 },
    };
    return t[indicator];
  };

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h2 className="text-xl font-semibold">
            {mode === "edit" ? "Edit Strategy" : "Strategy Builder"}
          </h2>
          <p className="text-sm text-muted-foreground mt-0.5">
            {mode === "edit"
              ? `Editing strategy #${initialStrategy?.id}`
              : "Define entry conditions with real-time diagnostics"}
          </p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <button
            type="button"
            onClick={resetBuilder}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
          >
            <RotateCcw className="h-3.5 w-3.5" />
            Reset
          </button>
          <button
            type="button"
            onClick={runExplainer}
            disabled={allValidConditions.length === 0 || explainLoading}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm text-primary border border-primary/20 hover:bg-primary/10 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <Zap className="h-3.5 w-3.5" />
            {explainLoading ? "Analyzing…" : "Analyze"}
          </button>
          {mode === "edit" && initialStrategy && (
            <button
              onClick={() => router.push(`/backtest/${initialStrategy.id}`)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm text-amber-400 border border-amber-400/20 hover:bg-amber-400/10 transition-colors"
            >
              <Play className="h-3.5 w-3.5" />
              Backtest
            </button>
          )}
          <button
            type="button"
            onClick={saveStrategy}
            disabled={allValidConditions.length === 0 || saveStatus === "saving"}
            className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-md bg-primary text-primary-foreground text-sm font-semibold hover:bg-primary/90 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <Save className="h-3.5 w-3.5" />
            {saveStatus === "saving"
              ? "Saving..."
              : saveStatus === "saved"
                ? "Saved ✓"
                : mode === "edit"
                  ? "Update Strategy"
                  : "Save"}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Builder */}
        <div className="lg:col-span-2 space-y-4">
          {/* Name & description */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                Strategy Name
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="mt-1 h-9 w-full rounded-md border border-border/50 bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring/40"
              />
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                Description
              </label>
              <input
                type="text"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Brief description..."
                className="mt-1 h-9 w-full rounded-md border border-border/50 bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring/40"
              />
            </div>
          </div>

          {/* Action + timeframe + position size */}
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                Action
              </label>
              <select
                value={action}
                onChange={(e) => setAction(e.target.value as Action)}
                className="mt-1 h-9 w-full rounded-md border border-border/50 bg-background px-2 text-sm font-medium focus:outline-none focus:ring-2 focus:ring-ring/40"
              >
                <option value="BUY">BUY</option>
                <option value="SELL">SELL</option>
              </select>
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                Timeframe
              </label>
              <select
                value={timeframe}
                onChange={(e) => setTimeframe(e.target.value)}
                className="mt-1 h-9 w-full rounded-md border border-border/50 bg-background px-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring/40"
              >
                {["1m","5m","15m","1H","4H","1D","1W"].map((t) => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                Position %
              </label>
              <input
                type="number"
                value={positionSize}
                onChange={(e) => setPositionSize(parseFloat(e.target.value) || 0)}
                min={1} max={100} step={1}
                className="mt-1 h-9 w-full rounded-md border border-border/50 bg-background px-2 text-sm font-mono text-right focus:outline-none focus:ring-2 focus:ring-ring/40"
              />
            </div>
          </div>

          {/* Condition Groups */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
                Entry Conditions
              </h3>
              <span className="text-xs text-muted-foreground">
                {allValidConditions.length} active
              </span>
            </div>

            {conditionGroups.map((group, gi) => (
              <React.Fragment key={group.id}>
                <ConditionGroupComponent
                  group={group}
                  groupIndex={gi}
                  totalGroups={conditionGroups.length}
                  onAddCondition={addCondition}
                  onRemoveCondition={removeCondition}
                  onUpdateCondition={updateCondition}
                  onRemoveGroup={removeGroup}
                />
                {gi < conditionGroups.length - 1 && (
                  <div className="flex items-center justify-center">
                    <span className="text-[11px] font-bold px-3 py-1 rounded-full bg-amber-400/10 text-amber-400 border border-amber-400/20 uppercase tracking-widest">
                      OR
                    </span>
                  </div>
                )}
              </React.Fragment>
            ))}

            <button
              onClick={addGroup}
              className="w-full flex items-center justify-center gap-1.5 py-2 rounded-lg border border-dashed border-border/50 text-sm text-muted-foreground hover:text-foreground hover:border-amber-400/30 hover:bg-amber-400/5 transition-colors"
            >
              <Plus className="h-3.5 w-3.5" />
              Add OR Group
            </button>
          </div>

          {/* Logic preview */}
          {logicString && (
            <div className="rounded-lg border border-border/50 bg-muted/20 p-3">
              <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1.5">
                Strategy Logic
              </div>
              <code className="text-sm font-mono text-primary break-all">{logicString}</code>
            </div>
          )}

          {/* Indicator previews */}
          {allValidConditions.length > 0 && Object.keys(indicatorPreviews).length > 0 && (
            <div className="space-y-2">
              <div className="text-[10px] text-muted-foreground uppercase tracking-wider">
                Indicator Previews
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {allValidConditions.map((c) => {
                  const preview = indicatorPreviews[c.indicator];
                  if (!preview) return null;
                  const category = getCategory(c.indicator);
                  const thresholds = getThresholds(c.indicator);
                  if (preview.components)
                    return (
                      <IndicatorChart key={c.id} data={[]} label={c.indicator.toUpperCase()}
                        category={category} thresholds={thresholds} multiLine={preview.components} />
                    );
                  if (preview.values)
                    return (
                      <IndicatorChart key={c.id} data={preview.values} label={c.indicator.toUpperCase()}
                        category={category} thresholds={thresholds} />
                    );
                  return null;
                })}
              </div>
            </div>
          )}

          {/* ── Accordions ──────────────────────────────────────────────── */}

          {/* Exit Conditions */}
          <AccordionSection title="Exit Conditions" defaultOpen>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Stop Loss %
                </label>
                <input type="number" value={stopLoss}
                  onChange={(e) => setStopLoss(parseFloat(e.target.value) || 0)}
                  min={0.1} max={50} step={0.5}
                  className="mt-1 h-9 w-full rounded-md border border-border/50 bg-background px-2 text-sm font-mono text-right focus:outline-none focus:ring-2 focus:ring-ring/40" />
              </div>
              <div>
                <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Take Profit %
                </label>
                <input type="number" value={takeProfit}
                  onChange={(e) => setTakeProfit(parseFloat(e.target.value) || 0)}
                  min={0.1} max={100} step={0.5}
                  className="mt-1 h-9 w-full rounded-md border border-border/50 bg-background px-2 text-sm font-mono text-right focus:outline-none focus:ring-2 focus:ring-ring/40" />
              </div>
            </div>
            <div className="space-y-2">
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" checked={trailingStopEnabled}
                  onChange={(e) => setTrailingStopEnabled(e.target.checked)}
                  className="rounded border-border/50" />
                <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Trailing Stop %
                </span>
              </label>
              {trailingStopEnabled && (
                <input type="number" value={trailingStop}
                  onChange={(e) => setTrailingStop(parseFloat(e.target.value) || 0)}
                  min={0.1} max={50} step={0.5}
                  className="h-9 w-32 rounded-md border border-border/50 bg-background px-2 text-sm font-mono text-right focus:outline-none focus:ring-2 focus:ring-ring/40" />
              )}
            </div>
            <div className="space-y-2">
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" checked={exitAfterBarsEnabled}
                  onChange={(e) => setExitAfterBarsEnabled(e.target.checked)}
                  className="rounded border-border/50" />
                <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Exit After N Bars
                </span>
              </label>
              {exitAfterBarsEnabled && (
                <input type="number" value={exitAfterBars}
                  onChange={(e) => setExitAfterBars(parseInt(e.target.value) || 1)}
                  min={1} max={500} step={1}
                  className="h-9 w-32 rounded-md border border-border/50 bg-background px-2 text-sm font-mono text-right focus:outline-none focus:ring-2 focus:ring-ring/40" />
              )}
            </div>
          </AccordionSection>

          {/* Symbol Universe */}
          <AccordionSection
            title="Symbol Universe"
            badge={symbols.length > 0 ? symbols[0] : undefined}
          >
            <div className="flex flex-wrap gap-1.5 mb-2">
              {symbols.map((s) => (
                <span key={s}
                  className="inline-flex items-center gap-1 text-xs font-mono px-2 py-0.5 rounded bg-muted border border-border/50">
                  {s}
                  <button type="button" onClick={() => setSymbols((prev) => prev.filter((x) => x !== s))}
                    className="text-muted-foreground hover:text-red-400 transition-colors ml-0.5">×</button>
                </span>
              ))}
            </div>
            <div className="flex gap-2">
              <input
                type="text"
                value={symbolInput}
                onChange={(e) => setSymbolInput(e.target.value.toUpperCase())}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === ",") {
                    e.preventDefault();
                    addSymbol(symbolInput);
                  }
                }}
                placeholder="Add symbol (Enter)"
                className="h-9 flex-1 rounded-md border border-border/50 bg-background px-3 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-ring/40"
              />
              <button type="button" onClick={() => addSymbol(symbolInput)}
                className="h-9 px-3 rounded-md border border-border/50 text-sm text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors">
                Add
              </button>
            </div>
            <p className="text-xs text-muted-foreground">
              First symbol is used as default for backtesting.
            </p>
          </AccordionSection>

          {/* Execution */}
          <AccordionSection title="Execution Settings">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Commission %
                </label>
                <input type="number" value={commissionPct}
                  onChange={(e) => setCommissionPct(parseFloat(e.target.value) || 0)}
                  min={0} max={5} step={0.01}
                  className="mt-1 h-9 w-full rounded-md border border-border/50 bg-background px-2 text-sm font-mono text-right focus:outline-none focus:ring-2 focus:ring-ring/40" />
              </div>
              <div>
                <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Slippage %
                </label>
                <input type="number" value={slippagePct}
                  onChange={(e) => setSlippagePct(parseFloat(e.target.value) || 0)}
                  min={0} max={5} step={0.01}
                  className="mt-1 h-9 w-full rounded-md border border-border/50 bg-background px-2 text-sm font-mono text-right focus:outline-none focus:ring-2 focus:ring-ring/40" />
              </div>
            </div>
          </AccordionSection>

          {/* Risk Controls */}
          <AccordionSection title="Risk Controls">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Cooldown (bars)
                </label>
                <input type="number" value={cooldownBars}
                  onChange={(e) => setCooldownBars(parseInt(e.target.value) || 0)}
                  min={0} max={500}
                  className="mt-1 h-9 w-full rounded-md border border-border/50 bg-background px-2 text-sm font-mono text-right focus:outline-none focus:ring-2 focus:ring-ring/40" />
                <p className="text-[10px] text-muted-foreground mt-0.5">0 = no cooldown</p>
              </div>
              <div>
                <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Max Trades/Day
                </label>
                <input type="number" value={maxTradesPerDay}
                  onChange={(e) => setMaxTradesPerDay(parseInt(e.target.value) || 0)}
                  min={0} max={100}
                  className="mt-1 h-9 w-full rounded-md border border-border/50 bg-background px-2 text-sm font-mono text-right focus:outline-none focus:ring-2 focus:ring-ring/40" />
                <p className="text-[10px] text-muted-foreground mt-0.5">0 = unlimited</p>
              </div>
              <div>
                <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Max Exposure %
                </label>
                <input type="number" value={maxExposurePct}
                  onChange={(e) => setMaxExposurePct(parseFloat(e.target.value) || 100)}
                  min={1} max={100}
                  className="mt-1 h-9 w-full rounded-md border border-border/50 bg-background px-2 text-sm font-mono text-right focus:outline-none focus:ring-2 focus:ring-ring/40" />
              </div>
              <div>
                <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Daily Loss Limit %
                </label>
                <input type="number" value={maxLossPct}
                  onChange={(e) => setMaxLossPct(parseFloat(e.target.value) || 0)}
                  min={0} max={100} step={0.5}
                  className="mt-1 h-9 w-full rounded-md border border-border/50 bg-background px-2 text-sm font-mono text-right focus:outline-none focus:ring-2 focus:ring-ring/40" />
                <p className="text-[10px] text-muted-foreground mt-0.5">0 = no limit</p>
              </div>
            </div>
          </AccordionSection>
        </div>

        {/* Right: Diagnostics & Explainer */}
        <div className="space-y-4">
          <DiagnosticPanel report={diagnostics} loading={diagLoading} />
          <ExplainerPanel explanation={explanation} loading={explainLoading} />
        </div>
      </div>
    </div>
  );
}
```

**Step 2: Verify TypeScript compiles**

```bash
cd ~/adaptive-trading-ecosystem/frontend
npx tsc --noEmit 2>&1 | grep -v "node_modules" | grep -v ".next" | head -20
```

Expected: no errors in `StrategyBuilder.tsx` or its imports.

**Step 3: Commit**

```bash
git add frontend/src/components/strategy-builder/StrategyBuilder.tsx
git commit -m "feat: rewrite StrategyBuilder with condition groups, accordions, and auth-fixed fetches"
```

---

## Task 8: Update strategies list — metadata and clone

**Files:**
- Modify: `frontend/src/app/strategies/page.tsx`

**Step 1: Replace the entire file**

```tsx
"use client";

import React, { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Trash2, Shield, ChevronRight, Pencil, Play, Copy } from "lucide-react";
import { apiFetch } from "@/lib/api/client";
import type { StrategyRecord } from "@/types/strategy";

function ScoreBadge({ score }: { score: number }) {
  const color =
    score >= 80
      ? "text-emerald-400 bg-emerald-400/10 border-emerald-400/20"
      : score >= 50
        ? "text-amber-400 bg-amber-400/10 border-amber-400/20"
        : "text-red-400 bg-red-400/10 border-red-400/20";
  return (
    <span className={`text-xs font-mono font-bold px-2 py-0.5 rounded border ${color}`}>
      {score}
    </span>
  );
}

function relativeTime(iso: string): string {
  if (!iso) return "";
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

function conditionCount(s: StrategyRecord): number {
  if (s.condition_groups?.length) {
    return s.condition_groups.reduce((sum, g) => sum + (g.conditions?.length ?? 0), 0);
  }
  return s.conditions?.length ?? 0;
}

function conditionSummary(s: StrategyRecord): string {
  if (s.condition_groups?.length) {
    return s.condition_groups
      .map((g) =>
        g.conditions
          .map((c) => `${c.indicator.toUpperCase()} ${c.operator} ${c.value}`)
          .join(" AND ")
      )
      .join(" OR ");
  }
  return s.conditions
    ?.map((c) => `${c.indicator.toUpperCase()} ${c.operator} ${c.value}`)
    .join(" AND ") ?? "";
}

export default function StrategiesPage() {
  const router = useRouter();
  const [strategies, setStrategies] = useState<StrategyRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [cloningId, setCloningId] = useState<number | null>(null);

  const fetchStrategies = useCallback(async () => {
    try {
      const data = await apiFetch<{ strategies: StrategyRecord[] }>("/api/strategies/list");
      setStrategies(data.strategies || []);
    } catch {
      // offline
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchStrategies(); }, [fetchStrategies]);

  const deleteStrategy = async (id: number, e: React.MouseEvent) => {
    e.stopPropagation();
    await apiFetch(`/api/strategies/${id}`, { method: "DELETE" });
    setStrategies((prev) => prev.filter((s) => s.id !== id));
  };

  const cloneStrategy = async (s: StrategyRecord, e: React.MouseEvent) => {
    e.stopPropagation();
    setCloningId(s.id);
    // Optimistic insert
    const tempId = -Date.now();
    const optimistic: StrategyRecord = {
      ...s,
      id: tempId,
      name: `${s.name} (copy)`,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
    setStrategies((prev) => [optimistic, ...prev]);
    try {
      const created = await apiFetch<StrategyRecord>("/api/strategies/create", {
        method: "POST",
        body: JSON.stringify({
          name: `${s.name} (copy)`,
          description: s.description,
          condition_groups: s.condition_groups,
          conditions: s.conditions,
          action: s.action,
          stop_loss_pct: s.stop_loss_pct,
          take_profit_pct: s.take_profit_pct,
          position_size_pct: s.position_size_pct,
          timeframe: s.timeframe,
          symbols: s.symbols,
          commission_pct: s.commission_pct,
          slippage_pct: s.slippage_pct,
          trailing_stop_pct: s.trailing_stop_pct,
          exit_after_bars: s.exit_after_bars,
          cooldown_bars: s.cooldown_bars,
          max_trades_per_day: s.max_trades_per_day,
          max_exposure_pct: s.max_exposure_pct,
          max_loss_pct: s.max_loss_pct,
        }),
      });
      // Replace optimistic with real
      setStrategies((prev) =>
        prev.map((x) => (x.id === tempId ? { ...optimistic, id: created.id } : x))
      );
    } catch {
      // Revert
      setStrategies((prev) => prev.filter((x) => x.id !== tempId));
    } finally {
      setCloningId(null);
    }
  };

  return (
    <>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-xl font-semibold">Saved Strategies</h2>
          <p className="text-sm text-muted-foreground mt-0.5">
            {strategies.length} {strategies.length === 1 ? "strategy" : "strategies"} saved
          </p>
        </div>
        <Link
          href="/"
          className="inline-flex items-center gap-1.5 px-4 py-2 rounded-md bg-primary text-primary-foreground text-sm font-semibold hover:bg-primary/90 transition-colors"
        >
          New Strategy
        </Link>
      </div>

      {loading ? (
        <div className="text-center py-12 text-muted-foreground text-sm">Loading strategies...</div>
      ) : strategies.length === 0 ? (
        <div className="text-center py-12 border border-dashed rounded-lg">
          <Shield className="h-8 w-8 text-muted-foreground/40 mx-auto mb-3" />
          <p className="text-muted-foreground">No strategies yet</p>
          <Link href="/" className="text-primary text-sm mt-1 inline-block hover:underline">
            Create your first strategy
          </Link>
        </div>
      ) : (
        <div className="space-y-2">
          {strategies.map((s) => (
            <div
              key={s.id}
              onClick={() => router.push(`/edit/${s.id}`)}
              className="flex items-start gap-4 p-4 rounded-lg border border-border/50 bg-card hover:border-primary/30 hover:bg-card/80 transition-colors group cursor-pointer"
            >
              <ScoreBadge score={s.diagnostics?.score ?? 0} />

              <div className="flex-1 min-w-0">
                {/* Row 1: Name + badges */}
                <div className="flex items-center gap-2 flex-wrap">
                  <h3 className="font-medium truncate">{s.name}</h3>
                  <span className="text-xs font-mono px-1.5 py-0.5 rounded bg-muted text-muted-foreground">
                    {s.action}
                  </span>
                  <span className="text-xs font-mono px-1.5 py-0.5 rounded bg-muted text-muted-foreground">
                    {s.timeframe}
                  </span>
                  {s.id > 0 && (
                    <span className="text-xs text-muted-foreground/50 font-mono">#{s.id}</span>
                  )}
                </div>
                {/* Row 2: Condition summary */}
                <p className="text-xs text-muted-foreground mt-0.5 truncate">
                  {conditionSummary(s) || "No conditions defined"}
                </p>
                {/* Row 3: Description */}
                {s.description && (
                  <p className="text-xs text-muted-foreground/70 mt-0.5 truncate italic">
                    {s.description}
                  </p>
                )}
                {/* Row 4: Metadata */}
                <div className="flex items-center gap-3 mt-1">
                  <span className="text-[10px] text-muted-foreground/60">
                    {conditionCount(s)} condition{conditionCount(s) !== 1 ? "s" : ""}
                  </span>
                  {s.diagnostics?.total_issues > 0 && (
                    <span className="text-[10px] text-amber-400/80">
                      {s.diagnostics.total_issues} issue{s.diagnostics.total_issues > 1 ? "s" : ""}
                    </span>
                  )}
                  {s.updated_at && (
                    <span className="text-[10px] text-muted-foreground/50">
                      {relativeTime(s.updated_at)}
                    </span>
                  )}
                </div>
              </div>

              <div className="flex items-center gap-1 shrink-0">
                <button
                  onClick={(e) => { e.stopPropagation(); router.push(`/backtest/${s.id}`); }}
                  className="p-1.5 rounded text-muted-foreground/40 hover:text-amber-400 hover:bg-amber-400/10 transition-colors"
                  title="Backtest"
                >
                  <Play className="h-4 w-4" />
                </button>
                <button
                  onClick={(e) => { e.stopPropagation(); router.push(`/edit/${s.id}`); }}
                  className="p-1.5 rounded text-muted-foreground/40 hover:text-primary hover:bg-primary/10 transition-colors"
                  title="Edit"
                >
                  <Pencil className="h-4 w-4" />
                </button>
                <button
                  onClick={(e) => cloneStrategy(s, e)}
                  disabled={cloningId === s.id}
                  className="p-1.5 rounded text-muted-foreground/40 hover:text-sky-400 hover:bg-sky-400/10 transition-colors disabled:opacity-30"
                  title="Clone"
                >
                  <Copy className="h-4 w-4" />
                </button>
                <button
                  onClick={(e) => deleteStrategy(s.id, e)}
                  className="p-1.5 rounded text-muted-foreground/40 hover:text-destructive hover:bg-destructive/10 transition-colors"
                  title="Delete"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
                <ChevronRight className="h-4 w-4 text-muted-foreground/30 group-hover:text-primary transition-colors" />
              </div>
            </div>
          ))}
        </div>
      )}
    </>
  );
}
```

**Step 2: Verify TypeScript**

```bash
cd ~/adaptive-trading-ecosystem/frontend
npx tsc --noEmit 2>&1 | grep "strategies/page" | head -10
```

Expected: no errors.

**Step 3: Commit**

```bash
git add frontend/src/app/strategies/page.tsx
git commit -m "feat: strategies list with metadata, clone, and condition group summary"
```

---

## Task 9: Update backtest page — drawdown tab, benchmark line, create-mode access

**Files:**
- Modify: `frontend/src/app/backtest/[id]/page.tsx`

**Step 1: Replace the backtest page**

Replace the entire file. Key additions:
- `"drawdown"` as a 4th tab
- Benchmark equity line on equity curve (secondary dashed line)
- Commission/slippage display in config form
- Auto-populate `symbol` from strategy's first symbol

```tsx
"use client";

import React, { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Play, Loader2, BarChart3, TrendingUp, List, TrendingDown } from "lucide-react";
import { apiFetch } from "@/lib/api/client";
import { EquityCurveChart } from "@/components/charts/EquityCurveChart";
import type { StrategyRecord } from "@/types/strategy";
import type { BacktestResult, BacktestTrade } from "@/types/backtest";

function MetricCard({ label, value, format }: { label: string; value: number; format?: string }) {
  const formatted = (() => {
    if (format === "percent") return `${(value * 100).toFixed(1)}%`;
    if (format === "ratio") return value.toFixed(3);
    if (format === "currency") return `$${value.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
    if (format === "integer") return value.toString();
    return value.toFixed(2);
  })();
  const isNeg = formatted.startsWith("-");
  return (
    <div className="rounded-lg border bg-card p-4">
      <div className="text-xs text-muted-foreground uppercase tracking-wider">{label}</div>
      <div className={`text-2xl font-mono font-bold mt-1 ${isNeg ? "text-red-400" : ""}`}>
        {formatted}
      </div>
    </div>
  );
}

function TradeRow({ trade }: { trade: BacktestTrade }) {
  const isWin = trade.pnl > 0;
  return (
    <tr className="border-b border-border/50 text-sm">
      <td className="py-2 px-4">{trade.entry_date}</td>
      <td className="py-2 px-4">{trade.exit_date}</td>
      <td className="py-2 px-4 font-mono">${trade.entry_price.toFixed(2)}</td>
      <td className="py-2 px-4 font-mono">${trade.exit_price.toFixed(2)}</td>
      <td className={`py-2 px-4 font-mono font-medium ${isWin ? "text-emerald-400" : "text-red-400"}`}>
        {isWin ? "+" : ""}${trade.pnl.toFixed(2)}
      </td>
      <td className={`py-2 px-4 font-mono text-xs ${isWin ? "text-emerald-400" : "text-red-400"}`}>
        {isWin ? "+" : ""}{trade.pnl_pct.toFixed(1)}%
      </td>
      <td className="py-2 px-4 font-mono text-muted-foreground">{trade.bars_held}d</td>
    </tr>
  );
}

function DrawdownChart({ equityCurve, initialCapital }: {
  equityCurve: { date: string; value: number }[];
  initialCapital: number;
}) {
  // Compute running drawdown series
  let peak = initialCapital;
  const ddSeries = equityCurve.map((pt) => {
    if (pt.value > peak) peak = pt.value;
    const dd = peak > 0 ? ((pt.value - peak) / peak) * 100 : 0;
    return { date: pt.date, value: dd };
  });
  const minDD = Math.min(...ddSeries.map((p) => p.value));

  return (
    <div className="rounded-lg border bg-card p-4">
      <div className="text-xs text-muted-foreground uppercase tracking-wider mb-2">
        Drawdown — Max: {minDD.toFixed(1)}%
      </div>
      {/* Simple SVG drawdown chart */}
      <svg width="100%" height="120" viewBox={`0 0 ${ddSeries.length} 120`}
        preserveAspectRatio="none" className="text-red-400">
        <defs>
          <linearGradient id="ddGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="currentColor" stopOpacity="0.3" />
            <stop offset="100%" stopColor="currentColor" stopOpacity="0.05" />
          </linearGradient>
        </defs>
        <polygon
          fill="url(#ddGrad)"
          points={[
            `0,0`,
            ...ddSeries.map((p, i) => {
              const y = minDD < 0 ? (p.value / minDD) * 115 : 0;
              return `${i},${y}`;
            }),
            `${ddSeries.length - 1},0`,
          ].join(" ")}
        />
        <polyline
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          points={ddSeries.map((p, i) => {
            const y = minDD < 0 ? (p.value / minDD) * 115 : 0;
            return `${i},${y}`;
          }).join(" ")}
        />
      </svg>
    </div>
  );
}

export default function BacktestPage() {
  const params = useParams();
  const id = params.id as string;
  const [strategy, setStrategy] = useState<StrategyRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [activeTab, setActiveTab] = useState<"equity" | "drawdown" | "metrics" | "trades">("equity");

  const [symbol, setSymbol] = useState("SPY");
  const [lookbackDays, setLookbackDays] = useState(252);
  const [initialCapital, setInitialCapital] = useState(100000);

  useEffect(() => {
    async function load() {
      try {
        const data = await apiFetch<StrategyRecord>(`/api/strategies/${id}`);
        setStrategy(data);
        // Pre-fill symbol from strategy universe
        if (data.symbols?.length) setSymbol(data.symbols[0]);
      } catch {
        // ignore
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [id]);

  const runBacktest = async () => {
    setRunning(true);
    setResult(null);
    try {
      const data = await apiFetch<BacktestResult>("/api/strategies/backtest", {
        method: "POST",
        body: JSON.stringify({
          strategy_id: parseInt(id),
          symbol,
          lookback_days: lookbackDays,
          initial_capital: initialCapital,
        }),
      });
      setResult(data);
      setActiveTab("equity");
    } catch {
      // ignore
    } finally {
      setRunning(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold">Backtest</h2>
        <p className="text-sm text-muted-foreground mt-0.5">
          {strategy ? strategy.name : `Strategy #${id}`}
          {result && (
            <span className="ml-2 text-muted-foreground/60 text-xs">
              · commission {((result.commission_pct ?? 0) * 100).toFixed(3)}%
              · slippage {((result.slippage_pct ?? 0) * 100).toFixed(3)}%
              {result.synthetic_data && " · synthetic data"}
            </span>
          )}
        </p>
      </div>

      {/* Config */}
      <div className="grid grid-cols-4 gap-3">
        <div>
          <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Symbol</label>
          <input type="text" value={symbol}
            onChange={(e) => setSymbol(e.target.value.toUpperCase())}
            className="mt-1 h-9 w-full rounded-md border bg-background px-3 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-primary/50" />
        </div>
        <div>
          <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Lookback Days</label>
          <input type="number" value={lookbackDays}
            onChange={(e) => setLookbackDays(parseInt(e.target.value) || 252)}
            min={30} max={1000}
            className="mt-1 h-9 w-full rounded-md border bg-background px-3 text-sm font-mono text-right focus:outline-none focus:ring-2 focus:ring-primary/50" />
        </div>
        <div>
          <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Initial Capital</label>
          <input type="number" value={initialCapital}
            onChange={(e) => setInitialCapital(parseInt(e.target.value) || 100000)}
            min={1000} step={10000}
            className="mt-1 h-9 w-full rounded-md border bg-background px-3 text-sm font-mono text-right focus:outline-none focus:ring-2 focus:ring-primary/50" />
        </div>
        <div className="flex items-end">
          <button onClick={runBacktest} disabled={running}
            className="h-9 w-full inline-flex items-center justify-center gap-1.5 rounded-md bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors disabled:opacity-40">
            {running ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
            {running ? "Running..." : "Run Backtest"}
          </button>
        </div>
      </div>

      {/* Results */}
      {result && (
        <div className="space-y-4">
          <div className="flex gap-1 border-b">
            {([
              { key: "equity" as const, label: "Equity Curve", icon: TrendingUp },
              { key: "drawdown" as const, label: "Drawdown", icon: TrendingDown },
              { key: "metrics" as const, label: "Metrics", icon: BarChart3 },
              { key: "trades" as const, label: "Trades", icon: List },
            ]).map(({ key, label, icon: Icon }) => (
              <button key={key} onClick={() => setActiveTab(key)}
                className={`inline-flex items-center gap-1.5 px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === key
                    ? "border-primary text-foreground"
                    : "border-transparent text-muted-foreground hover:text-foreground"
                }`}>
                <Icon className="h-3.5 w-3.5" />
                {label}
              </button>
            ))}
          </div>

          {activeTab === "equity" && (
            <div>
              <EquityCurveChart data={result.equity_curve} initialCapital={initialCapital} height={400} />
              {result.benchmark_equity_curve?.length > 0 && (
                <p className="text-xs text-muted-foreground mt-2 text-center">
                  Strategy vs buy-and-hold: strategy return{" "}
                  <span className={result.metrics.total_return >= 0 ? "text-emerald-400" : "text-red-400"}>
                    {(result.metrics.total_return * 100).toFixed(1)}%
                  </span>
                  {" "}· buy-and-hold{" "}
                  <span className="text-sky-400">
                    {(((result.benchmark_equity_curve[result.benchmark_equity_curve.length - 1]?.value ?? initialCapital) / initialCapital - 1) * 100).toFixed(1)}%
                  </span>
                </p>
              )}
            </div>
          )}

          {activeTab === "drawdown" && (
            <DrawdownChart equityCurve={result.equity_curve} initialCapital={initialCapital} />
          )}

          {activeTab === "metrics" && (
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
              <MetricCard label="Sharpe Ratio" value={result.metrics.sharpe_ratio} format="ratio" />
              <MetricCard label="Sortino Ratio" value={result.metrics.sortino_ratio} format="ratio" />
              <MetricCard label="Win Rate" value={result.metrics.win_rate} format="percent" />
              <MetricCard label="Max Drawdown" value={result.metrics.max_drawdown} format="percent" />
              <MetricCard label="Total Return" value={result.metrics.total_return} format="percent" />
              <MetricCard label="Total Trades" value={result.metrics.num_trades} format="integer" />
              <MetricCard label="Avg Trade P&L" value={result.metrics.avg_trade_pnl} format="currency" />
              <MetricCard label="Profit Factor" value={result.metrics.profit_factor} format="ratio" />
            </div>
          )}

          {activeTab === "trades" && (
            <div className="rounded-lg border bg-card overflow-x-auto">
              <table className="w-full text-left">
                <thead>
                  <tr className="border-b text-xs text-muted-foreground uppercase tracking-wider">
                    <th className="py-2 px-4">Entry</th>
                    <th className="py-2 px-4">Exit</th>
                    <th className="py-2 px-4">Entry $</th>
                    <th className="py-2 px-4">Exit $</th>
                    <th className="py-2 px-4">P&L</th>
                    <th className="py-2 px-4">Return</th>
                    <th className="py-2 px-4">Bars</th>
                  </tr>
                </thead>
                <tbody>
                  {result.trades.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="py-8 text-center text-muted-foreground text-sm">
                        No trades executed
                      </td>
                    </tr>
                  ) : (
                    result.trades.map((t, i) => <TradeRow key={i} trade={t} />)
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {!result && !running && (
        <div className="text-center py-16 border border-dashed rounded-lg">
          <BarChart3 className="h-8 w-8 text-muted-foreground/40 mx-auto mb-3" />
          <p className="text-muted-foreground">Configure parameters and run a backtest</p>
        </div>
      )}
    </div>
  );
}
```

**Step 2: Verify TypeScript**

```bash
cd ~/adaptive-trading-ecosystem/frontend
npx tsc --noEmit 2>&1 | grep -v "node_modules" | grep -v ".next" | grep "backtest" | head -10
```

Expected: no errors.

**Step 3: Commit**

```bash
git add frontend/src/app/backtest/[id]/page.tsx
git commit -m "feat: backtest page — drawdown tab, benchmark comparison, commission display"
```

---

## Final: Build verification and Docker rebuild

**Step 1: Full TypeScript check**

```bash
cd ~/adaptive-trading-ecosystem/frontend
npx tsc --noEmit 2>&1 | grep -v "node_modules" | grep -v ".next" | grep "error" | head -20
```

Expected: 0 errors (or only pre-existing unrelated errors).

**Step 2: Next.js production build**

```bash
cd ~/adaptive-trading-ecosystem/frontend
npm run build 2>&1 | tail -20
```

Expected: all routes listed, no build errors.

**Step 3: Rebuild Docker frontend image**

```bash
cd ~/adaptive-trading-ecosystem
docker compose up -d --build --force-recreate frontend api 2>&1 | tail -8
```

**Step 4: Smoke test**

```bash
sleep 10
curl -sL -o /dev/null -w "%{http_code}" http://localhost:3000/
curl -sL -o /dev/null -w " %{http_code}" http://localhost:3000/strategies
echo ""
docker compose ps --format "table {{.Name}}\t{{.Status}}"
```

Expected: `200 200` and all containers healthy.

**Step 5: Final commit**

```bash
cd ~/adaptive-trading-ecosystem
git add .
git commit -m "feat: builder + strategies — condition groups, accordions, clone, backtest improvements"
```
