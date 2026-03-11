"""
Strategy Intelligence API routes.
Handles strategy CRUD with DB persistence (StrategyTemplate + StrategyInstance),
indicator computation, diagnostics, and backtesting.
All strategy queries are scoped to the user's active trading mode.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Any, Optional, Union
import structlog

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from db.database import get_session
from db.models import (
    StrategyTemplate,
    StrategyInstance,
    Strategy,
    TradingModeEnum,
    SystemEventType,
)
from services.event_logger import log_event

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/strategies", tags=["strategies"])


# ── Request/Response Models ──────────────────────────────────────────────

class ConditionSchema(BaseModel):
    indicator: str
    operator: str = ">"
    value: Union[float, str] = 0
    compare_to: Optional[str] = None  # e.g., "close", "ema_200"
    params: dict[str, Any] = Field(default_factory=dict)
    action: str = "BUY"

class StrategySchema(BaseModel):
    name: str
    description: str = ""
    conditions: list[ConditionSchema] = Field(default_factory=list)
    condition_groups: list[dict] = Field(default_factory=list)
    action: str = "BUY"
    stop_loss_pct: float = 0.02
    take_profit_pct: float = 0.05
    position_size_pct: float = 0.1
    timeframe: str = "1D"
    symbols: list[str] = Field(default_factory=lambda: ["SPY"])
    commission_pct: float = 0.001
    slippage_pct: float = 0.0005
    trailing_stop_pct: Optional[float] = None
    exit_after_bars: Optional[int] = None
    cooldown_bars: int = 0
    max_trades_per_day: int = 0
    max_exposure_pct: float = 1.0
    max_loss_pct: float = 0.0
    strategy_type: str = "manual"
    source_prompt: Optional[str] = None
    ai_context: dict[str, Any] = Field(default_factory=dict)

class StrategyUpdateSchema(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    conditions: Optional[list[ConditionSchema]] = None
    condition_groups: Optional[list[dict]] = None
    action: Optional[str] = None
    stop_loss_pct: Optional[float] = None
    take_profit_pct: Optional[float] = None
    position_size_pct: Optional[float] = None
    timeframe: Optional[str] = None
    nickname: Optional[str] = None
    max_position_value: Optional[float] = None
    symbols: Optional[list[str]] = None
    commission_pct: Optional[float] = None
    slippage_pct: Optional[float] = None
    trailing_stop_pct: Optional[float] = None
    exit_after_bars: Optional[int] = None
    cooldown_bars: Optional[int] = None
    max_trades_per_day: Optional[int] = None
    max_exposure_pct: Optional[float] = None
    max_loss_pct: Optional[float] = None
    strategy_type: Optional[str] = None
    source_prompt: Optional[str] = None
    ai_context: Optional[dict[str, Any]] = None

class StrategyResponse(BaseModel):
    id: int
    name: str
    conditions: list[dict]
    diagnostics: dict
    created_at: str

class PromoteRequest(BaseModel):
    position_size_pct: Optional[float] = None
    max_position_value: Optional[float] = None
    nickname: Optional[str] = None

class ComputeRequest(BaseModel):
    indicator: str
    params: dict[str, Any] = Field(default_factory=dict)
    symbol: str = "SPY"
    bars: int = 200

class DiagnoseRequest(BaseModel):
    conditions: list[ConditionSchema]
    parameters: dict[str, dict[str, Any]] = Field(default_factory=dict)

class BacktestRequest(BaseModel):
    strategy_id: Optional[int] = None
    conditions: Optional[list[ConditionSchema]] = None
    condition_groups: Optional[list[dict]] = None
    symbol: str = "SPY"
    lookback_days: int = 252
    initial_capital: float = 100_000.0
    commission_pct: float = 0.001
    slippage_pct: float = 0.0005


# ── Helpers ───────────────────────────────────────────────────────────────

def _instance_to_dict(inst: StrategyInstance) -> dict:
    """Serialize a StrategyInstance joined with its template."""
    t = inst.template
    return {
        "id": inst.id,
        "template_id": t.id,
        "name": t.name,
        "description": t.description or "",
        "conditions": t.conditions or [],
        "condition_groups": t.condition_groups or [],
        "action": t.action,
        "stop_loss_pct": t.stop_loss_pct,
        "take_profit_pct": t.take_profit_pct,
        "position_size_pct": inst.position_size_pct,
        "max_position_value": inst.max_position_value,
        "timeframe": t.timeframe,
        "diagnostics": t.diagnostics or {},
        "mode": inst.mode.value if hasattr(inst.mode, "value") else str(inst.mode),
        "is_active": inst.is_active,
        "nickname": inst.nickname,
        "promoted_from_id": inst.promoted_from_id,
        "created_at": t.created_at.isoformat() if t.created_at else "",
        "updated_at": t.updated_at.isoformat() if t.updated_at else "",
        "symbols": t.symbols or ["SPY"],
        "commission_pct": t.commission_pct or 0.001,
        "slippage_pct": t.slippage_pct or 0.0005,
        "trailing_stop_pct": t.trailing_stop_pct,
        "exit_after_bars": t.exit_after_bars,
        "cooldown_bars": t.cooldown_bars or 0,
        "max_trades_per_day": t.max_trades_per_day or 0,
        "max_exposure_pct": t.max_exposure_pct or 1.0,
        "max_loss_pct": t.max_loss_pct or 0.0,
        "strategy_type": t.strategy_type or "manual",
        "source_prompt": t.source_prompt,
        "ai_context": t.ai_context or {},
    }


def _strategy_to_dict(s) -> dict:
    """Legacy helper for old Strategy model (backward compat)."""
    return {
        "id": s.id,
        "name": s.name,
        "description": s.description or "",
        "conditions": s.conditions or [],
        "condition_groups": s.condition_groups or [],
        "action": s.action,
        "stop_loss_pct": s.stop_loss_pct,
        "take_profit_pct": s.take_profit_pct,
        "position_size_pct": s.position_size_pct,
        "timeframe": s.timeframe,
        "diagnostics": s.diagnostics or {},
        "created_at": s.created_at.isoformat() if s.created_at else "",
        "updated_at": s.updated_at.isoformat() if s.updated_at else "",
        "symbols": s.symbols or ["SPY"],
        "commission_pct": s.commission_pct or 0.001,
        "slippage_pct": s.slippage_pct or 0.0005,
        "trailing_stop_pct": s.trailing_stop_pct,
        "exit_after_bars": s.exit_after_bars,
        "cooldown_bars": s.cooldown_bars or 0,
        "max_trades_per_day": s.max_trades_per_day or 0,
        "max_exposure_pct": s.max_exposure_pct or 1.0,
        "max_loss_pct": s.max_loss_pct or 0.0,
        "strategy_type": s.strategy_type or "manual",
        "source_prompt": s.source_prompt,
        "ai_context": s.ai_context or {},
    }


# ── Routes ───────────────────────────────────────────────────────────────

@router.post("/create", response_model=StrategyResponse)
async def create_strategy(strategy: StrategySchema, request: Request):
    """Create a new strategy template + instance for the current mode."""
    from services.diagnostics import StrategyDiagnostics

    user_id = request.state.user_id
    mode = request.state.trading_mode

    conditions_dicts = [c.model_dump() for c in strategy.conditions]
    # Flatten condition_groups to conditions for diagnostics when groups present
    if strategy.condition_groups:
        flat = [c for g in strategy.condition_groups for c in g.get("conditions", [])]
        conditions_dicts = flat
    params = {}
    for c in conditions_dicts:
        ind = c["indicator"] if isinstance(c, dict) else c.indicator
        p = c.get("params", {}) if isinstance(c, dict) else c.params
        params[ind] = p

    report = StrategyDiagnostics.run_all(conditions_dicts, params)

    async with get_session() as session:
        # Create the template (logic)
        template = StrategyTemplate(
            user_id=user_id,
            name=strategy.name,
            description=strategy.description,
            conditions=conditions_dicts,
            condition_groups=strategy.condition_groups or [],
            action=strategy.action,
            stop_loss_pct=strategy.stop_loss_pct,
            take_profit_pct=strategy.take_profit_pct,
            timeframe=strategy.timeframe,
            diagnostics=report.to_dict(),
            symbols=strategy.symbols,
            commission_pct=strategy.commission_pct,
            slippage_pct=strategy.slippage_pct,
            trailing_stop_pct=strategy.trailing_stop_pct,
            exit_after_bars=strategy.exit_after_bars,
            cooldown_bars=strategy.cooldown_bars,
            max_trades_per_day=strategy.max_trades_per_day,
            max_exposure_pct=strategy.max_exposure_pct,
            max_loss_pct=strategy.max_loss_pct,
            strategy_type=strategy.strategy_type,
            source_prompt=strategy.source_prompt,
            ai_context=strategy.ai_context,
        )
        session.add(template)
        await session.flush()

        # Create the instance (sizing, mode-specific)
        instance = StrategyInstance(
            template_id=template.id,
            user_id=user_id,
            mode=mode,
            is_active=True,
            position_size_pct=strategy.position_size_pct,
        )
        session.add(instance)
        await session.flush()

        logger.info(
            "strategy_created",
            template_id=template.id,
            instance_id=instance.id,
            name=strategy.name,
            mode=mode.value,
            score=report.score,
        )
        return StrategyResponse(
            id=instance.id,
            name=strategy.name,
            conditions=conditions_dicts,
            diagnostics=report.to_dict(),
            created_at=template.created_at.isoformat() if template.created_at else "",
        )


@router.get("/list")
async def list_strategies(request: Request):
    """List strategy instances for the current user and mode."""
    user_id = request.state.user_id
    mode = request.state.trading_mode

    async with get_session() as session:
        result = await session.execute(
            select(StrategyInstance)
            .options(selectinload(StrategyInstance.template))
            .where(
                StrategyInstance.user_id == user_id,
                StrategyInstance.mode == mode,
                StrategyInstance.is_active == True,  # noqa: E712
            )
            .order_by(StrategyInstance.created_at.desc())
        )
        instances = result.scalars().all()
        strategies = [_instance_to_dict(inst) for inst in instances]

    return {"strategies": strategies, "mode": mode.value}


@router.get("/{instance_id}")
async def get_strategy(instance_id: int, request: Request):
    """Get a single strategy instance by ID — scoped to user."""
    user_id = request.state.user_id

    async with get_session() as session:
        result = await session.execute(
            select(StrategyInstance)
            .options(selectinload(StrategyInstance.template))
            .where(
                StrategyInstance.id == instance_id,
                StrategyInstance.user_id == user_id,
            )
        )
        inst = result.scalar_one_or_none()
        if not inst:
            raise HTTPException(404, f"Strategy instance {instance_id} not found")
        return _instance_to_dict(inst)


@router.patch("/{instance_id}")
async def update_strategy(instance_id: int, update: StrategyUpdateSchema, request: Request):
    """Update a strategy template (logic) and/or instance (sizing)."""
    from services.diagnostics import StrategyDiagnostics

    user_id = request.state.user_id

    async with get_session() as session:
        result = await session.execute(
            select(StrategyInstance)
            .options(selectinload(StrategyInstance.template))
            .where(
                StrategyInstance.id == instance_id,
                StrategyInstance.user_id == user_id,
            )
        )
        inst = result.scalar_one_or_none()
        if not inst:
            raise HTTPException(404, f"Strategy instance {instance_id} not found")

        template = inst.template
        update_data = update.model_dump(exclude_unset=True)
        conditions_changed = False

        # Template-level fields
        template_fields = {
            "name", "description", "conditions", "condition_groups", "action",
            "stop_loss_pct", "take_profit_pct", "timeframe",
            "symbols", "commission_pct", "slippage_pct",
            "trailing_stop_pct", "exit_after_bars",
            "cooldown_bars", "max_trades_per_day", "max_exposure_pct", "max_loss_pct",
            "strategy_type", "source_prompt", "ai_context",
        }
        # Instance-level fields
        instance_fields = {"position_size_pct", "nickname", "max_position_value"}

        for field, value in update_data.items():
            if field in template_fields:
                if field == "conditions":
                    value = [c.model_dump() if hasattr(c, "model_dump") else c for c in value]
                    conditions_changed = True
                elif field == "condition_groups":
                    # Flatten groups → conditions for diagnostics re-run
                    flat = [c for g in value for c in g.get("conditions", [])]
                    template.conditions = flat
                    conditions_changed = True
                setattr(template, field, value)
            elif field in instance_fields:
                setattr(inst, field, value)

        # Re-run diagnostics if conditions changed
        if conditions_changed:
            conditions_dicts = template.conditions
            params = {}
            for c in conditions_dicts:
                params[c["indicator"]] = c.get("params", {})
            report = StrategyDiagnostics.run_all(conditions_dicts, params)
            template.diagnostics = report.to_dict()

        await session.flush()
        logger.info("strategy_updated", instance_id=instance_id)
        return _instance_to_dict(inst)


@router.delete("/{instance_id}")
async def delete_strategy(instance_id: int, request: Request):
    """Deactivate a strategy instance (soft delete)."""
    user_id = request.state.user_id

    async with get_session() as session:
        result = await session.execute(
            select(StrategyInstance).where(
                StrategyInstance.id == instance_id,
                StrategyInstance.user_id == user_id,
            )
        )
        inst = result.scalar_one_or_none()
        if not inst:
            raise HTTPException(404, f"Strategy instance {instance_id} not found")
        inst.is_active = False
        await session.flush()

    return {"deactivated": instance_id}


@router.post("/{instance_id}/promote")
async def promote_strategy(instance_id: int, req: PromoteRequest, request: Request):
    """Promote a paper strategy instance to live."""
    user_id = request.state.user_id
    mode = request.state.trading_mode

    if mode != TradingModeEnum.PAPER:
        raise HTTPException(400, "Can only promote from paper mode")

    async with get_session() as db:
        result = await db.execute(
            select(StrategyInstance).where(
                StrategyInstance.id == instance_id,
                StrategyInstance.user_id == user_id,
                StrategyInstance.mode == TradingModeEnum.PAPER,
            )
        )
        paper_inst = result.scalar_one_or_none()
        if not paper_inst:
            raise HTTPException(404, "Paper strategy instance not found")

        live_inst = StrategyInstance(
            template_id=paper_inst.template_id,
            user_id=user_id,
            mode=TradingModeEnum.LIVE,
            is_active=True,
            position_size_pct=req.position_size_pct or paper_inst.position_size_pct,
            max_position_value=req.max_position_value,
            nickname=req.nickname,
            promoted_from_id=paper_inst.id,
        )
        db.add(live_inst)
        await db.flush()
        new_id = live_inst.id

    await log_event(
        user_id=user_id,
        event_type=SystemEventType.STRATEGY_PROMOTED,
        mode=TradingModeEnum.LIVE,
        description=f"Promoted instance {instance_id} to live",
    )

    return {"id": new_id, "mode": "live", "promoted_from": instance_id}


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

    # Generate synthetic OHLCV for indicator shape preview only.
    # This is NOT real market data — results show indicator behavior, not a real signal.
    np.random.seed(42)
    n = req.bars
    end_date = pd.Timestamp.utcnow().normalize()
    dates = pd.date_range(end=end_date, periods=n, freq="B")
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
        return {"indicator": req.indicator, "params": req.params, "values": values, "synthetic_data": True}
    elif isinstance(result, dict):
        serialized = {}
        for k, v in result.items():
            if isinstance(v, pd.Series):
                serialized[k] = v.tail(50).tolist()
            else:
                serialized[k] = v
        return {"indicator": req.indicator, "params": req.params, "components": serialized, "synthetic_data": True}
    return {"indicator": req.indicator, "params": req.params, "value": str(result), "synthetic_data": True}


@router.post("/backtest")
async def run_backtest(req: BacktestRequest, request: Request = None):
    import pandas as pd
    import numpy as np
    from services.indicator_engine import IndicatorEngine

    # Load conditions from DB or inline
    commission_pct = req.commission_pct
    slippage_pct = req.slippage_pct
    if req.strategy_id is not None:
        user_id = getattr(request.state, "user_id", None) if request else None
        async with get_session() as session:
            # Try StrategyInstance first (new model)
            if user_id:
                inst_result = await session.execute(
                    select(StrategyInstance).where(
                        StrategyInstance.id == req.strategy_id,
                        StrategyInstance.user_id == user_id,
                    )
                )
                inst = inst_result.scalar_one_or_none()
                if inst:
                    t = inst.template
                    if t.condition_groups:
                        groups = t.condition_groups
                        conditions = [c for g in groups for c in g.get("conditions", [])]
                    else:
                        groups = [{"conditions": t.conditions or []}]
                        conditions = t.conditions or []
                    stop_loss_pct = t.stop_loss_pct
                    take_profit_pct = t.take_profit_pct
                else:
                    # Fall back to legacy Strategy table
                    s = await session.get(Strategy, req.strategy_id)
                    if not s:
                        raise HTTPException(404, f"Strategy {req.strategy_id} not found")
                    if s.condition_groups:
                        groups = s.condition_groups
                        conditions = [c for g in groups for c in g.get("conditions", [])]
                    else:
                        groups = [{"conditions": s.conditions or []}]
                        conditions = s.conditions or []
                    stop_loss_pct = s.stop_loss_pct
                    take_profit_pct = s.take_profit_pct
                    commission_pct = s.commission_pct or req.commission_pct
                    slippage_pct = s.slippage_pct or req.slippage_pct
            else:
                s = await session.get(Strategy, req.strategy_id)
                if not s:
                    raise HTTPException(404, f"Strategy {req.strategy_id} not found")
                if s.condition_groups:
                    groups = s.condition_groups
                    conditions = [c for g in groups for c in g.get("conditions", [])]
                else:
                    groups = [{"conditions": s.conditions or []}]
                    conditions = s.conditions or []
                stop_loss_pct = s.stop_loss_pct
                take_profit_pct = s.take_profit_pct
    elif req.condition_groups:
        groups = req.condition_groups
        conditions = [c for g in groups for c in g.get("conditions", [])]
        stop_loss_pct = 0.02
        take_profit_pct = 0.05
    elif req.conditions:
        conditions = [c.model_dump() for c in req.conditions]
        groups = [{"conditions": conditions}]
        stop_loss_pct = 0.02
        take_profit_pct = 0.05
    else:
        raise HTTPException(400, "Provide strategy_id or inline conditions")

    # NOTE: synthetic OHLCV — real market data integration not yet wired.
    # All metrics below are computed on a random walk, NOT on historical prices.
    # Do not use these results for live trading decisions.
    np.random.seed(123)
    n = req.lookback_days
    end_date = pd.Timestamp.utcnow().normalize()
    dates = pd.date_range(end=end_date, periods=n, freq="B")
    returns = np.random.randn(n) * 0.012
    close = 100 * np.exp(np.cumsum(returns))
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

    # Pre-compute all indicators
    indicator_cache: dict[str, Any] = {}
    for cond in conditions:
        ind_name = cond["indicator"]
        if ind_name not in indicator_cache:
            indicator_cache[ind_name] = IndicatorEngine.compute(ind_name, df, cond.get("params", {}))

    # Evaluate conditions per bar — AND within group, OR between groups
    n_bars = len(df)
    signals = np.zeros(n_bars)

    def _eval_cond(cond: dict, i: int) -> bool:
        ind_name = cond["indicator"]
        op = cond["operator"]
        val = cond["value"]
        result = indicator_cache.get(ind_name)
        if result is None:
            return False
        if isinstance(result, pd.Series):
            ind_val = result.iloc[i]
        elif isinstance(result, dict):
            first_key = next(iter(result))
            series = result[first_key]
            ind_val = series.iloc[i] if isinstance(series, pd.Series) else np.nan
        else:
            ind_val = np.nan
        if pd.isna(ind_val):
            return False
        threshold = float(val) if not isinstance(val, (int, float)) else val
        if op == ">":
            return ind_val > threshold
        elif op == "<":
            return ind_val < threshold
        elif op == ">=":
            return ind_val >= threshold
        elif op == "<=":
            return ind_val <= threshold
        elif op == "==":
            return abs(ind_val - threshold) < 0.001
        elif op in ("crosses_above", "crosses_below"):
            if i == 0:
                return False
            prev_result = indicator_cache[ind_name]
            if isinstance(prev_result, pd.Series):
                prev_val = prev_result.iloc[i - 1]
            elif isinstance(prev_result, dict):
                fk = next(iter(prev_result))
                sv = prev_result[fk]
                prev_val = sv.iloc[i - 1] if isinstance(sv, pd.Series) else np.nan
            else:
                prev_val = np.nan
            if pd.isna(prev_val):
                return False
            if op == "crosses_above":
                return prev_val <= threshold and ind_val > threshold
            else:
                return prev_val >= threshold and ind_val < threshold
        return False

    for i in range(n_bars):
        for g in groups:
            group_conds = g.get("conditions", [])
            if group_conds and all(_eval_cond(c, i) for c in group_conds):
                signals[i] = 1
                break

    # Simulate trades with stop-loss/take-profit and friction costs
    friction = (commission_pct + slippage_pct) * 2  # round-trip: entry + exit
    trades = []
    equity = [req.initial_capital]
    capital = req.initial_capital
    in_position = False
    entry_price = 0.0
    entry_idx = 0

    for i in range(n_bars):
        price = close[i]

        if in_position:
            pnl_pct = (price - entry_price) / entry_price
            # Check stop-loss
            if pnl_pct <= -stop_loss_pct:
                exit_price = entry_price * (1 - stop_loss_pct)
                pnl = capital * (exit_price / entry_price - 1) - capital * friction
                capital += pnl
                trades.append({
                    "entry_date": dates[entry_idx].strftime("%Y-%m-%d"),
                    "exit_date": dates[i].strftime("%Y-%m-%d"),
                    "direction": "LONG",
                    "entry_price": round(entry_price, 2),
                    "exit_price": round(exit_price, 2),
                    "pnl": round(pnl, 2),
                    "pnl_pct": round(-stop_loss_pct * 100, 2),
                    "bars_held": i - entry_idx,
                })
                in_position = False
            # Check take-profit
            elif pnl_pct >= take_profit_pct:
                exit_price = entry_price * (1 + take_profit_pct)
                pnl = capital * (exit_price / entry_price - 1) - capital * friction
                capital += pnl
                trades.append({
                    "entry_date": dates[entry_idx].strftime("%Y-%m-%d"),
                    "exit_date": dates[i].strftime("%Y-%m-%d"),
                    "direction": "LONG",
                    "entry_price": round(entry_price, 2),
                    "exit_price": round(exit_price, 2),
                    "pnl": round(pnl, 2),
                    "pnl_pct": round(take_profit_pct * 100, 2),
                    "bars_held": i - entry_idx,
                })
                in_position = False

        if not in_position and signals[i] == 1:
            entry_price = price
            entry_idx = i
            in_position = True

        equity.append(capital if not in_position else capital * (price / entry_price))

    # Close any open position at end
    if in_position:
        final_price = close[-1]
        pnl = capital * (final_price / entry_price - 1) - capital * friction
        capital += pnl
        trades.append({
            "entry_date": dates[entry_idx].strftime("%Y-%m-%d"),
            "exit_date": dates[-1].strftime("%Y-%m-%d"),
            "direction": "LONG",
            "entry_price": round(entry_price, 2),
            "exit_price": round(final_price, 2),
            "pnl": round(pnl, 2),
            "pnl_pct": round((final_price / entry_price - 1) * 100, 2),
            "bars_held": n_bars - 1 - entry_idx,
        })
        equity[-1] = capital

    # Buy-and-hold benchmark
    bh_start = close[0]
    benchmark_equity = [req.initial_capital * (close[i] / bh_start) for i in range(n_bars)]

    # Compute metrics
    equity_arr = np.array(equity[1:])  # skip initial
    daily_returns = np.diff(equity_arr) / equity_arr[:-1] if len(equity_arr) > 1 else np.array([0.0])
    daily_returns = daily_returns[~np.isnan(daily_returns)]

    total_return = (equity_arr[-1] / req.initial_capital - 1) if len(equity_arr) > 0 else 0.0
    sharpe = (np.mean(daily_returns) / np.std(daily_returns) * np.sqrt(252)) if np.std(daily_returns) > 0 else 0.0
    downside = daily_returns[daily_returns < 0]
    sortino = (np.mean(daily_returns) / np.std(downside) * np.sqrt(252)) if len(downside) > 0 and np.std(downside) > 0 else 0.0

    wins = [t for t in trades if t["pnl"] > 0]
    win_rate = len(wins) / len(trades) if trades else 0.0

    # Max drawdown
    peak = np.maximum.accumulate(equity_arr)
    dd = (equity_arr - peak) / peak
    max_drawdown = abs(float(np.min(dd))) if len(dd) > 0 else 0.0

    avg_pnl = np.mean([t["pnl"] for t in trades]) if trades else 0.0
    gross_profit = sum(t["pnl"] for t in trades if t["pnl"] > 0)
    gross_loss = abs(sum(t["pnl"] for t in trades if t["pnl"] < 0))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf") if gross_profit > 0 else 0.0

    # Build equity curve points
    equity_curve = []
    for i in range(min(len(dates), len(equity_arr))):
        equity_curve.append({
            "date": dates[i].strftime("%Y-%m-%d"),
            "value": round(float(equity_arr[i]), 2),
        })

    benchmark_curve = [
        {"date": dates[i].strftime("%Y-%m-%d"), "value": round(float(benchmark_equity[i]), 2)}
        for i in range(min(len(dates), len(benchmark_equity)))
    ]

    return {
        "synthetic_data": True,
        "data_warning": "Backtest ran on synthetic random-walk data, not real historical prices. Results are for logic verification only.",
        "commission_pct": commission_pct,
        "slippage_pct": slippage_pct,
        "metrics": {
            "sharpe_ratio": round(float(sharpe), 3),
            "sortino_ratio": round(float(sortino), 3),
            "win_rate": round(float(win_rate), 3),
            "max_drawdown": round(float(max_drawdown), 4),
            "total_return": round(float(total_return), 4),
            "num_trades": len(trades),
            "avg_trade_pnl": round(float(avg_pnl), 2),
            "profit_factor": round(float(min(profit_factor, 999)), 3),
        },
        "equity_curve": equity_curve,
        "benchmark_equity_curve": benchmark_curve,
        "trades": trades,
    }


# ── Strategy Config Endpoints ────────────────────────────────────────────

class StrategyConfigUpdate(BaseModel):
    """Request body for updating the strategy config."""
    name: Optional[str] = None
    version: Optional[str] = None
    active_strategies: Optional[list[str]] = None
    risk_params: Optional[dict[str, Any]] = None
    execution: Optional[dict[str, Any]] = None
    backtest: Optional[dict[str, Any]] = None


@router.get("/trading/strategy-config")
async def get_strategy_config():
    """Return the current strategy configuration."""
    from trading.strategy_loader import StrategyLoader

    loader = StrategyLoader()
    try:
        config = loader.load_config()
    except FileNotFoundError:
        raise HTTPException(404, "Strategy config file not found")

    valid, errors = loader.validate_config(config)
    return {
        "config": config,
        "valid": valid,
        "errors": errors,
    }


@router.post("/trading/strategy-config")
async def update_strategy_config(update: StrategyConfigUpdate):
    """Update the strategy configuration. Merges provided fields into current config."""
    from trading.strategy_loader import StrategyLoader

    loader = StrategyLoader()

    # Load current config
    try:
        config = loader.load_config()
    except FileNotFoundError:
        config = {}

    # Merge updates
    update_data = update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if isinstance(value, dict) and isinstance(config.get(key), dict):
            config[key].update(value)
        else:
            config[key] = value

    # Validate before saving
    valid, errors = loader.validate_config(config)
    if not valid:
        raise HTTPException(400, {"message": "Invalid config", "errors": errors})

    # Save
    path = loader.save_config(config)
    logger.info("strategy_config_updated", path=path)

    return {
        "config": config,
        "valid": True,
        "saved_to": path,
    }
