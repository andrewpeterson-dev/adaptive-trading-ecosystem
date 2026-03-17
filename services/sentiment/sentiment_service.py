"""High-level sentiment analysis service."""
from __future__ import annotations

import asyncio
import math
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import structlog

from config.settings import get_settings
from services.ai_core.providers.fingpt_provider import FinGPTProvider

logger = structlog.get_logger(__name__)

_SOURCE_CREDIBILITY: Dict[str, float] = {
    "reuters": 1.0, "bloomberg": 1.0, "wsj": 0.95, "wall street journal": 0.95,
    "financial times": 0.95, "ft": 0.95, "cnbc": 0.85, "marketwatch": 0.8,
    "barrons": 0.85, "yahoo finance": 0.7, "yahoo": 0.7, "seeking alpha": 0.65,
    "motley fool": 0.6, "benzinga": 0.65, "investopedia": 0.7,
    "alpha vantage": 0.7, "finnhub": 0.7,
}
_DEFAULT_CREDIBILITY = 0.5
_cache: Dict[str, tuple] = {}


def _get_source_credibility(source: Optional[str]) -> float:
    if not source:
        return _DEFAULT_CREDIBILITY
    source_lower = source.lower().strip()
    for known_source, weight in _SOURCE_CREDIBILITY.items():
        if known_source in source_lower:
            return weight
    return _DEFAULT_CREDIBILITY


def _compute_recency_weight(published_at: Optional[str], now: datetime) -> float:
    if not published_at:
        return 0.3
    try:
        if isinstance(published_at, str):
            pub_dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        else:
            pub_dt = published_at
        if pub_dt.tzinfo is None:
            pub_dt = pub_dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return 0.3
    age_hours = max(0.0, (now - pub_dt).total_seconds() / 3600.0)
    half_life_hours = 48.0
    weight = math.exp(-0.693 * age_hours / half_life_hours)
    return max(0.1, weight)


async def _fetch_news_for_ticker(ticker: str, lookback_days: int = 7) -> List[Dict[str, Any]]:
    articles: List[Dict[str, Any]] = []
    try:
        from news.ingestion import NewsIngestion
        ingestion = NewsIngestion()
        articles = await ingestion.fetch_news_async([ticker], limit=20)
        if articles:
            logger.info("sentiment_news_fetched", ticker=ticker, source="news_ingestion", count=len(articles))
            return articles
    except Exception as exc:
        logger.warning("sentiment_news_ingestion_failed", ticker=ticker, error=str(exc))

    try:
        import yfinance as yf

        def _fetch_yf_news() -> List[Dict[str, Any]]:
            t = yf.Ticker(ticker)
            news_items = t.news or []
            results: List[Dict[str, Any]] = []
            for item in news_items[:20]:
                results.append({
                    "title": item.get("title", ""),
                    "summary": item.get("summary", item.get("title", "")),
                    "url": item.get("link", ""),
                    "published_at": item.get("providerPublishTime", ""),
                    "source": item.get("publisher", ""),
                })
            return results

        articles = await asyncio.to_thread(_fetch_yf_news)
        if articles:
            logger.info("sentiment_news_fetched", ticker=ticker, source="yfinance", count=len(articles))
    except Exception as exc:
        logger.warning("sentiment_yfinance_news_failed", ticker=ticker, error=str(exc))
    return articles


