# AI Brain Feature Completion — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the AI Brain feature so AI is an active trader with per-bot model selection, performance tracking, auto-routing, and full UI visibility.

**Architecture:** The foundation exists — AITradingEngine, BotRunner AI routing, BotModelPerformance table, shadow comparison, ModelLeaderboard component, and DeployConfigModal with model selection. What's missing: (1) a performance tracker service to compute aggregated metrics (Sharpe, drawdown), (2) an auto-router that picks the best model based on performance, (3) wiring auto-routing into BotRunner, (4) enhanced API endpoints, and (5) frontend integration of the ModelLeaderboard + model controls into the bot detail page.

**Tech Stack:** Python/FastAPI (backend), SQLAlchemy async (ORM), Next.js 14/React/TypeScript (frontend), SQLite/PostgreSQL (DB)

---

## File Structure

### Backend (new files)
| File | Responsibility |
|------|---------------|
| `services/ai_brain/performance_tracker.py` | Compute aggregated metrics (Sharpe, win rate, avg return, max drawdown) per model per bot from `bot_model_performance` table |
| `services/ai_brain/auto_router.py` | Weighted scoring to pick best model for a bot; fallback + exploration logic |
| `tests/test_performance_tracker.py` | Unit tests for performance tracker |
| `tests/test_auto_router.py` | Unit tests for auto-router |
| `tests/test_ai_brain_integration.py` | Integration test: AI decision → trade execution → performance update → routing |

### Backend (modify)
| File | Change |
|------|--------|
| `db/cerberus_models.py` | Add `auto_route_enabled` column to `CerberusBot` |
| `alembic/versions/011_auto_routing.py` | Migration for new column |
| `services/bot_engine/runner.py` | Call auto-router before AI evaluation if enabled |
| `api/routes/ai_tools.py` | Enhance model-comparison endpoint; add auto-route toggle endpoint |

### Frontend (modify)
| File | Change |
|------|--------|
| `frontend/src/app/bots/[id]/page.tsx` | Mount ModelLeaderboard + model controls on bot detail page |
| `frontend/src/components/bots/ModelLeaderboard.tsx` | Add Sharpe, drawdown columns; add auto-optimize toggle |
| `frontend/src/components/bots/BotModelSettings.tsx` | **New** — model dropdown + auto-optimize toggle for inline bot settings |
| `frontend/src/lib/cerberus-api.ts` | Add API calls for model settings, auto-route toggle |

---

## Task 1: Performance Tracker Service

**Files:**
- Create: `services/ai_brain/performance_tracker.py`
- Test: `tests/test_performance_tracker.py`

This service queries `bot_model_performance` rows, computes aggregated metrics per model per bot.

- [ ] **Step 1: Write failing test for compute_model_metrics**

```python
# tests/test_performance_tracker.py
import pytest
from unittest.mock import AsyncMock, patch
from services.ai_brain.performance_tracker import compute_model_metrics

def test_compute_model_metrics_basic():
    """Given resolved decisions with P&L, compute win_rate, avg_return, sharpe, drawdown."""
    mock_rows = [
        {"pnl": 10.0, "confidence": 0.8, "decided_at": "2026-03-20T10:00:00"},
        {"pnl": -5.0, "confidence": 0.6, "decided_at": "2026-03-20T11:00:00"},
        {"pnl": 15.0, "confidence": 0.9, "decided_at": "2026-03-20T12:00:00"},
        {"pnl": -3.0, "confidence": 0.5, "decided_at": "2026-03-20T13:00:00"},
        {"pnl": 8.0, "confidence": 0.7, "decided_at": "2026-03-20T14:00:00"},
    ]
    metrics = compute_model_metrics(mock_rows)
    assert metrics["trades_count"] == 5
    assert metrics["win_rate"] == 0.6  # 3 wins out of 5
    assert round(metrics["avg_return"], 2) == 5.0  # (10 - 5 + 15 - 3 + 8) / 5
    assert metrics["max_drawdown"] < 0  # should be negative
    assert "sharpe_ratio" in metrics

def test_compute_model_metrics_empty():
    metrics = compute_model_metrics([])
    assert metrics["trades_count"] == 0
    assert metrics["win_rate"] == 0.0
    assert metrics["sharpe_ratio"] == 0.0

def test_compute_model_metrics_all_wins():
    mock_rows = [
        {"pnl": 10.0, "confidence": 0.8, "decided_at": "2026-03-20T10:00:00"},
        {"pnl": 5.0, "confidence": 0.9, "decided_at": "2026-03-20T11:00:00"},
    ]
    metrics = compute_model_metrics(mock_rows)
    assert metrics["win_rate"] == 1.0
    assert metrics["max_drawdown"] == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/adaptive-trading-ecosystem && python -m pytest tests/test_performance_tracker.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'services.ai_brain.performance_tracker'`

- [ ] **Step 3: Implement performance_tracker.py**

