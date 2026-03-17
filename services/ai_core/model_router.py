"""Deterministic model router for the Cerberus."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import structlog

from config.settings import get_settings
from services.ai_core.providers.base import BaseProvider
from services.ai_core.providers.openai_provider import OpenAIProvider
from services.ai_core.providers.anthropic_provider import AnthropicProvider
from services.ai_core.providers.perplexity_provider import PerplexityProvider
from services.ai_core.providers.fingpt_provider import FinGPTProvider

logger = structlog.get_logger(__name__)


class RoutingIntent(str, Enum):
    """High-level intent categories for routing."""
    SIMPLE_HELP = "simple_help"
    PORTFOLIO_ANALYSIS = "portfolio_analysis"
    STRATEGY = "strategy"
    TRADE_ACTION = "trade_action"
    BOT_MANAGEMENT = "bot_management"
    RISK_ANALYSIS = "risk_analysis"
    MARKET_DATA = "market_data"
    RESEARCH = "research"
    DEEP_RESEARCH = "deep_research"
    DOCUMENT_ANALYSIS = "document_analysis"
    UI_COMMAND = "ui_command"
    SENTIMENT_ANALYSIS = "sentiment_analysis"
    GENERAL = "general"


@dataclass
class RoutingDecision:
    """Result of model routing."""
    provider: BaseProvider
    model: str
    provider_name: str
    intent: RoutingIntent
    store: bool  # OpenAI store parameter
    reason: str


class ModelRouter:
    """Routes requests to the appropriate AI provider and model."""

    def __init__(self):
        self._openai = OpenAIProvider()
        self._anthropic = AnthropicProvider()
        self._perplexity = PerplexityProvider()
        self._fingpt = FinGPTProvider()
        self._settings = get_settings()

    def route(
        self,
        mode: str,
        message: str,
        has_tools: bool = False,
        has_documents: bool = False,
        has_sensitive_data: bool = True,
        tool_count: int = 0,
        openai_failed: bool = False,
        explicit_research: bool = False,
        allow_slow_expert: bool = False,
    ) -> RoutingDecision:
        """Determine which provider/model to use for a given request."""

        intent = self._classify_intent(mode, message, has_tools, has_documents, explicit_research, tool_count)

        # Fallback to Anthropic if OpenAI is down
        if openai_failed:
            return RoutingDecision(
                provider=self._anthropic,
                model=self._settings.anthropic_fallback_model,
                provider_name="anthropic",
                intent=intent,
                store=True,
                reason="OpenAI unavailable, using Anthropic fallback",
            )

        # Deep research → Perplexity
        if intent == RoutingIntent.DEEP_RESEARCH:
            return RoutingDecision(
                provider=self._perplexity,
                model=self._settings.perplexity_deep_research_model,
                provider_name="perplexity",
                intent=intent,
                store=True,
                reason="Explicit deep research request",
            )

        # Research mode with documents → Anthropic (long context)
        if intent == RoutingIntent.RESEARCH and has_documents:
            return RoutingDecision(
                provider=self._anthropic,
                model=self._settings.anthropic_fallback_model,
                provider_name="anthropic",
                intent=intent,
                store=True,
                reason="Research mode with documents, Anthropic long-context",
            )

        # Explicit research mode → Anthropic
        if explicit_research and intent == RoutingIntent.RESEARCH:
            return RoutingDecision(
                provider=self._anthropic,
                model=self._settings.anthropic_fallback_model,
                provider_name="anthropic",
                intent=intent,
                store=True,
                reason="Explicit research mode",
            )

        # Sentiment analysis -> FinGPT provider (must be checked before slow_expert)
        if intent == RoutingIntent.SENTIMENT_ANALYSIS:
            return RoutingDecision(
                provider=self._fingpt,
                model="fingpt-sentiment_llama2-13b_lora",
                provider_name="fingpt",
                intent=intent,
                store=False,
                reason="Sentiment analysis request, routing to FinGPT",
            )

        # Slow expert mode (optional, analysis-only)
        if allow_slow_expert and self._settings.feature_slow_expert_mode_enabled:
            return RoutingDecision(
                provider=self._openai,
                model=self._settings.openai_expert_model,
                provider_name="openai",
                intent=intent,
                store=False,
                reason="Slow expert mode enabled",
            )

        # Simple help → gpt-4.1 (low latency)
        if intent == RoutingIntent.SIMPLE_HELP:
            return RoutingDecision(
                provider=self._openai,
                model=self._settings.openai_low_latency_model,
                provider_name="openai",
                intent=intent,
                store=not has_sensitive_data,
                reason="Simple help, low-latency model",
            )

        # Everything else complex → gpt-5.4 (primary)
        return RoutingDecision(
            provider=self._openai,
            model=self._settings.openai_primary_model,
            provider_name="openai",
            intent=intent,
            store=not has_sensitive_data,
            reason=f"Complex {intent.value} request, primary model",
        )

    def route_search(self) -> RoutingDecision:
        """Route a market news / search query to Perplexity."""
        return RoutingDecision(
            provider=self._perplexity,
            model=self._settings.perplexity_search_model,
            provider_name="perplexity",
            intent=RoutingIntent.RESEARCH,
            store=True,
            reason="Market search via Perplexity",
        )

    def _classify_intent(
        self,
        mode: str,
        message: str,
        has_tools: bool,
        has_documents: bool,
        explicit_research: bool,
        tool_count: int,
    ) -> RoutingIntent:
        """Classify the routing intent from the request context."""
        msg_lower = message.lower()

        # Explicit modes
        if mode == "research" or explicit_research:
            if any(kw in msg_lower for kw in ["deep research", "exhaustive", "comprehensive analysis"]):
                return RoutingIntent.DEEP_RESEARCH
            return RoutingIntent.RESEARCH

        if mode == "strategy":
            return RoutingIntent.STRATEGY
        if mode == "bot_control":
            return RoutingIntent.BOT_MANAGEMENT
        if mode == "portfolio":
            return RoutingIntent.PORTFOLIO_ANALYSIS

        # Document analysis
        if has_documents:
            return RoutingIntent.DOCUMENT_ANALYSIS

        # Sentiment analysis
        if any(kw in msg_lower for kw in [
            "sentiment", "market mood", "news impact", "bullish or bearish",
            "market feeling", "investor sentiment", "news sentiment",
            "how does the market feel", "what is the mood",
        ]):
            return RoutingIntent.SENTIMENT_ANALYSIS

        # Trade actions
        if any(kw in msg_lower for kw in ["buy", "sell", "trade", "order", "execute"]):
            return RoutingIntent.TRADE_ACTION

        # Risk analysis
        if any(kw in msg_lower for kw in ["risk", "var", "drawdown", "exposure", "hedge"]):
            return RoutingIntent.RISK_ANALYSIS

        # Portfolio
        if any(kw in msg_lower for kw in ["portfolio", "positions", "holdings", "balance", "pnl", "p&l"]):
            return RoutingIntent.PORTFOLIO_ANALYSIS

        # Market data
        if any(kw in msg_lower for kw in ["price", "quote", "chart", "indicator", "earnings"]):
            return RoutingIntent.MARKET_DATA

        # Strategy
        if any(kw in msg_lower for kw in ["strategy", "backtest", "bot", "algorithm"]):
            return RoutingIntent.STRATEGY

        # Simple help (short messages, no tools needed)
        if len(message) < 100 and tool_count == 0 and not has_tools:
            return RoutingIntent.SIMPLE_HELP

        return RoutingIntent.GENERAL
