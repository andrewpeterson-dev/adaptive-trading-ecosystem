"""Entry point for running the multi-agent trade analysis pipeline."""

from __future__ import annotations

import asyncio
import time
import uuid
from datetime import datetime
from typing import Optional

import structlog

from services.ai_core.multi_agent.state import TradeAnalysisResult, TradeAnalysisState

logger = structlog.get_logger(__name__)


async def run_trade_analysis(
    symbol: str,
    action: str,
    size: float,
    user_id: int,
    model_override: str = "",
    skip_nodes: list[str] | None = None,
    trading_thesis: str = "",
    macro_data: dict | None = None,
    portfolio_data: dict | None = None,
) -> TradeAnalysisResult:
    """Run the full multi-agent analysis pipeline.

    Args:
        symbol: Ticker symbol (e.g. AAPL).
        action: Proposed action - "buy" or "sell".
        size: Proposed position size (shares/contracts).
        user_id: Authenticated user ID (used for tool access).

    Returns:
        ``TradeAnalysisResult`` containing all reports, the final
        recommendation, confidence score, and audit trail.
    """
    analysis_id = str(uuid.uuid4())
    start = time.monotonic()

    logger.info(
        "trade_analysis_started",
        analysis_id=analysis_id,
        symbol=symbol,
        action=action,
        size=size,
        user_id=user_id,
    )

    # Fetch current price for context
    current_price = 0.0
    try:
        from data.market_data import market_data

        quote = await market_data.get_quote(symbol)
        if quote and quote.get("price") is not None:
            current_price = float(quote["price"])
    except Exception as exc:
        logger.warning("trade_analysis_price_fetch_failed", symbol=symbol, error=str(exc))

    # Build initial state
    initial_state: TradeAnalysisState = {
        "symbol": symbol.upper(),
        "current_price": current_price,
        "proposed_action": action.lower(),
        "proposed_size": size,
        "user_id": user_id,
        "technical_report": "",
        "fundamental_report": "",
        "sentiment_report": "",
        "bull_case": "",
        "bear_case": "",
        "risk_assessment": "",
        "recommendation": "hold",
        "confidence": 0.0,
        "reasoning": "",
        "trading_thesis": trading_thesis,
        "model_override": model_override,
        "skip_nodes": skip_nodes or [],
        "macro_data": macro_data or {},
        "portfolio_data": portfolio_data or {},
        "node_trace": [],
        "errors": [],
    }

    # Run the graph
    try:
        from services.ai_core.multi_agent.graph import get_trade_analysis_graph

        graph = get_trade_analysis_graph()
        final_state = await asyncio.wait_for(
            graph.ainvoke(initial_state),
            timeout=120.0,
        )
    except asyncio.TimeoutError:
        logger.error(
            "trade_analysis_graph_timeout",
            analysis_id=analysis_id,
            symbol=symbol,
        )
        final_state = dict(initial_state)
        final_state["recommendation"] = "hold"
        final_state["confidence"] = 0.0
        final_state["reasoning"] = "Analysis pipeline timed out after 120 seconds."
        final_state.setdefault("errors", []).append("graph_execution: timeout after 120s")
    except Exception as exc:
        logger.error(
            "trade_analysis_graph_failed",
            analysis_id=analysis_id,
            error=str(exc),
        )
        final_state = dict(initial_state)
        final_state["recommendation"] = "hold"
        final_state["confidence"] = 0.0
        final_state["reasoning"] = f"Analysis pipeline failed: {exc}"
        final_state.setdefault("errors", []).append(f"graph_execution: {exc}")

    elapsed = round(time.monotonic() - start, 2)
    logger.info(
        "trade_analysis_completed",
        analysis_id=analysis_id,
        symbol=symbol,
        recommendation=final_state.get("recommendation"),
        confidence=final_state.get("confidence"),
        elapsed_seconds=elapsed,
        node_count=len(final_state.get("node_trace", [])),
        error_count=len(final_state.get("errors", [])),
    )

    # Build result
    result = TradeAnalysisResult(
        analysis_id=analysis_id,
        symbol=final_state.get("symbol", symbol.upper()),
        action=action,
        proposed_size=size,
        current_price=final_state.get("current_price", current_price),
        technical_report=final_state.get("technical_report", ""),
        fundamental_report=final_state.get("fundamental_report", ""),
        sentiment_report=final_state.get("sentiment_report", ""),
        bull_case=final_state.get("bull_case", ""),
        bear_case=final_state.get("bear_case", ""),
        risk_assessment=final_state.get("risk_assessment", ""),
        recommendation=final_state.get("recommendation", "hold"),
        confidence=final_state.get("confidence", 0.0),
        reasoning=final_state.get("reasoning", ""),
        node_trace=final_state.get("node_trace", []),
        errors=final_state.get("errors", []),
    )

    # Persist to DB
    await _persist_analysis(result, user_id)

    return result


async def _persist_analysis(result: TradeAnalysisResult, user_id: int) -> None:
    """Persist the analysis result to the database."""
    try:
        from db.database import get_session
        from db.cerberus_models import TradeAnalysis

        async with get_session() as session:
            record = TradeAnalysis(
                id=result.analysis_id,
                user_id=user_id,
                symbol=result.symbol,
                action=result.action,
                proposed_size=result.proposed_size,
                current_price=result.current_price,
                technical_report=result.technical_report,
                fundamental_report=result.fundamental_report,
                sentiment_report=result.sentiment_report,
                bull_case=result.bull_case,
                bear_case=result.bear_case,
                risk_assessment=result.risk_assessment,
                recommendation=result.recommendation,
                confidence=result.confidence,
                reasoning=result.reasoning,
                node_trace=result.node_trace,
                errors=result.errors,
            )
            session.add(record)

        logger.info("trade_analysis_persisted", analysis_id=result.analysis_id)

    except Exception as exc:
        logger.error(
            "trade_analysis_persist_failed",
            analysis_id=result.analysis_id,
            error=str(exc),
        )


async def get_analysis_by_id(analysis_id: str, user_id: int) -> Optional[TradeAnalysisResult]:
    """Retrieve a past analysis from the database."""
    try:
        from db.database import get_session
        from db.cerberus_models import TradeAnalysis
        from sqlalchemy import select

        async with get_session() as session:
            stmt = select(TradeAnalysis).where(
                TradeAnalysis.id == analysis_id,
                TradeAnalysis.user_id == user_id,
            )
            row = await session.execute(stmt)
            record = row.scalar_one_or_none()

        if not record:
            return None

        return TradeAnalysisResult(
            analysis_id=record.id,
            symbol=record.symbol,
            action=record.action,
            proposed_size=record.proposed_size,
            current_price=record.current_price or 0.0,
            technical_report=record.technical_report or "",
            fundamental_report=record.fundamental_report or "",
            sentiment_report=record.sentiment_report or "",
            bull_case=record.bull_case or "",
            bear_case=record.bear_case or "",
            risk_assessment=record.risk_assessment or "",
            recommendation=record.recommendation or "hold",
            confidence=record.confidence or 0.0,
            reasoning=record.reasoning or "",
            node_trace=record.node_trace or [],
            errors=record.errors or [],
        )

    except Exception as exc:
        logger.error("trade_analysis_fetch_failed", analysis_id=analysis_id, error=str(exc))
        return None
