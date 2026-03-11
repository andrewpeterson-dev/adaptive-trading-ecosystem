"""Market data tools for the Cerberus."""
from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta, timezone
from typing import Any

import httpx
import structlog

from data.market_data import market_data
from services.indicator_engine import IndicatorEngine
from services.options_data import fetch_options_chain
from services.ai_core.tools.base import ToolDefinition, ToolCategory, ToolSideEffect
from services.ai_core.tools.provider_utils import resolve_provider_credentials
from services.ai_core.tools.registry import get_registry

logger = structlog.get_logger(__name__)


_DEFAULT_EARNINGS_UNIVERSE = [
    "AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "TSLA", "AMD", "NFLX", "JPM",
]

_TIMEFRAME_FROM_INTERVAL = {
    "1m": "1m",
    "2m": "1m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "60m": "1h",
    "90m": "1h",
    "1h": "1h",
    "1d": "1D",
    "5d": "1W",
    "1wk": "1W",
    "1w": "1W",
    "1mo": "1W",
    "3mo": "1W",
}

_PERIOD_TO_DAYS = {
    "1d": 1,
    "5d": 5,
    "1mo": 30,
    "3mo": 90,
    "6mo": 180,
    "1y": 365,
    "2y": 730,
    "5y": 1825,
    "10y": 3650,
    "ytd": 365,
    "max": 3650,
}

_BARS_PER_DAY = {
    "1m": 390,
    "5m": 78,
    "15m": 26,
    "30m": 13,
    "1h": 7,
    "1D": 1,
    "1W": 0.2,
}


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if numeric != numeric or numeric in (float("inf"), float("-inf")):
        return None
    return numeric


def _coerce_int(value: Any) -> int | None:
    numeric = _coerce_float(value)
    return None if numeric is None else int(numeric)


def _coerce_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, (list, tuple)):
        for item in value:
            parsed = _coerce_date(item)
            if parsed:
                return parsed
        return None

    text = str(value).strip()
    if not text:
        return None

    normalized = text.replace("Z", "+00:00")
    for parser in (date.fromisoformat, datetime.fromisoformat):
        try:
            parsed = parser(normalized)
            return parsed if isinstance(parsed, date) and not isinstance(parsed, datetime) else parsed.date()
        except ValueError:
            continue

    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%b %d, %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _normalize_interval(interval: str) -> str:
    return _TIMEFRAME_FROM_INTERVAL.get(str(interval or "1d").strip().lower(), "1D")


def _estimate_bar_limit(period: str, interval: str) -> int:
    timeframe = _normalize_interval(interval)
    days = _PERIOD_TO_DAYS.get(str(period or "1mo").strip().lower(), 30)
    bars_per_day = _BARS_PER_DAY.get(timeframe, 1)
    estimate = int(days * bars_per_day) if bars_per_day >= 1 else int(days * bars_per_day)
    return max(32, min(5000, estimate + 32))


