from models.base import ModelBase, ModelMetrics, Signal
from models.momentum import MomentumModel
from models.mean_reversion import MeanReversionModel
from models.volatility import VolatilityModel
from models.ensemble import EnsembleMetaModel
from models.breakout import BreakoutModel
from models.iv_crush import IVCrushModel
from models.earnings import EarningsMomentumModel
from models.pairs import PairsModel
from models.registry import create_default_models, get_model_class, list_model_classes


def __getattr__(name):
    if name == "MLModel":
        from models.ml_model import MLModel
        return MLModel
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "ModelBase", "ModelMetrics", "Signal",
    "MomentumModel", "MeanReversionModel", "VolatilityModel",
    "MLModel", "EnsembleMetaModel",
    "BreakoutModel", "IVCrushModel", "EarningsMomentumModel", "PairsModel",
    "create_default_models", "get_model_class", "list_model_classes",
]
