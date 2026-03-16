"""
Technical indicator calculations from OHLCV bar data.

Pure numpy implementations — no TA-lib dependency. Each method returns
NaN-safe values and None when insufficient data is available.

Bar format: accepts both MarketDataService format (t/o/h/l/c/v)
and expanded format (timestamp/open/high/low/close/volume).
"""
from __future__ import annotations

import numpy as np
import structlog

logger = structlog.get_logger(__name__)


def _extract_arrays(bars: list[dict]) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Extract OHLCV numpy arrays from bars, handling both key formats."""
    opens = np.array([b.get("o") or b.get("open") or 0.0 for b in bars], dtype=np.float64)
    highs = np.array([b.get("h") or b.get("high") or 0.0 for b in bars], dtype=np.float64)
    lows = np.array([b.get("l") or b.get("low") or 0.0 for b in bars], dtype=np.float64)
    closes = np.array([b.get("c") or b.get("close") or 0.0 for b in bars], dtype=np.float64)
    volumes = np.array([b.get("v") or b.get("volume") or 0.0 for b in bars], dtype=np.float64)
    return opens, highs, lows, closes, volumes


def _ema_series(data: np.ndarray, period: int) -> np.ndarray:
    """Compute full EMA series. NaN-padded where insufficient data."""
    result = np.full(len(data), np.nan)
    if len(data) < period:
        return result
    multiplier = 2.0 / (period + 1)
    result[period - 1] = np.mean(data[:period])
    for i in range(period, len(data)):
        result[i] = (data[i] - result[i - 1]) * multiplier + result[i - 1]
    return result


def _wilder_smooth(data: np.ndarray, period: int) -> np.ndarray:
    """Wilder's smoothing method (used by RSI, ATR, ADX)."""
    result = np.full(len(data), np.nan)
    if len(data) < period:
        return result
    result[period - 1] = np.mean(data[:period])
    for i in range(period, len(data)):
        result[i] = (result[i - 1] * (period - 1) + data[i]) / period
    return result


