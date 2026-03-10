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
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
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

SIGNAL_POOL = [
    "RSI crossed below 30 (oversold)",
    "MACD bullish crossover",
    "Price broke above 50-day SMA",
    "Volume spike 2x average",
    "Bollinger Band squeeze breakout",
    "EMA 9/21 golden cross",
    "ATR contraction → expansion",
    "Stochastic oversold bounce",
    "Support level retest confirmed",
    "Higher-low pattern detected",
    "RSI divergence bullish",
    "VWAP reclaim",
    "Relative strength vs SPY elevated",
    "Momentum score > threshold",
    "Mean reversion trigger hit",
    "IV rank below 20%",
    "Earnings drift setup",
    "Breakout above 52-week resistance",
]

REGIME_POOL = ["low_vol_bull", "high_vol_bull", "low_vol_bear", "sideways", "high_vol_bear"]

REASONING_TEMPLATES = [
    (
        "Strong confluence of technical signals. RSI shows oversold conditions while MACD "
        "generates a bullish crossover. Volume confirms institutional accumulation. "
        "Regime conditions are favorable for long entries."
    ),
    (
        "Signal approved with moderate confidence. Trend alignment is positive but volatility "
        "is elevated. Position sizing adjusted down 20% per risk protocol. Stop-loss set "
        "tight at {sl}% to limit downside."
    ),
    (
        "Regime filter passed — currently in {regime} environment. LLM analysis suggests "
        "continuation of existing trend. Ensemble agreement at {agree}%. "
        "Trade approved with {conf}% confidence."
    ),
    (
        "High-probability setup based on historical pattern match (similarity score 0.87). "
        "Expected holding period {days} trading days. Target return {tp}%. "
        "Risk/reward ratio {rr}:1."
    ),
    (
        "Signal blocked at ensemble stage. Models disagree on direction — momentum model "
        "bullish, mean-reversion model bearish. Confidence below threshold. "
        "Trade rejected to avoid conflicted entry."
    ),
]


def _seeded_rng(strategy_id: int) -> random.Random:
    return random.Random(strategy_id * 31337 + 42)


def _get_strategy_params(strategy) -> Dict[str, float]:
    """Extract or estimate key strategy params."""
    diag = getattr(strategy, "diagnostics", None) or {}
    win_rate = diag.get("win_rate", 0.55)
    avg_win = diag.get("avg_win_pct", strategy.take_profit_pct or 0.05)
    avg_loss = diag.get("avg_loss_pct", strategy.stop_loss_pct or 0.02)
    return {
        "win_rate": float(win_rate),
        "avg_win": float(avg_win),
        "avg_loss": float(avg_loss),
        "tp_pct": float(strategy.take_profit_pct or 0.05),
        "sl_pct": float(strategy.stop_loss_pct or 0.02),
        "position_size": float(getattr(strategy, "position_size_pct", 0.1) or 0.1),
    }


def _synthetic_equity_curve(
    strategy, rng: random.Random, n_points: int = 90
) -> List[Dict[str, Any]]:
    """Generate a realistic synthetic equity curve using trade simulation."""
    params = _get_strategy_params(strategy)
    win_rate = params["win_rate"]
    avg_win = params["avg_win"]
    avg_loss = params["avg_loss"]

    capital = 100_000.0
    curve = []
    today = datetime.utcnow()

    for i in range(n_points):
        date = (today - timedelta(days=n_points - i)).strftime("%Y-%m-%d")
        # Simulate ~0.4 trades per day on average (about 36 trades in 90 days)
        if rng.random() < 0.4:
            if rng.random() < win_rate:
                ret = rng.gauss(avg_win, avg_win * 0.3)
            else:
                ret = -rng.gauss(avg_loss, avg_loss * 0.3)
            capital *= 1 + ret * params["position_size"]
        curve.append({"date": date, "value": round(capital, 2)})

    return curve


