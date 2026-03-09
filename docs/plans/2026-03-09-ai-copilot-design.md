# AI Copilot Design Document

**Date**: 2026-03-09
**Status**: Approved (user-provided spec)
**Scope**: Embedded AI trading copilot for the adaptive-trading-ecosystem platform

## Summary

Add an embedded AI Copilot to the existing trading platform. The copilot provides Bloomberg Terminal-style AI assistance: portfolio analysis, strategy building, bot management, document research, and safe trade proposals — all through a floating chat widget integrated into the existing Next.js frontend backed by a FastAPI AI core service.

## Key Architectural Decisions

1. **LLM is copilot, not trader** — AI analyzes, explains, drafts, orchestrates. Never owns execution authority.
2. **Model routing**: gpt-5.4 (primary), gpt-4.1 (simple), claude-sonnet-4-6 (fallback/research), Perplexity (external search)
3. **Trade safety**: Draft-first → risk check → user confirm → token validate → re-check → execute → audit
4. **Existing stack preserved**: FastAPI backend, Next.js frontend, SQLAlchemy models, JWT auth, broker adapters
5. **New subsystems added alongside existing code** — no rewrites of working systems

## Implementation Approach

### What Exists (Preserve)
- 16 SQLAlchemy models (User, Trade, BrokerCredential, etc.)
- JWT auth middleware
- Webull + Alpaca broker adapters
- 12 signal models + ensemble
- Risk manager + execution engine
- Backtester with walk-forward
- Next.js frontend with dashboard, trading, strategies, portfolio, risk pages

### What's New (Add)
- ~15 new DB tables (conversations, memory, documents, proposals, tool calls, audit)
- AI Core orchestration (model router, tool registry, context assembler, prompt builder, safety guard)
- Memory service (short-term, operational, semantic with pgvector)
- Document ingestion pipeline (upload → parse → chunk → embed → index)
- Trade proposal/confirmation flow
- Trade analytics service + materialized views
- UI command system (allowlisted semantic commands)
- Frontend copilot widget (floating bubble → slide-out panel with 5 tabs)
- Shared TypeScript types for API payloads and UI commands
- WebSocket streaming for assistant responses
- Feature flags for progressive rollout

### Directory Structure (New Files)
```
adaptive-trading-ecosystem/
├── services/
│   └── ai_core/
│       ├── __init__.py
│       ├── chat_controller.py
│       ├── model_router.py
│       ├── context_assembler.py
│       ├── prompt_builder.py
│       ├── response_streamer.py
│       ├── safety_guard.py
│       ├── citation_assembler.py
│       ├── ui_command_formatter.py
│       ├── tools/
│       │   ├── registry.py
│       │   ├── executor.py
│       │   ├── portfolio_tools.py
│       │   ├── risk_tools.py
│       │   ├── market_tools.py
│       │   ├── trading_tools.py
│       │   ├── analytics_tools.py
│       │   └── research_tools.py
│       ├── memory/
│       │   ├── memory_service.py
│       │   ├── retrieval.py
│       │   ├── summarizer.py
│       │   ├── embeddings.py
│       │   └── save_policy.py
│       ├── providers/
│       │   ├── openai_provider.py
│       │   ├── anthropic_provider.py
│       │   └── perplexity_provider.py
│       ├── documents/
│       │   ├── ingestion.py
│       │   ├── parsers.py
│       │   ├── chunker.py
│       │   └── upload.py
│       ├── proposals/
│       │   ├── trade_proposal_service.py
│       │   └── confirmation_service.py
│       └── analytics/
│           └── trade_analytics.py
├── api/routes/
│   ├── ai_chat.py
│   ├── ai_tools.py
│   └── documents.py
├── frontend/src/
│   ├── components/copilot/
│   │   ├── AIWidget.tsx
│   │   ├── ChatPanel.tsx
│   │   ├── MessageList.tsx
│   │   ├── MessageInput.tsx
│   │   ├── StrategyBuilder.tsx
│   │   ├── PortfolioAnalysis.tsx
│   │   ├── BotControlPanel.tsx
│   │   ├── ResearchPanel.tsx
│   │   ├── TradeSignalCard.tsx
│   │   ├── ChartRenderer.tsx
│   │   ├── CitationList.tsx
│   │   ├── ConfirmationModal.tsx
│   │   └── ToolStatusPill.tsx
│   ├── stores/
│   │   ├── copilot-store.ts
│   │   ├── ui-context-store.ts
│   │   └── portfolio-store.ts
│   ├── lib/
│   │   ├── copilot-api.ts
│   │   ├── copilot-websocket.ts
│   │   └── ui-command-executor.ts
│   └── types/
│       ├── copilot.ts
│       └── ui-commands.ts
└── packages/
    └── shared-types/
        ├── api-payloads.ts
        └── ui-command-schema.ts
```

Full spec details preserved in the user's original prompt (26 sections).
