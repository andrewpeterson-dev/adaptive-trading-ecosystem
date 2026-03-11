"""Risk analysis tools for the Cerberus."""
from __future__ import annotations

import asyncio
import math
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import structlog

from data.market_data import market_data
from risk.analytics import HAS_SCIPY, PortfolioRiskAnalyzer
from services.ai_core.tools.base import ToolDefinition, ToolCategory, ToolSideEffect
from services.ai_core.tools.registry import get_registry

logger = structlog.get_logger(__name__)

_risk_analyzer = PortfolioRiskAnalyzer()


def _z_score(confidence: float) -> float:
    if HAS_SCIPY:
        from scipy import stats as scipy_stats

        return float(scipy_stats.norm.ppf(1 - confidence))
    z_table = {0.90: -1.2816, 0.95: -1.6449, 0.99: -2.3263}
    return z_table.get(round(confidence, 2), -1.6449)


def _horizon_returns(returns: pd.Series, horizon_days: int) -> pd.Series:
    clean = returns.dropna()
    if horizon_days <= 1 or clean.empty:
        return clean
    return ((1 + clean).rolling(horizon_days).apply(np.prod, raw=True) - 1).dropna()


def _monte_carlo_var(returns: pd.Series, confidence: float, horizon_days: int, simulations: int = 5000) -> float:
    clean = returns.dropna()
    if clean.empty or len(clean) < 2:
        return 0.0
    sampled = np.random.choice(clean.to_numpy(), size=(simulations, max(horizon_days, 1)), replace=True)
    compounded = np.prod(1 + sampled, axis=1) - 1
    return float(np.percentile(compounded, (1 - confidence) * 100))


async def _portfolio_returns_from_snapshots(user_id: int, lookback_days: int = 365) -> tuple[pd.Series, dict]:
    from db.database import get_session
    from db.cerberus_models import CerberusPortfolioSnapshot
    from sqlalchemy import select

    cutoff = datetime.utcnow() - timedelta(days=lookback_days)

    async with get_session() as session:
        stmt = (
            select(CerberusPortfolioSnapshot)
            .where(
                CerberusPortfolioSnapshot.user_id == user_id,
                CerberusPortfolioSnapshot.snapshot_ts >= cutoff,
            )
            .order_by(CerberusPortfolioSnapshot.snapshot_ts.asc())
        )
        result = await session.execute(stmt)
        snapshots = result.scalars().all()

    rows = [
        {"date": pd.Timestamp(s.snapshot_ts).normalize(), "equity": float(s.equity or 0)}
        for s in snapshots
        if s.snapshot_ts and s.equity
    ]
    if len(rows) < 20:
        return pd.Series(dtype=float), {"source": "portfolio_snapshots", "observations": 0}

    frame = pd.DataFrame(rows)
    grouped = frame.groupby("date", as_index=True)["equity"].sum().sort_index()
    returns = grouped.pct_change().dropna()
    return returns, {
        "source": "portfolio_snapshots",
        "observations": int(len(returns)),
        "window_start": grouped.index.min().date().isoformat() if not grouped.empty else None,
        "window_end": grouped.index.max().date().isoformat() if not grouped.empty else None,
    }


async def _load_positions(user_id: int) -> list:
    from db.database import get_session
    from db.cerberus_models import CerberusPosition
    from sqlalchemy import select

    async with get_session() as session:
        stmt = select(CerberusPosition).where(CerberusPosition.user_id == user_id)
        result = await session.execute(stmt)
        return result.scalars().all()


