"""Research tools for the Cerberus."""
from __future__ import annotations

import asyncio
import re
from datetime import datetime
from typing import Any

import pandas as pd
import structlog

from data.market_data import market_data
from news.ingestion import NewsIngestion
from news.ticker_validator import TickerValidator
from services.ai_core.tools.market_tools import _get_macro_calendar
from services.ai_core.tools.base import ToolDefinition, ToolCategory, ToolSideEffect
from services.ai_core.tools.registry import get_registry

logger = structlog.get_logger(__name__)

_news_ingestion = NewsIngestion()
_ticker_validator = TickerValidator()


def _extract_symbols(text: str, explicit_symbols: list[str] | None = None) -> list[str]:
    symbols: set[str] = set()

    for item in explicit_symbols or []:
        token = item.upper().strip()
        if token and _ticker_validator.is_valid(token):
            symbols.add(token)

    if text:
        for symbol in _news_ingestion.extract_tickers(text):
            if _ticker_validator.is_valid(symbol):
                symbols.add(symbol.upper())

        for token in re.findall(r"\$?([A-Za-z]{1,5}(?:[.-][A-Za-z])?)", text):
            candidate = token.upper()
            if _ticker_validator.is_valid(candidate):
                symbols.add(candidate)

    return sorted(symbols)


def _filter_news_articles(query: str, articles: list[dict], max_results: int) -> list[dict]:
    if not articles:
        return []

    query_terms = {
        term.lower()
        for term in re.findall(r"[A-Za-z]{3,}", query)
        if not _ticker_validator.is_valid(term.upper())
    }
    if not query_terms:
        return articles[:max_results]

    ranked: list[tuple[int, dict]] = []
    for article in articles:
        haystack = f"{article.get('title', '')} {article.get('summary', '')}".lower()
        score = sum(1 for term in query_terms if term in haystack)
        ranked.append((score, article))

    ranked.sort(key=lambda item: item[0], reverse=True)
    filtered = [article for score, article in ranked if score > 0]
    return (filtered or articles)[:max_results]


def _summarize_bars(symbol: str, bars: list[dict]) -> dict[str, Any]:
    if not bars:
        return {"symbol": symbol, "available": False}

    closes = pd.Series([float(bar.get("c", 0) or 0) for bar in bars], dtype=float)
    volumes = pd.Series([float(bar.get("v", 0) or 0) for bar in bars], dtype=float)
    if closes.empty or closes.iloc[-1] == 0:
        return {"symbol": symbol, "available": False}

    latest_close = float(closes.iloc[-1])
    day_change_pct = float(((latest_close / closes.iloc[-2]) - 1) * 100) if len(closes) > 1 and closes.iloc[-2] else None
    return_20d = float(((latest_close / closes.iloc[-21]) - 1) * 100) if len(closes) > 20 and closes.iloc[-21] else None
    volatility_20d = float(closes.pct_change().dropna().tail(20).std() * (252 ** 0.5) * 100) if len(closes) > 20 else None
    avg_volume_20d = float(volumes.tail(20).mean()) if len(volumes) > 0 else None

    return {
        "symbol": symbol,
        "available": True,
        "latest_close": round(latest_close, 4),
        "day_change_pct": round(day_change_pct, 4) if day_change_pct is not None else None,
        "return_20d_pct": round(return_20d, 4) if return_20d is not None else None,
        "annualized_volatility_20d_pct": round(volatility_20d, 4) if volatility_20d is not None else None,
        "avg_volume_20d": round(avg_volume_20d, 2) if avg_volume_20d is not None else None,
        "bars_analyzed": len(bars),
    }


async def _load_symbol_market_context(symbol: str) -> dict[str, Any]:
    quote, bars = await asyncio.gather(
        market_data.get_quote(symbol),
        market_data.get_bars(symbol, timeframe="1D", limit=60),
    )
    summary = _summarize_bars(symbol, bars or [])
    summary["quote"] = quote
    return summary


