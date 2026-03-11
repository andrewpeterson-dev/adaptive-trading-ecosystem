"""
MarketDataService — fetches, normalizes, and caches market data.

Fallback chain per operation:
  quote:  yFinance → Alpaca → Finnhub
  bars:   yFinance → Alpaca

Redis cache keys:
  market:price:{SYMBOL}          TTL 5 s  (live quote)
  market:bars:{SYMBOL}:{tf}      TTL 60 s (OHLCV bars)
"""

import asyncio
import json
import time
from typing import Optional

import structlog
try:
    import redis.asyncio as aioredis
except ImportError:  # pragma: no cover - optional dependency in test/dev
    aioredis = None

from config.settings import get_settings

logger = structlog.get_logger(__name__)

# Unified quote schema
QuoteDict = dict  # {symbol, price, bid, ask, volume, change, change_pct, timestamp}


def _redis_client():
    if aioredis is None:
        return None
    settings = get_settings()
    return aioredis.from_url(settings.redis_url, decode_responses=True)


# ── Normalizers ──────────────────────────────────────────────────────────────

def _norm_yf_quote(symbol: str, info: dict) -> QuoteDict:
    price = info.get("currentPrice") or info.get("regularMarketPrice") or info.get("ask") or 0.0
    prev = info.get("regularMarketPreviousClose") or info.get("previousClose") or price
    change = price - prev
    change_pct = (change / prev * 100) if prev else 0.0
    return {
        "symbol": symbol,
        "price": float(price),
        "bid": float(info.get("bid") or price),
        "ask": float(info.get("ask") or price),
        "volume": int(info.get("regularMarketVolume") or info.get("volume") or 0),
        "change": round(change, 4),
        "change_pct": round(change_pct, 4),
        "timestamp": int(time.time()),
        "source": "yfinance",
    }


def _norm_finnhub_quote(symbol: str, data: dict) -> QuoteDict:
    price = float(data.get("c") or 0)
    prev = float(data.get("pc") or price)
    change = price - prev
    change_pct = (change / prev * 100) if prev else 0.0
    return {
        "symbol": symbol,
        "price": price,
        "bid": float(data.get("b") or price),
        "ask": float(data.get("a") or price),
        "volume": 0,
        "change": round(change, 4),
        "change_pct": round(change_pct, 4),
        "timestamp": int(data.get("t") or time.time()),
        "source": "finnhub",
    }


def _norm_alpaca_quote(symbol: str, data) -> QuoteDict:
    """Normalize an Alpaca LatestTrade or LatestQuote object."""
    price = float(getattr(data, "price", 0) or getattr(data, "close", 0) or 0)
    return {
        "symbol": symbol,
        "price": price,
        "bid": float(getattr(data, "bid_price", price) or price),
        "ask": float(getattr(data, "ask_price", price) or price),
        "volume": int(getattr(data, "volume", 0) or 0),
        "change": 0.0,
        "change_pct": 0.0,
        "timestamp": int(time.time()),
        "source": "alpaca",
    }


# ── Fetchers ─────────────────────────────────────────────────────────────────

async def _yf_quote(symbol: str) -> Optional[QuoteDict]:
    try:
        import yfinance as yf
        ticker = await asyncio.get_event_loop().run_in_executor(
            None, lambda: yf.Ticker(symbol)
        )
        info = await asyncio.get_event_loop().run_in_executor(None, lambda: ticker.fast_info)
        price = float(getattr(info, "last_price", None) or getattr(info, "regular_market_price", None) or 0)
        if not price:
            return None
        prev = float(getattr(info, "previous_close", None) or price)
        change = price - prev
        change_pct = (change / prev * 100) if prev else 0.0
        return {
            "symbol": symbol,
            "price": price,
            "bid": price,
            "ask": price,
            "volume": int(getattr(info, "three_month_average_volume", 0) or 0),
            "change": round(change, 4),
            "change_pct": round(change_pct, 4),
            "timestamp": int(time.time()),
            "source": "yfinance",
        }
    except Exception as e:
        logger.debug("yf_quote_failed", symbol=symbol, error=str(e))
        return None


