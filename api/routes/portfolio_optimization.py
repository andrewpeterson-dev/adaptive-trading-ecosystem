"""
Portfolio optimization API routes.

Provides endpoints for:
- Running portfolio optimizations (Max Sharpe, Min Vol, HRP, Risk Parity)
- Generating rebalance plans from current holdings
- Computing efficient frontier curves for charting
- Computing correlation matrices
"""

from __future__ import annotations

import asyncio
from typing import Dict, List, Optional

import structlog
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from services.portfolio_optimizer import (
    OptimizationConstraints,
    compute_correlation_matrix,
    compute_efficient_frontier,
    optimize_black_litterman,
    run_optimization,
)
from services.rebalance_planner import (
    CurrentHolding,
    generate_rebalance_plan,
)

logger = structlog.get_logger(__name__)
router = APIRouter()


# ── Request / Response models ────────────────────────────────────────────────


class ConstraintsInput(BaseModel):
    max_weight: float = Field(default=0.40, ge=0.01, le=1.0)
    min_weight: float = Field(default=0.0, ge=0.0, le=1.0)
    sector_caps: Dict[str, float] = Field(default_factory=dict)


class OptimizeRequest(BaseModel):
    tickers: List[str] = Field(..., min_length=2, max_length=50)
    method: str = Field(default="max_sharpe")
    constraints: Optional[ConstraintsInput] = None
    lookback_days: int = Field(default=252, ge=30, le=1260)


class BlackLittermanRequest(BaseModel):
    tickers: List[str] = Field(..., min_length=2, max_length=50)
    views: Dict[str, float] = Field(
        ...,
        description="Absolute return views, e.g. {'AAPL': 0.10, 'GOOG': 0.05}",
    )
    constraints: Optional[ConstraintsInput] = None
    lookback_days: int = Field(default=252, ge=30, le=1260)


class OptimizeResponse(BaseModel):
    weights: Dict[str, float]
    expected_return: float
    volatility: float
    sharpe: float
    method: str


class FrontierPointResponse(BaseModel):
    expected_return: float
    volatility: float
    sharpe: float


class CorrelationResponse(BaseModel):
    tickers: List[str]
    matrix: List[List[float]]


class RebalanceOrderResponse(BaseModel):
    ticker: str
    action: str
    shares: float
    estimated_cost: float
    reason: str
    current_weight: float
    target_weight: float
    weight_delta: float
    is_tax_loss_harvest: bool


class RebalancePlanResponse(BaseModel):
    orders: List[RebalanceOrderResponse]
    total_portfolio_value: float
    cash_available: float
    estimated_total_cost: float
    num_buys: int
    num_sells: int
    tax_loss_harvest_count: int


# ── Routes ───────────────────────────────────────────────────────────────────


