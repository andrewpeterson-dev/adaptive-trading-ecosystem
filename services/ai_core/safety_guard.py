"""Safety guard — validates inputs, outputs, and enforces safety rules."""

from __future__ import annotations

import re
from typing import Optional

import structlog

from config.settings import get_settings

logger = structlog.get_logger(__name__)


class SafetyViolation(Exception):
    """Raised when a safety check fails."""
    def __init__(self, message: str, violation_type: str = "general"):
        self.violation_type = violation_type
        super().__init__(message)


class SafetyGuard:
    """Enforces safety rules for the AI Copilot."""

    # Patterns that should never appear in model outputs sent to the browser
    DANGEROUS_OUTPUT_PATTERNS = [
        r"<script",
        r"javascript:",
        r"on\w+\s*=",
        r"eval\s*\(",
        r"Function\s*\(",
        r"innerHTML",
        r"document\.write",
        r"window\.location\s*=",
    ]

    # Sensitive fields that must be redacted before sending to models
    SENSITIVE_FIELDS = {
        "api_key", "api_secret", "access_token", "refresh_token",
        "password", "secret", "credential", "encryption_key",
        "jwt_secret", "kms_key", "private_key",
    }

    def __init__(self):
        self._settings = get_settings()

    def check_feature_enabled(self, feature: str) -> None:
        """Verify a feature flag is enabled."""
        flag_map = {
            "copilot": self._settings.feature_copilot_enabled,
            "research": self._settings.feature_research_mode_enabled,
            "bot_mutations": self._settings.feature_bot_mutations_enabled,
            "paper_trade_proposals": self._settings.feature_paper_trade_proposals_enabled,
            "live_trade_proposals": self._settings.feature_live_trade_proposals_enabled,
            "slow_expert_mode": self._settings.feature_slow_expert_mode_enabled,
        }
        if not flag_map.get(feature, False):
            raise SafetyViolation(
                f"Feature '{feature}' is not enabled",
                violation_type="feature_disabled",
            )

    def validate_output(self, content: str) -> str:
        """Validate and sanitize model output before sending to frontend."""
        for pattern in self.DANGEROUS_OUTPUT_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                logger.warning("dangerous_output_detected", pattern=pattern)
                content = re.sub(pattern, "[BLOCKED]", content, flags=re.IGNORECASE)
        return content

    def redact_sensitive_data(self, data: dict) -> dict:
        """Redact sensitive fields from data before sending to model."""
        redacted = {}
        for key, value in data.items():
            key_lower = key.lower()
            if any(sensitive in key_lower for sensitive in self.SENSITIVE_FIELDS):
                redacted[key] = "[REDACTED]"
            elif isinstance(value, dict):
                redacted[key] = self.redact_sensitive_data(value)
            elif isinstance(value, list):
                redacted[key] = [
                    self.redact_sensitive_data(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                redacted[key] = value
        return redacted

    def check_trade_proposal_allowed(self, paper_or_live: str) -> None:
        """Check if trade proposals are allowed for the given mode."""
        if paper_or_live == "live":
            self.check_feature_enabled("live_trade_proposals")
            if not self._settings.live_trading_enabled:
                raise SafetyViolation(
                    "Live trading is not enabled",
                    violation_type="live_trading_disabled",
                )
        elif paper_or_live == "paper":
            self.check_feature_enabled("paper_trade_proposals")

    def check_bot_mutation_allowed(self) -> None:
        """Check if bot mutations are allowed."""
        self.check_feature_enabled("bot_mutations")

    def validate_ui_commands(self, commands: list[dict]) -> list[dict]:
        """Validate UI commands against allowlist."""
        from services.ai_core.ui_command_formatter import ALLOWED_ACTIONS, ALLOWED_COMPONENT_IDS

        validated = []
        for cmd in commands:
            action = cmd.get("action")
            if action not in ALLOWED_ACTIONS:
                logger.warning("blocked_ui_command", action=action)
                continue
            component_id = cmd.get("componentId")
            if component_id and component_id not in ALLOWED_COMPONENT_IDS:
                logger.warning("blocked_component_id", component_id=component_id)
                continue
            # Block navigation to external URLs
            route = cmd.get("route", "")
            if route and not route.startswith("/"):
                logger.warning("blocked_external_navigation", route=route)
                continue
            validated.append(cmd)
        return validated

    def check_rate_limit(self, user_id: int, action: str = "chat") -> None:
        """Check rate limits. For now, a simple in-memory check (upgrade to Redis later)."""
        # TODO: Implement Redis-backed rate limiting
        pass

    def validate_message_input(self, message: str) -> str:
        """Validate and sanitize user message input."""
        if not message or not message.strip():
            raise SafetyViolation("Empty message", violation_type="empty_input")
        if len(message) > 50000:
            raise SafetyViolation("Message too long (max 50000 chars)", violation_type="input_too_long")
        return message.strip()
