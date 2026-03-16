"""
Fundamental data features from Finnhub basic financials.

Lightweight — not a full quant model. Returns None for any unavailable metric.
All HTTP calls are async via httpx with timeouts.
"""
from __future__ import annotations

import time

import structlog

from config.settings import get_settings

logger = structlog.get_logger(__name__)

# In-memory cache
_cache: dict[str, tuple[float, dict]] = {}
_CACHE_TTL = 3600  # 1 hour — fundamentals change infrequently


class FundamentalFeatures:
    """Fundamental data features — lightweight, not a full quant model."""

    def __init__(self) -> None:
        self._settings = get_settings()

    async def compute(self, symbol: str) -> dict:
        """
        Fetch and return fundamental features for a symbol.

        Returns a dict with keys:
            pe_ratio, pb_ratio, market_cap, dividend_yield,
            revenue_growth_yoy, earnings_growth_yoy, debt_to_equity
        All values are float or None if unavailable.
        """
        result: dict = {
            "pe_ratio": None,
            "pb_ratio": None,
            "market_cap": None,
            "dividend_yield": None,
            "revenue_growth_yoy": None,
            "earnings_growth_yoy": None,
            "debt_to_equity": None,
        }

        api_key = self._settings.finnhub_api_key
        if not api_key:
            logger.debug("fundamental_no_api_key", symbol=symbol)
            return result

        # Check cache
        cache_key = f"fundamental:{symbol.upper()}"
        entry = _cache.get(cache_key)
        if entry and (time.time() - entry[0]) < _CACHE_TTL:
            return entry[1]

        try:
            import httpx
        except ImportError:
            logger.warning("fundamental_httpx_not_installed")
            return result

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    "https://finnhub.io/api/v1/stock/metric",
                    params={
                        "symbol": symbol.upper(),
                        "metric": "all",
                        "token": api_key,
                    },
                )

                if resp.status_code == 429:
                    logger.warning("finnhub_rate_limited", endpoint="metric", symbol=symbol)
                    return result
                if resp.status_code != 200:
                    logger.debug("fundamental_bad_status", symbol=symbol, status=resp.status_code)
                    return result

                data = resp.json()
                metric = data.get("metric", {})
                if not metric:
                    return result

                result["pe_ratio"] = _safe_float(metric.get("peBasicExclExtraTTM") or metric.get("peTTM"))
                result["pb_ratio"] = _safe_float(metric.get("pbQuarterly") or metric.get("pbAnnual"))
                result["market_cap"] = _safe_float(metric.get("marketCapitalization"))
                result["dividend_yield"] = _safe_float(metric.get("dividendYieldIndicatedAnnual"))
                result["revenue_growth_yoy"] = _safe_float(
                    metric.get("revenueGrowthQuarterlyYoy")
                    or metric.get("revenueGrowth3Y")
                )
                result["earnings_growth_yoy"] = _safe_float(
                    metric.get("epsGrowthQuarterlyYoy")
                    or metric.get("epsGrowth3Y")
                )
                result["debt_to_equity"] = _safe_float(
                    metric.get("totalDebt/totalEquityQuarterly")
                    or metric.get("totalDebt/totalEquityAnnual")
                )

                _cache[cache_key] = (time.time(), result)

        except Exception as e:
            logger.warning("fundamental_fetch_failed", symbol=symbol, error=str(e))

        return result


def _safe_float(value: object) -> float | None:
    """Convert to float, returning None for missing/invalid values."""
    if value is None:
        return None
    try:
        f = float(value)
        if f != f:  # NaN check
            return None
        return f
    except (TypeError, ValueError):
        return None
