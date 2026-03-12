"""VIX volatility level via yfinance."""
from __future__ import annotations
import asyncio
import hashlib
from datetime import datetime, timedelta
import structlog

logger = structlog.get_logger(__name__)

def _fetch_vix_sync() -> dict | None:
    try:
        import yfinance as yf
        ticker = yf.Ticker("^VIX")
        hist = ticker.history(period="1d", interval="1m")
        if hist.empty:
            return None
        last = hist.iloc[-1]
        vix_val = float(last["Close"])
        return {"vix": vix_val, "timestamp": datetime.utcnow().isoformat()}
    except Exception as e:
        logger.warning("vix_fetch_failed", error=str(e))
        return None

async def fetch_vix_events() -> list[dict]:
    loop = asyncio.get_running_loop()
    data = await loop.run_in_executor(None, _fetch_vix_sync)
    if not data:
        return []

    vix = data["vix"]
    if vix < 18:
        return []

    if vix > 40:
        impact = "HIGH"
        headline = f"VIX EXTREME: {vix:.1f} — market panic levels"
    elif vix > 25:
        impact = "HIGH"
        headline = f"VIX HIGH: {vix:.1f} — elevated volatility"
    else:
        impact = "MEDIUM"
        headline = f"VIX elevated: {vix:.1f}"

    source_id = hashlib.sha256(f"vix_{datetime.utcnow().strftime('%Y%m%d%H')}".encode()).hexdigest()[:32]
    return [{
        "event_type": "volatility",
        "impact": impact,
        "symbols": [],
        "sectors": [],
        "headline": headline,
        "raw_data": data,
        "source": "yfinance_vix",
        "source_id": source_id,
        "expires_at": datetime.utcnow() + timedelta(minutes=30),
    }]
