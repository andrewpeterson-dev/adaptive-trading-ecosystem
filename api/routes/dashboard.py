"""
Dashboard data endpoints — serves pre-computed data for the Streamlit frontend.
"""

from fastapi import APIRouter

from allocation.capital import CapitalAllocator
from engine.backtester import BacktestEngine
from intelligence.regime import RegimeDetector
from models.registry import create_default_models
from risk.manager import RiskManager

router = APIRouter()


@router.get("/equity-curve")
async def get_equity_curve():
    """Get equity curve data for charting."""
    engine = BacktestEngine()
    results = engine.get_results_summary()
    return {"results": results}


@router.get("/overview")
async def get_dashboard_overview():
    """Aggregated dashboard overview."""
    models = create_default_models()
    allocator = CapitalAllocator()
    risk = RiskManager()

    return {
        "total_models": len(models),
        "trained_models": sum(1 for m in models if m.is_trained),
        "allocation": allocator.get_allocation_summary(),
        "risk": risk.get_risk_summary(allocator.total_capital),
    }
