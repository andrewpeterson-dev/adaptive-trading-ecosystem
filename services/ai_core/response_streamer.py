"""Response streamer — emits typed WebSocket events for copilot streaming."""

from __future__ import annotations

from typing import Any


class ResponseStreamer:
    """Formats events for WebSocket streaming to the frontend.

    Event types (from spec section 16):
      assistant.delta  — partial text token
      assistant.message — final assembled message
      tool.start        — tool execution started
      tool.result       — tool execution completed
      chart.payload     — inline chart data
      ui.command        — UI command envelope
      trade.proposal    — trade proposal surfaced
      warning           — non-fatal warning
      error             — error message
      done              — turn complete
    """

    @staticmethod
    def delta(text: str) -> dict:
        return {"type": "assistant.delta", "data": {"text": text}}

    @staticmethod
    def message(
        turn_id: str,
        markdown: str,
        citations: list[dict] | None = None,
        charts: list[dict] | None = None,
        ui_commands: list[dict] | None = None,
        trade_signals: list[dict] | None = None,
        warnings: list[str] | None = None,
    ) -> dict:
        return {
            "type": "assistant.message",
            "data": {
                "turnId": turn_id,
                "markdown": markdown,
                "citations": citations or [],
                "charts": charts or [],
                "uiCommands": ui_commands or [],
                "structuredTradeSignals": trade_signals or [],
                "warnings": warnings or [],
            },
        }

    @staticmethod
    def tool_start(tool_name: str, category: str, input_data: dict | None = None) -> dict:
        return {
            "type": "tool.start",
            "data": {
                "toolName": tool_name,
                "category": category,
                "status": "running",
                "input": input_data or {},
            },
        }

    @staticmethod
    def tool_result(
        tool_name: str,
        category: str,
        output: Any = None,
        latency_ms: int = 0,
        error: str | None = None,
    ) -> dict:
        return {
            "type": "tool.result",
            "data": {
                "toolName": tool_name,
                "category": category,
                "status": "failed" if error else "completed",
                "output": output,
                "latencyMs": latency_ms,
                "error": error,
            },
        }

    @staticmethod
    def chart_payload(chart_spec: dict) -> dict:
        return {"type": "chart.payload", "data": chart_spec}

    @staticmethod
    def ui_command(commands: list[dict]) -> dict:
        return {"type": "ui.command", "data": {"commands": commands}}

    @staticmethod
    def trade_proposal(proposal: dict) -> dict:
        return {"type": "trade.proposal", "data": proposal}

    @staticmethod
    def warning(message: str) -> dict:
        return {"type": "warning", "data": {"message": message}}

    @staticmethod
    def error(message: str) -> dict:
        return {"type": "error", "data": {"message": message}}

    @staticmethod
    def done() -> dict:
        return {"type": "done", "data": {}}