def _build_research_synthesis(
    topic: str,
    symbols: list[str],
    market_data_by_symbol: dict[str, dict],
    articles: list[dict],
    document_chunks: list[dict],
    macro_events: list[dict],
) -> str:
    lines: list[str] = [f"Research summary for {topic}."]

    if symbols:
        available = []
        for symbol in symbols:
            snapshot = market_data_by_symbol.get(symbol, {})
            latest_close = snapshot.get("latest_close")
            return_20d = snapshot.get("return_20d_pct")
            if latest_close is not None:
                fragment = f"{symbol} last traded at {latest_close:.2f}"
                if return_20d is not None:
                    fragment += f" with a 20-day return of {return_20d:.2f}%"
                available.append(fragment)
        if available:
            lines.append("Market context: " + "; ".join(available[:3]) + ".")

    if articles:
        headlines = [article.get("title", "").strip() for article in articles if article.get("title")]
        if headlines:
            lines.append("Recent headlines: " + "; ".join(headlines[:3]) + ".")

    if macro_events:
        upcoming = [event.get("event") for event in macro_events[:3] if event.get("event")]
        if upcoming:
            lines.append("Upcoming macro events: " + ", ".join(upcoming) + ".")

    if document_chunks:
        headings = [chunk.get("heading") or chunk.get("document_id") for chunk in document_chunks[:3]]
        headings = [heading for heading in headings if heading]
        if headings:
            lines.append("Internal documents surfaced: " + ", ".join(headings) + ".")

    return " ".join(lines)


async def _fetch_symbol_earnings_profile(symbol: str) -> dict[str, Any]:
    import yfinance as yf

    def _fetch() -> dict[str, Any]:
        ticker = yf.Ticker(symbol)
        try:
            earnings_dates = ticker.get_earnings_dates(limit=8)
        except Exception:
            earnings_dates = None

        events: list[dict] = []
        if isinstance(earnings_dates, pd.DataFrame) and not earnings_dates.empty:
            for idx, row in earnings_dates.iterrows():
                dt = idx.to_pydatetime() if hasattr(idx, "to_pydatetime") else idx
                event_dt = dt if isinstance(dt, datetime) else datetime.fromisoformat(str(dt))
                events.append(
                    {
                        "date": event_dt.date().isoformat(),
                        "eps_estimate": float(row["EPS Estimate"]) if pd.notna(row.get("EPS Estimate")) else None,
                        "eps_actual": float(row["Reported EPS"]) if pd.notna(row.get("Reported EPS")) else None,
                        "surprise_pct": float(row["Surprise(%)"]) if pd.notna(row.get("Surprise(%)")) else None,
                    }
                )

        events.sort(key=lambda item: item["date"])
        today = datetime.utcnow().date().isoformat()
        previous = [event for event in events if event["date"] < today]
        upcoming = [event for event in events if event["date"] >= today]
        next_earnings = upcoming[0] if upcoming else None
        previous_earnings = previous[-1] if previous else None
        analyst_estimates = {
            "eps_estimate": next_earnings.get("eps_estimate") if next_earnings else None,
            "eps_actual_last": previous_earnings.get("eps_actual") if previous_earnings else None,
            "surprise_pct_last": previous_earnings.get("surprise_pct") if previous_earnings else None,
        }
        return {
            "next_earnings": next_earnings,
            "previous_earnings": previous_earnings,
            "analyst_estimates": analyst_estimates,
        }

    return await asyncio.to_thread(_fetch)


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

