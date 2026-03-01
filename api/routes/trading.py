"""
Trading endpoints — execute signals, manage positions, view orders.
"""

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import pandas as pd

from config.settings import get_settings, TradingMode
from engine.executor import ExecutionEngine, OrderType
from models.base import Signal
from risk.analytics import PortfolioRiskAnalyzer
from risk.manager import RiskManager
from services.security.verification import TransactionVerifier

router = APIRouter()

# Shared instances (lazy init — Alpaca client needs API keys)
_risk_manager = RiskManager()
_executor = None
_risk_analyzer = PortfolioRiskAnalyzer()


def _get_executor() -> ExecutionEngine:
    global _executor
    if _executor is None:
        _executor = ExecutionEngine(risk_manager=_risk_manager)
    return _executor


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
        account = _get_executor().get_account()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Broker unavailable: {str(e)}")

    current_equity = account["equity"]
    positions = _get_executor().get_positions()
    current_exposure = sum(abs(float(p["market_value"])) for p in positions)

    # Get current price (use last trade price approximation)
    current_price = req.limit_price or 0
    if current_price == 0:
        # In production, fetch real-time quote here
        raise HTTPException(status_code=400, detail="Price required for execution")

    result = _get_executor().execute_signal(
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
        return _get_executor().get_account()
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/positions")
async def get_positions():
    """Get all open positions."""
    try:
        return _get_executor().get_positions()
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/orders")
async def get_orders(status: str = "open"):
    """Get orders by status."""
    return _get_executor().get_orders(status=status)


@router.get("/trade-log")
async def get_trade_log(limit: int = 100):
    """Get execution audit trail."""
    return _get_executor().get_trade_log(limit=limit)


@router.post("/switch-mode")
async def switch_mode(req: SwitchModeRequest):
    """Switch trading mode (paper/live)."""
    try:
        mode = TradingMode(req.mode)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid mode: {req.mode}")

    _get_executor().switch_mode(mode)
    return {"status": "switched", "mode": mode.value}


@router.get("/risk-summary")
async def get_risk_summary():
    """Get current risk status."""
    try:
        account = _get_executor().get_account()
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


@router.get("/verify")
async def verify_transactions():
    """Run transaction verification — compare broker orders against local audit log."""
    verifier = TransactionVerifier()
    try:
        report = verifier.verify_execution(_executor)
        return report
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Verification failed: {str(e)}")


@router.get("/portfolio-analytics")
async def get_portfolio_analytics(symbols: Optional[str] = None):
    """
    Generate portfolio risk analytics report.
    Optional query param `symbols` — comma-separated list to restrict analysis.
    """
    try:
        positions = _get_executor().get_positions()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Broker unavailable: {str(e)}")

    # Filter positions by requested symbols
    if symbols:
        requested = {s.strip().upper() for s in symbols.split(",")}
        positions = [p for p in positions if p.get("symbol", "").upper() in requested]

    if not positions:
        return _risk_analyzer.generate_risk_report([], pd.DataFrame())

    # Build price history from broker (bars endpoint)
    all_symbols = list({p["symbol"] for p in positions if p.get("symbol")})
    # Include SPY for beta calculations
    if "SPY" not in all_symbols:
        all_symbols.append("SPY")

    price_frames = {}
    for sym in all_symbols:
        try:
            bars = _get_executor().get_bars(sym, timeframe="1Day", limit=252)
            if bars:
                price_frames[sym] = pd.Series(
                    {b["timestamp"]: b["close"] for b in bars}
                )
        except Exception:
            pass  # warnings will note missing symbols

    if price_frames:
        price_history = pd.DataFrame(price_frames).sort_index().dropna(how="all")
    else:
        price_history = pd.DataFrame()

    try:
        account = _get_executor().get_account()
        portfolio_value = account.get("equity")
    except Exception:
        portfolio_value = None

    report = _risk_analyzer.generate_risk_report(
        positions=positions,
        price_history=price_history,
        portfolio_value=portfolio_value,
    )
    return report
