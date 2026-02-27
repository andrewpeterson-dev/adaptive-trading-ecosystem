"""
Ensemble Meta-Model.
Aggregates signals from all sub-models and learns optimal combination weights
per market regime.
"""

from datetime import datetime

import numpy as np
import pandas as pd
import structlog

from models.base import ModelBase, ModelMetrics, Signal

logger = structlog.get_logger(__name__)


class EnsembleMetaModel(ModelBase):
    """
    Meta-model that:
    1. Collects signals from all registered sub-models
    2. Weights them by rolling performance
    3. Optionally learns regime-specific weights
    4. Produces a final consensus signal
    """

    def __init__(self, name: str = "ensemble_meta_v1"):
        super().__init__(name=name)
        self.sub_models: list[ModelBase] = []
        self.model_weights: dict[str, float] = {}
        self.regime_weights: dict[str, dict[str, float]] = {}  # regime -> {model_name: weight}

    def register_model(self, model: ModelBase) -> None:
        """Add a sub-model to the ensemble."""
        self.sub_models.append(model)
        # Initialize with equal weight
        n = len(self.sub_models)
        self.model_weights = {m.name: 1.0 / n for m in self.sub_models}
        logger.info("model_registered", model=model.name, total_models=n)

    def train(self, df: pd.DataFrame, **kwargs) -> None:
        """
        Train all sub-models and compute initial weights from their performance.
        """
        for model in self.sub_models:
            if not model.is_trained:
                model.train(df, **kwargs)

        self._update_weights_from_performance()
        self.is_trained = True
        self._artifact = {"weights": self.model_weights}

    def predict(self, df: pd.DataFrame) -> list[Signal]:
        """
        Aggregate sub-model signals into a consensus signal.
        """
        if not self.sub_models:
            return []

        all_signals: dict[str, list[tuple[float, float]]] = {}  # symbol -> [(direction_score, weight)]

        for model in self.sub_models:
            weight = self.model_weights.get(model.name, 0.0)
            if weight <= 0:
                continue

            signals = model.predict(df)
            for sig in signals:
                direction_score = {
                    "long": sig.strength,
                    "short": -sig.strength,
                    "flat": 0.0,
                }.get(sig.direction, 0.0)

                if sig.symbol not in all_signals:
                    all_signals[sig.symbol] = []
                all_signals[sig.symbol].append((direction_score, weight))

        # Produce consensus
        consensus_signals = []
        for symbol, scored in all_signals.items():
            weighted_sum = sum(score * weight for score, weight in scored)
            total_weight = sum(weight for _, weight in scored)
            consensus = weighted_sum / total_weight if total_weight > 0 else 0.0

            if abs(consensus) < 0.1:
                continue

            direction = "long" if consensus > 0 else "short"
            strength = min(1.0, abs(consensus))
            consensus_signals.append(Signal(
                symbol=symbol,
                direction=direction,
                strength=strength,
                model_name=self.name,
                metadata={"contributing_models": len(scored), "raw_consensus": consensus},
            ))

        return consensus_signals

    def evaluate(self, df: pd.DataFrame) -> ModelMetrics:
        """Evaluate ensemble by simulating consensus signals on held-out data."""
        # Evaluate each sub-model first
        for model in self.sub_models:
            model.evaluate(df)

        self._update_weights_from_performance()

        # Simulate ensemble returns
        returns_list = []
        for model in self.sub_models:
            weight = self.model_weights.get(model.name, 0.0)
            if weight > 0 and model.metrics.num_trades > 0:
                # Approximate: weight * model's avg return * num_trades
                model_contribution = weight * model.metrics.total_return
                returns_list.append(model_contribution)

        if returns_list:
            ensemble_return = sum(returns_list)
            # Construct a synthetic return series for metric computation
            synthetic = pd.Series([ensemble_return / 20] * 20)
            return self.update_metrics(synthetic)

        return self.metrics

    def _update_weights_from_performance(self) -> None:
        """Rebalance model weights based on rolling Sharpe ratio."""
        sharpe_scores = {}
        for model in self.sub_models:
            sharpe = max(model.metrics.sharpe_ratio, 0.0)  # Floor at 0
            sharpe_scores[model.name] = sharpe

        total = sum(sharpe_scores.values())
        if total > 0:
            self.model_weights = {name: score / total for name, score in sharpe_scores.items()}
        else:
            n = len(self.sub_models)
            self.model_weights = {m.name: 1.0 / n for m in self.sub_models}

        logger.info("weights_updated", weights=self.model_weights)

    def update_regime_weights(self, regime: str, performance_data: dict[str, float]) -> None:
        """
        Store regime-specific weights. Called by the regime detection system.
        performance_data: {model_name: sharpe_ratio_in_this_regime}
        """
        total = sum(max(v, 0) for v in performance_data.values())
        if total > 0:
            self.regime_weights[regime] = {
                name: max(v, 0) / total for name, v in performance_data.items()
            }
        logger.info("regime_weights_updated", regime=regime, weights=self.regime_weights.get(regime))

    def apply_regime(self, regime: str) -> None:
        """Switch to regime-specific weights if available."""
        if regime in self.regime_weights:
            self.model_weights = self.regime_weights[regime]
            logger.info("regime_applied", regime=regime, weights=self.model_weights)

    def get_model_status(self) -> list[dict]:
        """Summary of all sub-models and their current weights."""
        return [
            {
                "name": model.name,
                "weight": self.model_weights.get(model.name, 0.0),
                "sharpe": model.metrics.sharpe_ratio,
                "win_rate": model.metrics.win_rate,
                "max_drawdown": model.metrics.max_drawdown,
                "is_trained": model.is_trained,
            }
            for model in self.sub_models
        ]
