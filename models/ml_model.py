"""
Machine learning model using XGBoost and RandomForest.
Learns non-linear patterns from engineered features to predict next-period returns.
"""

import numpy as np
import pandas as pd
import structlog

from data.features import FeatureEngineer
from models.base import ModelBase, ModelMetrics, Signal

logger = structlog.get_logger(__name__)


class MLModel(ModelBase):
    """
    Supervised ML model that classifies next-period return direction.
    Supports XGBoost and RandomForest as the underlying estimator.
    """

    def __init__(
        self,
        name: str = "ml_xgboost_v1",
        estimator_type: str = "xgboost",
        prediction_horizon: int = 1,
        classification_threshold: float = 0.55,
    ):
        super().__init__(name=name)
        self.estimator_type = estimator_type
        self.prediction_horizon = prediction_horizon
        self.classification_threshold = classification_threshold
        self.feature_engineer = FeatureEngineer()
        self.feature_columns: list[str] = []
        self._model = None

    def _create_estimator(self):
        if self.estimator_type == "xgboost":
            from xgboost import XGBClassifier
            return XGBClassifier(
                n_estimators=200,
                max_depth=6,
                learning_rate=0.05,
                subsample=0.8,
                colsample_bytree=0.8,
                use_label_encoder=False,
                eval_metric="logloss",
                random_state=42,
            )
        elif self.estimator_type == "random_forest":
            from sklearn.ensemble import RandomForestClassifier
            return RandomForestClassifier(
                n_estimators=200,
                max_depth=10,
                min_samples_leaf=20,
                random_state=42,
                n_jobs=-1,
            )
        else:
            raise ValueError(f"Unknown estimator: {self.estimator_type}")

    def _prepare_labels(self, df: pd.DataFrame) -> pd.Series:
        """Binary label: 1 if future return > 0, else 0."""
        future_return = df["close"].pct_change(self.prediction_horizon).shift(-self.prediction_horizon)
        return (future_return > 0).astype(int)

    def train(self, df: pd.DataFrame, **kwargs) -> None:
        """Train the ML model on feature-engineered data."""
        featured = self.feature_engineer.build_feature_matrix(df)
        self.feature_columns = self.feature_engineer.get_feature_columns(featured)

        labels = self._prepare_labels(featured)
        # Drop rows where label is NaN (last `prediction_horizon` rows)
        valid_mask = labels.notna()
        X = featured.loc[valid_mask, self.feature_columns]
        y = labels[valid_mask]

        if len(X) < 50:
            logger.warning("insufficient_training_data", rows=len(X))
            return

        self._model = self._create_estimator()
        self._model.fit(X, y)
        self.is_trained = True
        self._artifact = self._model

        # Log feature importance
        if hasattr(self._model, "feature_importances_"):
            importance = dict(zip(self.feature_columns, self._model.feature_importances_))
            top_features = sorted(importance.items(), key=lambda x: x[1], reverse=True)[:10]
            logger.info("model_trained", name=self.name, top_features=top_features)

    def predict(self, df: pd.DataFrame) -> list[Signal]:
        """Generate trading signals based on ML predictions."""
        if not self.is_trained or self._model is None:
            return []

        featured = self.feature_engineer.build_feature_matrix(df)
        if len(featured) == 0:
            return []

        X = featured[self.feature_columns].iloc[[-1]]
        proba = self._model.predict_proba(X)[0]
        prob_up = proba[1] if len(proba) > 1 else proba[0]

        symbol = df["symbol"].iloc[0] if "symbol" in df.columns else "UNKNOWN"
        signals = []

        if prob_up > self.classification_threshold:
            strength = min(1.0, (prob_up - 0.5) * 2)
            signals.append(Signal(symbol=symbol, direction="long", strength=strength, model_name=self.name))
        elif prob_up < (1 - self.classification_threshold):
            strength = min(1.0, (0.5 - prob_up) * 2)
            signals.append(Signal(symbol=symbol, direction="short", strength=strength, model_name=self.name))

        return signals

    def evaluate(self, df: pd.DataFrame) -> ModelMetrics:
        """Evaluate on held-out data using simulated returns."""
        if not self.is_trained or self._model is None:
            return self.metrics

        featured = self.feature_engineer.build_feature_matrix(df)
        labels = self._prepare_labels(featured)
        valid_mask = labels.notna()
        X = featured.loc[valid_mask, self.feature_columns]

        if len(X) < 10:
            return self.metrics

        probas = self._model.predict_proba(X)
        prob_up = probas[:, 1] if probas.shape[1] > 1 else probas[:, 0]

        # Simulate returns: go long when prob > threshold, short when prob < (1-threshold)
        positions = pd.Series(0.0, index=X.index)
        positions[prob_up > self.classification_threshold] = 1.0
        positions[prob_up < (1 - self.classification_threshold)] = -1.0

        price_returns = featured.loc[valid_mask, "close"].pct_change().shift(-1)
        strategy_returns = (positions * price_returns).dropna()
        return self.update_metrics(strategy_returns)
