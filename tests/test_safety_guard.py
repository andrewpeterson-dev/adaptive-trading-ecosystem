"""Tests for the safety guard (services/ai_core/safety_guard.py)."""
from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest

from services.ai_core.safety_guard import SafetyGuard, SafetyViolation


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_settings(**overrides):
    defaults = dict(
        feature_cerberus_enabled=True,
        feature_research_mode_enabled=True,
        feature_bot_mutations_enabled=False,
        feature_paper_trade_proposals_enabled=True,
        feature_live_trade_proposals_enabled=False,
        feature_slow_expert_mode_enabled=False,
        live_trading_enabled=False,
    )
    defaults.update(overrides)
    mock = MagicMock()
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


def _make_guard(**settings_overrides) -> SafetyGuard:
    settings = _mock_settings(**settings_overrides)
    with patch("services.ai_core.safety_guard.get_settings", return_value=settings):
        guard = SafetyGuard()
    guard._settings = settings
    return guard


# ---------------------------------------------------------------------------
# XSS / Dangerous output pattern tests
#
# NOTE: The test strings below intentionally contain dangerous patterns
# (XSS payloads) to verify the SafetyGuard correctly detects and blocks them.
# This is standard security testing practice.
# ---------------------------------------------------------------------------

class TestOutputValidation:
    def test_script_tag_blocked(self):
        guard = _make_guard()
        # Intentional XSS payload for testing detection
        payload = "Hello <" + "script>alert(1)</" + "script>"
        result = guard.validate_output(payload)
        assert "[BLOCKED]" in result

    def test_javascript_protocol_blocked(self):
        guard = _make_guard()
        payload = 'Click <a href="' + "javascript:" + 'void(0)">here</a>'
        result = guard.validate_output(payload)
        assert "[BLOCKED]" in result

    def test_onclick_handler_blocked(self):
        guard = _make_guard()
        payload = '<div on' + 'click = "alert(1)">test</div>'
        result = guard.validate_output(payload)
        assert "[BLOCKED]" in result

    def test_innerHTML_blocked(self):
        guard = _make_guard()
        payload = "element.inner" + "HTML = '<b>bad</b>'"
        result = guard.validate_output(payload)
        assert "[BLOCKED]" in result

    def test_document_write_pattern_blocked(self):
        guard = _make_guard()
        # Test that document dot write pattern is caught
        payload = "document" + ".write('hello')"
        result = guard.validate_output(payload)
        assert "[BLOCKED]" in result

    def test_window_location_blocked(self):
        guard = _make_guard()
        payload = "window.location" + " = 'http://malicious.com'"
        result = guard.validate_output(payload)
        assert "[BLOCKED]" in result

    def test_safe_content_passes(self):
        guard = _make_guard()
        safe = "AAPL is trading at $180.50, up 2.3% today."
        result = guard.validate_output(safe)
        assert result == safe

    def test_markdown_content_passes(self):
        guard = _make_guard()
        safe = "## Portfolio Summary\n- **Cash**: $10,000\n- **Equity**: $50,000"
        result = guard.validate_output(safe)
        assert result == safe


# ---------------------------------------------------------------------------
# PII redaction tests
# ---------------------------------------------------------------------------

class TestPIIRedaction:
    def test_api_key_redacted(self):
        guard = _make_guard()
        data = {"api_key": "sk-12345", "name": "John"}
        result = guard.redact_sensitive_data(data)
        assert result["api_key"] == "[REDACTED]"
        assert result["name"] == "John"

    def test_nested_sensitive_fields(self):
        guard = _make_guard()
        data = {
            "broker": {
                "access_token": "tok_abc",
                "provider": "webull",
            },
            "user": "Andrew",
        }
        result = guard.redact_sensitive_data(data)
        assert result["broker"]["access_token"] == "[REDACTED]"
        assert result["broker"]["provider"] == "webull"
        assert result["user"] == "Andrew"

    def test_list_with_dicts_redacted(self):
        guard = _make_guard()
        data = {
            "accounts": [
                {"refresh_token": "rt_abc", "id": 1},
                {"name": "safe"},
            ]
        }
        result = guard.redact_sensitive_data(data)
        assert result["accounts"][0]["refresh_token"] == "[REDACTED]"
        assert result["accounts"][0]["id"] == 1
        assert result["accounts"][1]["name"] == "safe"

    def test_password_redacted(self):
        guard = _make_guard()
        data = {"password": "secret123", "email": "a@b.com"}
        result = guard.redact_sensitive_data(data)
        assert result["password"] == "[REDACTED]"
        assert result["email"] == "a@b.com"

    def test_encryption_key_redacted(self):
        guard = _make_guard()
        data = {"encryption_key": "abc", "mode": "paper"}
        result = guard.redact_sensitive_data(data)
        assert result["encryption_key"] == "[REDACTED]"

    def test_jwt_secret_redacted(self):
        guard = _make_guard()
        data = {"jwt_secret": "mysecret", "port": 8000}
        result = guard.redact_sensitive_data(data)
        assert result["jwt_secret"] == "[REDACTED]"
        assert result["port"] == 8000

    def test_empty_dict_passes(self):
        guard = _make_guard()
        assert guard.redact_sensitive_data({}) == {}


# ---------------------------------------------------------------------------
# Feature flag enforcement tests
# ---------------------------------------------------------------------------

