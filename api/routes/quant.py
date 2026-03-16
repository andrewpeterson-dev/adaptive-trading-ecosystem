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
from typing import Any, Dict, List

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


def _empty_performance() -> Dict[str, Any]:
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


def _compute_performance(
    equity_curve: List[Dict],
    trade_returns: List[float],
    trade_confidences: List[float],
) -> Dict[str, Any]:
    """Derive performance metrics from real equity snapshots and realized trade returns."""
    perf = _empty_performance()

    if len(equity_curve) >= 2:
        values = [p["value"] for p in equity_curve]
        daily_returns = [
            (values[i] - values[i - 1]) / values[i - 1]
            for i in range(1, len(values))
            if values[i - 1]
        ]

        perf["total_return"] = round((values[-1] - values[0]) / values[0], 4) if values[0] else None

        peak = values[0]
        max_dd = 0.0
        for value in values:
            if value > peak:
                peak = value
            if peak:
                drawdown = (value - peak) / peak
                if drawdown < max_dd:
                    max_dd = drawdown
        perf["max_drawdown"] = round(max_dd, 4)

        if len(daily_returns) > 1:
            std_r = statistics.stdev(daily_returns)
            if std_r > 1e-9:
                perf["sharpe"] = round(
                    statistics.mean(daily_returns) / std_r * math.sqrt(252),
                    3,
                )

            negative_returns = [ret for ret in daily_returns if ret < 0]
            if len(negative_returns) > 1:
                downside_std = statistics.stdev(negative_returns)
                if downside_std > 1e-9:
                    perf["sortino"] = round(
                        statistics.mean(daily_returns) / downside_std * math.sqrt(252),
                        3,
                    )

    if trade_returns:
        wins = [ret for ret in trade_returns if ret > 0]
        losses = [abs(ret) for ret in trade_returns if ret < 0]
        perf["num_trades"] = len(trade_returns)
        perf["win_rate"] = round(len(wins) / len(trade_returns), 3)
        if wins and losses:
            perf["profit_factor"] = round(sum(wins) / sum(losses), 3)

    if trade_confidences:
        perf["confidence"] = round(statistics.mean(trade_confidences), 1)

    return perf


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


def _feature_importance_not_available() -> Dict[str, Any]:
    return {
        "features": [],
        "status": "not_available",
    }


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

    # Equity curve from real snapshots only
    snap_result = await db.execute(
        select(StrategySnapshot)
        .where(StrategySnapshot.strategy_id == strategy_id)
        .order_by(StrategySnapshot.timestamp)
        .limit(200)
    )
    snapshots = snap_result.scalars().all()

    trade_metric_result = await db.execute(
        select(TradeEvent.pnl_pct, TradeEvent.confidence)
        .where(TradeEvent.strategy_id == strategy_id)
    )
    trade_metric_rows = trade_metric_result.all()
    trade_returns = [
        float(row[0]) / 100.0
        for row in trade_metric_rows
        if row[0] is not None
    ]
    trade_confidences = [
        float(row[1])
        for row in trade_metric_rows
        if row[1] is not None
    ]

    if snapshots:
        equity_curve = [
            {"date": s.timestamp.strftime("%Y-%m-%d"), "value": s.equity}
            for s in snapshots
        ]
        perf = _compute_performance(equity_curve, trade_returns, trade_confidences)
    else:
        equity_curve = []
        perf = _compute_performance(equity_curve, trade_returns, trade_confidences)

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

    result = await db.execute(
        select(TradeEvent)
        .where(
            TradeEvent.strategy_id == strategy_id,
            TradeEvent.reasoning_text.isnot(None),
        )
        .order_by(TradeEvent.timestamp.desc())
        .limit(limit)
    )
    entries = result.scalars().all()

    logs = [
        {
            "id": entry.id,
            "timestamp": (
                entry.timestamp.isoformat()
                if entry.timestamp
                else (
                    entry.entry_time.isoformat()
                    if entry.entry_time
                    else None
                )
            ),
            "symbol": entry.symbol,
            "confidence": float(entry.confidence or 0.0),
            "approved": bool(entry.approved),
            "regime": entry.regime or "unknown",
            "reasoning": entry.reasoning_text or "",
            "model": entry.model_name or "unknown",
            "latency_ms": 0,
        }
        for entry in entries
    ]

    return {"logs": logs, "total": len(logs)}


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

    return _feature_importance_not_available()


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

        # Use real snapshots only
        snap_result = await db.execute(
            select(StrategySnapshot)
            .where(StrategySnapshot.strategy_id == sid)
            .order_by(StrategySnapshot.timestamp)
            .limit(200)
        )
        snapshots = snap_result.scalars().all()

        trade_metric_result = await db.execute(
            select(TradeEvent.pnl_pct, TradeEvent.confidence)
            .where(TradeEvent.strategy_id == sid)
        )
        trade_metric_rows = trade_metric_result.all()
        trade_returns = [
            float(row[0]) / 100.0
            for row in trade_metric_rows
            if row[0] is not None
        ]
        trade_confidences = [
            float(row[1])
            for row in trade_metric_rows
            if row[1] is not None
        ]

        if snapshots:
            equity_curve = [
                {"date": s.timestamp.strftime("%Y-%m-%d"), "value": s.equity}
                for s in snapshots
            ]
            perf = _compute_performance(equity_curve, trade_returns, trade_confidences)
        else:
            equity_curve = []
            perf = _compute_performance(equity_curve, trade_returns, trade_confidences)

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
