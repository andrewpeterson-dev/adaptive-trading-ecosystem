"""
Walk-forward validation engine.

Splits historical data into rolling train/test windows and evaluates strategy
performance on each test segment using indicators warmed up on training data.
This proves whether a strategy adapts to changing market conditions.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import structlog

from services.backtesting.data_fetcher import fetch_ohlcv
from services.backtesting.vectorbt_engine import (
    build_entry_signals,
    build_exit_signals,
    freq_from_timeframe,
    safe_float,
)

logger = structlog.get_logger(__name__)


# ── Result types ──────────────────────────────────────────────────────────

class SegmentMetrics:
    """Metrics for a single walk-forward test segment."""

    __slots__ = ("start", "end", "sharpe", "total_return", "max_drawdown",
                 "win_rate", "num_trades")

    def __init__(
        self,
        start: str,
        end: str,
        sharpe: float = 0.0,
        total_return: float = 0.0,
        max_drawdown: float = 0.0,
        win_rate: float = 0.0,
        num_trades: int = 0,
    ):
        self.start = start
        self.end = end
        self.sharpe = sharpe
        self.total_return = total_return
        self.max_drawdown = max_drawdown
        self.win_rate = win_rate
        self.num_trades = num_trades

    def to_dict(self) -> Dict[str, Any]:
        return {
            "start": self.start,
            "end": self.end,
            "metrics": {
                "sharpe": round(self.sharpe, 3),
                "total_return": round(self.total_return, 4),
                "max_drawdown": round(self.max_drawdown, 4),
                "win_rate": round(self.win_rate, 3),
                "num_trades": self.num_trades,
            },
        }


class WalkForwardResult:
    """Aggregate result from a walk-forward validation run."""

    def __init__(
        self,
        segments: List[SegmentMetrics],
        aggregate_metrics: Dict[str, float],
        consistency_score: float,
        regime_adaptability_score: float,
        symbol: str,
        timeframe: str,
        n_segments: int,
        lookback_days: int,
    ):
        self.segments = segments
        self.aggregate_metrics = aggregate_metrics
        self.consistency_score = consistency_score
        self.regime_adaptability_score = regime_adaptability_score
        self.symbol = symbol
        self.timeframe = timeframe
        self.n_segments = n_segments
        self.lookback_days = lookback_days

    def to_dict(self) -> Dict[str, Any]:
        return {
            "segments": [s.to_dict() for s in self.segments],
            "aggregate_metrics": {
                k: round(v, 4) for k, v in self.aggregate_metrics.items()
            },
            "consistency_score": round(self.consistency_score, 3),
            "regime_adaptability_score": round(self.regime_adaptability_score, 3),
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "n_segments": self.n_segments,
            "lookback_days": self.lookback_days,
        }


# ── Helpers ───────────────────────────────────────────────────────────────

def _segment_volatility(close: pd.Series) -> float:
    """Annualized volatility of a price series."""
    returns = close.pct_change().dropna()
    if len(returns) < 2:
        return 0.0
    return float(np.std(returns, ddof=1) * np.sqrt(252))


def _run_segment_backtest(
    df: pd.DataFrame,
    conditions: Optional[List[Dict[str, Any]]],
    condition_groups: Optional[List[Dict[str, Any]]],
    exit_conditions: Optional[List[Dict[str, Any]]],
    commission_pct: float,
    slippage_pct: float,
    initial_capital: float,
    timeframe: str,
    test_start_bar: int = 0,
) -> Dict[str, float]:
    """Run a VectorBT backtest on a single segment DataFrame.

    We build signals on the *full* df (which includes training warmup +
    test window) so indicators warm up properly, but only measure
    metrics over the test period starting at ``test_start_bar``.
    """
    try:
        import vectorbt as vbt
    except ImportError as exc:
        raise RuntimeError("vectorbt is not installed") from exc

    close = df["close"]
    entries = build_entry_signals(df, conditions, condition_groups)
    exits = build_exit_signals(df, exit_conditions)
    fees = commission_pct + slippage_pct

    pf = vbt.Portfolio.from_signals(
        close=close,
        entries=entries,
        exits=exits,
        init_cash=initial_capital,
        fees=fees,
        freq=freq_from_timeframe(timeframe),
    )

    # Slice portfolio value to test period only
    equity = pf.value().iloc[test_start_bar:]
    returns = equity.pct_change().dropna()
    sharpe = (
        float(returns.mean() / returns.std(ddof=1) * np.sqrt(252))
        if len(returns) > 1 and returns.std() > 0
        else 0.0
    )
    total_return = (
        float(equity.iloc[-1] / equity.iloc[0] - 1)
        if len(equity) > 1
        else 0.0
    )
    max_drawdown = abs(float((equity / equity.cummax() - 1).min()))

    # Win rate from trades — only count trades entered during test period
    test_start_date = df.index[test_start_bar] if test_start_bar < len(df) else df.index[-1]
    num_trades = 0
    win_rate = 0.0
    try:
        trades = pf.trades.records_readable
        # Filter to trades with entry timestamp >= test start date
        entry_col = None
        for col_name in ("Entry Timestamp", "Entry Index", "entry_idx"):
            if col_name in trades.columns:
                entry_col = col_name
                break
        if entry_col is not None:
            trades = trades[trades[entry_col] >= test_start_date]
        num_trades = len(trades)
        if num_trades > 0:
            pnl_col = trades.get("PnL", trades.get("Return", pd.Series(dtype=float)))
            wins = int((pnl_col > 0).sum())
            win_rate = wins / num_trades
    except Exception:
        pass

    return {
        "sharpe": sharpe,
        "total_return": total_return,
        "max_drawdown": max_drawdown,
        "win_rate": win_rate,
        "num_trades": num_trades,
    }


# ── Main entry point ─────────────────────────────────────────────────────

def run_walk_forward(
    conditions: Optional[List[Dict[str, Any]]] = None,
    condition_groups: Optional[List[Dict[str, Any]]] = None,
    exit_conditions: Optional[List[Dict[str, Any]]] = None,
    symbol: str = "SPY",
    timeframe: str = "1D",
    lookback_days: int = 756,
    n_segments: int = 6,
    commission_pct: float = 0.001,
    slippage_pct: float = 0.0005,
    initial_capital: float = 100_000.0,
) -> Dict[str, Any]:
    """Run walk-forward validation.

    Divides the date range into *n_segments* test windows.  For each
    window, all prior data serves as the training/warmup period.
    Returns per-segment metrics plus aggregate scores.
    """
    try:
        import vectorbt as vbt  # noqa: F401 — ensure it is installed
    except ImportError as exc:
        raise RuntimeError("vectorbt is not installed") from exc

    logger.info(
        "walk_forward_start",
        symbol=symbol,
        timeframe=timeframe,
        lookback_days=lookback_days,
        n_segments=n_segments,
    )

    df = fetch_ohlcv(symbol, timeframe, lookback_days)
    if df.empty or len(df) < 40:
        raise ValueError(
            f"Insufficient data for walk-forward on {symbol} ({len(df)} bars, need >= 40)"
        )

    total_bars = len(df)
    # Ensure at least 20% of data is reserved for the first training window
    min_train_bars = max(int(total_bars * 0.2), 20)
    testable_bars = total_bars - min_train_bars

    if testable_bars < n_segments:
        raise ValueError(
            f"Not enough data for {n_segments} segments. "
            f"Have {total_bars} bars with {min_train_bars} reserved for initial training."
        )

    segment_size = testable_bars // n_segments

    segments: List[SegmentMetrics] = []
    segment_volatilities: List[float] = []
    segment_returns: List[float] = []

    for seg_idx in range(n_segments):
        test_start_idx = min_train_bars + seg_idx * segment_size
        test_end_idx = (
            min_train_bars + (seg_idx + 1) * segment_size
            if seg_idx < n_segments - 1
            else total_bars
        )

        # Training data = everything before the test window
        # We pass training + test to the backtest so indicators warm up,
        # but only slice the test window for metrics.
        full_slice = df.iloc[:test_end_idx].copy()
        test_slice = df.iloc[test_start_idx:test_end_idx]

        test_start_date = test_slice.index[0]
        test_end_date = test_slice.index[-1]

        start_str = (
            test_start_date.strftime("%Y-%m-%d")
            if hasattr(test_start_date, "strftime")
            else str(test_start_date)
        )
        end_str = (
            test_end_date.strftime("%Y-%m-%d")
            if hasattr(test_end_date, "strftime")
            else str(test_end_date)
        )

        # Compute segment volatility from test window close prices
        vol = _segment_volatility(test_slice["close"])
        segment_volatilities.append(vol)

        train_bars = test_start_idx  # number of training bars in this segment

        try:
            metrics = _run_segment_backtest(
                df=full_slice,
                conditions=conditions,
                condition_groups=condition_groups,
                exit_conditions=exit_conditions,
                commission_pct=commission_pct,
                slippage_pct=slippage_pct,
                initial_capital=initial_capital,
                timeframe=timeframe,
                test_start_bar=train_bars,
            )

            seg = SegmentMetrics(
                start=start_str,
                end=end_str,
                sharpe=metrics["sharpe"],
                total_return=metrics["total_return"],
                max_drawdown=metrics["max_drawdown"],
                win_rate=metrics["win_rate"],
                num_trades=metrics["num_trades"],
            )
            segment_returns.append(metrics["total_return"])
        except Exception as exc:
            logger.warning(
                "walk_forward_segment_failed",
                segment=seg_idx,
                error=str(exc),
            )
            seg = SegmentMetrics(start=start_str, end=end_str)
            segment_returns.append(0.0)

        segments.append(seg)

    # ── Aggregate metrics ────────────────────────────────────────────────
    sharpes = [s.sharpe for s in segments]
    returns = [s.total_return for s in segments]
    drawdowns = [s.max_drawdown for s in segments]
    win_rates = [s.win_rate for s in segments]
    trades_total = sum(s.num_trades for s in segments)

    aggregate_metrics: Dict[str, float] = {
        "mean_sharpe": float(np.mean(sharpes)) if sharpes else 0.0,
        "std_sharpe": float(np.std(sharpes, ddof=1)) if len(sharpes) > 1 else 0.0,
        "mean_return": float(np.mean(returns)) if returns else 0.0,
        "mean_max_drawdown": float(np.mean(drawdowns)) if drawdowns else 0.0,
        "mean_win_rate": float(np.mean(win_rates)) if win_rates else 0.0,
        "total_trades": float(trades_total),
    }

    # Consistency score = what % of segments were profitable
    profitable_count = sum(1 for r in returns if r > 0)
    consistency_score = profitable_count / len(returns) if returns else 0.0

    # Regime adaptability score = correlation between segment volatility and
    # segment returns.  Negative correlation is good (strategy performs well
    # even in volatile regimes).
    regime_adaptability_score = 0.0
    if len(segment_volatilities) >= 3 and len(segment_returns) >= 3:
        vols = np.array(segment_volatilities)
        rets = np.array(segment_returns)
        if np.std(vols) > 0 and np.std(rets) > 0:
            corr = float(np.corrcoef(vols, rets)[0, 1])
            if not math.isnan(corr):
                regime_adaptability_score = corr

    result = WalkForwardResult(
        segments=segments,
        aggregate_metrics=aggregate_metrics,
        consistency_score=consistency_score,
        regime_adaptability_score=regime_adaptability_score,
        symbol=symbol.upper(),
        timeframe=timeframe,
        n_segments=n_segments,
        lookback_days=lookback_days,
    )

    logger.info(
        "walk_forward_complete",
        symbol=symbol,
        segments=n_segments,
        consistency=round(consistency_score, 3),
        adaptability=round(regime_adaptability_score, 3),
    )

    return result.to_dict()