async def _alpaca_quote(symbol: str) -> Optional[QuoteDict]:
    try:
        settings = get_settings()
        if not settings.alpaca_api_key:
            return None
        from alpaca.data import StockHistoricalDataClient
        from alpaca.data.requests import StockLatestTradeRequest
        client = StockHistoricalDataClient(settings.alpaca_api_key, settings.alpaca_secret_key)
        req = StockLatestTradeRequest(symbol_or_symbols=symbol)
        trades = await asyncio.get_event_loop().run_in_executor(
            None, lambda: client.get_stock_latest_trade(req)
        )
        trade = trades.get(symbol)
        if not trade:
            return None
        return _norm_alpaca_quote(symbol, trade)
    except Exception as e:
        logger.debug("alpaca_quote_failed", symbol=symbol, error=str(e))
        return None


async def _finnhub_quote(symbol: str) -> Optional[QuoteDict]:
    try:
        settings = get_settings()
        if not settings.finnhub_api_key:
            return None
        import httpx
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(
                "https://finnhub.io/api/v1/quote",
                params={"symbol": symbol, "token": settings.finnhub_api_key},
            )
            if resp.status_code == 429:
                logger.warning("finnhub_rate_limited", symbol=symbol)
                return None
            if resp.status_code != 200:
                logger.debug("finnhub_bad_status", symbol=symbol, status=resp.status_code)
                return None
            data = resp.json()
        if not data.get("c"):
            return None
        return _norm_finnhub_quote(symbol, data)
    except Exception as e:
        logger.debug("finnhub_quote_failed", symbol=symbol, error=str(e))
        return None


async def _yf_bars(symbol: str, timeframe: str = "1D", limit: int = 100) -> Optional[list]:
    """Fetch OHLCV bars via yFinance. timeframe: 1m, 5m, 15m, 1h, 1D."""
    timeframe = {
        "1m": "1m",
        "m1": "1m",
        "5m": "5m",
        "m5": "5m",
        "15m": "15m",
        "m15": "15m",
        "30m": "30m",
        "m30": "30m",
        "1h": "1h",
        "1H": "1h",
        "h1": "1h",
        "4h": "1h",
        "4H": "1h",
        "h4": "1h",
        "1d": "1D",
        "1D": "1D",
        "d1": "1D",
        "1w": "1W",
        "1W": "1W",
        "w1": "1W",
    }.get(timeframe, timeframe)
    _tf_map = {"1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
               "1h": "1h", "4h": "1h", "1D": "1d", "1W": "1wk"}
    yf_interval = _tf_map.get(timeframe, "1d")
    period_map = {"1m": "1d", "5m": "5d", "15m": "5d", "30m": "1mo",
                  "1h": "1mo", "4h": "3mo", "1d": "1y", "1wk": "2y"}
    yf_period = period_map.get(yf_interval, "1y")
    try:
        import yfinance as yf
        df = await asyncio.get_event_loop().run_in_executor(
            None, lambda: yf.download(symbol, period=yf_period, interval=yf_interval,
                                       progress=False, auto_adjust=True)
        )
        if df is None or df.empty:
            return None
        df = df.tail(limit)
        bars = []
        for ts, row in df.iterrows():
            def _v(x):
                import pandas as pd
                return x.iloc[0] if isinstance(x, pd.Series) else x
            bars.append({
                "t": int(ts.timestamp()),
                "o": float(_v(row["Open"])),
                "h": float(_v(row["High"])),
                "l": float(_v(row["Low"])),
                "c": float(_v(row["Close"])),
                "v": int(_v(row.get("Volume", 0)) or 0),
            })
        return bars
    except Exception as e:
        logger.debug("yf_bars_failed", symbol=symbol, error=str(e))
        return None


