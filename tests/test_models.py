"""
Tests for trading model implementations.
Validates training, prediction, evaluation, and serialization.
"""

import numpy as np
import pandas as pd
import pytest

from models.momentum import MomentumModel
from models.mean_reversion import MeanReversionModel
from models.volatility import VolatilityModel
from models.ensemble import EnsembleMetaModel
from models.base import ModelMetrics

try:
    from models.ml_model import MLModel
    import importlib
    importlib.import_module("xgboost")
    HAS_XGBOOST = True
except Exception:
    HAS_XGBOOST = False
    MLModel = None


def _make_sample_data(n: int = 300, trend: float = 0.0005) -> pd.DataFrame:
    """Generate synthetic OHLCV data for testing."""
    np.random.seed(42)
    dates = pd.date_range("2023-01-01", periods=n, freq="D")
    close = 100 * np.exp(np.cumsum(np.random.normal(trend, 0.015, n)))
    high = close * (1 + np.random.uniform(0, 0.02, n))
    low = close * (1 - np.random.uniform(0, 0.02, n))
    open_ = close * (1 + np.random.normal(0, 0.005, n))
    volume = np.random.randint(1_000_000, 10_000_000, n)

    return pd.DataFrame({
        "timestamp": dates,
        "symbol": "TEST",
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    })


class TestMomentumModel:
    def test_train(self):
        model = MomentumModel()
        df = _make_sample_data()
        model.train(df)
        assert model.is_trained

    def test_predict_returns_signals(self):
        model = MomentumModel()
        df = _make_sample_data()
        model.train(df)
        signals = model.predict(df)
        # May or may not generate a signal depending on data
        assert isinstance(signals, list)

    def test_evaluate_returns_metrics(self):
        model = MomentumModel()
        df = _make_sample_data()
        model.train(df)
        metrics = model.evaluate(df)
        assert isinstance(metrics, ModelMetrics)
        assert metrics.num_trades > 0

    def test_save_load(self, tmp_path):
        model = MomentumModel()
        df = _make_sample_data()
        model.train(df)
        path = model.save(str(tmp_path))
        assert path.endswith(".joblib")

        new_model = MomentumModel()
        new_model.load(path)
        assert new_model.is_trained


class TestMeanReversionModel:
    def test_train_and_evaluate(self):
        model = MeanReversionModel()
        df = _make_sample_data(trend=0.0)  # Sideways for mean reversion
        model.train(df)
        assert model.is_trained
        metrics = model.evaluate(df)
        assert isinstance(metrics, ModelMetrics)


class TestVolatilityModel:
    def test_train_and_predict(self):
        model = VolatilityModel()
        df = _make_sample_data()
        model.train(df)
        assert model.is_trained
        signals = model.predict(df)
        assert isinstance(signals, list)


@pytest.mark.skipif(not HAS_XGBOOST, reason="xgboost/libomp not available")
class TestMLModel:
    def test_xgboost_train(self):
        model = MLModel(estimator_type="xgboost")
        df = _make_sample_data()
        model.train(df)
        assert model.is_trained
        assert len(model.feature_columns) > 0

    def test_random_forest_train(self):
        model = MLModel(name="rf", estimator_type="random_forest")
        df = _make_sample_data()
        model.train(df)
        assert model.is_trained

    def test_predict_after_train(self):
        model = MLModel(estimator_type="xgboost")
        df = _make_sample_data()
        model.train(df)
        signals = model.predict(df)
        assert isinstance(signals, list)

    def test_evaluate(self):
        model = MLModel(estimator_type="xgboost")
        df = _make_sample_data()
        model.train(df)
        metrics = model.evaluate(df)
        assert metrics.num_trades >= 0


class TestEnsembleMetaModel:
    def test_register_and_predict(self):
        ensemble = EnsembleMetaModel()
        m1 = MomentumModel(name="m1")
        m2 = MeanReversionModel(name="m2")
        ensemble.register_model(m1)
        ensemble.register_model(m2)
        assert len(ensemble.sub_models) == 2

    def test_train_ensemble(self):
        ensemble = EnsembleMetaModel()
        ensemble.register_model(MomentumModel(name="m1"))
        ensemble.register_model(MeanReversionModel(name="m2"))
        df = _make_sample_data()
        ensemble.train(df)
        assert ensemble.is_trained

    def test_weights_update(self):
        ensemble = EnsembleMetaModel()
        m1 = MomentumModel(name="m1")
        m2 = MeanReversionModel(name="m2")
        # Simulate different performance
        m1.metrics.sharpe_ratio = 1.5
        m2.metrics.sharpe_ratio = 0.5
        ensemble.register_model(m1)
        ensemble.register_model(m2)
        ensemble._update_weights_from_performance()
        assert ensemble.model_weights["m1"] > ensemble.model_weights["m2"]