```python
# services/ai_brain/performance_tracker.py
"""Aggregated performance metrics per model per bot."""
from __future__ import annotations

import math
from datetime import datetime
from typing import Optional

import structlog
from sqlalchemy import select, func, and_

from db.database import get_session
from db.cerberus_models import BotModelPerformance

logger = structlog.get_logger(__name__)


def compute_model_metrics(rows: list[dict]) -> dict:
    """Compute aggregated metrics from a list of resolved decision dicts.

    Each dict must have: pnl (float), confidence (float), decided_at (str).
    Returns: trades_count, win_rate, avg_return, sharpe_ratio, max_drawdown, total_pnl, avg_confidence.
    """
    if not rows:
        return {
            "trades_count": 0,
            "win_rate": 0.0,
            "avg_return": 0.0,
            "sharpe_ratio": 0.0,
            "max_drawdown": 0.0,
            "total_pnl": 0.0,
            "avg_confidence": 0.0,
        }

    pnls = [float(r["pnl"]) for r in rows]
    confidences = [float(r.get("confidence") or 0) for r in rows]

    trades_count = len(pnls)
    wins = sum(1 for p in pnls if p > 0)
    win_rate = round(wins / trades_count, 4)
    avg_return = round(sum(pnls) / trades_count, 4)
    total_pnl = round(sum(pnls), 4)
    avg_confidence = round(sum(confidences) / trades_count, 4) if confidences else 0.0

    # Sharpe ratio: mean(pnl) / std(pnl) * sqrt(252) — annualized
    # Use sample standard deviation (N-1) per financial convention
    mean_pnl = sum(pnls) / trades_count
    if trades_count < 2:
        sharpe_ratio = 0.0
    else:
        variance = sum((p - mean_pnl) ** 2 for p in pnls) / (trades_count - 1)
        std_pnl = math.sqrt(variance)
        sharpe_ratio = round((mean_pnl / std_pnl) * math.sqrt(252), 4) if std_pnl > 0 else 0.0

    # Max drawdown: peak-to-trough of cumulative P&L
    cumulative = 0.0
    peak = 0.0
    max_dd = 0.0
    for p in pnls:
        cumulative += p
        if cumulative > peak:
            peak = cumulative
        dd = cumulative - peak
        if dd < max_dd:
            max_dd = dd
    max_drawdown = round(max_dd, 4)

    return {
        "trades_count": trades_count,
        "win_rate": win_rate,
        "avg_return": avg_return,
        "sharpe_ratio": sharpe_ratio,
        "max_drawdown": max_drawdown,
        "total_pnl": total_pnl,
        "avg_confidence": avg_confidence,
    }


async def get_bot_model_metrics(bot_id: str) -> dict[str, dict]:
    """Query resolved decisions from DB and compute metrics per model.

    Returns: {"gpt-5.4": {metrics}, "claude-sonnet-4-6": {metrics}, ...}
    """
    async with get_session() as session:
        result = await session.execute(
            select(
                BotModelPerformance.model_used,
                BotModelPerformance.pnl,
                BotModelPerformance.confidence,
                BotModelPerformance.decided_at,
            )
            .where(
                BotModelPerformance.bot_id == bot_id,
                BotModelPerformance.resolved_at.isnot(None),
                BotModelPerformance.pnl.isnot(None),
            )
            .order_by(BotModelPerformance.decided_at)
        )
        rows = result.all()

    # Group by model
    by_model: dict[str, list[dict]] = {}
    for row in rows:
        model = row.model_used
        by_model.setdefault(model, []).append({
            "pnl": row.pnl,
            "confidence": row.confidence,
            "decided_at": row.decided_at.isoformat() if row.decided_at else "",
        })

    return {model: compute_model_metrics(decisions) for model, decisions in by_model.items()}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/adaptive-trading-ecosystem && python -m pytest tests/test_performance_tracker.py -v`
Expected: PASS (all 3 tests)

- [ ] **Step 5: Commit**

```bash
cd ~/adaptive-trading-ecosystem
git add services/ai_brain/performance_tracker.py tests/test_performance_tracker.py
git commit -m "feat: add performance tracker service for per-model metric aggregation"
```

---

## Task 2: Auto-Router Service

**Files:**
- Create: `services/ai_brain/auto_router.py`
- Test: `tests/test_auto_router.py`

The auto-router picks the best model for a bot based on a weighted score of aggregated metrics.

- [ ] **Step 1: Write failing test for select_best_model**

```python
# tests/test_auto_router.py
import pytest
from unittest.mock import AsyncMock, patch
from services.ai_brain.auto_router import select_best_model, score_model

def test_score_model_strong_performer():
    metrics = {
        "win_rate": 0.65,
        "avg_return": 8.0,
        "sharpe_ratio": 1.5,
        "max_drawdown": -5.0,
        "trades_count": 20,
    }
    score = score_model(metrics)
    assert score > 0

def test_score_model_weights():
    """Higher win rate should produce higher score than higher drawdown."""
    good = {"win_rate": 0.7, "avg_return": 5.0, "sharpe_ratio": 1.2, "max_drawdown": -3.0, "trades_count": 15}
    bad = {"win_rate": 0.3, "avg_return": -2.0, "sharpe_ratio": -0.5, "max_drawdown": -15.0, "trades_count": 15}
    assert score_model(good) > score_model(bad)

def test_score_model_insufficient_data():
    """Models with < MIN_TRADES should return -inf."""
    metrics = {"win_rate": 0.9, "avg_return": 20.0, "sharpe_ratio": 3.0, "max_drawdown": 0.0, "trades_count": 2}
    score = score_model(metrics)
    assert score == float("-inf")

@pytest.mark.asyncio
async def test_select_best_model_picks_highest_score():
    mock_metrics = {
        "gpt-5.4": {"win_rate": 0.5, "avg_return": 3.0, "sharpe_ratio": 0.8, "max_drawdown": -5.0, "trades_count": 20},
        "claude-sonnet-4-6": {"win_rate": 0.7, "avg_return": 8.0, "sharpe_ratio": 1.5, "max_drawdown": -2.0, "trades_count": 20},
    }
    with patch("services.ai_brain.auto_router.get_bot_model_metrics", new_callable=AsyncMock, return_value=mock_metrics):
        result = await select_best_model("bot-123", default_model="gpt-5.4")
    assert result == "claude-sonnet-4-6"

@pytest.mark.asyncio
async def test_select_best_model_fallback_on_no_data():
    with patch("services.ai_brain.auto_router.get_bot_model_metrics", new_callable=AsyncMock, return_value={}):
        result = await select_best_model("bot-123", default_model="gpt-5.4")
    assert result == "gpt-5.4"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/adaptive-trading-ecosystem && python -m pytest tests/test_auto_router.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement auto_router.py**

```python
# services/ai_brain/auto_router.py
"""Auto-routing: select the best-performing AI model for a bot."""
from __future__ import annotations

