"""
Sentiment and news feature extraction.

Uses Finnhub API for news sentiment and earnings calendar data.
All HTTP calls are async via httpx with timeouts.
Gracefully degrades when API key is missing or calls fail.
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta
from typing import Optional

import structlog

from config.settings import get_settings

logger = structlog.get_logger(__name__)

# In-memory cache: key -> (timestamp, value)
_cache: dict[str, tuple[float, object]] = {}
_CACHE_TTL_NEWS = 300       # 5 minutes
_CACHE_TTL_EARNINGS = 3600  # 1 hour
_CACHE_TTL_SECTOR = 600     # 10 minutes


def _get_cached(key: str, ttl: float) -> object | None:
    entry = _cache.get(key)
    if entry and (time.time() - entry[0]) < ttl:
        return entry[1]
    return None


def _set_cached(key: str, value: object) -> None:
    _cache[key] = (time.time(), value)


class SentimentFeatures:
    """News and sentiment feature extraction."""

    def __init__(self) -> None:
        self._settings = get_settings()

    async def compute(self, symbol: str) -> dict:
        """Fetch and compute sentiment features for a symbol."""
        result: dict = {
            "news_sentiment_score": None,
            "news_volume": None,
            "social_sentiment": None,   # placeholder for future integration
            "earnings_proximity": None,
            "sector_sentiment": None,
        }

        api_key = self._settings.finnhub_api_key
        if not api_key:
            logger.debug("sentiment_no_api_key", symbol=symbol)
            return result

        try:
            import httpx
        except ImportError:
            logger.warning("sentiment_httpx_not_installed")
            return result

        async with httpx.AsyncClient(timeout=10.0) as client:
            # Fetch news sentiment and earnings in parallel
            import asyncio
            news_task = self._fetch_news_sentiment(client, api_key, symbol)
            earnings_task = self._fetch_earnings_proximity(client, api_key, symbol)
            sector_task = self._fetch_sector_sentiment(client, api_key, symbol)

            news_result, earnings_days, sector_score = await asyncio.gather(
                news_task, earnings_task, sector_task,
                return_exceptions=True,
            )

            if isinstance(news_result, dict):
                result["news_sentiment_score"] = news_result.get("score")
                result["news_volume"] = news_result.get("count")
            elif isinstance(news_result, BaseException):
                logger.debug("sentiment_news_failed", symbol=symbol, error=str(news_result))

            if isinstance(earnings_days, (int, float)):
                result["earnings_proximity"] = int(earnings_days)
            elif isinstance(earnings_days, BaseException):
                logger.debug("sentiment_earnings_failed", symbol=symbol, error=str(earnings_days))

            if isinstance(sector_score, (int, float)):
                result["sector_sentiment"] = float(sector_score)
            elif isinstance(sector_score, BaseException):
                logger.debug("sentiment_sector_failed", symbol=symbol, error=str(sector_score))

        return result

    async def _fetch_news_sentiment(
        self, client, api_key: str, symbol: str,
    ) -> dict:
        """Fetch recent news and compute sentiment score from Finnhub."""
        cache_key = f"news:{symbol}"
        cached = _get_cached(cache_key, _CACHE_TTL_NEWS)
        if cached is not None:
            return cached

        now = datetime.utcnow()
        from_date = (now - timedelta(days=1)).strftime("%Y-%m-%d")
        to_date = now.strftime("%Y-%m-%d")

        resp = await client.get(
            "https://finnhub.io/api/v1/company-news",
            params={
                "symbol": symbol.upper(),
                "from": from_date,
                "to": to_date,
                "token": api_key,
            },
        )

        if resp.status_code == 429:
            logger.warning("finnhub_rate_limited", endpoint="company-news", symbol=symbol)
            return {"score": None, "count": 0}
        if resp.status_code != 200:
            return {"score": None, "count": 0}

        articles = resp.json()
        if not isinstance(articles, list):
            return {"score": None, "count": 0}

        count = len(articles)
        if count == 0:
            result = {"score": None, "count": 0}
            _set_cached(cache_key, result)
            return result

        # Finnhub news articles don't include sentiment directly.
        # Use Finnhub's news-sentiment endpoint if available.
        sentiment_resp = await client.get(
            "https://finnhub.io/api/v1/news-sentiment",
            params={"symbol": symbol.upper(), "token": api_key},
        )

        score: float | None = None
        if sentiment_resp.status_code == 200:
            data = sentiment_resp.json()
            sentiment = data.get("sentiment") or {}
            # Finnhub returns bullish/bearish scores
            bullish = sentiment.get("bullishPercent", 0.5)
            # Map 0-1 bullish to -1 to +1
            if bullish is not None:
                score = float(bullish) * 2 - 1  # 0 -> -1, 0.5 -> 0, 1 -> +1
                score = max(-1.0, min(1.0, score))

        result = {"score": score, "count": count}
        _set_cached(cache_key, result)
        return result

    async def _fetch_earnings_proximity(
        self, client, api_key: str, symbol: str,
    ) -> int | None:
        """Days until next earnings date from Finnhub earnings calendar."""
        cache_key = f"earnings:{symbol}"
        cached = _get_cached(cache_key, _CACHE_TTL_EARNINGS)
        if cached is not None:
            return cached

        now = datetime.utcnow()
        from_date = now.strftime("%Y-%m-%d")
        to_date = (now + timedelta(days=90)).strftime("%Y-%m-%d")

        resp = await client.get(
            "https://finnhub.io/api/v1/calendar/earnings",
            params={
                "symbol": symbol.upper(),
                "from": from_date,
                "to": to_date,
                "token": api_key,
            },
        )

        if resp.status_code != 200:
            return None

        data = resp.json()
        earnings = data.get("earningsCalendar", [])
        if not earnings:
            _set_cached(cache_key, None)
            return None

        # Find the earliest upcoming date
        closest_days: int | None = None
        for entry in earnings:
            date_str = entry.get("date")
            if not date_str:
                continue
            try:
                earn_date = datetime.strptime(date_str, "%Y-%m-%d")
                days = (earn_date - now).days
                if days >= 0 and (closest_days is None or days < closest_days):
                    closest_days = days
            except ValueError:
                continue

        _set_cached(cache_key, closest_days)
        return closest_days

    async def _fetch_sector_sentiment(
        self, client, api_key: str, symbol: str,
    ) -> float | None:
        """Aggregate sentiment for the stock's sector via market news."""
        cache_key = f"sector_sent:{symbol}"
        cached = _get_cached(cache_key, _CACHE_TTL_SECTOR)
        if cached is not None:
            return cached

        # First, determine the sector via Finnhub's company profile
        profile_resp = await client.get(
            "https://finnhub.io/api/v1/stock/profile2",
            params={"symbol": symbol.upper(), "token": api_key},
        )
        if profile_resp.status_code != 200:
            return None

        profile = profile_resp.json()
        sector = profile.get("finnhubIndustry") or profile.get("industry")
        if not sector:
            return None

        # Get general market news and filter by sector keywords
        resp = await client.get(
            "https://finnhub.io/api/v1/news",
            params={"category": "general", "token": api_key},
        )
        if resp.status_code != 200:
            return None

        articles = resp.json()
        if not isinstance(articles, list):
            return None

        # Simple keyword match for sector-related articles
        sector_lower = sector.lower()
        sector_words = set(sector_lower.split())
        relevant_count = 0
        positive_count = 0
        negative_count = 0

        positive_words = {"surge", "gain", "rally", "bullish", "upgrade", "beat", "growth", "strong", "record", "high"}
        negative_words = {"drop", "fall", "crash", "bearish", "downgrade", "miss", "decline", "weak", "loss", "low"}

        for article in articles[:100]:  # Cap processing
            headline = (article.get("headline") or "").lower()
            summary = (article.get("summary") or "").lower()
            text = headline + " " + summary

            if not any(word in text for word in sector_words):
                continue

            relevant_count += 1
            headline_words = set(headline.split())
            if headline_words & positive_words:
                positive_count += 1
            if headline_words & negative_words:
                negative_count += 1

        if relevant_count == 0:
            _set_cached(cache_key, None)
            return None

        total_sentiment = positive_count + negative_count
        if total_sentiment == 0:
            score = 0.0
        else:
            # Map to -1..+1
            score = (positive_count - negative_count) / total_sentiment

        _set_cached(cache_key, score)
        return score
