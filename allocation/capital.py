"""
Dynamic capital allocation engine.
Shifts capital toward outperforming models based on rolling metrics.
Implements performance-weighted allocation with floor/ceiling constraints.
"""

from datetime import datetime

import structlog

from config.settings import get_settings
from models.base import ModelBase

logger = structlog.get_logger(__name__)


class CapitalAllocator:
    """
    Allocates capital across models based on their rolling performance metrics.
    Uses a combination of Sharpe ratio, Sortino ratio, and drawdown to compute weights.
    """

    def __init__(self, total_capital: float = None):
        settings = get_settings()
        self.total_capital = total_capital or settings.initial_capital
        self.min_weight = settings.min_model_weight
        self.max_weight = settings.max_model_weight

        self.allocations: dict[str, float] = {}  # model_name -> weight (0-1)
        self.capital_map: dict[str, float] = {}    # model_name -> dollar amount
        self._history: list[dict] = []

    def compute_weights(self, models: list[ModelBase]) -> dict[str, float]:
        """
        Compute allocation weights from model performance metrics.

        Scoring formula:
            score = w1 * sharpe + w2 * sortino - w3 * abs(max_drawdown) + w4 * profit_factor
        """
        if not models:
            return {}

        scores = {}
        for model in models:
            m = model.metrics
            score = (
                0.35 * max(m.sharpe_ratio, 0)
                + 0.25 * max(m.sortino_ratio, 0)
                - 0.25 * abs(m.max_drawdown)
                + 0.15 * min(m.profit_factor, 5.0)  # Cap profit factor contribution
            )
            # Penalize models with very few trades
            if m.num_trades < 10:
                score *= 0.5
            scores[model.name] = max(score, 0.0)

        total_score = sum(scores.values())

        if total_score == 0:
            # Equal weight fallback
            n = len(models)
            raw_weights = {m.name: 1.0 / n for m in models}
        else:
            raw_weights = {name: score / total_score for name, score in scores.items()}

        # Apply floor and ceiling constraints
        weights = self._apply_constraints(raw_weights)
        self.allocations = weights

        # Compute dollar amounts
        self.capital_map = {name: w * self.total_capital for name, w in weights.items()}

        # Record history
        self._history.append({
            "timestamp": datetime.utcnow().isoformat(),
            "weights": dict(weights),
            "capital": dict(self.capital_map),
            "scores": scores,
        })

        logger.info("capital_allocated", weights=weights, total_capital=self.total_capital)
        return weights

    def _apply_constraints(self, raw_weights: dict[str, float]) -> dict[str, float]:
        """Enforce min/max weight constraints with redistribution."""
        weights = dict(raw_weights)
        len(weights)

        # Iteratively clamp and redistribute
        for _ in range(10):
            excess = 0.0
            deficit_count = 0

            for name, w in weights.items():
                if w < self.min_weight:
                    excess -= (self.min_weight - w)
                    weights[name] = self.min_weight
                elif w > self.max_weight:
                    excess += (w - self.max_weight)
                    weights[name] = self.max_weight
                else:
                    deficit_count += 1

            if abs(excess) < 1e-8:
                break

            # Redistribute excess to unclamped models
            adjustable = [n for n, w in weights.items() if self.min_weight < w < self.max_weight]
            if adjustable:
                per_model = excess / len(adjustable)
                for name in adjustable:
                    weights[name] += per_model

        # Normalize to sum to 1.0
        total = sum(weights.values())
        if total > 0:
            weights = {n: w / total for n, w in weights.items()}

        return weights

    def update_capital(self, new_total: float) -> None:
        """Update total capital (e.g., after P&L realization)."""
        self.total_capital = new_total
        self.capital_map = {name: w * new_total for name, w in self.allocations.items()}

    def get_allocation(self, model_name: str) -> float:
        """Get current dollar allocation for a model."""
        return self.capital_map.get(model_name, 0.0)

    def get_weight(self, model_name: str) -> float:
        """Get current weight for a model."""
        return self.allocations.get(model_name, 0.0)

    def get_allocation_summary(self) -> dict:
        return {
            "total_capital": self.total_capital,
            "allocations": dict(self.allocations),
            "capital_map": dict(self.capital_map),
            "num_models": len(self.allocations),
        }

    def get_history(self, limit: int = 50) -> list[dict]:
        return self._history[-limit:]