@router.post("/optimize", response_model=OptimizeResponse)
async def optimize_portfolio(body: OptimizeRequest, request: Request):
    """Run portfolio optimization with the specified method and constraints.

    Accepts a list of tickers, an optimization method, optional constraints,
    and a lookback period. Returns optimized weights and expected metrics.
    """
    user_id = request.state.user_id

    # Normalize tickers
    tickers = [t.strip().upper() for t in body.tickers if t.strip()]
    if len(tickers) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 valid tickers.")

    valid_methods = ("max_sharpe", "min_volatility", "hrp", "risk_parity")
    if body.method not in valid_methods:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid method '{body.method}'. Valid: {valid_methods}",
        )

    constraints = None
    if body.constraints:
        constraints = OptimizationConstraints(
            max_weight=body.constraints.max_weight,
            min_weight=body.constraints.min_weight,
            sector_caps=body.constraints.sector_caps,
        )

    try:
        result = await run_optimization(
            tickers=tickers,
            method=body.method,
            lookback_days=body.lookback_days,
            constraints=constraints,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("portfolio_optimization_failed", user_id=user_id, error=str(exc))
        raise HTTPException(status_code=500, detail="Optimization failed. Check ticker symbols and try again.")

    logger.info(
        "portfolio_optimized",
        user_id=user_id,
        method=result.method,
        sharpe=f"{result.sharpe:.4f}",
        num_tickers=len(tickers),
    )

    return OptimizeResponse(
        weights=result.weights,
        expected_return=result.expected_return,
        volatility=result.volatility,
        sharpe=result.sharpe,
        method=result.method,
    )


@router.post("/optimize/black-litterman", response_model=OptimizeResponse)
async def optimize_bl(body: BlackLittermanRequest, request: Request):
    """Run Black-Litterman optimization with user-supplied return views.

    Accepts tickers, a dict of absolute return views, optional constraints,
    and a lookback period. Returns optimized weights and expected metrics.
    """
    user_id = request.state.user_id

    tickers = [t.strip().upper() for t in body.tickers if t.strip()]
    if len(tickers) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 valid tickers.")

    # Normalize view keys to uppercase
    views = {k.strip().upper(): v for k, v in body.views.items()}

    # Validate that view tickers are a subset of the provided tickers
    unknown = set(views.keys()) - set(tickers)
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=f"View tickers not in ticker list: {sorted(unknown)}",
        )

    constraints = None
    if body.constraints:
        constraints = OptimizationConstraints(
            max_weight=body.constraints.max_weight,
            min_weight=body.constraints.min_weight,
            sector_caps=body.constraints.sector_caps,
        )

    try:
        result = await optimize_black_litterman(
            tickers=tickers,
            views=views,
            lookback_days=body.lookback_days,
            constraints=constraints,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("black_litterman_optimization_failed", user_id=user_id, error=str(exc), exc_info=True)
        raise HTTPException(status_code=500, detail="Optimization failed. Check ticker symbols and try again.")

    logger.info(
        "black_litterman_optimized",
        user_id=user_id,
        sharpe=f"{result.sharpe:.4f}",
        num_tickers=len(tickers),
        num_views=len(views),
    )

    return OptimizeResponse(
        weights=result.weights,
        expected_return=result.expected_return,
        volatility=result.volatility,
        sharpe=result.sharpe,
        method=result.method,
    )


@router.get("/efficient-frontier")
async def get_efficient_frontier(
    request: Request,
    tickers: str = Query(..., description="Comma-separated ticker symbols"),
    lookback_days: int = Query(default=252, ge=30, le=1260),
    n_points: int = Query(default=40, ge=10, le=100),
):
    """Return efficient frontier curve data for charting.

    Returns a list of {expected_return, volatility, sharpe} points along
    the frontier from minimum volatility to beyond the max-sharpe portfolio.
    """
    user_id = request.state.user_id
    ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]

    if len(ticker_list) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 tickers.")
    if len(ticker_list) > 50:
        raise HTTPException(status_code=400, detail="Maximum 50 tickers allowed")

    try:
        points = await compute_efficient_frontier(ticker_list, lookback_days, n_points)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("efficient_frontier_failed", user_id=user_id, error=str(exc))
        raise HTTPException(status_code=500, detail="Failed to compute efficient frontier.")

    return {
        "points": [
            {
                "expected_return": round(p.expected_return, 6),
                "volatility": round(p.volatility, 6),
                "sharpe": round(p.sharpe, 4),
            }
            for p in points
        ],
        "tickers": ticker_list,
    }


@router.get("/correlation-matrix", response_model=CorrelationResponse)
async def get_correlation_matrix(
    request: Request,
    tickers: str = Query(..., description="Comma-separated ticker symbols"),
    lookback_days: int = Query(default=252, ge=30, le=1260),
):
    """Return the correlation matrix for the given tickers.

    Used for heatmap visualization on the risk page.
    """
    user_id = request.state.user_id
    ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]

    if len(ticker_list) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 tickers.")
    if len(ticker_list) > 50:
        raise HTTPException(status_code=400, detail="Maximum 50 tickers allowed")

    try:
        result = await compute_correlation_matrix(ticker_list, lookback_days)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("correlation_matrix_failed", user_id=user_id, error=str(exc))
        raise HTTPException(status_code=500, detail="Failed to compute correlation matrix.")

    return CorrelationResponse(
        tickers=result["tickers"],
        matrix=result["matrix"],
    )


