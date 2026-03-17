"""Node implementations for the multi-agent trade analysis pipeline.

Each node is an async function that accepts ``TradeAnalysisState``,
calls existing tools/providers, and returns a partial state update.
Failures are captured in ``errors`` so the pipeline continues.

Because ``node_trace`` and ``errors`` use ``Annotated[list, operator.add]``,
each node returns single-element lists that the reducer concatenates.
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any

import structlog

from services.ai_core.model_router import ModelRouter
from services.ai_core.providers.base import ProviderMessage
from services.ai_core.multi_agent.state import TradeAnalysisState

logger = structlog.get_logger(__name__)

# Shared router instance for all nodes
_router = ModelRouter()


# ── Helpers ──────────────────────────────────────────────────────────────────

async def _call_llm(system_prompt: str, user_prompt: str) -> str:
    """Call the primary LLM via the existing model router."""
    routing = _router.route(
        mode="analysis",
        message=user_prompt[:200],
        has_tools=False,
        has_documents=False,
        has_sensitive_data=True,
    )
    messages = [
        ProviderMessage(role="system", content=system_prompt),
        ProviderMessage(role="user", content=user_prompt),
    ]
    response = await routing.provider.complete(
        messages=messages,
        model=routing.model,
        temperature=0.3,
        max_tokens=2048,
    )
    return response.content


async def _call_tool_handler(handler, **kwargs) -> dict:
    """Invoke a registered tool handler directly (bypasses executor caching)."""
    return await handler(**kwargs)


# ── Node: Technical Analyst ──────────────────────────────────────────────────

async def technical_analyst(state: TradeAnalysisState) -> dict:
    """Compute and interpret technical indicators."""
    node_name = "technical_analyst"
    symbol = state["symbol"]
    user_id = state["user_id"]
    try:
        from services.ai_core.tools.market_tools import (
            _get_price,
            _get_historical_prices,
            _get_indicators,
        )

        price_data, hist_data, indicator_data = await asyncio.gather(
            _call_tool_handler(_get_price, user_id=user_id, symbol=symbol),
            _call_tool_handler(
                _get_historical_prices,
                user_id=user_id,
                symbol=symbol,
                period="3mo",
                interval="1d",
            ),
            _call_tool_handler(
                _get_indicators,
                user_id=user_id,
                symbol=symbol,
                indicators=[
                    "rsi_14", "sma_20", "sma_50", "ema_12", "ema_26",
                    "macd", "bb_20",
                ],
                period="3mo",
                interval="1d",
            ),
        )

        # Compute support/resistance from recent bars
        bars = hist_data.get("bars", [])
        recent_highs = [b["high"] for b in bars[-20:]] if len(bars) >= 20 else []
        recent_lows = [b["low"] for b in bars[-20:]] if len(bars) >= 20 else []
        support = round(min(recent_lows), 2) if recent_lows else None
        resistance = round(max(recent_highs), 2) if recent_highs else None

        # Summarise volume trend
        volumes = [b["volume"] for b in bars[-20:]] if len(bars) >= 20 else []
        avg_vol = sum(volumes) / len(volumes) if volumes else 0
        latest_vol = bars[-1]["volume"] if bars else 0
        vol_ratio = round(latest_vol / avg_vol, 2) if avg_vol > 0 else 0

        data_summary = json.dumps(
            {
                "price": price_data,
                "indicators": indicator_data.get("indicators", {}),
                "support": support,
                "resistance": resistance,
                "volume_ratio_vs_20d_avg": vol_ratio,
                "bars_count": len(bars),
            },
            indent=2,
            default=str,
        )

        system = (
            "You are a senior technical analyst. Given the raw technical data below, "
            "produce a concise report covering: trend direction, momentum, RSI interpretation, "
            "MACD signal, Bollinger Band position, volume patterns, support/resistance levels, "
            "and an overall technical bias (bullish/bearish/neutral). Be specific with numbers."
        )
        user = (
            f"Symbol: {symbol}\n"
            f"Proposed action: {state.get('proposed_action', 'buy')}\n\n"
            f"Technical Data:\n{data_summary}"
        )
        report = await _call_llm(system, user)

        return {
            "technical_report": report,
            "node_trace": [node_name],
        }

    except Exception as exc:
        logger.error("technical_analyst_failed", symbol=symbol, error=str(exc))
        return {
            "technical_report": f"[Technical analysis unavailable: {exc}]",
            "node_trace": [node_name],
            "errors": [f"technical_analyst: {exc}"],
        }


# ── Node: Fundamental Analyst ────────────────────────────────────────────────

async def fundamental_analyst(state: TradeAnalysisState) -> dict:
    """Evaluate fundamentals via yfinance."""
    node_name = "fundamental_analyst"
    symbol = state["symbol"]
    try:
        import yfinance as yf

        def _fetch_fundamentals() -> dict:
            ticker = yf.Ticker(symbol)
            info = ticker.info or {}
            return {
                "pe_ratio": info.get("trailingPE"),
                "forward_pe": info.get("forwardPE"),
                "peg_ratio": info.get("pegRatio"),
                "price_to_book": info.get("priceToBook"),
                "market_cap": info.get("marketCap"),
                "revenue": info.get("totalRevenue"),
                "revenue_growth": info.get("revenueGrowth"),
                "earnings_growth": info.get("earningsGrowth"),
                "profit_margin": info.get("profitMargins"),
                "operating_margin": info.get("operatingMargins"),
                "return_on_equity": info.get("returnOnEquity"),
                "debt_to_equity": info.get("debtToEquity"),
                "current_ratio": info.get("currentRatio"),
                "free_cash_flow": info.get("freeCashflow"),
                "dividend_yield": info.get("dividendYield"),
                "sector": info.get("sector"),
                "industry": info.get("industry"),
                "short_name": info.get("shortName"),
            }

        fundamentals = await asyncio.to_thread(_fetch_fundamentals)
        data_summary = json.dumps(fundamentals, indent=2, default=str)

        system = (
            "You are a senior fundamental analyst. Given the fundamental data below, "
            "produce a concise report covering: valuation (P/E, P/B, PEG), growth metrics "
            "(revenue growth, earnings growth), profitability (margins, ROE), balance sheet "
            "health (debt-to-equity, current ratio, FCF), and an overall fundamental "
            "assessment (overvalued/fairly-valued/undervalued). Be specific with numbers."
        )
        user = (
            f"Symbol: {symbol}\n"
            f"Proposed action: {state.get('proposed_action', 'buy')}\n\n"
            f"Fundamental Data:\n{data_summary}"
        )
        report = await _call_llm(system, user)

        return {
            "fundamental_report": report,
            "node_trace": [node_name],
        }

    except Exception as exc:
        logger.error("fundamental_analyst_failed", symbol=symbol, error=str(exc))
        return {
            "fundamental_report": f"[Fundamental analysis unavailable: {exc}]",
            "node_trace": [node_name],
            "errors": [f"fundamental_analyst: {exc}"],
        }


# ── Node: Sentiment Analyst ──────────────────────────────────────────────────

async def sentiment_analyst(state: TradeAnalysisState) -> dict:
    """Analyze news and social sentiment using the existing sentiment service."""
    node_name = "sentiment_analyst"
    symbol = state["symbol"]
    user_id = state["user_id"]
    try:
        from services.ai_core.tools.sentiment_tools import _get_sentiment_analysis
        from services.ai_core.tools.research_tools import _get_market_news

        sentiment_data, news_data = await asyncio.gather(
            _call_tool_handler(
                _get_sentiment_analysis,
                user_id=user_id,
                ticker=symbol,
                lookback_days=7,
            ),
            _call_tool_handler(
                _get_market_news,
                user_id=user_id,
                query=symbol,
                max_results=5,
            ),
        )

        data_summary = json.dumps(
            {
                "sentiment": sentiment_data,
                "recent_news": [
                    {
                        "title": a.get("title", ""),
                        "source": a.get("source", ""),
                        "summary": (a.get("summary", "") or "")[:200],
                    }
                    for a in (news_data.get("articles") or [])[:5]
                ],
            },
            indent=2,
            default=str,
        )

        system = (
            "You are a sentiment analyst. Given the sentiment scores and recent news "
            "headlines below, produce a concise report covering: overall sentiment "
            "(bullish/bearish/neutral with score), key news themes driving sentiment, "
            "any notable catalysts or risks mentioned in headlines, and a sentiment bias "
            "for the proposed trade. Be specific."
        )
        user = (
            f"Symbol: {symbol}\n"
            f"Proposed action: {state.get('proposed_action', 'buy')}\n\n"
            f"Sentiment & News Data:\n{data_summary}"
        )
        report = await _call_llm(system, user)

        return {
            "sentiment_report": report,
            "node_trace": [node_name],
        }

    except Exception as exc:
        logger.error("sentiment_analyst_failed", symbol=symbol, error=str(exc))
        return {
            "sentiment_report": f"[Sentiment analysis unavailable: {exc}]",
            "node_trace": [node_name],
            "errors": [f"sentiment_analyst: {exc}"],
        }


# ── Node: Bullish Researcher ─────────────────────────────────────────────────

async def bullish_researcher(state: TradeAnalysisState) -> dict:
    """Build the strongest possible bull case from analyst reports."""
    node_name = "bullish_researcher"
    try:
        system = (
            "You are a senior equity researcher tasked with making the STRONGEST possible "
            "BULL CASE for the proposed trade. You must argue persuasively in favor of "
            "the trade, citing specific data from the analyst reports. Structure your "
            "argument as: (1) Key bullish thesis, (2) Supporting technical evidence, "
            "(3) Fundamental justification, (4) Sentiment tailwinds, (5) Potential "
            "catalysts and upside targets. Be specific with numbers and price levels."
        )
        user = (
            f"Symbol: {state['symbol']} | Action: {state.get('proposed_action', 'buy')} | "
            f"Current Price: ${state.get('current_price', 0):.2f}\n\n"
            f"--- TECHNICAL REPORT ---\n{state.get('technical_report', 'N/A')}\n\n"
            f"--- FUNDAMENTAL REPORT ---\n{state.get('fundamental_report', 'N/A')}\n\n"
            f"--- SENTIMENT REPORT ---\n{state.get('sentiment_report', 'N/A')}"
        )
        bull_case = await _call_llm(system, user)

        return {
            "bull_case": bull_case,
            "node_trace": [node_name],
        }

    except Exception as exc:
        logger.error("bullish_researcher_failed", error=str(exc))
        return {
            "bull_case": f"[Bull case unavailable: {exc}]",
            "node_trace": [node_name],
            "errors": [f"bullish_researcher: {exc}"],
        }


# ── Node: Bearish Researcher ─────────────────────────────────────────────────

async def bearish_researcher(state: TradeAnalysisState) -> dict:
    """Build the strongest possible bear case from analyst reports."""
    node_name = "bearish_researcher"
    try:
        system = (
            "You are a senior equity researcher tasked with making the STRONGEST possible "
            "BEAR CASE against the proposed trade. You must argue persuasively AGAINST "
            "the trade, citing specific data from the analyst reports. Structure your "
            "argument as: (1) Key bearish thesis, (2) Technical warning signals, "
            "(3) Fundamental red flags, (4) Sentiment headwinds, (5) Downside risks "
            "and price targets. Be specific with numbers and price levels."
        )
        user = (
            f"Symbol: {state['symbol']} | Action: {state.get('proposed_action', 'buy')} | "
            f"Current Price: ${state.get('current_price', 0):.2f}\n\n"
            f"--- TECHNICAL REPORT ---\n{state.get('technical_report', 'N/A')}\n\n"
            f"--- FUNDAMENTAL REPORT ---\n{state.get('fundamental_report', 'N/A')}\n\n"
            f"--- SENTIMENT REPORT ---\n{state.get('sentiment_report', 'N/A')}"
        )
        bear_case = await _call_llm(system, user)

        return {
            "bear_case": bear_case,
            "node_trace": [node_name],
        }

    except Exception as exc:
        logger.error("bearish_researcher_failed", error=str(exc))
        return {
            "bear_case": f"[Bear case unavailable: {exc}]",
            "node_trace": [node_name],
            "errors": [f"bearish_researcher: {exc}"],
        }


# ── Node: Risk Assessor ──────────────────────────────────────────────────────

async def risk_assessor(state: TradeAnalysisState) -> dict:
    """Evaluate risk metrics for the proposed trade."""
    node_name = "risk_assessor"
    user_id = state["user_id"]
    try:
        from services.ai_core.tools.risk_tools import (
            _portfolio_exposure,
            _concentration_risk,
            _calculate_var,
        )

        exposure_data, concentration_data, var_data = await asyncio.gather(
            _call_tool_handler(_portfolio_exposure, user_id=user_id),
            _call_tool_handler(_concentration_risk, user_id=user_id),
            _call_tool_handler(
                _calculate_var,
                user_id=user_id,
                confidence=0.95,
                horizon_days=1,
                method="historical",
            ),
        )

        data_summary = json.dumps(
            {
                "portfolio_exposure": exposure_data,
                "concentration": concentration_data,
                "var_95_1d": var_data,
            },
            indent=2,
            default=str,
        )

        system = (
            "You are a senior risk manager. Given the portfolio risk data and the proposed "
            "trade details, produce a concise risk assessment covering: (1) Portfolio impact "
            "(how this trade changes exposure and concentration), (2) VaR implications, "
            "(3) Correlation risk, (4) Maximum drawdown exposure, (5) Position sizing "
            "recommendation, (6) Overall risk rating (low/moderate/high/extreme). "
            "Be specific with numbers."
        )
        user = (
            f"Symbol: {state['symbol']} | Action: {state.get('proposed_action', 'buy')} | "
            f"Size: {state.get('proposed_size', 0)} | "
            f"Current Price: ${state.get('current_price', 0):.2f}\n\n"
            f"Risk Data:\n{data_summary}"
        )
        assessment = await _call_llm(system, user)

        return {
            "risk_assessment": assessment,
            "node_trace": [node_name],
        }

    except Exception as exc:
        logger.error("risk_assessor_failed", error=str(exc))
        return {
            "risk_assessment": f"[Risk assessment unavailable: {exc}]",
            "node_trace": [node_name],
            "errors": [f"risk_assessor: {exc}"],
        }


# ── Node: Decision Synthesizer ───────────────────────────────────────────────

async def decision_synthesizer(state: TradeAnalysisState) -> dict:
    """Synthesize all inputs into a final recommendation."""
    node_name = "decision_synthesizer"
    try:
        system = (
            "You are the Chief Investment Officer making the final call on a proposed trade. "
            "You have received a bull case, bear case, and risk assessment. Your job is to:\n"
            "1. Weigh both sides objectively.\n"
            "2. Factor in the risk assessment.\n"
            "3. Produce a FINAL RECOMMENDATION.\n\n"
            "You MUST output valid JSON at the END of your response in this exact format:\n"
            "```json\n"
            '{"recommendation": "<strong_buy|buy|hold|sell|strong_sell>", '
            '"confidence": <0.0-1.0>}\n'
            "```\n\n"
            "Before the JSON, write 2-4 paragraphs of reasoning explaining your decision. "
            "Be specific about what tipped the balance."
        )
        user = (
            f"Symbol: {state['symbol']} | Proposed Action: {state.get('proposed_action', 'buy')} | "
            f"Size: {state.get('proposed_size', 0)} | "
            f"Current Price: ${state.get('current_price', 0):.2f}\n\n"
            f"--- BULL CASE ---\n{state.get('bull_case', 'N/A')}\n\n"
            f"--- BEAR CASE ---\n{state.get('bear_case', 'N/A')}\n\n"
            f"--- RISK ASSESSMENT ---\n{state.get('risk_assessment', 'N/A')}"
        )
        raw = await _call_llm(system, user)

        # Parse recommendation and confidence from JSON block
        recommendation = "hold"
        confidence = 0.5

        # Try to extract JSON from the response
        json_match = re.search(r"```json\s*\n?(.+?)\n?\s*```", raw, re.DOTALL)
        if json_match:
            try:
                parsed = json.loads(json_match.group(1))
                recommendation = str(parsed.get("recommendation", "hold")).lower()
                confidence = float(parsed.get("confidence", 0.5))
                confidence = max(0.0, min(1.0, confidence))
            except (json.JSONDecodeError, ValueError, TypeError):
                pass
        else:
            # Fallback: try to find JSON-like patterns in the text
            for pattern in [
                r'"recommendation"\s*:\s*"(\w+)"',
                r"recommendation.*?(\bstrong_buy\b|\bbuy\b|\bhold\b|\bsell\b|\bstrong_sell\b)",
            ]:
                match = re.search(pattern, raw, re.IGNORECASE)
                if match:
                    recommendation = match.group(1).lower()
                    break

            conf_match = re.search(r'"confidence"\s*:\s*([\d.]+)', raw)
            if conf_match:
                try:
                    confidence = max(0.0, min(1.0, float(conf_match.group(1))))
                except ValueError:
                    pass

        valid_recs = {"strong_buy", "buy", "hold", "sell", "strong_sell"}
        if recommendation not in valid_recs:
            recommendation = "hold"

        # Reasoning is the text before the JSON block
        reasoning = raw
        if json_match:
            reasoning = raw[: json_match.start()].strip()

        return {
            "recommendation": recommendation,
            "confidence": confidence,
            "reasoning": reasoning,
            "node_trace": [node_name],
        }

    except Exception as exc:
        logger.error("decision_synthesizer_failed", error=str(exc))
        return {
            "recommendation": "hold",
            "confidence": 0.0,
            "reasoning": f"[Decision synthesis failed: {exc}]",
            "node_trace": [node_name],
            "errors": [f"decision_synthesizer: {exc}"],
        }
