"""Impact classification for market events."""
from __future__ import annotations

import json

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

    # If rules-based pass fell through to the default LOW, the headline may
    # be ambiguous.  Escalate to LLM for a more informed classification.
    default_impact = event.get("impact", "LOW")
    if default_impact == "LOW" and event_type == "news" and headline:
        symbols = event.get("symbols") or []
        return _llm_classify_sync(event.get("headline") or "", symbols)

    return default_impact


async def classify_impact_async(event: dict) -> str:
    """Async variant that can call the LLM for ambiguous headlines."""
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

    default_impact = event.get("impact", "LOW")
    if default_impact == "LOW" and event_type == "news" and (event.get("headline") or ""):
        symbols = event.get("symbols") or []
        impact, _ = await _llm_classify(event.get("headline") or "", symbols)
        return impact

    return default_impact


async def _llm_classify(headline: str, symbols: list[str]) -> tuple[str, str]:
    """Use LLM to classify ambiguous news headlines."""
    try:
        from services.ai_core.model_router import ModelRouter
        from services.ai_core.providers.base import ProviderMessage

        router = ModelRouter()
        routing = router.route(mode="simple", message=headline, has_tools=False)
        response = await routing.provider.complete(
            messages=[
                ProviderMessage(
                    role="system",
                    content=(
                        "You classify financial news impact. Return JSON only: "
                        '{"impact": "LOW"|"MEDIUM"|"HIGH", '
                        '"event_type": "news"|"earnings"|"macro"|"volatility"|"sentiment"}'
                    ),
                ),
                ProviderMessage(
                    role="user",
                    content=f"Headline: {headline}\nSymbols: {', '.join(symbols) if symbols else 'N/A'}",
                ),
            ],
            model=routing.model,
            temperature=0.1,
            max_tokens=100,
            store=False,
        )
        text = response.content if hasattr(response, "content") else str(response)
        parsed = json.loads(text.strip())
        impact = str(parsed.get("impact", "LOW")).upper()
        event_type = str(parsed.get("event_type", "news")).lower()
        if impact not in ("LOW", "MEDIUM", "HIGH"):
            impact = "LOW"
        logger.info("llm_classify_result", headline=headline[:80], impact=impact, event_type=event_type)
        return (impact, event_type)
    except Exception as exc:
        logger.warning("llm_classify_failed", error=str(exc), headline=headline[:80])
        return ("LOW", "news")


def _llm_classify_sync(headline: str, symbols: list[str]) -> str:
    """Sync wrapper that attempts async LLM classification, falls back to LOW."""
    try:
        import asyncio
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Cannot await in a running loop from sync code — return LOW
            return "LOW"
        impact, _ = loop.run_until_complete(_llm_classify(headline, symbols))
        return impact
    except Exception:
        return "LOW"