class SentimentService:
    """Aggregated sentiment analysis for tickers."""

    def __init__(self) -> None:
        self._provider = FinGPTProvider()
        self._settings = get_settings()

    async def analyze_ticker(self, ticker: str, lookback_days: int = 7) -> Dict[str, Any]:
        ticker = ticker.upper().strip()
        cache_ttl = self._settings.sentiment_cache_ttl

        cached = _cache.get(ticker)
        if cached is not None:
            result, cached_at = cached
            if time.time() - cached_at < cache_ttl:
                logger.info("sentiment_cache_hit", ticker=ticker)
                return result

        articles = await _fetch_news_for_ticker(ticker, lookback_days)
        if not articles:
            result = {
                "ticker": ticker, "overall_sentiment": "neutral", "score": 0.0,
                "confidence": 0.0, "num_articles": 0, "top_bullish": [],
                "top_bearish": [], "timestamp": datetime.now(timezone.utc).isoformat(),
                "message": "No news articles found for sentiment analysis",
            }
            _cache[ticker] = (result, time.time())
            return result

        now = datetime.now(timezone.utc)
        sentiment_tasks = []
        for article in articles:
            text = article.get("title", "")
            summary = article.get("summary", "")
            if summary and summary != text:
                text = f"{text}. {summary}"
            sentiment_tasks.append(self._provider.analyze_sentiment(text))

        sentiments = await asyncio.gather(*sentiment_tasks, return_exceptions=True)

        weighted_score_sum = 0.0
        weighted_confidence_sum = 0.0
        total_weight = 0.0
        scored_articles: List[Dict[str, Any]] = []

        for article, sentiment in zip(articles, sentiments):
            if isinstance(sentiment, Exception):
                logger.warning("sentiment_article_failed", error=str(sentiment))
                continue
            recency_weight = _compute_recency_weight(article.get("published_at"), now)
            credibility_weight = _get_source_credibility(article.get("source"))
            combined_weight = recency_weight * credibility_weight
            weighted_score_sum += sentiment["score"] * combined_weight
            weighted_confidence_sum += sentiment["confidence"] * combined_weight
            total_weight += combined_weight
            scored_articles.append({
                "title": article.get("title", ""), "source": article.get("source", ""),
                "url": article.get("url", ""), "published_at": article.get("published_at", ""),
                "sentiment": sentiment["sentiment"], "score": sentiment["score"],
                "confidence": sentiment["confidence"], "weight": round(combined_weight, 4),
            })

        if total_weight > 0:
            overall_score = weighted_score_sum / total_weight
            overall_confidence = weighted_confidence_sum / total_weight
        else:
            overall_score = 0.0
            overall_confidence = 0.0

        if overall_score > 0.15:
            overall_sentiment = "bullish"
        elif overall_score < -0.15:
            overall_sentiment = "bearish"
        else:
            overall_sentiment = "neutral"

        sorted_by_score = sorted(scored_articles, key=lambda x: x["score"], reverse=True)
        top_bullish = [a for a in sorted_by_score if a["score"] > 0.1][:3]
        top_bearish = [a for a in sorted_by_score if a["score"] < -0.1][-3:]
        top_bearish.reverse()

        result = {
            "ticker": ticker, "overall_sentiment": overall_sentiment,
            "score": round(overall_score, 4), "confidence": round(overall_confidence, 4),
            "num_articles": len(scored_articles), "top_bullish": top_bullish,
            "top_bearish": top_bearish, "timestamp": now.isoformat(),
        }
        _cache[ticker] = (result, time.time())
        logger.info("sentiment_analysis_complete", ticker=ticker, sentiment=overall_sentiment, score=round(overall_score, 4), articles=len(scored_articles))
        return result

    async def analyze_batch(self, tickers: List[str]) -> Dict[str, Dict[str, Any]]:
        tasks = [self.analyze_ticker(t) for t in tickers]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        output: Dict[str, Dict[str, Any]] = {}
        for ticker, result in zip(tickers, results):
            if isinstance(result, Exception):
                logger.warning("sentiment_batch_ticker_failed", ticker=ticker, error=str(result))
                output[ticker.upper()] = {
                    "ticker": ticker.upper(), "overall_sentiment": "neutral",
                    "score": 0.0, "confidence": 0.0, "num_articles": 0,
                    "top_bullish": [], "top_bearish": [],
                    "timestamp": datetime.now(timezone.utc).isoformat(), "error": str(result),
                }
            else:
                output[ticker.upper()] = result
        return output

    async def market_mood(self) -> Dict[str, Any]:
        indices = ["SPY", "QQQ", "DIA"]
        results = await self.analyze_batch(indices)
        scores = [r["score"] for r in results.values() if r.get("score") is not None]
        confidences = [r["confidence"] for r in results.values() if r.get("confidence") is not None]
        if scores:
            avg_score = sum(scores) / len(scores)
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        else:
            avg_score = 0.0
            avg_confidence = 0.0
        if avg_score > 0.15:
            mood = "bullish"
        elif avg_score < -0.15:
            mood = "bearish"
        else:
            mood = "neutral"
        return {
            "market_mood": mood, "score": round(avg_score, 4),
            "confidence": round(avg_confidence, 4), "indices": results,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


_service: Optional[SentimentService] = None


def get_sentiment_service() -> SentimentService:
    global _service
    if _service is None:
        _service = SentimentService()
    return _service