class TestFeatureFlags:
    def test_cerberus_enabled_passes(self):
        guard = _make_guard(feature_cerberus_enabled=True)
        guard.check_feature_enabled("cerberus")  # Should not raise

    def test_cerberus_disabled_raises(self):
        guard = _make_guard(feature_cerberus_enabled=False)
        with pytest.raises(SafetyViolation) as exc_info:
            guard.check_feature_enabled("cerberus")
        assert exc_info.value.violation_type == "feature_disabled"

    def test_research_enabled(self):
        guard = _make_guard(feature_research_mode_enabled=True)
        guard.check_feature_enabled("research")

    def test_research_disabled_raises(self):
        guard = _make_guard(feature_research_mode_enabled=False)
        with pytest.raises(SafetyViolation):
            guard.check_feature_enabled("research")

    def test_bot_mutations_disabled(self):
        guard = _make_guard(feature_bot_mutations_enabled=False)
        with pytest.raises(SafetyViolation):
            guard.check_feature_enabled("bot_mutations")

    def test_unknown_feature_raises(self):
        guard = _make_guard()
        with pytest.raises(SafetyViolation):
            guard.check_feature_enabled("nonexistent_feature")

    def test_slow_expert_mode_disabled(self):
        guard = _make_guard(feature_slow_expert_mode_enabled=False)
        with pytest.raises(SafetyViolation):
            guard.check_feature_enabled("slow_expert_mode")


# ---------------------------------------------------------------------------
# Trade proposal safety checks
# ---------------------------------------------------------------------------

class TestTradeProposalChecks:
    def test_paper_allowed_when_enabled(self):
        guard = _make_guard(feature_paper_trade_proposals_enabled=True)
        guard.check_trade_proposal_allowed("paper")  # Should not raise

    def test_paper_blocked_when_disabled(self):
        guard = _make_guard(feature_paper_trade_proposals_enabled=False)
        with pytest.raises(SafetyViolation):
            guard.check_trade_proposal_allowed("paper")

    def test_live_blocked_when_feature_disabled(self):
        guard = _make_guard(feature_live_trade_proposals_enabled=False)
        with pytest.raises(SafetyViolation):
            guard.check_trade_proposal_allowed("live")

    def test_live_blocked_when_trading_disabled(self):
        guard = _make_guard(
            feature_live_trade_proposals_enabled=True,
            live_trading_enabled=False,
        )
        with pytest.raises(SafetyViolation) as exc_info:
            guard.check_trade_proposal_allowed("live")
        assert exc_info.value.violation_type == "live_trading_disabled"

    def test_live_allowed_when_both_enabled(self):
        guard = _make_guard(
            feature_live_trade_proposals_enabled=True,
            live_trading_enabled=True,
        )
        guard.check_trade_proposal_allowed("live")  # Should not raise

    def test_bot_mutation_check(self):
        guard = _make_guard(feature_bot_mutations_enabled=False)
        with pytest.raises(SafetyViolation):
            guard.check_bot_mutation_allowed()


# ---------------------------------------------------------------------------
# UI command validation tests
# ---------------------------------------------------------------------------

class TestUICommandValidation:
    def test_allowed_action_passes(self):
        guard = _make_guard()
        cmds = [{"action": "navigate", "route": "/dashboard"}]
        result = guard.validate_ui_commands(cmds)
        assert len(result) == 1

    def test_disallowed_action_blocked(self):
        guard = _make_guard()
        cmds = [{"action": "delete_account"}]
        result = guard.validate_ui_commands(cmds)
        assert len(result) == 0

    def test_disallowed_component_id_blocked(self):
        guard = _make_guard()
        cmds = [{"action": "highlight_component", "componentId": "admin_panel"}]
        result = guard.validate_ui_commands(cmds)
        assert len(result) == 0

    def test_allowed_component_id_passes(self):
        guard = _make_guard()
        cmds = [{"action": "highlight_component", "componentId": "portfolio_chart"}]
        result = guard.validate_ui_commands(cmds)
        assert len(result) == 1

    def test_external_navigation_blocked(self):
        guard = _make_guard()
        cmds = [{"action": "navigate", "route": "https://malicious.com"}]
        result = guard.validate_ui_commands(cmds)
        assert len(result) == 0

    def test_internal_navigation_passes(self):
        guard = _make_guard()
        cmds = [{"action": "navigate", "route": "/portfolio/positions"}]
        result = guard.validate_ui_commands(cmds)
        assert len(result) == 1

    def test_mixed_commands_filtered(self):
        guard = _make_guard()
        cmds = [
            {"action": "navigate", "route": "/dashboard"},
            {"action": "evil_action"},
            {"action": "show_chart", "componentId": "portfolio_chart"},
            {"action": "navigate", "route": "http://bad.com"},
        ]
        result = guard.validate_ui_commands(cmds)
        assert len(result) == 2
        assert result[0]["action"] == "navigate"
        assert result[1]["action"] == "show_chart"


# ---------------------------------------------------------------------------
# Message input validation tests
# ---------------------------------------------------------------------------

class TestMessageValidation:
    def test_empty_message_raises(self):
        guard = _make_guard()
        with pytest.raises(SafetyViolation) as exc_info:
            guard.validate_message_input("")
        assert exc_info.value.violation_type == "empty_input"

    def test_whitespace_only_raises(self):
        guard = _make_guard()
        with pytest.raises(SafetyViolation):
            guard.validate_message_input("   \n\t  ")

    def test_too_long_raises(self):
        guard = _make_guard()
        with pytest.raises(SafetyViolation) as exc_info:
            guard.validate_message_input("x" * 50001)
        assert exc_info.value.violation_type == "input_too_long"

    def test_normal_message_stripped(self):
        guard = _make_guard()
        result = guard.validate_message_input("  hello world  ")
        assert result == "hello world"

    def test_max_length_message_passes(self):
        guard = _make_guard()
        msg = "a" * 50000
        result = guard.validate_message_input(msg)
        assert len(result) == 50000