async def _search_documents(user_id: int, query: str, limit: int = 10) -> dict:
    """Search document chunks via text LIKE matching.

    pgvector/embedding search is not yet available, so we fall back to
    a simple case-insensitive LIKE query on chunk content.
    """
    from db.database import get_session
    from db.cerberus_models import CerberusDocumentChunk
    from sqlalchemy import select

    async with get_session() as session:
        stmt = (
            select(CerberusDocumentChunk)
            .where(
                CerberusDocumentChunk.user_id == user_id,
                CerberusDocumentChunk.content.ilike(f"%{query}%"),
            )
            .order_by(CerberusDocumentChunk.created_at.desc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        chunks = result.scalars().all()

    return {
        "query": query,
        "count": len(chunks),
        "chunks": [
            {
                "chunk_id": c.id,
                "document_id": c.document_id,
                "chunk_index": c.chunk_index,
                "page_number": c.page_number,
                "heading": c.heading,
                "content": c.content[:500],  # Truncate for response size
                "metadata": c.metadata_json,
            }
            for c in chunks
        ],
    }


async def _get_document_excerpt(user_id: int, chunk_ids: list[str] = None, document_id: str = None) -> dict:
    """Get specific document chunks by ID or document."""
    from db.database import get_session
    from db.cerberus_models import CerberusDocumentChunk
    from sqlalchemy import select

    async with get_session() as session:
        if chunk_ids:
            stmt = select(CerberusDocumentChunk).where(
                CerberusDocumentChunk.user_id == user_id,
                CerberusDocumentChunk.id.in_(chunk_ids),
            )
        elif document_id:
            stmt = (
                select(CerberusDocumentChunk)
                .where(
                    CerberusDocumentChunk.user_id == user_id,
                    CerberusDocumentChunk.document_id == document_id,
                )
                .order_by(CerberusDocumentChunk.chunk_index.asc())
            )
        else:
            return {"error": "Provide either chunk_ids or document_id"}

        result = await session.execute(stmt)
        chunks = result.scalars().all()

    return {
        "count": len(chunks),
        "chunks": [
            {
                "chunk_id": c.id,
                "document_id": c.document_id,
                "chunk_index": c.chunk_index,
                "page_number": c.page_number,
                "heading": c.heading,
                "content": c.content,
                "metadata": c.metadata_json,
            }
            for c in chunks
        ],
    }


async def _get_market_news(user_id: int, query: str, max_results: int = 5) -> dict:
    """Search recent market news for detected ticker symbols."""
    symbols = _extract_symbols(query)
    if not symbols:
        return {
            "query": query,
            "symbols": [],
            "count": 0,
            "articles": [],
            "sources": [],
            "message": "No valid ticker symbols detected in query",
        }

    articles = await asyncio.to_thread(_news_ingestion.fetch_news, symbols, max(max_results * 2, max_results))
    filtered = _filter_news_articles(query, articles, max_results)
    sources = [
        {
            "title": article.get("title", ""),
            "url": article.get("url", ""),
            "snippet": article.get("summary", ""),
            "date": article.get("published_at"),
            "source": article.get("source"),
        }
        for article in filtered
    ]

    return {
        "query": query,
        "symbols": symbols,
        "count": len(filtered),
        "articles": filtered,
        "sources": sources,
        "message": None if filtered else "No market news found for the requested symbols",
    }


async def _get_macro_events(user_id: int, days_ahead: int = 7) -> dict:
    """Get upcoming macro events from the shared market tool."""
    return await _get_macro_calendar(user_id=user_id, days_ahead=days_ahead)


async def _get_earnings_context(user_id: int, symbol: str) -> dict:
    """Get earnings context for a symbol from real market data and documents."""
    symbol = symbol.upper().strip()
    earnings_profile, market_context, related_documents = await asyncio.gather(
        _fetch_symbol_earnings_profile(symbol),
        _load_symbol_market_context(symbol),
        _search_documents(user_id, f"{symbol} earnings", limit=5),
    )

    related_chunks = related_documents.get("chunks", [])
    sources = []
    if earnings_profile.get("next_earnings"):
        sources.append(
            {
                "title": f"{symbol} earnings schedule",
                "url": f"https://finance.yahoo.com/quote/{symbol}",
                "snippet": f"Next earnings date for {symbol}",
            }
        )

    return {
        "symbol": symbol,
        "next_earnings": earnings_profile.get("next_earnings"),
        "previous_earnings": earnings_profile.get("previous_earnings"),
        "analyst_estimates": earnings_profile.get("analyst_estimates"),
        "recent_price_context": market_context,
        "related_documents": related_chunks,
        "sources": sources,
        "message": None if (earnings_profile.get("next_earnings") or earnings_profile.get("previous_earnings") or related_chunks) else "No earnings context found",
    }


async def _run_research_session(
    user_id: int,
    topic: str,
    symbols: list[str] = None,
    depth: str = "standard",
) -> dict:
    """Run a multi-source research session with real documents, market data, and news."""
    symbol_list = _extract_symbols(topic, explicit_symbols=symbols)
    depth = depth if depth in {"quick", "standard", "deep"} else "standard"
    doc_limit = {"quick": 3, "standard": 6, "deep": 10}[depth]
    news_limit = {"quick": 3, "standard": 5, "deep": 8}[depth]
    macro_window = {"quick": 7, "standard": 14, "deep": 30}[depth]

    document_results, news_result, macro_result = await asyncio.gather(
        _search_documents(user_id, topic, limit=doc_limit),
        _get_market_news(user_id, " ".join(symbol_list) if symbol_list else topic, max_results=news_limit),
        _get_macro_events(user_id, days_ahead=macro_window),
    )

    market_snapshots_list = await asyncio.gather(
        *[_load_symbol_market_context(symbol) for symbol in symbol_list[:5]],
        return_exceptions=True,
    )
    market_snapshots: dict[str, dict] = {}
    for symbol, snapshot in zip(symbol_list[:5], market_snapshots_list):
        if isinstance(snapshot, Exception):
            logger.warning("research_market_context_failed", symbol=symbol, error=str(snapshot))
            continue
        market_snapshots[symbol] = snapshot

    earnings_contexts_list = await asyncio.gather(
        *[_get_earnings_context(user_id, symbol) for symbol in symbol_list[:3]],
        return_exceptions=True,
    )
    earnings_contexts = []
    for context in earnings_contexts_list:
        if isinstance(context, Exception):
            logger.warning("research_earnings_context_failed", error=str(context))
            continue
        earnings_contexts.append(context)

    document_chunks = document_results.get("chunks", [])
    news_articles = news_result.get("articles", [])
    macro_events = macro_result.get("events", [])
    synthesis = _build_research_synthesis(
        topic,
        symbol_list,
        market_snapshots,
        news_articles,
        document_chunks,
        macro_events,
    )

    return {
        "topic": topic,
        "symbols": symbol_list,
        "depth": depth,
        "document_results": document_chunks,
        "market_data": market_snapshots,
        "news_results": news_articles,
        "earnings_context": earnings_contexts,
        "macro_events": macro_events,
        "sources": news_result.get("sources", []),
        "synthesis": synthesis,
        "message": None if (document_chunks or market_snapshots or news_articles or macro_events) else "No research inputs found for the requested topic",
    }


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register():
    registry = get_registry()

    registry.register(ToolDefinition(
        name="searchDocuments",
        version="1.0",
        description="Search uploaded documents by keyword (text-based; vector search coming soon)",
        category=ToolCategory.RESEARCH,
        side_effect=ToolSideEffect.READ,
        timeout_ms=5000,
        cache_ttl_s=30,
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "limit": {"type": "integer", "description": "Max results", "default": 10},
            },
            "required": ["query"],
        },
        output_schema={"type": "object"},
        handler=_search_documents,
    ))

    registry.register(ToolDefinition(
        name="getDocumentExcerpt",
        version="1.0",
        description="Get specific document chunks by chunk ID or document ID",
        category=ToolCategory.RESEARCH,
        side_effect=ToolSideEffect.READ,
        timeout_ms=3000,
        cache_ttl_s=60,
        input_schema={
            "type": "object",
            "properties": {
                "chunk_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Specific chunk IDs to retrieve",
                },
                "document_id": {"type": "string", "description": "Document ID to get all chunks for"},
            },
        },
        output_schema={"type": "object"},
        handler=_get_document_excerpt,
    ))

    registry.register(ToolDefinition(
        name="getMarketNews",
        version="1.0",
        description="Search for recent market news and analysis",
        category=ToolCategory.RESEARCH,
        side_effect=ToolSideEffect.READ,
        timeout_ms=10000,
        cache_ttl_s=120,
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "News search query"},
                "max_results": {"type": "integer", "description": "Max articles", "default": 5},
            },
            "required": ["query"],
        },
        output_schema={"type": "object"},
        handler=_get_market_news,
    ))

    registry.register(ToolDefinition(
        name="getMacroEvents",
        version="1.0",
        description="Get upcoming macroeconomic events and data releases",
        category=ToolCategory.RESEARCH,
        side_effect=ToolSideEffect.READ,
        timeout_ms=5000,
        cache_ttl_s=300,
        input_schema={
            "type": "object",
            "properties": {
                "days_ahead": {"type": "integer", "description": "Days to look ahead", "default": 7},
            },
        },
        output_schema={"type": "object"},
        handler=_get_macro_events,
    ))

    registry.register(ToolDefinition(
        name="getEarningsContext",
        version="1.0",
        description="Get earnings context for a symbol (dates, estimates, related documents)",
        category=ToolCategory.RESEARCH,
        side_effect=ToolSideEffect.READ,
        timeout_ms=8000,
        cache_ttl_s=300,
        input_schema={
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Ticker symbol"},
            },
            "required": ["symbol"],
        },
        output_schema={"type": "object"},
        handler=_get_earnings_context,
    ))

    registry.register(ToolDefinition(
        name="runResearchSession",
        version="1.0",
        description="Run a comprehensive research session combining documents, market data, and news",
        category=ToolCategory.RESEARCH,
        side_effect=ToolSideEffect.READ,
        timeout_ms=30000,
        cache_ttl_s=120,
        input_schema={
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "Research topic or question"},
                "symbols": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Related ticker symbols",
                },
                "depth": {"type": "string", "enum": ["quick", "standard", "deep"], "default": "standard"},
            },
            "required": ["topic"],
        },
        output_schema={"type": "object"},
        handler=_run_research_session,
    ))
