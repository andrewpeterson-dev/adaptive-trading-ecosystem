"""
Continuous Position Manager — monitors open positions every N seconds for
stop-loss, take-profit, trailing-stop, time-based, and emergency exits.

Designed to fill the gap where the BotRunner only evaluates every 60 s
(at best).  This service checks *existing* positions far more frequently
so stops fire in near-real-time.
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime
from typing import Any

import structlog
from sqlalchemy import select

from config.settings import get_settings
from db.database import get_session
from db.cerberus_models import (
    CerberusBot,
    CerberusBotVersion,
    CerberusTrade,
)
from data.market_data import MarketDataService
from services.activity_bus import BotActivityEvent, activity_bus
from services.position_manager.stop_tracker import StopConfig, StopSignal, StopTracker

logger = structlog.get_logger(__name__)

# Config cache entries older than this are refreshed from DB
_CONFIG_CACHE_TTL = 120  # seconds


class PositionManager:
    """Continuously monitors open positions for stop-loss, take-profit,
    trailing stops, time-based exits, and emergency exits.

    Parameters
    ----------
    check_interval : float
        Seconds between successive position scans (default 10).
    market_data : MarketDataService | None
        Inject a custom MarketDataService; ``None`` creates the default singleton.
    """

    def __init__(
        self,
        check_interval: float = 10.0,
        market_data: MarketDataService | None = None,
    ) -> None:
        self._check_interval = max(check_interval, 1.0)
        self._market_data = market_data or MarketDataService()
        self._stop_tracker = StopTracker()
        self._running = False
        self._task: asyncio.Task | None = None
        # Cache: bot_id → (timestamp, StopConfig) — refreshed after _CONFIG_CACHE_TTL
        self._config_cache: dict[str, tuple[float, StopConfig]] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Launch the monitoring loop as a background ``asyncio.Task``."""
        if self._running:
            logger.warning("position_manager_already_running")
            return
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop(), name="position_manager")
        logger.info(
            "position_manager_started",
            check_interval=self._check_interval,
        )

    async def stop(self) -> None:
        """Gracefully shut down the monitor loop."""
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("position_manager_stopped")

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    async def _monitor_loop(self) -> None:
        """Main loop: fetch open positions, batch-fetch quotes, evaluate."""
        while self._running:
            try:
                await self._run_check_cycle()
            except asyncio.CancelledError:
                break
            except Exception:
                # Never let an unexpected error kill the loop
                logger.exception("position_manager_cycle_error")
            try:
                await asyncio.sleep(self._check_interval)
            except asyncio.CancelledError:
                break

    async def _run_check_cycle(self) -> None:
        """Single check cycle — extracted for testability."""
        # 1. Fetch all open positions (exit_ts IS NULL)
        trades = await self._fetch_open_trades()
        if not trades:
            return

        # 2. Collect unique symbols and batch-fetch quotes
        symbols = list({t.symbol.upper() for t in trades if t.symbol})
        quotes = await self._market_data.get_batch_quotes(symbols)

        if not quotes:
            logger.warning(
                "position_manager_no_quotes",
                symbols=symbols,
            )
            return

        # 3. Load bot configs for StopConfig resolution
        await self._refresh_config_cache([t.bot_id for t in trades if t.bot_id])

        # 4. Evaluate each open trade
        for trade in trades:
            sym = (trade.symbol or "").upper()
            quote = quotes.get(sym)
            if quote is None:
                logger.debug("position_manager_no_quote_for_symbol", symbol=sym)
                continue
            try:
                await self._check_position(trade, quote)
            except Exception:
                logger.exception(
                    "position_manager_check_error",
                    trade_id=trade.id,
                    symbol=sym,
                )

    # ------------------------------------------------------------------
    # Per-position evaluation
    # ------------------------------------------------------------------

    async def _check_position(self, trade: CerberusTrade, quote: dict) -> None:
        """Evaluate a single position against its stop/target/trailing rules."""
        current_price = float(quote.get("price") or 0)
        if current_price <= 0:
            return

        symbol = (trade.symbol or "").upper()
        entry_price = float(trade.entry_price or 0)
        side = (trade.side or "buy").lower()

        # Resolve config
        config = self._resolve_stop_config(trade)

        # Update trailing-stop high-water mark
        self._stop_tracker.update(symbol, current_price)

        # Check all exit rules
        signal: StopSignal | None = self._stop_tracker.check(
            entry_price=entry_price,
            current_price=current_price,
            side=side,
            config=config,
            entry_ts=trade.entry_ts,
            symbol=symbol,
        )

        if signal is None:
            return

        logger.info(
            "position_exit_signal",
            trade_id=trade.id,
            symbol=symbol,
            reason=signal.reason,
            urgency=signal.urgency,
            detail=signal.detail,
        )

        if signal.urgency == "immediate":
            await self._execute_exit(trade, signal.reason, current_price, signal.detail)
        else:
            # "next_check" urgency — publish an alert but don't auto-close
            self._publish_alert(trade, signal)

    # ------------------------------------------------------------------
    # Exit execution
    # ------------------------------------------------------------------

    async def _execute_exit(
        self,
        trade: CerberusTrade,
        reason: str,
        exit_price: float,
        detail: str = "",
    ) -> None:
        """Close a position: update DB record and notify via the activity bus."""
        entry_price = float(trade.entry_price or 0)
        quantity = float(trade.quantity or 0)
        is_long = (trade.side or "buy").lower() in ("buy", "long")

        # PnL
        if is_long:
            pnl = round((exit_price - entry_price) * quantity, 2)
        else:
            pnl = round((entry_price - exit_price) * quantity, 2)
        basis = entry_price * quantity
        return_pct = round(pnl / basis, 4) if basis > 0 else None

        async with get_session() as session:
            result = await session.execute(
                select(CerberusTrade).where(CerberusTrade.id == trade.id)
            )
            db_trade = result.scalar_one_or_none()
            if db_trade is None:
                logger.warning("position_manager_trade_not_found", trade_id=trade.id)
                return

            # Guard: already closed by another process (race condition)
            if db_trade.exit_ts is not None:
                logger.info(
                    "position_already_closed",
                    trade_id=trade.id,
                )
                return

            payload: dict[str, Any] = (
                db_trade.payload_json if isinstance(db_trade.payload_json, dict) else {}
            )
            payload["position_manager_exit"] = {
                "reason": reason,
                "detail": detail,
                "exit_price": exit_price,
                "pnl": pnl,
            }

            db_trade.exit_ts = datetime.utcnow()
            db_trade.exit_price = exit_price
            db_trade.gross_pnl = pnl
            db_trade.net_pnl = pnl
            db_trade.return_pct = return_pct
            db_trade.notes = detail or db_trade.notes
            db_trade.payload_json = payload

        # Clean up tracker state
        symbol = (trade.symbol or "").upper()
        self._stop_tracker.reset(symbol)

        logger.info(
            "position_exit_executed",
            trade_id=trade.id,
            symbol=symbol,
            reason=reason,
            exit_price=exit_price,
            pnl=pnl,
            return_pct=return_pct,
        )

        # Publish activity event for WebSocket push
        self._publish_exit_event(trade, reason, exit_price, pnl, detail)

    # ------------------------------------------------------------------
    # Trailing stop update
    # ------------------------------------------------------------------

    async def _update_trailing_stop(
        self, trade: CerberusTrade, current_price: float
    ) -> None:
        """Adjust trailing stop high-water mark if price moved favourably.

        Called automatically inside ``_check_position`` via
        ``StopTracker.update``, but exposed here for explicit use when
        processing streamed tick data.
        """
        symbol = (trade.symbol or "").upper()
        self._stop_tracker.update(symbol, current_price)

    # ------------------------------------------------------------------
    # Data fetching
    # ------------------------------------------------------------------

    async def _fetch_open_trades(self) -> list[CerberusTrade]:
        """Return all CerberusTrade rows where ``exit_ts IS NULL``."""
        async with get_session() as session:
            result = await session.execute(
                select(CerberusTrade)
                .where(CerberusTrade.exit_ts.is_(None))
                .order_by(CerberusTrade.entry_ts.asc())
            )
            return list(result.scalars().all())

    async def _refresh_config_cache(self, bot_ids: list[str]) -> None:
        """Load the latest bot version configs for the given bot IDs.

        Entries expire after _CONFIG_CACHE_TTL seconds so config changes
        (e.g. stop-loss adjustments) take effect within ~2 minutes.
        """
        now = time.monotonic()
        unique_ids = list(set(bid for bid in bot_ids if bid))
        # Fetch bots that are missing or stale
        stale = [
            bid for bid in unique_ids
            if bid not in self._config_cache
            or (now - self._config_cache[bid][0]) > _CONFIG_CACHE_TTL
        ]
        if not stale:
            return

        async with get_session() as session:
            result = await session.execute(
                select(CerberusBot, CerberusBotVersion)
                .join(
                    CerberusBotVersion,
                    CerberusBot.current_version_id == CerberusBotVersion.id,
                )
                .where(CerberusBot.id.in_(stale))
            )
            for bot, version in result.all():
                raw_config = version.config_json if isinstance(version.config_json, dict) else {}
                self._config_cache[bot.id] = (now, StopConfig.from_bot_config(raw_config))

        # Evict entries for bots no longer active (prevents unbounded growth)
        active_set = set(unique_ids)
        stale_keys = [k for k in self._config_cache if k not in active_set]
        for k in stale_keys:
            del self._config_cache[k]

    def _resolve_stop_config(self, trade: CerberusTrade) -> StopConfig:
        """Resolve the StopConfig for a trade, falling back to defaults."""
        if trade.bot_id and trade.bot_id in self._config_cache:
            return self._config_cache[trade.bot_id][1]

        # Check if the trade's payload_json has inline stop config
        payload = trade.payload_json if isinstance(trade.payload_json, dict) else {}
        if any(k in payload for k in ("stop_loss_pct", "take_profit_pct", "trailing_stop_pct")):
            return StopConfig.from_bot_config(payload)

        # Fall back to global settings
        settings = get_settings()
        return StopConfig(
            stop_loss_pct=settings.stop_loss_pct * 100.0 if settings.stop_loss_pct < 1 else settings.stop_loss_pct,
        )

    # ------------------------------------------------------------------
    # Activity bus integration
    # ------------------------------------------------------------------

    def _publish_exit_event(
        self,
        trade: CerberusTrade,
        reason: str,
        exit_price: float,
        pnl: float,
        detail: str = "",
    ) -> None:
        """Publish a BotActivityEvent when a position is closed."""
        pnl_str = f"+${pnl:.2f}" if pnl >= 0 else f"-${abs(pnl):.2f}"
        symbol = (trade.symbol or "").upper()
        headline = f"Position closed: {symbol} ({reason}) @ ${exit_price:.2f} [{pnl_str}]"

        event = BotActivityEvent(
            event_type=f"position_exit_{reason}",
            bot_id=trade.bot_id or "",
            bot_name=trade.strategy_tag or "unknown",
            symbol=symbol,
            headline=headline,
            detail={
                "trade_id": trade.id,
                "reason": reason,
                "exit_price": exit_price,
                "pnl": pnl,
                "detail": detail,
            },
            user_id=trade.user_id,
        )
        activity_bus.publish(event)

    def _publish_alert(self, trade: CerberusTrade, signal: StopSignal) -> None:
        """Publish a non-exit alert (e.g. time-exit flagged for review)."""
        symbol = (trade.symbol or "").upper()
        event = BotActivityEvent(
            event_type=f"position_alert_{signal.reason}",
            bot_id=trade.bot_id or "",
            bot_name=trade.strategy_tag or "unknown",
            symbol=symbol,
            headline=f"Alert: {symbol} — {signal.detail}",
            detail={
                "trade_id": trade.id,
                "reason": signal.reason,
                "urgency": signal.urgency,
                "detail": signal.detail,
                "price": signal.target_price,
            },
            user_id=trade.user_id,
        )
        activity_bus.publish(event)

    # ------------------------------------------------------------------
    # Housekeeping
    # ------------------------------------------------------------------

    def clear_config_cache(self) -> None:
        """Force a config refresh on the next cycle (e.g. after bot update)."""
        self._config_cache.clear()
