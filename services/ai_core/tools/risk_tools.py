"""Risk analysis tools for the Cerberus."""
from __future__ import annotations

import structlog

from services.ai_core.tools.base import ToolDefinition, ToolCategory, ToolSideEffect
from services.ai_core.tools.registry import get_registry

logger = structlog.get_logger(__name__)


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
    from db.database import get_session
    from db.cerberus_models import CerberusPosition
    from sqlalchemy import select

    async with get_session() as session:
        stmt = select(CerberusPosition).where(CerberusPosition.user_id == user_id)
        result = await session.execute(stmt)
        positions = result.scalars().all()

    if not positions:
        return {"var": 0, "confidence": confidence, "horizon_days": horizon_days, "message": "No positions found"}

    total_value = sum(float(p.market_value or 0) for p in positions)

    # TODO: Replace with proper VaR calculation using historical returns
    # For now, use a simplified parametric estimate (assume ~1.5% daily vol)
    import math
    from scipy.stats import norm

    z_score = norm.ppf(confidence)
    daily_vol_estimate = 0.015  # 1.5% placeholder
    var_estimate = total_value * z_score * daily_vol_estimate * math.sqrt(horizon_days)

    return {
        "var": round(var_estimate, 2),
        "var_pct": round(z_score * daily_vol_estimate * math.sqrt(horizon_days) * 100, 4),
        "confidence": confidence,
        "horizon_days": horizon_days,
        "method": method,
        "total_portfolio_value": round(total_value, 2),
        "note": "Simplified parametric VaR; replace with historical returns model",
    }


async def _calculate_drawdown(user_id: int, days: int = 30) -> dict:
    """Calculate max drawdown over a period using portfolio snapshots."""
    from datetime import datetime, timedelta
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