def _bar_date_from_epoch(epoch_seconds: int | float | None) -> str | None:
    if epoch_seconds is None:
        return None
    try:
        return datetime.fromtimestamp(float(epoch_seconds), tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        return None


def _latest_scalar(value: Any) -> float | None:
    try:
        import pandas as pd
    except ImportError:  # pragma: no cover - pandas is an existing runtime dependency
        pd = None

    if value is None:
        return None
    if pd is not None and isinstance(value, pd.Series):
        cleaned = value.dropna()
        if cleaned.empty:
            return None
        return _coerce_float(cleaned.iloc[-1])
    return _coerce_float(value)


def _normalize_earnings_event(
    *,
    symbol: str,
    event_date: Any,
    provider: str,
    time_of_day: str | None = None,
    eps_estimate: Any = None,
    eps_actual: Any = None,
    revenue_estimate: Any = None,
    revenue_actual: Any = None,
    surprise_pct: Any = None,
) -> dict | None:
    parsed_date = _coerce_date(event_date)
    if not parsed_date:
        return None

    today = date.today()
    event = {
        "symbol": symbol.upper(),
        "date": parsed_date.isoformat(),
        "event_type": "earnings",
        "status": "upcoming" if parsed_date >= today else "reported",
        "provider": provider,
        "time": time_of_day,
        "eps_estimate": _coerce_float(eps_estimate),
        "eps_actual": _coerce_float(eps_actual),
        "revenue_estimate": _coerce_float(revenue_estimate),
        "revenue_actual": _coerce_float(revenue_actual),
        "surprise_pct": _coerce_float(surprise_pct),
    }
    return event


async def _fetch_finnhub_earnings_calendar(
    user_id: int,
    symbol: str | None,
    days_ahead: int,
) -> list[dict]:
    _, credentials = await resolve_provider_credentials(user_id, ["finnhub", "finnhub_news"])
    api_key = (credentials or {}).get("api_key")
    if not api_key:
        return []

    start = date.today()
    end = start + timedelta(days=max(days_ahead, 1))
    params = {
        "from": start.isoformat(),
        "to": end.isoformat(),
        "token": api_key,
    }
    if symbol:
        params["symbol"] = symbol.upper()

    async with httpx.AsyncClient(timeout=12.0) as client:
        response = await client.get("https://finnhub.io/api/v1/calendar/earnings", params=params)
        response.raise_for_status()
        payload = response.json()

    raw_events = (
        payload.get("earningsCalendar")
        or payload.get("earnings_calendar")
        or payload.get("events")
        or []
    )

    events: list[dict] = []
    for item in raw_events:
        event = _normalize_earnings_event(
            symbol=(item.get("symbol") or symbol or "").upper(),
            event_date=item.get("date") or item.get("earningsDate"),
            provider="finnhub",
            time_of_day=item.get("hour") or item.get("time"),
            eps_estimate=item.get("epsEstimate"),
            eps_actual=item.get("epsActual"),
            revenue_estimate=item.get("revenueEstimate"),
            revenue_actual=item.get("revenueActual"),
            surprise_pct=item.get("surprisePercent"),
        )
        if event:
            events.append(event)

    events.sort(key=lambda item: (item["date"], item["symbol"]))
    return events


async def _fetch_yfinance_symbol_earnings(symbol: str) -> list[dict]:
    import asyncio
    import pandas as pd
    import yfinance as yf

    symbol = symbol.upper()

    def _fetch() -> list[dict]:
        ticker = yf.Ticker(symbol)
        events: list[dict] = []
        seen: set[tuple[str, str]] = set()

        calendar = ticker.calendar
        if isinstance(calendar, pd.DataFrame) and not calendar.empty:
            for _, row in calendar.iterrows():
                parsed = _normalize_earnings_event(
                    symbol=symbol,
                    event_date=row.get("Earnings Date") or row.get("Earnings"),
                    provider="yfinance",
                    eps_estimate=row.get("EPS Estimate"),
                    revenue_estimate=row.get("Revenue Estimate"),
                )
                if parsed and (parsed["symbol"], parsed["date"]) not in seen:
                    seen.add((parsed["symbol"], parsed["date"]))
                    events.append(parsed)
        elif isinstance(calendar, pd.Series):
            parsed = _normalize_earnings_event(
                symbol=symbol,
                event_date=calendar.get("Earnings Date") or calendar.get("Earnings"),
                provider="yfinance",
                eps_estimate=calendar.get("EPS Estimate"),
                revenue_estimate=calendar.get("Revenue Estimate"),
            )
            if parsed and (parsed["symbol"], parsed["date"]) not in seen:
                seen.add((parsed["symbol"], parsed["date"]))
                events.append(parsed)
        elif isinstance(calendar, dict):
            parsed = _normalize_earnings_event(
                symbol=symbol,
                event_date=calendar.get("Earnings Date") or calendar.get("Earnings"),
                provider="yfinance",
                eps_estimate=calendar.get("EPS Estimate"),
                revenue_estimate=calendar.get("Revenue Estimate"),
            )
            if parsed and (parsed["symbol"], parsed["date"]) not in seen:
                seen.add((parsed["symbol"], parsed["date"]))
                events.append(parsed)

        try:
            earnings_dates = ticker.get_earnings_dates(limit=8)
        except Exception:
            earnings_dates = None

        if isinstance(earnings_dates, pd.DataFrame) and not earnings_dates.empty:
            for idx, row in earnings_dates.iterrows():
                parsed = _normalize_earnings_event(
                    symbol=symbol,
                    event_date=idx,
                    provider="yfinance",
                    eps_estimate=row.get("EPS Estimate"),
                    eps_actual=row.get("Reported EPS"),
                    surprise_pct=row.get("Surprise(%)"),
                )
                if parsed and (parsed["symbol"], parsed["date"]) not in seen:
                    seen.add((parsed["symbol"], parsed["date"]))
                    events.append(parsed)

        events.sort(key=lambda item: (item["date"], item["symbol"]))
        return events

    return await asyncio.to_thread(_fetch)


async def _fetch_macro_calendar(user_id: int, days_ahead: int) -> tuple[list[dict], str | None]:
    _, credentials = await resolve_provider_credentials(user_id, ["finnhub", "finnhub_news"])
    api_key = (credentials or {}).get("api_key")
    if not api_key:
        return [], None

    start = date.today()
    end = start + timedelta(days=max(days_ahead, 1))
    params = {
        "from": start.isoformat(),
        "to": end.isoformat(),
        "token": api_key,
    }

    async with httpx.AsyncClient(timeout=12.0) as client:
        response = await client.get("https://finnhub.io/api/v1/calendar/economic", params=params)
        response.raise_for_status()
        payload = response.json()

    raw_events = (
        payload.get("economicCalendar")
        or payload.get("economic_calendar")
        or payload.get("events")
        or []
    )

    events: list[dict] = []
    for item in raw_events:
        event_date = _coerce_date(item.get("date"))
        if not event_date:
            continue
        events.append(
            {
                "date": event_date.isoformat(),
                "event": item.get("event") or item.get("indicator") or item.get("description"),
                "country": item.get("country") or "US",
                "time": item.get("time"),
                "impact": item.get("impact"),
                "actual": _coerce_float(item.get("actual")),
                "estimate": _coerce_float(item.get("estimate")),
                "previous": _coerce_float(item.get("prev") or item.get("previous")),
                "unit": item.get("unit"),
                "provider": "finnhub",
            }
        )

    events.sort(key=lambda item: (item["date"], item.get("time") or "", item.get("event") or ""))
    return events, "finnhub"


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

async def _get_price(user_id: int, symbol: str) -> dict:
    """Get current price for a symbol via the shared market data service."""
    quote = await market_data.get_quote(symbol)
    if not quote:
        return {"symbol": symbol.upper(), "price": None, "message": "No live quote available"}

    return {
        "symbol": symbol.upper(),
        "price": _coerce_float(quote.get("price")),
        "bid": _coerce_float(quote.get("bid")),
        "ask": _coerce_float(quote.get("ask")),
        "previous_close": _coerce_float(
            (quote.get("price") or 0) - (quote.get("change") or 0)
        ),
        "volume": _coerce_int(quote.get("volume")),
        "change": _coerce_float(quote.get("change")),
        "change_pct": _coerce_float(quote.get("change_pct")),
        "timestamp": quote.get("timestamp"),
        "provider": quote.get("source"),
    }


async def _get_historical_prices(
    user_id: int,
    symbol: str,
    period: str = "1mo",
    interval: str = "1d",
) -> dict:
    """Get OHLCV historical bars via the shared market data service."""
    timeframe = _normalize_interval(interval)
    limit = _estimate_bar_limit(period, interval)
    raw_bars = await market_data.get_bars(symbol, timeframe=timeframe, limit=limit)
    if not raw_bars:
        return {"symbol": symbol.upper(), "bars": [], "message": "No data returned"}

    bars = [
        {
            "date": _bar_date_from_epoch(bar.get("t")),
            "open": round(float(bar["o"]), 4),
            "high": round(float(bar["h"]), 4),
            "low": round(float(bar["l"]), 4),
            "close": round(float(bar["c"]), 4),
            "volume": int(bar.get("v") or 0),
        }
        for bar in raw_bars
    ]
    return {
        "symbol": symbol.upper(),
        "period": period,
        "interval": interval,
        "resolved_interval": timeframe,
        "count": len(bars),
        "bars": bars,
        "provider": "market_data_service",
    }


async def _get_options_chain(
    user_id: int,
    symbol: str,
    expiration: str = None,
) -> dict:
    """Get a normalized options chain for a symbol."""
    chain = await fetch_options_chain(symbol, expiration=expiration)
    contracts = chain.get("contracts", [])
    calls = [c for c in contracts if c.get("type") == "call"]
    puts = [c for c in contracts if c.get("type") == "put"]

    return {
        "symbol": symbol.upper(),
        "expiration": chain.get("selected_expiration") or expiration,
        "expirations": chain.get("expirations", []),
        "selected_expiration": chain.get("selected_expiration") or expiration,
        "strikes": chain.get("strikes", []),
        "contracts": contracts,
        "calls": calls,
        "puts": puts,
        "contract_count": len(contracts),
        "provider": "yfinance",
        "message": "No options contracts returned" if not contracts else None,
    }


async def _get_indicators(
    user_id: int,
    symbol: str,
    indicators: list[str] = None,
    period: str = "3mo",
    interval: str = "1d",
) -> dict:
    """Calculate technical indicators from real OHLCV bars."""
    import pandas as pd

    if not indicators:
        indicators = ["sma_20", "sma_50", "ema_12", "rsi_14"]
    timeframe = _normalize_interval(interval)
    limit = _estimate_bar_limit(period, interval)
    raw_bars = await market_data.get_bars(symbol, timeframe=timeframe, limit=limit)
    if not raw_bars:
        return {"symbol": symbol.upper(), "indicators": {}, "message": "No price data"}

    df = pd.DataFrame(
        [
            {
                "timestamp": _bar_date_from_epoch(bar.get("t")),
                "open": float(bar["o"]),
                "high": float(bar["h"]),
                "low": float(bar["l"]),
                "close": float(bar["c"]),
                "volume": float(bar.get("v") or 0),
            }
            for bar in raw_bars
        ]
    )

    def _parse_indicator(spec: str) -> tuple[str, dict[str, Any], str | None]:
        normalized = str(spec or "").strip().lower()
        if normalized.startswith("sma_"):
            return "sma", {"length": int(normalized.split("_", 1)[1])}, None
        if normalized.startswith("ema_"):
            return "ema", {"length": int(normalized.split("_", 1)[1])}, None
        if normalized.startswith("rsi_"):
            return "rsi", {"length": int(normalized.split("_", 1)[1])}, None
        if normalized.startswith("bb_"):
            return "bollinger_bands", {"length": int(normalized.split("_", 1)[1])}, None
        return normalized, {}, None

    results: dict[str, float | None] = {}
    for indicator_name in indicators:
        base_name, params, field = _parse_indicator(indicator_name)
        try:
            computed = IndicatorEngine.compute(base_name, df, params)
            if isinstance(computed, dict):
                if base_name == "macd":
                    results["macd_line"] = _latest_scalar(computed.get("macd"))
                    results["macd_signal"] = _latest_scalar(computed.get("signal"))
                    results["macd_histogram"] = _latest_scalar(computed.get("histogram"))
                    continue
                if base_name == "bollinger_bands":
                    length = params.get("length", 20)
                    results[f"bb_upper_{length}"] = _latest_scalar(computed.get("upper"))
                    results[f"bb_middle_{length}"] = _latest_scalar(computed.get("middle"))
                    results[f"bb_lower_{length}"] = _latest_scalar(computed.get("lower"))
                    continue
                selected = computed.get(field) if field else next(iter(computed.values()), None)
                results[indicator_name] = _latest_scalar(selected)
            else:
                results[indicator_name] = _latest_scalar(computed)
        except Exception as exc:
            logger.warning("indicator_calc_error", indicator=indicator_name, error=str(exc))
            results[indicator_name] = None

    return {
        "symbol": symbol.upper(),
        "period": period,
        "interval": interval,
        "resolved_interval": timeframe,
        "data_points": len(df),
        "latest_close": _latest_scalar(df["close"]),
        "indicators": {
            key: round(value, 4) if value is not None else None
            for key, value in results.items()
        },
        "provider": "market_data_service",
    }


async def _get_earnings_calendar(user_id: int, symbol: str = None, days_ahead: int = 7) -> dict:
    """Get real upcoming earnings events."""
    symbol = symbol.upper().strip() if symbol else None
    days_ahead = max(int(days_ahead or 7), 1)

    events: list[dict] = []
    provider: str | None = None

    try:
        events = await _fetch_finnhub_earnings_calendar(user_id, symbol, days_ahead)
        provider = "finnhub" if events else provider
    except Exception as exc:
        logger.warning("finnhub_earnings_calendar_failed", symbol=symbol, error=str(exc))

    if not events and symbol:
        try:
            timeline = await _fetch_yfinance_symbol_earnings(symbol)
            cutoff = date.today() + timedelta(days=days_ahead)
            events = [
                event
                for event in timeline
                if _coerce_date(event.get("date")) and date.today() <= _coerce_date(event["date"]) <= cutoff
            ]
            provider = "yfinance" if events else provider
        except Exception as exc:
            logger.warning("yfinance_earnings_calendar_failed", symbol=symbol, error=str(exc))

    if not events and not symbol:
        try:
            timelines = await asyncio.gather(
                *[_fetch_yfinance_symbol_earnings(item) for item in _DEFAULT_EARNINGS_UNIVERSE],
                return_exceptions=True,
            )
            cutoff = date.today() + timedelta(days=days_ahead)
            for timeline in timelines:
                if isinstance(timeline, Exception):
                    continue
                for event in timeline:
                    parsed_date = _coerce_date(event.get("date"))
                    if parsed_date and date.today() <= parsed_date <= cutoff:
                        events.append(event)
            provider = "yfinance" if events else provider
        except Exception as exc:
            logger.warning("market_earnings_calendar_failed", error=str(exc))

    deduped: dict[tuple[str, str], dict] = {}
    for event in events:
        key = (event.get("symbol", ""), event.get("date", ""))
        if key[0] and key[1]:
            deduped[key] = event
    normalized_events = sorted(deduped.values(), key=lambda item: (item["date"], item["symbol"]))

    return {
        "symbol": symbol,
        "days_ahead": days_ahead,
        "count": len(normalized_events),
        "events": normalized_events,
        "provider": provider,
        "coverage": "broad_market_universe" if not symbol and provider == "yfinance" else "symbol",
        "message": None if normalized_events else "No earnings events found for the requested window",
    }


async def _get_macro_calendar(user_id: int, days_ahead: int = 7) -> dict:
    """Get real upcoming macro events."""
    days_ahead = max(int(days_ahead or 7), 1)
    provider = None
    events: list[dict] = []

    try:
        events, provider = await _fetch_macro_calendar(user_id, days_ahead)
    except Exception as exc:
        logger.warning("macro_calendar_failed", error=str(exc))

    return {
        "days_ahead": days_ahead,
        "count": len(events),
        "events": events,
        "provider": provider,
        "message": None if events else "No macro calendar provider configured or no events found",
    }


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register():
    registry = get_registry()

    registry.register(ToolDefinition(
        name="getPrice",
        version="1.0",
        description="Get current price for a ticker symbol",
        category=ToolCategory.MARKET,
        side_effect=ToolSideEffect.READ,
        timeout_ms=5000,
        cache_ttl_s=15,
        input_schema={
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Ticker symbol (e.g., AAPL, SPY)"},
            },
            "required": ["symbol"],
        },
        output_schema={"type": "object"},
        handler=_get_price,
    ))

    registry.register(ToolDefinition(
        name="getHistoricalPrices",
        version="1.0",
        description="Get OHLCV historical price bars for a symbol",
        category=ToolCategory.MARKET,
        side_effect=ToolSideEffect.READ,
        timeout_ms=10000,
        cache_ttl_s=60,
        input_schema={
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Ticker symbol"},
                "period": {"type": "string", "description": "Time period (1d,5d,1mo,3mo,6mo,1y,2y,5y,10y,ytd,max)", "default": "1mo"},
                "interval": {"type": "string", "description": "Bar interval (1m,2m,5m,15m,30m,60m,90m,1h,1d,5d,1wk,1mo,3mo)", "default": "1d"},
            },
            "required": ["symbol"],
        },
        output_schema={"type": "object"},
        handler=_get_historical_prices,
    ))

    registry.register(ToolDefinition(
        name="getOptionsChain",
        version="1.0",
        description="Get options chain for a symbol and expiration date",
        category=ToolCategory.MARKET,
        side_effect=ToolSideEffect.READ,
        timeout_ms=8000,
        cache_ttl_s=30,
        input_schema={
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Ticker symbol"},
                "expiration": {"type": "string", "description": "Expiration date (YYYY-MM-DD)"},
            },
            "required": ["symbol"],
        },
        output_schema={"type": "object"},
        handler=_get_options_chain,
    ))

    registry.register(ToolDefinition(
        name="getIndicators",
        version="1.0",
        description="Calculate technical indicators (SMA, EMA, RSI, MACD, Bollinger Bands) for a symbol",
        category=ToolCategory.MARKET,
        side_effect=ToolSideEffect.READ,
        timeout_ms=10000,
        cache_ttl_s=60,
        input_schema={
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Ticker symbol"},
                "indicators": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of indicators to calculate (sma_20, ema_12, rsi_14, macd, bb_20, etc.)",
                },
                "period": {"type": "string", "description": "Data period", "default": "3mo"},
                "interval": {"type": "string", "description": "Data interval", "default": "1d"},
            },
            "required": ["symbol"],
        },
        output_schema={"type": "object"},
        handler=_get_indicators,
    ))

    registry.register(ToolDefinition(
        name="getEarningsCalendar",
        version="1.0",
        description="Get upcoming earnings announcements for a symbol or the market",
        category=ToolCategory.MARKET,
        side_effect=ToolSideEffect.READ,
        timeout_ms=5000,
        cache_ttl_s=300,
        input_schema={
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Ticker symbol (optional, omit for broad market)"},
                "days_ahead": {"type": "integer", "description": "Days to look ahead", "default": 7},
            },
        },
        output_schema={"type": "object"},
        handler=_get_earnings_calendar,
    ))

    registry.register(ToolDefinition(
        name="getMacroCalendar",
        version="1.0",
        description="Get upcoming macroeconomic events (FOMC, CPI, jobs, etc.)",
        category=ToolCategory.MARKET,
        side_effect=ToolSideEffect.READ,
        timeout_ms=5000,
        cache_ttl_s=300,
        input_schema={
            "type": "object",
            "properties": {
                "days_ahead": {"type": "integer", "description": "Days to look ahead", "default": 7},
            },
        },
        output_schema={"type": "object"},
        handler=_get_macro_calendar,
    ))
