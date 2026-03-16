"""
MarketDataService -- fetches, normalizes, and caches market data.

Fallback chain per operation:
  quote:  Polygon -> yFinance -> Alpaca -> Finnhub
  bars:   Polygon -> yFinance -> Alpaca

Redis cache keys:
  market:price:{SYMBOL}          TTL 5 s  (live quote)
  market:bars:{SYMBOL}:{tf}      TTL 60 s (OHLCV bars)
"""

import asyncio
import json
import time
from datetime import datetime, timedelta, timezone
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


# ── Validation ───────────────────────────────────────────────────────────────

# In-memory cache: symbol -> last known good price (for split/bad-data detection)
_last_known_prices: dict[str, float] = {}


def _is_weekend_or_holiday() -> bool:
    """Check if current time is a weekend (Sat/Sun). Holiday detection is best-effort."""
    now = datetime.now(timezone.utc)
    return now.weekday() >= 5  # 5 = Saturday, 6 = Sunday


def _validate_quote(quote: QuoteDict) -> bool:
    """Validate a quote for obvious data issues. Returns True if quote is usable."""
    symbol = quote.get("symbol", "")
    price = quote.get("price", 0)
    volume = quote.get("volume", 0)
    ts = quote.get("timestamp", 0)

    # Price must be positive
    if price <= 0:
        logger.warning("quote_validation_failed", symbol=symbol, reason="non_positive_price", price=price)
        return False

    # Volume must be non-negative
    if volume < 0:
        logger.warning("quote_validation_failed", symbol=symbol, reason="negative_volume", volume=volume)
        return False

    # Timestamp freshness: within 24 hours (allow stale on weekends/holidays)
    if ts:
        age_seconds = time.time() - ts
        if age_seconds > 86400 and not _is_weekend_or_holiday():
            logger.warning(
                "quote_validation_failed", symbol=symbol,
                reason="stale_timestamp", age_hours=round(age_seconds / 3600, 1),
            )
            return False

    # Price sanity: reject >50% change from last known price (likely split or bad data)
    last_price = _last_known_prices.get(symbol)
    if last_price and last_price > 0:
        change_ratio = abs(price - last_price) / last_price
        if change_ratio > 0.50:
            logger.warning(
                "quote_validation_failed", symbol=symbol,
                reason="extreme_price_change", price=price,
                last_price=last_price, change_pct=round(change_ratio * 100, 1),
            )
            return False

    # Passed all checks -- update last known price
    _last_known_prices[symbol] = price
    return True


def _validate_bars(bars: list[dict]) -> list[dict]:
    """Clean bars: remove zero/negative price bars, warn on insufficient data."""
    cleaned = []
    for bar in bars:
        o, h, l, c = bar.get("o", 0), bar.get("h", 0), bar.get("l", 0), bar.get("c", 0)
        if o <= 0 or h <= 0 or l <= 0 or c <= 0:
            continue
        cleaned.append(bar)

    if len(cleaned) < 14:
        logger.warning(
            "bars_insufficient_for_rsi",
            count=len(cleaned),
            minimum_recommended=14,
        )

    return cleaned


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


def _norm_polygon_quote(symbol: str, result: dict) -> QuoteDict:
    """Normalize a Polygon prev-day aggregate into QuoteDict."""
    c = float(result.get("c") or 0)
    o = float(result.get("o") or c)
    change = c - o
    change_pct = (change / o * 100) if o else 0.0
    ts = result.get("t", 0)
    # Polygon timestamps are in milliseconds
    if ts and ts > 1e12:
        ts = int(ts / 1000)
    return {
        "symbol": symbol,
        "price": c,
        "bid": c,
        "ask": c,
        "volume": int(result.get("v") or 0),
        "change": round(change, 4),
        "change_pct": round(change_pct, 4),
        "timestamp": int(ts) if ts else int(time.time()),
        "source": "polygon",
    }