import structlog

from services.ai_brain.performance_tracker import get_bot_model_metrics

logger = structlog.get_logger(__name__)

# Minimum resolved trades before a model is eligible for routing
MIN_TRADES = 5

# Scoring weights
W_WIN_RATE = 0.4
W_AVG_RETURN = 0.3
W_SHARPE = 0.2
W_DRAWDOWN = 0.1  # penalty — subtracted


def score_model(metrics: dict) -> float:
    """Compute weighted composite score for a model.

    score = (win_rate * 0.4) + (normalized_avg_return * 0.3)
            + (normalized_sharpe * 0.2) - (normalized_drawdown * 0.1)

    Returns float('-inf') if insufficient data.
    """
    if metrics.get("trades_count", 0) < MIN_TRADES:
        return float("-inf")

    win_rate = float(metrics.get("win_rate", 0))
    avg_return = float(metrics.get("avg_return", 0))
    sharpe = float(metrics.get("sharpe_ratio", 0))
    drawdown = abs(float(metrics.get("max_drawdown", 0)))

    # Normalize avg_return and sharpe to 0-1 range using sigmoid-like scaling
    norm_return = avg_return / (abs(avg_return) + 10)  # maps to (-1, 1) range
    norm_sharpe = sharpe / (abs(sharpe) + 2)            # maps to (-1, 1) range
    norm_drawdown = drawdown / (drawdown + 10)           # maps to (0, 1) range

    score = (
        W_WIN_RATE * win_rate
        + W_AVG_RETURN * norm_return
        + W_SHARPE * norm_sharpe
        - W_DRAWDOWN * norm_drawdown
    )
    return round(score, 6)


async def select_best_model(bot_id: str, default_model: str = "gpt-5.4") -> str:
    """Select the best model for a bot based on performance metrics.

    Returns the model name with the highest composite score.
    Falls back to default_model if no models have sufficient data.
    """
    try:
        metrics_by_model = await get_bot_model_metrics(bot_id)
    except Exception as e:
        logger.error("auto_router_metrics_error", bot_id=bot_id, error=str(e))
        return default_model

    if not metrics_by_model:
        logger.info("auto_router_no_data", bot_id=bot_id, fallback=default_model)
        return default_model

    scored = {}
    for model, metrics in metrics_by_model.items():
        s = score_model(metrics)
        scored[model] = s
        logger.debug("auto_router_score", bot_id=bot_id, model=model, score=s, metrics=metrics)

    # Filter out models with insufficient data
    eligible = {m: s for m, s in scored.items() if s != float("-inf")}

    if not eligible:
        logger.info("auto_router_insufficient_data", bot_id=bot_id, fallback=default_model)
        return default_model

    best = max(eligible, key=eligible.get)
    logger.info("auto_router_selected", bot_id=bot_id, model=best, score=eligible[best])
    return best
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/adaptive-trading-ecosystem && python -m pytest tests/test_auto_router.py -v`
Expected: PASS (all 5 tests)

- [ ] **Step 5: Commit**

```bash
cd ~/adaptive-trading-ecosystem
git add services/ai_brain/auto_router.py tests/test_auto_router.py
git commit -m "feat: add auto-router for model selection based on performance"
```

---

## Task 3: Database Migration — Add auto_route_enabled

**Files:**
- Create: `alembic/versions/011_auto_routing.py`
- Modify: `db/cerberus_models.py`

- [ ] **Step 1: Add column to CerberusBot model**

In `db/cerberus_models.py`, add after `ai_brain_config` column (line ~262):
```python
    auto_route_enabled = Column(Boolean, default=False, server_default=text("0"))
```
Also add `text` to the sqlalchemy imports at the top if not present (check first — it may already be imported via `from sqlalchemy import ... text`).

- [ ] **Step 2: Create migration**

```python
# alembic/versions/011_auto_routing.py
"""Add auto_route_enabled to cerberus_bots

Revision ID: 011_auto_routing
Revises: 010_ai_brain
Create Date: 2026-03-23
"""

revision = "011_auto_routing"
down_revision = "010_ai_brain"

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column(
        "cerberus_bots",
        sa.Column("auto_route_enabled", sa.Boolean, server_default=sa.text("0"), nullable=False),
    )


def downgrade():
    op.drop_column("cerberus_bots", "auto_route_enabled")
```

- [ ] **Step 3: Run migration**

Run: `cd ~/adaptive-trading-ecosystem && python -m alembic upgrade head`
Expected: Migration applies successfully

- [ ] **Step 4: Commit**

```bash
cd ~/adaptive-trading-ecosystem
git add db/cerberus_models.py alembic/versions/011_auto_routing.py
git commit -m "feat: add auto_route_enabled column to CerberusBot"
```

---

## Task 4: Wire Auto-Router into BotRunner

**Files:**
- Modify: `services/bot_engine/runner.py` (~line 277-310)

The BotRunner's `_evaluate_bot` method already routes through AITradingEngine when `ai_brain_config` is set. We need to insert auto-routing model selection before the AI engine call.

- [ ] **Step 1: Add auto-router import and call in BotRunner**

In `runner.py`, at the top imports section, add:
```python
from services.ai_brain.auto_router import select_best_model
```

Then in `_evaluate_bot`, inside the `if bot.ai_brain_config:` block (around line 277-310), BEFORE calling `self._ai_engine.evaluate()`, add model override logic:

Replace the section from line 300 (market_state building) through line 307 (decision = await) with:

```python
                # Auto-route: pick best model if enabled
                model_override = None
                if bot.auto_route_enabled:
                    brain_cfg = AIBrainConfig.from_json(bot.ai_brain_config)
                    model_override = await select_best_model(
                        bot.id, default_model=brain_cfg.primary_model,
                    )
                    if model_override != brain_cfg.primary_model:
                        logger.info(
                            "auto_router_override",
                            bot_id=bot.id,
                            default=brain_cfg.primary_model,
                            selected=model_override,
                        )

                market_state = {
                    "symbols": symbols,
                    "user_id": bot.user_id,
                    "macro": risk_context,
                    "portfolio": risk_context,
                }

                decision = await self._ai_engine.evaluate(
                    bot, market_state, model_override=model_override,
                )
