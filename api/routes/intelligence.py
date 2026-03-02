"""
Intelligence endpoints — LLM analysis, confidence model, ensemble state,
decision pipeline evaluation, and model accuracy.
"""

import re
import time
from typing import Optional

import structlog
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from config.settings import get_settings
from intelligence.confidence_model import ConfidenceModel
from intelligence.decision_pipeline import DecisionPipeline
from intelligence.ensemble_engine import EnsembleEngine
from intelligence.llm_analyst import LLMAnalyst
from intelligence.llm_router import LLMRouter
from models.base import Signal

logger = structlog.get_logger(__name__)

router = APIRouter()

# Lazy singletons
_llm_router: Optional[LLMRouter] = None
_llm_analyst: Optional[LLMAnalyst] = None
_confidence_model: Optional[ConfidenceModel] = None
_ensemble_engine: Optional[EnsembleEngine] = None
_decision_pipeline: Optional[DecisionPipeline] = None


def _get_llm_router() -> LLMRouter:
    global _llm_router
    if _llm_router is None:
        _llm_router = LLMRouter()
    return _llm_router


def _get_llm_analyst() -> LLMAnalyst:
    global _llm_analyst
    if _llm_analyst is None:
        _llm_analyst = LLMAnalyst()
    return _llm_analyst


def _get_confidence_model() -> ConfidenceModel:
    global _confidence_model
    if _confidence_model is None:
        _confidence_model = ConfidenceModel()
    return _confidence_model


def _get_ensemble_engine() -> EnsembleEngine:
    global _ensemble_engine
    if _ensemble_engine is None:
        _ensemble_engine = EnsembleEngine()
    return _ensemble_engine


def _get_decision_pipeline() -> DecisionPipeline:
    global _decision_pipeline
    if _decision_pipeline is None:
        _decision_pipeline = DecisionPipeline(
            confidence_model=_get_confidence_model(),
            ensemble_engine=_get_ensemble_engine(),
        )
    return _decision_pipeline


# --------------- Request / Response Models ---------------


class AnalyzeRequest(BaseModel):
    symbol: str
    context: Optional[str] = None


class EvaluateRequest(BaseModel):
    symbol: str
    direction: str = Field(..., description="long, short, or flat")
    confidence: float = Field(..., ge=0, le=100)
    model_name: str = "manual"


# --------------- Endpoints ---------------


@router.post("/analyze")
async def analyze_symbol(req: AnalyzeRequest):
    """Run LLM advisory analysis for a symbol via the LLM router."""
    llm_router = _get_llm_router()

    prompt = (
        f"Analyze the current market conditions and outlook for {req.symbol}. "
        f"Provide a concise assessment including direction bias (long/short/neutral), "
        f"confidence level (0-100), key factors, and risk level."
    )
    if req.context:
        prompt += f"\n\nAdditional context: {req.context}"

    start = time.monotonic()
    try:
        result = await llm_router.route(prompt=prompt)
    except Exception as e:
        logger.error("intelligence_analyze_failed", symbol=req.symbol, error=str(e))
        raise HTTPException(status_code=503, detail=f"LLM unavailable: {str(e)}")

    latency_ms = round((time.monotonic() - start) * 1000, 1)
    response_text = result.get("response", "")

    # Parse a simple direction from the response text
    lower = response_text.lower()
    if "long" in lower or "bullish" in lower:
        direction = "long"
    elif "short" in lower or "bearish" in lower:
        direction = "short"
    else:
        direction = "neutral"

    # Estimate a confidence score from the response
    confidence_score = 50.0  # default
    match = re.search(r"confidence[:\s]*(\d+)", lower)
    if match:
        confidence_score = min(100.0, max(0.0, float(match.group(1))))

    return {
        "symbol": req.symbol,
        "analysis": response_text,
        "confidence_score": confidence_score,
        "direction": direction,
        "backend_used": result.get("backend", "unknown"),
        "latency_ms": latency_ms,
    }


@router.get("/confidence")
async def get_confidence_state(symbol: Optional[str] = Query(None)):
    """Return current confidence model configuration and state."""
    cm = _get_confidence_model()
    settings = get_settings()

    return {
        "default_threshold": cm.min_confidence,
        "weights": {
            "llm": cm.llm_weight,
            "model": cm.model_weight,
            "track_record": cm.track_record_weight,
        },
        "regime_adjustments": {
            "high_vol_bear": -10.0,
            "high_vol_bull": -5.0,
            "sideways": -3.0,
        },
        "recent_history_count": len(cm.get_history()),
        "llm_provider": settings.llm_provider,
    }


@router.get("/ensemble")
async def get_ensemble_state(symbol: str = Query(..., description="Ticker symbol")):
    """Get latest ensemble aggregation state for a symbol."""
    engine = _get_ensemble_engine()

    # Filter prediction log for this symbol
    log = engine.get_prediction_log(limit=200)
    symbol_preds = [
        entry for entry in log
        if entry.get("symbol", "").upper() == symbol.upper()
    ]

    if not symbol_preds:
        return {
            "symbol": symbol,
            "consensus_direction": None,
            "weighted_confidence": 0.0,
            "agreement_ratio": 0.0,
            "blocked": True,
            "model_predictions": [],
            "message": "No predictions logged for this symbol yet",
        }

    # Build predictions list from logged entries
    predictions = []
    for entry in symbol_preds[-20:]:  # last 20 entries
        pred = entry.get("prediction", {})
        predictions.append({
            "model": entry.get("model_name", "unknown"),
            "symbol": symbol.upper(),
            "direction": pred.get("direction", "flat"),
            "confidence": pred.get("confidence", 0),
        })

    result = engine.aggregate_predictions(predictions)
    result["symbol"] = symbol.upper()
    return result


@router.post("/evaluate")
async def evaluate_signal(req: EvaluateRequest):
    """Run a signal through the full DecisionPipeline."""
    pipeline = _get_decision_pipeline()

    signal = Signal(
        symbol=req.symbol,
        direction=req.direction,
        strength=req.confidence / 100.0,
        model_name=req.model_name,
    )

    # Build a minimal prediction list for the ensemble stage
    all_model_predictions = [
        {
            "model": req.model_name,
            "symbol": req.symbol,
            "direction": req.direction,
            "confidence": req.confidence,
        }
    ]

    # Use neutral defaults for metrics and regime since this is an API evaluation
    model_metrics = {
        "sharpe_ratio": 0.0,
        "win_rate": 0.5,
        "max_drawdown": 0.0,
    }

    try:
        decision = pipeline.evaluate(
            signal=signal,
            llm_confidence=req.confidence,
            model_metrics=model_metrics,
            regime="sideways",
            all_model_predictions=all_model_predictions,
        )
    except Exception as e:
        logger.error("pipeline_evaluate_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Pipeline error: {str(e)}")

    return {
        "approved": decision["approved"],
        "rejection_stage": decision.get("rejection_stage"),
        "rejection_reason": decision.get("rejection_reason"),
        "final_confidence": decision["confidence_result"]["overall_confidence"],
        "consensus": decision.get("ensemble_result"),
    }


@router.get("/model-accuracy")
async def get_model_accuracy(
    model_name: Optional[str] = Query(None),
    window: int = Query(50, ge=1, le=500),
):
    """Get model prediction accuracy from EnsembleEngine logs."""
    engine = _get_ensemble_engine()

    if model_name:
        return engine.get_model_accuracy(model_name, window=window)

    return {
        "window": window,
        "models": engine.get_all_model_accuracies(window=window),
    }
