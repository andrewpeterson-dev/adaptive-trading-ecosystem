"""Finnhub earnings and economic calendar."""
from __future__ import annotations
import hashlib
from datetime import datetime, date, timedelta
import structlog
from config.settings import get_settings

logger = structlog.get_logger(__name__)

async def fetch_earnings_events(api_key_override: str = "") -> list[dict]:
    """Fetch upcoming earnings from Finnhub.

    Uses *api_key_override* first (e.g. from a user's stored connection),
    falls back to the server-level ``FINNHUB_API_KEY`` env var.
    """
    settings = get_settings()
    api_key = api_key_override or settings.finnhub_api_key
    if not api_key:
        logger.debug("finnhub_no_api_key")
        return []

    try:
        import httpx
        today = date.today()
        from_date = today.isoformat()
        to_date = (today + timedelta(days=7)).isoformat()

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://finnhub.io/api/v1/calendar/earnings",
                params={"from": from_date, "to": to_date, "token": api_key},
            )
            resp.raise_for_status()
            data = resp.json()

        events = []
        for item in (data.get("earningsCalendar") or [])[:50]:
            symbol = item.get("symbol", "")
            report_date = item.get("date", "")
            if not symbol or not report_date:
                continue

            source_id = hashlib.sha256(f"earnings_{symbol}_{report_date}".encode()).hexdigest()[:32]

            events.append({
                "event_type": "earnings",
                "impact": "MEDIUM",
                "symbols": [symbol],
                "sectors": [],
                "headline": f"{symbol} earnings on {report_date}",
                "raw_data": item,
                "source": "finnhub",
                "source_id": source_id,
                "expires_at": datetime.utcnow() + timedelta(hours=24),
            })
        return events
    except Exception as e:
        logger.warning("earnings_fetch_failed", error=str(e))
        return []

async def fetch_economic_events() -> list[dict]:
    settings = get_settings()
    if not settings.finnhub_api_key:
        return []

    try:
        import httpx
        today = date.today()

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://finnhub.io/api/v1/calendar/economic",
                params={"from": today.isoformat(), "to": (today + timedelta(days=3)).isoformat(), "token": settings.finnhub_api_key},
            )
            resp.raise_for_status()
            data = resp.json()

        events = []
        for item in (data.get("economicCalendar") or [])[:30]:
            event_name = item.get("event", "")
            if not event_name:
                continue

            impact_val = item.get("impact", 1)
            impact = "HIGH" if impact_val >= 3 else ("MEDIUM" if impact_val >= 2 else "LOW")

            source_id = hashlib.sha256(f"econ_{event_name}_{item.get('time', '')}".encode()).hexdigest()[:32]

            events.append({
                "event_type": "macro",
                "impact": impact,
                "symbols": [],
                "sectors": [],
                "headline": event_name[:512],
                "raw_data": item,
                "source": "finnhub",
                "source_id": source_id,
                "expires_at": datetime.utcnow() + timedelta(hours=1),
            })
        return events
    except Exception as e:
        logger.warning("economic_fetch_failed", error=str(e))
        return []
