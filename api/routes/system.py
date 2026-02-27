"""
System administration endpoints — health, config, scheduler controls.
"""

from fastapi import APIRouter

from config.settings import get_settings

router = APIRouter()


@router.get("/config")
async def get_config():
    """Get current system configuration (non-sensitive)."""
    s = get_settings()
    return {
        "trading_mode": s.trading_mode.value,
        "max_position_size_pct": s.max_position_size_pct,
        "max_portfolio_exposure_pct": s.max_portfolio_exposure_pct,
        "max_drawdown_pct": s.max_drawdown_pct,
        "stop_loss_pct": s.stop_loss_pct,
        "max_trades_per_hour": s.max_trades_per_hour,
        "retrain_interval_hours": s.retrain_interval_hours,
        "walk_forward_window_days": s.walk_forward_window_days,
        "initial_capital": s.initial_capital,
        "min_model_weight": s.min_model_weight,
        "max_model_weight": s.max_model_weight,
    }


@router.get("/version")
async def get_version():
    return {"version": "1.0.0", "name": "Adaptive Trading Ecosystem"}
