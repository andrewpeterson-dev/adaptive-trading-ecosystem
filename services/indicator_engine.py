"""
Indicator computation engine.
Computes technical indicators from OHLCV DataFrames using vectorized operations.
"""

import numpy as np
import pandas as pd
from typing import Any
import structlog

logger = structlog.get_logger(__name__)


class IndicatorEngine:
    """Stateless indicator computation. All methods are class-level or static."""

    @staticmethod
    def rsi(close: pd.Series, length: int = 14) -> pd.Series:
        delta = close.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        avg_gain = gain.ewm(alpha=1 / length, min_periods=length).mean()
        avg_loss = loss.ewm(alpha=1 / length, min_periods=length).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        return 100 - (100 / (1 + rs))

    @staticmethod
    def sma(close: pd.Series, length: int = 20) -> pd.Series:
        return close.rolling(window=length, min_periods=length).mean()

    @staticmethod
    def ema(close: pd.Series, length: int = 20) -> pd.Series:
        return close.ewm(span=length, adjust=False, min_periods=length).mean()

    @staticmethod
    def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> dict[str, pd.Series]:
        ema_fast = close.ewm(span=fast, adjust=False).mean()
        ema_slow = close.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line
        return {"macd": macd_line, "signal": signal_line, "histogram": histogram}

    @staticmethod
    def bollinger_bands(close: pd.Series, length: int = 20, std_dev: float = 2.0) -> dict[str, pd.Series]:
        middle = close.rolling(window=length).mean()
        std = close.rolling(window=length).std()
        upper = middle + std_dev * std
        lower = middle - std_dev * std
        width = (upper - lower) / middle
        pct_b = (close - lower) / (upper - lower)
        return {"upper": upper, "middle": middle, "lower": lower, "width": width, "pct_b": pct_b}

    @staticmethod
    def atr(high: pd.Series, low: pd.Series, close: pd.Series, length: int = 14) -> pd.Series:
        prev_close = close.shift(1)
        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.ewm(alpha=1 / length, min_periods=length).mean()

    @staticmethod
    def vwap(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series) -> pd.Series:
        typical_price = (high + low + close) / 3
        cum_tp_vol = (typical_price * volume).cumsum()
        cum_vol = volume.cumsum()
        return cum_tp_vol / cum_vol.replace(0, np.nan)

    @staticmethod
    def stochastic(high: pd.Series, low: pd.Series, close: pd.Series,
                   k_period: int = 14, d_period: int = 3, smooth_k: int = 3) -> dict[str, pd.Series]:
        lowest_low = low.rolling(window=k_period).min()
        highest_high = high.rolling(window=k_period).max()
        raw_k = 100 * (close - lowest_low) / (highest_high - lowest_low).replace(0, np.nan)
        k = raw_k.rolling(window=smooth_k).mean()
        d = k.rolling(window=d_period).mean()
        return {"k": k, "d": d}

    @staticmethod
    def obv(close: pd.Series, volume: pd.Series) -> pd.Series:
        direction = np.sign(close.diff())
        direction.iloc[0] = 0
        return (volume * direction).cumsum()

    @classmethod
    def compute(cls, indicator_name: str, df: pd.DataFrame, params: dict[str, Any]) -> Any:
        """Dispatch computation by indicator name."""
        name = indicator_name.lower().replace(" ", "_").replace("-", "_")
        dispatch = {
            "rsi": lambda: cls.rsi(df["close"], **params),
            "sma": lambda: cls.sma(df["close"], **params),
            "ema": lambda: cls.ema(df["close"], **params),
            "macd": lambda: cls.macd(df["close"], **params),
            "bollinger_bands": lambda: cls.bollinger_bands(df["close"], **params),
            "atr": lambda: cls.atr(df["high"], df["low"], df["close"], **params),
            "vwap": lambda: cls.vwap(df["high"], df["low"], df["close"], df["volume"]),
            "stochastic": lambda: cls.stochastic(df["high"], df["low"], df["close"], **params),
            "obv": lambda: cls.obv(df["close"], df["volume"]),
        }
        fn = dispatch.get(name)
        if fn is None:
            raise ValueError(f"Unknown indicator: {indicator_name}")
        logger.info("indicator_computed", name=name, params=params)
        return fn()

    @classmethod
    def compute_batch(cls, indicators: list[dict], df: pd.DataFrame) -> dict[str, Any]:
        """Compute multiple indicators at once. Each dict has 'name' and 'params'."""
        results = {}
        for spec in indicators:
            key = f"{spec['name']}_{hash(frozenset(spec.get('params', {}).items()))}"
            try:
                results[key] = cls.compute(spec["name"], df, spec.get("params", {}))
            except Exception as e:
                logger.error("indicator_batch_error", name=spec["name"], error=str(e))
                results[key] = None
        return results
