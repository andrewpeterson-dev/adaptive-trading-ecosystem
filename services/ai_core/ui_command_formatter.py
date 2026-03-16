"""UI command formatter — validates and formats UI commands for the frontend."""

from __future__ import annotations


import structlog

logger = structlog.get_logger(__name__)

ALLOWED_ACTIONS = {
    "open_panel", "switch_tab", "highlight_component", "populate_strategy_builder",
    "populate_order_ticket", "navigate", "show_chart", "show_toast",
    "focus_symbol", "select_bot", "open_confirmation_modal",
}

ALLOWED_COMPONENT_IDS = {
    "portfolio_chart", "positions_table", "options_chain", "risk_metrics",
    "order_ticket", "strategy_builder", "bot_list", "bot_performance_chart",
    "trade_history_table", "research_sources_panel",
}


def format_ui_commands(raw_commands: list[dict]) -> list[dict]:
    """Validate and format UI commands from model output."""
    validated = []
    for cmd in raw_commands:
        action = cmd.get("action")
        if action not in ALLOWED_ACTIONS:
            logger.warning("rejected_ui_command", action=action)
            continue

        component_id = cmd.get("componentId")
        if component_id and component_id not in ALLOWED_COMPONENT_IDS:
            logger.warning("rejected_component_id", id=component_id)
            continue

        route = cmd.get("route", "")
        if route and not route.startswith("/"):
            logger.warning("rejected_external_nav", route=route)
            continue

        validated.append(cmd)
    return validated
