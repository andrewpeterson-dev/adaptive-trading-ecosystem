"""
Technical indicator calculations from OHLCV bar data.

Pure Python/numpy implementations — no ta-lib or pandas_ta dependency.
"""

from __future__ import annotations

from typing import Any

import numpy as np


def _closes(bars: list[dict]) -> np.ndarray:
    return np.array([b["close"] for b in bars], dtype=np.float64)


def _highs(bars: list[dict]) -> np.ndarray:
    return np.array([b["high"] for b in bars], dtype=np.float64)


def _lows(bars: list[dict]) -> np.ndarray:
    return np.array([b["low"] for b in bars], dtype=np.float64)


def _volumes(bars: list[dict]) -> np.ndarray:
    return np.array([b["volume"] for b in bars], dtype=np.float64)


# ── Individual indicator functions ───────────────────────────────────────


def _rsi(closes: np.ndarray, period: int = 14) -> tuple[float, float]:
    """Return (current RSI, previous RSI)."""
    if len(closes) < period + 2:
        return (float("nan"), float("nan"))

    deltas = np.diff(closes)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)

    # Wilder's smoothed moving average (exponential)
    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])

    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    # We need the previous value too — recompute stopping one bar earlier
    avg_gain_prev = np.mean(gains[:period])
    avg_loss_prev = np.mean(losses[:period])
    for i in range(period, len(gains) - 1):
        avg_gain_prev = (avg_gain_prev * (period - 1) + gains[i]) / period
        avg_loss_prev = (avg_loss_prev * (period - 1) + losses[i]) / period

    def _calc(ag: float, al: float) -> float:
        if al == 0:
            return 100.0
        rs = ag / al
        return 100.0 - (100.0 / (1.0 + rs))

    return (_calc(avg_gain, avg_loss), _calc(avg_gain_prev, avg_loss_prev))


def _sma(closes: np.ndarray, period: int = 20) -> tuple[float, float]:
    """Return (current SMA, previous SMA)."""
    if len(closes) < period + 1:
        return (float("nan"), float("nan"))
    current = float(np.mean(closes[-period:]))
    previous = float(np.mean(closes[-period - 1 : -1]))
    return (current, previous)


def _ema(closes: np.ndarray, period: int = 20) -> tuple[float, float]:
    """Return (current EMA, previous EMA)."""
    if len(closes) < period + 1:
        return (float("nan"), float("nan"))

    multiplier = 2.0 / (period + 1)
    ema_val = float(np.mean(closes[:period]))  # seed with SMA

    prev_ema = ema_val
    for i in range(period, len(closes)):
        prev_ema = ema_val
        ema_val = (closes[i] - ema_val) * multiplier + ema_val

    return (ema_val, prev_ema)


def _ema_series(closes: np.ndarray, period: int) -> np.ndarray:
    """Return full EMA series (same length as closes, NaN-padded at start)."""
    result = np.full(len(closes), float("nan"))
    if len(closes) < period:
        return result

    multiplier = 2.0 / (period + 1)
    result[period - 1] = float(np.mean(closes[:period]))
    for i in range(period, len(closes)):
        result[i] = (closes[i] - result[i - 1]) * multiplier + result[i - 1]
    return result


