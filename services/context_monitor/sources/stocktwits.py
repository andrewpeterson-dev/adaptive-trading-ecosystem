"""StockTwits public sentiment."""
from __future__ import annotations
import hashlib
from datetime import datetime, timedelta
import structlog

logger = structlog.get_logger(__name__)

WATCHED_SYMBOLS = ["SPY", "QQQ", "AAPL", "TSLA", "NVDA", "AMZN", "META", "MSFT", "GOOGL"]

async def fetch_stocktwits_events() -> list[dict]:
    events = []
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10) as client:
            for symbol in WATCHED_SYMBOLS:
                try:
                    resp = await client.get(f"https://api.stocktwits.com/api/2/streams/symbol/{symbol}.json")
                    if resp.status_code != 200:
                        continue
                    data = resp.json()

                    sentiment = data.get("symbol", {}).get("sentiment", {})
                    if not sentiment:
                        continue

                    bullish = sentiment.get("bullish", 0) or 0
                    bearish = sentiment.get("bearish", 0) or 0
                    total = bullish + bearish
                    if total < 50:
                        continue

                    bull_pct = bullish / total * 100
                    if 30 <= bull_pct <= 70:
                        continue

                    if bull_pct > 70:
                        headline = f"StockTwits: {symbol} extremely bullish ({bull_pct:.0f}% bullish)"
                    else:
                        headline = f"StockTwits: {symbol} extremely bearish ({100-bull_pct:.0f}% bearish)"

                    source_id = hashlib.sha256(f"stocktwits_{symbol}_{datetime.utcnow().strftime('%Y%m%d%H')}".encode()).hexdigest()[:32]
                    events.append({
                        "event_type": "sentiment",
                        "impact": "LOW",
                        "symbols": [symbol],
                        "sectors": [],
                        "headline": headline,
                        "raw_data": {"bullish": bullish, "bearish": bearish, "total": total},
                        "source": "stocktwits",
                        "source_id": source_id,
                        "expires_at": datetime.utcnow() + timedelta(hours=1),
                    })
                except Exception:
                    continue
    except Exception as e:
        logger.warning("stocktwits_fetch_failed", error=str(e))
    return events
