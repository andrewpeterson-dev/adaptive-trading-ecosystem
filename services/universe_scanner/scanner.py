"""Universe Scanner — ranks symbol candidates for each bot."""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, time as dtime
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import select, delete

from db.database import get_session
from db.cerberus_models import (
    CerberusBot, CerberusBotVersion, UniverseCandidate, BotStatus,
)
from services.universe_scanner.pools import (
    get_sp500_symbols, get_nasdaq100_symbols, get_sector_symbols,
)

logger = structlog.get_logger(__name__)
_ET = ZoneInfo("America/New_York")


def _score_candidates_sync(symbols: list[str], strategy_type: str) -> list[dict]:
    """Score symbols using technical indicators. No LLM, pure math."""
    results = []
    try:
        import yfinance as yf
        if not symbols:
            return []

        batch_size = 20
        for i in range(0, len(symbols), batch_size):
            batch = symbols[i:i + batch_size]
            try:
                tickers = yf.Tickers(" ".join(batch))
                for symbol in batch:
                    try:
                        hist = tickers.tickers[symbol].history(period="30d", interval="1d")
                        if len(hist) < 10:
                            continue

                        closes = hist["Close"].values
                        volumes = hist["Volume"].values

                        # Momentum score
                        momentum = (closes[-1] - closes[-10]) / closes[-10] if closes[-10] != 0 else 0

                        # Volume ratio (recent vs average)
                        avg_vol = volumes[:-5].mean() if len(volumes) > 5 else volumes.mean()
                        recent_vol = volumes[-5:].mean()
                        vol_ratio = recent_vol / avg_vol if avg_vol > 0 else 1.0

                        # ATR for volatility
                        highs = hist["High"].values
                        lows = hist["Low"].values
                        tr = [max(hi - lo, abs(hi - closes[i-1]), abs(lo - closes[i-1])) for i, (hi, lo) in enumerate(zip(highs[1:], lows[1:]), 1)]
                        atr = sum(tr[-14:]) / min(14, len(tr)) if tr else 0
                        atr_pct = atr / closes[-1] if closes[-1] > 0 else 0

                        # Score based on strategy type
                        if strategy_type in ("momentum", "trend"):
                            score = min(1.0, max(0.0, 0.5 + momentum * 5 + (vol_ratio - 1) * 0.2))
                            reason = f"Momentum: {momentum*100:.1f}%, Vol ratio: {vol_ratio:.1f}x"
                        elif strategy_type == "mean_reversion":
                            # Distance from 20-day SMA
                            sma20 = closes[-20:].mean() if len(closes) >= 20 else closes.mean()
                            dist = (closes[-1] - sma20) / sma20 if sma20 > 0 else 0
                            score = min(1.0, max(0.0, 0.5 + abs(dist) * 10))
                            reason = f"Distance from SMA20: {dist*100:.1f}%"
                        elif strategy_type == "volatility":
                            score = min(1.0, max(0.0, atr_pct * 20))
                            reason = f"ATR: {atr_pct*100:.1f}%"
                        else:
                            score = min(1.0, max(0.0, 0.3 + momentum * 3 + vol_ratio * 0.1 + atr_pct * 5))
                            reason = f"Composite: mom={momentum*100:.1f}%, vol_ratio={vol_ratio:.1f}x, ATR={atr_pct*100:.1f}%"

                        results.append({"symbol": symbol, "score": round(score, 4), "reason": reason})
                    except Exception as exc:
                        logger.debug("score_symbol_failed", symbol=symbol, error=str(exc))
                        continue
            except Exception as exc:
                logger.warning("score_batch_failed", batch_start=i, batch_size=batch_size, error=str(exc))
                continue
    except Exception as e:
        logger.warning("score_candidates_failed", error=str(e))

    results.sort(key=lambda x: x["score"], reverse=True)
    return results


class UniverseScanner:
    """Background loop scanning and scoring universe candidates per bot."""

    def __init__(self) -> None:
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("universe_scanner_started")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("universe_scanner_stopped")

    async def _loop(self) -> None:
        while self._running:
            try:
                now = datetime.now(_ET)
                if now.weekday() < 5 and dtime(9, 0) <= now.time() <= dtime(16, 30):
                    await self._scan_all_bots()
                    interval = 900  # 15 min
                else:
                    interval = 3600  # 1 hour outside market
            except Exception as e:
                logger.exception("universe_scanner_error", error=str(e))
                interval = 900
            await asyncio.sleep(interval)

    async def _scan_all_bots(self) -> None:
        async with get_session() as session:
            result = await session.execute(
                select(CerberusBot, CerberusBotVersion)
                .join(CerberusBotVersion, CerberusBot.current_version_id == CerberusBotVersion.id)
                .where(CerberusBot.status == BotStatus.RUNNING)
            )
            bots = result.all()

        for bot, version in bots:
            try:
                await self._scan_bot(bot, version)
            except Exception as e:
                logger.error("universe_scan_bot_error", bot_id=bot.id, error=str(e))

    async def _scan_bot(self, bot: CerberusBot, version: CerberusBotVersion) -> None:
        universe_config = version.universe_config or {}
        mode = universe_config.get("mode", "fixed")

        if mode == "fixed":
            return  # Fixed symbols don't need scanning

        # Fetch candidate pool
        candidates: list[str] = []
        if mode == "sector":
            sectors = universe_config.get("sectors", [])
            candidates = await get_sector_symbols(sectors)
        elif mode == "index":
            index = universe_config.get("index", "sp500")
            if index == "sp500":
                candidates = await get_sp500_symbols()
            elif index == "nasdaq100":
                candidates = await get_nasdaq100_symbols()
        elif mode in ("full_market", "ai_selected"):
            candidates = await get_sp500_symbols()

        if not candidates:
            return

        # Apply filters
        exclude = set(s.upper() for s in universe_config.get("exclude_symbols", []))
        candidates = [s for s in candidates if s.upper() not in exclude]

        max_symbols = universe_config.get("max_symbols", 10)

        # Determine strategy type from config
        config = version.config_json or {}
        strategy_type = config.get("strategy_type", "momentum")

        # Score in thread pool
        loop = asyncio.get_running_loop()
        scored = await loop.run_in_executor(
            None, _score_candidates_sync, candidates[:50], strategy_type
        )

        top = scored[:max_symbols]

        # Guard: never delete existing candidates if scoring returned nothing
        if not top:
            logger.warning("universe_scan_empty_results", bot_id=bot.id, candidates_pool=len(candidates))
            return

        # Replace old candidates for this bot (atomic within session transaction)
        async with get_session() as session:
            await session.execute(
                delete(UniverseCandidate).where(UniverseCandidate.bot_id == bot.id)
            )
            for item in top:
                session.add(UniverseCandidate(
                    id=str(uuid.uuid4()),
                    bot_id=bot.id,
                    symbol=item["symbol"],
                    score=item["score"],
                    reason=item["reason"],
                    scanned_at=datetime.utcnow(),
                ))

        logger.info("universe_scan_complete", bot_id=bot.id, candidates=len(top))