async def _portfolio_returns_from_positions(positions: list, lookback_bars: int = 260) -> tuple[pd.Series, dict]:
    tradable_positions = [p for p in positions if p.symbol and float(p.market_value or 0)]
    if not tradable_positions:
        return pd.Series(dtype=float), {"source": "position_price_history", "observations": 0}

    symbols = sorted({p.symbol.upper() for p in tradable_positions})
    bars_list = await asyncio.gather(
        *[market_data.get_bars(symbol, timeframe="1D", limit=lookback_bars) for symbol in symbols],
        return_exceptions=True,
    )

    price_series: dict[str, pd.Series] = {}
    for symbol, bars in zip(symbols, bars_list):
        if isinstance(bars, Exception) or not bars:
            continue
        series = pd.Series(
            {pd.to_datetime(int(bar["t"]), unit="s"): float(bar["c"]) for bar in bars if bar.get("c") is not None}
        ).sort_index()
        if len(series) >= 20:
            price_series[symbol] = series

    if not price_series:
        return pd.Series(dtype=float), {"source": "position_price_history", "observations": 0}

    price_frame = pd.DataFrame(price_series).sort_index().ffill().dropna(how="all")
    returns_frame = price_frame.pct_change().dropna(how="all")
    if returns_frame.empty:
        return pd.Series(dtype=float), {"source": "position_price_history", "observations": 0}

    total_value = sum(abs(float(p.market_value or 0)) for p in tradable_positions)
    weights: dict[str, float] = {}
    for position in tradable_positions:
        symbol = position.symbol.upper()
        if symbol in returns_frame.columns and symbol not in weights:
            weights[symbol] = abs(float(position.market_value or 0)) / total_value if total_value else 0.0

    portfolio_returns = pd.Series(0.0, index=returns_frame.index)
    for symbol, weight in weights.items():
        portfolio_returns += returns_frame[symbol].fillna(0.0) * weight

    return portfolio_returns.dropna(), {
        "source": "position_price_history",
        "observations": int(len(portfolio_returns.dropna())),
        "symbols": sorted(weights.keys()),
    }


async def _load_portfolio_returns(user_id: int) -> tuple[pd.Series, float, dict]:
    positions = await _load_positions(user_id)
    total_value = sum(abs(float(p.market_value or 0)) for p in positions)

    returns, metadata = await _portfolio_returns_from_snapshots(user_id)
    if len(returns) >= 20:
        return returns, total_value, metadata

    returns, price_metadata = await _portfolio_returns_from_positions(positions)
    return returns, total_value, price_metadata


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

async def _calculate_var(
    user_id: int,
    confidence: float = 0.95,
    horizon_days: int = 1,
    method: str = "historical",
) -> dict:
    """Calculate Value at Risk for the current portfolio."""
    confidence = float(confidence or 0.95)
    horizon_days = max(int(horizon_days or 1), 1)
    method = (method or "historical").lower()

    returns, total_value, metadata = await _load_portfolio_returns(user_id)
    if total_value <= 0:
        return {"var": 0, "confidence": confidence, "horizon_days": horizon_days, "message": "No positions found"}

    if returns.empty or len(returns) < 2:
        return {
            "var": 0,
            "var_pct": 0,
            "confidence": confidence,
            "horizon_days": horizon_days,
            "method": method,
            "total_portfolio_value": round(total_value, 2),
            "message": "Insufficient historical returns to calculate VaR",
            "data_source": metadata.get("source"),
        }

    if method == "historical":
        var_return = _risk_analyzer.calculate_var(_horizon_returns(returns, horizon_days), confidence=confidence, method="historical")
    elif method == "parametric":
        mu = float(returns.mean()) * horizon_days
        sigma = float(returns.std()) * math.sqrt(horizon_days)
        var_return = mu + _z_score(confidence) * sigma if sigma else 0.0
    elif method == "monte_carlo":
        var_return = _monte_carlo_var(returns, confidence=confidence, horizon_days=horizon_days)
    else:
        raise ValueError(f"Unsupported VaR method: {method}")

    var_amount = abs(var_return) * total_value

    return {
        "var": round(var_amount, 2),
        "var_pct": round(abs(var_return) * 100, 4),
        "portfolio_return_var": round(var_return, 6),
        "confidence": confidence,
        "horizon_days": horizon_days,
        "method": method,
        "total_portfolio_value": round(total_value, 2),
        "observations": metadata.get("observations", int(len(returns))),
        "data_source": metadata.get("source"),
        "symbols": metadata.get("symbols"),
    }


