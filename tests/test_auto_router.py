# tests/test_auto_router.py
import pytest
from unittest.mock import AsyncMock, patch
from services.ai_brain.auto_router import select_best_model, score_model

def test_score_model_strong_performer():
    metrics = {
        "win_rate": 0.65,
        "avg_return": 8.0,
        "sharpe_ratio": 1.5,
        "max_drawdown": -5.0,
        "trades_count": 20,
    }
    score = score_model(metrics)
    assert score > 0

def test_score_model_weights():
    """Higher win rate should produce higher score than higher drawdown."""
    good = {"win_rate": 0.7, "avg_return": 5.0, "sharpe_ratio": 1.2, "max_drawdown": -3.0, "trades_count": 15}
    bad = {"win_rate": 0.3, "avg_return": -2.0, "sharpe_ratio": -0.5, "max_drawdown": -15.0, "trades_count": 15}
    assert score_model(good) > score_model(bad)

def test_score_model_insufficient_data():
    """Models with < MIN_TRADES should return -inf."""
    metrics = {"win_rate": 0.9, "avg_return": 20.0, "sharpe_ratio": 3.0, "max_drawdown": 0.0, "trades_count": 2}
    score = score_model(metrics)
    assert score == float("-inf")

@pytest.mark.asyncio
async def test_select_best_model_picks_highest_score():
    mock_metrics = {
        "gpt-5.4": {"win_rate": 0.5, "avg_return": 3.0, "sharpe_ratio": 0.8, "max_drawdown": -5.0, "trades_count": 20},
        "claude-sonnet-4-6": {"win_rate": 0.7, "avg_return": 8.0, "sharpe_ratio": 1.5, "max_drawdown": -2.0, "trades_count": 20},
    }
    with patch("services.ai_brain.auto_router.get_bot_model_metrics", new_callable=AsyncMock, return_value=mock_metrics):
        result = await select_best_model("bot-123", default_model="gpt-5.4")
    assert result == "claude-sonnet-4-6"

@pytest.mark.asyncio
async def test_select_best_model_fallback_on_no_data():
    with patch("services.ai_brain.auto_router.get_bot_model_metrics", new_callable=AsyncMock, return_value={}):
        result = await select_best_model("bot-123", default_model="gpt-5.4")
    assert result == "gpt-5.4"
