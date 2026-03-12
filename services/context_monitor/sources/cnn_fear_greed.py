"""CNN Fear & Greed Index."""
from __future__ import annotations
import hashlib
from datetime import datetime, timedelta
import structlog

logger = structlog.get_logger(__name__)

async def fetch_fear_greed_events() -> list[dict]:
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get("https://production.dataviz.cnn.io/index/fearandgreed/graphdata")
            resp.raise_for_status()
            data = resp.json()

        score = data.get("fear_and_greed", {}).get("score")
        if score is None:
            return []

        score = float(score)
        if 25 <= score <= 75:
            return []

        if score < 25:
            impact = "MEDIUM" if score >= 15 else "HIGH"
            headline = f"Fear & Greed: Extreme Fear ({score:.0f})"
        else:
            impact = "MEDIUM" if score <= 85 else "HIGH"
            headline = f"Fear & Greed: Extreme Greed ({score:.0f})"

        source_id = hashlib.sha256(f"fng_{datetime.utcnow().strftime('%Y%m%d%H')}".encode()).hexdigest()[:32]
        return [{
            "event_type": "sentiment",
            "impact": impact,
            "symbols": [],
            "sectors": [],
            "headline": headline,
            "raw_data": {"score": score, "rating": data.get("fear_and_greed", {}).get("rating", "")},
            "source": "cnn_fear_greed",
            "source_id": source_id,
            "expires_at": datetime.utcnow() + timedelta(hours=1),
        }]
    except Exception as e:
        logger.warning("fear_greed_fetch_failed", error=str(e))
        return []
