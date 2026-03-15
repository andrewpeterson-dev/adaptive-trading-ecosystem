"""Trade journal — records enriched trade data with AI context."""
from __future__ import annotations

import uuid
from datetime import datetime

import structlog
from sqlalchemy import select

from db.database import get_session
from db.cerberus_models import BotTradeJournal, MarketEvent, TradeDecision

logger = structlog.get_logger(__name__)


async def record_trade(
    *,
    bot_id: str,
    trade_id: str,
    symbol: str,
    side: str,
    entry_price: float | None = None,
    exit_price: float | None = None,
    entry_at: datetime | None = None,
    exit_at: datetime | None = None,
    pnl: float | None = None,
    pnl_pct: float | None = None,
    vix: float | None = None,
    regime: str | None = None,
    trade_decision: TradeDecision | None = None,
) -> BotTradeJournal:
    """Record a trade in the journal with full context."""

    # Fetch active market events at time of trade
    market_event_ids = []
    try:
        async with get_session() as session:
            now = datetime.utcnow()
            result = await session.execute(
                select(MarketEvent.id).where(
                    (MarketEvent.expires_at.is_(None)) | (MarketEvent.expires_at > now)
                ).limit(20)
            )
            market_event_ids = [r[0] for r in result.all()]
    except Exception:
        pass

    hold_duration = None
    if entry_at and exit_at:
        hold_duration = int((exit_at - entry_at).total_seconds())

    # Fetch sector momentum at time of entry
    sector_momentum = None
    try:
        import yfinance as yf
        ticker_info = yf.Ticker(symbol).info or {}
        sector = ticker_info.get("sector", "")
        if sector:
            sector_etfs = {
                "Technology": "XLK", "Healthcare": "XLV", "Financial Services": "XLF",
                "Energy": "XLE", "Consumer Cyclical": "XLY", "Industrials": "XLI",
                "Basic Materials": "XLB", "Utilities": "XLU", "Real Estate": "XLRE",
                "Communication Services": "XLC", "Consumer Defensive": "XLP",
            }
            etf = sector_etfs.get(sector)
            if etf:
                etf_hist = yf.Ticker(etf).history(period="5d")
                if len(etf_hist) >= 2:
                    sector_momentum = float(
                        (etf_hist["Close"].iloc[-1] / etf_hist["Close"].iloc[0] - 1) * 100
                    )
    except Exception:
        pass

    journal_entry = BotTradeJournal(
        id=str(uuid.uuid4()),
        bot_id=bot_id,
        trade_id=trade_id,
        symbol=symbol,
        side=side,
        entry_price=entry_price,
        exit_price=exit_price,
        entry_at=entry_at or datetime.utcnow(),
        exit_at=exit_at,
        hold_duration_seconds=hold_duration,
        pnl=pnl,
        pnl_pct=pnl_pct,
        market_events=market_event_ids,
        vix_at_entry=vix,
        ai_confidence_at_entry=trade_decision.ai_confidence if trade_decision else None,
        ai_decision=trade_decision.decision if trade_decision else None,
        ai_reasoning=trade_decision.reasoning if trade_decision else None,
        regime_at_entry=regime,
        sector_momentum_at_entry=sector_momentum,
        created_at=datetime.utcnow(),
    )

    async with get_session() as session:
        session.add(journal_entry)

    logger.info("trade_journaled", bot_id=bot_id, symbol=symbol, side=side, pnl=pnl)

    # Update regime stats after recording
    from services.bot_memory.regime_tracker import update_regime_stats
    await update_regime_stats(bot_id)

    return journal_entry
