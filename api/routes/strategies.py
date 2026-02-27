"""
Strategy Intelligence API routes.
Handles strategy CRUD, indicator computation, and diagnostics.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Any, Optional
import structlog

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/strategies", tags=["strategies"])


# ── Request/Response Models ──────────────────────────────────────────────

class ConditionSchema(BaseModel):
    indicator: str
    operator: str = ">"
    value: float | str = 0
    compare_to: Optional[str] = None  # e.g., "close", "ema_200"
    params: dict[str, Any] = Field(default_factory=dict)
    action: str = "BUY"

class StrategySchema(BaseModel):
    name: str
    description: str = ""
    conditions: list[ConditionSchema]
    action: str = "BUY"
    stop_loss_pct: float = 0.02
    take_profit_pct: float = 0.05
    position_size_pct: float = 0.1
    timeframe: str = "1D"

class StrategyResponse(BaseModel):
    id: str
    name: str
    conditions: list[dict]
    diagnostics: dict
    created_at: str

class ComputeRequest(BaseModel):
    indicator: str
    params: dict[str, Any] = Field(default_factory=dict)
    symbol: str = "SPY"
    bars: int = 200

class DiagnoseRequest(BaseModel):
    conditions: list[ConditionSchema]
    parameters: dict[str, dict[str, Any]] = Field(default_factory=dict)

class ExplainRequest(BaseModel):
    strategy_logic: str

class ExplainResponse(BaseModel):
    summary: str
    market_regime: str
    strengths: list[str]
    weaknesses: list[str]
    risk_profile: str
    overfitting_warning: bool


# ── In-memory store (replace with PostgreSQL in production) ──────────────

_strategies: dict[str, dict] = {}
_next_id = 1


# ── Routes ───────────────────────────────────────────────────────────────

@router.post("/create", response_model=StrategyResponse)
async def create_strategy(strategy: StrategySchema):
    global _next_id
    from services.diagnostics import StrategyDiagnostics
    from datetime import datetime

    conditions_dicts = [c.model_dump() for c in strategy.conditions]
    params = {}
    for c in strategy.conditions:
        params[c.indicator] = c.params

    report = StrategyDiagnostics.run_all(conditions_dicts, params)

    strategy_id = f"strat_{_next_id:04d}"
    _next_id += 1

    record = {
        "id": strategy_id,
        "name": strategy.name,
        "description": strategy.description,
        "conditions": conditions_dicts,
        "action": strategy.action,
        "stop_loss_pct": strategy.stop_loss_pct,
        "take_profit_pct": strategy.take_profit_pct,
        "position_size_pct": strategy.position_size_pct,
        "timeframe": strategy.timeframe,
        "diagnostics": report.to_dict(),
        "created_at": datetime.now().isoformat(),
    }
    _strategies[strategy_id] = record

    logger.info("strategy_created", id=strategy_id, name=strategy.name, score=report.score)
    return StrategyResponse(
        id=strategy_id,
        name=strategy.name,
        conditions=conditions_dicts,
        diagnostics=report.to_dict(),
        created_at=record["created_at"],
    )


@router.get("/list")
async def list_strategies():
    return {"strategies": list(_strategies.values())}


@router.get("/{strategy_id}")
async def get_strategy(strategy_id: str):
    if strategy_id not in _strategies:
        raise HTTPException(404, f"Strategy {strategy_id} not found")
    return _strategies[strategy_id]


@router.delete("/{strategy_id}")
async def delete_strategy(strategy_id: str):
    if strategy_id not in _strategies:
        raise HTTPException(404, f"Strategy {strategy_id} not found")
    del _strategies[strategy_id]
    return {"deleted": strategy_id}


@router.post("/diagnose")
async def diagnose_strategy(req: DiagnoseRequest):
    from services.diagnostics import StrategyDiagnostics

    conditions = [c.model_dump() for c in req.conditions]
    report = StrategyDiagnostics.run_all(conditions, req.parameters)
    return report.to_dict()


@router.post("/compute-indicator")
async def compute_indicator(req: ComputeRequest):
    import pandas as pd
    import numpy as np
    from services.indicator_engine import IndicatorEngine

    # Generate sample data for computation preview
    np.random.seed(42)
    n = req.bars
    dates = pd.date_range(end="2026-02-27", periods=n, freq="B")
    close = 100 * np.exp(np.cumsum(np.random.randn(n) * 0.01))
    high = close * (1 + np.abs(np.random.randn(n) * 0.005))
    low = close * (1 - np.abs(np.random.randn(n) * 0.005))
    volume = np.random.randint(1_000_000, 50_000_000, n).astype(float)

    df = pd.DataFrame({
        "timestamp": dates,
        "open": close * (1 + np.random.randn(n) * 0.002),
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    })

    result = IndicatorEngine.compute(req.indicator, df, req.params)

    # Serialize result
    if isinstance(result, pd.Series):
        values = result.tail(50).tolist()
        return {"indicator": req.indicator, "params": req.params, "values": values}
    elif isinstance(result, dict):
        serialized = {}
        for k, v in result.items():
            if isinstance(v, pd.Series):
                serialized[k] = v.tail(50).tolist()
            else:
                serialized[k] = v
        return {"indicator": req.indicator, "params": req.params, "components": serialized}
    return {"indicator": req.indicator, "params": req.params, "value": str(result)}
