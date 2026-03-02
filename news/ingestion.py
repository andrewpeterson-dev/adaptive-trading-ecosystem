"""
News ingestion from free APIs with rate limiting and caching.
Primary: Alpha Vantage NEWS_SENTIMENT endpoint (free tier).
Fallback: Finnhub news endpoint.
"""

import re
import time
from datetime import datetime, timezone

import httpx
import structlog

from config.settings import get_settings
from news.ticker_validator import TickerValidator

logger = structlog.get_logger(__name__)


class NewsIngestion:
    """Fetch news articles from free APIs with rate limiting and caching."""

    def __init__(self):
        self.settings = get_settings()
        self._validator = TickerValidator()
        # In-memory TTL cache: key -> (articles, fetch_time)
        self._cache: dict[str, tuple[list[dict], float]] = {}
        self._cache_ttl = 300  # 5 minutes
        # Rate limiting
        self._last_request_time: float = 0
        self._min_request_interval = 1.0  # seconds between API calls

    def fetch_news(self, symbols: list[str], limit: int = 10) -> list[dict]:
        """
        Fetch recent news for given ticker symbols.
        Returns list of article dicts with keys:
            title, url, source, published_at, summary, symbols
        """
        # Validate symbols first
        valid_symbols = [s.upper().strip() for s in symbols if self._validator.is_valid(s)]
        if not valid_symbols:
            logger.warning("no_valid_symbols", requested=symbols)
            return []

        cache_key = ",".join(sorted(valid_symbols))
        cached = self._get_cached(cache_key)
        if cached is not None:
            logger.debug("news_cache_hit", symbols=valid_symbols)
            return cached[:limit]

        # Try Alpha Vantage first
        articles = self._fetch_alphavantage(valid_symbols, limit)

        # Fallback to Finnhub
        if not articles:
            articles = self._fetch_finnhub(valid_symbols, limit)

        self._cache[cache_key] = (articles, time.time())
        return articles[:limit]

    def extract_tickers(self, text: str) -> list[str]:
        """Extract ticker symbols mentioned in article text."""
        if not text:
            return []
        # Match $TICKER or standalone uppercase 1-5 letter words that are known tickers
        dollar_tickers = re.findall(r"\$([A-Z]{1,5})", text)
        # Also match standalone uppercase words that are known tickers
        word_tickers = re.findall(r"\b([A-Z]{2,5})\b", text)
        candidates = set(dollar_tickers + word_tickers)
        # Filter to only validated tickers to avoid false positives
        return [t for t in candidates if self._validator.is_valid(t)]

    def _rate_limit(self):
        """Enforce minimum interval between API requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_request_interval:
            time.sleep(self._min_request_interval - elapsed)
        self._last_request_time = time.time()

    def _get_cached(self, key: str):
        """Return cached articles if still fresh, else None."""
        if key in self._cache:
            articles, fetch_time = self._cache[key]
            if time.time() - fetch_time < self._cache_ttl:
                return articles
            del self._cache[key]
        return None

    def _fetch_alphavantage(self, symbols: list[str], limit: int) -> list[dict]:
        """Fetch from Alpha Vantage NEWS_SENTIMENT (free tier: 25 req/day)."""
        api_key = self.settings.alphavantage_api_key if hasattr(self.settings, "alphavantage_api_key") else ""
        if not api_key:
            # Use demo key for limited access
            api_key = "demo"

        tickers = ",".join(symbols)
        url = "https://www.alphavantage.co/query"
        params = {
            "function": "NEWS_SENTIMENT",
            "tickers": tickers,
            "limit": min(limit * 2, 50),  # fetch extra, filter later
            "apikey": api_key,
        }

        self._rate_limit()
        try:
            resp = httpx.get(url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.warning("alphavantage_fetch_failed", error=str(e))
            return []

        if "feed" not in data:
            logger.debug("alphavantage_no_feed", response_keys=list(data.keys()))
            return []

        articles = []
        for item in data["feed"]:
            # Extract relevant tickers from Alpha Vantage's ticker_sentiment
            item_tickers = [
                ts["ticker"] for ts in item.get("ticker_sentiment", [])
                if ts["ticker"] in symbols
            ]
            if not item_tickers:
                item_tickers = symbols  # fallback: associate with requested symbols

            published = item.get("time_published", "")
            try:
                dt = datetime.strptime(published, "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)
                published_iso = dt.isoformat()
            except (ValueError, TypeError):
                published_iso = published

            articles.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "source": item.get("source", ""),
                "published_at": published_iso,
                "summary": item.get("summary", ""),
                "symbols": item_tickers,
            })

        logger.info("alphavantage_fetched", count=len(articles), symbols=symbols)
        return articles

    def _fetch_finnhub(self, symbols: list[str], limit: int) -> list[dict]:
        """Fallback: fetch from Finnhub free API (60 calls/min)."""
        api_key = self.settings.finnhub_api_key if hasattr(self.settings, "finnhub_api_key") else ""
        if not api_key:
            logger.debug("finnhub_no_api_key")
            return []

        articles = []
        now = datetime.now(timezone.utc)
        from_date = now.strftime("%Y-%m-%d")

        for symbol in symbols[:5]:  # limit to avoid rate exhaustion
            url = "https://finnhub.io/api/v1/company-news"
            params = {
                "symbol": symbol,
                "from": from_date,
                "to": from_date,
                "token": api_key,
            }
            self._rate_limit()
            try:
                resp = httpx.get(url, params=params, timeout=10)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                logger.warning("finnhub_fetch_failed", symbol=symbol, error=str(e))
                continue

            for item in data[:limit]:
                published = item.get("datetime", 0)
                try:
                    published_iso = datetime.fromtimestamp(published, tz=timezone.utc).isoformat()
                except (ValueError, TypeError, OSError):
                    published_iso = str(published)

                articles.append({
                    "title": item.get("headline", ""),
                    "url": item.get("url", ""),
                    "source": item.get("source", ""),
                    "published_at": published_iso,
                    "summary": item.get("summary", ""),
                    "symbols": [symbol],
                })

        logger.info("finnhub_fetched", count=len(articles), symbols=symbols)
        return articles
