"""
Meta-learning layer.
Learns which models perform best under which market regimes
and adjusts ensemble weights accordingly.
Scaffold for future reinforcement learning upgrade.
"""

from collections import defaultdict
from datetime import datetime

import numpy as np
import structlog

from intelligence.regime import Regime
from models.base import ModelBase

logger = structlog.get_logger(__name__)


class MetaLearner:
    """
    Tracks model performance per regime and learns optimal allocation patterns.

    Current implementation: weighted averaging of historical performance per regime.
    Future: replace with RL agent (e.g., contextual bandit or PPO) that learns
    allocation policies from regime features.
    """

    def __init__(self):
        # regime -> model_name -> list of sharpe observations
        self._regime_performance: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
        self._regime_weights: dict[str, dict[str, float]] = {}
        self._decision_log: list[dict] = []

    def record_performance(self, regime: Regime, model: ModelBase) -> None:
        """Record a model's current performance under the given regime."""
        self._regime_performance[regime.value][model.name].append(model.metrics.sharpe_ratio)

    def record_all(self, regime: Regime, models: list[ModelBase]) -> None:
        """Record performance for all models under current regime."""
        for model in models:
            self.record_performance(regime, model)

    def compute_regime_weights(self, regime: Regime) -> dict[str, float]:
        """
        Compute optimal model weights for a given regime based on
        historical performance in that regime.
        """
        perf = self._regime_performance.get(regime.value, {})
        if not perf:
            return {}

        # Use exponentially weighted mean — recent observations matter more
        scores = {}
        for model_name, sharpe_history in perf.items():
            if not sharpe_history:
                continue
            weights = np.exp(np.linspace(-1, 0, len(sharpe_history)))
            weights /= weights.sum()
            scores[model_name] = max(np.dot(weights, sharpe_history), 0.0)

        total = sum(scores.values())
        if total > 0:
            regime_weights = {name: score / total for name, score in scores.items()}
        else:
            n = len(scores)
            regime_weights = {name: 1.0 / n for name in scores} if n > 0 else {}

        self._regime_weights[regime.value] = regime_weights
        logger.info("regime_weights_computed", regime=regime.value, weights=regime_weights)
        return regime_weights

    def get_recommended_weights(self, current_regime: Regime, models: list[ModelBase]) -> dict[str, float]:
        """
        Get weight recommendations for the current regime.
        Falls back to equal weights if no regime-specific data exists.
        """
        regime_weights = self._regime_weights.get(current_regime.value)

        if regime_weights and len(regime_weights) > 0:
            # Blend regime-specific with global performance (70/30)
            global_scores = {m.name: max(m.metrics.sharpe_ratio, 0.0) for m in models}
            global_total = sum(global_scores.values())
            if global_total > 0:
                global_weights = {n: s / global_total for n, s in global_scores.items()}
            else:
                global_weights = {m.name: 1.0 / len(models) for m in models}

            blended = {}
            all_names = set(list(regime_weights.keys()) + list(global_weights.keys()))
            for name in all_names:
                rw = regime_weights.get(name, 0.0)
                gw = global_weights.get(name, 0.0)
                blended[name] = 0.7 * rw + 0.3 * gw

            total = sum(blended.values())
            if total > 0:
                blended = {n: w / total for n, w in blended.items()}

            decision = {
                "timestamp": datetime.utcnow().isoformat(),
                "regime": current_regime.value,
                "weights": blended,
                "source": "regime_blended",
            }
            self._decision_log.append(decision)
            return blended

        # Fallback: equal weights
        n = len(models)
        equal = {m.name: 1.0 / n for m in models}
        self._decision_log.append({
            "timestamp": datetime.utcnow().isoformat(),
            "regime": current_regime.value,
            "weights": equal,
            "source": "equal_fallback",
        })
        return equal

    def get_regime_summary(self) -> dict:
        """Summary of all learned regime-performance data."""
        summary = {}
        for regime, models in self._regime_performance.items():
            summary[regime] = {
                model: {
                    "observations": len(history),
                    "mean_sharpe": np.mean(history) if history else 0.0,
                    "latest_sharpe": history[-1] if history else 0.0,
                }
                for model, history in models.items()
            }
        return summary

    def get_decision_log(self, limit: int = 50) -> list[dict]:
        return self._decision_log[-limit:]

    # ── RL Scaffold ──────────────────────────────────────────────────────
    # Future: Replace compute_regime_weights with an RL policy that:
    # - State: regime features (vol, trend, correlation, macro indicators)
    # - Action: model weight vector
    # - Reward: portfolio sharpe / return over next period
    # - Algorithm: PPO or contextual bandit
    #
    # def train_rl_policy(self, experience_buffer):
    #     """Train RL agent on historical regime-allocation-reward tuples."""
    #     pass
    #
    # def rl_predict_weights(self, regime_features):
    #     """Use trained RL policy to predict optimal weights."""
    #     pass
