"""Tests for the deterministic model router (services/ai_core/model_router.py)."""
from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest

from services.ai_core.model_router import ModelRouter, RoutingIntent, RoutingDecision


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_settings(**overrides):
    """Return a mock settings object with sensible defaults."""
    defaults = dict(
        openai_primary_model="gpt-5.4",
        openai_low_latency_model="gpt-4.1",
        openai_expert_model="gpt-5.4-pro",
        anthropic_fallback_model="claude-sonnet-4-6",
        perplexity_search_model="sonar",
        perplexity_deep_research_model="sonar-deep-research",
        feature_slow_expert_mode_enabled=False,
    )
    defaults.update(overrides)
    mock = MagicMock()
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


def _make_router(**settings_overrides) -> ModelRouter:
    """Build a ModelRouter with mocked providers and settings."""
    settings = _mock_settings(**settings_overrides)
    with (
        patch("services.ai_core.model_router.OpenAIProvider"),
        patch("services.ai_core.model_router.AnthropicProvider"),
        patch("services.ai_core.model_router.PerplexityProvider"),
        patch("services.ai_core.model_router.get_settings", return_value=settings),
    ):
        router = ModelRouter()
    # Re-assign the settings so the route() method uses our mock
    router._settings = settings
    return router


# ---------------------------------------------------------------------------
# Intent classification tests
# ---------------------------------------------------------------------------

class TestIntentClassification:
    def test_short_no_tools_is_simple_help(self):
        router = _make_router()
        intent = router._classify_intent(
            mode="chat", message="hi", has_tools=False,
            has_documents=False, explicit_research=False, tool_count=0,
        )
        assert intent == RoutingIntent.SIMPLE_HELP

    def test_trade_keywords_detected(self):
        router = _make_router()
        for msg in ["buy 100 AAPL", "sell TSLA", "execute the order", "place a trade"]:
            intent = router._classify_intent(
                mode="chat", message=msg, has_tools=False,
                has_documents=False, explicit_research=False, tool_count=0,
            )
            assert intent == RoutingIntent.TRADE_ACTION, f"Failed for: {msg}"

    def test_risk_keywords_detected(self):
        router = _make_router()
        for msg in ["what is my risk", "VaR calculation", "drawdown analysis", "hedge my portfolio"]:
            intent = router._classify_intent(
                mode="chat", message=msg, has_tools=False,
                has_documents=False, explicit_research=False, tool_count=0,
            )
            assert intent == RoutingIntent.RISK_ANALYSIS, f"Failed for: {msg}"

    def test_research_mode_returns_research(self):
        router = _make_router()
        intent = router._classify_intent(
            mode="research", message="anything",
            has_tools=False, has_documents=False, explicit_research=False, tool_count=0,
        )
        assert intent == RoutingIntent.RESEARCH

    def test_deep_research_keywords(self):
        router = _make_router()
        intent = router._classify_intent(
            mode="research", message="do a deep research on macro trends",
            has_tools=False, has_documents=False, explicit_research=False, tool_count=0,
        )
        assert intent == RoutingIntent.DEEP_RESEARCH

    def test_strategy_mode(self):
        router = _make_router()
        intent = router._classify_intent(
            mode="strategy", message="anything",
            has_tools=False, has_documents=False, explicit_research=False, tool_count=0,
        )
        assert intent == RoutingIntent.STRATEGY

    def test_bot_control_mode(self):
        router = _make_router()
        intent = router._classify_intent(
            mode="bot_control", message="anything",
            has_tools=False, has_documents=False, explicit_research=False, tool_count=0,
        )
        assert intent == RoutingIntent.BOT_MANAGEMENT

    def test_documents_trigger_document_analysis(self):
        router = _make_router()
        intent = router._classify_intent(
            mode="chat", message="summarise this document " * 10,
            has_tools=False, has_documents=True, explicit_research=False, tool_count=0,
        )
        assert intent == RoutingIntent.DOCUMENT_ANALYSIS

    def test_long_message_is_general(self):
        router = _make_router()
        intent = router._classify_intent(
            mode="chat", message="a" * 200,
            has_tools=False, has_documents=False, explicit_research=False, tool_count=0,
        )
        assert intent == RoutingIntent.GENERAL

    def test_portfolio_keywords_detected(self):
        router = _make_router()
        intent = router._classify_intent(
            mode="chat", message="show my portfolio positions and P&L breakdown",
            has_tools=False, has_documents=False, explicit_research=False, tool_count=0,
        )
        assert intent == RoutingIntent.PORTFOLIO_ANALYSIS


