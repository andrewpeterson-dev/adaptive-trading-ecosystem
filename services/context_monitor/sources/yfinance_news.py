"""Yahoo Finance news — free fallback when Finnhub key is unavailable."""
from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime, timedelta

import structlog

logger = structlog.get_logger(__name__)

WATCHED_SYMBOLS = ["AAPL", "TSLA", "NVDA", "MSFT", "AMZN", "META", "GOOGL", "SPY", "QQQ"]


def _fetch_yfinance_news_sync() -> list[dict]:
    results = []
    try:
        import yfinance as yf

        for symbol in WATCHED_SYMBOLS:
            try:
                ticker = yf.Ticker(symbol)
                news = ticker.news or []
                for article in news[:3]:
                    # yfinance v2 nests everything inside 'content'
                    content = article.get("content", article)
                    title = content.get("title", "") or article.get("title", "")
                    if not title:
                        continue

                    # Parse publish time — try ISO format first, then unix timestamp
                    pub_date = content.get("pubDate", "")
                    if pub_date:
                        try:
                            pub_time = int(datetime.fromisoformat(pub_date.replace("Z", "+00:00")).timestamp())
                        except (ValueError, TypeError):
                            pub_time = 0
                    else:
                        pub_time = article.get("providerPublishTime", 0)

                    # Skip articles older than 24h
                    if pub_time and (datetime.utcnow().timestamp() - pub_time) > 86400:
                        continue

                    # Extract URL from canonical or clickthrough
                    url = ""
                    canonical = content.get("canonicalUrl", {})
                    if isinstance(canonical, dict):
                        url = canonical.get("url", "")
                    if not url:
                        url = article.get("link", "")

                    provider = content.get("provider", {})
                    source_name = provider.get("displayName", "Yahoo Finance") if isinstance(provider, dict) else "Yahoo Finance"

                    results.append({
                        "symbol": symbol,
                        "title": title,
                        "url": url,
                        "source": source_name,
                        "pub_time": pub_time,
                    })
            except Exception:
                continue
    except Exception as e:
        logger.warning("yfinance_news_fetch_failed", error=str(e))
    return results


async def fetch_yfinance_news_events() -> list[dict]:
    loop = asyncio.get_running_loop()
    articles = await loop.run_in_executor(None, _fetch_yfinance_news_sync)

    events = []
    seen = set()
    for article in articles:
        title = article["title"]
        source_id = hashlib.sha256(f"yfnews_{title[:60]}".encode()).hexdigest()[:32]
        if source_id in seen:
            continue
        seen.add(source_id)

        events.append({
            "event_type": "news",
            "impact": "LOW",
            "symbols": [article["symbol"]],
            "sectors": [],
            "headline": title[:512],
            "raw_data": {
                "url": article.get("url", ""),
                "source": article.get("source", "Yahoo Finance"),
                "datetime": article.get("pub_time", 0),
            },
            "source": "yfinance",
            "source_id": source_id,
            "expires_at": datetime.utcnow() + timedelta(hours=6),
        })
    return events
