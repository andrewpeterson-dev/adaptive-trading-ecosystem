"""
OHLCV data fetching and caching for the backtesting engine.

Uses yfinance for historical data with a file-based cache to avoid
repeated downloads.  Supports daily and common intraday timeframes.
"""
from __future__ import annotations

import hashlib
import os
import time
from pathlib import Path
from typing import Optional

import pandas as pd
import structlog

logger = structlog.get_logger(__name__)

# Cache directory lives inside the project data/ folder
_CACHE_DIR = Path(os.environ.get(
    "BACKTEST_CACHE_DIR",
    str(Path(__file__).resolve().parents[2] / "data" / "backtest_cache"),
))

# How long a cache entry is considered fresh (seconds)
_CACHE_TTL: int = int(os.environ.get("BACKTEST_CACHE_TTL", str(4 * 3600)))  # 4 hours

# Mapping from our canonical timeframes to yfinance interval strings
_YF_INTERVAL_MAP = {
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
    "1H": "1h",
    "4H": "1h",   # fetch 1h, resample later
    "1D": "1d",
    "1W": "1wk",
}

# yfinance max period strings keyed by interval
_YF_PERIOD_MAP = {
    "1m": "7d",
    "5m": "60d",
    "15m": "60d",
    "1h": "730d",
    "1d": "max",
    "1wk": "max",
}


def _cache_key(symbol: str, timeframe: str, lookback_days: int) -> str:
    raw = f"{symbol.upper()}|{timeframe}|{lookback_days}"
    return hashlib.md5(raw.encode()).hexdigest()


def _cache_path(symbol: str, timeframe: str, lookback_days: int) -> Path:
    return _CACHE_DIR / f"{_cache_key(symbol, timeframe, lookback_days)}.parquet"


def _is_cache_fresh(path: Path) -> bool:
    if not path.exists():
        return False
    age = time.time() - path.stat().st_mtime
    return age < _CACHE_TTL


def fetch_ohlcv(
    symbol: str,
    timeframe: str = "1D",
    lookback_days: int = 252,
    force_refresh: bool = False,
) -> pd.DataFrame:
    """
    Fetch OHLCV data for *symbol* at *timeframe* resolution.

    Returns a DataFrame with columns:
        open, high, low, close, volume
    and a DatetimeIndex.

    Results are cached to parquet on disk.
    """
    import yfinance as yf

    symbol = symbol.upper()
    tf = timeframe if timeframe in _YF_INTERVAL_MAP else "1D"
    yf_interval = _YF_INTERVAL_MAP[tf]

    cache = _cache_path(symbol, tf, lookback_days)
    if not force_refresh and _is_cache_fresh(cache):
        logger.debug("backtest_data_cache_hit", symbol=symbol, timeframe=tf)
        df = pd.read_parquet(cache)
        if not df.empty:
            return df

    logger.info("backtest_data_fetch", symbol=symbol, timeframe=tf, lookback_days=lookback_days)

    # Determine period
    yf_period = _YF_PERIOD_MAP.get(yf_interval, "max")
    ticker = yf.Ticker(symbol)
    raw: pd.DataFrame = ticker.history(period=yf_period, interval=yf_interval)

    if raw.empty:
        logger.warning("backtest_data_empty", symbol=symbol, timeframe=tf)
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

    # Normalise column names
    raw.columns = [c.lower().replace(" ", "_") for c in raw.columns]
    keep_cols = ["open", "high", "low", "close", "volume"]
    for col in keep_cols:
        if col not in raw.columns:
            raw[col] = 0.0
    df = raw[keep_cols].copy()
    df.index = pd.to_datetime(df.index, utc=True)
    df = df.sort_index()

    # Resample 1h -> 4h if needed
    if tf == "4H":
        df = (
            df.resample("4h")
            .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
            .dropna()
        )

    # Trim to lookback
    if tf in {"1D", "1W"}:
        n_rows = int(lookback_days * 1.5) if tf == "1D" else int(lookback_days / 5)
        df = df.tail(max(n_rows, 50))
    else:
        df = df.tail(max(lookback_days * 7, 200))

    # Persist cache
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = cache.with_suffix(".tmp")
    df.to_parquet(tmp)
    tmp.rename(cache)  # atomic on POSIX

    logger.info("backtest_data_fetched", symbol=symbol, rows=len(df))
    return df


def clear_cache(symbol: Optional[str] = None) -> int:
    """Remove cached files.  If *symbol* is None, clear entire cache."""
    removed = 0
    if not _CACHE_DIR.exists():
        return removed
    for f in _CACHE_DIR.glob("*.parquet"):
        if symbol is None or symbol.upper() in f.stem:
            f.unlink(missing_ok=True)
            removed += 1
    return removed
