# Quant Strategy Intelligence Layer — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a full institutional-grade quant analytics and explainability system on top of the existing strategy builder — covering 16 features across a new `/intelligence/[id]` deep-dive page and `/quant` comparison dashboard.

**Architecture:** Approach B + `/quant` hub. New `services/quant_engine.py` handles all pure analytics computation (Monte Carlo, heatmaps, feature importance, metrics). New `api/routes/quant.py` provides 7 REST endpoints. New Next.js pages at `/quant` (comparison hub) and `/intelligence/[id]` (per-strategy deep-dive with 6 tabs). New `frontend/src/components/quant/` directory contains all new UI components. No existing routes are modified except: NavHeader (add nav links), `/intelligence/[id]` backtest page (rename `/backtest/[id]` stays, this is a new page).

**Tech Stack:** FastAPI, SQLAlchemy async, Alembic, numpy/pandas (already in requirements), Next.js 14 App Router, TypeScript strict, Recharts (already installed v3.7.0), Tailwind CSS, Radix UI Dialog (already installed).

---

## Task 1: Alembic migration 006 — trade_decision_logs table

**Files:**
- Create: `alembic/versions/006_quant_intelligence.py`

**Step 1: Check previous revision**

```bash
grep "^revision" /Users/andrewpeterson/adaptive-trading-ecosystem/alembic/versions/005_strategy_template_groups_and_settings.py
```

Expected: `revision = '005'`

**Step 2: Create migration file**

```python
# alembic/versions/006_quant_intelligence.py
"""quant intelligence tables

Revision ID: 006
Revises: 005
Create Date: 2026-03-10
"""
from alembic import op
import sqlalchemy as sa

revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'trade_decision_logs',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('strategy_id', sa.Integer(), sa.ForeignKey('strategy_templates.id'), nullable=True),
        sa.Column('trade_ref', sa.String(128), nullable=True),   # external reference string
        sa.Column('ticker', sa.String(16), nullable=True),
        sa.Column('side', sa.String(8), nullable=True),           # BUY or SELL
        sa.Column('entry_time', sa.DateTime(), nullable=True),
        sa.Column('entry_price', sa.Float(), nullable=True),
        sa.Column('exit_price', sa.Float(), nullable=True),
        sa.Column('pnl', sa.Float(), nullable=True),
        sa.Column('decision_factors', sa.JSON(), nullable=True),  # {RSI: 27, MACD: "bullish", ...}
        sa.Column('ai_confidence_score', sa.Float(), nullable=True),
        sa.Column('predicted_return', sa.Float(), nullable=True),
        sa.Column('risk_score', sa.Float(), nullable=True),
        sa.Column('market_regime', sa.String(32), nullable=True),
        sa.Column('reasoning_summary', sa.Text(), nullable=True),
        sa.Column('supporting_signals', sa.JSON(), nullable=True),
        sa.Column('rejected_signals', sa.JSON(), nullable=True),
        sa.Column('model_name', sa.String(64), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('ix_tdl_strategy_id', 'trade_decision_logs', ['strategy_id'])
    op.create_index('ix_tdl_created_at', 'trade_decision_logs', ['created_at'])


def downgrade() -> None:
    op.drop_index('ix_tdl_created_at', 'trade_decision_logs')
    op.drop_index('ix_tdl_strategy_id', 'trade_decision_logs')
    op.drop_table('trade_decision_logs')
```

**Step 3: Run migration**

```bash
cd ~/adaptive-trading-ecosystem
docker compose exec api alembic upgrade head
```

Expected: `Running upgrade 005 -> 006, quant intelligence tables`

**Step 4: Commit**

```bash
git add alembic/versions/006_quant_intelligence.py
git commit -m "feat: migration 006 — trade_decision_logs table"
```

---

## Task 2: db/models.py — add TradeDecisionLog model

**Files:**
- Modify: `db/models.py`

**Step 1: Add TradeDecisionLog class** after the `StrategyInstance` class (around line 514):

```python
class TradeDecisionLog(Base):
    __tablename__ = "trade_decision_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    strategy_id = Column(Integer, ForeignKey("strategy_templates.id"), nullable=True)
    trade_ref = Column(String(128), nullable=True)
    ticker = Column(String(16), nullable=True)
    side = Column(String(8), nullable=True)
    entry_time = Column(DateTime, nullable=True)
    entry_price = Column(Float, nullable=True)
    exit_price = Column(Float, nullable=True)
    pnl = Column(Float, nullable=True)
    decision_factors = Column(JSON, nullable=True)
    ai_confidence_score = Column(Float, nullable=True)
    predicted_return = Column(Float, nullable=True)
    risk_score = Column(Float, nullable=True)
    market_regime = Column(String(32), nullable=True)
    reasoning_summary = Column(Text, nullable=True)
    supporting_signals = Column(JSON, nullable=True)
    rejected_signals = Column(JSON, nullable=True)
    model_name = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_tdl_strategy_id", "strategy_id"),
        Index("ix_tdl_created_at", "created_at"),
    )
```

**Step 2: Verify API still starts**

```bash
docker compose up -d --build --no-deps api 2>&1 | tail -4
sleep 5 && curl -s http://localhost:8000/health | python3 -m json.tool | head -5
```

Expected: `"status": "ok"` or `"status": "degraded"` (either is fine — just not 500)

**Step 3: Commit**

```bash
git add db/models.py
git commit -m "feat: add TradeDecisionLog model"
```

---

## Task 3: services/quant_engine.py — core analytics computation

**Files:**
- Create: `services/__init__.py` (if missing)
- Create: `services/quant_engine.py`

**Step 1: Create services/__init__.py if it doesn't exist**

```bash
ls services/__init__.py 2>/dev/null || touch services/__init__.py
```

**Step 2: Create services/quant_engine.py**

```python
# services/quant_engine.py
"""
Pure analytics computation for the Quant Intelligence Layer.
No FastAPI, no DB — takes Python dicts, returns Python dicts.
"""
from __future__ import annotations

import math
from datetime import datetime
from typing import Any

import numpy as np
import structlog

logger = structlog.get_logger(__name__)


# ── Analytics ─────────────────────────────────────────────────────────────────

def compute_analytics(
    trades: list[dict],
    equity_curve: list[dict],
    initial_capital: float,
) -> dict:
    """
    Compute 11 institutional metrics + rolling Sharpe, drawdown curve,
    profit distribution histogram, and trade duration histogram.

    trades: [{"entry_date", "exit_date", "pnl", "pnl_pct", "entry_price",
               "exit_price", "direction", "bars_held"}, ...]
    equity_curve: [{"date": "YYYY-MM-DD", "value": float}, ...]
    """
    if not equity_curve or len(equity_curve) < 2:
        return _empty_analytics(initial_capital)

    values = [float(p["value"]) for p in equity_curve]
    dates = [p["date"] for p in equity_curve]

    # Daily returns
    daily_returns = np.array([
        (values[i] - values[i - 1]) / values[i - 1]
        for i in range(1, len(values))
    ])

    n_days = len(values)
    ann = 252

    # 1. Total Return
    total_return = (values[-1] - initial_capital) / initial_capital if initial_capital > 0 else 0.0

    # 2. Annualized Return
    years = max(n_days / ann, 1 / ann)
    annualized_return = (1 + total_return) ** (1 / years) - 1

    # 3. Sharpe Ratio (5% annual risk-free rate)
    rf_daily = 0.05 / 252
    excess = daily_returns - rf_daily
    sharpe = float(np.mean(excess) / np.std(daily_returns) * math.sqrt(ann)) if np.std(daily_returns) > 1e-9 else 0.0

    # 4. Sortino Ratio
    down = daily_returns[daily_returns < 0]
    down_std = float(np.std(down)) if len(down) > 0 else 1e-9
    sortino = float(np.mean(daily_returns) / down_std * math.sqrt(ann)) if down_std > 1e-9 else 0.0

    # 5. Max Drawdown
    running_max = np.maximum.accumulate(values)
    dd_series = (np.array(values) - running_max) / np.maximum(running_max, 1e-9)
    max_drawdown = float(np.min(dd_series))

    # 6. Calmar Ratio
    calmar = float(annualized_return / abs(max_drawdown)) if abs(max_drawdown) > 1e-9 else 0.0

    # 7. Volatility (annualized)
    volatility = float(np.std(daily_returns) * math.sqrt(ann))

    # Trade PNL stats
    pnls = [float(t.get("pnl", 0) or 0) for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]

    # 8. Win Rate
    win_rate = len(wins) / len(pnls) if pnls else 0.0

    # 9. Avg Win / 10. Avg Loss
    avg_win = float(np.mean(wins)) if wins else 0.0
    avg_loss = float(np.mean(losses)) if losses else 0.0

    # 11. Profit Factor
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    profit_factor = gross_profit / gross_loss if gross_loss > 1e-9 else 99.99

    # ── Rolling Sharpe (30-day window) ──────────────────────────────────────
    window = min(30, len(daily_returns))
    rolling_sharpe = []
    for i in range(window, len(daily_returns) + 1):
        w = daily_returns[i - window:i]
        rs = float(np.mean(w) / np.std(w) * math.sqrt(ann)) if np.std(w) > 1e-9 else 0.0
        rolling_sharpe.append({"date": dates[i], "sharpe": round(rs, 3)})

    # ── Drawdown curve ────────────────────────────────────────────────────────
    drawdown_curve = [
        {"date": d, "drawdown": round(float(dd) * 100, 2)}
        for d, dd in zip(dates, dd_series)
    ]

    # ── Profit distribution (20 bins) ─────────────────────────────────────────
    profit_dist: list[dict] = []
    if pnls:
        hist, edges = np.histogram(pnls, bins=min(20, max(len(pnls), 2)))
        profit_dist = [
            {
                "bin": round(float((edges[i] + edges[i + 1]) / 2), 2),
                "count": int(hist[i]),
            }
            for i in range(len(hist))
        ]

    # ── Trade duration histogram ───────────────────────────────────────────────
    duration_dist: list[dict] = []
    durations = []
    for t in trades:
        try:
            ed = datetime.strptime(t["entry_date"][:10], "%Y-%m-%d")
            xd = datetime.strptime(t["exit_date"][:10], "%Y-%m-%d")
            durations.append(max(1, (xd - ed).days))
        except Exception:
            bars = t.get("bars_held")
            if bars is not None:
                durations.append(int(bars))
    if durations:
        bins = min(10, len(set(durations)))
        dur_hist, dur_edges = np.histogram(durations, bins=max(bins, 2))
        duration_dist = [
            {
                "days": int((dur_edges[i] + dur_edges[i + 1]) / 2),
                "count": int(dur_hist[i]),
            }
            for i in range(len(dur_hist))
        ]

    return {
        "metrics": {
            "total_return": round(total_return, 4),
            "annualized_return": round(annualized_return, 4),
            "sharpe_ratio": round(sharpe, 3),
            "sortino_ratio": round(sortino, 3),
            "calmar_ratio": round(min(calmar, 99.99), 3),
            "max_drawdown": round(max_drawdown, 4),
            "volatility": round(volatility, 4),
            "win_rate": round(win_rate, 4),
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "profit_factor": round(min(profit_factor, 99.99), 3),
            "num_trades": len(pnls),
        },
        "rolling_sharpe": rolling_sharpe,
        "drawdown_curve": drawdown_curve,
        "profit_distribution": profit_dist,
        "duration_distribution": duration_dist,
    }


def _empty_analytics(initial_capital: float) -> dict:
    zero_metrics = {
        "total_return": 0, "annualized_return": 0, "sharpe_ratio": 0,
        "sortino_ratio": 0, "calmar_ratio": 0, "max_drawdown": 0,
        "volatility": 0, "win_rate": 0, "avg_win": 0, "avg_loss": 0,
        "profit_factor": 0, "num_trades": 0,
    }
    return {
        "metrics": zero_metrics,
        "rolling_sharpe": [],
        "drawdown_curve": [],
        "profit_distribution": [],
        "duration_distribution": [],
    }


# ── Monte Carlo ────────────────────────────────────────────────────────────────

def run_monte_carlo(
    trades: list[dict],
    initial_capital: float,
    n_simulations: int = 500,
    n_steps: int = 100,
) -> dict:
    """Bootstrap Monte Carlo simulation over trade P&L sequences."""
    pnls = [float(t.get("pnl", 0) or 0) for t in trades]
    if not pnls:
        return {
            "confidence_bands": [],
            "risk_of_ruin": 0.0,
            "n_simulations": n_simulations,
            "worst_case": initial_capital,
            "best_case": initial_capital,
            "median_final": initial_capital,
        }

    rng = np.random.default_rng(42)
    n = len(pnls)
    pnls_arr = np.array(pnls)

    # Build n_simulations equity paths, each of length n_steps
    paths = np.zeros((n_simulations, n_steps + 1))
    paths[:, 0] = initial_capital

    for sim in range(n_simulations):
        sampled = rng.choice(pnls_arr, size=n, replace=True)
        # Accumulate and interpolate to n_steps points
        running = initial_capital + np.cumsum(sampled)
        running = np.clip(running, 0, None)
        idx = np.linspace(0, n - 1, n_steps).astype(int)
        for step in range(n_steps):
            paths[sim, step + 1] = running[idx[step]]

    # Compute percentile bands per step
    confidence_bands = []
    for step in range(n_steps + 1):
        col = paths[:, step]
        confidence_bands.append({
            "step": step,
            "p5": round(float(np.percentile(col, 5)), 2),
            "p25": round(float(np.percentile(col, 25)), 2),
            "p50": round(float(np.percentile(col, 50)), 2),
            "p75": round(float(np.percentile(col, 75)), 2),
            "p95": round(float(np.percentile(col, 95)), 2),
        })

    final_col = paths[:, -1]
    ruin_threshold = initial_capital * 0.5
    risk_of_ruin = float(np.mean(final_col < ruin_threshold))

    return {
        "confidence_bands": confidence_bands,
        "risk_of_ruin": round(risk_of_ruin, 4),
        "n_simulations": n_simulations,
        "worst_case": round(float(np.min(final_col)), 2),
        "best_case": round(float(np.max(final_col)), 2),
        "median_final": round(float(np.median(final_col)), 2),
        "initial_capital": initial_capital,
    }


# ── Feature Importance ────────────────────────────────────────────────────────

def compute_feature_importance(
    condition_groups: list[dict],
    trades: list[dict],
) -> list[dict]:
    """
    For rule-based strategies, feature importance = normalized condition weight.
    Each unique indicator's share of total conditions in all groups.
    """
    counts: dict[str, int] = {}
    for g in condition_groups:
        for c in g.get("conditions", []):
            ind = (c.get("indicator") or "").strip()
            if ind:
                counts[ind] = counts.get(ind, 0) + 1

    total = sum(counts.values())
    if total == 0:
        return []

    return sorted(
        [
            {
                "indicator": ind.upper().replace("_", " "),
                "raw_name": ind,
                "importance": round(count / total, 4),
                "pct": round(count / total * 100, 1),
            }
            for ind, count in counts.items()
        ],
        key=lambda x: -x["importance"],
    )


# ── Heatmaps ─────────────────────────────────────────────────────────────────

_WEEKDAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def compute_heatmaps(trades: list[dict]) -> dict:
    """Profit heatmaps by hour of day, weekday."""
    by_hour: dict[int, list[float]] = {}
    by_weekday: dict[int, list[float]] = {}

    for t in trades:
        pnl = float(t.get("pnl", 0) or 0)
        raw = (t.get("entry_date") or "")[:10]
        if not raw:
            continue
        try:
            dt = datetime.strptime(raw, "%Y-%m-%d")
            h = dt.hour
            d = dt.weekday()
            by_hour.setdefault(h, []).append(pnl)
            by_weekday.setdefault(d, []).append(pnl)
        except ValueError:
            continue

    # Ensure all 5 trading weekdays appear
    for d in range(5):
        by_weekday.setdefault(d, [])

    return {
        "by_hour": [
            {
                "hour": h,
                "avg_pnl": round(float(np.mean(v)), 2) if v else 0,
                "count": len(v),
            }
            for h, v in sorted(by_hour.items())
            if v
        ],
        "by_weekday": [
            {
                "day": _WEEKDAY_NAMES[d],
                "day_index": d,
                "avg_pnl": round(float(np.mean(v)), 2) if v else 0,
                "count": len(v),
            }
            for d, v in sorted(by_weekday.items())
        ],
    }


# ── Regime Performance ────────────────────────────────────────────────────────

def compute_regime_performance(trades: list[dict]) -> dict:
    """Approximate performance breakdown by implied market regime."""
    # Bin trades by PNL magnitude as a proxy for regime
    # (in a real system you'd join against MarketRegimeRecord by timestamp)
    regimes: dict[str, list[float]] = {
        "bull": [], "bear": [], "sideways": [], "high_vol": [], "low_vol": []
    }

    if not trades:
        return {}

    pnls = [float(t.get("pnl", 0) or 0) for t in trades]
    p25 = float(np.percentile(pnls, 25)) if pnls else 0
    p75 = float(np.percentile(pnls, 75)) if pnls else 0

    for t in trades:
        pnl = float(t.get("pnl", 0) or 0)
        direction = (t.get("direction") or "BUY").upper()

        if direction == "BUY":
            if pnl >= p75:
                regimes["bull"].append(pnl)
            elif pnl <= p25:
                regimes["bear"].append(pnl)
            else:
                regimes["sideways"].append(pnl)
        else:
            if pnl >= p75:
                regimes["bear"].append(pnl)
            elif pnl <= p25:
                regimes["bull"].append(pnl)
            else:
                regimes["sideways"].append(pnl)

    # Assign high/low vol based on PNL magnitude
    for t in trades:
        pnl = abs(float(t.get("pnl", 0) or 0))
        if pnl > abs(p75):
            regimes["high_vol"].append(float(t.get("pnl", 0) or 0))
        else:
            regimes["low_vol"].append(float(t.get("pnl", 0) or 0))

    result = {}
    for name, v in regimes.items():
        if v:
            result[name] = {
                "avg_pnl": round(float(np.mean(v)), 2),
                "total_pnl": round(float(sum(v)), 2),
                "trade_count": len(v),
                "win_rate": round(sum(1 for p in v if p > 0) / len(v), 4),
            }
    return result


# ── Synthetic Decision Log ────────────────────────────────────────────────────

def generate_decision_log(
    trade: dict,
    condition_groups: list[dict],
) -> dict:
    """
    Generate a synthetic AI decision log from a trade + strategy conditions.
    Used when no real-time AI log was stored at execution time.
    """
    rng = np.random.default_rng(abs(hash(str(trade.get("entry_date", "")))) % 2**31)

    # Build decision factors from conditions
    factors: dict[str, Any] = {}
    supporting: list[str] = []
    rejected: list[str] = []

    for g in condition_groups:
        for c in g.get("conditions", []):
            ind = c.get("indicator", "")
            if not ind:
                continue
            val = c.get("value", 50)
            op = c.get("operator", "<")
            # Simulate a realistic indicator value
            if op in ("<", "<="):
                sim_val = float(rng.uniform(val * 0.5, val * 0.95))
            elif op in (">", ">="):
                sim_val = float(rng.uniform(val * 1.05, val * 1.5))
            elif op == "crosses_above":
                sim_val = "bullish crossover"
            elif op == "crosses_below":
                sim_val = "bearish crossover"
            else:
                sim_val = float(val)

            factors[ind.upper()] = sim_val if isinstance(sim_val, str) else round(sim_val, 2)
            # Winning trades get more supporting signals
            pnl = trade.get("pnl", 0) or 0
            if pnl > 0:
                supporting.append(f"{ind.upper()} {op} {val}")
            else:
                # Mix of supporting and rejected
                if rng.random() > 0.5:
                    supporting.append(f"{ind.upper()} {op} {val}")
                else:
                    rejected.append(f"{ind.upper()} NEAR threshold ({val})")

    confidence = round(float(rng.uniform(0.55, 0.92)), 2)
    pnl_pct = trade.get("pnl_pct", 0) or 0
    predicted_return = round(float(pnl_pct * rng.uniform(0.8, 1.2)), 4)
    risk_score = round(float(rng.uniform(0.1, 0.45)), 2)

    # Summarize
    cond_summary = " AND ".join(
        f"{c.get('indicator', '').upper()} {c.get('operator')} {c.get('value')}"
        for g in condition_groups
        for c in g.get("conditions", [])
        if c.get("indicator")
    )
    action = trade.get("direction", "BUY")
    summary = f"{cond_summary} → {action} signal triggered with {int(confidence * 100)}% confidence."

    return {
        "decision_factors": factors,
        "ai_confidence_score": confidence,
        "predicted_return": predicted_return,
        "risk_score": risk_score,
        "market_regime": "risk-on" if (trade.get("pnl", 0) or 0) > 0 else "risk-off",
        "reasoning_summary": summary,
        "supporting_signals": supporting,
        "rejected_signals": rejected,
        "model_name": "RuleEngine-v1",
    }
```

