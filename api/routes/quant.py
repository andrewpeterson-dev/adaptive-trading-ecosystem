"""
Quant Strategy Intelligence Layer — per-strategy deep-dive and comparison endpoints.

Endpoints:
  GET  /strategy/{id}                  — full intelligence bundle
  GET  /strategy/{id}/trades           — trades with decision metadata
  GET  /strategy/{id}/reasoning-logs   — AI reasoning log entries
  GET  /strategy/{id}/monte-carlo      — Monte Carlo simulation paths
  GET  /strategy/{id}/feature-importance — condition/feature weights
  GET  /strategy/{id}/heatmap          — profit by hour × day-of-week
  GET  /compare                        — side-by-side strategy comparison
"""

import math
import random
import statistics
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db
from db.models import (
    MarketRegimeRecord,
    Strategy,
    StrategyInstance,
    StrategySnapshot,
    StrategyTemplate,
    TradeEvent,
)

logger = structlog.get_logger(__name__)
router = APIRouter()

# ── Helpers ──────────────────────────────────────────────────────────────────

REGIME_COLORS = {
    "low_vol_bull": "#10b981",
    "high_vol_bull": "#f59e0b",
    "low_vol_bear": "#ef4444",
    "high_vol_bear": "#dc2626",
    "sideways": "#6b7280",
}


def _get_strategy_params(strategy) -> Dict[str, Optional[float]]:
    """Extract strategy params from config. No defaults — returns None if not set."""
    diag = getattr(strategy, "diagnostics", None) or {}
    return {
        "win_rate": float(diag["win_rate"]) if "win_rate" in diag else None,
        "avg_win": float(diag["avg_win_pct"]) if "avg_win_pct" in diag else None,
        "avg_loss": float(diag["avg_loss_pct"]) if "avg_loss_pct" in diag else None,
        "tp_pct": float(strategy.take_profit_pct) if strategy.take_profit_pct else None,
        "sl_pct": float(strategy.stop_loss_pct) if strategy.stop_loss_pct else None,
        "position_size": float(getattr(strategy, "position_size_pct", None) or 0) or None,
    }


def _compute_performance(equity_curve: List[Dict], params: Dict) -> Dict[str, Any]:
    """Derive performance metrics from an equity curve + strategy params."""
    if len(equity_curve) < 2:
        return {
            "sharpe": None,
            "sortino": None,
            "win_rate": None,
            "profit_factor": None,
            "max_drawdown": None,
            "total_return": None,
            "num_trades": 0,
            "confidence": None,
        }

    values = [p["value"] for p in equity_curve]
    daily_returns = [(values[i] - values[i - 1]) / values[i - 1] for i in range(1, len(values))]

    # Total return
    total_return = (values[-1] - values[0]) / values[0]

    # Max drawdown
    peak = values[0]
    max_dd = 0.0
    for v in values:
        if v > peak:
            peak = v
        dd = (v - peak) / peak
        if dd < max_dd:
            max_dd = dd

    # Sharpe (annualised, assuming daily returns, rf=0)
    if len(daily_returns) > 1:
        mean_r = statistics.mean(daily_returns)
        std_r = statistics.stdev(daily_returns)
        sharpe = (mean_r / std_r * math.sqrt(252)) if std_r > 1e-9 else 0.0
    else:
        sharpe = 0.0

    # Sortino (downside deviation)
    neg_rets = [r for r in daily_returns if r < 0]
    if neg_rets and len(neg_rets) > 1:
        downside_std = statistics.stdev(neg_rets)
        sortino = (statistics.mean(daily_returns) / downside_std * math.sqrt(252)) if downside_std > 1e-9 else 0.0
    else:
        sortino = sharpe * 1.2

    # Profit factor estimate
    wins = [r for r in daily_returns if r > 0]
    losses = [abs(r) for r in daily_returns if r < 0]
    if losses:
        profit_factor = sum(wins) / sum(losses) if wins else 0.0
    else:
        profit_factor = 99.0 if wins else 0.0

    # Trade count — only real if provided, otherwise null
    num_trades = None

    # Confidence — not computed synthetically, only from real data
    confidence = None

    return {
        "sharpe": round(sharpe, 3),
        "sortino": round(sortino, 3),
        "win_rate": round(params["win_rate"], 3) if params.get("win_rate") is not None else None,
        "profit_factor": round(profit_factor, 3),
        "max_drawdown": round(max_dd, 4),
        "total_return": round(total_return, 4),
        "num_trades": num_trades,
        "confidence": confidence,
    }


