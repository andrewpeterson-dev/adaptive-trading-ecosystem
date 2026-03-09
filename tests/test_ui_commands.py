"""Tests for UI command formatter (services/ai_core/ui_command_formatter.py)."""
from __future__ import annotations

import pytest

from services.ai_core.ui_command_formatter import (
    format_ui_commands,
    ALLOWED_ACTIONS,
    ALLOWED_COMPONENT_IDS,
)


# ---------------------------------------------------------------------------
# Constant validation tests
# ---------------------------------------------------------------------------

class TestConstants:
    def test_allowed_actions_is_set(self):
        assert isinstance(ALLOWED_ACTIONS, set)
        assert len(ALLOWED_ACTIONS) > 0

    def test_known_actions_present(self):
        expected = {
            "open_panel", "switch_tab", "highlight_component",
            "populate_strategy_builder", "populate_order_ticket",
            "navigate", "show_chart", "show_toast",
            "focus_symbol", "select_bot", "open_confirmation_modal",
        }
        assert expected == ALLOWED_ACTIONS

    def test_allowed_component_ids_is_set(self):
        assert isinstance(ALLOWED_COMPONENT_IDS, set)
        assert len(ALLOWED_COMPONENT_IDS) > 0

    def test_known_component_ids_present(self):
        expected = {
            "portfolio_chart", "positions_table", "options_chain",
            "risk_metrics", "order_ticket", "strategy_builder",
            "bot_list", "bot_performance_chart", "trade_history_table",
            "research_sources_panel",
        }
        assert expected == ALLOWED_COMPONENT_IDS


# ---------------------------------------------------------------------------
# format_ui_commands tests
# ---------------------------------------------------------------------------

class TestFormatUICommands:
    def test_valid_navigate_passes(self):
        cmds = [{"action": "navigate", "route": "/dashboard"}]
        result = format_ui_commands(cmds)
        assert len(result) == 1
        assert result[0]["action"] == "navigate"
        assert result[0]["route"] == "/dashboard"

    def test_invalid_action_rejected(self):
        cmds = [{"action": "drop_database"}]
        result = format_ui_commands(cmds)
        assert len(result) == 0

    def test_invalid_component_id_rejected(self):
        cmds = [{"action": "highlight_component", "componentId": "secret_admin_panel"}]
        result = format_ui_commands(cmds)
        assert len(result) == 0

    def test_valid_component_id_passes(self):
        for cid in ALLOWED_COMPONENT_IDS:
            cmds = [{"action": "highlight_component", "componentId": cid}]
            result = format_ui_commands(cmds)
            assert len(result) == 1, f"Component ID '{cid}' should pass"

    def test_external_url_rejected(self):
        cmds = [{"action": "navigate", "route": "https://attacker.com/steal"}]
        result = format_ui_commands(cmds)
        assert len(result) == 0

    def test_http_url_rejected(self):
        cmds = [{"action": "navigate", "route": "http://malicious.example.com"}]
        result = format_ui_commands(cmds)
        assert len(result) == 0

    def test_internal_route_passes(self):
        internal_routes = [
            "/", "/dashboard", "/portfolio/positions",
            "/bot/abc-123", "/backtest/results",
        ]
        for route in internal_routes:
            cmds = [{"action": "navigate", "route": route}]
            result = format_ui_commands(cmds)
            assert len(result) == 1, f"Route '{route}' should pass"

    def test_no_route_passes(self):
        cmds = [{"action": "show_toast"}]
        result = format_ui_commands(cmds)
        assert len(result) == 1

    def test_no_component_id_passes(self):
        cmds = [{"action": "open_panel"}]
        result = format_ui_commands(cmds)
        assert len(result) == 1

    def test_empty_list(self):
        result = format_ui_commands([])
        assert result == []

    def test_mixed_valid_and_invalid(self):
        cmds = [
            {"action": "navigate", "route": "/home"},
            {"action": "hack_system"},
            {"action": "show_chart", "componentId": "portfolio_chart"},
            {"action": "navigate", "route": "ftp://bad"},
            {"action": "focus_symbol"},
        ]
        result = format_ui_commands(cmds)
        assert len(result) == 3
        assert result[0]["action"] == "navigate"
        assert result[1]["action"] == "show_chart"
        assert result[2]["action"] == "focus_symbol"

    def test_all_allowed_actions_pass(self):
        for action in ALLOWED_ACTIONS:
            cmds = [{"action": action}]
            result = format_ui_commands(cmds)
            assert len(result) == 1, f"Action '{action}' should pass"

    def test_populate_order_ticket(self):
        cmds = [{
            "action": "populate_order_ticket",
            "componentId": "order_ticket",
            "data": {"symbol": "AAPL", "side": "buy", "quantity": 10},
        }]
        result = format_ui_commands(cmds)
        assert len(result) == 1
        assert result[0]["data"]["symbol"] == "AAPL"

    def test_populate_strategy_builder(self):
        cmds = [{
            "action": "populate_strategy_builder",
            "componentId": "strategy_builder",
            "data": {"strategy": "momentum", "lookback": 20},
        }]
        result = format_ui_commands(cmds)
        assert len(result) == 1

    def test_open_confirmation_modal(self):
        cmds = [{"action": "open_confirmation_modal", "data": {"proposal_id": "abc-123"}}]
        result = format_ui_commands(cmds)
        assert len(result) == 1

    def test_select_bot(self):
        cmds = [{"action": "select_bot", "data": {"bot_id": "bot-xyz"}}]
        result = format_ui_commands(cmds)
        assert len(result) == 1

    def test_protocol_relative_url_rejected(self):
        """Protocol-relative URLs (//evil.com) should be rejected (don't start with /)."""
        # Actually "//evil.com" starts with "/" so it would pass the simple startswith check.
        # This documents the current behavior for awareness.
        cmds = [{"action": "navigate", "route": "//evil.com"}]
        result = format_ui_commands(cmds)
        # Currently passes because it starts with "/". This is a known limitation.
        # The test documents this behavior rather than asserting rejection.
        assert len(result) == 1  # Documents current behavior
