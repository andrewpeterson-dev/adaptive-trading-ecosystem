"""Impact classification for market events."""
from __future__ import annotations
import structlog

logger = structlog.get_logger(__name__)

def classify_impact(event: dict) -> str:
    """Rules-based impact classification. Returns 'LOW', 'MEDIUM', or 'HIGH'."""
    event_type = event.get("event_type", "")
    headline = (event.get("headline") or "").upper()
    raw_data = event.get("raw_data", {})

    # HIGH impact keywords
    high_keywords = ["FOMC", "FED RATE", "CIRCUIT BREAKER", "HALT", "CRASH", "EMERGENCY", "WAR", "TARIFF", "SANCTIONS"]
    for kw in high_keywords:
        if kw in headline:
            return "HIGH"

    # Sector moves >3%
    if event_type == "sector_move":
        change = abs(raw_data.get("change_pct", 0))
        if change > 3.0:
            return "HIGH"
        if change > 2.0:
            return "MEDIUM"

    # VIX-based
    if event_type == "volatility":
        vix = raw_data.get("vix", 0)
        if vix > 40:
            return "HIGH"
        if vix > 25:
            return "HIGH"
        if vix > 18:
            return "MEDIUM"

    # Sentiment extremes
    if event_type == "sentiment":
        score = raw_data.get("score", 50)
        if score < 15 or score > 85:
            return "HIGH"
        if score < 25 or score > 75:
            return "MEDIUM"

    return event.get("impact", "LOW")
