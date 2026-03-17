"""
VectorBT-powered backtesting engine.

Accepts strategy conditions in the same format the Strategy Builder produces
(indicators + comparison operators + thresholds), converts them into entry/exit
signal arrays, and uses ``vbt.Portfolio.from_signals()`` to run the backtest.

Supported indicators: RSI, SMA, EMA, MACD, ATR, VWAP, Bollinger Bands,
Volume, Stochastic, OBV.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import structlog

from services.backtesting.data_fetcher import fetch_ohlcv

logger = structlog.get_logger(__name__)

# ── Indicator helpers ────────────────────────────────────────────────────────

_INDICATOR_ALIASES: Dict[str, str] = {
    "bollinger_bands": "bbands",
    "bollinger": "bbands",
    "bb": "bbands",
    "stoch": "stochastic",
    "stoch_rsi": "stochastic",
    "moving_average": "sma",
    "exponential_moving_average": "ema",
}


def canon(name: str) -> str:
    n = name.strip().lower().replace(" ", "_").replace("-", "_")
    return _INDICATOR_ALIASES.get(n, n)


def _compute_indicator_series(
    name: str,
    df: pd.DataFrame,
    params: Optional[Dict[str, Any]] = None,
    field: Optional[str] = None,
) -> pd.Series:
    """Return a pandas Series for the requested indicator/field."""
    params = dict(params or {})
    canonical = canon(name)

    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]

    # Normalise 'period' -> the key each indicator expects
    period = params.pop("period", params.pop("length", None))

    if canonical == "rsi":
        length = int(period or 14)
        delta = close.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        avg_gain = gain.ewm(alpha=1 / length, min_periods=length).mean()
        avg_loss = loss.ewm(alpha=1 / length, min_periods=length).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        return 100 - (100 / (1 + rs))

    elif canonical == "sma":
        length = int(period or 20)
        return close.rolling(window=length, min_periods=length).mean()

    elif canonical == "ema":
        length = int(period or 20)
        return close.ewm(span=length, adjust=False, min_periods=length).mean()

    elif canonical == "macd":
        fast = int(params.get("fast", 12))
        slow = int(params.get("slow", 26))
        sig = int(params.get("signal", 9))
        ema_fast = close.ewm(span=fast, adjust=False).mean()
        ema_slow = close.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=sig, adjust=False).mean()
        histogram = macd_line - signal_line
        components = {"macd": macd_line, "signal": signal_line, "histogram": histogram}
        target = (field or "macd").strip().lower()
        return components.get(target, macd_line)

    elif canonical == "bbands":
        length = int(period or 20)
        std_dev = float(params.get("std", params.get("std_dev", 2.0)))
        middle = close.rolling(window=length).mean()
        std = close.rolling(window=length).std(ddof=0)
        upper = middle + std_dev * std
        lower = middle - std_dev * std
        width = (upper - lower) / middle
        pct_b = (close - lower) / (upper - lower)
        components = {"upper": upper, "middle": middle, "lower": lower, "width": width, "pct_b": pct_b}
        target = (field or "middle").strip().lower()
        return components.get(target, middle)

    elif canonical == "atr":
        length = int(period or 14)
        prev_close = close.shift(1)
        tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
        return tr.ewm(alpha=1 / length, min_periods=length).mean()

    elif canonical == "vwap":
        tp = (high + low + close) / 3
        date_key = df.index.normalize()
        cum_tp_vol = (tp * volume).groupby(date_key).cumsum()
        cum_vol = volume.groupby(date_key).cumsum()
        return cum_tp_vol / cum_vol.replace(0, np.nan)

    elif canonical == "stochastic":
        k_period = int(period or params.get("k_period", 14))
        d_period = int(params.get("d_period", 3))
        smooth_k = int(params.get("smooth_k", 3))
        lowest_low = low.rolling(window=k_period).min()
        highest_high = high.rolling(window=k_period).max()
        raw_k = 100 * (close - lowest_low) / (highest_high - lowest_low).replace(0, np.nan)
        k = raw_k.rolling(window=smooth_k).mean()
        d = k.rolling(window=d_period).mean()
        components = {"k": k, "d": d}
        target = (field or "k").strip().lower()
        return components.get(target, k)

    elif canonical == "volume":
        return volume.astype(float)

    elif canonical == "obv":
        direction = np.sign(close.diff())
        direction.iloc[0] = 0
        return (volume * direction).cumsum()

    else:
        raise ValueError(f"Unsupported indicator: {name}")


def _resolve_threshold_series(
    df: pd.DataFrame,
    conditions: List[Dict[str, Any]],
    compare_to: str,
) -> pd.Series:
    """Resolve a dynamic threshold reference to a Series."""
    ref = compare_to.strip().lower()
    if ref in {"price", "close"}:
        return df["close"]
    if ref in {"open"}:
        return df["open"]
    if ref in {"high"}:
        return df["high"]
    if ref in {"low"}:
        return df["low"]

    # Try matching against a condition's indicator (e.g. "ema_200", "sma_50.middle")
    field: Optional[str] = None
    indicator_ref = ref
    if "." in indicator_ref:
        indicator_ref, field = indicator_ref.split(".", 1)

    params: Dict[str, Any] = {}
    if "_" in indicator_ref:
        base, suffix = indicator_ref.rsplit("_", 1)
        if suffix.isdigit():
            indicator_ref = base
            params["period"] = int(suffix)

    # Check if any condition matches this indicator ref
    for cond in conditions:
        cond_name = canon(cond.get("indicator", ""))
        cond_params = cond.get("params") or {}
        cond_period = cond_params.get("period", cond_params.get("length"))
        aliases = {cond_name}
        if cond_period is not None:
            aliases.add(f"{cond_name}_{int(cond_period)}")
        if indicator_ref in aliases:
            return _compute_indicator_series(
                cond["indicator"],
                df,
                cond.get("params"),
                field or cond.get("field"),
            )

    return _compute_indicator_series(indicator_ref, df, params, field)


# ── Signal generation ────────────────────────────────────────────────────────

def _build_condition_mask(
    df: pd.DataFrame,
    condition: Dict[str, Any],
    all_conditions: List[Dict[str, Any]],
) -> pd.Series:
    """
    Evaluate a single condition and return a boolean Series.
    Handles comparison operators including crosses_above / crosses_below.
    """
    indicator_name = condition["indicator"]
    operator = condition.get("operator", ">")
    params = condition.get("params") or {}
    field = condition.get("field")

    series = _compute_indicator_series(indicator_name, df, params, field)

    # Resolve threshold
    compare_to = str(condition.get("compare_to", "") or "").strip()
    if compare_to:
        threshold = _resolve_threshold_series(df, all_conditions, compare_to)
    else:
        raw_val = condition.get("value", 0)
        threshold = safe_float(raw_val, default=0.0)

    if operator == ">":
        return series > threshold
    elif operator == "<":
        return series < threshold
    elif operator == ">=":
        return series >= threshold
    elif operator == "<=":
        return series <= threshold
    elif operator == "==":
        if isinstance(threshold, pd.Series):
            return (series - threshold).abs() < 0.001
        return (series - threshold).abs() < 0.001
    elif operator == "crosses_above":
        prev = series.shift(1)
        if isinstance(threshold, pd.Series):
            prev_thresh = threshold.shift(1)
            return (prev <= prev_thresh) & (series > threshold)
        return (prev <= threshold) & (series > threshold)
    elif operator == "crosses_below":
        prev = series.shift(1)
        if isinstance(threshold, pd.Series):
            prev_thresh = threshold.shift(1)
            return (prev >= prev_thresh) & (series < threshold)
        return (prev >= threshold) & (series < threshold)
    else:
        logger.warning("unknown_operator", operator=operator)
        return pd.Series(False, index=df.index)


def build_entry_signals(
    df: pd.DataFrame,
    conditions: Optional[List[Dict[str, Any]]] = None,
    condition_groups: Optional[List[Dict[str, Any]]] = None,
) -> pd.Series:
    """
    Build a boolean entry signal array from strategy conditions.

    Logic: AND within a group, OR between groups.
    """
    if condition_groups:
        groups = condition_groups
    elif conditions:
        groups = [{"conditions": conditions}]
    else:
        return pd.Series(False, index=df.index)

    flat_conditions = [c for g in groups for c in g.get("conditions", [])]

    group_signals = []
    for group in groups:
        group_conds = group.get("conditions", [])
        if not group_conds:
            continue
        masks = [_build_condition_mask(df, c, flat_conditions) for c in group_conds]
        combined = masks[0]
        for m in masks[1:]:
            combined = combined & m
        group_signals.append(combined)

    if not group_signals:
        return pd.Series(False, index=df.index)

    result = group_signals[0]
    for gs in group_signals[1:]:
        result = result | gs

    return result.fillna(False)


def build_exit_signals(
    df: pd.DataFrame,
    exit_conditions: Optional[List[Dict[str, Any]]] = None,
) -> pd.Series:
    """Build exit signals from explicit exit conditions, or return all-False."""
    if not exit_conditions:
        return pd.Series(False, index=df.index)
    return build_entry_signals(df, conditions=exit_conditions)


# ── Core backtest runner ─────────────────────────────────────────────────────

def run_vectorbt_backtest(
    symbol: str = "SPY",
    timeframe: str = "1D",
    lookback_days: int = 252,
    conditions: Optional[List[Dict[str, Any]]] = None,
    condition_groups: Optional[List[Dict[str, Any]]] = None,
    exit_conditions: Optional[List[Dict[str, Any]]] = None,
    initial_capital: float = 100_000.0,
    commission_pct: float = 0.001,
    slippage_pct: float = 0.0005,
    stop_loss_pct: Optional[float] = None,
    take_profit_pct: Optional[float] = None,
    action: str = "BUY",
    direction: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Run a full backtest using VectorBT.

    Returns dict with: metrics, equity_curve, trades, drawdown_curve,
    benchmark_equity_curve, symbol, timeframe, commission_pct, slippage_pct,
    diagnostics.
    """
    try:
        import vectorbt as vbt
    except ImportError as exc:
        raise RuntimeError("vectorbt is not installed: pip install vectorbt") from exc

    df = fetch_ohlcv(symbol, timeframe, lookback_days)
    if df.empty or len(df) < 20:
        raise ValueError(f"Insufficient data for {symbol} on {timeframe} ({len(df)} bars)")

    close = df["close"]

    is_short = False
    if direction:
        is_short = direction.strip().lower() in {"short", "sell"}
    else:
        is_short = str(action).upper() in {"SELL", "SHORT"}

    entries = build_entry_signals(df, conditions, condition_groups)
    exits = build_exit_signals(df, exit_conditions)

    fees = commission_pct + slippage_pct
    sl_stop = stop_loss_pct if stop_loss_pct and stop_loss_pct > 0 else None
    tp_stop = take_profit_pct if take_profit_pct and take_profit_pct > 0 else None

    if is_short:
        pf = vbt.Portfolio.from_signals(
            close=close,
            short_entries=entries,
            short_exits=exits,
            init_cash=initial_capital,
            fees=fees,
            sl_stop=sl_stop,
            tp_stop=tp_stop,
            freq=freq_from_timeframe(timeframe),
        )
    else:
        pf = vbt.Portfolio.from_signals(
            close=close,
            entries=entries,
            exits=exits,
            init_cash=initial_capital,
            fees=fees,
            sl_stop=sl_stop,
            tp_stop=tp_stop,
            freq=freq_from_timeframe(timeframe),
        )

    return _extract_results(
        pf=pf, df=df, close=close, symbol=symbol, timeframe=timeframe,
        initial_capital=initial_capital, commission_pct=commission_pct,
        slippage_pct=slippage_pct, entries=entries, conditions=conditions,
        condition_groups=condition_groups, is_short=is_short,
    )