```

Also add import for AIBrainConfig at the top if not already there:
```python
from services.ai_brain.types import AITradeDecision, AIBrainConfig
```

- [ ] **Step 2: Verify BotRunner still starts**

Run: `cd ~/adaptive-trading-ecosystem && python -c "from services.bot_engine.runner import BotRunner; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
cd ~/adaptive-trading-ecosystem
git add services/bot_engine/runner.py
git commit -m "feat: wire auto-router into BotRunner for dynamic model selection"
```

---

## Task 5: Enhanced API Endpoints

**Files:**
- Modify: `api/routes/ai_tools.py`

Enhance the model-comparison endpoint with Sharpe/drawdown, add auto-route toggle, add bot model settings endpoint.

- [ ] **Step 1: Enhance model-comparison endpoint**

Replace the existing `model_comparison` function (line ~1311-1375) to use performance_tracker:

```python
@router.get("/bots/{bot_id}/model-comparison")
async def model_comparison(bot_id: str, request: Request):
    """Get model comparison leaderboard with full metrics for a bot."""
    user_id = request.state.user_id
    from db.cerberus_models import CerberusBot

    async with get_session() as session:
        bot_result = await session.execute(
            select(CerberusBot).where(
                CerberusBot.id == bot_id,
                CerberusBot.user_id == user_id,
            )
        )
        bot = bot_result.scalar_one_or_none()
        if not bot:
            raise HTTPException(status_code=404, detail="Bot not found")
        # Capture values inside session to avoid DetachedInstanceError
        primary_model = (bot.ai_brain_config or {}).get("model_config", {}).get("primary_model", "")
        auto_route_enabled = bool(bot.auto_route_enabled)

    from services.ai_brain.performance_tracker import get_bot_model_metrics
    metrics_by_model = await get_bot_model_metrics(bot_id)

    models = []
    for model_name, metrics in metrics_by_model.items():
        models.append({
            "model": model_name,
            "is_primary": model_name == primary_model,
            "trades_count": metrics["trades_count"],
            "win_rate": metrics["win_rate"],
            "avg_return": metrics["avg_return"],
            "sharpe_ratio": metrics["sharpe_ratio"],
            "max_drawdown": metrics["max_drawdown"],
            "total_pnl": metrics["total_pnl"],
            "avg_confidence": metrics["avg_confidence"],
        })

    # Sort by composite score descending
    from services.ai_brain.auto_router import score_model
    models.sort(key=lambda m: score_model(m), reverse=True)

    return {
        "bot_id": bot_id,
        "auto_route_enabled": auto_route_enabled,
        "models": models,
    }
```

- [ ] **Step 2: Add auto-route toggle endpoint**

Add after the model-comparison endpoint:

```python
@router.patch("/bots/{bot_id}/auto-route")
async def toggle_auto_route(bot_id: str, request: Request):
    """Enable or disable auto-routing for a bot."""
    user_id = request.state.user_id
    body = await request.json()
    enabled = bool(body.get("enabled", False))

    async with get_session() as session:
        result = await session.execute(
            select(CerberusBot).where(
                CerberusBot.id == bot_id,
                CerberusBot.user_id == user_id,
            )
        )
        bot = result.scalar_one_or_none()
        if not bot:
            raise HTTPException(status_code=404, detail="Bot not found")
        bot.auto_route_enabled = enabled

    return {"bot_id": bot_id, "auto_route_enabled": enabled}
```

- [ ] **Step 3: Add recent decisions endpoint (for live feed)**

Add after auto-route endpoint:

```python
@router.get("/bots/{bot_id}/recent-decisions")
async def recent_decisions(bot_id: str, request: Request, limit: int = 20):
    """Get recent AI decisions for the live decision feed."""
    user_id = request.state.user_id
    from db.cerberus_models import BotModelPerformance

    async with get_session() as session:
        bot_result = await session.execute(
            select(CerberusBot).where(
                CerberusBot.id == bot_id,
                CerberusBot.user_id == user_id,
            )
        )
        if not bot_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Bot not found")

        result = await session.execute(
            select(BotModelPerformance)
            .where(BotModelPerformance.bot_id == bot_id)
            .order_by(BotModelPerformance.decided_at.desc())
            .limit(min(limit, 50))
        )
        decisions = result.scalars().all()

    return {
        "bot_id": bot_id,
        "decisions": [
            {
                "id": d.id,
                "model_used": d.model_used,
                "symbol": d.symbol,
                "action": d.action,
                "confidence": d.confidence,
                "reasoning_summary": d.reasoning_summary,
                "entry_price": d.entry_price,
                "pnl": d.pnl,
                "is_shadow": d.is_shadow,
                "decided_at": d.decided_at.isoformat() if d.decided_at else None,
                "resolved_at": d.resolved_at.isoformat() if d.resolved_at else None,
            }
            for d in decisions
        ],
    }
```

- [ ] **Step 4: Verify endpoints import correctly**

Run: `cd ~/adaptive-trading-ecosystem && python -c "from api.routes.ai_tools import router; print('OK')"`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
cd ~/adaptive-trading-ecosystem
git add api/routes/ai_tools.py
git commit -m "feat: enhanced model-comparison with Sharpe/drawdown, auto-route toggle, live decisions feed"
```

---

## Task 6: Frontend — BotModelSettings Component

**Files:**
- Create: `frontend/src/components/bots/BotModelSettings.tsx`
- Modify: `frontend/src/lib/cerberus-api.ts`

- [ ] **Step 1: Add API functions to cerberus-api.ts**

