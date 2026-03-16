"""
Bot execution engine — background async loop that evaluates running bots
against market data and executes trades when conditions are met.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from datetime import datetime, time as dtime
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import select

from config.settings import get_settings
from db.database import get_session
from db.cerberus_models import (
    CerberusBot,
    CerberusBotVersion,
    CerberusTrade,
    UniverseCandidate,
    BotStatus,
)
from db.models import UserApiSettings, UserApiConnection, ApiProvider
from services.activity_bus import BotActivityEvent, activity_bus
from services.bot_engine.indicators import compute_indicators
from services.bot_engine.evaluator import evaluate_conditions
from services.bot_engine.ai_evaluator import ai_evaluate_entries, AIEntrySignal
from services.reasoning_engine import ReasoningEngine
from services.strategy_learning_engine import normalize_bot_config

logger = structlog.get_logger(__name__)
_MARKET_TIMEZONE = ZoneInfo("America/New_York")

_bar_cache: dict[str, tuple[float, list[dict]]] = {}
_BAR_CACHE_TTL = 60  # seconds


class BotRunner:
    """Background service that evaluates and executes running trading bots."""

    def __init__(self) -> None:
        self._running = False
        self._task: asyncio.Task | None = None
        # Track last evaluation time per bot to avoid duplicate signals
        self._last_eval: dict[str, datetime] = {}
        self._reasoning_engine = ReasoningEngine()

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

        # Evaluate bots outside the query session — each bot fetches its own market data
        error_bot_ids: list[str] = []
        for bot, version in bots:
            try:
                await self._evaluate_bot(bot, version)
            except Exception as e:
                logger.error("bot_eval_error", bot_id=bot.id, error=str(e))
                error_bot_ids.append(bot.id)

        # Batch-update error status in a single session instead of one per bot
        if error_bot_ids:
            try:
                async with get_session() as session:
                    for bot_id in error_bot_ids:
                        result = await session.execute(
                            select(CerberusBot).where(CerberusBot.id == bot_id)
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
        if version.backtest_required:
            logger.warning(
                "bot_skipped_unvalidated_version",
                bot_id=bot.id,
                version_id=version.id,
            )
            return

        config = normalize_bot_config(version.config_json or {})
        symbols = config.get("symbols", [])
        conditions = config.get("conditions", [])
        action = config.get("action", "BUY")
        timeframe = config.get("timeframe", "1D")
        position_size_pct = config.get("position_size_pct", 5.0)
        strategy_type = config.get("strategy_type", "manual")

        # Dynamic universe: pull candidates from UniverseScanner if not "fixed" mode
        universe_config = version.universe_config or {}
        universe_mode = universe_config.get("mode", "fixed")
        if universe_mode != "fixed":
            async with get_session() as session:
                result = await session.execute(
                    select(UniverseCandidate.symbol)
                    .where(UniverseCandidate.bot_id == bot.id)
                    .order_by(UniverseCandidate.score.desc())
                )
                dynamic_symbols = [r[0] for r in result.all()]
            if dynamic_symbols:
                symbols = dynamic_symbols

        if not symbols:
            logger.warning("bot_skipped_no_symbols", bot_id=bot.id)
            return

        # For rigid-condition bots, still require conditions
        if strategy_type not in ("ai_generated", "custom") and not conditions:
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

        risk_context = await self._build_risk_context(bot)

        # Use AI evaluation when an LLM API key is available; fall back to
        # rigid conditions only when no key is configured.
        settings = get_settings()
        use_ai_eval = bool(settings.openai_api_key or settings.anthropic_api_key)
        if use_ai_eval:
            await self._ai_evaluate_bot(bot, config, symbols, action, position_size_pct, risk_context)
        else:
            for symbol in symbols:
                try:
                    await self._evaluate_symbol(
                        bot, config, symbol, conditions, action,
                        position_size_pct, risk_context,
                    )
                except Exception as e:
                    logger.error(
                        "bot_symbol_eval_error",
                        bot_id=bot.id, symbol=symbol, error=str(e),
                    )

        self._last_eval[bot.id] = datetime.utcnow()

    async def _ai_evaluate_bot(
        self,
        bot: CerberusBot,
        config: dict,
        symbols: list[str],
        action: str,
        position_size_pct: float,
        risk_context: dict,
    ) -> None:
        """Use AI evaluation to decide entries for all symbols at once."""
        conditions = config.get("conditions", [])
        exit_conditions = config.get("exit_conditions") or []

        # Step 1: Fetch bars and compute indicators for all symbols
        symbol_data: list[dict] = []
        symbol_bars: dict[str, list[dict]] = {}
        symbol_indicators: dict[str, dict] = {}
        open_position_symbols: list[str] = []

        for symbol in symbols:
            bars = await self._fetch_bars(symbol, config.get("timeframe", "1D"))
            if not bars or len(bars) < 50:
                continue

            # Compute indicators using the same logic as rigid evaluation
            indicators_needed = [
                {"indicator": c["indicator"], "params": c.get("params", {})}
                for c in [*conditions, *exit_conditions]
                if isinstance(c, dict) and c.get("indicator")
            ]
            # Always compute common indicators for AI context
            for ind_spec in [
                {"indicator": "rsi", "params": {"period": 14}},
                {"indicator": "sma", "params": {"period": 50}},
                {"indicator": "ema", "params": {"period": 200}},
                {"indicator": "macd", "params": {"fast": 12, "slow": 26, "signal": 9}},
                {"indicator": "atr", "params": {"period": 14}},
                {"indicator": "volume", "params": {}},
            ]:
                if not any(
                    i["indicator"].lower() == ind_spec["indicator"]
                    and i.get("params", {}).get("period") == ind_spec["params"].get("period")
                    for i in indicators_needed
                ):
                    indicators_needed.append(ind_spec)

            indicator_values = compute_indicators(bars, indicators_needed)
            current_price = float(bars[-1].get("close", 0) or 0)
            indicator_values["CLOSE"] = current_price

            # Check for existing open positions
            open_trades = await self._get_open_trades(bot.id, symbol)
            if open_trades:
                open_position_symbols.append(symbol)
                # Still check exit conditions for open positions
                should_exit, exit_reasons = self._should_exit_position(
                    open_trades=open_trades,
                    config=config,
                    indicator_values=indicator_values,
                    current_price=current_price,
                )
                if should_exit:
                    await self._close_open_trades(
                        bot=bot, symbol=symbol, open_trades=open_trades,
                        current_price=current_price, reasons=exit_reasons,
                    )
                continue

            symbol_data.append({
                "symbol": symbol,
                "price": current_price,
                "indicators": indicator_values,
            })
            symbol_bars[symbol] = bars
            symbol_indicators[symbol] = indicator_values

        if not symbol_data:
            return

        # Step 2: Call AI evaluator with all symbol data
        description = config.get("description") or config.get("overview") or config.get("name", "")
        ai_context = config.get("ai_context") or {}
        overview = ai_context.get("overview") or description

        # Synthesize description from conditions when none exists
        if not overview or len(overview) < 10:
            condition_parts = []
            for c in conditions:
                ind = c.get("indicator", "").upper()
                op = c.get("operator", ">")
                val = c.get("value", 0)
                params = c.get("params") or {}
                period = params.get("period", "")
                condition_parts.append(f"{ind}({period}) {op} {val}")
            exit_parts = []
            for c in exit_conditions:
                ind = c.get("indicator", "").upper()
                op = c.get("operator", ">")
                val = c.get("value", 0)
                exit_parts.append(f"{ind} {op} {val}")
            overview = (
                f"{action} strategy on {config.get('timeframe', '1D')} timeframe. "
                f"Entry signals: {', '.join(condition_parts) if condition_parts else 'AI discretion'}. "
                f"Exit signals: {', '.join(exit_parts) if exit_parts else 'stop loss/take profit'}."
            )

        ai_thinking = ai_context.get("ai_thinking") or {}
        if ai_thinking:
            full_description = f"{overview}\n\nAI Guidance: {ai_thinking.get('adaptiveBehavior', '')}"
        else:
            full_description = overview

        signals = await ai_evaluate_entries(
            strategy_name=config.get("name", bot.name),
            strategy_description=full_description,
            action=action,
            stop_loss_pct=float(config.get("stop_loss_pct", 0.02)),
            take_profit_pct=float(config.get("take_profit_pct", 0.05)),
            position_size_pct=float(config.get("position_size_pct", 0.10)),
            timeframe=config.get("timeframe", "1D"),
            symbol_data=symbol_data,
            open_positions=open_position_symbols,
        )

        # Step 3: Process AI signals — execute entries with high confidence
        for signal in signals:
            if signal.action != "enter" or signal.confidence < 60:
                logger.debug(
                    "ai_eval_hold",
                    bot_id=bot.id, symbol=signal.symbol,
                    confidence=signal.confidence, reasoning=signal.reasoning,
                )
                continue

            symbol = signal.symbol
            indicator_values = symbol_indicators.get(symbol)
            if not indicator_values:
                continue
            current_price = indicator_values.get("CLOSE", 0)

            logger.info(
                "ai_signal_triggered",
                bot_id=bot.id, symbol=symbol, action=action,
                confidence=signal.confidence, reasoning=signal.reasoning,
            )

            # Gate through Reasoning Engine for safety checks
            decision = None
            try:
                decision = await self._reasoning_engine.evaluate(
                    bot=bot, symbol=symbol, signal=action,
                    strategy_config=config,
                    vix=risk_context.get("vix"),
                    portfolio_exposure=self._calculate_symbol_exposure(
                        risk_context, symbol, current_price,
                    ),
                    daily_pnl_pct=float(risk_context.get("daily_pnl_pct") or 0.0),
                )

                if decision.decision == "PAUSE_BOT":
                    await self._pause_bot(bot.id, decision.reasoning)
                    logger.info("bot_paused_by_reasoning", bot_id=bot.id, symbol=symbol, reasoning=decision.reasoning)
                    self._publish_activity(
                        "bot_paused", bot, symbol,
                        f"{bot.name} paused — {decision.reasoning}",
                        {"decision": decision.decision, "reasoning": decision.reasoning},
                    )
                    return

                if decision.decision in ("EXIT_POSITION", "DELAY_TRADE"):
                    logger.info(
                        "ai_trade_blocked_by_reasoning",
                        bot_id=bot.id, symbol=symbol,
                        decision=decision.decision, reasoning=decision.reasoning,
                    )
                    continue

                if decision.delay_seconds > 0:
                    logger.info(
                        "ai_trade_delayed_by_reasoning",
                        bot_id=bot.id, symbol=symbol,
                        delay=decision.delay_seconds, reasoning=decision.reasoning,
                    )
                    continue

                # Apply size adjustments from both AI confidence and reasoning engine
                adjusted_size = position_size_pct * decision.size_adjustment
                # Scale by AI evaluator confidence (60-100 → 0.6-1.0 multiplier)
                confidence_scale = signal.confidence / 100.0
                adjusted_size = adjusted_size * confidence_scale

            except Exception as e:
                logger.warning("reasoning_engine_error", bot_id=bot.id, error=str(e))
                # In paper mode, still execute at reduced size
                adjusted_size = position_size_pct * 0.5

            executed_trade = await self._execute_trade(
                bot, symbol, action, adjusted_size, current_price,
                reasons=[f"AI: {signal.reasoning} (confidence: {signal.confidence}%)"],
            )
            if not executed_trade:
                continue

            self._publish_activity(
                "trade_executed", bot, symbol,
                f"{bot.name} AI {action} {symbol} @ ${current_price:.2f} (conf: {signal.confidence}%)",
                {"action": action, "price": current_price, "size_pct": adjusted_size,
                 "ai_confidence": signal.confidence, "ai_reasoning": signal.reasoning},
            )

            # Record in trade journal
            try:
                from services.bot_memory.journal import record_trade
                await record_trade(
                    bot_id=bot.id, trade_id=executed_trade.id,
                    symbol=symbol, side=action, entry_price=current_price,
                    vix=risk_context.get("vix"), entry_at=executed_trade.entry_ts,
                    trade_decision=decision,
                )
            except Exception as e:
                logger.warning("journal_record_error", bot_id=bot.id, error=str(e))

    async def _evaluate_symbol(
        self,
        bot: CerberusBot,
        config: dict,
        symbol: str,
        conditions: list[dict],
        action: str,
        position_size_pct: float,
        risk_context: dict,
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

        exit_conditions = config.get("exit_conditions") or []

        # Compute indicators
        indicators_needed = [
            {"indicator": c["indicator"], "params": c.get("params", {})}
            for c in [*conditions, *exit_conditions]
            if isinstance(c, dict) and c.get("indicator")
        ]
        indicator_values = compute_indicators(bars, indicators_needed)

        # Inject current close price so evaluator can use compare_to="PRICE"
        current_price = float(bars[-1].get("close", 0) or 0)
        indicator_values["CLOSE"] = current_price

        open_trades = await self._get_open_trades(bot.id, symbol)
        if open_trades:
            should_exit, exit_reasons = self._should_exit_position(
                open_trades=open_trades,
                config=config,
                indicator_values=indicator_values,
                current_price=current_price,
            )
            if should_exit:
                await self._close_open_trades(
                    bot=bot,
                    symbol=symbol,
                    open_trades=open_trades,
                    current_price=current_price,
                    reasons=exit_reasons,
                )
            else:
                logger.debug(
                    "bot_position_held",
                    bot_id=bot.id,
                    symbol=symbol,
                    open_trades=len(open_trades),
                )
            return

        # Evaluate conditions
        all_passed, reasons = evaluate_conditions(conditions, indicator_values)

        if not all_passed:
            logger.debug(
                "bot_conditions_not_met",
                bot_id=bot.id,
                symbol=symbol,
                reasons=reasons,
            )

        if all_passed:
            logger.info(
                "bot_signal_triggered",
                bot_id=bot.id,
                symbol=symbol,
                action=action,
                reasons=reasons,
            )

            # Gate through Reasoning Engine before execution
            decision = None
            try:
                decision = await self._reasoning_engine.evaluate(
                    bot=bot,
                    symbol=symbol,
                    signal=action,
                    strategy_config=config,
                    vix=risk_context.get("vix"),
                    portfolio_exposure=self._calculate_symbol_exposure(
                        risk_context,
                        symbol,
                        current_price,
                    ),
                    daily_pnl_pct=float(risk_context.get("daily_pnl_pct") or 0.0),
                )

                if decision.decision == "PAUSE_BOT":
                    await self._pause_bot(bot.id, decision.reasoning)
                    logger.info(
                        "bot_paused_by_reasoning",
                        bot_id=bot.id,
                        symbol=symbol,
                        reasoning=decision.reasoning,
                    )
                    self._publish_activity(
                        "bot_paused", bot, symbol,
                        f"{bot.name} paused — {decision.reasoning}",
                        {"decision": decision.decision, "reasoning": decision.reasoning},
                    )
                    return

                if decision.decision in ("EXIT_POSITION", "DELAY_TRADE"):
                    logger.info(
                        "bot_trade_blocked_by_reasoning",
                        bot_id=bot.id, symbol=symbol,
                        decision=decision.decision, reasoning=decision.reasoning,
                    )
                    self._publish_activity(
                        "trade_delayed" if decision.decision == "DELAY_TRADE" else "safety_block",
                        bot, symbol,
                        f"{bot.name} {symbol} {decision.decision.lower().replace('_', ' ')} — {decision.reasoning}",
                        {"decision": decision.decision, "reasoning": decision.reasoning, "confidence": decision.ai_confidence},
                    )
                    return
                if decision.delay_seconds > 0:
                    logger.info(
                        "bot_trade_delayed_by_reasoning",
                        bot_id=bot.id, symbol=symbol,
                        delay=decision.delay_seconds, reasoning=decision.reasoning,
                    )
                    self._publish_activity(
                        "trade_delayed", bot, symbol,
                        f"{bot.name} {symbol} delayed {decision.delay_seconds}s — {decision.reasoning}",
                        {"delay_seconds": decision.delay_seconds, "reasoning": decision.reasoning},
                    )
                    return  # Will re-evaluate on next cycle

                # Apply size adjustment from reasoning
                adjusted_size = position_size_pct * decision.size_adjustment

                # AI capital management: scale position based on confidence
                ai_capital_enabled = bool(
                    bot.reasoning_model_config
                    and isinstance(bot.reasoning_model_config, dict)
                    and bot.reasoning_model_config.get("ai_capital_management")
                )
                if ai_capital_enabled and decision.ai_confidence > 0:
                    # Scale position: high confidence → up to 1.5x, low → down to 0.5x
                    confidence_multiplier = 0.5 + decision.ai_confidence
                    adjusted_size = adjusted_size * confidence_multiplier
                    logger.info(
                        "ai_capital_adjustment",
                        bot_id=bot.id,
                        symbol=symbol,
                        confidence=decision.ai_confidence,
                        multiplier=confidence_multiplier,
                        adjusted_size=adjusted_size,
                    )
            except Exception as e:
                logger.warning("reasoning_engine_error", bot_id=bot.id, error=str(e))
                return

            executed_trade = await self._execute_trade(
                bot,
                symbol,
                action,
                adjusted_size,
                current_price,
                reasons=reasons,
            )
            if not executed_trade:
                return

            # AI capital management: adjust allocated_capital after trade based on performance
            if ai_capital_enabled and bot.allocated_capital:
                await self._ai_adjust_capital(bot)

            self._publish_activity(
                "trade_executed", bot, symbol,
                f"{bot.name} {action} {symbol} @ ${current_price:.2f} (conf: {decision.ai_confidence:.0%})",
                {"action": action, "price": current_price, "size_pct": adjusted_size, "confidence": decision.ai_confidence},
            )

            # Record in trade journal
            try:
                from services.bot_memory.journal import record_trade
                await record_trade(
                    bot_id=bot.id,
                    trade_id=executed_trade.id,
                    symbol=symbol,
                    side=action,
                    entry_price=current_price,
                    vix=risk_context.get("vix"),
                    entry_at=executed_trade.entry_ts,
                    trade_decision=decision,
                )
            except Exception as e:
                logger.warning("journal_record_error", bot_id=bot.id, error=str(e))
        else:
            logger.debug(
                "bot_conditions_not_met", bot_id=bot.id, symbol=symbol
            )

    async def _get_open_trades(self, bot_id: str, symbol: str) -> list[CerberusTrade]:
        async with get_session() as session:
            result = await session.execute(
                select(CerberusTrade)
                .where(
                    CerberusTrade.bot_id == bot_id,
                    CerberusTrade.symbol == symbol.upper(),
                    CerberusTrade.exit_ts.is_(None),
                )
                .order_by(CerberusTrade.created_at.asc())
            )
            return list(result.scalars().all())

    async def _build_risk_context(self, bot: CerberusBot) -> dict:
        from db.models import PaperPortfolio, PaperPosition, PaperTrade

        positions: dict[str, dict[str, float]] = {}
        total_equity = 0.0
        daily_pnl_pct = 0.0

        async with get_session() as session:
            portfolio_result = await session.execute(
                select(PaperPortfolio).where(PaperPortfolio.user_id == bot.user_id)
            )
            portfolio = portfolio_result.scalar_one_or_none()

            position_result = await session.execute(
                select(PaperPosition).where(PaperPosition.user_id == bot.user_id)
            )
            portfolio_positions = list(position_result.scalars().all())

            for position in portfolio_positions:
                mark_price = float(position.current_price or position.avg_entry_price or 0.0)
                positions[position.symbol.upper()] = {
                    "quantity": float(position.quantity or 0.0),
                    "mark_price": mark_price,
                }

            if portfolio:
                positions_value = sum(
                    abs(float(position.quantity or 0.0))
                    * float(position.current_price or position.avg_entry_price or 0.0)
                    for position in portfolio_positions
                )
                total_equity = float(portfolio.cash or 0.0) + positions_value

                start_of_day = datetime.utcnow().replace(
                    hour=0,
                    minute=0,
                    second=0,
                    microsecond=0,
                )
                trade_result = await session.execute(
                    select(PaperTrade.pnl).where(
                        PaperTrade.user_id == bot.user_id,
                        PaperTrade.exit_time.is_not(None),
                        PaperTrade.exit_time >= start_of_day,
                    )
                )
                realized_today = sum(float(row[0] or 0.0) for row in trade_result.all())
                initial_capital = float(portfolio.initial_capital or 0.0)
                if initial_capital > 0:
                    daily_pnl_pct = realized_today / initial_capital * 100.0

        vix = await self._fetch_reference_price("^VIX")
        return {
            "vix": vix,
            "daily_pnl_pct": daily_pnl_pct,
            "total_equity": total_equity,
            "positions": positions,
        }

    def _calculate_symbol_exposure(
        self,
        risk_context: dict,
        symbol: str,
        current_price: float,
    ) -> float:
        positions = risk_context.get("positions") or {}
        total_equity = float(risk_context.get("total_equity") or 0.0)
        if total_equity <= 0:
            return 0.0

        position = positions.get(symbol.upper()) or {}
        quantity = abs(float(position.get("quantity") or 0.0))
        price = float(position.get("mark_price") or current_price or 0.0)
        if quantity <= 0 or price <= 0:
            return 0.0
        return (quantity * price) / total_equity

    async def _fetch_reference_price(self, symbol: str) -> float | None:
        bars = await self._fetch_bars(symbol, "1D")
        if not bars:
            return None
        try:
            return float(bars[-1].get("close", 0) or 0)
        except (TypeError, ValueError):
            return None

    def _should_exit_position(
        self,
        *,
        open_trades: list[CerberusTrade],
        config: dict,
        indicator_values: dict,
        current_price: float,
    ) -> tuple[bool, list[str]]:
        reasons: list[str] = []
        stop_loss_pct = float(config.get("stop_loss_pct") or 0.0)
        take_profit_pct = float(config.get("take_profit_pct") or 0.0)

        for trade in open_trades:
            entry_price = float(trade.entry_price or 0.0)
            if entry_price <= 0 or current_price <= 0:
                continue

            is_short = str(trade.side or "").lower().startswith("sell")
            if stop_loss_pct > 0:
                stop_price = entry_price * (1 + stop_loss_pct if is_short else 1 - stop_loss_pct)
                if (is_short and current_price >= stop_price) or (not is_short and current_price <= stop_price):
                    reasons.append(f"Stop loss triggered at {current_price:.2f}")

            if take_profit_pct > 0:
                target_price = entry_price * (1 - take_profit_pct if is_short else 1 + take_profit_pct)
                if (is_short and current_price <= target_price) or (not is_short and current_price >= target_price):
                    reasons.append(f"Take profit triggered at {current_price:.2f}")

        exit_conditions = config.get("exit_conditions") or []
        if exit_conditions:
            exit_passed, exit_reasons = evaluate_conditions(exit_conditions, indicator_values)
            if exit_passed:
                reasons.extend(exit_reasons)

        unique_reasons = [reason for reason in dict.fromkeys(reason.strip() for reason in reasons if reason.strip())]
        return (bool(unique_reasons), unique_reasons)

    async def _close_open_trades(
        self,
        *,
        bot: CerberusBot,
        symbol: str,
        open_trades: list[CerberusTrade],
        current_price: float,
        reasons: list[str],
    ) -> None:
        # Resolve broker once for all exit orders in this batch
        broker = await self._resolve_broker(bot.user_id)

        closed_count = 0
        for open_trade in open_trades:
            exit_side = "BUY" if str(open_trade.side or "").lower().startswith("sell") else "SELL"
            trade_result = None
            try:
                if broker == "webull":
                    try:
                        trade_result = await self._submit_webull_order(
                            user_id=bot.user_id,
                            symbol=symbol,
                            side=exit_side,
                            quantity=int(open_trade.quantity or 0),
                        )
                    except Exception as e:
                        logger.warning(
                            "webull_exit_failed_falling_back",
                            bot_id=bot.id, symbol=symbol, error=str(e),
                        )
                if trade_result is None:
                    trade_result = await self._submit_alpaca_order(
                        symbol=symbol,
                        side=exit_side,
                        quantity=int(open_trade.quantity or 0),
                    )
            except Exception as e:
                logger.error("bot_exit_order_failed", bot_id=bot.id, symbol=symbol, error=str(e))
                continue
            if not trade_result:
                continue

            pnl = self._calculate_realized_pnl(open_trade, current_price)
            return_pct = self._calculate_return_pct(open_trade, pnl)
            explanation = "; ".join(reason.strip() for reason in reasons if reason.strip()) or None

            async with get_session() as session:
                result = await session.execute(
                    select(CerberusTrade).where(CerberusTrade.id == open_trade.id)
                )
                db_trade = result.scalar_one_or_none()
                if not db_trade:
                    continue

                payload = db_trade.payload_json if isinstance(db_trade.payload_json, dict) else {}
                payload["exit_reasons"] = reasons
                db_trade.exit_ts = datetime.utcnow()
                db_trade.exit_price = current_price
                db_trade.gross_pnl = pnl
                db_trade.net_pnl = pnl
                db_trade.return_pct = return_pct
                db_trade.notes = explanation or db_trade.notes
                db_trade.payload_json = payload
                await session.flush()

            closed_count += 1

        if closed_count:
            logger.info(
                "bot_position_closed",
                bot_id=bot.id,
                symbol=symbol,
                closed_trades=closed_count,
                reasons=reasons,
            )

    def _calculate_realized_pnl(self, trade: CerberusTrade, current_price: float) -> float:
        entry_price = float(trade.entry_price or 0.0)
        quantity = float(trade.quantity or 0.0)
        if entry_price <= 0 or quantity <= 0 or current_price <= 0:
            return 0.0

        is_short = str(trade.side or "").lower().startswith("sell")
        if is_short:
            return round((entry_price - current_price) * quantity, 2)
        return round((current_price - entry_price) * quantity, 2)

    def _calculate_return_pct(self, trade: CerberusTrade, pnl: float) -> float | None:
        entry_price = float(trade.entry_price or 0.0)
        quantity = float(trade.quantity or 0.0)
        basis = entry_price * quantity
        if basis <= 0:
            return None
        return round(pnl / basis, 4)

    async def _pause_bot(self, bot_id: str, reason: str) -> None:
        async with get_session() as session:
            result = await session.execute(
                select(CerberusBot).where(CerberusBot.id == bot_id)
            )
            db_bot = result.scalar_one_or_none()
            if not db_bot:
                return
            db_bot.status = BotStatus.PAUSED
            learning_status = db_bot.learning_status_json if isinstance(db_bot.learning_status_json, dict) else {}
            learning_status["status"] = "paused"
            learning_status["summary"] = reason or learning_status.get("summary") or "Paused by AI reasoning."
            db_bot.learning_status_json = learning_status

    async def _fetch_bars(self, symbol: str, timeframe: str) -> list[dict]:
        """Fetch OHLCV bars using yfinance (run in thread to avoid blocking)."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._fetch_bars_sync, symbol, timeframe)

    def _fetch_bars_sync(self, symbol: str, timeframe: str) -> list[dict]:
        """Synchronous yfinance fetch with TTL cache."""
        cache_key = f"{symbol}:{timeframe}"
        now = time.time()
        cached = _bar_cache.get(cache_key)
        if cached and (now - cached[0]) < _BAR_CACHE_TTL:
            return cached[1]

        import yfinance as yf

        # Map timeframe to yfinance parameters
        tf_map = {
            "1m": ("1m", "1d"),
            "5m": ("5m", "5d"),
            "15m": ("15m", "5d"),
            "1H": ("1h", "30d"),
            "4H": ("1h", "60d"),  # yf doesn't have 4h, use 1h
            "1D": ("1d", "1y"),
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
            _bar_cache[cache_key] = (now, bars)
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
        reasons: list[str] | None = None,
    ) -> CerberusTrade | None:
        """Execute a trade via the user's active broker (Webull or Alpaca)."""
        user_id = bot.user_id

        if current_price <= 0:
            logger.warning("bot_no_price", bot_id=bot.id, symbol=symbol)
            return None

        position_fraction = self._normalize_position_size(position_size_pct)
        if position_fraction <= 0:
            logger.warning(
                "bot_invalid_position_size",
                bot_id=bot.id,
                symbol=symbol,
                position_size_pct=position_size_pct,
            )
            return None

        # Map action to side
        side = "BUY" if action.upper() in ("BUY", "LONG") else "SELL"

        # Resolve which broker to use for this user
        broker = await self._resolve_broker(user_id)

        try:
            # Use bot's allocated capital if set, otherwise fall back to Alpaca equity
            if bot.allocated_capital and bot.allocated_capital > 0:
                equity = bot.allocated_capital
            else:
                alpaca_client = self._get_alpaca_client()
                account = alpaca_client.get_account()
                equity = float(account.equity)

            position_value = equity * position_fraction
            quantity = int(position_value / current_price)
            if quantity < 1:
                logger.warning(
                    "bot_insufficient_funds",
                    bot_id=bot.id,
                    symbol=symbol,
                    equity=equity,
                    allocated_capital=bot.allocated_capital,
                )
                return None

            # Submit order to the resolved broker
            order: dict | None = None
            used_broker = broker

            if broker == "webull":
                try:
                    order = await self._submit_webull_order(
                        user_id=user_id, symbol=symbol, side=side, quantity=quantity,
                    )
                except Exception as e:
                    logger.warning(
                        "webull_order_failed_falling_back",
                        bot_id=bot.id,
                        symbol=symbol,
                        error=str(e),
                    )
                    # Fall back to Alpaca paper
                    used_broker = "alpaca"

            if order is None:
                order = await self._submit_alpaca_order(
                    symbol=symbol, side=side, quantity=quantity,
                )
                used_broker = "alpaca"

            order_id = order.get("id") or order.get("order_id") or order.get("client_order_id")
            fill_price = float(order.get("filled_avg_price") or current_price)
            broker_tag = f"webull_{order.get('mode', 'paper')}" if used_broker == "webull" else "alpaca_paper"

            logger.info(
                "bot_trade_executed",
                bot_id=bot.id,
                symbol=symbol,
                side=side,
                quantity=quantity,
                price=fill_price,
                broker=broker_tag,
                order_id=order_id,
            )

            # Record in CerberusTrade for audit trail
            async with get_session() as session:
                explanation = "; ".join(reason.strip() for reason in (reasons or []) if reason.strip()) or None
                trade = CerberusTrade(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    bot_id=bot.id,
                    symbol=symbol.upper(),
                    side=side.lower(),
                    quantity=quantity,
                    entry_ts=datetime.utcnow(),
                    entry_price=fill_price,
                    strategy_tag=bot.name,
                    notes=explanation,
                    payload_json={
                        "reasons": reasons or [],
                        "bot_explanation": explanation,
                        "order_id": order_id,
                        "broker": broker_tag,
                    },
                    created_at=datetime.utcnow(),
                )
                session.add(trade)
                await session.flush()
                await session.refresh(trade)
                return trade

        except Exception as e:
            logger.error(
                "bot_trade_failed", bot_id=bot.id, symbol=symbol, error=str(e)
            )
        return None

    def _get_alpaca_client(self):
        """Get Alpaca paper trading client."""
        if not hasattr(self, "_alpaca_client") or self._alpaca_client is None:
            from config.settings import get_settings
            from alpaca.trading.client import TradingClient
            settings = get_settings()
            self._alpaca_client = TradingClient(
                settings.alpaca_api_key,
                settings.alpaca_secret_key,
                paper=True,
            )
        return self._alpaca_client

    async def _submit_alpaca_order(
        self, *, symbol: str, side: str, quantity: int,
    ) -> dict:
        """Submit a market order to Alpaca paper trading."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, self._submit_alpaca_order_sync, symbol, side, quantity,
        )

    def _submit_alpaca_order_sync(
        self, symbol: str, side: str, quantity: int,
    ) -> dict:
        from alpaca.trading.requests import MarketOrderRequest
        from alpaca.trading.enums import OrderSide, TimeInForce

        client = self._get_alpaca_client()
        order_data = MarketOrderRequest(
            symbol=symbol.upper(),
            qty=quantity,
            side=OrderSide.BUY if side.upper() == "BUY" else OrderSide.SELL,
            time_in_force=TimeInForce.DAY,
        )
        order = client.submit_order(order_data)
        return {
            "id": str(order.id),
            "status": str(order.status),
            "filled_avg_price": float(order.filled_avg_price) if order.filled_avg_price else None,
            "filled_qty": float(order.filled_qty) if order.filled_qty else None,
            "symbol": order.symbol,
            "side": str(order.side),
        }

    # ── Broker resolution ─────────────────────────────────────────────────

    async def _resolve_broker(self, user_id: int) -> str:
        """Determine which broker to use for a user.

        Checks UserApiSettings.active_equity_broker_id → UserApiConnection →
        ApiProvider to see if the active broker is Webull. Returns "webull" or
        "alpaca" (the default fallback).
        """
        try:
            async with get_session() as session:
                settings_result = await session.execute(
                    select(UserApiSettings).where(UserApiSettings.user_id == user_id)
                )
                settings = settings_result.scalar_one_or_none()
                if not settings or not settings.active_equity_broker_id:
                    return "alpaca"

                conn_result = await session.execute(
                    select(UserApiConnection)
                    .join(ApiProvider)
                    .where(
                        UserApiConnection.id == settings.active_equity_broker_id,
                        UserApiConnection.status == "connected",
                    )
                )
                conn = conn_result.scalar_one_or_none()
                if not conn:
                    return "alpaca"

                provider_result = await session.execute(
                    select(ApiProvider).where(ApiProvider.id == conn.provider_id)
                )
                provider = provider_result.scalar_one_or_none()
                if provider and provider.slug == "webull":
                    return "webull"
        except Exception as e:
            logger.warning("broker_resolve_error", user_id=user_id, error=str(e))

        return "alpaca"

    # ── Webull order submission ───────────────────────────────────────────

    async def _get_webull_clients(self, user_id: int, mode: str = "paper"):
        """Load Webull clients for a user, mirroring api/routes/webull._get_user_clients."""
        import json
        from db.encryption import decrypt_value
        from db.models import BrokerCredential, BrokerType
        from data.webull import create_webull_clients

        app_key = None
        app_secret = None

        # 1. Prefer UserApiConnection system
        async with get_session() as db:
            result = await db.execute(
                select(UserApiConnection)
                .join(ApiProvider)
                .where(
                    UserApiConnection.user_id == user_id,
                    UserApiConnection.status == "connected",
                    ApiProvider.slug == "webull",
                )
            )
            conn = result.scalar_one_or_none()

        if conn:
            try:
                creds = json.loads(decrypt_value(conn.encrypted_credentials))
                app_key = creds.get("app_key", "")
                app_secret = creds.get("app_secret", "")
            except Exception as exc:
                logger.error("webull_cred_decrypt_failed", user_id=user_id, error=str(exc))
                return None
        else:
            # 2. Fall back to legacy BrokerCredential
            async with get_session() as db:
                result = await db.execute(
                    select(BrokerCredential).where(
                        BrokerCredential.user_id == user_id,
                        BrokerCredential.broker_type == BrokerType.WEBULL,
                    )
                )
                cred = result.scalar_one_or_none()

            if not cred:
                return None

            app_key = decrypt_value(cred.encrypted_api_key)
            app_secret = decrypt_value(cred.encrypted_api_secret)

        if not app_key or not app_secret:
            return None

        try:
            return create_webull_clients(mode, app_key=app_key, app_secret=app_secret)
        except Exception as exc:
            logger.error("webull_client_create_error", user_id=user_id, error=str(exc))
            return None

    async def _submit_webull_order(
        self, *, user_id: int, symbol: str, side: str, quantity: int,
    ) -> dict:
        """Submit a market order via Webull. Returns a dict matching the Alpaca
        order result shape for consistency, or raises on failure."""
        from data.webull.trading import OrderRequest as WBOrderRequest

        clients = await self._get_webull_clients(user_id, mode="paper")
        if not clients:
            raise RuntimeError("No Webull credentials found for user")

        wb_req = WBOrderRequest(
            symbol=symbol.upper(),
            side=side.upper(),
            qty=quantity,
            order_type="MKT",
            tif="DAY",
        )

        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None,
            lambda: clients.trading.place_order(wb_req, user_confirmed=True),
        )

        if not result.success:
            raise RuntimeError(f"Webull order failed: {result.error}")

        return {
            "id": result.order_id,
            "client_order_id": result.client_order_id,
            "status": "submitted",
            "filled_avg_price": None,
            "filled_qty": None,
            "symbol": symbol.upper(),
            "side": side.upper(),
            "mode": result.mode,
        }

    def _is_market_open(self) -> bool:
        """Check if US stock market is currently open (rough check)."""
        now = datetime.now(_MARKET_TIMEZONE)
        # Weekends
        if now.weekday() >= 5:
            return False
        # Market hours: 9:30 AM - 4:00 PM ET
        market_open = dtime(9, 30)
        market_close = dtime(16, 0)
        return market_open <= now.time() <= market_close

    def _timeframe_to_seconds(self, tf: str) -> int:
        """Convert timeframe string to minimum seconds between evaluations.

        For daily (1D) strategies, evaluate every 5 minutes rather than once
        per day — conditions can change intraday and we want to catch the
        moment they trigger during market hours.
        """
        mapping = {
            "1m": 60,
            "5m": 300,
            "15m": 900,
            "1H": 3600,
            "4H": 14400,
            "1D": 300,
        }
        return mapping.get(tf, 300)

    async def _ai_adjust_capital(self, bot: CerberusBot) -> None:
        """Adjust allocated capital based on recent trade performance.

        Winning bots get more capital (up to 2x initial), losing bots get
        scaled back (down to 0.25x).  Adjustments are capped at ±10% per
        evaluation to avoid whipsawing.
        """
        try:
            async with get_session() as session:
                result = await session.execute(
                    select(CerberusTrade)
                    .where(
                        CerberusTrade.bot_id == bot.id,
                        CerberusTrade.exit_ts.is_not(None),
                    )
                    .order_by(CerberusTrade.exit_ts.desc())
                    .limit(10)
                )
                recent_trades = list(result.scalars().all())

            if len(recent_trades) < 3:
                return  # Not enough history

            wins = sum(1 for t in recent_trades if (t.gross_pnl or 0) > 0)
            win_rate = wins / len(recent_trades)

            current = bot.allocated_capital or 0
            if current <= 0:
                return

            # Scale: 70%+ win rate → grow, <40% → shrink
            if win_rate >= 0.7:
                new_capital = min(current * 1.10, current * 2.0)  # +10%, max 2x
            elif win_rate < 0.4:
                new_capital = max(current * 0.90, current * 0.25)  # -10%, min 0.25x
            else:
                return  # Neutral — no adjustment

            new_capital = round(new_capital, 2)
            if abs(new_capital - current) < 1:
                return

            async with get_session() as session:
                result = await session.execute(
                    select(CerberusBot).where(CerberusBot.id == bot.id)
                )
                db_bot = result.scalar_one_or_none()
                if db_bot:
                    db_bot.allocated_capital = new_capital

            logger.info(
                "ai_capital_adjusted",
                bot_id=bot.id,
                old_capital=current,
                new_capital=new_capital,
                win_rate=win_rate,
                recent_trades=len(recent_trades),
            )

            self._publish_activity(
                "capital_adjusted", bot, None,
                f"{bot.name} capital {'increased' if new_capital > current else 'decreased'}: "
                f"${current:,.0f} → ${new_capital:,.0f} (win rate {win_rate:.0%})",
                {"old_capital": current, "new_capital": new_capital, "win_rate": win_rate},
            )
        except Exception as e:
            logger.warning("ai_capital_adjust_error", bot_id=bot.id, error=str(e))

    def _normalize_position_size(self, position_size_pct: float) -> float:
        """Accept both fractional sizing (0.1 = 10%) and percent sizing (10 = 10%)."""
        if position_size_pct <= 0:
            return 0.0
        if position_size_pct <= 1:
            return position_size_pct
        return position_size_pct / 100.0

    @staticmethod
    def _publish_activity(
        event_type: str,
        bot: CerberusBot,
        symbol: str | None,
        headline: str,
        detail: dict | None = None,
    ) -> None:
        """Publish a bot activity event to the activity bus."""
        try:
            activity_bus.publish(BotActivityEvent(
                event_type=event_type,
                bot_id=bot.id,
                bot_name=bot.name or "Unnamed Bot",
                symbol=symbol,
                headline=headline,
                detail=detail or {},
                user_id=bot.user_id,
            ))
        except Exception:
            pass  # Never let event publishing break the bot loop


# Singleton instance
bot_runner = BotRunner()
