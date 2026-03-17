"""
Parameter sweep / optimization using VectorBT broadcasting.

Accepts a strategy template with parameter ranges (e.g., RSI period: 10-30,
SMA period: 20-100) and tests all combinations simultaneously.  Returns a
heatmap-ready matrix of the selected metric across parameter combos.

Maximum combinations capped at 10,000 to prevent memory issues.
"""
from __future__ import annotations

import itertools
import math
from copy import deepcopy
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import structlog

from services.backtesting.data_fetcher import fetch_ohlcv
from services.backtesting.vectorbt_engine import (
    canon,
    freq_from_timeframe,
    safe_float,
    build_entry_signals,
)

logger = structlog.get_logger(__name__)

MAX_COMBINATIONS = 10_000


def run_parameter_sweep(
    conditions: Optional[List[Dict[str, Any]]] = None,
    condition_groups: Optional[List[Dict[str, Any]]] = None,
    parameter_ranges: Optional[Dict[str, Dict[str, Any]]] = None,
    symbol: str = "SPY",
    timeframe: str = "1D",
    lookback_days: int = 252,
    initial_capital: float = 100_000.0,
    commission_pct: float = 0.001,
    slippage_pct: float = 0.0005,
    stop_loss_pct: Optional[float] = None,
    take_profit_pct: Optional[float] = None,
    action: str = "BUY",
    metric: str = "sharpe_ratio",
) -> Dict[str, Any]:
    """
    Run a parameter sweep over the given ranges.

    Returns dict with: heatmap, best_params, best_value, param_axes,
    matrix (if 2 params), total_combinations.
    """
    try:
        import vectorbt as vbt  # noqa: F811
    except ImportError as exc:
        raise RuntimeError("vectorbt is not installed: pip install vectorbt") from exc

    if not parameter_ranges:
        raise ValueError("parameter_ranges is required for a sweep")

    if condition_groups:
        flat_conditions = [c for g in condition_groups for c in g.get("conditions", [])]
    elif conditions:
        flat_conditions = list(conditions)
    else:
        raise ValueError("conditions or condition_groups required")

    # Build axes
    axes: Dict[str, List[Any]] = {}
    for key, spec in parameter_ranges.items():
        lo = spec.get("min", spec.get("low", 1))
        hi = spec.get("max", spec.get("high", 100))
        step = spec.get("step", 1)
        if isinstance(lo, float) or isinstance(hi, float) or isinstance(step, float):
            vals = list(np.arange(float(lo), float(hi) + step / 2, float(step)))
        else:
            vals = list(range(int(lo), int(hi) + 1, int(step)))
        axes[key] = vals

    total_combos = 1
    for vals in axes.values():
        total_combos *= len(vals)
    if total_combos > MAX_COMBINATIONS:
        logger.warning("parameter_sweep_too_large", combos=total_combos, max=MAX_COMBINATIONS)
        axes = _reduce_axes(axes, MAX_COMBINATIONS)
        total_combos = 1
        for vals in axes.values():
            total_combos *= len(vals)

    logger.info("parameter_sweep_start", symbol=symbol, combinations=total_combos, params=list(axes.keys()))

    df = fetch_ohlcv(symbol, timeframe, lookback_days)
    if df.empty or len(df) < 20:
        raise ValueError(f"Insufficient data for {symbol} on {timeframe}")

    close = df["close"]
    is_short = str(action).upper() in {"SELL", "SHORT"}
    fees = commission_pct + slippage_pct

    param_keys = list(axes.keys())
    param_values_list = [axes[k] for k in param_keys]
    all_combos = list(itertools.product(*param_values_list))

    results: List[Dict[str, Any]] = []

    for combo in all_combos:
        combo_dict = dict(zip(param_keys, combo))
        tweaked_conditions = _apply_overrides(flat_conditions, combo_dict)
        tweaked_groups = [{"conditions": tweaked_conditions}]

        sl = combo_dict.get("stop_loss_pct", stop_loss_pct)
        tp = combo_dict.get("take_profit_pct", take_profit_pct)

        try:
            entries = build_entry_signals(df, condition_groups=tweaked_groups)
            exits = pd.Series(False, index=df.index)

            sl_val = float(sl) if sl and float(sl) > 0 else None
            tp_val = float(tp) if tp and float(tp) > 0 else None

            if is_short:
                pf = vbt.Portfolio.from_signals(
                    close=close, short_entries=entries, short_exits=exits,
                    init_cash=initial_capital, fees=fees,
                    sl_stop=sl_val, tp_stop=tp_val,
                    freq=freq_from_timeframe(timeframe),
                )
            else:
                pf = vbt.Portfolio.from_signals(
                    close=close, entries=entries, exits=exits,
                    init_cash=initial_capital, fees=fees,
                    sl_stop=sl_val, tp_stop=tp_val,
                    freq=freq_from_timeframe(timeframe),
                )

            metric_val = _extract_metric(pf, metric)
        except Exception as exc:
            logger.debug("sweep_combo_failed", combo=combo_dict, error=str(exc))
            metric_val = float("nan")

        results.append({
            "params": combo_dict,
            "value": round(safe_float(metric_val), 6),
        })

    valid_results = [r for r in results if not math.isnan(r["value"])]
    if metric == "max_drawdown":
        best = min(valid_results, key=lambda r: r["value"]) if valid_results else results[0]
    else:
        best = max(valid_results, key=lambda r: r["value"]) if valid_results else results[0]

    matrix: Optional[List[List[float]]] = None
    if len(param_keys) == 2:
        k0, k1 = param_keys
        v0, v1 = axes[k0], axes[k1]
        lookup = {(r["params"][k0], r["params"][k1]): r["value"] for r in results}
        matrix = []
        for a in v0:
            row = [lookup.get((a, b), float("nan")) for b in v1]
            matrix.append(row)

    logger.info("parameter_sweep_complete", combinations=total_combos, best_params=best["params"], best_value=best["value"])

    return {
        "heatmap": results,
        "best_params": best["params"],
        "best_value": best["value"],
        "param_axes": {k: [_jsonify(v) for v in vals] for k, vals in axes.items()},
        "matrix": matrix,
        "total_combinations": total_combos,
        "metric": metric,
        "symbol": symbol.upper(),
        "timeframe": timeframe,
    }