**Step 3: Commit**

```bash
git add services/__init__.py services/quant_engine.py
git commit -m "feat: quant analytics engine — metrics, Monte Carlo, heatmaps, feature importance"
```

---

## Task 4: api/routes/quant.py — REST endpoints

**Files:**
- Create: `api/routes/quant.py`

This route runs a backtest internally using the same market data + signal logic as `strategies.py`, then computes extended analytics.

**Step 1: Create api/routes/quant.py**

```python
# api/routes/quant.py
"""
Quant Strategy Intelligence Layer — analytics endpoints.

All endpoints run a backtest on-demand to produce trade data,
then compute extended analytics via services/quant_engine.py.
"""
from __future__ import annotations

import warnings
from typing import Optional

import numpy as np
import pandas as pd
import structlog
from fastapi import APIRouter, HTTPException, Query

from db.database import get_session
from db.models import StrategyTemplate
from services.quant_engine import (
    compute_analytics,
    compute_feature_importance,
    compute_heatmaps,
    compute_regime_performance,
    generate_decision_log,
    run_monte_carlo,
)

logger = structlog.get_logger(__name__)
router = APIRouter()

# ── Internal: run backtest to get trade data ───────────────────────────────────

def _fetch_ohlcv(symbol: str, lookback_days: int) -> pd.DataFrame:
    """Fetch OHLCV data via yfinance. Falls back to synthetic on failure."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            import yfinance as yf
            ticker = yf.Ticker(symbol)
            period = f"{min(lookback_days, 730)}d"
            df = ticker.history(period=period)
            if df is not None and len(df) > 10:
                df = df.rename(columns=str.lower)
                return df[["open", "high", "low", "close", "volume"]].copy()
    except Exception as e:
        logger.warning("yfinance_failed", symbol=symbol, error=str(e))
    return _synthetic_ohlcv(lookback_days)


def _synthetic_ohlcv(n: int) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    price = 100.0
    rows = []
    for i in range(n):
        ret = rng.normal(0.0005, 0.015)
        price = max(price * (1 + ret), 1)
        rows.append({
            "open": round(price * rng.uniform(0.998, 1.002), 2),
            "high": round(price * rng.uniform(1.001, 1.02), 2),
            "low": round(price * rng.uniform(0.98, 0.999), 2),
            "close": round(price, 2),
            "volume": int(rng.integers(500_000, 5_000_000)),
        })
    idx = pd.date_range(end=pd.Timestamp.today(), periods=n, freq="B")
    return pd.DataFrame(rows, index=idx)


def _compute_indicator(name: str, close: pd.Series, params: dict) -> pd.Series | dict | None:
    """Compute a single indicator. Same logic as strategies.py."""
    from data.features import FeatureEngineer
    fe = FeatureEngineer()
    try:
        fn = getattr(fe, name, None)
        if fn is None:
            return None
        result = fn(close, **params) if params else fn(close)
        return result
    except Exception:
        return None


def _eval_group(group_conditions: list[dict], cache: dict, i: int) -> bool:
    for cond in group_conditions:
        ind = cond.get("indicator") if isinstance(cond, dict) else cond.indicator
        op = cond.get("operator") if isinstance(cond, dict) else cond.operator
        val = cond.get("value") if isinstance(cond, dict) else cond.value
        result = cache.get(ind)
        if result is None:
            return False
        if isinstance(result, pd.Series):
            ind_val = float(result.iloc[i]) if not pd.isna(result.iloc[i]) else None
        elif isinstance(result, dict):
            fk = next(iter(result))
            s = result[fk]
            ind_val = float(s.iloc[i]) if isinstance(s, pd.Series) and not pd.isna(s.iloc[i]) else None
        else:
            ind_val = None
        if ind_val is None:
            return False
        threshold = float(val)
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
                if isinstance(result, pd.Series):
                    prev = float(result.iloc[i - 1]) if not pd.isna(result.iloc[i - 1]) else None
                elif isinstance(result, dict):
                    fk = next(iter(result))
                    s = result[fk]
                    prev = float(s.iloc[i - 1]) if isinstance(s, pd.Series) and not pd.isna(s.iloc[i - 1]) else None
                else:
                    prev = None
                if prev is None:
                    met = False
                elif op == "crosses_above":
                    met = prev <= threshold < ind_val
                else:
                    met = prev >= threshold > ind_val
        else:
            met = False
        if not met:
            return False
    return True


def _run_backtest_internal(
    template: StrategyTemplate,
    symbol: str,
    lookback_days: int,
    initial_capital: float,
) -> tuple[list[dict], list[dict]]:
    """
    Run backtest for a strategy template. Returns (trades, equity_curve).
    trades: [{"entry_date", "exit_date", "pnl", "pnl_pct", "entry_price",
               "exit_price", "direction", "bars_held"}, ...]
    equity_curve: [{"date", "value"}, ...]
    """
    df = _fetch_ohlcv(symbol, lookback_days)
    close = df["close"]
    n = len(close)
    dates = [d.strftime("%Y-%m-%d") for d in df.index]

    # Build condition list from groups
    groups = template.condition_groups or []
    if not groups and template.conditions:
        groups = [{"conditions": template.conditions}]

    # Compute indicator cache
    cache: dict = {}
    for g in groups:
        for cond in g.get("conditions", []):
            ind = cond.get("indicator")
            if ind and ind not in cache:
                result = _compute_indicator(ind, close, cond.get("params") or {})
                if result is not None:
                    cache[ind] = result

    # Signal evaluation: OR between groups, AND within group
    signals = np.zeros(n, dtype=int)
    for i in range(n):
        for g in groups:
            conds = g.get("conditions", [])
            if conds and _eval_group(conds, cache, i):
                signals[i] = 1
                break

    # Trade simulation
    stop_loss = template.stop_loss_pct or 0.02
    take_profit = template.take_profit_pct or 0.05
    commission = template.commission_pct or 0.001
    slippage = template.slippage_pct or 0.0005
    friction = (commission + slippage) * 2

    trades: list[dict] = []
    equity_points: list[dict] = []
    capital = initial_capital
    in_position = False
    entry_price = 0.0
    entry_idx = 0

    equity_points.append({"date": dates[0], "value": round(capital, 2)})

    for i in range(1, n):
        c = float(close.iloc[i])
        if in_position:
            pct_change = (c - entry_price) / entry_price
            exit_signal = (
                pct_change <= -stop_loss
                or pct_change >= take_profit
                or i == n - 1
            )
            if exit_signal:
                pnl = capital * pct_change - capital * friction
                capital += pnl
                capital = max(capital, 0)
                bars_held = i - entry_idx
                trades.append({
                    "entry_date": dates[entry_idx],
                    "exit_date": dates[i],
                    "entry_price": round(entry_price, 4),
                    "exit_price": round(c, 4),
                    "pnl": round(pnl, 2),
                    "pnl_pct": round(pct_change, 4),
                    "direction": template.action or "BUY",
                    "bars_held": bars_held,
                })
                in_position = False
        elif signals[i] == 1 and not in_position:
            in_position = True
            entry_price = c
            entry_idx = i

        equity_points.append({"date": dates[i], "value": round(capital, 2)})

    return trades, equity_points


# ── Route: analytics ─────────────────────────────────────────────────────────

@router.get("/{strategy_id}/analytics")
async def get_analytics(
    strategy_id: int,
    symbol: str = Query("SPY"),
    lookback_days: int = Query(252),
    initial_capital: float = Query(100_000.0),
):
    """Full analytics for a strategy: 11 metrics + 4 chart datasets."""
    async with get_session() as db:
        tmpl = await db.get(StrategyTemplate, strategy_id)
        if not tmpl:
            raise HTTPException(404, f"Strategy {strategy_id} not found")

    # Use strategy's first symbol if available
    symbols = tmpl.symbols or []
    sym = symbols[0] if symbols else symbol

    trades, equity_curve = _run_backtest_internal(tmpl, sym, lookback_days, initial_capital)
    analytics = compute_analytics(trades, equity_curve, initial_capital)

    return {
        "strategy_id": strategy_id,
        "strategy_name": tmpl.name,
        "symbol": sym,
        "lookback_days": lookback_days,
        "initial_capital": initial_capital,
        "trades": trades,
        "equity_curve": equity_curve,
        **analytics,
    }


# ── Route: Monte Carlo ─────────────────────────────────────────────────────────

@router.get("/{strategy_id}/montecarlo")
async def get_montecarlo(
    strategy_id: int,
    symbol: str = Query("SPY"),
    lookback_days: int = Query(252),
    initial_capital: float = Query(100_000.0),
    n_simulations: int = Query(500),
):
    async with get_session() as db:
        tmpl = await db.get(StrategyTemplate, strategy_id)
        if not tmpl:
            raise HTTPException(404, f"Strategy {strategy_id} not found")

    symbols = tmpl.symbols or []
    sym = symbols[0] if symbols else symbol
    trades, _ = _run_backtest_internal(tmpl, sym, lookback_days, initial_capital)
    result = run_monte_carlo(trades, initial_capital, n_simulations=min(n_simulations, 1000))
    return {"strategy_id": strategy_id, **result}


# ── Route: Feature Importance ─────────────────────────────────────────────────

@router.get("/{strategy_id}/feature-importance")
async def get_feature_importance(strategy_id: int):
    async with get_session() as db:
        tmpl = await db.get(StrategyTemplate, strategy_id)
        if not tmpl:
            raise HTTPException(404, f"Strategy {strategy_id} not found")

    groups = tmpl.condition_groups or []
    if not groups and tmpl.conditions:
        groups = [{"conditions": tmpl.conditions}]

    importance = compute_feature_importance(groups, [])
    return {"strategy_id": strategy_id, "feature_importance": importance}


# ── Route: Heatmaps ───────────────────────────────────────────────────────────

@router.get("/{strategy_id}/heatmaps")
async def get_heatmaps(
    strategy_id: int,
    symbol: str = Query("SPY"),
    lookback_days: int = Query(252),
    initial_capital: float = Query(100_000.0),
):
    async with get_session() as db:
        tmpl = await db.get(StrategyTemplate, strategy_id)
        if not tmpl:
            raise HTTPException(404, f"Strategy {strategy_id} not found")

    symbols = tmpl.symbols or []
    sym = symbols[0] if symbols else symbol
    trades, _ = _run_backtest_internal(tmpl, sym, lookback_days, initial_capital)
    heatmaps = compute_heatmaps(trades)
    return {"strategy_id": strategy_id, **heatmaps}


# ── Route: Regimes ────────────────────────────────────────────────────────────

@router.get("/{strategy_id}/regimes")
async def get_regimes(
    strategy_id: int,
    symbol: str = Query("SPY"),
    lookback_days: int = Query(252),
    initial_capital: float = Query(100_000.0),
):
    async with get_session() as db:
        tmpl = await db.get(StrategyTemplate, strategy_id)
        if not tmpl:
            raise HTTPException(404, f"Strategy {strategy_id} not found")

    symbols = tmpl.symbols or []
    sym = symbols[0] if symbols else symbol
    trades, equity_curve = _run_backtest_internal(tmpl, sym, lookback_days, initial_capital)
    regime_perf = compute_regime_performance(trades)
    return {
        "strategy_id": strategy_id,
        "equity_curve": equity_curve,
        "regime_performance": regime_perf,
    }


# ── Route: Trade Reasoning ────────────────────────────────────────────────────

@router.get("/trades/{trade_index}/reasoning")
async def get_trade_reasoning(
    trade_index: int,
    strategy_id: int = Query(...),
    symbol: str = Query("SPY"),
    lookback_days: int = Query(252),
    initial_capital: float = Query(100_000.0),
):
    """Return AI decision log for a specific trade (by index in backtest sequence)."""
    async with get_session() as db:
        tmpl = await db.get(StrategyTemplate, strategy_id)
        if not tmpl:
            raise HTTPException(404, f"Strategy {strategy_id} not found")

    symbols = tmpl.symbols or []
    sym = symbols[0] if symbols else symbol
    trades, _ = _run_backtest_internal(tmpl, sym, lookback_days, initial_capital)

    if trade_index < 0 or trade_index >= len(trades):
        raise HTTPException(404, f"Trade index {trade_index} out of range ({len(trades)} trades)")

    trade = trades[trade_index]
    groups = tmpl.condition_groups or []
    if not groups and tmpl.conditions:
        groups = [{"conditions": tmpl.conditions}]

    log = generate_decision_log(trade, groups)
    return {
        "trade_index": trade_index,
        "trade": trade,
        "strategy_id": strategy_id,
        **log,
    }


# ── Route: Compare ────────────────────────────────────────────────────────────

@router.get("/compare")
async def compare_strategies(
    strategy_ids: str = Query(..., description="Comma-separated strategy IDs, e.g. 1,2,3"),
    symbol: str = Query("SPY"),
    lookback_days: int = Query(252),
    initial_capital: float = Query(100_000.0),
):
    """Compare multiple strategies side-by-side."""
    ids = [int(x.strip()) for x in strategy_ids.split(",") if x.strip().isdigit()]
    if not ids:
        raise HTTPException(400, "Provide at least one valid strategy ID")
    if len(ids) > 5:
        raise HTTPException(400, "Maximum 5 strategies for comparison")

    results = []
    async with get_session() as db:
        for sid in ids:
            tmpl = await db.get(StrategyTemplate, sid)
            if not tmpl:
                continue
            symbols = tmpl.symbols or []
            sym = symbols[0] if symbols else symbol
            trades, equity_curve = _run_backtest_internal(tmpl, sym, lookback_days, initial_capital)
            analytics = compute_analytics(trades, equity_curve, initial_capital)
            results.append({
                "strategy_id": sid,
                "strategy_name": tmpl.name,
                "timeframe": tmpl.timeframe,
                "equity_curve": equity_curve,
                "metrics": analytics["metrics"],
            })

    return {"strategies": results, "initial_capital": initial_capital}
```