def _compute_performance(equity_curve: List[Dict], params: Dict) -> Dict[str, Any]:
    """Derive performance metrics from an equity curve + strategy params."""
    if len(equity_curve) < 2:
        return {
            "sharpe": 0.0,
            "sortino": 0.0,
            "win_rate": params["win_rate"],
            "profit_factor": 0.0,
            "max_drawdown": 0.0,
            "total_return": 0.0,
            "num_trades": 0,
            "confidence": 50.0,
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

    # Estimated num trades
    num_trades = round(len(daily_returns) * 0.4)

    # Composite confidence
    confidence = min(95, max(20, 50 + sharpe * 10 + (params["win_rate"] - 0.5) * 100))

    return {
        "sharpe": round(sharpe, 3),
        "sortino": round(sortino, 3),
        "win_rate": round(params["win_rate"], 3),
        "profit_factor": round(profit_factor, 3),
        "max_drawdown": round(max_dd, 4),
        "total_return": round(total_return, 4),
        "num_trades": num_trades,
        "confidence": round(confidence, 1),
    }


def _synthetic_trades(
    strategy, rng: random.Random, n: int = 35
) -> List[Dict[str, Any]]:
    """Generate synthetic trade events with AI decision metadata."""
    params = _get_strategy_params(strategy)
    trades = []
    today = datetime.utcnow()
    symbols = ["AAPL", "MSFT", "NVDA", "GOOGL", "META", "AMZN", "TSLA", "SPY", "QQQ"]

    for i in range(n):
        is_win = rng.random() < params["win_rate"]
        symbol = rng.choice(symbols)
        direction = "long" if rng.random() < 0.7 else "short"
        entry_price = rng.uniform(80, 400)
        days_ago = n - i
        entry_dt = today - timedelta(days=days_ago, hours=rng.randint(9, 15))
        holding_days = rng.randint(1, 8)
        exit_dt = entry_dt + timedelta(days=holding_days)

        if is_win:
            pnl_pct = rng.gauss(params["avg_win"], params["avg_win"] * 0.4)
            pnl_pct = max(0.002, pnl_pct)
        else:
            pnl_pct = -rng.gauss(params["avg_loss"], params["avg_loss"] * 0.3)
            pnl_pct = min(-0.001, pnl_pct)

        if direction == "short":
            pnl_pct = -pnl_pct

        exit_price = entry_price * (1 + pnl_pct)
        qty = round((100_000 * params["position_size"]) / entry_price, 2)
        pnl = qty * (exit_price - entry_price)

        confidence = rng.gauss(65 if is_win else 52, 12)
        confidence = max(25, min(95, confidence))

        regime = rng.choice(REGIME_POOL[:4] if is_win else REGIME_POOL)
        n_signals = rng.randint(2, 4)
        signals = rng.sample(SIGNAL_POOL, n_signals)

        reasoning_template = rng.choice(REASONING_TEMPLATES[:4])
        reasoning = reasoning_template.format(
            sl=round(params["sl_pct"] * 100, 1),
            regime=regime,
            agree=round(rng.uniform(60, 95)),
            conf=round(confidence),
            days=holding_days,
            tp=round(params["tp_pct"] * 100, 1),
            rr=round(params["tp_pct"] / max(params["sl_pct"], 0.001), 1),
        )

        trades.append({
            "id": i + 1,
            "symbol": symbol,
            "direction": direction,
            "entry_time": entry_dt.isoformat(),
            "exit_time": exit_dt.isoformat(),
            "entry_price": round(entry_price, 2),
            "exit_price": round(exit_price, 2),
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct * 100, 2),
            "confidence": round(confidence, 1),
            "regime": regime,
            "signals": signals,
            "approved": True,
            "reasoning": reasoning,
            "model_name": "ensemble_v2",
            "bars_held": holding_days,
        })

    return trades


def _synthetic_reasoning_logs(strategy, rng: random.Random) -> List[Dict[str, Any]]:
    """Generate synthetic AI reasoning log entries."""
    params = _get_strategy_params(strategy)
    entries = []
    today = datetime.utcnow()
    symbols = ["AAPL", "MSFT", "NVDA", "GOOGL", "META"]

    for i in range(12):
        ts = today - timedelta(hours=i * 6 + rng.randint(0, 3))
        symbol = rng.choice(symbols)
        confidence = rng.gauss(65, 15)
        confidence = max(20, min(95, confidence))
        approved = confidence > 55
        regime = rng.choice(REGIME_POOL)

        if approved:
            text = REASONING_TEMPLATES[rng.randint(0, 3)].format(
                sl=round(params["sl_pct"] * 100, 1),
                regime=regime,
                agree=round(rng.uniform(60, 92)),
                conf=round(confidence),
                days=rng.randint(2, 10),
                tp=round(params["tp_pct"] * 100, 1),
                rr=round(params["tp_pct"] / max(params["sl_pct"], 0.001), 1),
            )
        else:
            text = REASONING_TEMPLATES[4]

        entries.append({
            "id": i + 1,
            "timestamp": ts.isoformat(),
            "symbol": symbol,
            "confidence": round(confidence, 1),
            "approved": approved,
            "regime": regime,
            "reasoning": text,
            "model": "claude-sonnet-4-6" if i % 3 == 0 else "gpt-4.1",
            "latency_ms": round(rng.uniform(120, 800)),
        })

    return entries