# ---------------------------------------------------------------------------
# Routing decision tests
# ---------------------------------------------------------------------------

class TestRouting:
    def test_simple_message_routes_to_gpt41(self):
        router = _make_router()
        decision = router.route(mode="chat", message="hi", has_tools=False, tool_count=0)
        assert decision.model == "gpt-4.1"
        assert decision.provider_name == "openai"
        assert decision.intent == RoutingIntent.SIMPLE_HELP

    def test_complex_message_routes_to_gpt54(self):
        router = _make_router()
        decision = router.route(
            mode="chat",
            message="Analyze my portfolio and suggest rebalancing across multiple asset classes " * 3,
            has_tools=True,
            tool_count=5,
        )
        assert decision.model == "gpt-5.4"
        assert decision.provider_name == "openai"

    def test_research_mode_routes_to_anthropic(self):
        router = _make_router()
        decision = router.route(
            mode="chat",
            message="Tell me about semiconductors",
            explicit_research=True,
        )
        assert decision.model == "claude-sonnet-4-6"
        assert decision.provider_name == "anthropic"

    def test_deep_research_routes_to_perplexity(self):
        router = _make_router()
        decision = router.route(
            mode="research",
            message="deep research on the macro environment and comprehensive analysis",
        )
        assert decision.model == "sonar-deep-research"
        assert decision.provider_name == "perplexity"

    def test_openai_fallback_routes_to_anthropic(self):
        router = _make_router()
        decision = router.route(
            mode="chat",
            message="hi",
            openai_failed=True,
        )
        assert decision.model == "claude-sonnet-4-6"
        assert decision.provider_name == "anthropic"
        assert "fallback" in decision.reason.lower()

    def test_slow_expert_mode_disabled_by_default(self):
        router = _make_router(feature_slow_expert_mode_enabled=False)
        decision = router.route(
            mode="chat",
            message="Give me an expert analysis of volatility surface" * 5,
            allow_slow_expert=True,
        )
        # Should NOT route to expert model because feature flag is off
        assert decision.model != "gpt-5.4-pro"

    def test_slow_expert_mode_enabled_gates_pro(self):
        router = _make_router(feature_slow_expert_mode_enabled=True)
        decision = router.route(
            mode="chat",
            message="Give me an expert analysis of the vol surface" * 5,
            allow_slow_expert=True,
        )
        assert decision.model == "gpt-5.4-pro"
        assert decision.provider_name == "openai"
        assert decision.store is False  # expert mode doesn't store

    def test_research_with_documents_routes_to_anthropic(self):
        router = _make_router()
        decision = router.route(
            mode="research",
            message="summarise the uploaded 10-K filing",
            has_documents=True,
            explicit_research=True,
        )
        assert decision.model == "claude-sonnet-4-6"
        assert decision.provider_name == "anthropic"

    def test_route_search(self):
        router = _make_router()
        decision = router.route_search()
        assert decision.model == "sonar"
        assert decision.provider_name == "perplexity"
        assert decision.intent == RoutingIntent.RESEARCH

    def test_sensitive_data_disables_store(self):
        router = _make_router()
        decision = router.route(mode="chat", message="hi", has_sensitive_data=True)
        assert decision.store is False or decision.store is True
        # For simple help with sensitive data: store = not has_sensitive_data = False
        decision_sensitive = router.route(mode="chat", message="hi", has_sensitive_data=True)
        assert decision_sensitive.store is False

    def test_non_sensitive_enables_store(self):
        router = _make_router()
        decision = router.route(mode="chat", message="hi", has_sensitive_data=False)
        assert decision.store is True
