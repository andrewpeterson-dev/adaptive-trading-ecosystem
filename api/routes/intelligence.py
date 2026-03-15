"""
Intelligence endpoints — LLM analysis, confidence model, ensemble state,
decision pipeline evaluation, and model accuracy.
"""

import json
import time
from typing import Literal, Optional

import structlog
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

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


class AnalyzeResponsePayload(BaseModel):
    direction: Literal["long", "short", "neutral"]
    confidence_score: float = Field(..., ge=0, le=100)
    analysis: str = Field(..., min_length=1, max_length=4000)
    risk_level: Literal["low", "medium", "high"]
    key_factors: list[str] = Field(default_factory=list, max_length=6)

    @field_validator("analysis")
    @classmethod
    def _normalize_analysis(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("analysis is required")
        return normalized

    @field_validator("key_factors", mode="before")
    @classmethod
    def _normalize_key_factors(cls, value) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError("key_factors must be a list")
        normalized = [str(item).strip() for item in value if str(item).strip()]
        return normalized[:6]


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
        "Analyze the symbol and respond with JSON only. "
        'Return exactly this schema: {"direction":"long|short|neutral","confidence_score":0-100,'
        '"analysis":"brief summary","risk_level":"low|medium|high","key_factors":["factor 1"]}. '
        f"Analyze the current market conditions and outlook for {req.symbol}."
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
    response_text = str(result.get("response", "")).strip()
    if response_text.startswith("```"):
        response_text = response_text.strip("`")
        if response_text.lower().startswith("json"):
            response_text = response_text[4:].strip()

    try:
        payload = AnalyzeResponsePayload.model_validate(json.loads(response_text))
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning(
            "intelligence_analyze_invalid_payload",
            symbol=req.symbol,
            backend=result.get("backend", "unknown"),
            error=str(exc),
        )
        raise HTTPException(
            status_code=502,
            detail="LLM returned an invalid analysis payload",
        ) from exc

    return {
        "symbol": req.symbol,
        "analysis": payload.analysis,
        "confidence_score": payload.confidence_score,
        "direction": payload.direction,
        "risk_level": payload.risk_level,
        "key_factors": payload.key_factors,
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