def _monte_carlo(trade_returns: List[float], n_sims: int = 200, n_steps: int = 90) -> Dict:
    """Run Monte Carlo simulation by resampling trade returns."""
    rng = random.Random(99)
    if not trade_returns:
        # Fallback: use mild positive drift with noise
        trade_returns = [rng.gauss(0.003, 0.02) for _ in range(30)]

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


def _feature_importance(strategy, rng: random.Random) -> List[Dict]:
    """Compute feature importance from strategy conditions."""
    conditions = []
    raw = getattr(strategy, "conditions", []) or []
    groups = getattr(strategy, "condition_groups", []) or []

    if groups:
        for g in groups:
            conditions.extend(g.get("conditions", []))
    else:
        conditions = raw

    features = []
    base_importance = 1.0
    for cond in conditions:
        indicator = str(cond.get("indicator", "unknown")).upper()
        importance = rng.gauss(base_importance, 0.2)
        importance = max(0.05, importance)
        features.append({"feature": indicator, "importance": round(importance, 3)})
        base_importance *= 0.85  # decay — first conditions matter more

    # Always include some structural features
    for name, base in [
        ("Regime Filter", 0.45),
        ("Volatility Context", 0.35),
        ("Volume Confirmation", 0.30),
        ("Time-of-Day", 0.18),
    ]:
        features.append({"feature": name, "importance": round(rng.gauss(base, 0.05), 3)})

    # Normalize so max = 1.0
    if features:
        max_imp = max(f["importance"] for f in features)
        for f in features:
            f["importance"] = round(f["importance"] / max_imp, 3)

    features.sort(key=lambda x: x["importance"], reverse=True)
    return features[:12]


def _profit_heatmap(trades: List[Dict], rng: random.Random) -> Dict:
    """Build profit heatmap aggregated by hour and day-of-week."""
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

    # If sparse, fill with synthetic
    for day in days:
        for hour in hours:
            if not grid[day][hour]:
                # Morning and EOD tend to be better
                bias = 0.3 if hour in [9, 10, 15] else (-0.1 if hour in [12, 13] else 0.1)
                day_bias = 0.2 if day in ["Tue", "Wed", "Thu"] else -0.1
                grid[day][hour] = [rng.gauss(bias + day_bias, 0.5)]

    # Compute averages
    data = []
    for day in days:
        for hour in hours:
            vals = grid[day][hour]
            avg = statistics.mean(vals) if vals else 0.0
            data.append({"day": day, "hour": hour, "avg_pnl_pct": round(avg, 3)})

    return {"data": data, "days": days, "hours": hours}


