"""
Scheduled model retraining system.
Handles walk-forward validation, performance decay detection, and automatic retraining.
"""

from datetime import datetime, timedelta

import pandas as pd
import structlog

from config.settings import get_settings
from data.ingestion import DataIngestor
from data.features import FeatureEngineer
from models.base import ModelBase, ModelMetrics

logger = structlog.get_logger(__name__)


class ModelRetrainer:
    """
    Manages the retraining lifecycle:
    1. Detects performance decay
    2. Fetches fresh data
    3. Runs walk-forward validation
    4. Retrains if performance improves
    5. Swaps in the new model version
    """

    def __init__(self):
        settings = get_settings()
        self.retrain_interval_hours = settings.retrain_interval_hours
        self.walk_forward_days = settings.walk_forward_window_days
        self.decay_threshold = settings.performance_decay_threshold
        self.ingestor = DataIngestor()
        self.feature_engineer = FeatureEngineer()
        self._last_retrain: dict[str, datetime] = {}
        self._retrain_log: list[dict] = []

    def needs_retrain(self, model: ModelBase) -> bool:
        """Check if a model needs retraining based on time and performance decay."""
        # Time-based check
        last = self._last_retrain.get(model.name)
        if last is None or (datetime.utcnow() - last) > timedelta(hours=self.retrain_interval_hours):
            return True

        # Performance decay check
        if model.metrics.sharpe_ratio < self.decay_threshold:
            logger.warning("performance_decay", model=model.name, sharpe=model.metrics.sharpe_ratio)
            return True

        return False

    def retrain_model(
        self,
        model: ModelBase,
        df: pd.DataFrame,
        train_window: int = 200,
        test_window: int = 20,
    ) -> tuple[bool, ModelMetrics]:
        """
        Retrain a model using walk-forward validation.
        Returns (success, new_metrics).
        """
        # Store pre-retrain metrics for comparison
        old_metrics = ModelMetrics(
            sharpe_ratio=model.metrics.sharpe_ratio,
            win_rate=model.metrics.win_rate,
            max_drawdown=model.metrics.max_drawdown,
        )

        # Walk-forward splits
        splits = self.ingestor.prepare_walk_forward_splits(df, train_window, test_window)
        if not splits:
            logger.warning("no_wf_splits", model=model.name)
            return False, model.metrics

        # Train on all splits, evaluate on last test fold
        all_test_metrics = []
        for train_df, test_df in splits:
            model.train(train_df)
            metrics = model.evaluate(test_df)
            all_test_metrics.append(metrics)

        # Final evaluation: use last fold's metrics
        final_metrics = all_test_metrics[-1] if all_test_metrics else model.metrics

        # Accept retrain if performance improved or is acceptable
        improved = final_metrics.sharpe_ratio >= old_metrics.sharpe_ratio * 0.9  # Allow 10% tolerance

        self._last_retrain[model.name] = datetime.utcnow()
        self._retrain_log.append({
            "model": model.name,
            "timestamp": datetime.utcnow().isoformat(),
            "old_sharpe": old_metrics.sharpe_ratio,
            "new_sharpe": final_metrics.sharpe_ratio,
            "accepted": improved,
            "num_folds": len(splits),
        })

        if improved:
            logger.info(
                "retrain_accepted",
                model=model.name,
                old_sharpe=old_metrics.sharpe_ratio,
                new_sharpe=final_metrics.sharpe_ratio,
            )
        else:
            logger.warning(
                "retrain_rejected",
                model=model.name,
                old_sharpe=old_metrics.sharpe_ratio,
                new_sharpe=final_metrics.sharpe_ratio,
            )

        return improved, final_metrics

    def retrain_all(
        self,
        models: list[ModelBase],
        df: pd.DataFrame,
        force: bool = False,
    ) -> dict[str, bool]:
        """Retrain all models that need it. Returns {model_name: retrained}."""
        results = {}
        for model in models:
            if force or self.needs_retrain(model):
                success, _ = self.retrain_model(model, df)
                results[model.name] = success
            else:
                results[model.name] = False
        return results

    def get_retrain_log(self, limit: int = 50) -> list[dict]:
        return self._retrain_log[-limit:]