def _macd(
    closes: np.ndarray,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> dict[str, float]:
    """Return MACD dict with current and previous values."""
    if len(closes) < slow + signal:
        return {
            "macd": float("nan"),
            "signal": float("nan"),
            "histogram": float("nan"),
            "prev_macd": float("nan"),
            "prev_signal": float("nan"),
            "prev_histogram": float("nan"),
        }

    fast_ema = _ema_series(closes, fast)
    slow_ema = _ema_series(closes, slow)
    macd_line = fast_ema - slow_ema

    # Signal line = EMA of MACD line
    # Find first valid MACD value
    valid_start = slow - 1
    macd_valid = macd_line[valid_start:]
    signal_ema = _ema_series(macd_valid, signal)

    # Map back
    signal_line = np.full(len(closes), float("nan"))
    signal_line[valid_start:] = signal_ema

    histogram = macd_line - signal_line

    return {
        "macd": float(macd_line[-1]),
        "signal": float(signal_line[-1]),
        "histogram": float(histogram[-1]),
        "prev_macd": float(macd_line[-2]) if len(macd_line) >= 2 else float("nan"),
        "prev_signal": float(signal_line[-2]) if len(signal_line) >= 2 else float("nan"),
        "prev_histogram": float(histogram[-2]) if len(histogram) >= 2 else float("nan"),
    }


def _bbands(
    closes: np.ndarray, period: int = 20, std: float = 2.0
) -> dict[str, float]:
    """Return Bollinger Bands (upper, middle, lower) with prev values."""
    if len(closes) < period + 1:
        return {
            "upper": float("nan"),
            "middle": float("nan"),
            "lower": float("nan"),
            "prev_upper": float("nan"),
            "prev_middle": float("nan"),
            "prev_lower": float("nan"),
        }

    middle = float(np.mean(closes[-period:]))
    sd = float(np.std(closes[-period:], ddof=0))

    prev_middle = float(np.mean(closes[-period - 1 : -1]))
    prev_sd = float(np.std(closes[-period - 1 : -1], ddof=0))

    return {
        "upper": middle + std * sd,
        "middle": middle,
        "lower": middle - std * sd,
        "prev_upper": prev_middle + std * prev_sd,
        "prev_middle": prev_middle,
        "prev_lower": prev_middle - std * prev_sd,
    }


def _atr(bars: list[dict], period: int = 14) -> tuple[float, float]:
    """Return (current ATR, previous ATR)."""
    if len(bars) < period + 2:
        return (float("nan"), float("nan"))

    highs = _highs(bars)
    lows = _lows(bars)
    closes = _closes(bars)

    true_ranges = np.zeros(len(bars) - 1)
    for i in range(1, len(bars)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        true_ranges[i - 1] = tr

    # Wilder's smoothing
    atr_val = float(np.mean(true_ranges[:period]))
    prev_atr = atr_val
    for i in range(period, len(true_ranges)):
        prev_atr = atr_val
        atr_val = (atr_val * (period - 1) + true_ranges[i]) / period

    return (atr_val, prev_atr)


def _stochastic(
    bars: list[dict], k_period: int = 14, d_period: int = 3
) -> dict[str, float]:
    """Return Stochastic %K and %D with previous values."""
    if len(bars) < k_period + d_period:
        return {
            "k": float("nan"),
            "d": float("nan"),
            "prev_k": float("nan"),
            "prev_d": float("nan"),
        }

    highs = _highs(bars)
    lows = _lows(bars)
    closes = _closes(bars)

    # Compute raw %K for all valid windows
    k_values = []
    for i in range(k_period - 1, len(bars)):
        window_high = np.max(highs[i - k_period + 1 : i + 1])
        window_low = np.min(lows[i - k_period + 1 : i + 1])
        if window_high == window_low:
            k_values.append(50.0)
        else:
            k_values.append(
                100.0 * (closes[i] - window_low) / (window_high - window_low)
            )

    k_arr = np.array(k_values)

    # %D = SMA of %K
    if len(k_arr) < d_period + 1:
        return {
            "k": float(k_arr[-1]) if len(k_arr) > 0 else float("nan"),
            "d": float("nan"),
            "prev_k": float(k_arr[-2]) if len(k_arr) > 1 else float("nan"),
            "prev_d": float("nan"),
        }

    d_current = float(np.mean(k_arr[-d_period:]))
    d_prev = float(np.mean(k_arr[-d_period - 1 : -1]))

    return {
        "k": float(k_arr[-1]),
        "d": d_current,
        "prev_k": float(k_arr[-2]),
        "prev_d": d_prev,
    }


def _vwap(bars: list[dict]) -> tuple[float, float]:
    """Return (current VWAP, previous VWAP) for the session."""
    if len(bars) < 2:
        return (float("nan"), float("nan"))

    # Cumulative VWAP
    cum_vol = 0.0
    cum_tp_vol = 0.0
    prev_vwap = float("nan")

    for i, bar in enumerate(bars):
        tp = (bar["high"] + bar["low"] + bar["close"]) / 3.0
        vol = bar["volume"]
        cum_vol += vol
        cum_tp_vol += tp * vol
        if i == len(bars) - 2 and cum_vol > 0:
            prev_vwap = cum_tp_vol / cum_vol

    current_vwap = cum_tp_vol / cum_vol if cum_vol > 0 else float("nan")
    return (current_vwap, prev_vwap)


# ── Main entry point ─────────────────────────────────────────────────────


def compute_indicators(
    bars: list[dict], indicators_needed: list[dict]
) -> dict[str, Any]:
    """
    Compute requested indicators from OHLCV bars.

    Parameters
    ----------
    bars : list[dict]
        OHLCV bars with keys: open, high, low, close, volume, time.
    indicators_needed : list[dict]
        Each dict has ``indicator`` (str) and ``params`` (dict).
        Example: [{"indicator": "RSI", "params": {"period": 14}}, ...]

    Returns
    -------
    dict mapping indicator key to its value(s).
        Scalars: ``{"RSI_14": 45.2, "SMA_20": 150.3}``
        Composite: ``{"MACD": {"macd": 1.2, "signal": 0.8, ...}}``

    Each entry also stores ``_prev`` suffixed keys for crossover detection.
    """
    if not bars:
        return {}

    closes = _closes(bars)
    result: dict[str, Any] = {}
    seen: set[str] = set()

    for spec in indicators_needed:
        name = spec["indicator"].upper()
        params = spec.get("params") or {}

        if name == "RSI":
            period = int(params.get("period", 14))
            key = f"RSI_{period}"
            if key not in seen:
                cur, prev = _rsi(closes, period)
                result[key] = cur
                result[f"{key}_prev"] = prev
                seen.add(key)

        elif name == "SMA":
            period = int(params.get("period", 20))
            key = f"SMA_{period}"
            if key not in seen:
                cur, prev = _sma(closes, period)
                result[key] = cur
                result[f"{key}_prev"] = prev
                seen.add(key)

        elif name == "EMA":
            period = int(params.get("period", 20))
            key = f"EMA_{period}"
            if key not in seen:
                cur, prev = _ema(closes, period)
                result[key] = cur
                result[f"{key}_prev"] = prev
                seen.add(key)

        elif name == "MACD":
            fast = int(params.get("fast", 12))
            slow = int(params.get("slow", 26))
            signal = int(params.get("signal", 9))
            key = "MACD"
            if key not in seen:
                result[key] = _macd(closes, fast, slow, signal)
                seen.add(key)

        elif name == "BBANDS":
            period = int(params.get("period", 20))
            std = float(params.get("std", 2.0))
            key = "BBANDS"
            if key not in seen:
                result[key] = _bbands(closes, period, std)
                seen.add(key)

        elif name == "ATR":
            period = int(params.get("period", 14))
            key = f"ATR_{period}"
            if key not in seen:
                cur, prev = _atr(bars, period)
                result[key] = cur
                result[f"{key}_prev"] = prev
                seen.add(key)

        elif name == "STOCHASTIC":
            k_period = int(params.get("k_period", 14))
            d_period = int(params.get("d_period", 3))
            key = "STOCHASTIC"
            if key not in seen:
                result[key] = _stochastic(bars, k_period, d_period)
                seen.add(key)

        elif name == "VWAP":
            key = "VWAP"
            if key not in seen:
                cur, prev = _vwap(bars)
                result[key] = cur
                result[f"{key}_prev"] = prev
                seen.add(key)

        elif name == "VOLUME":
            key = "VOLUME"
            if key not in seen:
                result[key] = float(bars[-1]["volume"])
                result[f"{key}_prev"] = float(bars[-2]["volume"]) if len(bars) >= 2 else float("nan")
                seen.add(key)

    return result