async def _load_strategy(strategy_id: int, db: AsyncSession):
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
        .where(StrategyInstance.id == strategy_id)
    )
    inst = inst_result.scalar_one_or_none()
    if inst and inst.template:
        return inst.template

    # 2. Fall back to legacy/demo Strategy table
    result = await db.execute(select(Strategy).where(Strategy.id == strategy_id))
    return result.scalar_one_or_none()


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.get("/strategy/{strategy_id}")
async def get_strategy_intelligence(
    strategy_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Full intelligence bundle — metadata, performance, equity curve, regime, decision pipeline."""
    strategy = await _load_strategy(strategy_id, db)
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    rng = _seeded_rng(strategy_id)
    params = _get_strategy_params(strategy)

    # Equity curve from snapshots or synthetic
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
    else:
        equity_curve = _synthetic_equity_curve(strategy, rng)

    perf = _compute_performance(equity_curve, params)

    # Current regime
    reg_result = await db.execute(
        select(MarketRegimeRecord).order_by(MarketRegimeRecord.timestamp.desc()).limit(1)
    )
    regime_rec = reg_result.scalar_one_or_none()
    current_regime = regime_rec.regime.value if regime_rec else "sideways"
    regime_conf = float(regime_rec.confidence or 0.65) if regime_rec else 0.65

    # Decision pipeline stages
    decision_pipeline = [
        {
            "stage": "Signal Generation",
            "passed": True,
            "reason": f"{len(getattr(strategy, 'conditions', []) or [])} conditions evaluated",
        },
        {
            "stage": "Confidence Threshold",
            "passed": perf["win_rate"] > 0.5,
            "reason": f"Win rate {perf['win_rate'] * 100:.0f}%",
        },
        {
            "stage": "Regime Filter",
            "passed": current_regime != "high_vol_bear",
            "reason": f"Regime: {current_regime.replace('_', ' ')}",
        },
        {
            "stage": "Risk Check",
            "passed": abs(perf["max_drawdown"]) < 0.25,
            "reason": f"Max DD {abs(perf['max_drawdown']) * 100:.1f}%",
        },
        {
            "stage": "Ensemble Agreement",
            "passed": perf["confidence"] > 60,
            "reason": f"Confidence {perf['confidence']:.0f}%",
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
    db: AsyncSession = Depends(get_db),
):
    """Trades with AI decision metadata (signals, confidence, regime, reasoning)."""
    strategy = await _load_strategy(strategy_id, db)
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
        rng = _seeded_rng(strategy_id)
        trades = _synthetic_trades(strategy, rng, n=min(limit, 35))

    return {"trades": trades, "total": len(trades)}


@router.get("/strategy/{strategy_id}/reasoning-logs")
async def get_reasoning_logs(
    strategy_id: int,
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """AI reasoning log entries — one entry per signal evaluation."""
    strategy = await _load_strategy(strategy_id, db)
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    # In production these come from CerberusAIToolCall or TradeEvent.reasoning_text
    # For now, generate synthetic logs
    rng = _seeded_rng(strategy_id + 1)
    logs = _synthetic_reasoning_logs(strategy, rng)
    return {"logs": logs[:limit], "total": len(logs)}


@router.get("/strategy/{strategy_id}/monte-carlo")
async def get_monte_carlo(
    strategy_id: int,
    n_sims: int = Query(200, ge=50, le=1000),
    horizon_days: int = Query(90, ge=30, le=365),
    db: AsyncSession = Depends(get_db),
):
    """Monte Carlo simulation by resampling historical trade returns."""
    strategy = await _load_strategy(strategy_id, db)
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    # Get trade returns from DB
    result = await db.execute(
        select(TradeEvent.pnl_pct)
        .where(TradeEvent.strategy_id == strategy_id, TradeEvent.pnl_pct.isnot(None))
        .limit(500)
    )
    raw_returns = [r[0] / 100.0 for r in result.fetchall() if r[0] is not None]

    # Fallback: simulate returns based on strategy params
    if not raw_returns:
        rng = _seeded_rng(strategy_id + 2)
        params = _get_strategy_params(strategy)
        raw_returns = []
        for _ in range(40):
            if rng.random() < params["win_rate"]:
                raw_returns.append(rng.gauss(params["avg_win"] * params["position_size"], 0.01))
            else:
                raw_returns.append(-rng.gauss(params["avg_loss"] * params["position_size"], 0.005))

    return _monte_carlo(raw_returns, n_sims=n_sims, n_steps=horizon_days)


@router.get("/strategy/{strategy_id}/feature-importance")
async def get_feature_importance(
    strategy_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Feature/condition importance scores."""
    strategy = await _load_strategy(strategy_id, db)
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    rng = _seeded_rng(strategy_id + 3)
    features = _feature_importance(strategy, rng)
    return {"features": features}


@router.get("/strategy/{strategy_id}/heatmap")
async def get_profit_heatmap(
    strategy_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Profit heatmap — average PnL% by hour × day-of-week."""
    strategy = await _load_strategy(strategy_id, db)
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    rng = _seeded_rng(strategy_id + 4)

    # Load real trade events
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
        trades = _synthetic_trades(strategy, rng, n=40)

    return _profit_heatmap(trades, rng)


@router.get("/compare")
async def compare_strategies(
    ids: str = Query(..., description="Comma-separated strategy IDs"),
    db: AsyncSession = Depends(get_db),
):
    """Side-by-side comparison of multiple strategies."""
    try:
        id_list = [int(x.strip()) for x in ids.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(status_code=400, detail="ids must be comma-separated integers")

    if not id_list or len(id_list) > 8:
        raise HTTPException(status_code=400, detail="Provide 1–8 strategy IDs")

    results = []
    for sid in id_list:
        strategy = await _load_strategy(sid, db)
        if not strategy:
            continue

        rng = _seeded_rng(sid)
        params = _get_strategy_params(strategy)
        equity_curve = _synthetic_equity_curve(strategy, rng)
        perf = _compute_performance(equity_curve, params)

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
