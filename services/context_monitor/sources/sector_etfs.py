"""Sector ETF momentum tracking."""
from __future__ import annotations
import asyncio
import hashlib
from datetime import datetime, timedelta
import structlog

logger = structlog.get_logger(__name__)

SECTOR_ETFS = {
    "SPY": "S&P 500",
    "QQQ": "Nasdaq 100",
    "XLF": "Financials",
    "XLK": "Technology",
    "XLE": "Energy",
    "XLV": "Healthcare",
    "XLI": "Industrials",
    "XLU": "Utilities",
    "XLP": "Consumer Staples",
    "XLY": "Consumer Discretionary",
    "XLRE": "Real Estate",
    "XLB": "Materials",
    "XLC": "Communication Services",
}

def _fetch_sector_data_sync() -> list[dict]:
    results = []
    try:
        import yfinance as yf
        tickers = yf.Tickers(" ".join(SECTOR_ETFS.keys()))
        for symbol, name in SECTOR_ETFS.items():
            try:
                hist = tickers.tickers[symbol].history(period="2d", interval="1d")
                if len(hist) < 2:
                    continue
                prev_close = float(hist.iloc[-2]["Close"])
                curr_close = float(hist.iloc[-1]["Close"])
                change_pct = ((curr_close - prev_close) / prev_close) * 100
                results.append({"symbol": symbol, "name": name, "change_pct": change_pct})
            except Exception as exc:
                logger.debug("sector_etf_fetch_skipped", symbol=symbol, error=str(exc))
                continue
    except Exception as e:
        logger.warning("sector_etf_fetch_failed", error=str(e))
    return results

async def fetch_sector_events() -> list[dict]:
    loop = asyncio.get_running_loop()
    sectors = await loop.run_in_executor(None, _fetch_sector_data_sync)

    events = []
    for s in sectors:
        if abs(s["change_pct"]) < 0.5:
            continue

        impact = "HIGH" if abs(s["change_pct"]) > 3.0 else "MEDIUM" if abs(s["change_pct"]) > 1.5 else "LOW"
        direction = "up" if s["change_pct"] > 0 else "down"
        headline = f"{s['name']} ({s['symbol']}) {direction} {abs(s['change_pct']):.1f}% today"

        source_id = hashlib.sha256(f"sector_{s['symbol']}_{datetime.utcnow().strftime('%Y%m%d')}".encode()).hexdigest()[:32]
        events.append({
            "event_type": "sector_move",
            "impact": impact,
            "symbols": [s["symbol"]],
            "sectors": [s["name"]],
            "headline": headline,
            "raw_data": s,
            "source": "yfinance_sector",
            "source_id": source_id,
            "expires_at": datetime.utcnow() + timedelta(hours=1),
        })
    return events
