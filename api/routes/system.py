"""
System administration endpoints — health, config, monitoring, scheduler controls.
"""

from fastapi import APIRouter, Request

from config.settings import get_settings
from services.security.access_control import require_admin

router = APIRouter()

# Shared instances — initialized on first request
_health_checker = None
_watchdog = None
_scheduler = None


def _get_health_checker():
    global _health_checker
    if _health_checker is None:
        from monitor.health_check import HealthChecker
        _health_checker = HealthChecker()
    return _health_checker


def _get_watchdog():
    global _watchdog
    if _watchdog is None:
        from monitor.llm_watchdog import LLMWatchdog
        _watchdog = LLMWatchdog()
    return _watchdog


def _get_scheduler():
    global _scheduler
    if _scheduler is None:
        from monitor.scheduler import JobScheduler
        _scheduler = JobScheduler()
    return _scheduler


@router.get("/config")
async def get_config(request: Request):
    """Get current system configuration (non-sensitive)."""
    await require_admin(request)
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


@router.get("/health/detailed")
async def detailed_health_check(request: Request):
    """Comprehensive health check — database, Redis, broker, disk, memory."""
    await require_admin(request)
    checker = _get_health_checker()
    return await checker.check_all()


@router.get("/monitor/stats")
async def monitor_stats(request: Request):
    """Get watchdog and scheduler statistics."""
    await require_admin(request)
    watchdog = _get_watchdog()
    scheduler = _get_scheduler()
    return {
        "watchdog": watchdog.get_stats(),
        "scheduler": scheduler.get_status(),
    }