Add to `cerberus-api.ts`:

```typescript
export async function updateBotModel(botId: string, model: string): Promise<void> {
  await apiFetch(`/api/ai/tools/bots/${botId}/ai-config`, {
    method: "PATCH",
    body: JSON.stringify({ model_config: { primary_model: model } }),
  });
}

export async function toggleAutoRoute(botId: string, enabled: boolean): Promise<void> {
  await apiFetch(`/api/ai/tools/bots/${botId}/auto-route`, {
    method: "PATCH",
    body: JSON.stringify({ enabled }),
  });
}

export interface ModelComparisonData {
  bot_id: string;
  auto_route_enabled: boolean;
  models: {
    model: string;
    is_primary: boolean;
    trades_count: number;
    win_rate: number;
    avg_return: number;
    sharpe_ratio: number;
    max_drawdown: number;
    total_pnl: number;
    avg_confidence: number;
  }[];
}

export async function getModelComparison(botId: string): Promise<ModelComparisonData> {
  return apiFetch(`/api/ai/tools/bots/${botId}/model-comparison`);
}

export interface AIDecisionItem {
  id: string;
  model_used: string;
  symbol: string;
  action: string;
  confidence: number;
  reasoning_summary: string;
  entry_price: number | null;
  pnl: number | null;
  is_shadow: boolean;
  decided_at: string | null;
  resolved_at: string | null;
}

export async function getRecentDecisions(botId: string, limit?: number): Promise<{ decisions: AIDecisionItem[] }> {
  const params = limit ? `?limit=${limit}` : "";
  return apiFetch(`/api/ai/tools/bots/${botId}/recent-decisions${params}`);
}
```

- [ ] **Step 2: Create BotModelSettings component**

```tsx
// frontend/src/components/bots/BotModelSettings.tsx
"use client";

import { useState, useEffect } from "react";
import { Cpu, Zap } from "lucide-react";
import { updateBotModel, toggleAutoRoute } from "@/lib/cerberus-api";

const AI_MODELS = [
  { value: "gpt-5.4", label: "GPT-5.4" },
  { value: "claude-sonnet-4-6", label: "Claude Sonnet 4.6" },
  { value: "gpt-4.1", label: "GPT-4.1 (Fast)" },
  { value: "deepseek-r1", label: "DeepSeek R1" },
];

interface BotModelSettingsProps {
  botId: string;
  currentModel: string;
  autoRouteEnabled: boolean;
  onUpdate?: () => void;
}

export function BotModelSettings({
  botId,
  currentModel,
  autoRouteEnabled: initialAutoRoute,
  onUpdate,
}: BotModelSettingsProps) {
  const [model, setModel] = useState(currentModel);
  const [autoRoute, setAutoRoute] = useState(initialAutoRoute);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setModel(currentModel);
    setAutoRoute(initialAutoRoute);
  }, [currentModel, initialAutoRoute]);

  const handleModelChange = async (newModel: string) => {
    setSaving(true);
    try {
      await updateBotModel(botId, newModel);
      setModel(newModel);
      onUpdate?.();
    } catch {
      // revert
    } finally {
      setSaving(false);
    }
  };

  const handleAutoRouteToggle = async () => {
    setSaving(true);
    try {
      const newVal = !autoRoute;
      await toggleAutoRoute(botId, newVal);
      setAutoRoute(newVal);
      onUpdate?.();
    } catch {
      // revert
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="app-panel p-4">
      <div className="flex items-center gap-2 mb-3">
        <Cpu className="h-4 w-4 text-violet-400" />
        <h3 className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
          AI Model
        </h3>
      </div>

      <div className="space-y-3">
        <div>
          <label className="app-label mb-1.5 block text-[11px]">Primary Model</label>
          <select
            value={model}
            onChange={(e) => handleModelChange(e.target.value)}
            disabled={saving || autoRoute}
            className="app-select text-sm"
          >
            {AI_MODELS.map((m) => (
              <option key={m.value} value={m.value}>{m.label}</option>
            ))}
          </select>
          {autoRoute && (
            <p className="mt-1 text-[10px] text-muted-foreground">
              Auto-routing active — model selected automatically
            </p>
          )}
        </div>

        <label className="flex items-center gap-3 cursor-pointer group">
          <div className="relative">
            <input
              type="checkbox"
              checked={autoRoute}
              onChange={handleAutoRouteToggle}
              disabled={saving}
              className="peer sr-only"
            />
            <div className="h-5 w-9 rounded-full border border-border/60 bg-muted/30 transition-colors peer-checked:border-violet-400/40 peer-checked:bg-violet-400/20" />
            <div className="absolute left-0.5 top-0.5 h-4 w-4 rounded-full bg-muted-foreground/60 transition-all peer-checked:translate-x-4 peer-checked:bg-violet-400" />
          </div>
          <div>
            <span className="text-sm text-muted-foreground group-hover:text-foreground transition-colors flex items-center gap-1.5">
              <Zap className="h-3 w-3" /> Auto-Optimize Model
            </span>
            <p className="text-[10px] text-muted-foreground/70">
              Automatically switch to the best-performing model
            </p>
          </div>
        </label>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
cd ~/adaptive-trading-ecosystem/frontend
git add src/components/bots/BotModelSettings.tsx src/lib/cerberus-api.ts
git commit -m "feat: add BotModelSettings component and API functions"
```

---

## Task 7: Frontend — Enhanced ModelLeaderboard + Live Decision Feed

**Files:**
- Modify: `frontend/src/components/bots/ModelLeaderboard.tsx`
- Create: `frontend/src/components/bots/LiveDecisionFeed.tsx`

- [ ] **Step 1: Rewrite ModelLeaderboard with full metrics**

Replace `ModelLeaderboard.tsx` with enhanced version that uses the new `getModelComparison` API and shows Sharpe, drawdown, and highlights best model:

```tsx
"use client";

import React, { useEffect, useState } from "react";
import { Trophy, ArrowUpRight, TrendingUp, TrendingDown } from "lucide-react";
import { getModelComparison, updateBotModel, type ModelComparisonData } from "@/lib/cerberus-api";

interface ModelLeaderboardProps {
  botId: string;
  onUpdate?: () => void;
}

export function ModelLeaderboard({ botId, onUpdate }: ModelLeaderboardProps) {
  const [data, setData] = useState<ModelComparisonData | null>(null);
  const [loading, setLoading] = useState(true);

  const load = () => {
    setLoading(true);
    getModelComparison(botId)
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(load, [botId]);

  const handlePromote = async (model: string) => {
    if (!confirm(`Switch primary model to ${model}?`)) return;
    await updateBotModel(botId, model);
    load();
    onUpdate?.();
  };

  if (loading) return <div className="text-sm text-zinc-500 p-4">Loading model data...</div>;
  if (!data || data.models.length === 0) return <div className="text-sm text-zinc-500 p-4">No model comparison data yet.</div>;

  const bestIdx = data.models.findIndex((_, i) => i === 0); // Already sorted by score

  return (
    <div className="rounded-lg border border-border bg-muted/15 overflow-hidden">
      <div className="px-4 py-3 border-b border-border flex items-center gap-2">
        <Trophy className="w-4 h-4 text-yellow-400" />
        <h3 className="text-sm font-medium text-zinc-200">Model Leaderboard</h3>
        {data.auto_route_enabled && (
          <span className="ml-auto text-[10px] text-violet-400 bg-violet-500/10 px-2 py-0.5 rounded-full">
            Auto-routing active
          </span>
        )}
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-zinc-700 text-xs text-zinc-400">
              <th className="px-3 py-2 text-left">Model</th>
              <th className="px-3 py-2 text-right">Trades</th>
              <th className="px-3 py-2 text-right">Win Rate</th>
              <th className="px-3 py-2 text-right">Avg Return</th>
              <th className="px-3 py-2 text-right">Sharpe</th>
              <th className="px-3 py-2 text-right">Drawdown</th>
              <th className="px-3 py-2 text-right">Total P&L</th>
              <th className="px-3 py-2 text-right"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-700/50">
            {data.models.map((m, i) => (
              <tr key={m.model} className={`hover:bg-zinc-700/20 ${i === bestIdx ? "bg-emerald-400/5" : ""}`}>
                <td className="px-3 py-2 text-zinc-200 font-mono text-xs">
                  {m.model}
                  {m.is_primary && (
                    <span className="ml-2 text-[9px] text-blue-400 bg-blue-500/10 px-1.5 py-0.5 rounded">
                      primary
                    </span>
                  )}
                  {i === bestIdx && (
                    <span className="ml-1 text-[9px] text-emerald-400 bg-emerald-500/10 px-1.5 py-0.5 rounded">
                      best
                    </span>
                  )}
                </td>
                <td className="px-3 py-2 text-right text-zinc-300 tabular-nums">{m.trades_count}</td>
                <td className="px-3 py-2 text-right tabular-nums">
                  <span className={m.win_rate >= 0.5 ? "text-green-400" : "text-red-400"}>
                    {(m.win_rate * 100).toFixed(0)}%
                  </span>
                </td>
                <td className="px-3 py-2 text-right tabular-nums">
                  <span className={m.avg_return >= 0 ? "text-green-400" : "text-red-400"}>
                    ${m.avg_return.toFixed(2)}
                  </span>
                </td>
                <td className="px-3 py-2 text-right tabular-nums">
                  <span className={m.sharpe_ratio >= 1 ? "text-green-400" : m.sharpe_ratio >= 0 ? "text-zinc-300" : "text-red-400"}>
                    {m.sharpe_ratio.toFixed(2)}
                  </span>
                </td>
                <td className="px-3 py-2 text-right tabular-nums">
                  <span className="text-red-400">{m.max_drawdown.toFixed(2)}</span>
                </td>
                <td className="px-3 py-2 text-right tabular-nums">
                  <span className={m.total_pnl >= 0 ? "text-green-400" : "text-red-400"}>
                    ${m.total_pnl.toFixed(2)}
                  </span>
                </td>
                <td className="px-3 py-2 text-right">
                  {!m.is_primary && (
                    <button
                      onClick={() => handlePromote(m.model)}
                      className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1"
                    >
                      <ArrowUpRight className="w-3 h-3" /> Use
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create LiveDecisionFeed component**

```tsx
// frontend/src/components/bots/LiveDecisionFeed.tsx
"use client";

import { useEffect, useState } from "react";
import { Activity } from "lucide-react";
import { getRecentDecisions, type AIDecisionItem } from "@/lib/cerberus-api";

const ACTION_COLORS: Record<string, string> = {
  BUY: "text-emerald-400 bg-emerald-400/10 border-emerald-400/20",
  SELL: "text-rose-400 bg-rose-400/10 border-rose-400/20",
  EXIT: "text-amber-400 bg-amber-400/10 border-amber-400/20",
  HOLD: "text-zinc-400 bg-zinc-400/10 border-zinc-400/20",
};

