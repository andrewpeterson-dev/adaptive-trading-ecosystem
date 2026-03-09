"""Save policy — determines which assistant outputs should be persisted to memory."""

from __future__ import annotations

import structlog

logger = structlog.get_logger(__name__)

# Minimum content length to consider saving
_MIN_CONTENT_LENGTH = 100

# Keywords that indicate content worth persisting
_SAVE_KEYWORDS = {
    "strategy", "analysis", "recommendation", "risk assessment",
    "portfolio review", "backtest result", "trade rationale",
    "research finding", "earnings analysis", "macro outlook",
}

# Content types that should always be saved
_ALWAYS_SAVE_TYPES = {"thread_summary", "strategy_note", "research_note"}


class SavePolicy:
    """Determines whether assistant-generated content should be persisted to semantic memory."""

    def should_save(
        self,
        content: str,
        memory_type: str = "general",
        tool_calls: list[dict] | None = None,
        mode: str = "chat",
    ) -> bool:
        """Decide if this content warrants persistence.

        Criteria:
          1. Thread summaries and strategy/research notes always saved
          2. Content must exceed minimum length
          3. Research mode content is always saved
          4. Content with analytical keywords is saved
          5. Content produced alongside tool calls (indicates substantive analysis)
        """
        # Always save certain types
        if memory_type in _ALWAYS_SAVE_TYPES:
            return True

        # Too short to be meaningful
        if len(content.strip()) < _MIN_CONTENT_LENGTH:
            return False

        # Research mode always saved
        if mode == "research":
            return True

        # Check for analytical keywords
        content_lower = content.lower()
        if any(kw in content_lower for kw in _SAVE_KEYWORDS):
            return True

        # Content with tool calls indicates substantive work
        if tool_calls and len(tool_calls) > 0:
            return True

        return False

    def compute_importance(
        self,
        content: str,
        memory_type: str = "general",
        tool_calls: list[dict] | None = None,
    ) -> float:
        """Compute an importance score (0.0-1.0) for ranking memory items.

        Higher scores = more important = retrieved first in context.
        """
        score = 0.3  # base

        # Type bonus
        type_scores = {
            "thread_summary": 0.2,
            "strategy_note": 0.3,
            "research_note": 0.25,
            "trade_rationale": 0.35,
        }
        score += type_scores.get(memory_type, 0.0)

        # Length bonus (longer = more substantive, up to a point)
        length = len(content.strip())
        if length > 500:
            score += 0.1
        if length > 1500:
            score += 0.1

        # Tool call bonus
        if tool_calls:
            score += min(0.2, len(tool_calls) * 0.05)

        # Keyword bonus
        content_lower = content.lower()
        keyword_hits = sum(1 for kw in _SAVE_KEYWORDS if kw in content_lower)
        score += min(0.15, keyword_hits * 0.05)

        return min(1.0, score)
