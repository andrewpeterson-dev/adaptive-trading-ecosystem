"""Symbol pool fetching with daily caching."""
from __future__ import annotations

import asyncio
import time
from datetime import datetime

import structlog

logger = structlog.get_logger(__name__)

_cache: dict[str, tuple[float, list[str]]] = {}
_CACHE_TTL = 86400  # 24 hours


def _get_cached(key: str) -> list[str] | None:
    if key in _cache:
        ts, data = _cache[key]
        if time.time() - ts < _CACHE_TTL:
            return data
    return None


def _set_cached(key: str, data: list[str]) -> None:
    _cache[key] = (time.time(), data)


def _fetch_sp500_sync() -> list[str]:
    try:
        import pandas as pd
        table = pd.read_html("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")[0]
        symbols = table["Symbol"].str.replace(".", "-", regex=False).tolist()
        return symbols
    except Exception as e:
        logger.warning("sp500_fetch_failed", error=str(e))
        return []


def _fetch_nasdaq100_sync() -> list[str]:
    try:
        import pandas as pd
        table = pd.read_html("https://en.wikipedia.org/wiki/Nasdaq-100")[4]
        symbols = table["Ticker"].tolist()
        return symbols
    except Exception as e:
        logger.warning("nasdaq100_fetch_failed", error=str(e))
        return []


async def get_sp500_symbols() -> list[str]:
    cached = _get_cached("sp500")
    if cached:
        return cached
    loop = asyncio.get_running_loop()
    symbols = await loop.run_in_executor(None, _fetch_sp500_sync)
    if symbols:
        _set_cached("sp500", symbols)
    return symbols


async def get_nasdaq100_symbols() -> list[str]:
    cached = _get_cached("nasdaq100")
    if cached:
        return cached
    loop = asyncio.get_running_loop()
    symbols = await loop.run_in_executor(None, _fetch_nasdaq100_sync)
    if symbols:
        _set_cached("nasdaq100", symbols)
    return symbols


SECTOR_SYMBOLS = {
    "technology": ["AAPL", "MSFT", "NVDA", "GOOGL", "META", "AVGO", "ORCL", "CRM", "AMD", "ADBE", "INTC", "CSCO"],
    "healthcare": ["UNH", "JNJ", "LLY", "PFE", "ABBV", "MRK", "TMO", "ABT", "DHR", "BMY", "AMGN", "GILD"],
    "financials": ["JPM", "BAC", "WFC", "GS", "MS", "BLK", "C", "SCHW", "AXP", "USB", "PNC", "TFC"],
    "energy": ["XOM", "CVX", "COP", "SLB", "EOG", "MPC", "PSX", "VLO", "OXY", "HES", "DVN", "HAL"],
    "consumer_discretionary": ["AMZN", "TSLA", "HD", "MCD", "NKE", "SBUX", "LOW", "TJX", "BKNG", "CMG"],
    "consumer_staples": ["PG", "KO", "PEP", "COST", "WMT", "PM", "MO", "CL", "MDLZ", "KHC"],
    "industrials": ["CAT", "RTX", "HON", "UPS", "BA", "DE", "LMT", "GE", "MMM", "UNP"],
    "utilities": ["NEE", "DUK", "SO", "D", "AEP", "SRE", "EXC", "XEL", "ED", "WEC"],
    "real_estate": ["PLD", "AMT", "CCI", "EQIX", "PSA", "SPG", "O", "WELL", "DLR", "AVB"],
    "materials": ["LIN", "APD", "SHW", "ECL", "DD", "NEM", "FCX", "NUE", "VMC", "MLM"],
    "communication": ["GOOGL", "META", "NFLX", "DIS", "CMCSA", "VZ", "T", "TMUS", "CHTR", "EA"],
}


async def get_sector_symbols(sectors: list[str]) -> list[str]:
    symbols = []
    for sector in sectors:
        key = sector.lower().replace(" ", "_")
        if key in SECTOR_SYMBOLS:
            symbols.extend(SECTOR_SYMBOLS[key])
    return list(dict.fromkeys(symbols))  # Dedupe preserving order
