"""Sentiment analysis tools for the Cerberus."""
from __future__ import annotations

import structlog

from services.ai_core.tools.base import ToolDefinition, ToolCategory, ToolSideEffect
from services.ai_core.tools.registry import get_registry

logger = structlog.get_logger(__name__)


async def _get_sentiment_analysis(user_id: int, ticker: str, lookback_days: int = 7) -> dict:
    from services.sentiment.sentiment_service import get_sentiment_service
    service = get_sentiment_service()
    return await service.analyze_ticker(ticker=ticker, lookback_days=lookback_days)


async def _get_batch_sentiment(user_id: int, tickers: list, lookback_days: int = 7) -> dict:
    from services.sentiment.sentiment_service import get_sentiment_service
    if not tickers:
        return {"error": "No tickers provided", "results": {}}
    service = get_sentiment_service()
    results = await service.analyze_batch(tickers=tickers)
    return {"results": results, "count": len(results)}


async def _get_market_mood(user_id: int) -> dict:
    from services.sentiment.sentiment_service import get_sentiment_service
    service = get_sentiment_service()
    return await service.market_mood()


def register():
    registry = get_registry()

    registry.register(ToolDefinition(
        name="getSentimentAnalysis", version="1.0",
        description="Get AI-powered financial sentiment analysis for a ticker symbol using FinGPT. Analyzes recent news headlines and articles, returning bullish/bearish/neutral with a confidence score.",
        category=ToolCategory.MARKET, side_effect=ToolSideEffect.READ,
        timeout_ms=30000, cache_ttl_s=900,
        input_schema={"type": "object", "properties": {"ticker": {"type": "string", "description": "Ticker symbol (e.g., AAPL, TSLA, SPY)"}, "lookback_days": {"type": "integer", "description": "Number of days of news to analyze", "default": 7}}, "required": ["ticker"]},
        output_schema={"type": "object"}, handler=_get_sentiment_analysis,
    ))

    registry.register(ToolDefinition(
        name="getBatchSentiment", version="1.0",
        description="Get sentiment analysis for multiple ticker symbols at once",
        category=ToolCategory.MARKET, side_effect=ToolSideEffect.READ,
        timeout_ms=60000, cache_ttl_s=900,
        input_schema={"type": "object", "properties": {"tickers": {"type": "array", "items": {"type": "string"}, "description": "List of ticker symbols to analyze"}, "lookback_days": {"type": "integer", "description": "Number of days of news to analyze", "default": 7}}, "required": ["tickers"]},
        output_schema={"type": "object"}, handler=_get_batch_sentiment,
    ))

    registry.register(ToolDefinition(
        name="getMarketMood", version="1.0",
        description="Get aggregated market mood sentiment across major indices (SPY, QQQ, DIA). Returns overall bullish/bearish/neutral with breakdown per index.",
        category=ToolCategory.MARKET, side_effect=ToolSideEffect.READ,
        timeout_ms=60000, cache_ttl_s=900,
        input_schema={"type": "object", "properties": {}},
        output_schema={"type": "object"}, handler=_get_market_mood,
    ))
