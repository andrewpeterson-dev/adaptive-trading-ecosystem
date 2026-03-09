"""Research tools for the Cerberus."""
from __future__ import annotations

import structlog

from services.ai_core.tools.base import ToolDefinition, ToolCategory, ToolSideEffect
from services.ai_core.tools.registry import get_registry

logger = structlog.get_logger(__name__)


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
    """Search market news via Perplexity provider. Stub."""
    # TODO: Integrate with Perplexity API or news aggregator
    return {
        "query": query,
        "articles": [],
        "message": "Market news search not yet implemented; will integrate with Perplexity/news API",
    }


async def _get_macro_events(user_id: int, days_ahead: int = 7) -> dict:
    """Get upcoming macro events. Stub."""
    # TODO: Integrate with economic calendar API
    return {
        "days_ahead": days_ahead,
        "events": [],
        "message": "Macro events not yet implemented; will integrate with economic calendar API",
    }


async def _get_earnings_context(user_id: int, symbol: str) -> dict:
    """Get earnings context for a symbol. Stub."""
    # TODO: Integrate with earnings data provider + document search
    return {
        "symbol": symbol.upper(),
        "next_earnings": None,
        "previous_earnings": None,
        "analyst_estimates": None,
        "related_documents": [],
        "message": "Earnings context not yet implemented; will integrate with financial data providers",
    }


async def _run_research_session(
    user_id: int,
    topic: str,
    symbols: list[str] = None,
    depth: str = "standard",
) -> dict:
    """Run a full research session combining documents + market data + search.

    Stub that returns a placeholder structure for the full research pipeline.
    """
    # TODO: Implement multi-source research pipeline:
    # 1. Search user documents for relevant context
    # 2. Fetch market data for related symbols
    # 3. Query Perplexity for recent news/analysis
    # 4. Synthesize findings
    return {
        "topic": topic,
        "symbols": symbols or [],
        "depth": depth,
        "document_results": [],
        "market_data": {},
        "news_results": [],
        "synthesis": None,
        "message": "Full research session not yet implemented; will combine document search, market data, and external sources",
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
