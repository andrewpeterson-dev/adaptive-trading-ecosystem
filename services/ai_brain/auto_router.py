"""Auto-routing: select the best-performing AI model for a bot."""
from __future__ import annotations

import structlog

from services.ai_brain.performance_tracker import get_bot_model_metrics

logger = structlog.get_logger(__name__)

# Minimum resolved trades before a model is eligible for routing
MIN_TRADES = 5

# Scoring weights
W_WIN_RATE = 0.4
W_AVG_RETURN = 0.3
W_SHARPE = 0.2
W_DRAWDOWN = 0.1  # penalty — subtracted


def score_model(metrics: dict) -> float:
    """Compute weighted composite score for a model.

    score = (win_rate * 0.4) + (normalized_avg_return * 0.3)
            + (normalized_sharpe * 0.2) - (normalized_drawdown * 0.1)

    Returns float('-inf') if insufficient data.
    """
    if metrics.get("trades_count", 0) < MIN_TRADES:
        return float("-inf")

    win_rate = float(metrics.get("win_rate", 0))
    avg_return = float(metrics.get("avg_return", 0))
    sharpe = float(metrics.get("sharpe_ratio", 0))
    drawdown = abs(float(metrics.get("max_drawdown", 0)))

    # Normalize avg_return and sharpe to 0-1 range using sigmoid-like scaling
    norm_return = avg_return / (abs(avg_return) + 10)  # maps to (-1, 1) range
    norm_sharpe = sharpe / (abs(sharpe) + 2)            # maps to (-1, 1) range
    norm_drawdown = drawdown / (drawdown + 10)           # maps to (0, 1) range

    score = (
        W_WIN_RATE * win_rate
        + W_AVG_RETURN * norm_return
        + W_SHARPE * norm_sharpe
        - W_DRAWDOWN * norm_drawdown
    )
    return round(score, 6)


async def select_best_model(bot_id: str, default_model: str = "gpt-5.4") -> str:
    """Select the best model for a bot based on performance metrics.

    Returns the model name with the highest composite score.
    Falls back to default_model if no models have sufficient data.
    """
    try:
        metrics_by_model = await get_bot_model_metrics(bot_id)
    except Exception as e:
        logger.error("auto_router_metrics_error", bot_id=bot_id, error=str(e))
        return default_model

    if not metrics_by_model:
        logger.info("auto_router_no_data", bot_id=bot_id, fallback=default_model)
        return default_model

    scored = {}
    for model, metrics in metrics_by_model.items():
        s = score_model(metrics)
        scored[model] = s
        logger.debug("auto_router_score", bot_id=bot_id, model=model, score=s, metrics=metrics)

    # Filter out models with insufficient data
    eligible = {m: s for m, s in scored.items() if s != float("-inf")}

    if not eligible:
        logger.info("auto_router_insufficient_data", bot_id=bot_id, fallback=default_model)
        return default_model

    best = max(eligible, key=eligible.get)
    logger.info("auto_router_selected", bot_id=bot_id, model=best, score=eligible[best])
    return best