async def _alpaca_bars(symbol: str, timeframe: str = "1D", limit: int = 100) -> Optional[list]:
    try:
        settings = get_settings()
        if not settings.alpaca_api_key:
            return None
        from alpaca.data import StockHistoricalDataClient
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
        _tf_map = {"1m": TimeFrame(1, TimeFrameUnit.Minute),
                   "5m": TimeFrame(5, TimeFrameUnit.Minute),
                   "15m": TimeFrame(15, TimeFrameUnit.Minute),
                   "1h": TimeFrame(1, TimeFrameUnit.Hour),
                   "1D": TimeFrame(1, TimeFrameUnit.Day)}
        tf = _tf_map.get(timeframe, TimeFrame(1, TimeFrameUnit.Day))
        client = StockHistoricalDataClient(settings.alpaca_api_key, settings.alpaca_secret_key)
        req = StockBarsRequest(symbol_or_symbols=symbol, timeframe=tf, limit=limit)
        result = await asyncio.get_event_loop().run_in_executor(
            None, lambda: client.get_stock_bars(req)
        )
        raw = result.get(symbol, [])
        return [
            {
                "t": int(b.timestamp.timestamp()),
                "o": float(b.open),
                "h": float(b.high),
                "l": float(b.low),
                "c": float(b.close),
                "v": int(b.volume),
            }
            for b in raw
        ]
    except Exception as e:
        logger.debug("alpaca_bars_failed", symbol=symbol, error=str(e))
        return None


# ── MarketDataService ─────────────────────────────────────────────────────────

class MarketDataService:
    """Central market data service with Redis caching and provider fallback."""

    QUOTE_TTL = 5    # seconds
    BARS_TTL = 60    # seconds

    def __init__(self) -> None:
        self._redis = None

    # ── Public API ────────────────────────────────────────────────────────────

    async def get_quote(self, symbol: str) -> Optional[QuoteDict]:
        symbol = symbol.upper()
        cached = await self._get_cache(f"market:price:{symbol}")
        if cached:
            return cached

        quote = await _yf_quote(symbol)
        if not quote:
            quote = await _alpaca_quote(symbol)
        if not quote:
            quote = await _finnhub_quote(symbol)

        if quote:
            await self._set_cache(f"market:price:{symbol}", quote, ttl=self.QUOTE_TTL)
            await self._publish(quote)
            logger.debug("quote_fetched", symbol=symbol, source=quote["source"])
        else:
            logger.warning("quote_all_sources_failed", symbol=symbol)

        return quote

    async def get_bars(
        self, symbol: str, timeframe: str = "1D", limit: int = 100
    ) -> Optional[list]:
        symbol = symbol.upper()
        cache_key = f"market:bars:{symbol}:{timeframe}:{int(limit)}"
        cached = await self._get_cache(cache_key)
        if cached:
            return cached

        bars = await _yf_bars(symbol, timeframe, limit)
        if not bars:
            bars = await _alpaca_bars(symbol, timeframe, limit)

        if bars:
            await self._set_cache(cache_key, bars, ttl=self.BARS_TTL)
        return bars

    async def get_batch_quotes(self, symbols: list[str]) -> dict[str, QuoteDict]:
        results = await asyncio.gather(*[self.get_quote(s) for s in symbols])
        return {s: q for s, q in zip(symbols, results) if q}

    # ── Cache helpers ─────────────────────────────────────────────────────────

    async def _get_redis(self):
        if self._redis is None:
            self._redis = _redis_client()
        return self._redis

    async def _reset_redis(self):
        if self._redis is not None:
            try:
                await self._redis.aclose()
            except Exception:
                pass
            self._redis = None

    async def _get_cache(self, key: str):
        try:
            r = await self._get_redis()
            if r is None:
                return None
            val = await r.get(key)
            return json.loads(val) if val else None
        except Exception:
            await self._reset_redis()
            return None

    async def _set_cache(self, key: str, value, ttl: int = 5):
        try:
            r = await self._get_redis()
            if r is None:
                return
            await r.setex(key, ttl, json.dumps(value))
        except Exception:
            await self._reset_redis()
            pass

    async def _publish(self, quote: QuoteDict):
        try:
            r = await self._get_redis()
            if r is None:
                return
            await r.publish("market:price_updates", json.dumps(quote))
        except Exception:
            await self._reset_redis()
            pass


# Module-level singleton
market_data = MarketDataService()
