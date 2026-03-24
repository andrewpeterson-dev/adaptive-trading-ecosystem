"""
AITradingEngine — orchestrates AI-driven trade decisions.

Gathers data based on bot focus profile, runs the multi-agent
pipeline with the bot's selected model, returns a structured decision.
"""
from __future__ import annotations

import time
from typing import Optional

import structlog

from services.ai_brain.types import AITradeDecision, AIBrainConfig

logger = structlog.get_logger(__name__)

# Maps data sources to pipeline nodes that should be skipped when absent
SOURCE_TO_NODES = {
    "technical": "technical_analyst",
    "sentiment": "sentiment_analyst",
    "fundamental": "fundamental_analyst",
}


class AITradingEngine:
    """Thin orchestrator for AI-driven trading decisions."""

    async def evaluate(
        self,
        bot,  # CerberusBot
        market_state: dict,
        model_override: Optional[str] = None,
    ) -> AITradeDecision:
        """
        Run the full AI decision pipeline for a bot.

        Args:
            bot: CerberusBot with ai_brain_config
            market_state: Dict with symbols, prices, indicators, positions
            model_override: Override model for shadow/comparison runs
        """
        config = AIBrainConfig.from_json(bot.ai_brain_config)
        model = model_override or config.primary_model
        start_time = time.monotonic()

        # Ensemble mode silently uses primary model in Phase 1
        if config.ensemble_mode:
            logger.info("ensemble_mode_ignored_phase1", bot_id=bot.id)

        # Resolve universe
        universe = self._resolve_universe(config, market_state)

        # Determine which pipeline nodes to skip
        all_sources = {"technical", "sentiment", "fundamental"}
        active_sources = set(config.data_sources) & all_sources
        skip_nodes = [
            SOURCE_TO_NODES[src]
            for src in all_sources - active_sources
            if src in SOURCE_TO_NODES
        ]

        # Build symbol list
        symbols = market_state.get("symbols", config.universe_symbols)
        if not symbols:
            return AITradeDecision(
                action="HOLD",
                symbol="",
                quantity=0,
                confidence=0,
                reasoning_summary="No symbols in universe to evaluate.",
                model_used=model,
            )

        # Inject macro + portfolio data if those sources are active
        macro_data = (
            market_state.get("macro", {}) if "macro" in config.data_sources else {}
        )
        portfolio_data = (
            market_state.get("portfolio", {})
            if "portfolio" in config.data_sources
            else {}
        )

        # Run the multi-agent pipeline for each symbol
        from services.ai_core.multi_agent.runner import run_trade_analysis

        best_decision = AITradeDecision(
            action="HOLD",
            symbol="",
            quantity=0,
            confidence=0,
            reasoning_summary="No actionable signal found across symbols.",
            model_used=model,
        )

        for symbol in symbols:
            if symbol in config.universe_blacklist:
                continue

            try:
                result = await run_trade_analysis(
                    symbol=symbol,
                    action="BUY",  # AI decides the actual action
                    size=config.max_position_pct,
                    user_id=market_state.get("user_id", 0),
                    model_override=model,
                    skip_nodes=skip_nodes,
                    trading_thesis=config.trading_thesis,
                    macro_data=macro_data,
                    portfolio_data=portfolio_data,
                )

                if result is None:
                    continue

                # Map recommendation to action
                rec = (result.recommendation or "hold").lower()
                if rec in ("strong_buy", "buy"):
                    action = "BUY"
                elif rec in ("strong_sell", "sell"):
                    action = "SELL"
                elif rec == "exit":
                    action = "EXIT"
                else:
                    action = "HOLD"

                confidence = result.confidence or 0.0

                # Track the highest-confidence actionable signal
                if action != "HOLD" and confidence > best_decision.confidence:
                    reasoning_full = {}
                    if result.technical_report:
                        reasoning_full["technical_analyst"] = result.technical_report
                    if result.fundamental_report:
                        reasoning_full["fundamental_analyst"] = (
                            result.fundamental_report
                        )
                    if result.sentiment_report:
                        reasoning_full["sentiment_analyst"] = result.sentiment_report
                    if result.bull_case:
                        reasoning_full["bullish_researcher"] = result.bull_case
                    if result.bear_case:
                        reasoning_full["bearish_researcher"] = result.bear_case
                    if result.risk_assessment:
                        reasoning_full["risk_assessor"] = result.risk_assessment

                    best_decision = AITradeDecision(
                        action=action,
                        symbol=symbol,
                        quantity=0,  # Sizing done by BotRunner
                        confidence=confidence,
                        reasoning_summary=result.reasoning
                        or f"AI {rec} signal for {symbol}",
                        reasoning_full=reasoning_full,
                        data_contributions=self._extract_contributions(
                            reasoning_full, config.data_sources
                        ),
                        model_used=model,
                    )

            except Exception as e:
                logger.error(
                    "ai_brain_symbol_eval_error",
                    bot_id=bot.id,
                    symbol=symbol,
                    model=model,
                    error=str(e),
                )
                continue

        # Validate universe
        if best_decision.action != "HOLD" and universe:
            if best_decision.symbol not in universe:
                logger.warning(
                    "ai_decision_outside_universe",
                    bot_id=bot.id,
                    symbol=best_decision.symbol,
                    universe_size=len(universe),
                )
                return AITradeDecision(
                    action="HOLD",
                    symbol=best_decision.symbol,
                    quantity=0,
                    confidence=0,
                    reasoning_summary=f"Symbol {best_decision.symbol} not in configured universe.",
                    model_used=model,
                )

        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        logger.info(
            "ai_brain_evaluation_complete",
            bot_id=bot.id,
            model=model,
            action=best_decision.action,
            symbol=best_decision.symbol,
            confidence=best_decision.confidence,
            elapsed_ms=elapsed_ms,
        )
        return best_decision

    def _resolve_universe(
        self, config: AIBrainConfig, market_state: dict
    ) -> set:
        """Resolve universe config to a concrete set of allowed symbols."""
        if config.universe_mode == "fixed":
            return set(config.universe_symbols)
        elif config.universe_mode == "ai":
            return set()  # No restriction — AI picks freely
        else:
            # sector/index modes: use symbols from market_state if provided
            return set(market_state.get("universe_symbols", []))

    def _extract_contributions(
        self, reasoning_full: dict, data_sources: list
    ) -> dict:
        """Estimate which data sources contributed to the decision."""
        contributions = {}
        source_map = {
            "technical_analyst": "technical",
            "fundamental_analyst": "fundamental",
            "sentiment_analyst": "sentiment",
        }
        active_count = sum(
            1
            for k in reasoning_full
            if k in source_map and source_map[k] in data_sources
        )
        if active_count == 0:
            return contributions
        weight = round(1.0 / active_count, 2)
        for node, source in source_map.items():
            if node in reasoning_full and source in data_sources:
                contributions[source] = weight
        return contributions
