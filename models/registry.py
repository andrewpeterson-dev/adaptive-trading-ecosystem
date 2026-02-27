"""
Model registry — central catalog for discovering, loading, and managing trading models.
New models are registered here and automatically become available to the ensemble.
"""

from typing import Type

import structlog

from models.base import ModelBase

logger = structlog.get_logger(__name__)

# Global model class registry
_MODEL_CLASSES: dict[str, Type[ModelBase]] = {}


def register_model_class(cls: Type[ModelBase]) -> Type[ModelBase]:
    """Decorator to register a model class."""
    key = cls.__name__
    _MODEL_CLASSES[key] = cls
    logger.info("model_class_registered", class_name=key)
    return cls


def get_model_class(name: str) -> Type[ModelBase]:
    """Retrieve a registered model class by name."""
    _ensure_registered()
    if name not in _MODEL_CLASSES:
        raise KeyError(f"Model class '{name}' not found. Available: {list(_MODEL_CLASSES.keys())}")
    return _MODEL_CLASSES[name]


def list_model_classes() -> dict[str, Type[ModelBase]]:
    """Return all registered model classes."""
    _ensure_registered()
    return dict(_MODEL_CLASSES)


def create_default_models() -> list[ModelBase]:
    """Instantiate the standard model set with default parameters."""
    from models.momentum import MomentumModel
    from models.mean_reversion import MeanReversionModel
    from models.volatility import VolatilityModel
    from models.breakout import BreakoutModel
    from models.iv_crush import IVCrushModel
    from models.earnings import EarningsMomentumModel
    from models.pairs import PairsModel

    models = [
        MomentumModel(name="momentum_fast", fast_window=5, slow_window=20),
        MomentumModel(name="momentum_slow", fast_window=20, slow_window=100),
        MeanReversionModel(name="mean_reversion_tight", lookback=15, entry_z=1.5),
        MeanReversionModel(name="mean_reversion_wide", lookback=30, entry_z=2.2),
        VolatilityModel(name="volatility_squeeze"),
        BreakoutModel(name="breakout_sr"),
        IVCrushModel(name="iv_crush"),
        EarningsMomentumModel(name="earnings_momentum"),
        PairsModel(name="pairs_statarb"),
    ]

    try:
        from models.ml_model import MLModel
        models.append(MLModel(name="ml_xgboost", estimator_type="xgboost"))
        models.append(MLModel(name="ml_random_forest", estimator_type="random_forest"))
    except Exception:
        logger.warning("ml_models_skipped", reason="xgboost/sklearn unavailable")

    return models


# Auto-register built-in model classes (lazy — deferred until first access)
_registered = False


def _ensure_registered():
    global _registered
    if _registered:
        return
    _registered = True

    from models.momentum import MomentumModel
    from models.mean_reversion import MeanReversionModel
    from models.volatility import VolatilityModel
    from models.ensemble import EnsembleMetaModel
    from models.breakout import BreakoutModel
    from models.iv_crush import IVCrushModel
    from models.earnings import EarningsMomentumModel
    from models.pairs import PairsModel

    for cls in [MomentumModel, MeanReversionModel, VolatilityModel, EnsembleMetaModel,
                BreakoutModel, IVCrushModel, EarningsMomentumModel, PairsModel]:
        register_model_class(cls)

    # ML model — optional (requires xgboost)
    try:
        from models.ml_model import MLModel
        register_model_class(MLModel)
    except ImportError:
        logger.warning("ml_model_unavailable", reason="xgboost not installed")
