"""
Strategy Intelligence API routes.
Handles strategy CRUD with DB persistence, indicator computation, diagnostics, and backtesting.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Any, Optional, Union
import structlog

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
    conditions: list[ConditionSchema]
    action: str = "BUY"
    stop_loss_pct: float = 0.02
    take_profit_pct: float = 0.05
    position_size_pct: float = 0.1
    timeframe: str = "1D"

class StrategyUpdateSchema(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    conditions: Optional[list[ConditionSchema]] = None
    action: Optional[str] = None
    stop_loss_pct: Optional[float] = None
    take_profit_pct: Optional[float] = None
    position_size_pct: Optional[float] = None
    timeframe: Optional[str] = None

class StrategyResponse(BaseModel):
    id: int
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

class BacktestRequest(BaseModel):
    strategy_id: Optional[int] = None
    conditions: Optional[list[ConditionSchema]] = None
    symbol: str = "SPY"
    lookback_days: int = 252
    initial_capital: float = 100_000.0


# ── Helpers ───────────────────────────────────────────────────────────────

def _strategy_to_dict(s) -> dict:
    return {
        "id": s.id,
        "name": s.name,
        "description": s.description or "",
        "conditions": s.conditions or [],
        "action": s.action,
        "stop_loss_pct": s.stop_loss_pct,
        "take_profit_pct": s.take_profit_pct,
        "position_size_pct": s.position_size_pct,
        "timeframe": s.timeframe,
        "diagnostics": s.diagnostics or {},
        "created_at": s.created_at.isoformat() if s.created_at else "",
        "updated_at": s.updated_at.isoformat() if s.updated_at else "",
    }


# ── Routes ───────────────────────────────────────────────────────────────

@router.post("/create", response_model=StrategyResponse)
async def create_strategy(strategy: StrategySchema):
    from services.diagnostics import StrategyDiagnostics
    from db.database import get_session
    from db.models import Strategy

    conditions_dicts = [c.model_dump() for c in strategy.conditions]
    params = {}
    for c in strategy.conditions:
        params[c.indicator] = c.params

    report = StrategyDiagnostics.run_all(conditions_dicts, params)

    async with get_session() as session:
        db_strategy = Strategy(
            name=strategy.name,
            description=strategy.description,
            conditions=conditions_dicts,
            action=strategy.action,
            stop_loss_pct=strategy.stop_loss_pct,
            take_profit_pct=strategy.take_profit_pct,
            position_size_pct=strategy.position_size_pct,
            timeframe=strategy.timeframe,
            diagnostics=report.to_dict(),
        )
        session.add(db_strategy)
        await session.flush()

        logger.info("strategy_created", id=db_strategy.id, name=strategy.name, score=report.score)
        return StrategyResponse(
            id=db_strategy.id,
            name=strategy.name,
            conditions=conditions_dicts,
            diagnostics=report.to_dict(),
            created_at=db_strategy.created_at.isoformat() if db_strategy.created_at else "",
        )


@router.get("/list")
async def list_strategies():
    from sqlalchemy import select
    from db.database import get_session
    from db.models import Strategy

    async with get_session() as session:
        result = await session.execute(
            select(Strategy).order_by(Strategy.created_at.desc())
        )
        strategies = result.scalars().all()
        return {"strategies": [_strategy_to_dict(s) for s in strategies]}


@router.get("/{strategy_id}")
async def get_strategy(strategy_id: int):
    from db.database import get_session
    from db.models import Strategy

    async with get_session() as session:
        s = await session.get(Strategy, strategy_id)
        if not s:
            raise HTTPException(404, f"Strategy {strategy_id} not found")
        return _strategy_to_dict(s)


@router.patch("/{strategy_id}")
async def update_strategy(strategy_id: int, update: StrategyUpdateSchema):
    from services.diagnostics import StrategyDiagnostics
    from db.database import get_session
    from db.models import Strategy

    async with get_session() as session:
        s = await session.get(Strategy, strategy_id)
        if not s:
            raise HTTPException(404, f"Strategy {strategy_id} not found")

        update_data = update.model_dump(exclude_unset=True)
        conditions_changed = False

        for field, value in update_data.items():
            if field == "conditions":
                value = [c.model_dump() if hasattr(c, "model_dump") else c for c in value]
                conditions_changed = True
            setattr(s, field, value)

        # Re-run diagnostics if conditions changed
        if conditions_changed:
            conditions_dicts = s.conditions
            params = {}
            for c in conditions_dicts:
                params[c["indicator"]] = c.get("params", {})
            report = StrategyDiagnostics.run_all(conditions_dicts, params)
            s.diagnostics = report.to_dict()

        await session.flush()
        logger.info("strategy_updated", id=strategy_id)
        return _strategy_to_dict(s)


@router.delete("/{strategy_id}")
async def delete_strategy(strategy_id: int):
    from db.database import get_session
    from db.models import Strategy

    async with get_session() as session:
        s = await session.get(Strategy, strategy_id)
        if not s:
            raise HTTPException(404, f"Strategy {strategy_id} not found")
        await session.delete(s)
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


@router.post("/backtest")
async def run_backtest(req: BacktestRequest):
    import pandas as pd
    import numpy as np
    from services.indicator_engine import IndicatorEngine

    # Load conditions from DB or inline
    if req.strategy_id is not None:
        from db.database import get_session
        from db.models import Strategy

        async with get_session() as session:
            s = await session.get(Strategy, req.strategy_id)
            if not s:
                raise HTTPException(404, f"Strategy {req.strategy_id} not found")
            conditions = s.conditions
            stop_loss_pct = s.stop_loss_pct
            take_profit_pct = s.take_profit_pct
    elif req.conditions:
        conditions = [c.model_dump() for c in req.conditions]
        stop_loss_pct = 0.02
        take_profit_pct = 0.05
    else:
        raise HTTPException(400, "Provide strategy_id or inline conditions")

    # Generate synthetic OHLCV data
    np.random.seed(123)
    n = req.lookback_days
    dates = pd.date_range(end="2026-02-27", periods=n, freq="B")
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

    # Evaluate conditions per bar to build signal series
    n_bars = len(df)
    signals = np.zeros(n_bars)  # 1 = entry signal

    for i in range(n_bars):
        all_met = True
        for cond in conditions:
            ind_name = cond["indicator"]
            op = cond["operator"]
            val = cond["value"]
            result = indicator_cache[ind_name]

            # Get indicator value at bar i
            if isinstance(result, pd.Series):
                ind_val = result.iloc[i]
            elif isinstance(result, dict):
                first_key = next(iter(result))
                series = result[first_key]
                ind_val = series.iloc[i] if isinstance(series, pd.Series) else np.nan
            else:
                ind_val = np.nan

            if pd.isna(ind_val):
                all_met = False
                break

            # Compare
            threshold = float(val) if not isinstance(val, (int, float)) else val
            if op == ">":
                met = ind_val > threshold
            elif op == "<":
                met = ind_val < threshold
            elif op == ">=":
                met = ind_val >= threshold
            elif op == "<=":
                met = ind_val <= threshold
            elif op == "==":
                met = abs(ind_val - threshold) < 0.001
            elif op in ("crosses_above", "crosses_below"):
                if i == 0:
                    met = False
                else:
                    prev_result = indicator_cache[ind_name]
                    if isinstance(prev_result, pd.Series):
                        prev_val = prev_result.iloc[i - 1]
                    elif isinstance(prev_result, dict):
                        first_key = next(iter(prev_result))
                        s = prev_result[first_key]
                        prev_val = s.iloc[i - 1] if isinstance(s, pd.Series) else np.nan
                    else:
                        prev_val = np.nan
                    if pd.isna(prev_val):
                        met = False
                    elif op == "crosses_above":
                        met = prev_val <= threshold and ind_val > threshold
                    else:
                        met = prev_val >= threshold and ind_val < threshold
            else:
                met = False

            if not met:
                all_met = False
                break

        if all_met:
            signals[i] = 1

    # Simulate trades with stop-loss/take-profit
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
                pnl = capital * (exit_price / entry_price - 1)
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
                pnl = capital * (exit_price / entry_price - 1)
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
        pnl = capital * (final_price / entry_price - 1)
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
        equity[-1] = capital + pnl

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

    return {
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
        "trades": trades,
    }