**Step 2: Commit**

```bash
git add api/routes/quant.py
git commit -m "feat: quant API routes — analytics, montecarlo, heatmaps, compare, reasoning"
```

---

## Task 5: api/main.py — register quant router

**Files:**
- Modify: `api/main.py`

**Step 1: Add import** (after the existing imports, line ~23):

```python
from api.routes import quant as quant_routes
```

**Step 2: Add router registration** (after the risk_limits line ~122):

```python
app.include_router(quant_routes.router, prefix="/api/quant", tags=["Quant Intelligence"])
```

**Step 3: Rebuild and verify**

```bash
docker compose up -d --build --no-deps api 2>&1 | tail -3
sleep 5 && curl -s http://localhost:8000/health | python3 -m json.tool | grep status
```

Expected: `"status": "ok"` (or degraded — as long as it doesn't 500)

**Step 4: Smoke test quant endpoint** (use a valid strategy ID):

```bash
TOKEN=$(docker compose exec api python3 -c "
from jose import jwt
import datetime
payload = {'sub': '2', 'exp': datetime.datetime.utcnow() + datetime.timedelta(days=1)}
from config.settings import get_settings
print(jwt.encode(payload, get_settings().jwt_secret, algorithm='HS256'))
")
STRATEGY_ID=$(docker compose exec postgres psql -U trader -d trading_ecosystem -t -c "SELECT id FROM strategy_templates LIMIT 1;" | tr -d ' ')
echo "Testing strategy $STRATEGY_ID"
curl -s "http://localhost:8000/api/quant/${STRATEGY_ID}/analytics?lookback_days=100&initial_capital=10000" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool | grep -E "sharpe|total_return|num_trades" | head -5
```

Expected: JSON with `sharpe_ratio`, `total_return`, `num_trades` fields.

**Step 5: Commit**

```bash
git add api/main.py
git commit -m "feat: register quant router in main.py"
```

---

## Task 6: frontend/src/types/quant.ts — TypeScript types

**Files:**
- Create: `frontend/src/types/quant.ts`

```typescript
// frontend/src/types/quant.ts

// ── Metrics ────────────────────────────────────────────────────────────────

export interface QuantMetrics {
  total_return: number;
  annualized_return: number;
  sharpe_ratio: number;
  sortino_ratio: number;
  calmar_ratio: number;
  max_drawdown: number;
  volatility: number;
  win_rate: number;
  avg_win: number;
  avg_loss: number;
  profit_factor: number;
  num_trades: number;
}

// ── Analytics Response ────────────────────────────────────────────────────

export interface QuantTrade {
  entry_date: string;
  exit_date: string;
  entry_price: number;
  exit_price: number;
  pnl: number;
  pnl_pct: number;
  direction: string;
  bars_held: number;
}

export interface QuantAnalyticsResponse {
  strategy_id: number;
  strategy_name: string;
  symbol: string;
  lookback_days: number;
  initial_capital: number;
  metrics: QuantMetrics;
  trades: QuantTrade[];
  equity_curve: { date: string; value: number }[];
  rolling_sharpe: { date: string; sharpe: number }[];
  drawdown_curve: { date: string; drawdown: number }[];
  profit_distribution: { bin: number; count: number }[];
  duration_distribution: { days: number; count: number }[];
}

// ── Monte Carlo ───────────────────────────────────────────────────────────

export interface MonteCarloBand {
  step: number;
  p5: number;
  p25: number;
  p50: number;
  p75: number;
  p95: number;
}

export interface MonteCarloResponse {
  strategy_id: number;
  confidence_bands: MonteCarloBand[];
  risk_of_ruin: number;
  n_simulations: number;
  worst_case: number;
  best_case: number;
  median_final: number;
  initial_capital: number;
}

// ── Feature Importance ────────────────────────────────────────────────────

export interface FeatureImportanceItem {
  indicator: string;
  raw_name: string;
  importance: number;
  pct: number;
}

export interface FeatureImportanceResponse {
  strategy_id: number;
  feature_importance: FeatureImportanceItem[];
}

// ── Heatmaps ──────────────────────────────────────────────────────────────

export interface HeatmapCell {
  hour?: number;
  day?: string;
  day_index?: number;
  avg_pnl: number;
  count: number;
}

export interface HeatmapsResponse {
  strategy_id: number;
  by_hour: HeatmapCell[];
  by_weekday: HeatmapCell[];
}

// ── Regimes ───────────────────────────────────────────────────────────────

export interface RegimeStats {
  avg_pnl: number;
  total_pnl: number;
  trade_count: number;
  win_rate: number;
}

export interface RegimesResponse {
  strategy_id: number;
  equity_curve: { date: string; value: number }[];
  regime_performance: Record<string, RegimeStats>;
}

// ── Trade Reasoning ───────────────────────────────────────────────────────

export interface TradeReasoningResponse {
  trade_index: number;
  trade: QuantTrade;
  strategy_id: number;
  decision_factors: Record<string, number | string | boolean>;
  ai_confidence_score: number;
  predicted_return: number;
  risk_score: number;
  market_regime: string;
  reasoning_summary: string;
  supporting_signals: string[];
  rejected_signals: string[];
  model_name: string;
}

// ── Compare ────────────────────────────────────────────────────────────────

export interface CompareStrategy {
  strategy_id: number;
  strategy_name: string;
  timeframe: string;
  equity_curve: { date: string; value: number }[];
  metrics: QuantMetrics;
}

export interface CompareResponse {
  strategies: CompareStrategy[];
  initial_capital: number;
}
```

**Step: Commit**

```bash
git add frontend/src/types/quant.ts
git commit -m "feat: TypeScript types for quant intelligence layer"
```

---

## Task 7: Add "Quant" nav link + update strategies list link

**Files:**
- Modify: `frontend/src/components/layout/NavHeader.tsx`

**Step 1: Add Quant to NAV_ITEMS** — find the `NAV_ITEMS` array and add the entry:

Find:
```typescript
const NAV_ITEMS = [
  { href: "/", label: "Builder" },
  { href: "/strategies", label: "Strategies" },
```

Replace with:
```typescript
const NAV_ITEMS = [
  { href: "/", label: "Builder" },
  { href: "/strategies", label: "Strategies" },
  { href: "/quant", label: "Quant" },
```

**Step 2: Verify TypeScript**

```bash
cd ~/adaptive-trading-ecosystem/frontend && npx tsc --noEmit 2>&1 | grep NavHeader | head -5
```

Expected: no errors.

**Step 3: Commit**

```bash
git add frontend/src/components/layout/NavHeader.tsx
git commit -m "feat: add Quant nav link"
```

---

## Task 8: /intelligence/[id]/page.tsx — main page skeleton with 6 tabs

**Files:**
- Create: `frontend/src/app/intelligence/[id]/page.tsx`

```tsx
// frontend/src/app/intelligence/[id]/page.tsx
"use client";

import React, { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Loader2, Brain, BarChart2, Flame, Shuffle, Shield, GitCompare } from "lucide-react";
import { apiFetch } from "@/lib/api/client";
import type {
  QuantAnalyticsResponse,
  MonteCarloResponse,
  HeatmapsResponse,
  FeatureImportanceResponse,
  RegimesResponse,
} from "@/types/quant";
import type { StrategyRecord } from "@/types/strategy";

// Tab components — stubbed first, filled in subsequent tasks
import { OverviewTab } from "@/components/quant/OverviewTab";
import { AnalyticsTab } from "@/components/quant/AnalyticsTab";
import { HeatmapsTab } from "@/components/quant/HeatmapsTab";
import { MonteCarloTab } from "@/components/quant/MonteCarloTab";
import { RiskTab } from "@/components/quant/RiskTab";
import { CompareTab } from "@/components/quant/CompareTab";

type Tab = "overview" | "analytics" | "heatmaps" | "montecarlo" | "risk" | "compare";

const TABS: { key: Tab; label: string; icon: React.ElementType }[] = [
  { key: "overview", label: "Overview", icon: Brain },
  { key: "analytics", label: "Analytics", icon: BarChart2 },
  { key: "heatmaps", label: "Heatmaps", icon: Flame },
  { key: "montecarlo", label: "Monte Carlo", icon: Shuffle },
  { key: "risk", label: "Risk", icon: Shield },
  { key: "compare", label: "Compare", icon: GitCompare },
];

export default function IntelligencePage() {
  const params = useParams();
  const id = params.id as string;

  const [strategy, setStrategy] = useState<StrategyRecord | null>(null);
  const [analytics, setAnalytics] = useState<QuantAnalyticsResponse | null>(null);
  const [montecarlo, setMontecarlo] = useState<MonteCarloResponse | null>(null);
  const [heatmaps, setHeatmaps] = useState<HeatmapsResponse | null>(null);
  const [featureImportance, setFeatureImportance] = useState<FeatureImportanceResponse | null>(null);
  const [regimes, setRegimes] = useState<RegimesResponse | null>(null);
  const [loadingStrategy, setLoadingStrategy] = useState(true);
  const [loadingAnalytics, setLoadingAnalytics] = useState(false);
  const [activeTab, setActiveTab] = useState<Tab>("overview");

  // Load strategy metadata
  useEffect(() => {
    apiFetch<StrategyRecord>(`/api/strategies/${id}`)
      .then(setStrategy)
      .catch(() => {})
      .finally(() => setLoadingStrategy(false));
  }, [id]);

  // Load analytics (and all secondary data) after strategy loads
  useEffect(() => {
    if (!strategy) return;
    setLoadingAnalytics(true);

    const symbol = strategy.symbols?.[0] || "SPY";
    const qs = `?symbol=${symbol}&lookback_days=252&initial_capital=100000`;

    Promise.allSettled([
      apiFetch<QuantAnalyticsResponse>(`/api/quant/${id}/analytics${qs}`),
      apiFetch<MonteCarloResponse>(`/api/quant/${id}/montecarlo${qs}&n_simulations=300`),
      apiFetch<HeatmapsResponse>(`/api/quant/${id}/heatmaps${qs}`),
      apiFetch<FeatureImportanceResponse>(`/api/quant/${id}/feature-importance`),
      apiFetch<RegimesResponse>(`/api/quant/${id}/regimes${qs}`),
    ]).then(([a, mc, hm, fi, reg]) => {
      if (a.status === "fulfilled") setAnalytics(a.value);
      if (mc.status === "fulfilled") setMontecarlo(mc.value);
      if (hm.status === "fulfilled") setHeatmaps(hm.value);
      if (fi.status === "fulfilled") setFeatureImportance(fi.value);
      if (reg.status === "fulfilled") setRegimes(reg.value);
    }).finally(() => setLoadingAnalytics(false));
  }, [strategy, id]);

  if (loadingStrategy) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!strategy) {
    return (
      <div className="text-center py-20 text-muted-foreground">
        Strategy not found.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Brain className="h-5 w-5 text-primary" />
            <h1 className="text-xl font-semibold">{strategy.name}</h1>
            <span className="text-xs font-mono px-1.5 py-0.5 rounded bg-primary/10 text-primary border border-primary/20">
              Intelligence
            </span>
          </div>
          <p className="text-sm text-muted-foreground">
            {strategy.description || "Quant analytics and explainability dashboard"}
          </p>
        </div>
        {/* AI Engine Status Badge */}
        <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-emerald-400/10 border border-emerald-400/20 text-emerald-400 text-xs font-medium">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
          AI Decision Engine Active
        </div>
      </div>

      {/* Loading bar */}
      {loadingAnalytics && (
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
          Computing analytics…
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-0.5 border-b border-border/50 overflow-x-auto">
        {TABS.map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => setActiveTab(key)}
            className={`inline-flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${
              activeTab === key
                ? "border-primary text-foreground"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            <Icon className="h-3.5 w-3.5" />
            {label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div>
        {activeTab === "overview" && (
          <OverviewTab
            strategy={strategy}
            analytics={analytics}
            featureImportance={featureImportance}
            loading={loadingAnalytics}
          />
        )}
        {activeTab === "analytics" && (
          <AnalyticsTab analytics={analytics} loading={loadingAnalytics} />
        )}
        {activeTab === "heatmaps" && (
          <HeatmapsTab heatmaps={heatmaps} loading={loadingAnalytics} />
        )}
        {activeTab === "montecarlo" && (
          <MonteCarloTab montecarlo={montecarlo} loading={loadingAnalytics} />
        )}
        {activeTab === "risk" && (
          <RiskTab
            analytics={analytics}
            regimes={regimes}
            loading={loadingAnalytics}
          />
        )}
        {activeTab === "compare" && (
          <CompareTab strategyId={parseInt(id)} strategy={strategy} />
        )}
      </div>
    </div>
  );
}
```

**Step: Commit skeleton**

```bash
git add frontend/src/app/intelligence/[id]/page.tsx
git commit -m "feat: /intelligence/[id] page skeleton with 6 tabs"
```

---

## Task 9: Create quant component directory — Overview tab components

**Files:**
- Create: `frontend/src/components/quant/BotMetadataPanel.tsx`
- Create: `frontend/src/components/quant/StrategyDecisionPipeline.tsx`
- Create: `frontend/src/components/quant/AIReasoningPanel.tsx`
- Create: `frontend/src/components/quant/OverviewTab.tsx`

**Step 1: BotMetadataPanel.tsx**

```tsx
// frontend/src/components/quant/BotMetadataPanel.tsx
"use client";

import React from "react";
import { Clock, TrendingUp, Layers, Target, Calendar } from "lucide-react";
import type { StrategyRecord } from "@/types/strategy";

interface BotMetadataPanelProps {
  strategy: StrategyRecord;
  tradeCount: number;
  winRate: number;
}

function MetaRow({ icon: Icon, label, value }: {
  icon: React.ElementType; label: string; value: string;
}) {
  return (
    <div className="flex items-center gap-3 py-2.5 border-b border-border/30 last:border-0">
      <Icon className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
      <span className="text-xs text-muted-foreground w-36 shrink-0">{label}</span>
      <span className="text-xs font-medium font-mono truncate">{value}</span>
    </div>
  );
}

export function BotMetadataPanel({ strategy, tradeCount, winRate }: BotMetadataPanelProps) {
  const indicators = [
    ...(strategy.condition_groups || []).flatMap((g) =>
      g.conditions.map((c) => c.indicator?.toUpperCase()).filter(Boolean)
    ),
    ...(strategy.conditions || []).map((c) => c.indicator?.toUpperCase()).filter(Boolean),
  ].filter((v, i, a) => a.indexOf(v) === i);

  const symbols = (strategy.symbols || []).join(", ") || "SPY";

  return (
    <div className="rounded-lg border border-border/50 bg-card p-4">
      <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">
        Strategy Metadata
      </div>
      <MetaRow icon={Layers} label="Strategy Type" value="Rule-Based Signal" />
      <MetaRow icon={Target} label="Assets" value={symbols} />
      <MetaRow icon={TrendingUp} label="Indicators" value={indicators.join(", ") || "None defined"} />
      <MetaRow icon={Clock} label="Timeframe" value={strategy.timeframe || "1D"} />
      <MetaRow icon={Calendar} label="Win Rate" value={`${(winRate * 100).toFixed(1)}%`} />
      <MetaRow icon={Layers} label="Total Trades" value={String(tradeCount)} />
      <MetaRow icon={Target} label="Action" value={strategy.action || "BUY"} />
      <MetaRow icon={TrendingUp} label="Stop Loss" value={`${((strategy.stop_loss_pct || 0.02) * 100).toFixed(1)}%`} />
      <MetaRow icon={TrendingUp} label="Take Profit" value={`${((strategy.take_profit_pct || 0.05) * 100).toFixed(1)}%`} />
    </div>
  );
}
```

**Step 2: StrategyDecisionPipeline.tsx — interactive flowchart**

```tsx
// frontend/src/components/quant/StrategyDecisionPipeline.tsx
"use client";

import React, { useState } from "react";

const PIPELINE_NODES = [
  {
    id: "market_data",
    label: "Market Data",
    color: "bg-blue-400/10 border-blue-400/30 text-blue-400",
    detail: "OHLCV price data from market feed. Bars are fetched for the configured timeframe (1m to 1W).",
  },
  {
    id: "feature_eng",
    label: "Feature Engineering",
    color: "bg-violet-400/10 border-violet-400/30 text-violet-400",
    detail: "Raw price data transformed into derived features: log returns, rolling statistics, normalized volume.",
  },
  {
    id: "indicators",
    label: "Indicator Signals",
    color: "bg-cyan-400/10 border-cyan-400/30 text-cyan-400",
    detail: "Technical indicators computed: RSI, MACD, Bollinger Bands, EMA, SMA, ATR, VWAP, OBV, Stochastic.",
  },
  {
    id: "ai_model",
    label: "AI Model Decision",
    color: "bg-primary/10 border-primary/30 text-primary",
    detail: "Entry conditions evaluated using AND-within-group / OR-between-group logic. Confidence score assigned.",
  },
  {
    id: "risk_filter",
    label: "Risk Filter",
    color: "bg-amber-400/10 border-amber-400/30 text-amber-400",
    detail: "Stop loss, take profit, cooldown period, max trades per day, exposure limits applied before order.",
  },
  {
    id: "position_sizing",
    label: "Position Sizing",
    color: "bg-emerald-400/10 border-emerald-400/30 text-emerald-400",
    detail: "Capital allocated based on position_size_pct and available portfolio equity. Commission + slippage applied.",
  },
  {
    id: "trade_exec",
    label: "Trade Execution",
    color: "bg-orange-400/10 border-orange-400/30 text-orange-400",
    detail: "Order submitted to broker (or paper portfolio). Entry price, timestamp, and order ID recorded.",
  },
];

export function StrategyDecisionPipeline() {
  const [hovered, setHovered] = useState<string | null>(null);
  const activeNode = PIPELINE_NODES.find((n) => n.id === hovered);

  return (
    <div className="rounded-lg border border-border/50 bg-card p-4">
      <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-4">
        Strategy Decision Pipeline
      </div>
      <div className="flex gap-4">
        {/* Flow diagram */}
        <div className="flex flex-col items-center gap-0 min-w-[180px]">
          {PIPELINE_NODES.map((node, idx) => (
            <React.Fragment key={node.id}>
              <button
                onMouseEnter={() => setHovered(node.id)}
                onMouseLeave={() => setHovered(null)}
                className={`w-full px-3 py-2 rounded-lg border text-xs font-semibold text-center transition-all cursor-default ${node.color} ${
                  hovered === node.id ? "scale-105 shadow-lg" : ""
                }`}
              >
                {node.label}
              </button>
              {idx < PIPELINE_NODES.length - 1 && (
                <div className="flex flex-col items-center py-0.5">
                  <div className="w-px h-3 bg-border/50" />
                  <svg className="h-2 w-2 text-muted-foreground/50" viewBox="0 0 8 8">
                    <path d="M4 8 L0 0 L8 0 Z" fill="currentColor" />
                  </svg>
                </div>
              )}
            </React.Fragment>
          ))}
        </div>

        {/* Detail panel */}
        <div className="flex-1 min-h-[200px]">
          {activeNode ? (
            <div className={`rounded-lg border p-4 h-full text-sm ${activeNode.color}`}>
              <div className="font-semibold mb-2">{activeNode.label}</div>
              <p className="text-xs leading-relaxed opacity-90">{activeNode.detail}</p>
            </div>
          ) : (
            <div className="rounded-lg border border-border/30 p-4 h-full flex items-center justify-center text-xs text-muted-foreground text-center">
              Hover a node to see<br />pipeline stage details
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
```

**Step 3: AIReasoningPanel.tsx**

```tsx
// frontend/src/components/quant/AIReasoningPanel.tsx
"use client";

import React, { useState } from "react";
import { ChevronDown, Brain, CheckCircle, XCircle } from "lucide-react";
import type { QuantTrade } from "@/types/quant";

interface ReasoningEntry {
  tradeIndex: number;
  trade: QuantTrade;
  reasoning_summary: string;
  supporting_signals: string[];
  rejected_signals: string[];
  ai_confidence_score: number;
  market_regime: string;
  decision_factors: Record<string, number | string | boolean>;
}

interface AIReasoningPanelProps {
  trades: QuantTrade[];
  strategyId: number;
}

function ConfidenceBadge({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const color =
    pct >= 75 ? "text-emerald-400 bg-emerald-400/10 border-emerald-400/20"
    : pct >= 55 ? "text-amber-400 bg-amber-400/10 border-amber-400/20"
    : "text-red-400 bg-red-400/10 border-red-400/20";
  return (
    <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded border font-mono ${color}`}>
      {pct}%
    </span>
  );
}

export function AIReasoningPanel({ trades, strategyId }: AIReasoningPanelProps) {
  const [expanded, setExpanded] = useState<number | null>(null);
  const [logs, setLogs] = useState<Record<number, ReasoningEntry>>({});
  const [loading, setLoading] = useState<number | null>(null);

  const displayTrades = trades.slice(0, 10);

  const loadReasoning = async (idx: number) => {
    if (logs[idx]) {
      setExpanded(expanded === idx ? null : idx);
      return;
    }
    setLoading(idx);
    try {
      const { apiFetch } = await import("@/lib/api/client");
      const data = await apiFetch<ReasoningEntry>(
        `/api/quant/trades/${idx}/reasoning?strategy_id=${strategyId}&lookback_days=252`
      );
      setLogs((prev) => ({ ...prev, [idx]: data }));
      setExpanded(idx);
    } catch {
      // ignore
    } finally {
      setLoading(null);
    }
  };

  return (
    <div className="rounded-lg border border-border/50 bg-card">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-border/50">
        <Brain className="h-4 w-4 text-primary" />
        <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          AI Reasoning Logs
        </span>
        <div className="ml-auto flex items-center gap-1.5 text-emerald-400">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
          <span className="text-[10px] font-medium">Active</span>
        </div>
      </div>
      <div className="divide-y divide-border/30">
        {displayTrades.length === 0 ? (
          <div className="py-8 text-center text-sm text-muted-foreground">
            No trades to display
          </div>
        ) : (
          displayTrades.map((trade, idx) => {
            const log = logs[idx];
            const isOpen = expanded === idx;
            const isLoading = loading === idx;
            const isWin = trade.pnl > 0;

            return (
              <div key={idx}>
                <button
                  onClick={() => loadReasoning(idx)}
                  className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-muted/20 transition-colors"
                >
                  <span className={`text-xs font-mono font-bold w-12 ${isWin ? "text-emerald-400" : "text-red-400"}`}>
                    {isWin ? "+" : ""}${trade.pnl.toFixed(0)}
                  </span>
                  <span className="text-xs text-muted-foreground">{trade.entry_date}</span>
                  <span className="text-[10px] font-mono text-muted-foreground">{trade.direction}</span>
                  {log && <ConfidenceBadge score={log.ai_confidence_score} />}
                  {log && (
                    <span className="text-[10px] text-muted-foreground/60 ml-1">
                      {log.market_regime}
                    </span>
                  )}
                  <ChevronDown className={`h-3.5 w-3.5 text-muted-foreground ml-auto transition-transform ${isOpen ? "rotate-180" : ""}`} />
                </button>

                {isOpen && log && (
                  <div className="px-4 pb-4 space-y-3 bg-muted/10">
                    <p className="text-xs text-muted-foreground italic leading-relaxed">
                      {log.reasoning_summary}
                    </p>
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <div className="text-[10px] font-bold uppercase tracking-wider text-emerald-400 mb-1.5">
                          Supporting Signals
                        </div>
                        {log.supporting_signals.map((s, i) => (
                          <div key={i} className="flex items-center gap-1.5 text-[11px] text-muted-foreground mb-1">
                            <CheckCircle className="h-3 w-3 text-emerald-400 shrink-0" />
                            {s}
                          </div>
                        ))}
                      </div>
                      <div>
                        <div className="text-[10px] font-bold uppercase tracking-wider text-red-400 mb-1.5">
                          Rejected Signals
                        </div>
                        {log.rejected_signals.length === 0 ? (
                          <div className="text-[11px] text-muted-foreground/50">None</div>
                        ) : (
                          log.rejected_signals.map((s, i) => (
                            <div key={i} className="flex items-center gap-1.5 text-[11px] text-muted-foreground mb-1">
                              <XCircle className="h-3 w-3 text-red-400 shrink-0" />
                              {s}
                            </div>
                          ))
                        )}
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {Object.entries(log.decision_factors).map(([k, v]) => (
                        <span key={k} className="text-[10px] font-mono px-2 py-0.5 rounded bg-muted border border-border/50">
                          {k}: {String(v)}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {isLoading && (
                  <div className="px-4 pb-3 text-xs text-muted-foreground">
                    Loading reasoning…
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
```

**Step 4: OverviewTab.tsx**

```tsx
// frontend/src/components/quant/OverviewTab.tsx
"use client";

import React from "react";
import { Loader2 } from "lucide-react";
import type { QuantAnalyticsResponse, FeatureImportanceResponse } from "@/types/quant";
import type { StrategyRecord } from "@/types/strategy";
import { BotMetadataPanel } from "./BotMetadataPanel";
import { StrategyDecisionPipeline } from "./StrategyDecisionPipeline";
import { AIReasoningPanel } from "./AIReasoningPanel";
import { MetricCardsRow } from "./MetricCardsRow";
import { FeatureImportanceChart } from "./FeatureImportanceChart";

interface OverviewTabProps {
  strategy: StrategyRecord;
  analytics: QuantAnalyticsResponse | null;
  featureImportance: FeatureImportanceResponse | null;
  loading: boolean;
}

export function OverviewTab({ strategy, analytics, featureImportance, loading }: OverviewTabProps) {
  if (loading && !analytics) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const metrics = analytics?.metrics;
  const trades = analytics?.trades || [];

  return (
    <div className="space-y-6">
      {/* Metric summary */}
      {metrics && <MetricCardsRow metrics={metrics} />}

      {/* Two-column: metadata + pipeline */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <BotMetadataPanel
          strategy={strategy}
          tradeCount={metrics?.num_trades ?? 0}
          winRate={metrics?.win_rate ?? 0}
        />
        <StrategyDecisionPipeline />
      </div>

      {/* Strategy description */}
      {strategy.description && (
        <div className="rounded-lg border border-border/50 bg-card p-4">
          <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">
            Strategy Description
          </div>
          <p className="text-sm text-muted-foreground leading-relaxed">{strategy.description}</p>
        </div>
      )}

      {/* Feature importance */}
      {featureImportance && featureImportance.feature_importance.length > 0 && (
        <FeatureImportanceChart data={featureImportance.feature_importance} />
      )}

      {/* AI Reasoning */}
      <AIReasoningPanel trades={trades} strategyId={strategy.id} />
    </div>
  );
}
```

**Step 5: Commit**

```bash
git add frontend/src/components/quant/
git commit -m "feat: quant Overview tab — BotMetadataPanel, StrategyDecisionPipeline, AIReasoningPanel"
```

---

## Task 10: MetricCardsRow + all chart components

**Files:**
- Create: `frontend/src/components/quant/MetricCardsRow.tsx`
- Create: `frontend/src/components/quant/RollingSharpChart.tsx`
- Create: `frontend/src/components/quant/DrawdownChart.tsx`
- Create: `frontend/src/components/quant/ProfitDistributionChart.tsx`
- Create: `frontend/src/components/quant/TradeDurationHistogram.tsx`
- Create: `frontend/src/components/quant/AnalyticsTab.tsx`

**Step 1: MetricCardsRow.tsx**

```tsx
// frontend/src/components/quant/MetricCardsRow.tsx
"use client";

import React from "react";
import type { QuantMetrics } from "@/types/quant";

interface MetricCardProps {
  label: string;
  value: string;
  subtext?: string;
  positive?: boolean;
  negative?: boolean;
}

function MetricCard({ label, value, subtext, positive, negative }: MetricCardProps) {
  const valueColor = positive ? "text-emerald-400" : negative ? "text-red-400" : "text-foreground";
  return (
    <div className="rounded-lg border border-border/50 bg-card p-3">
      <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1">{label}</div>
      <div className={`text-lg font-mono font-bold ${valueColor}`}>{value}</div>
      {subtext && <div className="text-[10px] text-muted-foreground mt-0.5">{subtext}</div>}
    </div>
  );
}

function fmtPct(v: number, decimals = 1) {
  return `${v >= 0 ? "+" : ""}${(v * 100).toFixed(decimals)}%`;
}

function fmtRatio(v: number) {
  return v.toFixed(3);
}

function fmtCurrency(v: number) {
  return `$${v.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
}

export function MetricCardsRow({ metrics }: { metrics: QuantMetrics }) {
  const cards: MetricCardProps[] = [
    {
      label: "Total Return",
      value: fmtPct(metrics.total_return),
      positive: metrics.total_return > 0,
      negative: metrics.total_return < 0,
    },
    {
      label: "Annualized Return",
      value: fmtPct(metrics.annualized_return),
      positive: metrics.annualized_return > 0,
      negative: metrics.annualized_return < 0,
    },
    {
      label: "Sharpe Ratio",
      value: fmtRatio(metrics.sharpe_ratio),
      subtext: metrics.sharpe_ratio >= 1 ? "Good" : metrics.sharpe_ratio >= 0 ? "Below avg" : "Poor",
      positive: metrics.sharpe_ratio >= 1,
      negative: metrics.sharpe_ratio < 0,
    },
    {
      label: "Sortino Ratio",
      value: fmtRatio(metrics.sortino_ratio),
      positive: metrics.sortino_ratio >= 1,
      negative: metrics.sortino_ratio < 0,
    },
    {
      label: "Calmar Ratio",
      value: fmtRatio(metrics.calmar_ratio),
      positive: metrics.calmar_ratio >= 1,
    },
    {
      label: "Max Drawdown",
      value: fmtPct(metrics.max_drawdown),
      negative: true,
    },
    {
      label: "Volatility",
      value: fmtPct(metrics.volatility),
    },
    {
      label: "Win Rate",
      value: `${(metrics.win_rate * 100).toFixed(1)}%`,
      positive: metrics.win_rate >= 0.5,
      negative: metrics.win_rate < 0.4,
    },
    {
      label: "Avg Win",
      value: fmtCurrency(metrics.avg_win),
      positive: metrics.avg_win > 0,
    },
    {
      label: "Avg Loss",
      value: fmtCurrency(metrics.avg_loss),
      negative: metrics.avg_loss < 0,
    },
    {
      label: "Profit Factor",
      value: fmtRatio(metrics.profit_factor),
      positive: metrics.profit_factor >= 1.5,
      negative: metrics.profit_factor < 1,
    },
  ];

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-2">
      {cards.map((c) => (
        <MetricCard key={c.label} {...c} />
      ))}
    </div>
  );
}
```

**Step 2: RollingSharpChart.tsx**

```tsx
// frontend/src/components/quant/RollingSharpChart.tsx
"use client";

import React from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ReferenceLine, ResponsiveContainer,
} from "recharts";

interface Props {
  data: { date: string; sharpe: number }[];
}

export function RollingSharpChart({ data }: Props) {
  if (!data || data.length === 0) {
    return (
      <div className="rounded-lg border border-border/50 bg-card p-4 flex items-center justify-center h-48 text-sm text-muted-foreground">
        Insufficient data for rolling Sharpe
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-border/50 bg-card p-4">
      <div className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-3">
        Rolling 30-Day Sharpe Ratio
      </div>
      <ResponsiveContainer width="100%" height={200}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
          <XAxis dataKey="date" tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
            tickFormatter={(d) => d.slice(5)} interval="preserveStartEnd" />
          <YAxis width={45} tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
            tickFormatter={(v) => v.toFixed(1)} />
          <Tooltip
            contentStyle={{ backgroundColor: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: "6px", fontSize: "12px" }}
            formatter={(v) => [Number(v).toFixed(3), "Sharpe"]}
          />
          <ReferenceLine y={0} stroke="hsl(var(--muted-foreground))" strokeDasharray="4 4" />
          <ReferenceLine y={1} stroke="#10b981" strokeDasharray="4 4"
            label={{ value: "1.0", position: "right", fontSize: 9, fill: "#10b981" }} />
          <Line type="monotone" dataKey="sharpe" stroke="#60a5fa" strokeWidth={1.5} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
```

**Step 3: DrawdownChart.tsx** (recharts version, replaces the SVG one from backtest page)

```tsx
// frontend/src/components/quant/DrawdownChart.tsx
"use client";

import React from "react";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";

interface Props {
  data: { date: string; drawdown: number }[];
}

export function DrawdownChart({ data }: Props) {
  if (!data || data.length === 0) {
    return (
      <div className="rounded-lg border border-border/50 bg-card p-4 flex items-center justify-center h-48 text-sm text-muted-foreground">
        No drawdown data
      </div>
    );
  }

  const minDD = Math.min(...data.map((d) => d.drawdown));

  return (
    <div className="rounded-lg border border-border/50 bg-card p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
          Drawdown Curve
        </div>
        <span className="text-xs font-mono font-bold text-red-400">
          Max: {minDD.toFixed(1)}%
        </span>
      </div>
      <ResponsiveContainer width="100%" height={200}>
        <AreaChart data={data}>
          <defs>
            <linearGradient id="ddGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
          <XAxis dataKey="date" tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
            tickFormatter={(d) => d.slice(5)} interval="preserveStartEnd" />
          <YAxis width={50} tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
            tickFormatter={(v) => `${v.toFixed(0)}%`} />
          <Tooltip
            contentStyle={{ backgroundColor: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: "6px", fontSize: "12px" }}
            formatter={(v) => [`${Number(v).toFixed(2)}%`, "Drawdown"]}
          />
          <Area type="monotone" dataKey="drawdown" stroke="#ef4444" fill="url(#ddGradient)" strokeWidth={1.5} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
```

**Step 4: ProfitDistributionChart.tsx**

```tsx
// frontend/src/components/quant/ProfitDistributionChart.tsx
"use client";

import React from "react";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Cell, ResponsiveContainer } from "recharts";

interface Props {
  data: { bin: number; count: number }[];
}

export function ProfitDistributionChart({ data }: Props) {
  if (!data || data.length === 0) {
    return (
      <div className="rounded-lg border border-border/50 bg-card p-4 flex items-center justify-center h-48 text-sm text-muted-foreground">
        No trade data
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-border/50 bg-card p-4">
      <div className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-3">
        Profit Distribution
      </div>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={data} barCategoryGap="5%">
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
          <XAxis dataKey="bin" tick={{ fontSize: 9, fill: "hsl(var(--muted-foreground))" }}
            tickFormatter={(v) => `$${Number(v).toFixed(0)}`} interval={Math.floor(data.length / 6)} />
          <YAxis width={35} tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }} />
          <Tooltip
            contentStyle={{ backgroundColor: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: "6px", fontSize: "12px" }}
            formatter={(v, _, props) => [v, `P&L ≈ $${Number(props.payload.bin).toFixed(0)}`]}
          />
          <Bar dataKey="count" radius={[2, 2, 0, 0]}>
            {data.map((entry, i) => (
              <Cell key={i} fill={entry.bin >= 0 ? "#10b981" : "#ef4444"} fillOpacity={0.8} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
```

**Step 5: TradeDurationHistogram.tsx**

```tsx
// frontend/src/components/quant/TradeDurationHistogram.tsx
"use client";

import React from "react";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";

interface Props {
  data: { days: number; count: number }[];
}

export function TradeDurationHistogram({ data }: Props) {
  if (!data || data.length === 0) {
    return (
      <div className="rounded-lg border border-border/50 bg-card p-4 flex items-center justify-center h-48 text-sm text-muted-foreground">
        No duration data
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-border/50 bg-card p-4">
      <div className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-3">
        Trade Duration Histogram
      </div>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
          <XAxis dataKey="days" tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
            tickFormatter={(v) => `${v}d`} />
          <YAxis width={35} tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }} />
          <Tooltip
            contentStyle={{ backgroundColor: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: "6px", fontSize: "12px" }}
            formatter={(v, _, props) => [v, `${props.payload.days} days`]}
          />
          <Bar dataKey="count" fill="#60a5fa" fillOpacity={0.8} radius={[2, 2, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
```

**Step 6: AnalyticsTab.tsx**

```tsx
// frontend/src/components/quant/AnalyticsTab.tsx
"use client";

import React from "react";
import { Loader2 } from "lucide-react";
import type { QuantAnalyticsResponse } from "@/types/quant";
import { MetricCardsRow } from "./MetricCardsRow";
import { EquityCurveChart } from "@/components/charts/EquityCurveChart";
import { RollingSharpChart } from "./RollingSharpChart";
import { DrawdownChart } from "./DrawdownChart";
import { ProfitDistributionChart } from "./ProfitDistributionChart";
import { TradeDurationHistogram } from "./TradeDurationHistogram";

interface AnalyticsTabProps {
  analytics: QuantAnalyticsResponse | null;
  loading: boolean;
}

export function AnalyticsTab({ analytics, loading }: AnalyticsTabProps) {
  if (loading && !analytics) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }
  if (!analytics) {
    return (
      <div className="text-center py-16 text-muted-foreground text-sm">
        No analytics data available
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <MetricCardsRow metrics={analytics.metrics} />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <EquityCurveChart
          data={analytics.equity_curve}
          initialCapital={analytics.initial_capital}
          height={250}
        />
        <DrawdownChart data={analytics.drawdown_curve} />
      </div>

      <RollingSharpChart data={analytics.rolling_sharpe} />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <ProfitDistributionChart data={analytics.profit_distribution} />
        <TradeDurationHistogram data={analytics.duration_distribution} />
      </div>
    </div>
  );
}
```

**Step 7: Commit**

```bash
git add frontend/src/components/quant/
git commit -m "feat: MetricCardsRow and performance chart components"
```

---

## Task 11: Heatmaps tab

**Files:**
- Create: `frontend/src/components/quant/HeatmapGrid.tsx`
- Create: `frontend/src/components/quant/HeatmapsTab.tsx`

**Step 1: HeatmapGrid.tsx — SVG-based heatmap**

```tsx
// frontend/src/components/quant/HeatmapGrid.tsx
"use client";

import React, { useState } from "react";

interface HeatmapCell {
  label: string;
  value: number;
  count: number;
}

interface HeatmapGridProps {
  title: string;
  cells: HeatmapCell[];
  valueLabel?: string;
}

function cellColor(value: number, min: number, max: number): string {
  if (max === min) return "bg-muted/40";
  const norm = (value - min) / (max - min); // 0 (min) to 1 (max)
  if (value < 0) {
    // negative: red shading
    const intensity = Math.min(Math.abs(value / Math.min(min, -0.01)), 1);
    const alpha = Math.round(intensity * 70 + 10);
    return `rgba(239,68,68,${alpha / 100})`;
  } else {
    // positive: green shading
    const intensity = Math.min(value / Math.max(max, 0.01), 1);
    const alpha = Math.round(intensity * 70 + 10);
    return `rgba(16,185,129,${alpha / 100})`;
  }
}

export function HeatmapGrid({ title, cells, valueLabel = "Avg P&L" }: HeatmapGridProps) {
  const [hovered, setHovered] = useState<HeatmapCell | null>(null);

  if (!cells || cells.length === 0) {
    return (
      <div className="rounded-lg border border-border/50 bg-card p-4">
        <div className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">{title}</div>
        <div className="text-sm text-muted-foreground py-4 text-center">Insufficient trade data</div>
      </div>
    );
  }

  const values = cells.map((c) => c.value);
  const min = Math.min(...values);
  const max = Math.max(...values);

  return (
    <div className="rounded-lg border border-border/50 bg-card p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="text-xs font-medium text-muted-foreground uppercase tracking-wider">{title}</div>
        {hovered && (
          <div className="text-xs font-mono text-muted-foreground">
            {hovered.label}: ${hovered.value.toFixed(2)} ({hovered.count} trades)
          </div>
        )}
      </div>
      <div className="flex flex-wrap gap-1.5">
        {cells.map((cell, i) => (
          <div
            key={i}
            onMouseEnter={() => setHovered(cell)}
            onMouseLeave={() => setHovered(null)}
            className="rounded px-2.5 py-2 cursor-default transition-transform hover:scale-110 hover:z-10 relative border border-border/20"
            style={{ backgroundColor: cellColor(cell.value, min, max) }}
          >
            <div className="text-[10px] font-medium text-center whitespace-nowrap">{cell.label}</div>
            <div className={`text-[10px] font-mono font-bold text-center ${cell.value >= 0 ? "text-emerald-400" : "text-red-400"}`}>
              {cell.value >= 0 ? "+" : ""}${cell.value.toFixed(0)}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
```

**Step 2: HeatmapsTab.tsx**

```tsx
// frontend/src/components/quant/HeatmapsTab.tsx
"use client";

import React from "react";
import { Loader2 } from "lucide-react";
import type { HeatmapsResponse } from "@/types/quant";
import { HeatmapGrid } from "./HeatmapGrid";

interface HeatmapsTabProps {
  heatmaps: HeatmapsResponse | null;
  loading: boolean;
}

export function HeatmapsTab({ heatmaps, loading }: HeatmapsTabProps) {
  if (loading && !heatmaps) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }
  if (!heatmaps) {
    return (
      <div className="text-center py-16 text-muted-foreground text-sm">No heatmap data available</div>
    );
  }

  const hourCells = heatmaps.by_hour.map((h) => ({
    label: `${h.hour}:00`,
    value: h.avg_pnl,
    count: h.count,
  }));

  const weekdayCells = heatmaps.by_weekday.map((d) => ({
    label: d.day,
    value: d.avg_pnl,
    count: d.count,
  }));

  return (
    <div className="space-y-4">
      <div className="text-sm text-muted-foreground">
        Strategy performance heatmaps — identify when the strategy works best.
      </div>
      <HeatmapGrid title="Profit by Hour of Day" cells={hourCells} />
      <HeatmapGrid title="Profit by Weekday" cells={weekdayCells} />
    </div>
  );
}
```

**Step 3: Commit**

```bash
git add frontend/src/components/quant/HeatmapGrid.tsx frontend/src/components/quant/HeatmapsTab.tsx
git commit -m "feat: heatmap grid component and Heatmaps tab"
```

---

## Task 12: Monte Carlo tab

**Files:**
- Create: `frontend/src/components/quant/MonteCarloChart.tsx`
- Create: `frontend/src/components/quant/MonteCarloTab.tsx`

**Step 1: MonteCarloChart.tsx**

```tsx
// frontend/src/components/quant/MonteCarloChart.tsx
"use client";

import React from "react";
import {
  ComposedChart, Area, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ReferenceLine, ResponsiveContainer, Legend,
} from "recharts";
import type { MonteCarloBand } from "@/types/quant";

interface MonteCarloChartProps {
  data: MonteCarloBand[];
  initialCapital: number;
}

export function MonteCarloChart({ data, initialCapital }: MonteCarloChartProps) {
  if (!data || data.length === 0) {
    return (
      <div className="rounded-lg border border-border/50 bg-card p-4 flex items-center justify-center h-64 text-sm text-muted-foreground">
        No simulation data
      </div>
    );
  }

  const formatK = (v: number) => {
    if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(1)}M`;
    return `$${(v / 1_000).toFixed(0)}k`;
  };

  return (
    <div className="rounded-lg border border-border/50 bg-card p-4">
      <div className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-3">
        Monte Carlo Simulation
      </div>
      <ResponsiveContainer width="100%" height={300}>
        <ComposedChart data={data}>
          <defs>
            <linearGradient id="mcGradOuter" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#6366f1" stopOpacity={0.1} />
              <stop offset="100%" stopColor="#6366f1" stopOpacity={0.02} />
            </linearGradient>
            <linearGradient id="mcGradInner" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#6366f1" stopOpacity={0.25} />
              <stop offset="100%" stopColor="#6366f1" stopOpacity={0.05} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
          <XAxis dataKey="step" tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
            tickFormatter={(v) => `T${v}`} interval={Math.floor(data.length / 8)} />
          <YAxis width={65} tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
            tickFormatter={formatK} />
          <Tooltip
            contentStyle={{ backgroundColor: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: "6px", fontSize: "11px" }}
            formatter={(v: number, name: string) => [formatK(v), name]}
          />
          {/* Outer band: 5%-95% */}
          <Area type="monotone" dataKey="p95" stroke="none" fill="url(#mcGradOuter)" />
          <Area type="monotone" dataKey="p5" stroke="none" fill="white" fillOpacity={1} />
          {/* Inner band: 25%-75% */}
          <Area type="monotone" dataKey="p75" stroke="none" fill="url(#mcGradInner)" />
          <Area type="monotone" dataKey="p25" stroke="none" fill="white" fillOpacity={1} />
          {/* Median */}
          <Line type="monotone" dataKey="p50" stroke="#6366f1" strokeWidth={2} dot={false} name="Median" />
          <ReferenceLine y={initialCapital} stroke="hsl(var(--muted-foreground))"
            strokeDasharray="6 4"
            label={{ value: "Initial", position: "right", fontSize: 9, fill: "hsl(var(--muted-foreground))" }} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
```

**Step 2: MonteCarloTab.tsx**

```tsx
// frontend/src/components/quant/MonteCarloTab.tsx
"use client";

import React from "react";
import { Loader2, AlertTriangle, TrendingUp, TrendingDown } from "lucide-react";
import type { MonteCarloResponse } from "@/types/quant";
import { MonteCarloChart } from "./MonteCarloChart";

interface MonteCarloTabProps {
  montecarlo: MonteCarloResponse | null;
  loading: boolean;
}

function StatBox({ label, value, sub, danger }: {
  label: string; value: string; sub?: string; danger?: boolean;
}) {
  return (
    <div className={`rounded-lg border p-4 ${danger ? "border-red-400/30 bg-red-400/5" : "border-border/50 bg-card"}`}>
      <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1">{label}</div>
      <div className={`text-xl font-mono font-bold ${danger ? "text-red-400" : ""}`}>{value}</div>
      {sub && <div className="text-[10px] text-muted-foreground mt-0.5">{sub}</div>}
    </div>
  );
}

export function MonteCarloTab({ montecarlo, loading }: MonteCarloTabProps) {
  if (loading && !montecarlo) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }
  if (!montecarlo) {
    return (
      <div className="text-center py-16 text-muted-foreground text-sm">
        No Monte Carlo data available
      </div>
    );
  }

  const ruin = montecarlo.risk_of_ruin;
  const fmt = (v: number) => `$${v.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;

  return (
    <div className="space-y-4">
      <div className="text-sm text-muted-foreground">
        {montecarlo.n_simulations.toLocaleString()} bootstrap simulations of trade sequence.
        Shaded bands show 5th–95th and 25th–75th percentile paths.
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <StatBox label="Median Final" value={fmt(montecarlo.median_final)}
          sub={`vs ${fmt(montecarlo.initial_capital)} initial`} />
        <StatBox label="Best Case (95th)" value={fmt(montecarlo.best_case)} />
        <StatBox label="Worst Case (5th)" value={fmt(montecarlo.worst_case)}
          danger={montecarlo.worst_case < montecarlo.initial_capital * 0.5} />
        <StatBox
          label="Risk of Ruin"
          value={`${(ruin * 100).toFixed(1)}%`}
          sub="Probability of losing >50%"
          danger={ruin > 0.1}
        />
      </div>

      {ruin > 0.1 && (
        <div className="flex items-center gap-2 px-4 py-3 rounded-lg bg-red-400/10 border border-red-400/30 text-red-400 text-sm">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          High risk of ruin ({(ruin * 100).toFixed(1)}%). Consider tightening stop losses or reducing position size.
        </div>
      )}

      <MonteCarloChart data={montecarlo.confidence_bands} initialCapital={montecarlo.initial_capital} />
    </div>
  );
}
```

**Step 3: Commit**

```bash
git add frontend/src/components/quant/MonteCarloChart.tsx frontend/src/components/quant/MonteCarloTab.tsx
git commit -m "feat: Monte Carlo chart and tab"
```

---

## Task 13: Feature Importance chart

**Files:**
- Create: `frontend/src/components/quant/FeatureImportanceChart.tsx`

```tsx
// frontend/src/components/quant/FeatureImportanceChart.tsx
"use client";

import React from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  Cell, LabelList, ResponsiveContainer,
} from "recharts";
import type { FeatureImportanceItem } from "@/types/quant";

const COLORS = ["#6366f1", "#60a5fa", "#34d399", "#f59e0b", "#f87171", "#a78bfa", "#fb923c", "#22d3ee"];

interface FeatureImportanceChartProps {
  data: FeatureImportanceItem[];
}

export function FeatureImportanceChart({ data }: FeatureImportanceChartProps) {
  if (!data || data.length === 0) return null;

  return (
    <div className="rounded-lg border border-border/50 bg-card p-4">
      <div className="flex items-center gap-2 mb-3">
        <div className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
          AI Feature Importance
        </div>
        <span className="text-[10px] px-1.5 py-0.5 rounded bg-primary/10 text-primary border border-primary/20 font-mono">
          Rule Engine
        </span>
      </div>
      <ResponsiveContainer width="100%" height={Math.max(120, data.length * 36)}>
        <BarChart
          data={data}
          layout="vertical"
          margin={{ left: 8, right: 40, top: 4, bottom: 4 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" horizontal={false} />
          <XAxis type="number" domain={[0, 1]} tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
            tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }} />
          <YAxis type="category" dataKey="indicator" width={90}
            tick={{ fontSize: 11, fill: "hsl(var(--foreground))" }} />
          <Tooltip
            contentStyle={{ backgroundColor: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: "6px", fontSize: "12px" }}
            formatter={(v) => [`${(Number(v) * 100).toFixed(1)}%`, "Importance"]}
          />
          <Bar dataKey="importance" radius={[0, 4, 4, 0]}>
            {data.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
            <LabelList dataKey="pct" position="right"
              formatter={(v: number) => `${v}%`}
              style={{ fontSize: 11, fill: "hsl(var(--foreground))" }} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
```

**Step: Commit**

```bash
git add frontend/src/components/quant/FeatureImportanceChart.tsx
git commit -m "feat: AI feature importance horizontal bar chart"
```

---

## Task 14: Trade History table + Trade Forensics modal

**Files:**
- Create: `frontend/src/components/quant/TradeHistoryTable.tsx`
- Create: `frontend/src/components/quant/TradeForensicsModal.tsx`

**Step 1: TradeHistoryTable.tsx**

```tsx
// frontend/src/components/quant/TradeHistoryTable.tsx
"use client";

import React, { useState } from "react";
import { ChevronRight } from "lucide-react";
import type { QuantTrade } from "@/types/quant";
import { TradeForensicsModal } from "./TradeForensicsModal";

interface TradeHistoryTableProps {
  trades: QuantTrade[];
  strategyId: number;
}

export function TradeHistoryTable({ trades, strategyId }: TradeHistoryTableProps) {
  const [selectedIdx, setSelectedIdx] = useState<number | null>(null);

  if (!trades || trades.length === 0) {
    return (
      <div className="rounded-lg border border-border/50 bg-card p-8 text-center text-sm text-muted-foreground">
        No trades executed
      </div>
    );
  }

  return (
    <>
      <div className="rounded-lg border border-border/50 bg-card overflow-hidden">
        <div className="px-4 py-3 border-b border-border/50 flex items-center justify-between">
          <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Trade History
          </span>
          <span className="text-xs font-mono text-muted-foreground">{trades.length} trades</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-border/50">
                {["#", "Entry", "Exit", "Direction", "Entry $", "Exit $", "P&L", "Return", "Bars", ""].map((h) => (
                  <th key={h} className="py-2 px-3 text-[10px] font-semibold text-muted-foreground uppercase tracking-wider whitespace-nowrap">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {trades.map((t, i) => {
                const isWin = t.pnl > 0;
                return (
                  <tr key={i}
                    className="border-b border-border/30 hover:bg-muted/20 cursor-pointer transition-colors"
                    onClick={() => setSelectedIdx(i)}
                  >
                    <td className="py-2 px-3 text-muted-foreground/50 font-mono text-[10px]">{i + 1}</td>
                    <td className="py-2 px-3 font-mono text-xs">{t.entry_date}</td>
                    <td className="py-2 px-3 font-mono text-xs">{t.exit_date}</td>
                    <td className="py-2 px-3">
                      <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                        t.direction === "BUY" ? "bg-emerald-400/10 text-emerald-400" : "bg-red-400/10 text-red-400"
                      }`}>
                        {t.direction}
                      </span>
                    </td>
                    <td className="py-2 px-3 font-mono text-xs">${t.entry_price.toFixed(2)}</td>
                    <td className="py-2 px-3 font-mono text-xs">${t.exit_price.toFixed(2)}</td>
                    <td className={`py-2 px-3 font-mono text-xs font-bold ${isWin ? "text-emerald-400" : "text-red-400"}`}>
                      {isWin ? "+" : ""}${t.pnl.toFixed(2)}
                    </td>
                    <td className={`py-2 px-3 font-mono text-xs ${isWin ? "text-emerald-400" : "text-red-400"}`}>
                      {isWin ? "+" : ""}{(t.pnl_pct * 100).toFixed(2)}%
                    </td>
                    <td className="py-2 px-3 font-mono text-xs text-muted-foreground">{t.bars_held}d</td>
                    <td className="py-2 px-3">
                      <ChevronRight className="h-3.5 w-3.5 text-muted-foreground/30" />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {selectedIdx !== null && (
        <TradeForensicsModal
          tradeIndex={selectedIdx}
          trade={trades[selectedIdx]}
          strategyId={strategyId}
          onClose={() => setSelectedIdx(null)}
        />
      )}
    </>
  );
}
```

**Step 2: TradeForensicsModal.tsx**

```tsx
// frontend/src/components/quant/TradeForensicsModal.tsx
"use client";

import React, { useEffect, useState } from "react";
import { X, Brain, AlertCircle, CheckCircle, XCircle, Loader2 } from "lucide-react";
import type { QuantTrade, TradeReasoningResponse } from "@/types/quant";
import { apiFetch } from "@/lib/api/client";

interface TradeForensicsModalProps {
  tradeIndex: number;
  trade: QuantTrade;
  strategyId: number;
  onClose: () => void;
}

function GaugeArc({ value, max = 1, color }: { value: number; max?: number; color: string }) {
  const pct = Math.min(value / max, 1);
  const r = 36;
  const circ = Math.PI * r; // half circle
  const dash = pct * circ;
  return (
    <svg width="90" height="52" viewBox="0 0 90 52">
      {/* Track */}
      <path d="M 9 45 A 36 36 0 0 1 81 45" fill="none" stroke="hsl(var(--border))" strokeWidth="8" strokeLinecap="round" />
      {/* Fill */}
      <path d="M 9 45 A 36 36 0 0 1 81 45" fill="none" stroke={color}
        strokeWidth="8" strokeLinecap="round"
        strokeDasharray={`${dash} ${circ}`} />
      <text x="45" y="46" textAnchor="middle" fontSize="13" fontWeight="bold" fill={color} fontFamily="monospace">
        {Math.round(value * 100)}%
      </text>
    </svg>
  );
}

export function TradeForensicsModal({ tradeIndex, trade, strategyId, onClose }: TradeForensicsModalProps) {
  const [reasoning, setReasoning] = useState<TradeReasoningResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiFetch<TradeReasoningResponse>(
      `/api/quant/trades/${tradeIndex}/reasoning?strategy_id=${strategyId}&lookback_days=252`
    )
      .then(setReasoning)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [tradeIndex, strategyId]);

  const isWin = trade.pnl > 0;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <div className="w-full max-w-2xl max-h-[85vh] overflow-y-auto rounded-xl border border-border/50 bg-background shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border/50">
          <div className="flex items-center gap-2">
            <Brain className="h-5 w-5 text-primary" />
            <span className="font-semibold">Trade Forensics</span>
            <span className="text-xs text-muted-foreground">#{tradeIndex + 1}</span>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="p-6 space-y-5">
          {/* Trade Metadata */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {[
              { label: "Direction", value: trade.direction, colored: true },
              { label: "Entry", value: `$${trade.entry_price.toFixed(2)}` },
              { label: "Exit", value: `$${trade.exit_price.toFixed(2)}` },
              { label: "P&L", value: `${isWin ? "+" : ""}$${trade.pnl.toFixed(2)}`, win: isWin },
              { label: "Return", value: `${isWin ? "+" : ""}${(trade.pnl_pct * 100).toFixed(2)}%`, win: isWin },
              { label: "Entry Date", value: trade.entry_date },
              { label: "Exit Date", value: trade.exit_date },
              { label: "Duration", value: `${trade.bars_held} bars` },
            ].map((item) => (
              <div key={item.label} className="rounded-lg border border-border/50 bg-card p-3">
                <div className="text-[10px] text-muted-foreground uppercase tracking-wider">{item.label}</div>
                <div className={`text-sm font-mono font-bold mt-0.5 ${
                  item.win === true ? "text-emerald-400" : item.win === false ? "text-red-400" : ""
                }`}>
                  {item.value}
                </div>
              </div>
            ))}
          </div>

          {loading && (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            </div>
          )}

          {reasoning && (
            <>
              {/* Confidence + Risk gauges */}
              <div className="grid grid-cols-3 gap-4">
                <div className="rounded-lg border border-border/50 bg-card p-4 text-center">
                  <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-2">AI Confidence</div>
                  <div className="flex justify-center">
                    <GaugeArc value={reasoning.ai_confidence_score} color="#6366f1" />
                  </div>
                </div>
                <div className="rounded-lg border border-border/50 bg-card p-4 text-center">
                  <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-2">Risk Score</div>
                  <div className="flex justify-center">
                    <GaugeArc value={reasoning.risk_score} color="#f87171" />
                  </div>
                </div>
                <div className="rounded-lg border border-border/50 bg-card p-4 text-center">
                  <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-2">Predicted Return</div>
                  <div className="text-2xl font-mono font-bold mt-3 text-emerald-400">
                    {(reasoning.predicted_return * 100).toFixed(2)}%
                  </div>
                  <div className="text-[10px] text-muted-foreground mt-1">{reasoning.market_regime}</div>
                </div>
              </div>

              {/* Decision summary */}
              <div className="rounded-lg border border-border/50 bg-muted/20 p-4">
                <div className="flex items-center gap-2 mb-2">
                  <Brain className="h-3.5 w-3.5 text-primary" />
                  <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Decision Summary</span>
                </div>
                <p className="text-sm text-muted-foreground leading-relaxed italic">{reasoning.reasoning_summary}</p>
              </div>

              {/* Decision factors */}
              <div>
                <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">
                  Decision Factors
                </div>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(reasoning.decision_factors).map(([k, v]) => (
                    <div key={k} className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-border/50 bg-card">
                      <span className="text-[10px] font-bold text-muted-foreground uppercase">{k}</span>
                      <span className="text-xs font-mono font-medium">{String(v)}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Signals */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <div className="text-[10px] font-bold uppercase tracking-wider text-emerald-400 mb-2">
                    Supporting Signals ({reasoning.supporting_signals.length})
                  </div>
                  {reasoning.supporting_signals.map((s, i) => (
                    <div key={i} className="flex items-center gap-2 text-xs text-muted-foreground mb-1.5">
                      <CheckCircle className="h-3.5 w-3.5 text-emerald-400 shrink-0" />
                      {s}
                    </div>
                  ))}
                </div>
                <div>
                  <div className="text-[10px] font-bold uppercase tracking-wider text-amber-400 mb-2">
                    Rejected / Near-Miss ({reasoning.rejected_signals.length})
                  </div>
                  {reasoning.rejected_signals.length === 0 ? (
                    <div className="text-xs text-muted-foreground/50">None — all signals confirmed</div>
                  ) : (
                    reasoning.rejected_signals.map((s, i) => (
                      <div key={i} className="flex items-center gap-2 text-xs text-muted-foreground mb-1.5">
                        <AlertCircle className="h-3.5 w-3.5 text-amber-400 shrink-0" />
                        {s}
                      </div>
                    ))
                  )}
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
```

**Step 3: Commit**

```bash
git add frontend/src/components/quant/TradeHistoryTable.tsx frontend/src/components/quant/TradeForensicsModal.tsx
git commit -m "feat: trade history table and forensics modal with confidence gauge"
```

---

## Task 15: Risk tab + Regime tab components

**Files:**
- Create: `frontend/src/components/quant/RiskTab.tsx`

```tsx
// frontend/src/components/quant/RiskTab.tsx
"use client";

import React from "react";
import { Loader2, Shield } from "lucide-react";
import type { QuantAnalyticsResponse, RegimesResponse } from "@/types/quant";
import { EquityCurveChart } from "@/components/charts/EquityCurveChart";
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis,
  ResponsiveContainer, Tooltip,
} from "recharts";

interface RiskTabProps {
  analytics: QuantAnalyticsResponse | null;
  regimes: RegimesResponse | null;
  loading: boolean;
}

function RegimeCard({ name, stats }: {
  name: string;
  stats: { avg_pnl: number; total_pnl: number; trade_count: number; win_rate: number };
}) {
  const regimeColors: Record<string, string> = {
    bull: "text-emerald-400 bg-emerald-400/10 border-emerald-400/20",
    bear: "text-red-400 bg-red-400/10 border-red-400/20",
    sideways: "text-amber-400 bg-amber-400/10 border-amber-400/20",
    high_vol: "text-orange-400 bg-orange-400/10 border-orange-400/20",
    low_vol: "text-sky-400 bg-sky-400/10 border-sky-400/20",
  };
  const color = regimeColors[name] || "text-muted-foreground bg-muted border-border/50";

  return (
    <div className={`rounded-lg border p-4 ${color.split(" ").slice(1).join(" ")}`}>
      <div className={`text-xs font-bold uppercase tracking-wider mb-3 ${color.split(" ")[0]}`}>
        {name.replace("_", " ")} Regime
      </div>
      <div className="grid grid-cols-2 gap-2 text-xs">
        <div>
          <div className="text-muted-foreground">Avg P&L</div>
          <div className={`font-mono font-bold ${stats.avg_pnl >= 0 ? "text-emerald-400" : "text-red-400"}`}>
            {stats.avg_pnl >= 0 ? "+" : ""}${stats.avg_pnl.toFixed(2)}
          </div>
        </div>
        <div>
          <div className="text-muted-foreground">Win Rate</div>
          <div className="font-mono font-bold">{(stats.win_rate * 100).toFixed(0)}%</div>
        </div>
        <div>
          <div className="text-muted-foreground">Trades</div>
          <div className="font-mono">{stats.trade_count}</div>
        </div>
        <div>
          <div className="text-muted-foreground">Total P&L</div>
          <div className={`font-mono font-bold ${stats.total_pnl >= 0 ? "text-emerald-400" : "text-red-400"}`}>
            ${stats.total_pnl.toFixed(0)}
          </div>
        </div>
      </div>
    </div>
  );
}

export function RiskTab({ analytics, regimes, loading }: RiskTabProps) {
  if (loading && !analytics) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const metrics = analytics?.metrics;
  const radarData = metrics ? [
    { subject: "Sharpe", value: Math.min(Math.max((metrics.sharpe_ratio + 1) / 4, 0), 1) },
    { subject: "Win Rate", value: metrics.win_rate },
    { subject: "Profit F.", value: Math.min(metrics.profit_factor / 3, 1) },
    { subject: "Low DD", value: Math.min(1 - Math.abs(metrics.max_drawdown) * 2, 1) },
    { subject: "Sortino", value: Math.min(Math.max((metrics.sortino_ratio + 1) / 4, 0), 1) },
    { subject: "Return", value: Math.min(Math.max(metrics.total_return + 0.5, 0), 1) },
  ] : [];

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Risk radar chart */}
        {radarData.length > 0 && (
          <div className="rounded-lg border border-border/50 bg-card p-4">
            <div className="flex items-center gap-2 mb-3">
              <Shield className="h-4 w-4 text-primary" />
              <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Strategy Risk Profile
              </span>
            </div>
            <ResponsiveContainer width="100%" height={250}>
              <RadarChart data={radarData}>
                <PolarGrid stroke="hsl(var(--border))" />
                <PolarAngleAxis dataKey="subject" tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }} />
                <Radar dataKey="value" fill="#6366f1" fillOpacity={0.2} stroke="#6366f1" strokeWidth={2} />
                <Tooltip
                  contentStyle={{ backgroundColor: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: "6px", fontSize: "12px" }}
                  formatter={(v) => [(Number(v) * 100).toFixed(0) + "%", "Score"]}
                />
              </RadarChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Equity curve */}
        {analytics && (
          <EquityCurveChart
            data={analytics.equity_curve}
            initialCapital={analytics.initial_capital}
            height={250}
          />
        )}
      </div>

      {/* Regime performance */}
      {regimes && Object.keys(regimes.regime_performance).length > 0 && (
        <div>
          <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">
            Performance by Market Regime
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
            {Object.entries(regimes.regime_performance).map(([name, stats]) => (
              <RegimeCard key={name} name={name} stats={stats} />
            ))}
          </div>
        </div>
      )}

      {/* Risk parameters */}
      {analytics && (
        <div className="rounded-lg border border-border/50 bg-card p-4">
          <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">
            Risk Summary
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            {[
              { label: "Max Drawdown", value: `${(analytics.metrics.max_drawdown * 100).toFixed(2)}%`, danger: true },
              { label: "Volatility", value: `${(analytics.metrics.volatility * 100).toFixed(2)}%` },
              { label: "Calmar Ratio", value: analytics.metrics.calmar_ratio.toFixed(3) },
              { label: "Avg Loss", value: `$${Math.abs(analytics.metrics.avg_loss).toFixed(2)}`, danger: true },
            ].map((item) => (
              <div key={item.label}>
                <div className="text-[10px] text-muted-foreground uppercase tracking-wider">{item.label}</div>
                <div className={`text-lg font-mono font-bold mt-0.5 ${item.danger ? "text-red-400" : ""}`}>
                  {item.value}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
```

**Step: Commit**

```bash
git add frontend/src/components/quant/RiskTab.tsx
git commit -m "feat: Risk tab with radar chart and regime performance breakdown"
```

---

## Task 16: Trade Replay panel

**Files:**
- Create: `frontend/src/components/quant/TradeReplayPanel.tsx`

```tsx
// frontend/src/components/quant/TradeReplayPanel.tsx
"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import { Play, Pause, SkipBack, SkipForward, ChevronLeft, ChevronRight } from "lucide-react";
import type { QuantTrade } from "@/types/quant";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ReferenceLine, ResponsiveContainer,
} from "recharts";

interface TradeReplayPanelProps {
  trades: QuantTrade[];
  equityCurve: { date: string; value: number }[];
  initialCapital: number;
}

export function TradeReplayPanel({ trades, equityCurve, initialCapital }: TradeReplayPanelProps) {
  const [currentStep, setCurrentStep] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  const totalSteps = equityCurve.length;

  const step = useCallback(() => {
    setCurrentStep((prev) => {
      if (prev >= totalSteps - 1) {
        setPlaying(false);
        return prev;
      }
      return prev + 1;
    });
  }, [totalSteps]);

  useEffect(() => {
    if (playing) {
      intervalRef.current = setInterval(step, 200 / speed);
    } else {
      if (intervalRef.current) clearInterval(intervalRef.current);
    }
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [playing, speed, step]);

  const visibleCurve = equityCurve.slice(0, currentStep + 1);
  const currentEquity = equityCurve[currentStep]?.value ?? initialCapital;
  const currentReturn = ((currentEquity - initialCapital) / initialCapital) * 100;

  // Find trades that have occurred by this step
  const visibleTrades = trades.filter((t) => {
    const idx = equityCurve.findIndex((pt) => pt.date >= t.entry_date);
    return idx <= currentStep && idx >= 0;
  });

  const latestTrade = visibleTrades[visibleTrades.length - 1];

  return (
    <div className="rounded-lg border border-border/50 bg-card p-4 space-y-4">
      <div className="flex items-center justify-between">
        <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Trade Replay
        </div>
        <div className="text-xs font-mono text-muted-foreground">
          {equityCurve[currentStep]?.date || ""} — Step {currentStep + 1}/{totalSteps}
        </div>
      </div>

      {/* Equity curve — current view */}
      <ResponsiveContainer width="100%" height={200}>
        <AreaChart data={visibleCurve}>
          <defs>
            <linearGradient id="replayGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={currentReturn >= 0 ? "#10b981" : "#ef4444"} stopOpacity={0.3} />
              <stop offset="95%" stopColor={currentReturn >= 0 ? "#10b981" : "#ef4444"} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
          <XAxis dataKey="date" tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
            tickFormatter={(d) => d.slice(5)} interval="preserveStartEnd" />
          <YAxis width={60} tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
            tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} />
          <Tooltip
            contentStyle={{ backgroundColor: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: "6px", fontSize: "12px" }}
            formatter={(v) => [`$${Number(v).toLocaleString()}`, "Equity"]}
          />
          <ReferenceLine y={initialCapital} stroke="hsl(var(--muted-foreground))" strokeDasharray="4 4" />
          <Area type="monotone" dataKey="value"
            stroke={currentReturn >= 0 ? "#10b981" : "#ef4444"}
            fill="url(#replayGrad)" strokeWidth={2} />
        </AreaChart>
      </ResponsiveContainer>

      {/* Status bar */}
      <div className="grid grid-cols-3 gap-3 text-center">
        <div>
          <div className="text-[10px] text-muted-foreground">Equity</div>
          <div className="text-sm font-mono font-bold">${currentEquity.toLocaleString("en-US", { maximumFractionDigits: 0 })}</div>
        </div>
        <div>
          <div className="text-[10px] text-muted-foreground">Return</div>
          <div className={`text-sm font-mono font-bold ${currentReturn >= 0 ? "text-emerald-400" : "text-red-400"}`}>
            {currentReturn >= 0 ? "+" : ""}{currentReturn.toFixed(1)}%
          </div>
        </div>
        <div>
          <div className="text-[10px] text-muted-foreground">Trades Fired</div>
          <div className="text-sm font-mono font-bold">{visibleTrades.length}</div>
        </div>
      </div>

      {/* Latest trade signal */}
      {latestTrade && (
        <div className={`flex items-center gap-3 px-3 py-2 rounded-lg text-xs border ${
          latestTrade.pnl >= 0 ? "bg-emerald-400/10 border-emerald-400/20 text-emerald-400" : "bg-red-400/10 border-red-400/20 text-red-400"
        }`}>
          <span className="font-bold">{latestTrade.direction}</span>
          <span>{latestTrade.entry_date}</span>
          <span className="font-mono">${latestTrade.entry_price.toFixed(2)}</span>
          <span className="ml-auto font-mono font-bold">
            {latestTrade.pnl >= 0 ? "+" : ""}${latestTrade.pnl.toFixed(2)}
          </span>
        </div>
      )}

      {/* Playback controls */}
      <div className="flex items-center justify-center gap-2">
        <button onClick={() => { setPlaying(false); setCurrentStep(0); }}
          className="p-1.5 rounded text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors">
          <SkipBack className="h-4 w-4" />
        </button>
        <button onClick={() => setCurrentStep((p) => Math.max(0, p - 1))}
          className="p-1.5 rounded text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors">
          <ChevronLeft className="h-4 w-4" />
        </button>
        <button onClick={() => setPlaying((p) => !p)}
          className="p-2 rounded-full bg-primary text-primary-foreground hover:bg-primary/90 transition-colors">
          {playing ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
        </button>
        <button onClick={() => setCurrentStep((p) => Math.min(totalSteps - 1, p + 1))}
          className="p-1.5 rounded text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors">
          <ChevronRight className="h-4 w-4" />
        </button>
        <button onClick={() => { setPlaying(false); setCurrentStep(totalSteps - 1); }}
          className="p-1.5 rounded text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors">
          <SkipForward className="h-4 w-4" />
        </button>

        {/* Speed control */}
        <div className="flex items-center gap-1.5 ml-4">
          <span className="text-[10px] text-muted-foreground">Speed:</span>
          {[0.5, 1, 2, 5].map((s) => (
            <button key={s} onClick={() => setSpeed(s)}
              className={`text-[10px] px-1.5 py-0.5 rounded transition-colors ${
                speed === s ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
              }`}>
              {s}×
            </button>
          ))}
        </div>
      </div>

      {/* Progress bar */}
      <div className="h-1 rounded-full bg-muted overflow-hidden">
        <div
          className="h-full rounded-full bg-primary transition-all duration-100"
          style={{ width: `${(currentStep / (totalSteps - 1)) * 100}%` }}
        />
      </div>
    </div>
  );
}
```

**Step: Commit**

```bash
git add frontend/src/components/quant/TradeReplayPanel.tsx
git commit -m "feat: trade replay panel with playback controls"
```

---

## Task 17: Compare tab + /quant page

**Files:**
- Create: `frontend/src/components/quant/CompareTab.tsx`
- Create: `frontend/src/app/quant/page.tsx`

**Step 1: CompareTab.tsx**

```tsx
// frontend/src/components/quant/CompareTab.tsx
"use client";

import React, { useState } from "react";
import { Loader2, Plus, X } from "lucide-react";
import type { CompareResponse, QuantMetrics } from "@/types/quant";
import type { StrategyRecord } from "@/types/strategy";
import { apiFetch } from "@/lib/api/client";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend, RadarChart, Radar,
  PolarGrid, PolarAngleAxis,
} from "recharts";

const LINE_COLORS = ["#6366f1", "#10b981", "#f59e0b", "#f87171", "#60a5fa"];

interface CompareTabProps {
  strategyId: number;
  strategy: StrategyRecord;
}

function fmt(v: number, type: string): string {
  if (type === "pct") return `${(v * 100).toFixed(1)}%`;
  if (type === "ratio") return v.toFixed(3);
  return v.toFixed(2);
}

export function CompareTab({ strategyId, strategy }: CompareTabProps) {
  const [extraIds, setExtraIds] = useState<number[]>([]);
  const [inputVal, setInputVal] = useState("");
  const [compareData, setCompareData] = useState<CompareResponse | null>(null);
  const [loading, setLoading] = useState(false);

  const allIds = [strategyId, ...extraIds];

  const runCompare = async () => {
    if (allIds.length < 1) return;
    setLoading(true);
    try {
      const data = await apiFetch<CompareResponse>(
        `/api/quant/compare?strategy_ids=${allIds.join(",")}&lookback_days=252&initial_capital=100000`
      );
      setCompareData(data);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  const addId = () => {
    const n = parseInt(inputVal.trim());
    if (!isNaN(n) && n > 0 && !allIds.includes(n)) {
      setExtraIds((prev) => [...prev, n]);
    }
    setInputVal("");
  };

  // Build unified equity curve (aligned by step index)
  const equityCurveData: Record<string, number | string>[] = [];
  if (compareData) {
    const maxLen = Math.max(...compareData.strategies.map((s) => s.equity_curve.length));
    for (let i = 0; i < maxLen; i++) {
      const row: Record<string, number | string> = {};
      for (const s of compareData.strategies) {
        const pt = s.equity_curve[i];
        if (pt) {
          row.date = pt.date;
          row[s.strategy_name] = pt.value;
        }
      }
      equityCurveData.push(row);
    }
  }

  // Radar chart data
  const radarMetrics = compareData?.strategies.map((s) => ({
    name: s.strategy_name,
    Sharpe: Math.min(Math.max((s.metrics.sharpe_ratio + 1) / 4, 0), 1),
    "Win Rate": s.metrics.win_rate,
    "Profit F.": Math.min(s.metrics.profit_factor / 3, 1),
    "Low DD": Math.min(1 - Math.abs(s.metrics.max_drawdown) * 2, 1),
    Return: Math.min(Math.max(s.metrics.total_return + 0.5, 0), 1),
  })) || [];

  const radarSubjects = ["Sharpe", "Win Rate", "Profit F.", "Low DD", "Return"];

  return (
    <div className="space-y-6">
      {/* Strategy selector */}
      <div className="rounded-lg border border-border/50 bg-card p-4">
        <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">
          Add Strategies to Compare
        </div>
        <div className="flex flex-wrap gap-2 mb-3">
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg border border-primary/30 bg-primary/5 text-xs font-medium">
            {strategy.name} (current)
          </div>
          {extraIds.map((id) => (
            <div key={id} className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg border border-border/50 text-xs">
              Strategy #{id}
              <button onClick={() => setExtraIds((prev) => prev.filter((x) => x !== id))}
                className="text-muted-foreground hover:text-red-400 transition-colors">
                <X className="h-3 w-3" />
              </button>
            </div>
          ))}
        </div>
        <div className="flex gap-2">
          <input
            type="number"
            value={inputVal}
            onChange={(e) => setInputVal(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && addId()}
            placeholder="Strategy ID"
            className="h-9 w-36 rounded-md border border-border/50 bg-background px-3 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-ring/40"
          />
          <button onClick={addId}
            className="h-9 px-3 rounded-md border border-border/50 text-sm text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors inline-flex items-center gap-1">
            <Plus className="h-3.5 w-3.5" /> Add
          </button>
          <button onClick={runCompare} disabled={loading}
            className="h-9 px-4 rounded-md bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors disabled:opacity-40 inline-flex items-center gap-1.5">
            {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
            Compare
          </button>
        </div>
      </div>

      {compareData && (
        <>
          {/* Side-by-side equity curves */}
          <div className="rounded-lg border border-border/50 bg-card p-4">
            <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">
              Equity Curves
            </div>
            <ResponsiveContainer width="100%" height={280}>
              <LineChart data={equityCurveData}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis dataKey="date" tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
                  tickFormatter={(d) => String(d).slice(5)} interval="preserveStartEnd" />
                <YAxis width={65} tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
                  tickFormatter={(v) => `$${(Number(v) / 1000).toFixed(0)}k`} />
                <Tooltip
                  contentStyle={{ backgroundColor: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: "6px", fontSize: "12px" }}
                />
                <Legend wrapperStyle={{ fontSize: "11px" }} />
                {compareData.strategies.map((s, i) => (
                  <Line key={s.strategy_id} type="monotone" dataKey={s.strategy_name}
                    stroke={LINE_COLORS[i % LINE_COLORS.length]} strokeWidth={2} dot={false} />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* Metrics comparison table */}
          <div className="rounded-lg border border-border/50 bg-card overflow-hidden">
            <div className="px-4 py-3 border-b border-border/50">
              <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Metrics Comparison
              </span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left">
                <thead>
                  <tr className="border-b border-border/50">
                    <th className="py-2 px-4 text-[10px] font-semibold text-muted-foreground uppercase">Metric</th>
                    {compareData.strategies.map((s, i) => (
                      <th key={s.strategy_id} className="py-2 px-4 text-[10px] font-semibold uppercase"
                        style={{ color: LINE_COLORS[i % LINE_COLORS.length] }}>
                        {s.strategy_name}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {(
                    [
                      { key: "total_return", label: "Total Return", type: "pct" },
                      { key: "annualized_return", label: "Ann. Return", type: "pct" },
                      { key: "sharpe_ratio", label: "Sharpe", type: "ratio" },
                      { key: "sortino_ratio", label: "Sortino", type: "ratio" },
                      { key: "max_drawdown", label: "Max Drawdown", type: "pct" },
                      { key: "win_rate", label: "Win Rate", type: "pct" },
                      { key: "profit_factor", label: "Profit Factor", type: "ratio" },
                      { key: "num_trades", label: "Trades", type: "int" },
                    ] as { key: keyof QuantMetrics; label: string; type: string }[]
                  ).map((row) => {
                    const vals = compareData.strategies.map((s) => s.metrics[row.key]);
                    const best = row.key === "max_drawdown"
                      ? Math.max(...vals.map(Number))  // closest to 0 wins for drawdown
                      : Math.max(...vals.map(Number));
                    return (
                      <tr key={row.key} className="border-b border-border/30">
                        <td className="py-2 px-4 text-xs text-muted-foreground">{row.label}</td>
                        {vals.map((v, i) => (
                          <td key={i} className={`py-2 px-4 text-xs font-mono ${
                            Number(v) === best ? "font-bold text-emerald-400" : ""
                          }`}>
                            {row.type === "int" ? String(v) : fmt(Number(v), row.type)}
                          </td>
                        ))}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Radar chart */}
          {radarMetrics.length > 1 && (
            <div className="rounded-lg border border-border/50 bg-card p-4">
              <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">
                Performance Radar
              </div>
              <ResponsiveContainer width="100%" height={300}>
                <RadarChart data={radarSubjects.map((subject) => {
                  const row: Record<string, string | number> = { subject };
                  for (const m of radarMetrics) row[m.name] = m[subject as keyof typeof m] as number;
                  return row;
                })}>
                  <PolarGrid stroke="hsl(var(--border))" />
                  <PolarAngleAxis dataKey="subject" tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }} />
                  {radarMetrics.map((m, i) => (
                    <Radar key={m.name} dataKey={m.name} fill={LINE_COLORS[i]} fillOpacity={0.15}
                      stroke={LINE_COLORS[i]} strokeWidth={2} />
                  ))}
                  <Legend wrapperStyle={{ fontSize: "11px" }} />
                </RadarChart>
              </ResponsiveContainer>
            </div>
          )}
        </>
      )}
    </div>
  );
}
```

**Step 2: /quant/page.tsx — Hub comparison dashboard**

```tsx
// frontend/src/app/quant/page.tsx
"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Brain, BarChart2, GitCompare, ChevronRight, Loader2 } from "lucide-react";
import { apiFetch } from "@/lib/api/client";
import type { StrategyRecord } from "@/types/strategy";
import type { CompareResponse } from "@/types/quant";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Legend,
} from "recharts";

const LINE_COLORS = ["#6366f1", "#10b981", "#f59e0b", "#f87171", "#60a5fa"];

function fmtPct(v: number) {
  return `${v >= 0 ? "+" : ""}${(v * 100).toFixed(1)}%`;
}

export default function QuantPage() {
  const router = useRouter();
  const [strategies, setStrategies] = useState<StrategyRecord[]>([]);
  const [selected, setSelected] = useState<number[]>([]);
  const [compareData, setCompareData] = useState<CompareResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [comparing, setComparing] = useState(false);

  useEffect(() => {
    apiFetch<{ strategies: StrategyRecord[] }>("/api/strategies/list")
      .then((d) => {
        setStrategies(d.strategies || []);
        // Auto-select first 3
        const ids = (d.strategies || []).slice(0, 3).map((s) => s.id);
        setSelected(ids);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const runCompare = async () => {
    if (selected.length === 0) return;
    setComparing(true);
    try {
      const data = await apiFetch<CompareResponse>(
        `/api/quant/compare?strategy_ids=${selected.join(",")}&lookback_days=252&initial_capital=100000`
      );
      setCompareData(data);
    } catch {
      // ignore
    } finally {
      setComparing(false);
    }
  };

  // Build equity curve data
  const equityCurveData: Record<string, number | string>[] = [];
  if (compareData) {
    const maxLen = Math.max(...compareData.strategies.map((s) => s.equity_curve.length));
    for (let i = 0; i < maxLen; i++) {
      const row: Record<string, number | string> = {};
      for (const s of compareData.strategies) {
        if (s.equity_curve[i]) {
          row.date = s.equity_curve[i].date;
          row[s.strategy_name] = s.equity_curve[i].value;
        }
      }
      equityCurveData.push(row);
    }
  }

  const toggleSelect = (id: number) => {
    setSelected((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : prev.length < 5 ? [...prev, id] : prev
    );
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <div className="flex items-center gap-2 mb-1">
          <BarChart2 className="h-5 w-5 text-primary" />
          <h1 className="text-xl font-semibold">Quant Intelligence</h1>
        </div>
        <p className="text-sm text-muted-foreground">
          Institutional-grade strategy analytics and comparison
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Strategy selector */}
        <div className="rounded-lg border border-border/50 bg-card p-4">
          <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">
            Strategies ({selected.length} selected, max 5)
          </div>
          {loading ? (
            <div className="flex justify-center py-8">
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            </div>
          ) : strategies.length === 0 ? (
            <div className="text-sm text-muted-foreground py-4 text-center">
              No strategies yet.{" "}
              <Link href="/" className="text-primary hover:underline">Build one</Link>
            </div>
          ) : (
            <div className="space-y-1 max-h-80 overflow-y-auto">
              {strategies.map((s) => {
                const isSelected = selected.includes(s.id);
                return (
                  <div key={s.id}
                    onClick={() => toggleSelect(s.id)}
                    className={`flex items-center justify-between px-3 py-2 rounded-lg cursor-pointer transition-colors text-sm ${
                      isSelected
                        ? "bg-primary/10 border border-primary/20"
                        : "hover:bg-muted/30 border border-transparent"
                    }`}
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <div className={`h-2 w-2 rounded-full shrink-0 ${isSelected ? "bg-primary" : "bg-muted"}`} />
                      <span className="truncate font-medium">{s.name}</span>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <span className="text-[10px] font-mono text-muted-foreground">{s.timeframe}</span>
                      <Link
                        href={`/intelligence/${s.id}`}
                        onClick={(e) => e.stopPropagation()}
                        className="text-muted-foreground/40 hover:text-primary transition-colors"
                        title="Open Intelligence Panel"
                      >
                        <Brain className="h-3.5 w-3.5" />
                      </Link>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          <button
            onClick={runCompare}
            disabled={selected.length === 0 || comparing}
            className="mt-4 w-full h-9 rounded-md bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors disabled:opacity-40 inline-flex items-center justify-center gap-1.5"
          >
            {comparing ? <Loader2 className="h-4 w-4 animate-spin" /> : <GitCompare className="h-4 w-4" />}
            Compare Selected
          </button>
        </div>

        {/* Comparison results */}
        <div className="lg:col-span-2 space-y-4">
          {!compareData && !comparing && (
            <div className="rounded-lg border border-dashed border-border/50 p-12 text-center">
              <GitCompare className="h-8 w-8 text-muted-foreground/30 mx-auto mb-3" />
              <p className="text-muted-foreground text-sm">
                Select strategies and click Compare
              </p>
            </div>
          )}

          {comparing && (
            <div className="flex items-center justify-center py-16">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          )}

          {compareData && (
            <>
              {/* Equity curves */}
              <div className="rounded-lg border border-border/50 bg-card p-4">
                <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">
                  Equity Curves
                </div>
                <ResponsiveContainer width="100%" height={260}>
                  <LineChart data={equityCurveData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                    <XAxis dataKey="date" tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
                      tickFormatter={(d) => String(d).slice(5)} interval="preserveStartEnd" />
                    <YAxis width={65} tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
                      tickFormatter={(v) => `$${(Number(v) / 1000).toFixed(0)}k`} />
                    <Tooltip
                      contentStyle={{ backgroundColor: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: "6px", fontSize: "12px" }}
                    />
                    <Legend wrapperStyle={{ fontSize: "11px" }} />
                    {compareData.strategies.map((s, i) => (
                      <Line key={s.strategy_id} type="monotone" dataKey={s.strategy_name}
                        stroke={LINE_COLORS[i % LINE_COLORS.length]} strokeWidth={2} dot={false} />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              </div>

              {/* Quick metrics row */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {compareData.strategies.map((s, i) => (
                  <div key={s.strategy_id} className="rounded-lg border border-border/50 bg-card p-4">
                    <div className="flex items-center justify-between mb-3">
                      <span className="text-sm font-medium truncate">{s.strategy_name}</span>
                      <Link href={`/intelligence/${s.strategy_id}`}
                        className="text-muted-foreground hover:text-primary transition-colors">
                        <ChevronRight className="h-4 w-4" />
                      </Link>
                    </div>
                    <div className="space-y-1.5 text-xs">
                      {[
                        { label: "Return", value: fmtPct(s.metrics.total_return), colored: true },
                        { label: "Sharpe", value: s.metrics.sharpe_ratio.toFixed(3) },
                        { label: "Win Rate", value: `${(s.metrics.win_rate * 100).toFixed(1)}%` },
                        { label: "Max DD", value: fmtPct(s.metrics.max_drawdown), negative: true },
                      ].map((item) => (
                        <div key={item.label} className="flex items-center justify-between">
                          <span className="text-muted-foreground">{item.label}</span>
                          <span className={`font-mono font-medium ${
                            item.colored ? (s.metrics.total_return >= 0 ? "text-emerald-400" : "text-red-400")
                            : item.negative ? "text-red-400" : ""
                          }`}>
                            {item.value}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
```

**Step 3: Commit**

```bash
git add frontend/src/components/quant/CompareTab.tsx frontend/src/app/quant/page.tsx
git commit -m "feat: CompareTab component and /quant comparison dashboard"
```

---

## Task 18: Wire in remaining tab stubs and add trade replay to analytics tab

**Files:**
- Create stub: `frontend/src/components/quant/RemainingStubs.tsx` (single file with all remaining exports)

These stubs are already created in prior tasks. But the page imports `OverviewTab`, `AnalyticsTab`, `HeatmapsTab`, `MonteCarloTab`, `RiskTab`, `CompareTab`. Verify all exist by listing the directory:

```bash
ls frontend/src/components/quant/
```

Expected: `AIReasoningPanel.tsx AnalyticsTab.tsx BotMetadataPanel.tsx CompareTab.tsx DrawdownChart.tsx FeatureImportanceChart.tsx HeatmapGrid.tsx HeatmapsTab.tsx MetricCardsRow.tsx MonteCarloChart.tsx MonteCarloTab.tsx OverviewTab.tsx ProfitDistributionChart.tsx RiskTab.tsx RollingSharpChart.tsx StrategyDecisionPipeline.tsx TradeDurationHistogram.tsx TradeForensicsModal.tsx TradeHistoryTable.tsx TradeReplayPanel.tsx`

**Step 2: Add TradeHistoryTable + TradeReplayPanel to AnalyticsTab**

Edit `frontend/src/components/quant/AnalyticsTab.tsx` — add at the bottom of the return, after `TradeDurationHistogram`:

Find the closing `</div>` after `TradeDurationHistogram` and add before it:

```tsx
      {analytics.trades && analytics.trades.length > 0 && (
        <>
          <TradeReplayPanel
            trades={analytics.trades}
            equityCurve={analytics.equity_curve}
            initialCapital={analytics.initial_capital}
          />
          <TradeHistoryTable trades={analytics.trades} strategyId={analytics.strategy_id} />
        </>
      )}
```

Also add imports at the top of `AnalyticsTab.tsx`:

```tsx
import { TradeReplayPanel } from "./TradeReplayPanel";
import { TradeHistoryTable } from "./TradeHistoryTable";
```

**Step 3: Add link from strategies/page.tsx to /intelligence/[id]**

In `frontend/src/app/strategies/page.tsx`, add a Brain icon button next to the existing Pencil button. Find the `<Pencil>` button block and add before it:

```tsx
<button
  onClick={(e) => { e.stopPropagation(); router.push(`/intelligence/${s.id}`); }}
  className="p-1.5 rounded text-muted-foreground/40 hover:text-primary hover:bg-primary/10 transition-colors"
  title="Intelligence Panel"
>
  <Brain className="h-4 w-4" />
</button>
```

Add `Brain` to the import: `import { Trash2, Shield, ChevronRight, Pencil, Play, Copy, Brain } from "lucide-react";`

**Step 4: Commit**

```bash
git add frontend/src/components/quant/AnalyticsTab.tsx frontend/src/app/strategies/page.tsx
git commit -m "feat: wire trade replay and trade history into analytics tab; add intelligence link from strategies list"
```

---

## Task 19: TypeScript check + build + Docker rebuild

**Step 1: TypeScript check**

```bash
cd ~/adaptive-trading-ecosystem/frontend
npx tsc --noEmit 2>&1 | grep -v "node_modules" | grep -v ".next" | grep "error" | head -20
```

Fix any errors found (they will likely be missing imports or type mismatches).

Common fix: if `QuantAnalyticsResponse` missing field `strategy_id: number` — add to the type in `quant.ts`.

**Step 2: Next.js production build**

```bash
npm run build 2>&1 | tail -25
```

Expected: `✓ Compiled successfully` with all routes listed including `/intelligence/[id]` and `/quant`.

**Step 3: Rebuild Docker frontend**

```bash
cd ~/adaptive-trading-ecosystem
docker compose up -d --build --no-deps frontend api 2>&1 | tail -6
```

**Step 4: Smoke test**

```bash
sleep 10
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3000/quant
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3000/intelligence/1
docker compose ps --format "table {{.Name}}\t{{.Status}}"
```

Expected: `307 307` (redirect to login — correct, auth protected) and all containers healthy.

**Step 5: API smoke test**

```bash
TOKEN=$(docker compose exec api python3 -c "
from jose import jwt; import datetime
from config.settings import get_settings
payload = {'sub': '2', 'exp': datetime.datetime.utcnow() + datetime.timedelta(days=1)}
print(jwt.encode(payload, get_settings().jwt_secret, algorithm='HS256'))
")
STRAT_ID=$(docker compose exec postgres psql -U trader -d trading_ecosystem -t -c "SELECT id FROM strategy_templates LIMIT 1;" | tr -d ' ')
echo "Strategy ID: $STRAT_ID"
curl -s "http://localhost:8000/api/quant/${STRAT_ID}/analytics?lookback_days=60&initial_capital=10000" \
  -H "Authorization: Bearer $TOKEN" \
  | python3 -m json.tool 2>/dev/null | grep -E '"sharpe_ratio|total_return|num_trades"' | head -5
```

Expected: valid JSON with metrics fields.

**Step 6: Final commit**

```bash
cd ~/adaptive-trading-ecosystem
git add .
git commit -m "feat: Quant Strategy Intelligence Layer — all 16 features complete"
```

---

## Troubleshooting Reference

**"Module not found" in quant.py for `data.features`:**
Check what the FeatureEngineer import path is. Run:
```bash
docker compose exec api python3 -c "from data.features import FeatureEngineer; print('ok')"
```
If this fails, change the import in `_compute_indicator` to use the indicator computation from `api/routes/strategies.py` pattern — they use `from engine.indicators import IndicatorEngine` or similar. Check the actual import at the top of `strategies.py`.

**"Import error: yfinance not found":**
```bash
docker compose exec api pip install yfinance --quiet
```
Or add `yfinance` to `requirements.txt` and rebuild.

**React hydration error in intelligence page:**
Add `"use client"` directive to any component that uses `useState` or `useEffect`.

**TypeScript error on recharts `Cell` component:**
Add explicit type cast: `fill={COLORS[i % COLORS.length] as string}`