async def _calculate_drawdown(user_id: int, days: int = 30) -> dict:
    """Calculate max drawdown over a period using portfolio snapshots."""
    from db.database import get_session
    from db.cerberus_models import CerberusPortfolioSnapshot
    from sqlalchemy import select

    cutoff = datetime.utcnow() - timedelta(days=days)

    async with get_session() as session:
        stmt = (
            select(CerberusPortfolioSnapshot)
            .where(
                CerberusPortfolioSnapshot.user_id == user_id,
                CerberusPortfolioSnapshot.snapshot_ts >= cutoff,
            )
            .order_by(CerberusPortfolioSnapshot.snapshot_ts.asc())
        )
        result = await session.execute(stmt)
        snapshots = result.scalars().all()

    if not snapshots:
        return {"max_drawdown_pct": 0, "days": days, "message": "No snapshots found for period"}

    equities = [float(s.equity or 0) for s in snapshots]
    peak = equities[0]
    max_dd = 0.0
    max_dd_peak = peak
    max_dd_trough = peak

    for eq in equities:
        if eq > peak:
            peak = eq
        dd = (peak - eq) / peak if peak > 0 else 0
        if dd > max_dd:
            max_dd = dd
            max_dd_peak = peak
            max_dd_trough = eq

    return {
        "max_drawdown_pct": round(max_dd * 100, 4),
        "max_drawdown_peak": round(max_dd_peak, 2),
        "max_drawdown_trough": round(max_dd_trough, 2),
        "days": days,
        "snapshots_analyzed": len(snapshots),
    }


async def _portfolio_exposure(user_id: int) -> dict:
    """Get exposure breakdown by asset type and sector."""
    from db.database import get_session
    from db.cerberus_models import CerberusPosition
    from sqlalchemy import select

    async with get_session() as session:
        stmt = select(CerberusPosition).where(CerberusPosition.user_id == user_id)
        result = await session.execute(stmt)
        positions = result.scalars().all()

    if not positions:
        return {"total_exposure": 0, "by_asset_type": {}, "by_symbol": {}, "message": "No positions"}

    total = 0.0
    by_asset_type: dict[str, float] = {}
    by_symbol: dict[str, float] = {}

    for p in positions:
        mv = float(p.market_value or 0)
        total += abs(mv)
        atype = p.asset_type or "unknown"
        by_asset_type[atype] = by_asset_type.get(atype, 0) + mv
        by_symbol[p.symbol] = by_symbol.get(p.symbol, 0) + mv

    return {
        "total_exposure": round(total, 2),
        "long_exposure": round(sum(v for v in by_symbol.values() if v > 0), 2),
        "short_exposure": round(sum(v for v in by_symbol.values() if v < 0), 2),
        "by_asset_type": {k: round(v, 2) for k, v in by_asset_type.items()},
        "by_symbol": {k: round(v, 2) for k, v in by_symbol.items()},
    }


async def _concentration_risk(user_id: int) -> dict:
    """Get concentration metrics (HHI, top holdings weight)."""
    from db.database import get_session
    from db.cerberus_models import CerberusPosition
    from sqlalchemy import select

    async with get_session() as session:
        stmt = select(CerberusPosition).where(CerberusPosition.user_id == user_id)
        result = await session.execute(stmt)
        positions = result.scalars().all()

    if not positions:
        return {"hhi": 0, "top_5_weight_pct": 0, "message": "No positions"}

    values = [(p.symbol, abs(float(p.market_value or 0))) for p in positions]
    total = sum(v for _, v in values)
    if total == 0:
        return {"hhi": 0, "top_5_weight_pct": 0, "message": "All positions have zero value"}

    weights = [(sym, val / total) for sym, val in values]
    weights.sort(key=lambda x: x[1], reverse=True)

    hhi = sum(w ** 2 for _, w in weights)
    top_5_weight = sum(w for _, w in weights[:5])

    return {
        "hhi": round(hhi, 6),
        "hhi_normalized": round((hhi - 1 / len(weights)) / (1 - 1 / len(weights)), 6) if len(weights) > 1 else 1.0,
        "top_5_weight_pct": round(top_5_weight * 100, 2),
        "top_holdings": [{"symbol": sym, "weight_pct": round(w * 100, 2)} for sym, w in weights[:5]],
        "position_count": len(weights),
    }