def _apply_overrides(
    conditions: List[Dict[str, Any]],
    overrides: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Apply parameter overrides to a conditions list."""
    result = deepcopy(conditions)
    for key, val in overrides.items():
        if key in {"stop_loss_pct", "take_profit_pct"}:
            continue
        parts = key.rsplit("_", 1)
        if len(parts) != 2:
            logger.warning("sweep_unrecognized_param_key", key=key)
            continue
        indicator_part, param_type = parts
        indicator_canon = canon(indicator_part)

        for cond in result:
            if canon(cond.get("indicator", "")) == indicator_canon:
                if param_type == "period":
                    cond.setdefault("params", {})["period"] = int(val)
                elif param_type == "value":
                    cond["value"] = float(val)
    return result


def _extract_metric(pf: Any, metric: str) -> float:
    """Extract a metric value from a VectorBT Portfolio object."""
    if metric == "sharpe_ratio":
        return float(pf.sharpe_ratio())
    elif metric == "sortino_ratio":
        return float(pf.sortino_ratio())
    elif metric == "total_return":
        return float(pf.total_return())
    elif metric == "win_rate":
        try:
            trades = pf.trades.records_readable
            if len(trades) == 0:
                return 0.0
            wins = len(trades[trades.get("PnL", trades.get("Return", pd.Series())) > 0])
            return wins / len(trades)
        except Exception:
            return 0.0
    elif metric == "profit_factor":
        try:
            trades = pf.trades.records_readable
            if len(trades) == 0:
                return 0.0
            pnl = trades.get("PnL", pd.Series([0]))
            gross_profit = float(pnl[pnl > 0].sum())
            gross_loss = abs(float(pnl[pnl < 0].sum()))
            return gross_profit / gross_loss if gross_loss > 0 else 0.0
        except Exception:
            return 0.0
    elif metric == "calmar_ratio":
        tr = safe_float(pf.total_return())
        md = abs(safe_float(pf.max_drawdown()))
        return abs(tr / md) if md > 0 else 0.0
    elif metric == "max_drawdown":
        return abs(safe_float(pf.max_drawdown()))
    else:
        return float(pf.sharpe_ratio())


def _reduce_axes(axes: Dict[str, List[Any]], max_combos: int) -> Dict[str, List[Any]]:
    """Reduce axis sizes so total combinations <= max_combos."""
    reduced = {k: list(v) for k, v in axes.items()}
    while True:
        total = 1
        for v in reduced.values():
            total *= len(v)
        if total <= max_combos:
            break
        largest_key = max(reduced, key=lambda k: len(reduced[k]))
        vals = reduced[largest_key]
        reduced[largest_key] = vals[::2]
    return reduced


def _jsonify(val: Any) -> Any:
    """Ensure value is JSON-serializable."""
    if isinstance(val, (np.integer,)):
        return int(val)
    if isinstance(val, (np.floating,)):
        return float(val)
    return val