export function LiveDecisionFeed({ botId }: { botId: string }) {
  const [decisions, setDecisions] = useState<AIDecisionItem[]>([]);

  useEffect(() => {
    const load = () => {
      getRecentDecisions(botId, 15).then((r) => setDecisions(r.decisions)).catch(() => {});
    };
    load();
    const interval = setInterval(load, 30_000);
    return () => clearInterval(interval);
  }, [botId]);

  return (
    <div className="app-panel overflow-hidden">
      <div className="px-4 py-3 border-b border-border flex items-center gap-2">
        <Activity className="w-4 h-4 text-sky-400" />
        <h3 className="text-sm font-medium text-zinc-200">AI Decision Feed</h3>
        <span className="ml-auto text-[10px] text-muted-foreground">{decisions.length} recent</span>
      </div>
      <div className="max-h-[400px] overflow-y-auto divide-y divide-border/30">
        {decisions.length === 0 ? (
          <div className="px-4 py-6 text-center text-sm text-muted-foreground">
            No AI decisions recorded yet
          </div>
        ) : (
          decisions.map((d) => (
            <div key={d.id} className="px-4 py-3 hover:bg-muted/10">
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className={`rounded-full border px-2 py-0.5 text-[9px] font-bold uppercase ${ACTION_COLORS[d.action] ?? ""}`}>
                    {d.action}
                  </span>
                  <span className="font-mono text-sm text-foreground">{d.symbol}</span>
                  <span className="text-[10px] font-mono text-muted-foreground">{d.model_used}</span>
                  {d.is_shadow && (
                    <span className="text-[9px] text-zinc-500 bg-zinc-500/10 px-1 py-0.5 rounded">shadow</span>
                  )}
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-xs tabular-nums text-foreground">
                    {d.confidence ? `${(d.confidence * 100).toFixed(0)}%` : "--"}
                  </span>
                  {d.pnl !== null && (
                    <span className={`text-xs tabular-nums ${d.pnl >= 0 ? "text-green-400" : "text-red-400"}`}>
                      {d.pnl >= 0 ? "+" : ""}{d.pnl.toFixed(2)}
                    </span>
                  )}
                </div>
              </div>
              {d.reasoning_summary && (
                <p className="mt-1 text-[11px] text-muted-foreground leading-4 line-clamp-2">
                  {d.reasoning_summary}
                </p>
              )}
              <div className="mt-1 text-[10px] text-muted-foreground/60">
                {d.decided_at ? new Date(d.decided_at).toLocaleString() : ""}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
cd ~/adaptive-trading-ecosystem/frontend
git add src/components/bots/ModelLeaderboard.tsx src/components/bots/LiveDecisionFeed.tsx
git commit -m "feat: enhanced ModelLeaderboard with full metrics and LiveDecisionFeed component"
```

---

## Task 8: Frontend — Integrate into Bot Detail Page

**Files:**
- Modify: `frontend/src/app/bots/[id]/page.tsx`

Mount the ModelLeaderboard, BotModelSettings, and LiveDecisionFeed into the bot detail page.

- [ ] **Step 1: Add imports to bot detail page**

At the top of `bots/[id]/page.tsx`, add:
```typescript
import { ModelLeaderboard } from "@/components/bots/ModelLeaderboard";
import { BotModelSettings } from "@/components/bots/BotModelSettings";
import { LiveDecisionFeed } from "@/components/bots/LiveDecisionFeed";
```

- [ ] **Step 2: Add AI Brain section to terminal tab**

In the terminal tab content (inside `{activeTab === "terminal" && (` block), add a new row between the existing Row 3 and Row 4:

After the Universe/MarketContext/Scanner row (around line 254), add:

```tsx
          {/* Row 3.5: AI Brain — Model Settings + Leaderboard + Decision Feed */}
          {detail.aiBrainConfig && (
            <div className="grid grid-cols-1 gap-4 xl:grid-cols-[260px_1fr]">
              <BotModelSettings
                botId={botId}
                currentModel={(detail.aiBrainConfig as Record<string, unknown>)?.model_config?.primary_model as string ?? "gpt-5.4"}
                autoRouteEnabled={detail.autoRouteEnabled ?? false}
                onUpdate={() => {
                  // Trigger re-fetch
                  getBotDetail(botId).then(setDetail).catch(() => {});
                }}
              />
              <div className="space-y-4">
                <ModelLeaderboard
                  botId={botId}
                  onUpdate={() => getBotDetail(botId).then(setDetail).catch(() => {})}
                />
                <LiveDecisionFeed botId={botId} />
              </div>
            </div>
          )}
```

- [ ] **Step 3: Add aiBrainConfig and autoRouteEnabled to BotDetail type**

In `frontend/src/lib/cerberus-api.ts`, find the `BotDetail` type and add:
```typescript
  aiBrainConfig?: Record<string, unknown> | null;
  autoRouteEnabled?: boolean;
```

And in the `getBotDetail` function response mapping, ensure these fields are passed through.

- [ ] **Step 4: Ensure API returns the new fields**

In `api/routes/ai_tools.py`, find the `get_bot_detail` endpoint (search for the route that returns bot details including `performance`, `trades`, etc.). Inside the session context where the bot is loaded, add these fields to the response dict:

```python
        "aiBrainConfig": bot.ai_brain_config,
        "autoRouteEnabled": bool(bot.auto_route_enabled or False),
```

Make sure these are captured INSIDE the `async with get_session()` block to avoid DetachedInstanceError.

- [ ] **Step 5: Verify frontend builds**

Run: `cd ~/adaptive-trading-ecosystem/frontend && npx next build --no-lint 2>&1 | tail -5`
Expected: Build succeeds

- [ ] **Step 6: Commit**

```bash
cd ~/adaptive-trading-ecosystem
git add frontend/src/app/bots/\\[id\\]/page.tsx frontend/src/lib/cerberus-api.ts api/routes/ai_tools.py
git commit -m "feat: integrate AI Brain UI — model settings, leaderboard, decision feed on bot detail page"
```

---

## Task 9: Integration Test

**Files:**
- Create: `tests/test_ai_brain_integration.py`

Test the full pipeline: AI decision → record → performance tracker → auto-router.

- [ ] **Step 1: Write integration test**

```python
# tests/test_ai_brain_integration.py
"""Integration test for AI Brain pipeline: decision → record → metrics → routing."""
import pytest
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, patch

from services.ai_brain.performance_tracker import compute_model_metrics
from services.ai_brain.auto_router import select_best_model, score_model


class TestAIBrainPipeline:
    """Test the full AI Brain decision → performance → routing pipeline."""

    def test_decisions_produce_valid_metrics(self):
        """Decisions with P&L should produce valid performance metrics."""
        decisions = [
            {"pnl": 12.5, "confidence": 0.85, "decided_at": "2026-03-20T10:00:00"},
            {"pnl": -3.2, "confidence": 0.60, "decided_at": "2026-03-20T11:00:00"},
            {"pnl": 8.7, "confidence": 0.75, "decided_at": "2026-03-20T12:00:00"},
            {"pnl": -1.5, "confidence": 0.55, "decided_at": "2026-03-20T13:00:00"},
            {"pnl": 6.0, "confidence": 0.70, "decided_at": "2026-03-20T14:00:00"},
            {"pnl": 4.3, "confidence": 0.80, "decided_at": "2026-03-20T15:00:00"},
        ]
        metrics = compute_model_metrics(decisions)

        assert metrics["trades_count"] == 6
        assert 0 <= metrics["win_rate"] <= 1
        assert metrics["sharpe_ratio"] != 0  # Should have a real Sharpe value
        assert metrics["max_drawdown"] <= 0  # Drawdown is always non-positive
        assert metrics["total_pnl"] == pytest.approx(26.8, abs=0.01)

    def test_metrics_feed_into_scoring(self):
        """Performance metrics produce consistent scores for auto-routing."""
        good_metrics = compute_model_metrics([
            {"pnl": 10, "confidence": 0.8, "decided_at": f"2026-03-20T{10+i}:00:00"}
            for i in range(6)
        ])
        bad_metrics = compute_model_metrics([
            {"pnl": -5, "confidence": 0.4, "decided_at": f"2026-03-20T{10+i}:00:00"}
            for i in range(6)
        ])

        good_score = score_model(good_metrics)
        bad_score = score_model(bad_metrics)

        assert good_score > bad_score, "Profitable model should score higher"

    @pytest.mark.asyncio
    async def test_auto_router_selects_best(self):
        """Auto-router selects model with best score from real metrics."""
        model_a_decisions = [
            {"pnl": p, "confidence": 0.7, "decided_at": f"2026-03-20T{10+i}:00:00"}
            for i, p in enumerate([5, -2, 8, -1, 6])
        ]
        model_b_decisions = [
            {"pnl": p, "confidence": 0.6, "decided_at": f"2026-03-20T{10+i}:00:00"}
            for i, p in enumerate([-3, -5, 2, -4, -1])
        ]

        mock_metrics = {
            "model-a": compute_model_metrics(model_a_decisions),
            "model-b": compute_model_metrics(model_b_decisions),
        }

        with patch("services.ai_brain.auto_router.get_bot_model_metrics",
                    new_callable=AsyncMock, return_value=mock_metrics):
            best = await select_best_model("bot-123", default_model="model-b")

        assert best == "model-a", "Router should pick the profitable model"

    @pytest.mark.asyncio
    async def test_auto_router_falls_back_with_insufficient_data(self):
        """Auto-router falls back when models have < MIN_TRADES."""
        mock_metrics = {
            "model-a": compute_model_metrics([
                {"pnl": 100, "confidence": 0.9, "decided_at": "2026-03-20T10:00:00"},
                {"pnl": 50, "confidence": 0.8, "decided_at": "2026-03-20T11:00:00"},
            ]),  # Only 2 trades — below MIN_TRADES
        }

        with patch("services.ai_brain.auto_router.get_bot_model_metrics",
                    new_callable=AsyncMock, return_value=mock_metrics):
            best = await select_best_model("bot-123", default_model="gpt-5.4")

        assert best == "gpt-5.4", "Should fall back to default with insufficient data"
```

- [ ] **Step 2: Run tests**

Run: `cd ~/adaptive-trading-ecosystem && python -m pytest tests/test_ai_brain_integration.py -v`
Expected: All 4 tests PASS

- [ ] **Step 3: Commit**

```bash
cd ~/adaptive-trading-ecosystem
git add tests/test_ai_brain_integration.py
git commit -m "test: AI Brain integration tests for full pipeline"
```

---

## Task 10: Final Verification

- [ ] **Step 1: Run all AI Brain tests together**

Run: `cd ~/adaptive-trading-ecosystem && python -m pytest tests/test_performance_tracker.py tests/test_auto_router.py tests/test_ai_brain_integration.py -v`
Expected: All tests PASS

- [ ] **Step 2: Verify backend imports**

Run: `cd ~/adaptive-trading-ecosystem && python -c "from services.ai_brain.performance_tracker import get_bot_model_metrics; from services.ai_brain.auto_router import select_best_model; from api.routes.ai_tools import router; print('All imports OK')"`
Expected: `All imports OK`

- [ ] **Step 3: Verify frontend builds**

Run: `cd ~/adaptive-trading-ecosystem/frontend && npx next build --no-lint 2>&1 | tail -3`
Expected: Build succeeds

- [ ] **Step 4: Checklist verification**

Confirm all of the following:
- [x] Bots generate real AI decisions (AITradingEngine → BotRunner — already working)
- [x] Decisions trigger actual trades (BotRunner._execute_trade → broker — already working)
- [x] Each bot can use a different model (AIBrainConfig.primary_model + DeployConfigModal — already working)
- [ ] Performance is tracked per model (Task 1: performance_tracker.py)
- [ ] Best model is auto-selected over time (Task 2: auto_router.py + Task 4: BotRunner wiring)
- [ ] UI reflects real activity (Task 6-8: ModelLeaderboard, BotModelSettings, LiveDecisionFeed)
- [ ] Manual override works (Task 6: BotModelSettings dropdown)

- [ ] **Step 5: Final commit with all changes**

```bash
cd ~/adaptive-trading-ecosystem
git add -A
git status
# Review that only expected files are staged
git commit -m "feat: complete AI Brain feature — performance tracking, auto-routing, full UI"
```
