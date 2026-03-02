"""
Free market data via yfinance.
Provides real quotes, historical bars, and watchlist data.
No API keys required.
"""

from __future__ import annotations

import yfinance as yf
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta


@st.cache_data(ttl=30)
def get_quote(symbol: str) -> "dict | None":
    """Get current quote for a symbol. Returns dict or None on error."""
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.fast_info
        return {
            "symbol": symbol.upper(),
            "price": info.get("lastPrice", info.get("previousClose", 0)),
            "previous_close": info.get("previousClose", 0),
            "open": info.get("open", 0),
            "day_high": info.get("dayHigh", 0),
            "day_low": info.get("dayLow", 0),
            "volume": info.get("lastVolume", 0),
            "market_cap": info.get("marketCap", 0),
        }
    except Exception:
        return None


@st.cache_data(ttl=30)
def get_watchlist_quotes(symbols: list[str]) -> pd.DataFrame:
    """Get quotes for multiple symbols. Returns DataFrame."""
    rows = []
    for sym in symbols:
        q = get_quote(sym)
        if q:
            price = q["price"]
            prev = q["previous_close"]
            change = price - prev if prev else 0
            change_pct = (change / prev * 100) if prev else 0
            rows.append({
                "Symbol": sym.upper(),
                "Price": price,
                "Change": change,
                "Change %": change_pct,
                "Volume": q["volume"],
                "Day High": q["day_high"],
                "Day Low": q["day_low"],
            })
    return pd.DataFrame(rows) if rows else pd.DataFrame()


@st.cache_data(ttl=60)
def get_historical_bars(symbol: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
    """
    Get historical OHLCV bars.
    period: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, max
    interval: 1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo
    """
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period, interval=interval)
        if df.empty:
            return pd.DataFrame()
        df = df.reset_index()
        df.columns = [c.lower().replace(" ", "_") for c in df.columns]
        # Standardize column names
        rename_map = {"date": "timestamp", "datetime": "timestamp"}
        df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
        df["symbol"] = symbol.upper()
        return df[["timestamp", "symbol", "open", "high", "low", "close", "volume"]]
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=30)
def get_current_price(symbol: str) -> float:
    """Get just the current price for a symbol. Returns 0.0 on error."""
    q = get_quote(symbol)
    return q["price"] if q else 0.0


# Default watchlist with stocks + crypto
DEFAULT_WATCHLIST = [
    "SPY", "QQQ", "AAPL", "TSLA", "NVDA", "MSFT", "AMZN", "META",
    "BTC-USD", "ETH-USD", "SOL-USD",
]
