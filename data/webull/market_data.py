"""
Webull market data client — quotes and bars only.

NOTE: Per Webull API docs, HTTP market-data requests are NOT supported.
Real-time data must be consumed via the documented push/WebSocket hosts:
  Trading events: wss://events-api.webull.com/
  Market quotes:  wss://usquotes-api.webullfintech.com/

This client exposes push_events_host and push_quotes_host as properties
for callers that want to set up streaming connections.

For historical/snapshot data:
  get_quote()  — tries official SDK trade_instrument endpoint (if connected),
                 falls back to unofficial webull SDK (no auth required)
  get_bars()   — unofficial webull SDK only (works without auth for US stocks)
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import TYPE_CHECKING, Optional, TypedDict

import pandas as pd
import structlog

if TYPE_CHECKING:
    from .config import _SDKHandle

logger = structlog.get_logger(__name__)

_QUOTE_CACHE_TTL_SECS = 2


class Quote(TypedDict):
    symbol:     str
    price:      float
    open:       float
    high:       float
    low:        float
    close:      float
    volume:     int
    change:     float
    change_pct: float
    bid:        float
    ask:        float
    prev_close: float
    timestamp:  str


class MarketDataClient:
    """
    Market data client — quotes and OHLCV bars.
    No order placement or account read capability.
    Mode-independent for data purposes; shares the same SDK connection.
    """

    def __init__(self, handle: _SDKHandle) -> None:
        self._h = handle
        self._quote_cache: dict[str, dict] = {}

    # ── Push host accessors (for callers wiring WebSocket streams) ────────

    @property
    def push_events_host(self) -> str:
        """Documented push host for trading event alerts (WebSocket)."""
        return self._h.env.push_events_host

    @property
    def push_quotes_host(self) -> str:
        """Documented push host for real-time market quotes/news (WebSocket)."""
        return self._h.env.push_quotes_host

    # ── Internal ──────────────────────────────────────────────────────────

    def _ensure_connected(self) -> bool:
        if not self._h.connected:
            result = self._h.connect()
            return result.get("success", False)
        return True

    # ── Quotes ────────────────────────────────────────────────────────────

    def get_quote(self, symbol: str) -> Optional[Quote]:
        """
        Fetch current snapshot quote for a symbol.

        Strategy:
          1. Return cached value if fresher than 2 seconds.
          2. Try official SDK trade_instrument endpoint (requires connected SDK).
          3. Fall back to unofficial webull SDK (no auth, works for US equities).
        """
        cached = self._quote_cache.get(symbol)
        if cached and (time.time() - cached["ts"]) < _QUOTE_CACHE_TTL_SECS:
            return cached["data"]

        # Attempt official SDK
        if self._ensure_connected() and self._h.api:
            try:
                inst_id = self._h.get_instrument_id(symbol)
                if inst_id:
                    resp = self._h.api.trade_instrument.get_trade_instrument_detail(inst_id)
                    if resp.status_code == 200:
                        raw  = resp.json()
                        data = raw.get("data", raw) if isinstance(raw, dict) else raw
                        quote = self._parse_official_quote(symbol, data)
                        self._quote_cache[symbol] = {"data": quote, "ts": time.time()}
                        return quote
            except Exception as exc:
                logger.warning("official_quote_failed", symbol=symbol, error=str(exc))

        # Fall back to unofficial SDK
        return self._quote_unofficial(symbol)

    def get_quotes(self, symbols: list[str]) -> dict[str, Quote]:
        """Fetch quotes for multiple symbols. Omits symbols that fail."""
        return {sym: q for sym in symbols if (q := self.get_quote(sym)) is not None}

    # ── Bars ──────────────────────────────────────────────────────────────

    def get_bars(
        self,
        symbol: str,
        interval: str = "m5",
        count: int = 200,
    ) -> Optional[pd.DataFrame]:
        """
        Fetch OHLCV bars via unofficial webull SDK.

        Args:
            symbol:   Ticker symbol, e.g. "AAPL".
            interval: Bar interval. Common values: "m1", "m5", "m15", "m30",
                      "h1", "h2", "h4", "d1", "w1".
            count:    Number of bars to fetch (max ~1200 for daily).

        Returns:
            DataFrame with columns: timestamp, symbol, open, high, low, close, volume
            or None on failure.
        """
        try:
            from webull import webull
            wb  = webull()
            raw = wb.get_bars(symbol, interval=interval, count=count)

            if raw is None or (isinstance(raw, pd.DataFrame) and raw.empty):
                return None

            df = raw.copy() if isinstance(raw, pd.DataFrame) else pd.DataFrame(raw)

            # Normalize column names
            rename: dict[str, str] = {}
            for col in df.columns:
                lc = col.lower()
                if "open" in lc:
                    rename[col] = "open"
                elif "high" in lc:
                    rename[col] = "high"
                elif "low" in lc:
                    rename[col] = "low"
                elif "close" in lc:
                    rename[col] = "close"
                elif "vol" in lc:
                    rename[col] = "volume"
                elif "time" in lc or "date" in lc:
                    rename[col] = "timestamp"

            df = df.rename(columns=rename)
            df["symbol"] = symbol

            for col in ("open", "high", "low", "close", "volume"):
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")

            return df

        except Exception as exc:
            logger.error("bars_fetch_failed", symbol=symbol, interval=interval, error=str(exc))
            return None

    def get_bars_as_model_input(
        self,
        symbol: str,
        days: int = 500,
    ) -> Optional[pd.DataFrame]:
        """
        Daily bars formatted for ML model ingestion.

        Returns DataFrame with columns:
          timestamp, symbol, open, high, low, close, volume
        or None if data is unavailable.
        """
        df = self.get_bars(symbol, interval="d1", count=min(days, 1200))
        if df is None or df.empty:
            return None

        required = {"open", "high", "low", "close", "volume"}
        if not required.issubset(df.columns):
            return None

        if "timestamp" not in df.columns:
            df["timestamp"] = pd.date_range(
                end=datetime.now(), periods=len(df), freq="B"
            )

        return df[["timestamp", "symbol", "open", "high", "low", "close", "volume"]]

    def get_watchlist_quotes(
        self,
        symbols: Optional[list[str]] = None,
    ) -> pd.DataFrame:
        """Fetch quotes for a watchlist and return as a display-ready DataFrame."""
        if symbols is None:
            symbols = ["SPY", "QQQ", "AAPL", "TSLA", "NVDA", "MSFT", "AMZN", "META"]

        rows = []
        for sym in symbols:
            q = self.get_quote(sym)
            if q:
                rows.append({
                    "Symbol":   q["symbol"],
                    "Price":    q["price"],
                    "Change":   q.get("change", 0.0),
                    "Change %": q.get("change_pct", 0.0),
                    "Volume":   q.get("volume", 0),
                    "Bid":      q.get("bid", 0.0),
                    "Ask":      q.get("ask", 0.0),
                })

        return pd.DataFrame(rows) if rows else pd.DataFrame()

    # ── Private helpers ───────────────────────────────────────────────────

    @staticmethod
    def _parse_official_quote(symbol: str, data: dict) -> Quote:
        return Quote(
            symbol=symbol,
            price=float(data.get("close", data.get("lastPrice", 0))),
            open=float(data.get("open", 0)),
            high=float(data.get("high", 0)),
            low=float(data.get("low", 0)),
            close=float(data.get("close", data.get("lastPrice", 0))),
            volume=int(float(data.get("volume", 0))),
            change=float(data.get("change", 0)),
            change_pct=float(
                data.get("changeRatio", data.get("changePct", 0))
            ) * 100,
            bid=float(data.get("bidPrice", 0) or 0),
            ask=float(data.get("askPrice", 0) or 0),
            prev_close=float(data.get("preClose", 0)),
            timestamp=datetime.now().isoformat(),
        )

    def _quote_unofficial(self, symbol: str) -> Optional[Quote]:
        try:
            from webull import webull
            wb  = webull()
            raw = wb.get_quote(symbol)
            if not raw:
                return None

            quote = Quote(
                symbol=symbol,
                price=float(raw.get("close", 0)),
                open=float(raw.get("open", 0)),
                high=float(raw.get("high", 0)),
                low=float(raw.get("low", 0)),
                close=float(raw.get("close", 0)),
                volume=int(float(raw.get("volume", 0))),
                change=float(raw.get("change", 0)),
                change_pct=float(raw.get("changeRatio", 0)) * 100,
                bid=float(raw.get("bidPrice", 0) or 0),
                ask=float(raw.get("askPrice", 0) or 0),
                prev_close=float(raw.get("preClose", 0)),
                timestamp=datetime.now().isoformat(),
            )
            self._quote_cache[symbol] = {"data": quote, "ts": time.time()}
            return quote

        except Exception as exc:
            logger.error("unofficial_quote_failed", symbol=symbol, error=str(exc))
            return None
