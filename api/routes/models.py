"""
Model management endpoints — list models, view performance, trigger retraining.
"""

from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from allocation.capital import CapitalAllocator
from data.ingestion import DataIngestor
from intelligence.regime import RegimeDetector
from intelligence.retrainer import ModelRetrainer
from intelligence.meta import MetaLearner
from models.ensemble import EnsembleMetaModel
from models.registry import create_default_models

router = APIRouter()

# Shared instances
_models = create_default_models()
_ensemble = EnsembleMetaModel()
for m in _models:
    _ensemble.register_model(m)

_allocator = CapitalAllocator()
_retrainer = ModelRetrainer()
_regime_detector = RegimeDetector()
_meta_learner = MetaLearner()


class RetrainRequest(BaseModel):
    model_name: str = ""  # Empty = retrain all
    symbols: list[str] = ["SPY"]
    lookback_days: int = 252
    force: bool = False


class AllocateRequest(BaseModel):
    total_capital: float = 100000.0


@router.get("/list")
async def list_models():
    """List all registered models with their current status."""
    return [
        {
            "name": m.name,
            "type": m.__class__.__name__,
            "version": m.version,
            "is_trained": m.is_trained,
            "metrics": m.metrics.to_dict(),
        }
        for m in _models
    ]


@router.get("/ensemble-status")
async def ensemble_status():
    """Get ensemble model status including sub-model weights."""
    return {
        "models": _ensemble.get_model_status(),
        "weights": _ensemble.model_weights,
        "regime_weights": _ensemble.regime_weights,
    }


@router.post("/retrain")
async def retrain_models(req: RetrainRequest):
    """Trigger model retraining with walk-forward validation."""
    ingestor = DataIngestor()

    try:
        df = ingestor.fetch_and_cache(req.symbols[0], lookback_days=req.lookback_days)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Data fetch failed: {str(e)}")

    if req.model_name:
        # Retrain specific model
        target = next((m for m in _models if m.name == req.model_name), None)
        if not target:
            raise HTTPException(status_code=404, detail=f"Model not found: {req.model_name}")
        success, metrics = _retrainer.retrain_model(target, df)
        return {"model": req.model_name, "retrained": success, "metrics": metrics.to_dict()}
    else:
        # Retrain all
        results = _retrainer.retrain_all(_models, df, force=req.force)
        return {"results": results}


@router.post("/allocate")
async def allocate_capital(req: AllocateRequest):
    """Compute and apply capital allocation across models."""
    _allocator.total_capital = req.total_capital
    weights = _allocator.compute_weights(_models)
    return _allocator.get_allocation_summary()


@router.get("/allocation")
async def get_allocation():
    """Get current capital allocation."""
    return _allocator.get_allocation_summary()


@router.get("/allocation-history")
async def get_allocation_history(limit: int = 50):
    """Get capital allocation history."""
    return _allocator.get_history(limit=limit)


@router.get("/regime")
async def get_current_regime(symbol: str = "SPY"):
    """Detect current market regime."""
    ingestor = DataIngestor()
    try:
        df = ingestor.fetch_and_cache(symbol, lookback_days=120)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Data fetch failed: {str(e)}")

    regime = _regime_detector.detect(df)
    return regime


@router.get("/regime-history")
async def get_regime_history(limit: int = 50):
    """Get regime detection history."""
    return _regime_detector.get_regime_history(limit=limit)


@router.get("/meta-summary")
async def get_meta_summary():
    """Get meta-learner summary of model effectiveness per regime."""
    return _meta_learner.get_regime_summary()


@router.get("/retrain-log")
async def get_retrain_log(limit: int = 50):
    """Get model retraining history."""
    return _retrainer.get_retrain_log(limit=limit)


@router.get("/performance/{model_name}")
async def get_model_performance(model_name: str):
    """Get detailed performance for a specific model."""
    model = next((m for m in _models if m.name == model_name), None)
    if not model:
        raise HTTPException(status_code=404, detail=f"Model not found: {model_name}")
    return {
        "name": model.name,
        "type": model.__class__.__name__,
        "is_trained": model.is_trained,
        "metrics": model.metrics.to_dict(),
        "trade_log": model.get_trade_log()[-20:],
    }
