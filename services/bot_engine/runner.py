"""
Bot execution engine — background async loop that evaluates running bots
against market data and executes trades when conditions are met.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, time as dtime, timezone, timedelta
from types import SimpleNamespace

import structlog
from sqlalchemy import select

from db.database import get_session
from db.cerberus_models import (
    CerberusBot,
    CerberusBotVersion,
    CerberusTrade,
    BotStatus,
)
from services.bot_engine.indicators import compute_indicators
from services.bot_engine.evaluator import evaluate_conditions

logger = structlog.get_logger(__name__)


class BotRunner:
    """Background service that evaluates and executes running trading bots."""

    def __init__(self) -> None:
        self._running = False
        self._task: asyncio.Task | None = None
        # Track last evaluation time per bot to avoid duplicate signals
        self._last_eval: dict[str, datetime] = {}

    async def start(self) -> None:
        """Start the bot runner loop."""
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("bot_runner_started")

    async def stop(self) -> None:
        """Stop the bot runner loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("bot_runner_stopped")

    async def _loop(self) -> None:
        """Main loop — check running bots every 60 seconds."""
        while self._running:
            try:
                await self._check_bots()
            except Exception as e:
                logger.error("bot_runner_error", error=str(e))
            await asyncio.sleep(60)

    async def _check_bots(self) -> None:
        """Query all RUNNING bots and evaluate each one."""
        async with get_session() as session:
            result = await session.execute(
                select(CerberusBot, CerberusBotVersion)
                .join(
                    CerberusBotVersion,
                    CerberusBot.current_version_id == CerberusBotVersion.id,
                )
                .where(CerberusBot.status == BotStatus.RUNNING)
            )
            bots = result.all()

        if not bots:
            return

        logger.info("bot_runner_checking", count=len(bots))

        for bot, version in bots:
            try:
                await self._evaluate_bot(bot, version)
            except Exception as e:
                logger.error("bot_eval_error", bot_id=bot.id, error=str(e))
                # Mark as ERROR if persistent failure
                try:
                    async with get_session() as session:
                        result = await session.execute(
                            select(CerberusBot).where(CerberusBot.id == bot.id)
                        )
                        db_bot = result.scalar_one_or_none()
                        if db_bot:
                            db_bot.status = BotStatus.ERROR
                except Exception:
                    pass

    async def _evaluate_bot(
        self, bot: CerberusBot, version: CerberusBotVersion
    ) -> None:
        """Evaluate a single bot's conditions and execute if triggered."""
        config = version.config_json or {}
        symbols = config.get("symbols", [])
        conditions = config.get("conditions", [])
        action = config.get("action", "BUY")
        timeframe = config.get("timeframe", "1D")
        position_size_pct = config.get("position_size_pct", 5.0)

        if not symbols or not conditions:
            logger.warning("bot_skipped_no_config", bot_id=bot.id)
            return

        # Check if market is open (skip weekends, outside 9:30-16:00 ET)
        if not self._is_market_open():
            return

        # Rate limit: don't evaluate same bot more than once per timeframe interval
        interval_seconds = self._timeframe_to_seconds(timeframe)
        last = self._last_eval.get(bot.id)
        if last and (datetime.utcnow() - last).total_seconds() < interval_seconds:
            return

        for symbol in symbols:
            try:
                await self._evaluate_symbol(
                    bot, config, symbol, conditions, action, position_size_pct
                )
            except Exception as e:
                logger.error(
                    "bot_symbol_eval_error",
                    bot_id=bot.id,
                    symbol=symbol,
                    error=str(e),
                )

        self._last_eval[bot.id] = datetime.utcnow()

    async def _evaluate_symbol(
        self,
        bot: CerberusBot,
        config: dict,
        symbol: str,
        conditions: list[dict],
        action: str,
        position_size_pct: float,
    ) -> None:
        """Evaluate conditions for one symbol and execute if triggered."""
        # Fetch OHLCV bars using yfinance
        bars = await self._fetch_bars(symbol, config.get("timeframe", "1D"))
        if not bars or len(bars) < 50:
            logger.warning(
                "insufficient_bars",
                bot_id=bot.id,
                symbol=symbol,
                count=len(bars) if bars else 0,
            )
            return

        # Compute indicators
        indicators_needed = [
            {"indicator": c["indicator"], "params": c.get("params", {})}
            for c in conditions
        ]
        indicator_values = compute_indicators(bars, indicators_needed)

        # Evaluate conditions
        all_passed, reasons = evaluate_conditions(conditions, indicator_values)

        if all_passed:
            logger.info(
                "bot_signal_triggered",
                bot_id=bot.id,
                symbol=symbol,
                action=action,
                reasons=reasons,
            )
            await self._execute_trade(
                bot, symbol, action, position_size_pct, bars[-1].get("close", 0)
            )
        else:
            logger.debug(
                "bot_conditions_not_met", bot_id=bot.id, symbol=symbol
            )

    async def _fetch_bars(self, symbol: str, timeframe: str) -> list[dict]:
        """Fetch OHLCV bars using yfinance (run in thread to avoid blocking)."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._fetch_bars_sync, symbol, timeframe)

    def _fetch_bars_sync(self, symbol: str, timeframe: str) -> list[dict]:
        """Synchronous yfinance fetch."""
        import yfinance as yf

        # Map timeframe to yfinance parameters
        tf_map = {
            "1m": ("1m", "1d"),
            "5m": ("5m", "5d"),
            "15m": ("15m", "5d"),
            "1H": ("1h", "30d"),
            "4H": ("1h", "60d"),  # yf doesn't have 4h, use 1h
            "1D": ("1d", "120d"),
        }
        interval, period = tf_map.get(timeframe, ("1d", "120d"))

        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period, interval=interval)
            if df.empty:
                return []

            bars = []
            for idx, row in df.iterrows():
                bars.append(
                    {
                        "time": int(idx.timestamp()),
                        "open": float(row["Open"]),
                        "high": float(row["High"]),
                        "low": float(row["Low"]),
                        "close": float(row["Close"]),
                        "volume": int(row["Volume"]),
                    }
                )
            return bars
        except Exception as e:
            logger.error("bar_fetch_error", symbol=symbol, error=str(e))
            return []

    async def _execute_trade(
        self,
        bot: CerberusBot,
        symbol: str,
        action: str,
        position_size_pct: float,
        current_price: float,
    ) -> None:
        """Execute a trade for a bot via paper trading."""
        from api.routes.paper_trading import PaperTradeRequest, execute_paper_trade
        from db.models import PaperPortfolio

        user_id = bot.user_id

        # Calculate quantity from position_size_pct
        async with get_session() as session:
            result = await session.execute(
                select(PaperPortfolio).where(PaperPortfolio.user_id == user_id)
            )
            portfolio = result.scalar_one_or_none()

        if not portfolio or current_price <= 0:
            logger.warning(
                "bot_no_portfolio_or_price", bot_id=bot.id, user_id=user_id
            )
            return

        position_value = portfolio.cash * (position_size_pct / 100.0)
        quantity = int(position_value / current_price)
        if quantity < 1:
            logger.warning(
                "bot_insufficient_funds",
                bot_id=bot.id,
                symbol=symbol,
                cash=portfolio.cash,
            )
            return

        # Map action to side
        side = "BUY" if action.upper() in ("BUY", "LONG") else "SELL"

        # Execute via paper trading (bots always use paper mode for safety)
        try:
            mock_request = SimpleNamespace(
                state=SimpleNamespace(user_id=user_id, trading_mode=None)
            )

            paper_req = PaperTradeRequest(
                symbol=symbol.upper(),
                side=side,
                quantity=quantity,
                user_confirmed=True,  # Bot deployment = user pre-confirmed
            )
            trade_result = await execute_paper_trade(mock_request, paper_req)

            logger.info(
                "bot_trade_executed",
                bot_id=bot.id,
                symbol=symbol,
                side=side,
                quantity=quantity,
                price=current_price,
                result=trade_result,
            )

            # Record in CerberusTrade with bot_id for audit trail
            async with get_session() as session:
                trade = CerberusTrade(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    bot_id=bot.id,
                    symbol=symbol.upper(),
                    side=side.lower(),
                    quantity=quantity,
                    entry_price=current_price,
                    strategy_tag=bot.name,
                    created_at=datetime.utcnow(),
                )
                session.add(trade)

        except Exception as e:
            logger.error(
                "bot_trade_failed", bot_id=bot.id, symbol=symbol, error=str(e)
            )

    def _is_market_open(self) -> bool:
        """Check if US stock market is currently open (rough check)."""
        now = datetime.now(timezone(timedelta(hours=-5)))  # EST
        # Weekends
        if now.weekday() >= 5:
            return False
        # Market hours: 9:30 AM - 4:00 PM ET
        market_open = dtime(9, 30)
        market_close = dtime(16, 0)
        return market_open <= now.time() <= market_close

    def _timeframe_to_seconds(self, tf: str) -> int:
        """Convert timeframe string to minimum seconds between evaluations."""
        mapping = {
            "1m": 60,
            "5m": 300,
            "15m": 900,
            "1H": 3600,
            "4H": 14400,
            "1D": 86400,
        }
        return mapping.get(tf, 86400)


# Singleton instance
bot_runner = BotRunner()