def _norm_polygon_snapshot(symbol: str, ticker_data: dict) -> QuoteDict:
    """Normalize a Polygon snapshot ticker into QuoteDict."""
    day = ticker_data.get("day", {})
    prev_day = ticker_data.get("prevDay", {})
    last_quote = ticker_data.get("lastQuote", {})
    last_trade = ticker_data.get("lastTrade", {})

    price = float(last_trade.get("p") or day.get("c") or 0)
    prev_close = float(prev_day.get("c") or price)
    change = price - prev_close
    change_pct = (change / prev_close * 100) if prev_close else 0.0

    return {
        "symbol": symbol,
        "price": price,
        "bid": float(last_quote.get("p") or price),
        "ask": float(last_quote.get("P") or price),
        "volume": int(day.get("v") or 0),
        "change": round(change, 4),
        "change_pct": round(change_pct, 4),
        "timestamp": int(ticker_data.get("updated", 0) / 1e9) if ticker_data.get("updated") else int(time.time()),
        "source": "polygon",
    }


# ── Fetchers ─────────────────────────────────────────────────────────────────

async def _polygon_quote(symbol: str) -> Optional[QuoteDict]:
    """Fetch previous-day close from Polygon REST API."""
    try:
        settings = get_settings()
        if not settings.polygon_api_key:
            return None
        import httpx
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(
                f"https://api.polygon.io/v2/aggs/ticker/{symbol}/prev",
                params={"adjusted": "true", "apiKey": settings.polygon_api_key},
            )
            if resp.status_code == 429:
                logger.warning("polygon_rate_limited", symbol=symbol)
                return None
            if resp.status_code != 200:
                logger.debug("polygon_bad_status", symbol=symbol, status=resp.status_code)
                return None
            data = resp.json()
        results = data.get("results", [])
        if not results:
            return None
        return _norm_polygon_quote(symbol, results[0])
    except Exception as e:
        logger.debug("polygon_quote_failed", symbol=symbol, error=str(e))
        return None


async def _polygon_bars(symbol: str, timeframe: str = "1D", limit: int = 100) -> Optional[list]:
    """Fetch OHLCV bars from Polygon REST API."""
    try:
        settings = get_settings()
        if not settings.polygon_api_key:
            return None

        # Map timeframe to Polygon multiplier + timespan
        tf_map = {
            "1m": (1, "minute"), "5m": (5, "minute"), "15m": (15, "minute"),
            "30m": (30, "minute"), "1h": (1, "hour"), "4h": (4, "hour"),
            "1D": (1, "day"), "1W": (1, "week"),
        }
        multiplier, timespan = tf_map.get(timeframe, (1, "day"))

        # Calculate date range based on limit and timeframe
        now = datetime.now(timezone.utc)
        if timespan == "minute":
            delta = timedelta(minutes=multiplier * limit * 2)
        elif timespan == "hour":
            delta = timedelta(hours=multiplier * limit * 2)
        elif timespan == "week":
            delta = timedelta(weeks=limit * 2)
        else:
            delta = timedelta(days=limit * 2)

        from_date = (now - delta).strftime("%Y-%m-%d")
        to_date = now.strftime("%Y-%m-%d")

        import httpx
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"https://api.polygon.io/v2/aggs/ticker/{symbol}/range/{multiplier}/{timespan}/{from_date}/{to_date}",
                params={
                    "adjusted": "true",
                    "sort": "asc",
                    "limit": limit,
                    "apiKey": settings.polygon_api_key,
                },
            )
            if resp.status_code == 429:
                logger.warning("polygon_bars_rate_limited", symbol=symbol)
                return None
            if resp.status_code != 200:
                logger.debug("polygon_bars_bad_status", symbol=symbol, status=resp.status_code)
                return None
            data = resp.json()

        results = data.get("results", [])
        if not results:
            return None

        bars = []
        for r in results[-limit:]:
            ts = r.get("t", 0)
            if ts > 1e12:
                ts = int(ts / 1000)
            bars.append({
                "t": int(ts),
                "o": float(r.get("o", 0)),
                "h": float(r.get("h", 0)),
                "l": float(r.get("l", 0)),
                "c": float(r.get("c", 0)),
                "v": int(r.get("v", 0)),
            })
        return bars
    except Exception as e:
        logger.debug("polygon_bars_failed", symbol=symbol, error=str(e))
        return None


