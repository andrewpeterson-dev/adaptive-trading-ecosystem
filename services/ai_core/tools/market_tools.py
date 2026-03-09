"""Market data tools for the AI Copilot."""
from __future__ import annotations

import structlog

from services.ai_core.tools.base import ToolDefinition, ToolCategory, ToolSideEffect
from services.ai_core.tools.registry import get_registry

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

async def _get_price(user_id: int, symbol: str) -> dict:
    """Get current price for a symbol via yfinance."""
    import asyncio
    import yfinance as yf

    def _fetch():
        ticker = yf.Ticker(symbol.upper())
        info = ticker.fast_info
        return {
            "symbol": symbol.upper(),
            "price": round(float(info.last_price), 4) if hasattr(info, "last_price") and info.last_price else None,
            "previous_close": round(float(info.previous_close), 4) if hasattr(info, "previous_close") and info.previous_close else None,
            "market_cap": float(info.market_cap) if hasattr(info, "market_cap") and info.market_cap else None,
        }

    return await asyncio.to_thread(_fetch)


async def _get_historical_prices(
    user_id: int,
    symbol: str,
    period: str = "1mo",
    interval: str = "1d",
) -> dict:
    """Get OHLCV historical bars via yfinance."""
    import asyncio
    import yfinance as yf

    def _fetch():
        ticker = yf.Ticker(symbol.upper())
        df = ticker.history(period=period, interval=interval)
        if df.empty:
            return {"symbol": symbol.upper(), "bars": [], "message": "No data returned"}

        bars = []
        for ts, row in df.iterrows():
            bars.append({
                "date": ts.isoformat(),
                "open": round(float(row["Open"]), 4),
                "high": round(float(row["High"]), 4),
                "low": round(float(row["Low"]), 4),
                "close": round(float(row["Close"]), 4),
                "volume": int(row["Volume"]),
            })
        return {
            "symbol": symbol.upper(),
            "period": period,
            "interval": interval,
            "count": len(bars),
            "bars": bars,
        }

    return await asyncio.to_thread(_fetch)


async def _get_options_chain(
    user_id: int,
    symbol: str,
    expiration: str = None,
) -> dict:
    """Get options chain for a symbol. Stub — returns placeholder."""
    # TODO: Implement with yfinance or broker API
    return {
        "symbol": symbol.upper(),
        "expiration": expiration,
        "calls": [],
        "puts": [],
        "message": "Options chain not yet implemented; will integrate with broker API",
    }


async def _get_indicators(
    user_id: int,
    symbol: str,
    indicators: list[str] = None,
    period: str = "3mo",
    interval: str = "1d",
) -> dict:
    """Calculate technical indicators (SMA, EMA, RSI, MACD, Bollinger Bands)."""
    import asyncio
    import numpy as np
    import yfinance as yf

    if not indicators:
        indicators = ["sma_20", "sma_50", "ema_12", "rsi_14"]

    def _compute():
        ticker = yf.Ticker(symbol.upper())
        df = ticker.history(period=period, interval=interval)
        if df.empty:
            return {"symbol": symbol.upper(), "indicators": {}, "message": "No price data"}

        close = df["Close"].values
        results = {}

        for ind in indicators:
            ind_lower = ind.lower()
            try:
                if ind_lower.startswith("sma_"):
                    n = int(ind_lower.split("_")[1])
                    if len(close) >= n:
                        sma = float(np.mean(close[-n:]))
                        results[ind] = round(sma, 4)
                elif ind_lower.startswith("ema_"):
                    n = int(ind_lower.split("_")[1])
                    if len(close) >= n:
                        weights = np.exp(np.linspace(-1., 0., n))
                        weights /= weights.sum()
                        ema = float(np.convolve(close, weights, mode="valid")[-1])
                        results[ind] = round(ema, 4)
                elif ind_lower.startswith("rsi_"):
                    n = int(ind_lower.split("_")[1])
                    if len(close) > n:
                        deltas = np.diff(close)
                        gains = np.where(deltas > 0, deltas, 0)
                        losses = np.where(deltas < 0, -deltas, 0)
                        avg_gain = np.mean(gains[-n:])
                        avg_loss = np.mean(losses[-n:])
                        if avg_loss == 0:
                            results[ind] = 100.0
                        else:
                            rs = avg_gain / avg_loss
                            results[ind] = round(100 - 100 / (1 + rs), 4)
                elif ind_lower == "macd":
                    if len(close) >= 26:
                        ema12 = _ema_calc(close, 12)
                        ema26 = _ema_calc(close, 26)
                        macd_line = ema12 - ema26
                        signal = _ema_calc(macd_line[-9:], 9) if len(macd_line) >= 9 else macd_line[-1]
                        results["macd_line"] = round(float(macd_line[-1]), 4)
                        results["macd_signal"] = round(float(signal), 4)
                        results["macd_histogram"] = round(float(macd_line[-1] - signal), 4)
                elif ind_lower.startswith("bb_"):
                    n = int(ind_lower.split("_")[1]) if "_" in ind_lower[3:] else 20
                    if len(close) >= n:
                        sma = np.mean(close[-n:])
                        std = np.std(close[-n:])
                        results[f"bb_upper_{n}"] = round(float(sma + 2 * std), 4)
                        results[f"bb_middle_{n}"] = round(float(sma), 4)
                        results[f"bb_lower_{n}"] = round(float(sma - 2 * std), 4)
                else:
                    results[ind] = None
            except Exception as e:
                logger.warning("indicator_calc_error", indicator=ind, error=str(e))
                results[ind] = None

        return {
            "symbol": symbol.upper(),
            "period": period,
            "interval": interval,
            "data_points": len(close),
            "latest_close": round(float(close[-1]), 4) if len(close) > 0 else None,
            "indicators": results,
        }

    return await asyncio.to_thread(_compute)


def _ema_calc(data, n):
    """Helper: compute EMA over a numpy array."""
    import numpy as np
    alpha = 2 / (n + 1)
    ema = np.zeros_like(data, dtype=float)
    ema[0] = data[0]
    for i in range(1, len(data)):
        ema[i] = alpha * data[i] + (1 - alpha) * ema[i - 1]
    return ema


async def _get_earnings_calendar(user_id: int, symbol: str = None, days_ahead: int = 7) -> dict:
    """Get upcoming earnings. Stub."""
    # TODO: Integrate with earnings API (e.g., Alpha Vantage, FMP)
    return {
        "symbol": symbol,
        "days_ahead": days_ahead,
        "events": [],
        "message": "Earnings calendar not yet implemented; will integrate with financial data provider",
    }


async def _get_macro_calendar(user_id: int, days_ahead: int = 7) -> dict:
    """Get upcoming macro events. Stub."""
    # TODO: Integrate with economic calendar API
    return {
        "days_ahead": days_ahead,
        "events": [],
        "message": "Macro calendar not yet implemented; will integrate with economic data provider",
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
