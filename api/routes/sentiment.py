"""Sentiment analysis API endpoints."""
from __future__ import annotations

from typing import List, Optional

import structlog
from fastapi import APIRouter, HTTPException, Query, Request

from services.sentiment.sentiment_service import get_sentiment_service

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.get("/batch/analyze")
async def get_batch_sentiment(
    request: Request,
    tickers: str = Query(description="Comma-separated ticker symbols (e.g., AAPL,TSLA,MSFT)"),
    lookback_days: int = Query(default=7, ge=1, le=30, description="Days of news to analyze"),
) -> dict:
    ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    if not ticker_list:
        raise HTTPException(status_code=400, detail="No valid tickers provided")
    if len(ticker_list) > 20:
        raise HTTPException(status_code=400, detail="Maximum 20 tickers per batch request")
    try:
        service = get_sentiment_service()
        results = await service.analyze_batch(tickers=ticker_list)
        return {"results": results, "count": len(results)}
    except Exception as exc:
        logger.error("sentiment_batch_error", tickers=ticker_list, error=str(exc))
        raise HTTPException(status_code=500, detail="Batch sentiment analysis failed. Please try again.")


@router.get("/market-mood/overview")
async def get_market_mood(request: Request) -> dict:
    try:
        service = get_sentiment_service()
        return await service.market_mood()
    except Exception as exc:
        logger.error("market_mood_error", error=str(exc))
        raise HTTPException(status_code=500, detail="Market mood analysis failed. Please try again.")


@router.get("/{ticker}")
async def get_sentiment(
    request: Request,
    ticker: str,
    lookback_days: int = Query(default=7, ge=1, le=30, description="Days of news to analyze"),
) -> dict:
    try:
        service = get_sentiment_service()
        return await service.analyze_ticker(ticker=ticker, lookback_days=lookback_days)
    except Exception as exc:
        logger.error("sentiment_endpoint_error", ticker=ticker, error=str(exc))
        raise HTTPException(status_code=500, detail="Sentiment analysis failed. Please try again.")