def _monte_carlo(trade_returns: List[float], n_sims: int = 200, n_steps: int = 90) -> Dict:
    """Run Monte Carlo simulation by resampling trade returns."""
    if not trade_returns:
        return None

    rng = random.Random(99)

    paths = []
    for _ in range(n_sims):
        path = [100_000.0]
        for __ in range(n_steps):
            r = rng.choice(trade_returns)
            path.append(path[-1] * (1 + r))
        paths.append(path)

    # Percentile bands
    p5 = [sorted(p[i] for p in paths)[int(n_sims * 0.05)] for i in range(n_steps + 1)]
    p25 = [sorted(p[i] for p in paths)[int(n_sims * 0.25)] for i in range(n_steps + 1)]
    p50 = [sorted(p[i] for p in paths)[int(n_sims * 0.50)] for i in range(n_steps + 1)]
    p75 = [sorted(p[i] for p in paths)[int(n_sims * 0.75)] for i in range(n_steps + 1)]
    p95 = [sorted(p[i] for p in paths)[int(n_sims * 0.95)] for i in range(n_steps + 1)]

    finals = [p[-1] for p in paths]
    risk_of_ruin = sum(1 for f in finals if f < 80_000) / n_sims
    expected_final = statistics.mean(finals)
    std_final = statistics.stdev(finals)

    today = datetime.utcnow()
    dates = [(today + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(n_steps + 1)]

    return {
        "dates": dates,
        "p5": [round(v, 2) for v in p5],
        "p25": [round(v, 2) for v in p25],
        "p50": [round(v, 2) for v in p50],
        "p75": [round(v, 2) for v in p75],
        "p95": [round(v, 2) for v in p95],
        "risk_of_ruin": round(risk_of_ruin, 3),
        "expected_final": round(expected_final, 2),
        "std_final": round(std_final, 2),
        "ci_90_low": round(p5[-1], 2),
        "ci_90_high": round(p95[-1], 2),
        "n_sims": n_sims,
    }


def _feature_importance(strategy) -> List[Dict]:
    """Compute feature importance deterministically from actual strategy conditions only."""
    conditions = []
    raw = getattr(strategy, "conditions", []) or []
    groups = getattr(strategy, "condition_groups", []) or []

    if groups:
        for g in groups:
            conditions.extend(g.get("conditions", []))
    else:
        conditions = raw

    if not conditions:
        return []

    features = []
    base_importance = 1.0
    for cond in conditions:
        indicator = str(cond.get("indicator", "unknown")).upper()
        importance = base_importance
        features.append({"feature": indicator, "importance": round(importance, 3)})
        base_importance *= 0.85  # decay — first conditions matter more

    # Normalize so max = 1.0
    if features:
        max_imp = max(f["importance"] for f in features)
        for f in features:
            f["importance"] = round(f["importance"] / max_imp, 3) if max_imp > 0 else 0.0

    features.sort(key=lambda x: x["importance"], reverse=True)
    return features[:12]


def _profit_heatmap(trades: List[Dict]) -> Dict:
    """Build profit heatmap aggregated by hour and day-of-week. Real trades only."""
    days = ["Mon", "Tue", "Wed", "Thu", "Fri"]
    hours = [9, 10, 11, 12, 13, 14, 15, 16]

    # Aggregate from trades
    grid: Dict[str, Dict[int, List[float]]] = {d: {h: [] for h in hours} for d in days}

    for t in trades:
        try:
            dt = datetime.fromisoformat(t["entry_time"])
            day_idx = dt.weekday()
            if day_idx >= 5:
                continue
            day_name = days[day_idx]
            hour = dt.hour
            if hour in grid[day_name]:
                grid[day_name][hour].append(t.get("pnl_pct", 0))
        except Exception:
            continue

    # Compute averages — empty cells stay as null
    data = []
    for day in days:
        for hour in hours:
            vals = grid[day][hour]
            avg = statistics.mean(vals) if vals else None
            data.append({"day": day, "hour": hour, "avg_pnl_pct": round(avg, 3) if avg is not None else None})

    return {"data": data, "days": days, "hours": hours}


async def _load_strategy(strategy_id: int, user_id: int, db: AsyncSession):
    """Load strategy by ID.

    Resolution order (matches how frontend references strategies):
    1. StrategyInstance.id → returns its template (real user strategies)
    2. Strategy.id — legacy / demo seeded strategies (user_id=NULL)

    We deliberately skip direct StrategyTemplate.id lookup to avoid ID-space
    collisions with Strategy demo records.
    """
    from sqlalchemy.orm import selectinload as _selectinload

    # 1. Try StrategyInstance.id → return its template (user-created strategies)
    inst_result = await db.execute(
        select(StrategyInstance)
        .options(_selectinload(StrategyInstance.template))
        .where(
            StrategyInstance.id == strategy_id,
            StrategyInstance.user_id == user_id,
        )
    )
    inst = inst_result.scalar_one_or_none()
    if inst and inst.template:
        return inst.template

    # 2. Fall back to legacy/demo Strategy table
    result = await db.execute(
        select(Strategy).where(
            Strategy.id == strategy_id,
            or_(Strategy.user_id == user_id, Strategy.user_id.is_(None)),
        )
    )
    return result.scalar_one_or_none()


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.get("/strategy/{strategy_id}")
async def get_strategy_intelligence(
    strategy_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Full intelligence bundle — metadata, performance, equity curve, regime, decision pipeline."""
    strategy = await _load_strategy(strategy_id, request.state.user_id, db)
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    params = _get_strategy_params(strategy)

    # Equity curve from real snapshots only
    snap_result = await db.execute(
        select(StrategySnapshot)
        .where(StrategySnapshot.strategy_id == strategy_id)
        .order_by(StrategySnapshot.timestamp)
        .limit(200)
    )
    snapshots = snap_result.scalars().all()

    if snapshots:
        equity_curve = [
            {"date": s.timestamp.strftime("%Y-%m-%d"), "value": s.equity}
            for s in snapshots
        ]
        perf = _compute_performance(equity_curve, params)
    else:
        equity_curve = []
        perf = {
            "sharpe": None,
            "sortino": None,
            "win_rate": None,
            "profit_factor": None,
            "max_drawdown": None,
            "total_return": None,
            "num_trades": 0,
            "confidence": None,
        }

    # Current regime — only from real data
    reg_result = await db.execute(
        select(MarketRegimeRecord).order_by(MarketRegimeRecord.timestamp.desc()).limit(1)
    )
    regime_rec = reg_result.scalar_one_or_none()
    current_regime = regime_rec.regime.value if regime_rec else None
    regime_conf = float(regime_rec.confidence) if regime_rec and regime_rec.confidence else None

    # Decision pipeline stages — only show real data, null for stages without data
    n_conditions = len(getattr(strategy, "conditions", []) or [])
    decision_pipeline = [
        {
            "stage": "Signal Generation",
            "passed": n_conditions > 0 if n_conditions else None,
            "reason": f"{n_conditions} conditions configured" if n_conditions > 0 else "No conditions configured",
        },
        {
            "stage": "Confidence Threshold",
            "passed": perf["win_rate"] > 0.5 if perf["win_rate"] is not None else None,
            "reason": f"Win rate {perf['win_rate'] * 100:.0f}%" if perf["win_rate"] is not None else "No data",
        },
        {
            "stage": "Regime Filter",
            "passed": current_regime != "high_vol_bear" if current_regime is not None else None,
            "reason": f"Regime: {current_regime.replace('_', ' ')}" if current_regime else "No data",
        },
        {
            "stage": "Risk Check",
            "passed": abs(perf["max_drawdown"]) < 0.25 if perf["max_drawdown"] is not None else None,
            "reason": f"Max DD {abs(perf['max_drawdown']) * 100:.1f}%" if perf["max_drawdown"] is not None else "No data",
        },
        {
            "stage": "Ensemble Agreement",
            "passed": perf["confidence"] > 60 if perf["confidence"] is not None else None,
            "reason": f"Confidence {perf['confidence']:.0f}%" if perf["confidence"] is not None else "No data",
        },
    ]

    return {
        "strategy": {
            "id": strategy.id,
            "name": strategy.name,
            "description": getattr(strategy, "description", None),
            "timeframe": strategy.timeframe,
            "action": strategy.action,
            "stop_loss_pct": strategy.stop_loss_pct,
            "take_profit_pct": strategy.take_profit_pct,
            "conditions": getattr(strategy, "conditions", []) or [],
            "symbols": getattr(strategy, "symbols", []) or [],
            "created_at": (
                strategy.created_at.isoformat() if strategy.created_at else None
            ),
        },
        "performance": perf,
        "regime": {"current": current_regime, "confidence": regime_conf},
        "equity_curve": equity_curve,
        "decision_pipeline": decision_pipeline,
    }


@router.get("/strategy/{strategy_id}/trades")
async def get_strategy_trades(
    strategy_id: int,
    limit: int = Query(50, ge=1, le=200),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    """Trades with AI decision metadata (signals, confidence, regime, reasoning)."""
    strategy = await _load_strategy(strategy_id, request.state.user_id, db)
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    result = await db.execute(
        select(TradeEvent)
        .where(TradeEvent.strategy_id == strategy_id)
        .order_by(TradeEvent.entry_time.desc())
        .limit(limit)
    )
    db_trades = result.scalars().all()

    if db_trades:
        trades = [
            {
                "id": t.id,
                "symbol": t.symbol,
                "direction": t.direction,
                "entry_time": t.entry_time.isoformat() if t.entry_time else None,
                "exit_time": t.exit_time.isoformat() if t.exit_time else None,
                "entry_price": t.entry_price,
                "exit_price": t.exit_price,
                "pnl": t.pnl,
                "pnl_pct": t.pnl_pct,
                "confidence": t.confidence,
                "regime": t.regime,
                "signals": t.signals_json or [],
                "approved": t.approved,
                "reasoning": t.reasoning_text,
                "model_name": t.model_name,
                "bars_held": None,
            }
            for t in db_trades
        ]
    else:
        trades = []

    return {"trades": trades, "total": len(trades)}


@router.get("/strategy/{strategy_id}/reasoning-logs")
async def get_reasoning_logs(
    strategy_id: int,
    limit: int = Query(20, ge=1, le=100),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    """AI reasoning log entries — one entry per signal evaluation."""
    strategy = await _load_strategy(strategy_id, request.state.user_id, db)
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    # In production these come from CerberusAIToolCall or TradeEvent.reasoning_text
    # Return empty until real data exists
    return {"logs": [], "total": 0}


@router.get("/strategy/{strategy_id}/monte-carlo")
async def get_monte_carlo(
    strategy_id: int,
    n_sims: int = Query(200, ge=50, le=1000),
    horizon_days: int = Query(90, ge=30, le=365),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    """Monte Carlo simulation by resampling historical trade returns."""
    strategy = await _load_strategy(strategy_id, request.state.user_id, db)
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    # Get trade returns from DB
    result = await db.execute(
        select(TradeEvent.pnl_pct)
        .where(TradeEvent.strategy_id == strategy_id, TradeEvent.pnl_pct.isnot(None))
        .limit(500)
    )
    raw_returns = [r[0] / 100.0 for r in result.fetchall() if r[0] is not None]

    # No real data — return null (no fake fallback)
    if not raw_returns:
        return None

    return _monte_carlo(raw_returns, n_sims=n_sims, n_steps=horizon_days)


@router.get("/strategy/{strategy_id}/feature-importance")
async def get_feature_importance(
    strategy_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Feature/condition importance scores."""
    strategy = await _load_strategy(strategy_id, request.state.user_id, db)
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    features = _feature_importance(strategy)
    return {"features": features}


@router.get("/strategy/{strategy_id}/heatmap")
async def get_profit_heatmap(
    strategy_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Profit heatmap — average PnL% by hour × day-of-week."""
    strategy = await _load_strategy(strategy_id, request.state.user_id, db)
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    # Load real trade events only
    result = await db.execute(
        select(TradeEvent)
        .where(TradeEvent.strategy_id == strategy_id)
        .order_by(TradeEvent.entry_time.desc())
        .limit(500)
    )
    db_trades = result.scalars().all()

    if db_trades:
        trades = [
            {
                "entry_time": t.entry_time.isoformat() if t.entry_time else "",
                "pnl_pct": t.pnl_pct or 0.0,
            }
            for t in db_trades
        ]
    else:
        trades = []

    return _profit_heatmap(trades)


@router.get("/compare")
async def compare_strategies(
    ids: str = Query(..., description="Comma-separated strategy IDs"),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    """Side-by-side comparison of multiple strategies."""
    try:
        id_list = [int(x.strip()) for x in ids.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(status_code=400, detail="ids must be comma-separated integers")

    if not id_list or len(id_list) > 8:
        raise HTTPException(status_code=400, detail="Provide 1-8 strategy IDs")

    results = []
    for sid in id_list:
        strategy = await _load_strategy(sid, request.state.user_id, db)
        if not strategy:
            continue

        params = _get_strategy_params(strategy)

        # Use real snapshots only
        snap_result = await db.execute(
            select(StrategySnapshot)
            .where(StrategySnapshot.strategy_id == sid)
            .order_by(StrategySnapshot.timestamp)
            .limit(200)
        )
        snapshots = snap_result.scalars().all()

        if snapshots:
            equity_curve = [
                {"date": s.timestamp.strftime("%Y-%m-%d"), "value": s.equity}
                for s in snapshots
            ]
            perf = _compute_performance(equity_curve, params)
        else:
            equity_curve = []
            perf = {
                "sharpe": None,
                "sortino": None,
                "win_rate": None,
                "profit_factor": None,
                "max_drawdown": None,
                "total_return": None,
                "num_trades": 0,
                "confidence": None,
            }

        results.append(
            {
                "id": strategy.id,
                "name": strategy.name,
                "timeframe": strategy.timeframe,
                "action": strategy.action,
                "performance": perf,
                "equity_curve": equity_curve[-60:],  # last 60 points for comparison chart
            }
        )

    return {"strategies": results}