async def _options_greek_exposure(user_id: int) -> dict:
    """Get aggregate Greeks exposure across all options positions."""
    from db.database import get_session
    from db.cerberus_models import CerberusPosition
    from sqlalchemy import select

    async with get_session() as session:
        stmt = select(CerberusPosition).where(
            CerberusPosition.user_id == user_id,
            CerberusPosition.asset_type.in_(["option", "call", "put"]),
        )
        result = await session.execute(stmt)
        positions = result.scalars().all()

    if not positions:
        return {
            "delta": 0, "gamma": 0, "vega": 0, "theta": 0,
            "positions": 0, "message": "No options positions found",
        }

    agg_delta = 0.0
    agg_gamma = 0.0
    agg_vega = 0.0
    agg_theta = 0.0

    for p in positions:
        greeks = p.greeks_json or {}
        qty = float(p.quantity or 0)
        agg_delta += float(greeks.get("delta", 0)) * qty
        agg_gamma += float(greeks.get("gamma", 0)) * qty
        agg_vega += float(greeks.get("vega", 0)) * qty
        agg_theta += float(greeks.get("theta", 0)) * qty

    return {
        "delta": round(agg_delta, 4),
        "gamma": round(agg_gamma, 6),
        "vega": round(agg_vega, 4),
        "theta": round(agg_theta, 4),
        "positions": len(positions),
    }


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register():
    registry = get_registry()

    registry.register(ToolDefinition(
        name="calculateVaR",
        version="1.0",
        description="Calculate Value at Risk for the portfolio at a given confidence level and horizon",
        category=ToolCategory.RISK,
        side_effect=ToolSideEffect.READ,
        timeout_ms=5000,
        cache_ttl_s=60,
        input_schema={
            "type": "object",
            "properties": {
                "confidence": {"type": "number", "description": "Confidence level (0-1)", "default": 0.95},
                "horizon_days": {"type": "integer", "description": "Time horizon in days", "default": 1},
                "method": {"type": "string", "enum": ["historical", "parametric", "monte_carlo"], "default": "historical"},
            },
        },
        output_schema={"type": "object"},
        handler=_calculate_var,
    ))

    registry.register(ToolDefinition(
        name="calculateDrawdown",
        version="1.0",
        description="Calculate maximum drawdown over a given period",
        category=ToolCategory.RISK,
        side_effect=ToolSideEffect.READ,
        timeout_ms=3000,
        cache_ttl_s=60,
        input_schema={
            "type": "object",
            "properties": {
                "days": {"type": "integer", "description": "Lookback period in days", "default": 30},
            },
        },
        output_schema={"type": "object"},
        handler=_calculate_drawdown,
    ))

    registry.register(ToolDefinition(
        name="portfolioExposure",
        version="1.0",
        description="Get exposure breakdown by asset type and symbol (long/short)",
        category=ToolCategory.RISK,
        side_effect=ToolSideEffect.READ,
        timeout_ms=2000,
        cache_ttl_s=30,
        input_schema={"type": "object", "properties": {}},
        output_schema={"type": "object"},
        handler=_portfolio_exposure,
    ))

    registry.register(ToolDefinition(
        name="concentrationRisk",
        version="1.0",
        description="Get portfolio concentration metrics (HHI, top holdings weight)",
        category=ToolCategory.RISK,
        side_effect=ToolSideEffect.READ,
        timeout_ms=2000,
        cache_ttl_s=30,
        input_schema={"type": "object", "properties": {}},
        output_schema={"type": "object"},
        handler=_concentration_risk,
    ))

    registry.register(ToolDefinition(
        name="optionsGreekExposure",
        version="1.0",
        description="Get aggregate Greeks exposure (delta, gamma, vega, theta) across options positions",
        category=ToolCategory.RISK,
        side_effect=ToolSideEffect.READ,
        timeout_ms=2000,
        cache_ttl_s=15,
        input_schema={"type": "object", "properties": {}},
        output_schema={"type": "object"},
        handler=_options_greek_exposure,
    ))
