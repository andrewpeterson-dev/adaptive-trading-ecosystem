"""
Market regime detection.
Classifies current market conditions using volatility, trend, and correlation features.
"""

from datetime import datetime
from enum import Enum

import numpy as np
import pandas as pd
import structlog

logger = structlog.get_logger(__name__)


class Regime(str, Enum):
    LOW_VOL_BULL = "low_vol_bull"
    HIGH_VOL_BULL = "high_vol_bull"
    LOW_VOL_BEAR = "low_vol_bear"
    HIGH_VOL_BEAR = "high_vol_bear"
    SIDEWAYS = "sideways"


class RegimeDetector:
    """
    Volatility-based regime classifier.
    Uses 20-day rolling volatility and 50-day trend to classify market state.
    Scaffold for future HMM or clustering-based regime detection.
    """

    def __init__(
        self,
        vol_window: int = 20,
        trend_window: int = 50,
        vol_threshold_percentile: float = 50.0,
        trend_threshold: float = 0.0,
    ):
        self.vol_window = vol_window
        self.trend_window = trend_window
        self.vol_threshold_percentile = vol_threshold_percentile
        self.trend_threshold = trend_threshold
        self._history: list[dict] = []

    def detect(self, df: pd.DataFrame) -> dict:
        """
        Classify current market regime.
        Returns dict with regime label, confidence, and supporting metrics.
        """
        if len(df) < max(self.vol_window, self.trend_window) + 10:
            return {"regime": Regime.SIDEWAYS, "confidence": 0.0, "volatility_20d": 0.0, "trend_strength": 0.0}

        # Compute rolling volatility (annualized)
        log_returns = np.log(df["close"] / df["close"].shift(1))
        vol_20d = log_returns.rolling(self.vol_window).std() * np.sqrt(252)
        current_vol = vol_20d.iloc[-1]

        # Volatility regime: percentile rank over lookback
        vol_percentile = vol_20d.rank(pct=True).iloc[-1] * 100
        is_high_vol = vol_percentile > self.vol_threshold_percentile

        # Trend detection: slope of 50-day regression
        close = df["close"].iloc[-self.trend_window:]
        x = np.arange(len(close))
        slope = np.polyfit(x, close.values, 1)[0]
        trend_strength = slope / close.mean()  # Normalized slope
        is_bullish = trend_strength > self.trend_threshold
        is_bearish = trend_strength < -self.trend_threshold

        # Classify
        if abs(trend_strength) < 0.0001:
            regime = Regime.SIDEWAYS
        elif is_high_vol and is_bullish:
            regime = Regime.HIGH_VOL_BULL
        elif not is_high_vol and is_bullish:
            regime = Regime.LOW_VOL_BULL
        elif is_high_vol and is_bearish:
            regime = Regime.HIGH_VOL_BEAR
        elif not is_high_vol and is_bearish:
            regime = Regime.LOW_VOL_BEAR
        else:
            regime = Regime.SIDEWAYS

        # Confidence based on how extreme the signals are
        vol_z = (current_vol - vol_20d.mean()) / vol_20d.std() if vol_20d.std() > 0 else 0
        confidence = min(1.0, (abs(trend_strength) * 1000 + abs(vol_z)) / 4.0)

        result = {
            "regime": regime,
            "confidence": round(confidence, 3),
            "volatility_20d": round(current_vol, 4),
            "vol_percentile": round(vol_percentile, 1),
            "trend_strength": round(trend_strength, 6),
            "timestamp": datetime.utcnow().isoformat(),
        }

        self._history.append(result)
        logger.info("regime_detected", **result)
        return result

    def get_regime_history(self, limit: int = 50) -> list[dict]:
        return self._history[-limit:]
