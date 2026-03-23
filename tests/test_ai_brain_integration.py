# tests/test_ai_brain_integration.py
"""Integration test for AI Brain pipeline: decision -> record -> metrics -> routing."""
import pytest
from unittest.mock import AsyncMock, patch

from services.ai_brain.performance_tracker import compute_model_metrics
from services.ai_brain.auto_router import select_best_model, score_model


class TestAIBrainPipeline:
    """Test the full AI Brain decision -> performance -> routing pipeline."""

    def test_decisions_produce_valid_metrics(self):
        """Decisions with P&L should produce valid performance metrics."""
        decisions = [
            {"pnl": 12.5, "confidence": 0.85, "decided_at": "2026-03-20T10:00:00"},
            {"pnl": -3.2, "confidence": 0.60, "decided_at": "2026-03-20T11:00:00"},
            {"pnl": 8.7, "confidence": 0.75, "decided_at": "2026-03-20T12:00:00"},
            {"pnl": -1.5, "confidence": 0.55, "decided_at": "2026-03-20T13:00:00"},
            {"pnl": 6.0, "confidence": 0.70, "decided_at": "2026-03-20T14:00:00"},
            {"pnl": 4.3, "confidence": 0.80, "decided_at": "2026-03-20T15:00:00"},
        ]
        metrics = compute_model_metrics(decisions)

        assert metrics["trades_count"] == 6
        assert 0 <= metrics["win_rate"] <= 1
        assert metrics["sharpe_ratio"] != 0  # Should have a real Sharpe value
        assert metrics["max_drawdown"] <= 0  # Drawdown is always non-positive
        assert metrics["total_pnl"] == pytest.approx(26.8, abs=0.01)

    def test_metrics_feed_into_scoring(self):
        """Performance metrics produce consistent scores for auto-routing."""
        good_metrics = compute_model_metrics([
            {"pnl": 10, "confidence": 0.8, "decided_at": f"2026-03-20T{10+i}:00:00"}
            for i in range(6)
        ])
        bad_metrics = compute_model_metrics([
            {"pnl": -5, "confidence": 0.4, "decided_at": f"2026-03-20T{10+i}:00:00"}
            for i in range(6)
        ])

        good_score = score_model(good_metrics)
        bad_score = score_model(bad_metrics)

        assert good_score > bad_score, "Profitable model should score higher"

    @pytest.mark.asyncio
    async def test_auto_router_selects_best(self):
        """Auto-router selects model with best score from real metrics."""
        model_a_decisions = [
            {"pnl": p, "confidence": 0.7, "decided_at": f"2026-03-20T{10+i}:00:00"}
            for i, p in enumerate([5, -2, 8, -1, 6])
        ]
        model_b_decisions = [
            {"pnl": p, "confidence": 0.6, "decided_at": f"2026-03-20T{10+i}:00:00"}
            for i, p in enumerate([-3, -5, 2, -4, -1])
        ]

        mock_metrics = {
            "model-a": compute_model_metrics(model_a_decisions),
            "model-b": compute_model_metrics(model_b_decisions),
        }

        with patch("services.ai_brain.auto_router.get_bot_model_metrics",
                    new_callable=AsyncMock, return_value=mock_metrics):
            best = await select_best_model("bot-123", default_model="model-b")

        assert best == "model-a", "Router should pick the profitable model"

    @pytest.mark.asyncio
    async def test_auto_router_falls_back_with_insufficient_data(self):
        """Auto-router falls back when models have < MIN_TRADES."""
        mock_metrics = {
            "model-a": compute_model_metrics([
                {"pnl": 100, "confidence": 0.9, "decided_at": "2026-03-20T10:00:00"},
                {"pnl": 50, "confidence": 0.8, "decided_at": "2026-03-20T11:00:00"},
            ]),  # Only 2 trades -- below MIN_TRADES
        }

        with patch("services.ai_brain.auto_router.get_bot_model_metrics",
                    new_callable=AsyncMock, return_value=mock_metrics):
            best = await select_best_model("bot-123", default_model="gpt-5.4")

        assert best == "gpt-5.4", "Should fall back to default with insufficient data"