@router.get("/rebalance-plan", response_model=RebalancePlanResponse)
async def get_rebalance_plan(
    request: Request,
    method: str = Query(default="max_sharpe"),
    lookback_days: int = Query(default=252, ge=30, le=1260),
    max_weight: float = Query(default=0.40, ge=0.01, le=1.0),
    min_trade_value: float = Query(default=50.0, ge=0),
    tax_loss_harvesting: bool = Query(default=False),
):
    """Generate a rebalance plan from current Webull holdings.

    Fetches the user's current positions from Webull, runs optimization
    on those tickers, and returns a list of proposed trades to align
    the portfolio with the optimized weights.
    """
    user_id = request.state.user_id

    # Lazy import to avoid circular deps
    from api.routes.webull import _get_user_clients

    # Determine mode
    from db.models import TradingModeEnum
    mode_enum = getattr(request.state, "trading_mode", TradingModeEnum.PAPER)
    mode_str = "real" if mode_enum == TradingModeEnum.LIVE else "paper"

    clients = await _get_user_clients(user_id, mode_str)
    if not clients:
        raise HTTPException(status_code=400, detail="No Webull credentials configured. Connect a broker first.")

    # Fetch positions and account summary in parallel
    positions_data, account_data = await asyncio.gather(
        asyncio.to_thread(clients.account.get_positions),
        asyncio.to_thread(clients.account.get_summary),
    )

    if not positions_data:
        raise HTTPException(
            status_code=400,
            detail="No positions found. Open some positions first or use the optimize endpoint with manual tickers.",
        )

    # Parse holdings
    holdings: List[CurrentHolding] = []
    for pos in positions_data:
        ticker = pos.get("symbol") or pos.get("ticker", "")
        qty = float(pos.get("quantity", 0) or pos.get("qty", 0))
        price = float(pos.get("market_price", 0) or pos.get("lastPrice", 0) or pos.get("current_price", 0))
        market_val = float(pos.get("market_value", 0) or pos.get("marketValue", qty * price))
        cost_basis = pos.get("cost_basis") or pos.get("costBasis")
        if cost_basis is not None:
            cost_basis = float(cost_basis)

        if ticker and qty > 0 and price > 0:
            holdings.append(CurrentHolding(
                ticker=ticker.upper(),
                quantity=qty,
                current_price=price,
                market_value=market_val,
                cost_basis=cost_basis,
            ))

    if len(holdings) < 2:
        raise HTTPException(
            status_code=400,
            detail="Need at least 2 positions to optimize. Use the optimize endpoint for manual ticker selection.",
        )

    tickers = [h.ticker for h in holdings]
    total_value = sum(h.market_value for h in holdings)
    cash = float((account_data or {}).get("cash", 0) or (account_data or {}).get("cashBalance", 0))
    total_portfolio_value = total_value + cash

    # Run optimization
    constraints = OptimizationConstraints(max_weight=max_weight)
    try:
        result = await run_optimization(
            tickers=tickers,
            method=method,
            lookback_days=lookback_days,
            constraints=constraints,
        )
    except Exception as exc:
        logger.error("rebalance_optimization_failed", user_id=user_id, error=str(exc), exc_info=True)
        raise HTTPException(status_code=500, detail="Optimization failed. Check ticker symbols and try again.")

    # Generate rebalance plan
    plan = await generate_rebalance_plan(
        holdings=holdings,
        target_weights=result.weights,
        total_portfolio_value=total_portfolio_value,
        cash_available=cash,
        min_trade_value=min_trade_value,
        enable_tax_loss_harvesting=tax_loss_harvesting,
    )

    return RebalancePlanResponse(
        orders=[
            RebalanceOrderResponse(
                ticker=o.ticker,
                action=o.action,
                shares=o.shares,
                estimated_cost=o.estimated_cost,
                reason=o.reason,
                current_weight=o.current_weight,
                target_weight=o.target_weight,
                weight_delta=o.weight_delta,
                is_tax_loss_harvest=o.is_tax_loss_harvest,
            )
            for o in plan.orders
        ],
        total_portfolio_value=plan.total_portfolio_value,
        cash_available=plan.cash_available,
        estimated_total_cost=plan.estimated_total_cost,
        num_buys=plan.num_buys,
        num_sells=plan.num_sells,
        tax_loss_harvest_count=plan.tax_loss_harvest_count,
    )
