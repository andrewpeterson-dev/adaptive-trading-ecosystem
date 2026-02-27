"""
Trading endpoints — execute signals, manage positions, view orders.
"""

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from config.settings import get_settings, TradingMode
from engine.executor import ExecutionEngine, OrderType
from models.base import Signal
from risk.manager import RiskManager

router = APIRouter()

# Shared instances (in production, use dependency injection)
_risk_manager = RiskManager()
_executor = ExecutionEngine(risk_manager=_risk_manager)


class ExecuteSignalRequest(BaseModel):
    symbol: str
    direction: str  # "long", "short", "flat"
    strength: float = 1.0
    quantity: float = 10.0
    model_name: str = "manual"
    order_type: str = "market"
    limit_price: Optional[float] = None


class SwitchModeRequest(BaseModel):
    mode: str  # "paper", "live", "backtest"


@router.post("/execute")
async def execute_signal(req: ExecuteSignalRequest):
    """Execute a trading signal through the risk management layer."""
    signal = Signal(
        symbol=req.symbol,
        direction=req.direction,
        strength=req.strength,
        model_name=req.model_name,
    )

    try:
        account = _executor.get_account()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Broker unavailable: {str(e)}")

    current_equity = account["equity"]
    positions = _executor.get_positions()
    current_exposure = sum(abs(float(p["market_value"])) for p in positions)

    # Get current price (use last trade price approximation)
    current_price = req.limit_price or 0
    if current_price == 0:
        # In production, fetch real-time quote here
        raise HTTPException(status_code=400, detail="Price required for execution")

    result = _executor.execute_signal(
        signal=signal,
        quantity=req.quantity,
        current_price=current_price,
        current_equity=current_equity,
        current_exposure=current_exposure,
        order_type=OrderType(req.order_type),
        limit_price=req.limit_price,
    )

    if result is None:
        raise HTTPException(status_code=422, detail="Trade rejected by risk management")

    return result


@router.get("/account")
async def get_account():
    """Get current account information."""
    try:
        return _executor.get_account()
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/positions")
async def get_positions():
    """Get all open positions."""
    try:
        return _executor.get_positions()
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/orders")
async def get_orders(status: str = "open"):
    """Get orders by status."""
    return _executor.get_orders(status=status)


@router.get("/trade-log")
async def get_trade_log(limit: int = 100):
    """Get execution audit trail."""
    return _executor.get_trade_log(limit=limit)


@router.post("/switch-mode")
async def switch_mode(req: SwitchModeRequest):
    """Switch trading mode (paper/live)."""
    try:
        mode = TradingMode(req.mode)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid mode: {req.mode}")

    _executor.switch_mode(mode)
    return {"status": "switched", "mode": mode.value}


@router.get("/risk-summary")
async def get_risk_summary():
    """Get current risk status."""
    try:
        account = _executor.get_account()
        return _risk_manager.get_risk_summary(account["equity"])
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/risk-events")
async def get_risk_events(limit: int = 50):
    """Get recent risk events."""
    return _risk_manager.get_risk_events(limit=limit)


@router.post("/resume-trading")
async def resume_trading():
    """Resume trading after a halt."""
    _risk_manager.resume_trading()
    return {"status": "resumed"}
