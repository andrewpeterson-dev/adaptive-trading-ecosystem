"""
Ablation study engine.

Compares a real strategy's performance against a distribution of random
strategies that trade at the same frequency.  Returns a p-value indicating
the probability that the observed performance is due to luck.
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


# ── Result type ───────────────────────────────────────────────────────────

class AblationResult:
    """Holds the output of an ablation study."""

    def __init__(
        self,
        strategy_sharpe: float,
        random_mean_sharpe: float,
        random_std: float,
        percentile: float,
        p_value: float,
        is_significant: bool,
        random_distribution_histogram: List[Dict[str, Any]],
        n_random_trials: int,
        symbol: str,
        timeframe: str,
        lookback_days: int,
    ):
        self.strategy_sharpe = strategy_sharpe
        self.random_mean_sharpe = random_mean_sharpe
        self.random_std = random_std
        self.percentile = percentile
        self.p_value = p_value
        self.is_significant = is_significant
        self.random_distribution_histogram = random_distribution_histogram
        self.n_random_trials = n_random_trials
        self.symbol = symbol
        self.timeframe = timeframe
        self.lookback_days = lookback_days

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_sharpe": round(self.strategy_sharpe, 4),
            "random_mean_sharpe": round(self.random_mean_sharpe, 4),
            "random_std": round(self.random_std, 4),
            "percentile": round(self.percentile, 2),
            "p_value": round(self.p_value, 4),
            "is_significant": self.is_significant,
            "random_distribution_histogram": self.random_distribution_histogram,
            "n_random_trials": self.n_random_trials,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "lookback_days": self.lookback_days,
        }


# ── Helpers ───────────────────────────────────────────────────────────────

def _build_histogram(
    random_sharpes: np.ndarray,
    strategy_sharpe: float,
    n_bins: int = 30,
) -> List[Dict[str, Any]]:
    """Build a histogram of the random Sharpe distribution.

    Returns a list of {bin_start, bin_end, count, contains_strategy} dicts
    suitable for front-end charting.
    """
    if len(random_sharpes) == 0:
        return []

    lo = float(np.min(random_sharpes))
    hi = float(np.max(random_sharpes))

    # Extend range to include the strategy value
    lo = min(lo, strategy_sharpe) - 0.1
    hi = max(hi, strategy_sharpe) + 0.1

    bin_width = (hi - lo) / n_bins
    if bin_width <= 0:
        bin_width = 0.1

    bins: List[Dict[str, Any]] = []
    for i in range(n_bins):
        bin_start = lo + i * bin_width
        bin_end = bin_start + bin_width
        count = int(np.sum((random_sharpes >= bin_start) & (random_sharpes < bin_end)))
        contains_strategy = bin_start <= strategy_sharpe < bin_end
        bins.append({
            "bin_start": round(bin_start, 4),
            "bin_end": round(bin_end, 4),
            "count": count,
            "contains_strategy": contains_strategy,
        })

    return bins


def _random_signals(n_bars: int, trade_frequency: float, rng: np.random.Generator) -> np.ndarray:
    """Generate a random boolean entry signal array with approximately
    the same trade frequency as the real strategy."""
    return rng.random(n_bars) < trade_frequency


def _sharpe_from_portfolio(pf: Any) -> float:
    """Extract Sharpe ratio from a VectorBT portfolio, returning 0 on failure."""
    return safe_float(pf.sharpe_ratio())


# ── Main entry point ─────────────────────────────────────────────────────

def run_ablation_study(
    conditions: Optional[List[Dict[str, Any]]] = None,
    condition_groups: Optional[List[Dict[str, Any]]] = None,
    exit_conditions: Optional[List[Dict[str, Any]]] = None,
    symbol: str = "SPY",
    timeframe: str = "1D",
    lookback_days: int = 252,
    n_random_trials: int = 1000,
    commission_pct: float = 0.001,
    slippage_pct: float = 0.0005,
    initial_capital: float = 100_000.0,
) -> Dict[str, Any]:
    """Run an ablation study comparing the real strategy against random baselines.

    1. Run the real strategy through VectorBT to get the baseline Sharpe.
    2. Measure the real strategy's trade frequency (fraction of bars with entries).
    3. Generate *n_random_trials* random signal arrays with the same average frequency.
    4. Run each through ``vbt.Portfolio.from_signals()`` and collect Sharpes.
    5. Compute the p-value: proportion of random Sharpes >= real Sharpe.
    """
    try:
        import vectorbt as vbt
    except ImportError as exc:
        raise RuntimeError("vectorbt is not installed") from exc

    logger.info(
        "ablation_study_start",
        symbol=symbol,
        timeframe=timeframe,
        lookback_days=lookback_days,
        n_random_trials=n_random_trials,
    )

    df = fetch_ohlcv(symbol, timeframe, lookback_days)
    if df.empty or len(df) < 20:
        raise ValueError(
            f"Insufficient data for ablation study on {symbol} ({len(df)} bars)"
        )

    close = df["close"]
    n_bars = len(df)
    fees = commission_pct + slippage_pct
    freq = freq_from_timeframe(timeframe)

    # ── Step 1: Real strategy backtest ────────────────────────────────────
    entries = build_entry_signals(df, conditions, condition_groups)
    exits = build_exit_signals(df, exit_conditions)

    pf_real = vbt.Portfolio.from_signals(
        close=close,
        entries=entries,
        exits=exits,
        init_cash=initial_capital,
        fees=fees,
        freq=freq,
    )
    strategy_sharpe = _sharpe_from_portfolio(pf_real)

    # ── Step 2: Measure trade frequency ──────────────────────────────────
    entry_count = int(entries.sum())
    trade_frequency = entry_count / n_bars if n_bars > 0 else 0.01
    # Clamp to sane range so random strategies have trades
    trade_frequency = max(trade_frequency, 0.005)
    trade_frequency = min(trade_frequency, 0.5)

    logger.info(
        "ablation_real_strategy",
        sharpe=round(strategy_sharpe, 4),
        entry_count=entry_count,
        trade_frequency=round(trade_frequency, 4),
    )

    # ── Step 3 & 4: Random trials ────────────────────────────────────────
    rng = np.random.default_rng(seed=42)
    random_sharpes: List[float] = []

    # Pre-generate all random entry matrices for vectorized processing
    # Process in batches to manage memory
    batch_size = min(200, n_random_trials)

    for batch_start in range(0, n_random_trials, batch_size):
        batch_end = min(batch_start + batch_size, n_random_trials)
        actual_batch = batch_end - batch_start

        for _ in range(actual_batch):
            rand_entries = pd.Series(
                _random_signals(n_bars, trade_frequency, rng),
                index=df.index,
            )
            rand_exits = pd.Series(False, index=df.index)

            try:
                pf_rand = vbt.Portfolio.from_signals(
                    close=close,
                    entries=rand_entries,
                    exits=rand_exits,
                    init_cash=initial_capital,
                    fees=fees,
                    freq=freq,
                )
                random_sharpes.append(_sharpe_from_portfolio(pf_rand))
            except Exception:
                random_sharpes.append(0.0)

    random_arr = np.array(random_sharpes, dtype=float)
    # Replace NaN/Inf with 0
    random_arr = np.where(np.isfinite(random_arr), random_arr, 0.0)

    # ── Step 5: Statistics ───────────────────────────────────────────────
    random_mean = float(np.mean(random_arr))
    random_std = float(np.std(random_arr, ddof=1)) if len(random_arr) > 1 else 0.0

    # Percentile: what % of random strategies did worse
    if len(random_arr) > 0:
        percentile = float(np.sum(random_arr <= strategy_sharpe) / len(random_arr) * 100)
    else:
        percentile = 50.0

    # P-value: fraction of random strategies >= real strategy's Sharpe
    if len(random_arr) > 0:
        p_value = float(np.sum(random_arr >= strategy_sharpe) / len(random_arr))
    else:
        p_value = 1.0

    is_significant = p_value < 0.05

    histogram = _build_histogram(random_arr, strategy_sharpe)

    result = AblationResult(
        strategy_sharpe=strategy_sharpe,
        random_mean_sharpe=random_mean,
        random_std=random_std,
        percentile=percentile,
        p_value=p_value,
        is_significant=is_significant,
        random_distribution_histogram=histogram,
        n_random_trials=len(random_arr),
        symbol=symbol.upper(),
        timeframe=timeframe,
        lookback_days=lookback_days,
    )

    logger.info(
        "ablation_study_complete",
        symbol=symbol,
        strategy_sharpe=round(strategy_sharpe, 4),
        random_mean=round(random_mean, 4),
        p_value=round(p_value, 4),
        is_significant=is_significant,
        percentile=round(percentile, 2),
    )

    return result.to_dict()
