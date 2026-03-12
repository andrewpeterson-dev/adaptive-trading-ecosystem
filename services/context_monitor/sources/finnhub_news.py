"""Finnhub market news."""
from __future__ import annotations
import hashlib
from datetime import datetime, timedelta
import structlog
from config.settings import get_settings

logger = structlog.get_logger(__name__)

async def fetch_finnhub_news_events() -> list[dict]:
    settings = get_settings()
    if not settings.finnhub_api_key:
        return []

    try:
        import httpx
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://finnhub.io/api/v1/news",
                params={"category": "general", "token": settings.finnhub_api_key},
            )
            resp.raise_for_status()
            articles = resp.json()

        events = []
        for article in articles[:20]:
            headline = article.get("headline", "")
            if not headline:
                continue

            source_id = hashlib.sha256(
                f"finnhub_news_{article.get('id', '')}_{headline[:50]}".encode()
            ).hexdigest()[:32]

            related = article.get("related", "")
            symbols = [s.strip() for s in related.split(",") if s.strip()] if related else []

            events.append({
                "event_type": "news",
                "impact": "LOW",
                "symbols": symbols[:10],
                "sectors": [],
                "headline": headline[:512],
                "raw_data": {"url": article.get("url", ""), "source": article.get("source", ""), "datetime": article.get("datetime", 0)},
                "source": "finnhub",
                "source_id": source_id,
                "expires_at": datetime.utcnow() + timedelta(hours=4),
            })
        return events
    except Exception as e:
        logger.warning("finnhub_news_failed", error=str(e))
        return []
