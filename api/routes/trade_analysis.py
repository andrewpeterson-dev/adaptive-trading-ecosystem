"""API routes for multi-agent trade analysis."""

from __future__ import annotations

from typing import Optional

import structlog
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

logger = structlog.get_logger(__name__)
router = APIRouter()


class TradeAnalysisRequest(BaseModel):
    """Request body for POST /api/trade-analysis."""

    symbol: str = Field(min_length=1, max_length=10)
    action: str = Field(default="buy")
    size: float = Field(default=0, ge=0)

    @field_validator("symbol", mode="before")
    @classmethod
    def normalize_symbol(cls, v: str) -> str:
        return str(v).strip().upper()

    @field_validator("action", mode="before")
    @classmethod
    def normalize_action(cls, v: str) -> str:
        normalized = str(v).strip().lower()
        if normalized not in {"buy", "sell"}:
            raise ValueError("action must be 'buy' or 'sell'")
        return normalized


@router.post("")
async def run_analysis(request: Request, body: TradeAnalysisRequest):
    """Run the multi-agent trade analysis pipeline.

    Executes a 7-agent analysis covering technical, fundamental, and
    sentiment analysis, followed by bull/bear argumentation, risk
    assessment, and a final recommendation with confidence score.

    Typical runtime: 30-90 seconds.
    """
    user_id = request.state.user_id
    logger.info(
        "trade_analysis_api_request",
        user_id=user_id,
        symbol=body.symbol,
        action=body.action,
        size=body.size,
    )

    try:
        from services.ai_core.multi_agent.runner import run_trade_analysis

        result = await run_trade_analysis(
            symbol=body.symbol,
            action=body.action,
            size=body.size,
            user_id=user_id,
        )
    except Exception as exc:
        logger.error("trade_analysis_api_error", error=str(exc))
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}") from exc

    return result.to_dict()


@router.get("/{analysis_id}")
async def get_analysis(request: Request, analysis_id: str):
    """Retrieve a past trade analysis by ID."""
    user_id = request.state.user_id

    from services.ai_core.multi_agent.runner import get_analysis_by_id

    result = await get_analysis_by_id(analysis_id, user_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Analysis not found")

    return result.to_dict()