def freq_from_timeframe(tf: str) -> str:
    mapping = {
        "1m": "1min", "5m": "5min", "15m": "15min",
        "1H": "1h", "4H": "4h", "1D": "1D", "1W": "1W",
    }
    return mapping.get(tf, "1D")


def safe_float(val: Any, default: float = 0.0) -> float:
    """Convert to float, handling NaN/Inf/None."""
    if val is None:
        return default
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return default
        return f
    except (TypeError, ValueError):
        return default


def _extract_results(
    pf: Any,
    df: pd.DataFrame,
    close: pd.Series,
    symbol: str,
    timeframe: str,
    initial_capital: float,
    commission_pct: float,
    slippage_pct: float,
    entries: pd.Series,
    conditions: Optional[List[Dict[str, Any]]],
    condition_groups: Optional[List[Dict[str, Any]]],
    is_short: bool,
) -> Dict[str, Any]:
    """Extract a standardized result dict from a VectorBT Portfolio."""

    # Equity curve
    equity_series = pf.value()
    equity_curve: List[Dict[str, Any]] = []
    for ts, val in equity_series.items():
        equity_curve.append({
            "date": ts.strftime("%Y-%m-%d") if hasattr(ts, "strftime") else str(ts),
            "value": round(float(val), 2),
        })

    # Drawdown curve
    dd_series = pf.drawdown() * 100
    drawdown_curve: List[Dict[str, Any]] = []
    for ts, val in dd_series.items():
        drawdown_curve.append({
            "date": ts.strftime("%Y-%m-%d") if hasattr(ts, "strftime") else str(ts),
            "drawdown_pct": round(safe_float(val), 4),
        })

    # Trade records
    trades_list: List[Dict[str, Any]] = []
    try:
        trade_records = pf.trades.records_readable
        if len(trade_records) > 0:
            for _, row in trade_records.iterrows():
                entry_ts = row.get("Entry Timestamp", row.get("Entry Index", ""))
                exit_ts = row.get("Exit Timestamp", row.get("Exit Index", ""))
                entry_price = safe_float(row.get("Avg Entry Price", row.get("Entry Price", 0)))
                exit_price = safe_float(row.get("Avg Exit Price", row.get("Exit Price", 0)))
                pnl = safe_float(row.get("PnL", 0))
                ret = safe_float(row.get("Return", 0))

                entry_date = entry_ts.strftime("%Y-%m-%d") if hasattr(entry_ts, "strftime") else str(entry_ts)
                exit_date = exit_ts.strftime("%Y-%m-%d") if hasattr(exit_ts, "strftime") else str(exit_ts)

                trades_list.append({
                    "entry_date": entry_date,
                    "exit_date": exit_date,
                    "symbol": symbol.upper(),
                    "side": "SHORT" if is_short else "LONG",
                    "entry_price": round(entry_price, 2),
                    "exit_price": round(exit_price, 2),
                    "pnl": round(pnl, 2),
                    "pnl_pct": round(ret * 100, 2),
                })
    except Exception as exc:
        logger.warning("trade_extraction_failed", error=str(exc))

    # Benchmark (buy-and-hold)
    bh_start = float(close.iloc[0])
    benchmark_equity = [
        {
            "date": ts.strftime("%Y-%m-%d") if hasattr(ts, "strftime") else str(ts),
            "value": round(initial_capital * (float(price) / bh_start), 2),
        }
        for ts, price in close.items()
    ]

    # Metrics
    total_return = safe_float(pf.total_return())
    sharpe = safe_float(pf.sharpe_ratio())
    sortino = safe_float(pf.sortino_ratio())
    max_drawdown = abs(safe_float(pf.max_drawdown()))
    num_trades = len(trades_list)

    wins = [t for t in trades_list if t["pnl"] > 0]
    losses = [t for t in trades_list if t["pnl"] < 0]
    win_rate = len(wins) / num_trades if num_trades > 0 else 0.0

    gross_profit = sum(t["pnl"] for t in wins)
    gross_loss = abs(sum(t["pnl"] for t in losses))
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (float("inf") if gross_profit > 0 else 0.0)

    avg_trade_duration = 0.0
    if trades_list:
        durations = []
        for t in trades_list:
            try:
                ed = pd.to_datetime(t["entry_date"])
                xd = pd.to_datetime(t["exit_date"])
                durations.append((xd - ed).days)
            except (ValueError, TypeError):
                continue
        avg_trade_duration = sum(durations) / len(durations) if durations else 0.0

    calmar = abs(total_return / max_drawdown) if max_drawdown > 0 else 0.0

    avg_win = (gross_profit / len(wins)) if wins else 0.0
    avg_loss_val = (gross_loss / len(losses)) if losses else 0.0
    expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss_val)

    total_signals = int(entries.sum())
    groups = condition_groups or ([{"conditions": conditions}] if conditions else [])
    conditions_count = sum(len(g.get("conditions", [])) for g in groups)

    return {
        "symbol": symbol.upper(),
        "timeframe": timeframe,
        "commission_pct": commission_pct,
        "slippage_pct": slippage_pct,
        "metrics": {
            "sharpe_ratio": round(sharpe, 3),
            "sortino_ratio": round(sortino, 3),
            "max_drawdown": round(max_drawdown, 4),
            "win_rate": round(win_rate, 3),
            "profit_factor": round(min(float(profit_factor), 999), 3),
            "total_return": round(total_return, 4),
            "avg_trade_duration": round(avg_trade_duration, 1),
            "num_trades": num_trades,
            "calmar_ratio": round(calmar, 3),
            "expectancy": round(expectancy, 2),
            "avg_trade_pnl": round(sum(t["pnl"] for t in trades_list) / num_trades, 2) if num_trades else 0.0,
        },
        "diagnostics": {
            "bars_evaluated": len(df),
            "total_signals": total_signals,
            "conditions_count": conditions_count,
            "groups_count": len(groups),
        },
        "equity_curve": equity_curve,
        "drawdown_curve": drawdown_curve,
        "benchmark_equity_curve": benchmark_equity,
        "trades": trades_list,
    }
