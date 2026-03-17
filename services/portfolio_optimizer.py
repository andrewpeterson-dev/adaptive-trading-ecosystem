"""
Portfolio optimization service using PyPortfolioOpt.

Supports multiple optimization methods:
- Efficient Frontier (Max Sharpe Ratio)
- Efficient Frontier (Min Volatility)
- Hierarchical Risk Parity (HRP)
- Risk Parity (equal risk contribution)
- Black-Litterman (user views on expected returns)

All methods apply Ledoit-Wolf covariance shrinkage for robustness.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import structlog

logger = structlog.get_logger(__name__)

# Risk-free rate assumption (annualized)
RISK_FREE_RATE = 0.05


@dataclass
class OptimizationConstraints:
    """User-configurable constraints for portfolio optimization."""
    max_weight: float = 0.25
    min_weight: float = 0.0
    sector_caps: Dict[str, float] = field(default_factory=dict)


@dataclass
class OptimizationResult:
    """Output from any optimization method."""
    weights: Dict[str, float]
    expected_return: float
    volatility: float
    sharpe: float
    method: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EfficientFrontierPoint:
    """A single point on the efficient frontier."""
    expected_return: float
    volatility: float
    sharpe: float
    weights: Dict[str, float]


async def fetch_price_data(
    tickers: List[str],
    lookback_days: int = 252,
) -> pd.DataFrame:
    """Fetch historical adjusted close prices via yfinance.

    Returns a DataFrame with tickers as columns and dates as the index.
    """
    import yfinance as yf

    end = datetime.utcnow()
    start = end - timedelta(days=lookback_days)

    def _download() -> pd.DataFrame:
        data = yf.download(
            tickers,
            start=start.strftime("%Y-%m-%d"),
            end=end.strftime("%Y-%m-%d"),
            progress=False,
            auto_adjust=True,
            threads=True,
        )
        if data.empty:
            return pd.DataFrame()

        # yfinance returns multi-level columns when multiple tickers
        if isinstance(data.columns, pd.MultiIndex):
            prices = data["Close"] if "Close" in data.columns.get_level_values(0) else data
        else:
            prices = data[["Close"]].rename(columns={"Close": tickers[0]}) if len(tickers) == 1 else data

        # If single ticker came back as a Series, wrap it
        if isinstance(prices, pd.Series):
            prices = prices.to_frame(name=tickers[0])

        # Flatten any remaining MultiIndex
        if isinstance(prices.columns, pd.MultiIndex):
            prices.columns = prices.columns.get_level_values(-1)

        return prices

    prices = await asyncio.to_thread(_download)

    if prices.empty:
        raise ValueError(f"No price data returned for tickers: {tickers}")

    # Drop columns with > 30% missing data, forward-fill the rest
    threshold = len(prices) * 0.7
    prices = prices.dropna(axis=1, thresh=int(threshold))
    prices = prices.ffill().dropna()

    if prices.shape[1] < 2:
        raise ValueError("Need at least 2 tickers with sufficient price history.")

    return prices


def _compute_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """Compute daily log returns from price data."""
    return np.log(prices / prices.shift(1)).dropna()


def _ledoit_wolf_cov(prices: pd.DataFrame) -> pd.DataFrame:
    """Compute Ledoit-Wolf shrunk covariance matrix from *prices*.

    PyPortfolioOpt's CovarianceShrinkage expects a price DataFrame
    (it computes returns internally).
    """
    from pypfopt import risk_models

    cov = risk_models.CovarianceShrinkage(prices).ledoit_wolf()
    return cov


def _apply_constraints(
    ef: Any,
    constraints: OptimizationConstraints,
    tickers: List[str],
) -> None:
    """Apply sector caps and L2 regularization to an EfficientFrontier object.

    Note: per-asset weight bounds (min_weight, max_weight) are set via the
    ``weight_bounds`` parameter at EfficientFrontier construction time — NOT
    via ``add_constraint``.
    """
    from pypfopt import objective_functions

    # Sector caps: constraints.sector_caps maps sector_name -> max_weight
    # and we need a ticker -> sector mapping. For now we skip sector caps
    # if no mapping provided (would require external data).

    # L2 regularization to avoid extreme weights
    ef.add_objective(objective_functions.L2_reg, gamma=0.1)


async def optimize_max_sharpe(
    tickers: List[str],
    lookback_days: int = 252,
    constraints: Optional[OptimizationConstraints] = None,
) -> OptimizationResult:
    """Maximize the Sharpe ratio using the Efficient Frontier."""
    from pypfopt import expected_returns, EfficientFrontier

    constraints = constraints or OptimizationConstraints()
    prices = await fetch_price_data(tickers, lookback_days)
    mu = expected_returns.mean_historical_return(prices)
    cov = _ledoit_wolf_cov(prices)

    def _optimize() -> OptimizationResult:
        ef = EfficientFrontier(
            mu, cov,
            weight_bounds=(constraints.min_weight, constraints.max_weight),
        )
        _apply_constraints(ef, constraints, tickers)
        ef.max_sharpe(risk_free_rate=RISK_FREE_RATE)
        cleaned = ef.clean_weights()
        perf = ef.portfolio_performance(risk_free_rate=RISK_FREE_RATE)
        return OptimizationResult(
            weights=dict(cleaned),
            expected_return=float(perf[0]),
            volatility=float(perf[1]),
            sharpe=float(perf[2]),
            method="max_sharpe",
        )

    return await asyncio.to_thread(_optimize)


async def optimize_min_volatility(
    tickers: List[str],
    lookback_days: int = 252,
    constraints: Optional[OptimizationConstraints] = None,
) -> OptimizationResult:
    """Find the minimum variance portfolio on the Efficient Frontier."""
    from pypfopt import expected_returns, EfficientFrontier

    constraints = constraints or OptimizationConstraints()
    prices = await fetch_price_data(tickers, lookback_days)
    mu = expected_returns.mean_historical_return(prices)
    cov = _ledoit_wolf_cov(prices)

    def _optimize() -> OptimizationResult:
        ef = EfficientFrontier(
            mu, cov,
            weight_bounds=(constraints.min_weight, constraints.max_weight),
        )
        _apply_constraints(ef, constraints, tickers)
        ef.min_volatility()
        cleaned = ef.clean_weights()
        perf = ef.portfolio_performance(risk_free_rate=RISK_FREE_RATE)
        return OptimizationResult(
            weights=dict(cleaned),
            expected_return=float(perf[0]),
            volatility=float(perf[1]),
            sharpe=float(perf[2]),
            method="min_volatility",
        )

    return await asyncio.to_thread(_optimize)


async def optimize_hrp(
    tickers: List[str],
    lookback_days: int = 252,
    constraints: Optional[OptimizationConstraints] = None,
) -> OptimizationResult:
    """Hierarchical Risk Parity — cluster-based allocation.

    Does not require covariance inversion, making it more robust for
    ill-conditioned matrices.
    """
    from pypfopt import HRPOpt

    constraints = constraints or OptimizationConstraints()
    prices = await fetch_price_data(tickers, lookback_days)
    returns = _compute_returns(prices)
    lw_cov = _ledoit_wolf_cov(prices)

    def _optimize() -> OptimizationResult:
        hrp = HRPOpt(returns)
        hrp.optimize()
        cleaned = hrp.clean_weights()

        # Enforce max/min weight constraints by clipping and re-normalizing
        weights = dict(cleaned)
        weights = _clip_and_renormalize(weights, constraints)

        # Compute portfolio metrics using Ledoit-Wolf shrunk covariance
        w_array = np.array([weights.get(t, 0.0) for t in returns.columns])
        ann_ret = float(np.sum(returns.mean() * w_array) * 252)
        ann_vol = float(np.sqrt(np.dot(w_array, np.dot(lw_cov.values * 252, w_array))))
        sharpe = (ann_ret - RISK_FREE_RATE) / ann_vol if ann_vol > 0 else 0.0

        return OptimizationResult(
            weights=weights,
            expected_return=ann_ret,
            volatility=ann_vol,
            sharpe=sharpe,
            method="hrp",
        )

    return await asyncio.to_thread(_optimize)


async def optimize_risk_parity(
    tickers: List[str],
    lookback_days: int = 252,
    constraints: Optional[OptimizationConstraints] = None,
) -> OptimizationResult:
    """Risk Parity — equal risk contribution from each asset."""
    constraints = constraints or OptimizationConstraints()
    prices = await fetch_price_data(tickers, lookback_days)
    returns = _compute_returns(prices)
    cov = _ledoit_wolf_cov(prices)

    def _optimize() -> OptimizationResult:
        cov_matrix = cov.values
        n = cov_matrix.shape[0]

        # Iterative risk-parity using inverse-volatility as a starting point
        inv_vol = 1.0 / np.sqrt(np.diag(cov_matrix))
        weights_arr = inv_vol / inv_vol.sum()

        # Newton-like iteration to equalize risk contribution
        for _ in range(100):
            prev_weights = weights_arr.copy()
            port_var = weights_arr @ cov_matrix @ weights_arr
            if port_var <= 0:
                break
            marginal_risk = cov_matrix @ weights_arr
            risk_contrib = weights_arr * marginal_risk / np.sqrt(port_var)
            target_rc = np.sqrt(port_var) / n
            adjustment = target_rc / (risk_contrib + 1e-12)
            weights_arr = weights_arr * adjustment
            weights_arr = weights_arr / weights_arr.sum()
            if np.max(np.abs(weights_arr - prev_weights)) < 1e-8:
                break

        ticker_names = list(cov.columns)
        weights = {ticker_names[i]: float(weights_arr[i]) for i in range(n)}
        weights = _clip_and_renormalize(weights, constraints)

        w_array = np.array([weights.get(t, 0.0) for t in returns.columns])
        ann_ret = float(np.sum(returns.mean() * w_array) * 252)
        ann_vol = float(np.sqrt(np.dot(w_array, np.dot(cov.values * 252, w_array))))
        sharpe = (ann_ret - RISK_FREE_RATE) / ann_vol if ann_vol > 0 else 0.0

        return OptimizationResult(
            weights=weights,
            expected_return=ann_ret,
            volatility=ann_vol,
            sharpe=sharpe,
            method="risk_parity",
        )

    return await asyncio.to_thread(_optimize)


async def optimize_black_litterman(
    tickers: List[str],
    views: Dict[str, float],
    lookback_days: int = 252,
    constraints: Optional[OptimizationConstraints] = None,
) -> OptimizationResult:
    """Black-Litterman model — incorporates user views on expected returns.

    Args:
        tickers: List of ticker symbols.
        views: Dict mapping ticker -> expected return (e.g. {"AAPL": 0.10}).
        lookback_days: Historical data lookback.
        constraints: Weight constraints.
    """
    from pypfopt import BlackLittermanModel, EfficientFrontier
    from pypfopt import risk_models, expected_returns

    constraints = constraints or OptimizationConstraints()
    prices = await fetch_price_data(tickers, lookback_days)
    cov = _ledoit_wolf_cov(prices)

    # Market-cap weights approximation (equal weight as fallback)
    market_caps = {t: 1.0 for t in prices.columns}

    def _optimize() -> OptimizationResult:
        bl = BlackLittermanModel(
            cov,
            pi="market",
            market_caps=market_caps,
            absolute_views=views,
        )
        bl_returns = bl.bl_returns()
        bl_cov = bl.bl_cov()

        ef = EfficientFrontier(
            bl_returns, bl_cov,
            weight_bounds=(constraints.min_weight, constraints.max_weight),
        )
        _apply_constraints(ef, constraints, tickers)
        ef.max_sharpe(risk_free_rate=RISK_FREE_RATE)
        cleaned = ef.clean_weights()
        perf = ef.portfolio_performance(risk_free_rate=RISK_FREE_RATE)

        return OptimizationResult(
            weights=dict(cleaned),
            expected_return=float(perf[0]),
            volatility=float(perf[1]),
            sharpe=float(perf[2]),
            method="black_litterman",
        )

    return await asyncio.to_thread(_optimize)


async def compute_efficient_frontier(
    tickers: List[str],
    lookback_days: int = 252,
    n_points: int = 50,
) -> List[EfficientFrontierPoint]:
    """Compute the efficient frontier curve for charting.

    Returns n_points along the frontier from min-vol to max-return.
    """
    from pypfopt import expected_returns, EfficientFrontier

    prices = await fetch_price_data(tickers, lookback_days)
    mu = expected_returns.mean_historical_return(prices)
    cov = _ledoit_wolf_cov(prices)

    def _compute() -> List[EfficientFrontierPoint]:
        points: List[EfficientFrontierPoint] = []

        # Find min and max return bounds
        ef_min = EfficientFrontier(mu, cov)
        ef_min.min_volatility()
        min_ret = ef_min.portfolio_performance()[0]

        ef_max = EfficientFrontier(mu, cov)
        ef_max.max_sharpe(risk_free_rate=RISK_FREE_RATE)
        max_ret = ef_max.portfolio_performance()[0]

        if max_ret <= min_ret:
            return []

        # Extend slightly beyond max-sharpe for visualization
        target_returns = np.linspace(min_ret, max_ret * 1.15, n_points)

        for target_ret in target_returns:
            try:
                ef = EfficientFrontier(mu, cov)
                ef.efficient_return(float(target_ret))
                cleaned = ef.clean_weights()
                perf = ef.portfolio_performance(risk_free_rate=RISK_FREE_RATE)
                points.append(EfficientFrontierPoint(
                    expected_return=float(perf[0]),
                    volatility=float(perf[1]),
                    sharpe=float(perf[2]),
                    weights=dict(cleaned),
                ))
            except Exception as exc:
                # Some target returns may be infeasible
                logger.debug("frontier_point_failed", target_return=float(target_ret), error=str(exc))
                continue

        return points

    return await asyncio.to_thread(_compute)


async def compute_correlation_matrix(
    tickers: List[str],
    lookback_days: int = 252,
) -> Dict[str, Any]:
    """Compute the correlation matrix for the given tickers.

    Returns a dict with tickers and the correlation values.
    """
    prices = await fetch_price_data(tickers, lookback_days)
    returns = _compute_returns(prices)

    def _compute() -> Dict[str, Any]:
        corr = returns.corr()
        return {
            "tickers": list(corr.columns),
            "matrix": corr.values.tolist(),
        }

    return await asyncio.to_thread(_compute)


def _clip_and_renormalize(
    weights: Dict[str, float],
    constraints: OptimizationConstraints,
) -> Dict[str, float]:
    """Clip weights to [min_weight, max_weight] and re-normalize to sum to 1."""
    clipped = {
        k: max(constraints.min_weight, min(constraints.max_weight, v))
        for k, v in weights.items()
    }
    total = sum(clipped.values())
    if total <= 0:
        n = len(clipped)
        return {k: 1.0 / n for k in clipped}
    return {k: v / total for k, v in clipped.items()}


# Dispatcher for optimization methods
_OPTIMIZERS = {
    "max_sharpe": optimize_max_sharpe,
    "min_volatility": optimize_min_volatility,
    "hrp": optimize_hrp,
    "risk_parity": optimize_risk_parity,
}


async def run_optimization(
    tickers: List[str],
    method: str = "max_sharpe",
    lookback_days: int = 252,
    constraints: Optional[OptimizationConstraints] = None,
) -> OptimizationResult:
    """Run portfolio optimization with the specified method."""
    optimizer = _OPTIMIZERS.get(method)
    if not optimizer:
        raise ValueError(f"Unknown optimization method: {method}. Valid: {list(_OPTIMIZERS.keys())}")

    logger.info(
        "portfolio_optimization_start",
        method=method,
        tickers=tickers,
        lookback_days=lookback_days,
    )

    result = await optimizer(tickers, lookback_days, constraints)

    logger.info(
        "portfolio_optimization_complete",
        method=method,
        expected_return=f"{result.expected_return:.4f}",
        volatility=f"{result.volatility:.4f}",
        sharpe=f"{result.sharpe:.4f}",
    )

    return result