class TechnicalFeatures:
    """Pure-function technical indicator calculations using numpy."""

    @staticmethod
    def compute(bars: list[dict]) -> dict:
        """
        Compute all technical features from OHLCV bars.

        Returns a flat dict of indicator values. Missing/insufficient-data
        indicators are set to None.
        """
        if not bars or len(bars) < 2:
            return {}

        opens, highs, lows, closes, volumes = _extract_arrays(bars)
        result: dict = {}

        # --- RSI (14-period) ---
        result.update(TechnicalFeatures._rsi(closes, 14))

        # --- MACD (12, 26, 9) ---
        result.update(TechnicalFeatures._macd(closes, 12, 26, 9))

        # --- Bollinger Bands (20, 2) ---
        result.update(TechnicalFeatures._bollinger(closes, 20, 2.0))

        # --- ATR (14-period) ---
        result.update(TechnicalFeatures._atr(highs, lows, closes, 14))

        # --- Volume profile ---
        result.update(TechnicalFeatures._volume_profile(volumes))

        # --- Moving averages ---
        result.update(TechnicalFeatures._moving_averages(closes))

        # --- Price momentum (ROC) ---
        result.update(TechnicalFeatures._rate_of_change(closes))

        # --- Volatility ---
        result.update(TechnicalFeatures._volatility(closes))

        # --- ADX (14-period) ---
        result.update(TechnicalFeatures._adx(highs, lows, closes, 14))

        # --- Support / Resistance ---
        result.update(TechnicalFeatures._support_resistance(highs, lows, closes))

        return result

    # ── Individual indicator implementations ──────────────────────────────

    @staticmethod
    def _rsi(closes: np.ndarray, period: int = 14) -> dict:
        n = len(closes)
        if n < period + 1:
            return {"rsi_14": None}

        deltas = np.diff(closes)
        gains = np.where(deltas > 0, deltas, 0.0)
        losses = np.where(deltas < 0, -deltas, 0.0)

        avg_gain = _wilder_smooth(gains, period)
        avg_loss = _wilder_smooth(losses, period)

        last_gain = avg_gain[-1]
        last_loss = avg_loss[-1]

        if np.isnan(last_gain) or np.isnan(last_loss):
            return {"rsi_14": None}
        if last_loss == 0.0:
            rsi = 100.0
        else:
            rs = last_gain / last_loss
            rsi = 100.0 - (100.0 / (1.0 + rs))

        return {"rsi_14": float(rsi)}

    @staticmethod
    def _macd(closes: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9) -> dict:
        n = len(closes)
        if n < slow + signal:
            return {
                "macd_value": None,
                "macd_signal": None,
                "macd_histogram": None,
            }

        fast_ema = _ema_series(closes, fast)
        slow_ema = _ema_series(closes, slow)
        macd_line = fast_ema - slow_ema

        # Signal line: EMA of valid MACD values
        valid_start = slow - 1
        macd_valid = macd_line[valid_start:]
        signal_ema = _ema_series(macd_valid, signal)

        signal_line = np.full(n, np.nan)
        signal_line[valid_start:] = signal_ema

        histogram = macd_line - signal_line

        def _safe(arr: np.ndarray) -> float | None:
            v = arr[-1]
            return float(v) if not np.isnan(v) else None

        return {
            "macd_value": _safe(macd_line),
            "macd_signal": _safe(signal_line),
            "macd_histogram": _safe(histogram),
        }

    @staticmethod
    def _bollinger(closes: np.ndarray, period: int = 20, num_std: float = 2.0) -> dict:
        n = len(closes)
        if n < period:
            return {
                "bb_upper": None,
                "bb_middle": None,
                "bb_lower": None,
                "bb_percent_b": None,
                "bb_bandwidth": None,
            }

        window = closes[-period:]
        middle = float(np.mean(window))
        sd = float(np.std(window, ddof=0))
        upper = middle + num_std * sd
        lower = middle - num_std * sd

        price = float(closes[-1])
        band_range = upper - lower
        pct_b = (price - lower) / band_range if band_range > 0 else 0.5
        bandwidth = band_range / middle if middle > 0 else 0.0

        return {
            "bb_upper": upper,
            "bb_middle": middle,
            "bb_lower": lower,
            "bb_percent_b": float(pct_b),
            "bb_bandwidth": float(bandwidth),
        }

    @staticmethod
    def _atr(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14) -> dict:
        n = len(closes)
        if n < period + 1:
            return {"atr_14": None}

        # True Range
        prev_close = np.roll(closes, 1)
        prev_close[0] = closes[0]
        tr1 = highs - lows
        tr2 = np.abs(highs - prev_close)
        tr3 = np.abs(lows - prev_close)
        true_range = np.maximum(tr1, np.maximum(tr2, tr3))

        # Wilder's smoothing on TR (skip first bar which has no prev close)
        tr_valid = true_range[1:]
        smoothed = _wilder_smooth(tr_valid, period)

        last = smoothed[-1]
        if np.isnan(last):
            return {"atr_14": None}
        return {"atr_14": float(last)}

    @staticmethod
    def _volume_profile(volumes: np.ndarray) -> dict:
        n = len(volumes)
        result: dict = {}

        # Volume ratio vs 20-day average
        if n >= 20:
            avg_20 = float(np.mean(volumes[-20:]))
            current_vol = float(volumes[-1])
            result["volume_ratio"] = current_vol / avg_20 if avg_20 > 0 else None
        else:
            result["volume_ratio"] = None

        # Volume trend: 5-day slope (linear regression)
        if n >= 5:
            recent = volumes[-5:]
            x = np.arange(5, dtype=np.float64)
            # Normalize to avoid large numbers
            vol_mean = np.mean(recent)
            if vol_mean > 0:
                normalized = recent / vol_mean
                slope = float(np.polyfit(x, normalized, 1)[0])
                result["volume_trend"] = slope
            else:
                result["volume_trend"] = 0.0
        else:
            result["volume_trend"] = None

        return result

    @staticmethod
    def _moving_averages(closes: np.ndarray) -> dict:
        n = len(closes)
        result: dict = {}

        # SMA 20, 50, 200
        for period in (20, 50, 200):
            key = f"sma_{period}"
            if n >= period:
                result[key] = float(np.mean(closes[-period:]))
            else:
                result[key] = None

        # EMA 12, 26
        for period in (12, 26):
            key = f"ema_{period}"
            if n >= period:
                ema = _ema_series(closes, period)
                val = ema[-1]
                result[key] = float(val) if not np.isnan(val) else None
            else:
                result[key] = None

        return result

    @staticmethod
    def _rate_of_change(closes: np.ndarray) -> dict:
        n = len(closes)
        result: dict = {}

        for period in (5, 10, 20):
            key = f"roc_{period}d"
            if n > period:
                prev = closes[-period - 1]
                if prev > 0:
                    result[key] = float((closes[-1] - prev) / prev * 100)
                else:
                    result[key] = None
            else:
                result[key] = None

        return result

    @staticmethod
    def _volatility(closes: np.ndarray) -> dict:
        result: dict = {}

        log_returns = np.diff(np.log(closes[closes > 0]))

        # 20-day realized vol (annualized)
        if len(log_returns) >= 20:
            result["realized_vol_20d"] = float(np.std(log_returns[-20:], ddof=1) * np.sqrt(252))
        else:
            result["realized_vol_20d"] = None

        # 5-day realized vol (annualized)
        if len(log_returns) >= 5:
            result["realized_vol_5d"] = float(np.std(log_returns[-5:], ddof=1) * np.sqrt(252))
        else:
            result["realized_vol_5d"] = None

        # Vol ratio: short-term / long-term
        if result["realized_vol_5d"] is not None and result["realized_vol_20d"] is not None:
            if result["realized_vol_20d"] > 0:
                result["vol_ratio"] = result["realized_vol_5d"] / result["realized_vol_20d"]
            else:
                result["vol_ratio"] = None
        else:
            result["vol_ratio"] = None

        return result

    @staticmethod
    def _adx(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14) -> dict:
        """Average Directional Index — measures trend strength regardless of direction."""
        n = len(closes)
        if n < period * 2 + 1:
            return {"adx_14": None, "plus_di": None, "minus_di": None}

        # Directional movement
        up_move = np.diff(highs)
        down_move = -np.diff(lows)

        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

        # True Range
        prev_close = closes[:-1]
        tr1 = highs[1:] - lows[1:]
        tr2 = np.abs(highs[1:] - prev_close)
        tr3 = np.abs(lows[1:] - prev_close)
        true_range = np.maximum(tr1, np.maximum(tr2, tr3))

        # Wilder's smoothing
        smooth_tr = _wilder_smooth(true_range, period)
        smooth_plus_dm = _wilder_smooth(plus_dm, period)
        smooth_minus_dm = _wilder_smooth(minus_dm, period)

        # Directional indicators
        # Avoid division by zero
        with np.errstate(divide="ignore", invalid="ignore"):
            plus_di = np.where(smooth_tr > 0, 100.0 * smooth_plus_dm / smooth_tr, 0.0)
            minus_di = np.where(smooth_tr > 0, 100.0 * smooth_minus_dm / smooth_tr, 0.0)

        # DX
        di_sum = plus_di + minus_di
        with np.errstate(divide="ignore", invalid="ignore"):
            dx = np.where(di_sum > 0, 100.0 * np.abs(plus_di - minus_di) / di_sum, 0.0)

        # ADX = Wilder smooth of DX
        # Only compute from valid DX values (after period warmup)
        valid_dx = dx[~np.isnan(dx)]
        if len(valid_dx) < period:
            return {"adx_14": None, "plus_di": None, "minus_di": None}

        adx_series = _wilder_smooth(valid_dx, period)
        last_adx = adx_series[-1]
        last_plus = plus_di[~np.isnan(plus_di)]
        last_minus = minus_di[~np.isnan(minus_di)]

        return {
            "adx_14": float(last_adx) if not np.isnan(last_adx) else None,
            "plus_di": float(last_plus[-1]) if len(last_plus) > 0 and not np.isnan(last_plus[-1]) else None,
            "minus_di": float(last_minus[-1]) if len(last_minus) > 0 and not np.isnan(last_minus[-1]) else None,
        }

    @staticmethod
    def _support_resistance(
        highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, lookback: int = 50,
    ) -> dict:
        """Identify recent swing highs/lows as support and resistance levels."""
        n = len(closes)
        window = min(n, lookback)
        if window < 5:
            return {
                "resistance_1": None,
                "resistance_2": None,
                "support_1": None,
                "support_2": None,
            }

        h = highs[-window:]
        lo = lows[-window:]

        # Swing highs: bars where high > both neighbors
        swing_highs: list[float] = []
        swing_lows: list[float] = []

        for i in range(1, len(h) - 1):
            if h[i] > h[i - 1] and h[i] > h[i + 1]:
                swing_highs.append(float(h[i]))
            if lo[i] < lo[i - 1] and lo[i] < lo[i + 1]:
                swing_lows.append(float(lo[i]))

        # Sort and pick nearest levels above/below current price
        current_price = float(closes[-1])

        resistances = sorted([p for p in swing_highs if p > current_price])
        supports = sorted([p for p in swing_lows if p < current_price], reverse=True)

        return {
            "resistance_1": resistances[0] if len(resistances) >= 1 else None,
            "resistance_2": resistances[1] if len(resistances) >= 2 else None,
            "support_1": supports[0] if len(supports) >= 1 else None,
            "support_2": supports[1] if len(supports) >= 2 else None,
        }