async def _polygon_snapshot(symbols: list[str]) -> dict[str, QuoteDict]:
    """Fetch batch quotes via Polygon snapshot endpoint (all tickers in one call)."""
    try:
        settings = get_settings()
        if not settings.polygon_api_key:
            return {}

        import httpx
        params = {"apiKey": settings.polygon_api_key}
        # If requesting specific symbols, use the tickers param to filter
        if symbols:
            params["tickers"] = ",".join(s.upper() for s in symbols)

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/tickers",
                params=params,
            )
            if resp.status_code == 429:
                logger.warning("polygon_snapshot_rate_limited")
                return {}
            if resp.status_code != 200:
                logger.debug("polygon_snapshot_bad_status", status=resp.status_code)
                return {}
            data = resp.json()

        tickers = data.get("tickers", [])
        result: dict[str, QuoteDict] = {}
        for t in tickers:
            sym = t.get("ticker", "")
            if sym:
                quote = _norm_polygon_snapshot(sym, t)
                if _validate_quote(quote):
                    result[sym] = quote
        return result
    except Exception as e:
        logger.debug("polygon_snapshot_failed", error=str(e))
        return {}


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

        # Fallback chain: Polygon -> yFinance -> Alpaca -> Finnhub
        quote = await _polygon_quote(symbol)
        if not quote or not _validate_quote(quote):
            quote = await _yf_quote(symbol)
        if not quote or not _validate_quote(quote):
            quote = await _alpaca_quote(symbol)
        if not quote or not _validate_quote(quote):
            quote = await _finnhub_quote(symbol)

        if quote and _validate_quote(quote):
            await self._set_cache(f"market:price:{symbol}", quote, ttl=self.QUOTE_TTL)
            await self._publish(quote)
            logger.debug("quote_fetched", symbol=symbol, source=quote["source"])
        else:
            logger.warning("quote_all_sources_failed", symbol=symbol)
            quote = None

        return quote

    async def get_bars(
        self, symbol: str, timeframe: str = "1D", limit: int = 100
    ) -> Optional[list]:
        symbol = symbol.upper()
        cache_key = f"market:bars:{symbol}:{timeframe}:{int(limit)}"
        cached = await self._get_cache(cache_key)
        if cached:
            return cached

        # Fallback chain: Polygon -> yFinance -> Alpaca
        bars = await _polygon_bars(symbol, timeframe, limit)
        if not bars:
            bars = await _yf_bars(symbol, timeframe, limit)
        if not bars:
            bars = await _alpaca_bars(symbol, timeframe, limit)

        if bars:
            bars = _validate_bars(bars)
            if bars:
                await self._set_cache(cache_key, bars, ttl=self.BARS_TTL)
        return bars or None

    async def get_batch_quotes(self, symbols: list[str]) -> dict[str, QuoteDict]:
        """Fetch batch quotes. Uses Polygon snapshot when available (single API call)."""
        symbols = [s.upper() for s in symbols]

        # Try Polygon snapshot first -- much more efficient than N individual calls
        settings = get_settings()
        if settings.polygon_api_key:
            snapshot = await _polygon_snapshot(symbols)
            if snapshot:
                # Cache each quote individually
                for sym, quote in snapshot.items():
                    await self._set_cache(f"market:price:{sym}", quote, ttl=self.QUOTE_TTL)
                    await self._publish(quote)

                # If snapshot covered all requested symbols, return immediately
                missing = [s for s in symbols if s not in snapshot]
                if not missing:
                    return snapshot

                # Fetch missing symbols individually
                extra = await asyncio.gather(*[self.get_quote(s) for s in missing])
                for s, q in zip(missing, extra):
                    if q:
                        snapshot[s] = q
                return snapshot

        # Fallback: fetch individually
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
