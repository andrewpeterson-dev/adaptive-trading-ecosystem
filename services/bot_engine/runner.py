"""
Bot execution engine — background async loop that evaluates running bots
against market data and executes trades when conditions are met.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from datetime import datetime, time as dtime
from typing import Optional
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
from db.models import (
    UserApiSettings,
    UserApiConnection,
    ApiProvider,
    UserRiskLimits,
    UserTradingSession,
    TradingModeEnum,
)
from services.activity_bus import BotActivityEvent, activity_bus
from services.bot_engine.indicators import compute_indicators
from services.bot_engine.evaluator import evaluate_conditions
from services.bot_engine.ai_evaluator import ai_evaluate_entries
from services.ai_brain import AITradingEngine
from services.ai_brain.types import AITradeDecision
from services.reasoning_engine import ReasoningEngine
from services.reasoning_engine.safety import (
    calculate_kelly_position_size,
    check_sector_concentration,
    update_category_scores,
)
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
        self._ai_engine = AITradingEngine()
        self._background_tasks: set[asyncio.Task] = set()

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
                logger.exception("bot_runner_error", error=str(e))
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
            # ── Kill-switch gate (primary) ───────────────────────────────
            try:
                if await self._is_kill_switch_active(bot.user_id):
                    logger.warning(
                        "bot_skipped_kill_switch",
                        bot_id=bot.id,
                        user_id=bot.user_id,
                    )
                    await self._pause_bot(
                        bot.id, "Kill switch active — bot paused automatically"
                    )
                    self._publish_activity(
                        "kill_switch_block", bot, None,
                        f"{bot.name} skipped — user kill switch is active",
                        {"reason": "kill_switch_active"},
                    )
                    continue
            except Exception as e:
                logger.error(
                    "kill_switch_check_error",
                    bot_id=bot.id,
                    error=str(e),
                )
                continue  # fail-closed: skip bot on error

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
        extended_hours = bool(config.get("extended_hours", False))

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

        # Check if market is open (extended_hours bots get 4AM-8PM ET window)
        if not self._is_market_open(extended_hours=extended_hours):
            return

        # Rate limit: don't evaluate same bot more than once per timeframe interval
        interval_seconds = self._timeframe_to_seconds(timeframe)
        last = self._last_eval.get(bot.id)
        if last and (datetime.utcnow() - last).total_seconds() < interval_seconds:
            return

        risk_context = await self._build_risk_context(bot)

        # ── AI Brain routing ──────────────────────────────────────────────
        if bot.ai_brain_config:
            brain_config = bot.ai_brain_config
            exec_mode = brain_config.get("execution_mode", "manual")

            if exec_mode in ("ai_driven", "ai_assisted"):
                # In ai_assisted mode, only proceed if rules triggered
                if exec_mode == "ai_assisted" and conditions:
                    # Fetch bars for first symbol to check conditions
                    if symbols:
                        _bars = await self._fetch_bars(symbols[0], timeframe)
                        if _bars and len(_bars) >= 50:
                            _ind_vals = compute_indicators(_bars, [
                                {"indicator": c["indicator"], "params": c.get("params", {})}
                                for c in conditions if isinstance(c, dict) and c.get("indicator")
                            ])
                            _ind_vals["CLOSE"] = float(_bars[-1].get("close", 0) or 0)
                            _passed, _ = evaluate_conditions(conditions, _ind_vals)
                            if not _passed:
                                self._last_eval[bot.id] = datetime.utcnow()
                                return

                # Build market state for AITradingEngine
                market_state = {
                    "symbols": symbols,
                    "user_id": bot.user_id,
                    "macro": risk_context,
                    "portfolio": risk_context,
                }

                decision = await self._ai_engine.evaluate(bot, market_state)

                # Record every AI decision unconditionally
                await self._record_ai_decision(bot, decision, is_shadow=False)

                # Execute actionable decisions
                if decision.action in ("BUY", "SELL", "EXIT") and decision.symbol:
                    trading_mode = await self._resolve_trading_mode(bot.user_id, bot_id=bot.id)
                    current_price = 0.0
                    try:
                        _price_bars = await self._fetch_bars(decision.symbol, timeframe)
                        if _price_bars:
                            current_price = float(_price_bars[-1].get("close", 0) or 0)
                    except Exception:
                        pass

                    try:
                        re_decision = await self._reasoning_engine.evaluate(
                            bot=bot, symbol=decision.symbol, signal=decision.action,
                            strategy_config=config, vix=risk_context.get("vix"),
                            portfolio_exposure=self._calculate_symbol_exposure(
                                risk_context, decision.symbol, current_price,
                            ),
                            daily_pnl_pct=float(risk_context.get("daily_pnl_pct") or 0.0),
                            trading_mode=trading_mode,
                        )

                        if re_decision.decision == "PAUSE_BOT":
                            await self._pause_bot(bot.id, re_decision.reasoning)
                            self._publish_activity(
                                "bot_paused", bot, decision.symbol,
                                f"{bot.name} paused — {re_decision.reasoning}",
                                {"decision": re_decision.decision, "reasoning": re_decision.reasoning},
                            )
                        elif re_decision.decision not in ("EXIT_POSITION", "DELAY_TRADE"):
                            adjusted_size = position_size_pct * re_decision.size_adjustment * decision.confidence
                            executed = await self._execute_trade(
                                bot, decision.symbol, decision.action, adjusted_size,
                                current_price,
                                reasons=[f"AI Brain: {decision.reasoning_summary} (conf: {decision.confidence:.0%})"],
                                extended_hours=extended_hours,
                            )
                            if executed:
                                self._publish_activity(
                                    "trade_executed", bot, decision.symbol,
                                    f"{bot.name} AI Brain {decision.action} {decision.symbol} @ ${current_price:.2f} (conf: {decision.confidence:.0%})",
                                    {"action": decision.action, "confidence": decision.confidence,
                                     "model": decision.model_used, "reasoning": decision.reasoning_summary},
                                )
                    except Exception as e:
                        logger.error("ai_brain_reasoning_error", bot_id=bot.id, error=str(e))

                # Fire shadow model comparisons (non-blocking)
                for shadow_model in brain_config.get("comparison_models", []):
                    task = asyncio.create_task(
                        self._run_shadow_evaluation(bot, market_state, shadow_model)
                    )
                    self._background_tasks.add(task)
                    task.add_done_callback(self._background_tasks.discard)

                self._last_eval[bot.id] = datetime.utcnow()
                return

        # Manual strategies use rigid condition evaluation (the conditions
        # the user configured).  AI evaluation is only for ai_generated or
        # custom strategy types that are designed to let the LLM decide.
        if strategy_type in ("ai_generated", "custom"):
            settings = get_settings()
            if settings.openai_api_key or settings.anthropic_api_key:
                await self._ai_evaluate_bot(bot, config, symbols, action, position_size_pct, risk_context)
                return
        if True:  # rigid condition path for manual strategies
            trading_mode = await self._resolve_trading_mode(bot.user_id, bot_id=bot.id)
            for symbol in symbols:
                try:
                    await self._evaluate_symbol(
                        bot, config, symbol, conditions, action,
                        position_size_pct, risk_context,
                        trading_mode=trading_mode,
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
                        extended_hours=bool(config.get("extended_hours", False)),
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
            self._last_eval[bot.id] = datetime.utcnow()
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

        # Alert AI evaluator about extended hours session characteristics
        if config.get("extended_hours") and self._is_extended_session():
            full_description += (
                "\n\nIMPORTANT: This is an EXTENDED HOURS session (pre-market or after-hours). "
                "Liquidity is significantly lower, spreads are wider, and price moves can be "
                "exaggerated. Be more selective — only enter with high conviction. "
                "Volume-based indicators (VWAP, volume) are unreliable during this session."
            )

        trading_mode = await self._resolve_trading_mode(bot.user_id, bot_id=bot.id)

        # Fetch sentiment for all symbols — required for informed trading
        batch_sentiment = None
        try:
            from services.sentiment.sentiment_service import get_sentiment_service
            eval_symbols = [sd["symbol"] for sd in symbol_data]
            batch_sentiment = await get_sentiment_service().analyze_batch(eval_symbols)
            logger.info(
                "bot_runner_sentiment_fetched",
                bot_id=bot.id,
                symbols=list(batch_sentiment.keys()),
                count=len(batch_sentiment),
            )
        except Exception as exc:
            logger.error(
                "bot_runner_sentiment_failed",
                bot_id=bot.id,
                error=str(exc),
                exc_info=True,
            )
            # Paper mode: proceed without sentiment — no real money at risk.
            # Live mode: skip cycle until sentiment is available.
            if trading_mode == "live":
                logger.info(
                    "bot_skipping_cycle",
                    bot_id=bot.id,
                    reason="sentiment data unavailable — live mode, will not trade blind",
                )
                self._last_eval[bot.id] = datetime.utcnow()
                return
            logger.info(
                "bot_sentiment_skip_paper",
                bot_id=bot.id,
                reason="sentiment unavailable — paper mode, proceeding without",
            )

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
            mode=trading_mode,
            sentiment_data=batch_sentiment,
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
                    trading_mode=trading_mode,
                )

                if decision.decision == "PAUSE_BOT":
                    await self._pause_bot(bot.id, decision.reasoning)
                    logger.info("bot_paused_by_reasoning", bot_id=bot.id, symbol=symbol, reasoning=decision.reasoning)
                    self._publish_activity(
                        "bot_paused", bot, symbol,
                        f"{bot.name} paused — {decision.reasoning}",
                        {"decision": decision.decision, "reasoning": decision.reasoning},
                    )
                    self._last_eval[bot.id] = datetime.utcnow()
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
                logger.error(
                    "reasoning_engine_error",
                    bot_id=bot.id,
                    symbol=symbol,
                    error=str(e),
                    exc_info=True,
                )
                logger.info(
                    "bot_skipping_cycle",
                    bot_id=bot.id,
                    reason=f"reasoning engine error: {e}",
                )
                continue

            executed_trade = await self._execute_trade(
                bot, symbol, action, adjusted_size, current_price,
                reasons=[f"AI: {signal.reasoning} (confidence: {signal.confidence}%)"],
                extended_hours=bool(config.get("extended_hours", False)),
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

        self._last_eval[bot.id] = datetime.utcnow()

    async def _evaluate_symbol(
        self,
        bot: CerberusBot,
        config: dict,
        symbol: str,
        conditions: list[dict],
        action: str,
        position_size_pct: float,
        risk_context: dict,
        trading_mode: str = "paper",
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

        # Compute indicators — include both explicit conditions AND compare_to refs
        indicators_needed = []
        for c in [*conditions, *exit_conditions]:
            if not isinstance(c, dict) or not c.get("indicator"):
                continue
            indicators_needed.append({"indicator": c["indicator"], "params": c.get("params", {})})
            # Also compute the referenced indicator for dynamic thresholds
            compare_to = str(c.get("compare_to") or "").strip().lower()
            if compare_to and compare_to not in ("price", "close"):
                # Parse "ema_26" → indicator="ema", params={"period": 26}
                ref_indicator = compare_to
                ref_params: dict = {}
                if "." in ref_indicator:
                    ref_indicator = ref_indicator.split(".")[0]
                if "_" in ref_indicator:
                    parts = ref_indicator.rsplit("_", 1)
                    if parts[1].isdigit():
                        ref_indicator = parts[0]
                        ref_params = {"period": int(parts[1])}
                indicators_needed.append({"indicator": ref_indicator, "params": ref_params})
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
                    extended_hours=bool(config.get("extended_hours", False)),
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
                    trading_mode=trading_mode,
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
                logger.error(
                    "reasoning_engine_error",
                    bot_id=bot.id,
                    symbol=symbol,
                    error=str(e),
                    exc_info=True,
                )
                logger.info(
                    "bot_skipping_cycle",
                    bot_id=bot.id,
                    reason=f"reasoning engine error: {e}",
                )
                return

            executed_trade = await self._execute_trade(
                bot,
                symbol,
                action,
                adjusted_size,
                current_price,
                reasons=reasons,
                extended_hours=bool(config.get("extended_hours", False)),
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
        settings = get_settings()
        # Use config values, falling back to global defaults so exits always fire
        stop_loss_pct = float(config.get("stop_loss_pct") or 0.0)
        if stop_loss_pct <= 0:
            stop_loss_pct = settings.default_stop_loss_pct / 100.0  # Convert from percent to fraction
        take_profit_pct = float(config.get("take_profit_pct") or 0.0)
        if take_profit_pct <= 0:
            take_profit_pct = settings.default_take_profit_pct / 100.0  # Convert from percent to fraction
        # Emergency exit: if loss exceeds emergency threshold, always exit
        emergency_loss_pct = settings.emergency_loss_pct / 100.0

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

            # Emergency exit — always fire regardless of config
            if emergency_loss_pct > 0:
                if is_short:
                    loss_pct = (current_price - entry_price) / entry_price
                else:
                    loss_pct = (entry_price - current_price) / entry_price
                if loss_pct >= emergency_loss_pct:
                    reasons.append(f"EMERGENCY exit: loss {loss_pct:.1%} exceeds {emergency_loss_pct:.1%} threshold")

            # Max hold time check
            if trade.entry_ts:
                hold_hours = (datetime.utcnow() - trade.entry_ts).total_seconds() / 3600.0
                if hold_hours > settings.max_hold_hours:
                    reasons.append(f"Max hold time exceeded ({hold_hours:.0f}h > {settings.max_hold_hours:.0f}h)")

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
        extended_hours: bool = False,
    ) -> None:
        # Resolve broker and trading mode once for all exit orders in this batch
        broker = await self._resolve_broker(bot.user_id)
        trading_mode = await self._resolve_trading_mode(bot.user_id, bot_id=bot.id)
        is_paper = trading_mode != "live"

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
                            extended_hours=extended_hours,
                            mode=trading_mode,
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
                        extended_hours=extended_hours,
                        paper=is_paper,
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

            # Record result for per-bot circuit breaker
            try:
                from services.trading_orchestrator import orchestrator
                if orchestrator.risk_engine:
                    orchestrator.risk_engine.bot_cb.record_result(
                        bot.id, is_loss=(pnl < 0),
                    )
            except Exception:
                pass  # Never let circuit breaker bookkeeping break the exit flow

        if closed_count:
            logger.info(
                "bot_position_closed",
                bot_id=bot.id,
                symbol=symbol,
                closed_trades=closed_count,
                reasons=reasons,
            )
            try:
                await update_category_scores(bot.user_id)
            except Exception as e:
                logger.warning("category_update_error", bot_id=bot.id, error=str(e))

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

    async def _is_kill_switch_active(
        self, user_id: int, mode: Optional[TradingModeEnum] = None
    ) -> bool:
        """Check whether the user's kill switch is active for a trading mode.

        When *mode* is supplied the caller has already resolved it (avoiding a
        redundant DB round-trip and a possible TOCTOU race).  When omitted the
        method resolves it internally, returning ``True`` (fail-closed) if the
        mode lookup itself fails.
        """
        if mode is None:
            try:
                resolved = await self._resolve_trading_mode(user_id)
                mode = (
                    TradingModeEnum.LIVE if resolved == "live"
                    else TradingModeEnum.PAPER
                )
            except Exception as e:
                logger.error(
                    "kill_switch_mode_lookup_failed_fail_closed",
                    user_id=user_id,
                    error=str(e),
                )
                return True  # fail-closed: block trading when mode unknown

        try:
            async with get_session() as session:
                result = await session.execute(
                    select(UserRiskLimits).where(
                        UserRiskLimits.user_id == user_id,
                        UserRiskLimits.mode == mode,
                    )
                )
                limits = result.scalar_one_or_none()
                if limits and limits.kill_switch_active:
                    return True
                return False
        except Exception as e:
            logger.error(
                "kill_switch_lookup_failed_fail_closed",
                user_id=user_id,
                error=str(e),
            )
            return True  # fail-closed: block trading when kill switch state unknown

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
        extended_hours: bool = False,
    ) -> CerberusTrade | None:
        """Execute a trade via the user's active broker (Webull or Alpaca)."""
        user_id = bot.user_id

        # ── Resolve trading mode ONCE for both kill-switch and order routing ──
        try:
            trading_mode = await self._resolve_trading_mode(user_id, bot_id=bot.id)
        except Exception as e:
            logger.error(
                "trade_mode_resolve_error",
                bot_id=bot.id,
                error=str(e),
            )
            # Cannot determine mode — fail closed (same as kill-switch active).
            return None

        mode_enum = (
            TradingModeEnum.LIVE if trading_mode == "live"
            else TradingModeEnum.PAPER
        )

        # ── Kill-switch safety gate (secondary) ─────────────────────────
        # Re-check at execution time in case the switch was flipped after
        # the initial _check_bots() evaluation started.
        try:
            if await self._is_kill_switch_active(user_id, mode=mode_enum):
                logger.warning(
                    "trade_blocked_kill_switch",
                    bot_id=bot.id,
                    symbol=symbol,
                    user_id=user_id,
                )
                return None
        except Exception as e:
            logger.error(
                "kill_switch_exec_check_error",
                bot_id=bot.id,
                error=str(e),
            )
            # Fail-open would be dangerous for a kill switch — fail closed.
            return None

        is_paper = trading_mode != "live"

        if current_price <= 0:
            logger.warning("bot_no_price", bot_id=bot.id, symbol=symbol)
            return None

        # Auto-reduce position size during extended hours (lower liquidity)
        if extended_hours and self._is_extended_session():
            position_size_pct = position_size_pct * 0.5
            if reasons is None:
                reasons = []
            reasons.append("Extended hours: position size halved for lower liquidity")

        # Quarter-Kelly position sizing
        kelly_equity = 0.0
        try:
            if bot.allocated_capital and bot.allocated_capital > 0:
                kelly_equity = bot.allocated_capital
            else:
                alpaca_client = self._get_alpaca_client(paper=is_paper)
                loop = asyncio.get_running_loop()
                account = await loop.run_in_executor(None, alpaca_client.get_account)
                kelly_equity = float(account.equity)
            position_fraction_raw = self._normalize_position_size(position_size_pct)
            kelly_frac, kelly_expl = await calculate_kelly_position_size(
                bot_id=bot.id,
                total_equity=kelly_equity,
                configured_pct=position_fraction_raw,
                trading_mode=trading_mode,
            )
            position_fraction = min(position_fraction_raw, kelly_frac)
            if position_fraction < position_fraction_raw:
                if reasons is None:
                    reasons = []
                reasons.append(f"Kelly sizing: {kelly_expl}")
                logger.info("kelly_applied", bot_id=bot.id, symbol=symbol, configured=position_fraction_raw, kelly=kelly_frac)
        except Exception as e:
            logger.warning("kelly_error", bot_id=bot.id, error=str(e))
            position_fraction = self._normalize_position_size(position_size_pct)

        if position_fraction <= 0:
            logger.warning("bot_invalid_position_size", bot_id=bot.id, symbol=symbol, position_size_pct=position_size_pct)
            return None

        # Map action to side
        side = "BUY" if action.upper() in ("BUY", "LONG") else "SELL"

        # Resolve which broker to use for this user
        broker = await self._resolve_broker(user_id)

        try:
            if bot.allocated_capital and bot.allocated_capital > 0:
                equity = bot.allocated_capital
            elif kelly_equity > 0:
                equity = kelly_equity
            else:
                alpaca_client = self._get_alpaca_client(paper=is_paper)
                loop = asyncio.get_running_loop()
                account = await loop.run_in_executor(None, alpaca_client.get_account)
                equity = float(account.equity)

            position_value = equity * position_fraction

            # Sector concentration check
            try:
                sector_limit = 0.30
                async with get_session() as session:
                    rl = (await session.execute(select(UserRiskLimits).where(UserRiskLimits.user_id == user_id, UserRiskLimits.mode == mode_enum))).scalar_one_or_none()
                    if rl and rl.sector_concentration_limit is not None:
                        sector_limit = rl.sector_concentration_limit
                allowed, max_val, sector_reason = await check_sector_concentration(user_id=user_id, symbol=symbol, proposed_value=position_value, total_equity=equity, sector_limit=sector_limit)
                if not allowed:
                    if max_val <= 0:
                        logger.info("sector_blocked", bot_id=bot.id, symbol=symbol, reason=sector_reason)
                        return None
                    position_value = max_val
                    if reasons is None:
                        reasons = []
                    reasons.append(sector_reason)
            except Exception as e:
                logger.warning("sector_check_error", bot_id=bot.id, error=str(e))

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
                        extended_hours=extended_hours,
                        mode=trading_mode,
                    )
                except Exception as e:
                    logger.warning(
                        "webull_order_failed_falling_back",
                        bot_id=bot.id,
                        symbol=symbol,
                        error=str(e),
                    )
                    # Fall back to Alpaca
                    used_broker = "alpaca"

            if order is None:
                order = await self._submit_alpaca_order(
                    symbol=symbol, side=side, quantity=quantity,
                    extended_hours=extended_hours,
                    paper=is_paper,
                )
                used_broker = "alpaca"

            order_id = order.get("id") or order.get("order_id") or order.get("client_order_id")
            fill_price = float(order.get("filled_avg_price") or current_price)
            broker_tag = f"webull_{order.get('mode', trading_mode)}" if used_broker == "webull" else f"alpaca_{trading_mode}"

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
                        "extended_hours": extended_hours,
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

    def _get_alpaca_client(self, paper: bool = True):
        """Get Alpaca trading client for the given mode.

        Caches one client per mode (paper vs live) so repeated calls
        within the same mode are fast.
        """
        if not hasattr(self, "_alpaca_clients"):
            self._alpaca_clients: dict[bool, object] = {}

        if paper not in self._alpaca_clients:
            from config.settings import get_settings
            from alpaca.trading.client import TradingClient
            settings = get_settings()
            self._alpaca_clients[paper] = TradingClient(
                settings.alpaca_api_key,
                settings.alpaca_secret_key,
                paper=paper,
            )
        return self._alpaca_clients[paper]

    async def _submit_alpaca_order(
        self, *, symbol: str, side: str, quantity: int,
        extended_hours: bool = False,
        paper: bool = True,
    ) -> dict:
        """Submit a market order to Alpaca."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, self._submit_alpaca_order_sync, symbol, side, quantity,
            extended_hours, paper,
        )

    def _submit_alpaca_order_sync(
        self, symbol: str, side: str, quantity: int,
        extended_hours: bool = False,
        paper: bool = True,
    ) -> dict:
        from alpaca.trading.requests import MarketOrderRequest
        from alpaca.trading.enums import OrderSide, TimeInForce

        client = self._get_alpaca_client(paper=paper)
        order_data = MarketOrderRequest(
            symbol=symbol.upper(),
            qty=quantity,
            side=OrderSide.BUY if side.upper() == "BUY" else OrderSide.SELL,
            time_in_force=TimeInForce.DAY,
            extended_hours=extended_hours,
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

    async def _resolve_trading_mode(self, user_id: int, bot_id: Optional[int] = None) -> str:
        """Look up the user's active trading mode from UserTradingSession.

        Returns "paper" or "live".  Defaults to "paper" when no session row
        exists.  Raises on DB errors so the caller can decide the fallback
        (e.g. fail-closed for kill-switch checks, or paper for order routing).
        """
        async with get_session() as session:
            result = await session.execute(
                select(UserTradingSession).where(
                    UserTradingSession.user_id == user_id
                )
            )
            trading_session = result.scalar_one_or_none()
            if trading_session and trading_session.active_mode == TradingModeEnum.LIVE:
                mode = "live"
            else:
                mode = "paper"

        logger.info(
            "bot_trading_mode_resolved",
            bot_id=bot_id,
            user_id=user_id,
            mode=mode,
        )
        return mode

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
        extended_hours: bool = False,
        mode: str = "paper",
    ) -> dict:
        """Submit a market order via Webull. Returns a dict matching the Alpaca
        order result shape for consistency, or raises on failure."""
        from data.webull.trading import OrderRequest as WBOrderRequest

        clients = await self._get_webull_clients(user_id, mode=mode)
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

    def _is_extended_session(self) -> bool:
        """Return True if we're currently in extended hours (pre/post-market)."""
        now = datetime.now(_MARKET_TIMEZONE)
        if now.weekday() >= 5:
            return False
        t = now.time()
        return (dtime(4, 0) <= t < dtime(9, 30)) or (dtime(16, 0) < t <= dtime(20, 0))

    def _is_market_open(self, extended_hours: bool = False) -> bool:
        """Check if US stock market is currently open (rough check).

        When *extended_hours* is True the window widens to include pre-market
        (4:00 AM ET) and after-hours (8:00 PM ET).
        """
        now = datetime.now(_MARKET_TIMEZONE)
        # Weekends — no extended hours sessions either
        if now.weekday() >= 5:
            return False
        if extended_hours:
            return dtime(4, 0) <= now.time() <= dtime(20, 0)
        return dtime(9, 30) <= now.time() <= dtime(16, 0)

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
        """Accept both fractional sizing (0.1 = 10%) and percent sizing (10 = 10%).

        Hard cap at 25% of equity regardless of input.
        """
        if position_size_pct <= 0:
            return 0.0
        if position_size_pct <= 1:
            return min(position_size_pct, 0.25)
        return min(position_size_pct / 100.0, 0.25)

    async def _run_shadow_evaluation(
        self, bot, market_state: dict, model: str,
    ) -> None:
        """Run shadow model evaluation — fire-and-forget, errors logged not raised."""
        try:
            decision = await self._ai_engine.evaluate(bot, market_state, model_override=model)
            await self._record_ai_decision(bot, decision, is_shadow=True)
        except Exception as e:
            logger.error("shadow_eval_error", bot_id=bot.id, model=model, error=str(e))

    async def _record_ai_decision(
        self, bot, decision: AITradeDecision, is_shadow: bool = False,
    ) -> None:
        """Persist AI decision to bot_model_performance + ai_trade_reasoning."""
        try:
            from db.cerberus_models import BotModelPerformance, AITradeReasoning
            async with get_session() as session:
                perf = BotModelPerformance(
                    bot_id=bot.id,
                    model_used=decision.model_used or "unknown",
                    symbol=decision.symbol or "",
                    action=decision.action,
                    confidence=decision.confidence,
                    reasoning_summary=decision.reasoning_summary,
                    entry_price=0,  # Will be enriched from market data
                    is_shadow=is_shadow,
                    decided_at=datetime.utcnow(),
                )
                session.add(perf)
                await session.flush()

                # Store per-node reasoning for Tier C
                for node_name, output in (decision.reasoning_full or {}).items():
                    reasoning = AITradeReasoning(
                        performance_id=perf.id,
                        node_name=node_name,
                        node_output={"report": output} if isinstance(output, str) else output,
                        model_used=decision.model_used or "unknown",
                    )
                    session.add(reasoning)
        except Exception as e:
            logger.error("record_ai_decision_error", bot_id=bot.id, error=str(e))

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
