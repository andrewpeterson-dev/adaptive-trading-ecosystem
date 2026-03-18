# AI Brain Feature — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform AI from passive gatekeeper to active trading brain with per-bot model selection, model comparison, and tiered reasoning UI.

**Architecture:** New AITradingEngine service parallel to ReasoningEngine. BotRunner routes to AITradingEngine when `ai_brain_config` is set. Multi-agent LangGraph pipeline drives decisions. Shadow model comparison via asyncio.create_task fire-and-forget.

**Tech Stack:** Python/FastAPI backend, Next.js/React/Tailwind/shadcn frontend, SQLAlchemy/SQLite, LangGraph, pytest, Vitest

**Spec:** `docs/superpowers/specs/2026-03-18-ai-brain-feature-design.md`

---

## File Structure

### New Files (Backend)
| File | Responsibility |
|------|---------------|
| `services/ai_brain/__init__.py` | Package init |
| `services/ai_brain/engine.py` | AITradingEngine — thin orchestrator |
| `services/ai_brain/types.py` | AITradeDecision, AIBrainConfig dataclasses |
| `services/ai_brain/shadow_resolver.py` | Background task for shadow P&L mark-to-market |
| `alembic/versions/010_ai_brain_tables.py` | Migration: ai_brain_config, bot_model_performance, ai_trade_reasoning |
| `tests/test_ai_brain_engine.py` | AITradingEngine unit tests |
| `tests/test_ai_brain_api.py` | API route tests |

### New Files (Frontend)
| File | Responsibility |
|------|---------------|
| `frontend/src/components/bots/AIReasoningPanel.tsx` | Tiered reasoning display (B + expandable C) |
| `frontend/src/components/bots/ModelLeaderboard.tsx` | Model comparison table with promote button |
| `frontend/src/components/bots/AIPreviewButton.tsx` | "What would AI do?" preview |

### Modified Files
| File | Changes |
|------|---------|
| `db/cerberus_models.py` | Add ai_brain_config on CerberusBot, BotModelPerformance, AITradeReasoning tables, fix BotStatus constraint |
| `services/bot_engine/runner.py` | Add ai_driven/ai_assisted routing in _evaluate_bot, _background_tasks set |
| `services/ai_core/multi_agent/state.py` | Add trading_thesis, model_override, skip_nodes to state |
| `services/ai_core/multi_agent/graph.py` | Support skip_nodes in graph |
| `services/ai_core/multi_agent/runner.py` | Accept model_override, skip_nodes, return structured decision |
| `services/ai_core/model_router.py` | Add TRADING_DECISION intent |
| `api/routes/ai_tools.py` | Add ai-config, ai-preview, model-comparison, ai-reasoning endpoints |
| `frontend/src/components/bots/DeployConfigModal.tsx` | Add AI model selection, data sources, advanced toggle |

---

## Task 1: Database Models & Migration

**Files:**
- Modify: `db/cerberus_models.py` (lines 244-274, 268-274)
- Create: `alembic/versions/010_ai_brain_tables.py`

- [ ] **Step 1: Add ai_brain_config to CerberusBot**

In `db/cerberus_models.py`, add after `reasoning_model_config` (line 261):
```python
ai_brain_config = Column(JSON, nullable=True)  # AI Brain focus profile
```

Fix BotStatus check constraint (line 271) to include 'deleted':
```python
CheckConstraint(
    "status IN ('draft','running','paused','stopped','error','deleted')",
    name="ck_cerberus_bot_status",
),
```

- [ ] **Step 2: Add BotModelPerformance and AITradeReasoning models**

Add after the last class in `db/cerberus_models.py`:
```python
class BotModelPerformance(Base):
    """Tracks every AI trade decision for model comparison leaderboard."""
    __tablename__ = "bot_model_performance"

    id = Column(String(36), primary_key=True, default=_uuid)
    bot_id = Column(String(36), ForeignKey("cerberus_bots.id"), nullable=False)
    cerberus_trade_id = Column(String(36), ForeignKey("cerberus_trades.id"), nullable=True)
    model_used = Column(String(64), nullable=False)
    symbol = Column(String(16), nullable=False)
    action = Column(String(8), nullable=False)
    confidence = Column(Float, nullable=True)
    reasoning_summary = Column(Text, nullable=True)
    entry_price = Column(Float, nullable=True)
    exit_price = Column(Float, nullable=True)
    pnl = Column(Float, nullable=True)
    is_shadow = Column(Boolean, default=False)
    decided_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_bmp_bot_model", "bot_id", "model_used"),
        Index("ix_bmp_bot_resolved", "bot_id", "resolved_at"),
    )


class AITradeReasoning(Base):
    """Full reasoning chain per decision node — audit log for Tier C display."""
    __tablename__ = "ai_trade_reasoning"

    id = Column(String(36), primary_key=True, default=_uuid)
    performance_id = Column(String(36), ForeignKey("bot_model_performance.id"), nullable=False)
    node_name = Column(String(64), nullable=False)
    node_output = Column(JSON, nullable=True)
    model_used = Column(String(64), nullable=True)
    tokens_used = Column(Integer, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
```

- [ ] **Step 3: Write Alembic migration**

Create `alembic/versions/010_ai_brain_tables.py`:
```python
"""AI Brain: ai_brain_config, bot_model_performance, ai_trade_reasoning

Revision ID: 010_ai_brain
Revises: 009
"""
revision = "010_ai_brain"
down_revision = "009"

from alembic import op
import sqlalchemy as sa

def upgrade():
    # Add ai_brain_config to cerberus_bots
    op.add_column("cerberus_bots", sa.Column("ai_brain_config", sa.JSON, nullable=True))

    # Create bot_model_performance
    op.create_table(
        "bot_model_performance",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("bot_id", sa.String(36), sa.ForeignKey("cerberus_bots.id"), nullable=False),
        sa.Column("cerberus_trade_id", sa.String(36), sa.ForeignKey("cerberus_trades.id"), nullable=True),
        sa.Column("model_used", sa.String(64), nullable=False),
        sa.Column("symbol", sa.String(16), nullable=False),
        sa.Column("action", sa.String(8), nullable=False),
        sa.Column("confidence", sa.Float, nullable=True),
        sa.Column("reasoning_summary", sa.Text, nullable=True),
        sa.Column("entry_price", sa.Float, nullable=True),
        sa.Column("exit_price", sa.Float, nullable=True),
        sa.Column("pnl", sa.Float, nullable=True),
        sa.Column("is_shadow", sa.Boolean, default=False),
        sa.Column("decided_at", sa.DateTime, nullable=False),
        sa.Column("resolved_at", sa.DateTime, nullable=True),
    )
    op.create_index("ix_bmp_bot_model", "bot_model_performance", ["bot_id", "model_used"])
    op.create_index("ix_bmp_bot_resolved", "bot_model_performance", ["bot_id", "resolved_at"])

    # Create ai_trade_reasoning
    op.create_table(
        "ai_trade_reasoning",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("performance_id", sa.String(36), sa.ForeignKey("bot_model_performance.id"), nullable=False),
        sa.Column("node_name", sa.String(64), nullable=False),
        sa.Column("node_output", sa.JSON, nullable=True),
        sa.Column("model_used", sa.String(64), nullable=True),
        sa.Column("tokens_used", sa.Integer, nullable=True),
        sa.Column("latency_ms", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime),
    )

def downgrade():
    op.drop_table("ai_trade_reasoning")
    op.drop_table("bot_model_performance")
    op.drop_column("cerberus_bots", "ai_brain_config")
```

- [ ] **Step 4: Run migration**

```bash
cd ~/adaptive-trading-ecosystem && alembic upgrade head
```

- [ ] **Step 5: Commit**

```bash
git add db/cerberus_models.py alembic/versions/010_ai_brain_tables.py
git commit -m "feat(db): add AI Brain tables — ai_brain_config, bot_model_performance, ai_trade_reasoning"
```

---

## Task 2: AITradingEngine Types & Service

**Files:**
- Create: `services/ai_brain/__init__.py`
- Create: `services/ai_brain/types.py`
- Create: `services/ai_brain/engine.py`

- [ ] **Step 1: Create types module**

`services/ai_brain/__init__.py`:
```python
from services.ai_brain.types import AITradeDecision, AIBrainConfig
from services.ai_brain.engine import AITradingEngine

__all__ = ["AITradeDecision", "AIBrainConfig", "AITradingEngine"]
```

`services/ai_brain/types.py`:
```python
"""Data types for the AI Brain trading engine."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class AITradeDecision:
    """Structured decision output from AITradingEngine."""
    action: str              # BUY, SELL, HOLD, EXIT
    symbol: str
    quantity: float
    confidence: float        # 0.0 - 1.0
    reasoning_summary: str   # 2-3 sentence summary (Tier B)
    reasoning_full: dict = field(default_factory=dict)   # Node-by-node breakdown (Tier C)
    data_contributions: dict = field(default_factory=dict)  # Source weights
    model_used: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "action": self.action,
            "symbol": self.symbol,
            "quantity": self.quantity,
            "confidence": self.confidence,
            "reasoning_summary": self.reasoning_summary,
            "reasoning_full": self.reasoning_full,
            "data_contributions": self.data_contributions,
            "model_used": self.model_used,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class AIBrainConfig:
    """Parsed ai_brain_config from CerberusBot."""
    execution_mode: str = "manual"
    data_sources: list[str] = field(default_factory=lambda: ["technical"])
    trading_thesis: str = ""
    primary_model: str = "gpt-5.4"
    ensemble_mode: bool = False
    ensemble_models: list[str] = field(default_factory=list)
    comparison_models: list[str] = field(default_factory=list)
    universe_mode: str = "fixed"
    universe_symbols: list[str] = field(default_factory=list)
    universe_blacklist: list[str] = field(default_factory=list)
    max_trades_per_day: int = 10
    max_position_pct: float = 10.0
    allowed_sides: list[str] = field(default_factory=lambda: ["long", "short"])

    @classmethod
    def from_json(cls, data: dict | None) -> AIBrainConfig:
        if not data:
            return cls()
        model_config = data.get("model_config", {})
        universe = data.get("universe", {})
        constraints = data.get("constraints", {})
        return cls(
            execution_mode=data.get("execution_mode", "manual"),
            data_sources=data.get("data_sources", ["technical"]),
            trading_thesis=data.get("trading_thesis", ""),
            primary_model=model_config.get("primary_model", "gpt-5.4"),
            ensemble_mode=model_config.get("ensemble_mode", False),
            ensemble_models=model_config.get("ensemble_models", []),
            comparison_models=data.get("comparison_models", []),
            universe_mode=universe.get("mode", "fixed"),
            universe_symbols=universe.get("symbols", []),
            universe_blacklist=universe.get("blacklist", []),
            max_trades_per_day=constraints.get("max_trades_per_day", 10),
            max_position_pct=constraints.get("max_position_pct", 10.0),
            allowed_sides=constraints.get("allowed_sides", ["long", "short"]),
        )
```

- [ ] **Step 2: Create AITradingEngine**

`services/ai_brain/engine.py`:
```python
"""
AITradingEngine — orchestrates AI-driven trade decisions.

Gathers data based on bot focus profile, runs the multi-agent
pipeline with the bot's selected model, returns a structured decision.
"""
from __future__ import annotations

import time
from datetime import datetime
from typing import Optional

import structlog

from config.settings import get_settings
from services.ai_brain.types import AITradeDecision, AIBrainConfig

logger = structlog.get_logger(__name__)

# Maps data sources to pipeline nodes that should be skipped when absent
SOURCE_TO_NODES = {
    "technical": "technical_analyst",
    "sentiment": "sentiment_analyst",
    "fundamental": "fundamental_analyst",
}


class AITradingEngine:
    """Thin orchestrator for AI-driven trading decisions."""

    async def evaluate(
        self,
        bot,  # CerberusBot
        market_state: dict,
        model_override: Optional[str] = None,
    ) -> AITradeDecision:
        """
        Run the full AI decision pipeline for a bot.

        Args:
            bot: CerberusBot with ai_brain_config
            market_state: Dict with symbols, prices, indicators, positions, etc.
            model_override: Override model for shadow/comparison runs
        """
        config = AIBrainConfig.from_json(bot.ai_brain_config)
        model = model_override or config.primary_model
        start_time = time.monotonic()

        # Ensemble mode silently uses primary model in Phase 1
        if config.ensemble_mode:
            logger.info("ensemble_mode_ignored_phase1", bot_id=bot.id)

        # Resolve universe
        universe = self._resolve_universe(config, market_state)

        # Determine which pipeline nodes to skip
        all_sources = {"technical", "sentiment", "fundamental"}
        active_sources = set(config.data_sources) & all_sources
        skip_nodes = [
            SOURCE_TO_NODES[src]
            for src in all_sources - active_sources
            if src in SOURCE_TO_NODES
        ]

        # Build pipeline input state
        symbols = market_state.get("symbols", config.universe_symbols)
        if not symbols:
            return AITradeDecision(
                action="HOLD", symbol="", quantity=0, confidence=0,
                reasoning_summary="No symbols in universe to evaluate.",
                model_used=model,
            )

        # Inject macro + portfolio data into state if those sources are active
        macro_data = market_state.get("macro", {}) if "macro" in config.data_sources else {}
        portfolio_data = market_state.get("portfolio", {}) if "portfolio" in config.data_sources else {}

        # Run the multi-agent pipeline for each symbol
        from services.ai_core.multi_agent.runner import run_trade_analysis

        best_decision = AITradeDecision(
            action="HOLD", symbol="", quantity=0, confidence=0,
            reasoning_summary="No actionable signal found across symbols.",
            model_used=model,
        )

        for symbol in symbols:
            if symbol in config.universe_blacklist:
                continue

            try:
                result = await run_trade_analysis(
                    symbol=symbol,
                    action="BUY",  # AI decides the actual action
                    size=config.max_position_pct,
                    user_id=market_state.get("user_id", 0),
                    model_override=model,
                    skip_nodes=skip_nodes,
                    trading_thesis=config.trading_thesis,
                    macro_data=macro_data,
                    portfolio_data=portfolio_data,
                )

                if result is None:
                    continue

                # Map recommendation to action
                rec = (result.recommendation or "hold").lower()
                if rec in ("strong_buy", "buy"):
                    action = "BUY"
                elif rec in ("strong_sell", "sell"):
                    action = "SELL"
                elif rec == "exit":
                    action = "EXIT"
                else:
                    action = "HOLD"

                confidence = result.confidence or 0.0

                # Track the highest-confidence actionable signal
                if action != "HOLD" and confidence > best_decision.confidence:
                    # Build reasoning breakdown per node
                    reasoning_full = {}
                    if result.technical_report:
                        reasoning_full["technical_analyst"] = result.technical_report
                    if result.fundamental_report:
                        reasoning_full["fundamental_analyst"] = result.fundamental_report
                    if result.sentiment_report:
                        reasoning_full["sentiment_analyst"] = result.sentiment_report
                    if result.bull_case:
                        reasoning_full["bullish_researcher"] = result.bull_case
                    if result.bear_case:
                        reasoning_full["bearish_researcher"] = result.bear_case
                    if result.risk_assessment:
                        reasoning_full["risk_assessor"] = result.risk_assessment

                    best_decision = AITradeDecision(
                        action=action,
                        symbol=symbol,
                        quantity=0,  # Sizing done by BotRunner based on config
                        confidence=confidence,
                        reasoning_summary=result.reasoning or f"AI {rec} signal for {symbol}",
                        reasoning_full=reasoning_full,
                        data_contributions=self._extract_contributions(reasoning_full, config.data_sources),
                        model_used=model,
                    )

            except Exception as e:
                logger.error(
                    "ai_brain_symbol_eval_error",
                    bot_id=bot.id, symbol=symbol, model=model, error=str(e),
                )
                continue

        # Validate universe
        if best_decision.action != "HOLD" and universe:
            if best_decision.symbol not in universe:
                logger.warning(
                    "ai_decision_outside_universe",
                    bot_id=bot.id, symbol=best_decision.symbol,
                    universe_size=len(universe),
                )
                return AITradeDecision(
                    action="HOLD", symbol=best_decision.symbol, quantity=0,
                    confidence=0,
                    reasoning_summary=f"Symbol {best_decision.symbol} not in configured universe.",
                    model_used=model,
                )

        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        logger.info(
            "ai_brain_evaluation_complete",
            bot_id=bot.id, model=model,
            action=best_decision.action, symbol=best_decision.symbol,
            confidence=best_decision.confidence, elapsed_ms=elapsed_ms,
        )
        return best_decision

    def _resolve_universe(self, config: AIBrainConfig, market_state: dict) -> set[str]:
        """Resolve universe config to a concrete set of allowed symbols."""
        if config.universe_mode == "fixed":
            return set(config.universe_symbols)
        elif config.universe_mode == "ai":
            return set()  # No restriction — AI picks freely
        else:
            # sector/index modes: use symbols from market_state if provided
            return set(market_state.get("universe_symbols", []))

    def _extract_contributions(self, reasoning_full: dict, data_sources: list[str]) -> dict:
        """Estimate which data sources contributed to the decision."""
        contributions = {}
        source_map = {
            "technical_analyst": "technical",
            "fundamental_analyst": "fundamental",
            "sentiment_analyst": "sentiment",
        }
        active_count = sum(1 for k in reasoning_full if k in source_map and source_map[k] in data_sources)
        if active_count == 0:
            return contributions
        weight = round(1.0 / active_count, 2)
        for node, source in source_map.items():
            if node in reasoning_full and source in data_sources:
                contributions[source] = weight
        return contributions
```

- [ ] **Step 3: Commit**

```bash
git add services/ai_brain/
git commit -m "feat: add AITradingEngine service with types and orchestration logic"
```

---

## Task 3: Multi-Agent Pipeline Updates

**Files:**
- Modify: `services/ai_core/multi_agent/state.py` (lines 12-49)
- Modify: `services/ai_core/multi_agent/runner.py` (lines 18-100+)
- Modify: `services/ai_core/multi_agent/graph.py` (lines 37-91)
- Modify: `services/ai_core/multi_agent/nodes.py` (LLM calls)

- [ ] **Step 1: Update state schema**

In `state.py`, add to TradeAnalysisState TypedDict (after existing fields):
```python
# AI Brain fields
trading_thesis: str            # Natural language thesis from bot config
model_override: str            # Model to use instead of default
skip_nodes: list[str]          # Nodes to skip based on data source config
macro_data: dict               # VIX, Fed calendar, breadth (if macro source active)
portfolio_data: dict           # Positions, exposure, P&L (if portfolio source active)
```

- [ ] **Step 2: Update runner to accept new params**

In `runner.py` `run_trade_analysis()`, add parameters:
```python
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
```

Add these to initial_state:
```python
initial_state["trading_thesis"] = trading_thesis
initial_state["model_override"] = model_override
initial_state["skip_nodes"] = skip_nodes or []
initial_state["macro_data"] = macro_data or {}
initial_state["portfolio_data"] = portfolio_data or {}
```

- [ ] **Step 3: Add node skipping to graph**

In `graph.py` `build_trade_analysis_graph()`, modify each node function to check skip_nodes.
Wrap each node registration with a skip-check wrapper:

```python
def _make_skippable(node_fn, node_name):
    """Wrap a node to return empty output if it's in skip_nodes."""
    async def wrapper(state):
        if node_name in state.get("skip_nodes", []):
            return {f"{node_name.replace('_analyst', '')}_report": "", "node_trace": [f"{node_name}: SKIPPED"]}
        return await node_fn(state)
    wrapper.__name__ = node_fn.__name__
    return wrapper
```

Apply to each analyst node registration:
```python
graph.add_node("technical_analyst", _make_skippable(technical_analyst, "technical_analyst"))
graph.add_node("fundamental_analyst", _make_skippable(fundamental_analyst, "fundamental_analyst"))
graph.add_node("sentiment_analyst", _make_skippable(sentiment_analyst, "sentiment_analyst"))
```

- [ ] **Step 4: Pass model_override through nodes**

In `nodes.py`, update `_call_llm()` to check state for model_override:
```python
async def _call_llm(system_prompt: str, user_prompt: str, state: dict = None) -> str:
    model = (state or {}).get("model_override", "")
    # If model_override is set, use it directly
    if model:
        # Route through ModelRouter with explicit model
        ...
    # Existing routing logic
```

- [ ] **Step 5: Commit**

```bash
git add services/ai_core/multi_agent/
git commit -m "feat: add skip_nodes, model_override, and trading_thesis to multi-agent pipeline"
```

---

## Task 4: BotRunner Integration

**Files:**
- Modify: `services/bot_engine/runner.py` (lines 54-62, 156-235)

- [ ] **Step 1: Add AITradingEngine to BotRunner.__init__**

At line 62, after `self._reasoning_engine = ReasoningEngine()`:
```python
from services.ai_brain import AITradingEngine
self._ai_engine = AITradingEngine()
self._background_tasks: set[asyncio.Task] = set()
```

- [ ] **Step 2: Add ai_driven routing to _evaluate_bot**

At line 215, before the existing `if strategy_type in ("ai_generated", "custom"):` block, add:
```python
# ── AI Brain routing ──────────────────────────────────────────────
if bot.ai_brain_config:
    brain_config = bot.ai_brain_config
    exec_mode = brain_config.get("execution_mode", "manual")

    if exec_mode in ("ai_driven", "ai_assisted"):
        if exec_mode == "ai_assisted":
            # In assisted mode, only proceed if rule conditions triggered
            if strategy_type not in ("ai_generated", "custom") and not conditions:
                pass  # Fall through to manual path
            else:
                signal = evaluate_conditions(indicator_values, conditions) if conditions else True
                if not signal:
                    self._last_eval[bot.id] = datetime.utcnow()
                    return

        # Build market state for AITradingEngine
        market_state = {
            "symbols": symbols,
            "user_id": bot.user_id,
            "macro": risk_context,
            "portfolio": risk_context,
        }

        decision = await self._ai_engine.evaluate(bot, market_state)

        # Record every AI decision
        await self._record_ai_decision(bot, decision, is_shadow=False)

        # Execute actionable decisions
        if decision.action in ("BUY", "SELL", "EXIT"):
            trading_mode = await self._resolve_trading_mode(bot.user_id, bot_id=bot.id)
            re_decision = await self._reasoning_engine.evaluate(
                bot=bot, symbol=decision.symbol, signal=decision.action,
                strategy_config=config, vix=risk_context.get("vix"),
                portfolio_exposure=self._calculate_symbol_exposure(
                    risk_context, decision.symbol,
                    market_state.get("prices", {}).get(decision.symbol, 0),
                ),
                daily_pnl_pct=float(risk_context.get("daily_pnl_pct") or 0.0),
                trading_mode=trading_mode,
            )

            if re_decision.decision == "PAUSE_BOT":
                await self._pause_bot(bot.id, re_decision.reasoning)
            elif re_decision.decision not in ("EXIT_POSITION", "DELAY_TRADE"):
                adjusted_size = position_size_pct * re_decision.size_adjustment * decision.confidence
                executed = await self._execute_trade(
                    bot, decision.symbol, decision.action, adjusted_size,
                    market_state.get("prices", {}).get(decision.symbol, 0),
                    reasons=[f"AI Brain: {decision.reasoning_summary} (conf: {decision.confidence:.0%})"],
                    extended_hours=extended_hours,
                )
                if executed:
                    self._publish_activity(
                        "trade_executed", bot, decision.symbol,
                        f"{bot.name} AI Brain {decision.action} {decision.symbol} (conf: {decision.confidence:.0%})",
                        {"action": decision.action, "confidence": decision.confidence,
                         "model": decision.model_used, "reasoning": decision.reasoning_summary},
                    )

        # Fire shadow model comparisons (non-blocking)
        comparison_models = brain_config.get("comparison_models", [])
        for shadow_model in comparison_models:
            task = asyncio.create_task(
                self._run_shadow_evaluation(bot, market_state, shadow_model)
            )
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)

        self._last_eval[bot.id] = datetime.utcnow()
        return
```

- [ ] **Step 3: Add helper methods**

Add to BotRunner class:
```python
async def _run_shadow_evaluation(
    self, bot, market_state: dict, model: str,
) -> None:
    """Run shadow model evaluation — fire-and-forget, errors logged not raised."""
    try:
        decision = await self._ai_engine.evaluate(bot, market_state, model_override=model)
        await self._record_ai_decision(bot, decision, is_shadow=True)
    except Exception as e:
        logger.error("shadow_eval_error", bot_id=bot.id, model=model, error=str(e))

async def _record_ai_decision(
    self, bot, decision, is_shadow: bool = False,
) -> None:
    """Persist AI decision to bot_model_performance + ai_trade_reasoning."""
    from db.cerberus_models import BotModelPerformance, AITradeReasoning
    try:
        async with get_session() as session:
            perf = BotModelPerformance(
                bot_id=bot.id,
                model_used=decision.model_used,
                symbol=decision.symbol,
                action=decision.action,
                confidence=decision.confidence,
                reasoning_summary=decision.reasoning_summary,
                entry_price=0,  # Will be set from market data
                is_shadow=is_shadow,
                decided_at=datetime.utcnow(),
            )
            session.add(perf)
            await session.flush()

            # Store per-node reasoning for Tier C
            for node_name, output in decision.reasoning_full.items():
                reasoning = AITradeReasoning(
                    performance_id=perf.id,
                    node_name=node_name,
                    node_output={"report": output} if isinstance(output, str) else output,
                    model_used=decision.model_used,
                )
                session.add(reasoning)
    except Exception as e:
        logger.error("record_ai_decision_error", bot_id=bot.id, error=str(e))
```

- [ ] **Step 4: Commit**

```bash
git add services/bot_engine/runner.py
git commit -m "feat: integrate AITradingEngine into BotRunner with shadow model support"
```

---

## Task 5: API Routes

**Files:**
- Modify: `api/routes/ai_tools.py`

- [ ] **Step 1: Add AI Brain endpoints**

Add after existing bot endpoints:
```python
@router.patch("/bots/{bot_id}/ai-config")
async def update_ai_config(bot_id: str, request: Request):
    """Update a bot's AI Brain configuration."""
    user_id = request.state.user_id
    body = await request.json()
    async with get_session() as session:
        result = await session.execute(
            select(CerberusBot).where(CerberusBot.id == bot_id, CerberusBot.user_id == user_id)
        )
        bot = result.scalar_one_or_none()
        if not bot:
            raise HTTPException(404, "Bot not found")
        bot.ai_brain_config = body
    return {"status": "updated", "bot_id": bot_id}


@router.post("/bots/{bot_id}/ai-preview")
async def ai_preview(bot_id: str, request: Request):
    """Run AITradingEngine without executing — preview what AI would do."""
    user_id = request.state.user_id
    async with get_session() as session:
        result = await session.execute(
            select(CerberusBot).where(CerberusBot.id == bot_id, CerberusBot.user_id == user_id)
        )
        bot = result.scalar_one_or_none()
        if not bot:
            raise HTTPException(404, "Bot not found")
        if not bot.ai_brain_config:
            raise HTTPException(400, "Bot has no AI Brain config")

    from services.ai_brain import AITradingEngine
    engine = AITradingEngine()
    config = bot.ai_brain_config
    symbols = config.get("universe", {}).get("symbols", [])
    decision = await engine.evaluate(bot, {"symbols": symbols, "user_id": user_id})
    return {
        "decision": decision.to_dict(),
        "note": "Preview uses live data. Actual bot decisions may differ due to timing.",
    }


@router.get("/bots/{bot_id}/model-comparison")
async def model_comparison(bot_id: str, request: Request):
    """Get model comparison leaderboard for a bot."""
    user_id = request.state.user_id
    from db.cerberus_models import BotModelPerformance
    from sqlalchemy import func

    async with get_session() as session:
        # Verify ownership
        bot = (await session.execute(
            select(CerberusBot).where(CerberusBot.id == bot_id, CerberusBot.user_id == user_id)
        )).scalar_one_or_none()
        if not bot:
            raise HTTPException(404, "Bot not found")

        # Aggregate per model
        result = await session.execute(
            select(
                BotModelPerformance.model_used,
                BotModelPerformance.is_shadow,
                func.count().label("total_decisions"),
                func.avg(BotModelPerformance.confidence).label("avg_confidence"),
                func.sum(BotModelPerformance.pnl).label("total_pnl"),
            )
            .where(BotModelPerformance.bot_id == bot_id)
            .group_by(BotModelPerformance.model_used, BotModelPerformance.is_shadow)
        )
        rows = result.all()

    models = []
    primary_model = (bot.ai_brain_config or {}).get("model_config", {}).get("primary_model", "")
    for row in rows:
        resolved = await session.execute(
            select(func.count())
            .where(
                BotModelPerformance.bot_id == bot_id,
                BotModelPerformance.model_used == row.model_used,
                BotModelPerformance.resolved_at.isnot(None),
                BotModelPerformance.pnl > 0,
            )
        )
        wins = resolved.scalar() or 0
        total_resolved = await session.execute(
            select(func.count())
            .where(
                BotModelPerformance.bot_id == bot_id,
                BotModelPerformance.model_used == row.model_used,
                BotModelPerformance.resolved_at.isnot(None),
            )
        )
        total_res = total_resolved.scalar() or 0

        models.append({
            "model": row.model_used,
            "is_primary": row.model_used == primary_model,
            "total_decisions": row.total_decisions,
            "win_rate": round(wins / total_res, 2) if total_res > 0 else None,
            "avg_confidence": round(float(row.avg_confidence or 0), 2),
            "total_pnl": round(float(row.total_pnl or 0), 2),
        })

    return {"bot_id": bot_id, "models": models}


@router.get("/bots/{bot_id}/ai-reasoning/{decision_id}")
async def get_ai_reasoning(bot_id: str, decision_id: str, request: Request):
    """Get full Tier C reasoning for a specific AI decision."""
    user_id = request.state.user_id
    from db.cerberus_models import BotModelPerformance, AITradeReasoning

    async with get_session() as session:
        # Verify ownership
        perf = (await session.execute(
            select(BotModelPerformance)
            .join(CerberusBot, CerberusBot.id == BotModelPerformance.bot_id)
            .where(
                BotModelPerformance.id == decision_id,
                BotModelPerformance.bot_id == bot_id,
                CerberusBot.user_id == user_id,
            )
        )).scalar_one_or_none()
        if not perf:
            raise HTTPException(404, "Decision not found")

        reasoning_rows = (await session.execute(
            select(AITradeReasoning)
            .where(AITradeReasoning.performance_id == decision_id)
            .order_by(AITradeReasoning.created_at)
        )).scalars().all()

    return {
        "decision_id": decision_id,
        "model_used": perf.model_used,
        "action": perf.action,
        "symbol": perf.symbol,
        "confidence": perf.confidence,
        "nodes": [
            {
                "name": r.node_name,
                "output": r.node_output,
                "model": r.model_used,
                "tokens": r.tokens_used,
                "latency_ms": r.latency_ms,
            }
            for r in reasoning_rows
        ],
    }
```

- [ ] **Step 2: Update deploy endpoint**

In the existing `deploy_bot()` at line 777, add handling for ai_brain_config:
```python
# After existing universe_config handling:
if body and body.get("ai_brain_config"):
    bot.ai_brain_config = body["ai_brain_config"]
```

- [ ] **Step 3: Commit**

```bash
git add api/routes/ai_tools.py
git commit -m "feat(api): add AI Brain endpoints — ai-config, ai-preview, model-comparison, ai-reasoning"
```

---

## Task 6: Frontend — DeployConfigModal Updates

**Files:**
- Modify: `frontend/src/components/bots/DeployConfigModal.tsx`

- [ ] **Step 1: Add AI Brain state and controls**

Add new state after existing state declarations (~line 88):
```typescript
// AI Brain state
const [aiBrainEnabled, setAiBrainEnabled] = useState(false);
const [primaryModel, setPrimaryModel] = useState("gpt-5.4");
const [dataSources, setDataSources] = useState<string[]>(["technical", "sentiment", "fundamental", "macro", "portfolio"]);
const [tradingThesis, setTradingThesis] = useState("");
const [showAdvanced, setShowAdvanced] = useState(false);
const [comparisonModels, setComparisonModels] = useState<string[]>([]);
```

Add model options constant:
```typescript
const AI_MODELS = [
  { value: "gpt-5.4", label: "GPT-5.4 (Primary)" },
  { value: "claude-sonnet-4-6", label: "Claude Sonnet 4.6" },
  { value: "gpt-4.1", label: "GPT-4.1 (Fast)" },
  { value: "deepseek-r1", label: "DeepSeek R1" },
];

const DATA_SOURCE_OPTIONS = [
  { value: "technical", label: "Technical", desc: "RSI, MACD, BBands, support/resistance" },
  { value: "sentiment", label: "Sentiment", desc: "News, social media, options flow" },
  { value: "fundamental", label: "Fundamental", desc: "Earnings, P/E, revenue" },
  { value: "macro", label: "Macro", desc: "VIX, Fed calendar, market breadth" },
  { value: "portfolio", label: "Portfolio", desc: "Current positions, exposure, P&L" },
];
```

- [ ] **Step 2: Update Full Autonomy description and add AI controls**

Update OVERRIDE_OPTIONS for "full":
```typescript
{
  value: "full",
  label: "Full Autonomy",
  description: "AI analyzes markets and makes all trading decisions autonomously",
},
```

After override level selector, add AI Brain controls (shown when overrideLevel === "full"):
```typescript
{overrideLevel === "full" && (
  <div className="space-y-4 mt-4 p-4 rounded-lg bg-zinc-800/50 border border-zinc-700">
    <h4 className="text-sm font-medium text-zinc-300 flex items-center gap-2">
      <Cpu className="w-4 h-4" /> AI Brain Configuration
    </h4>

    {/* Model Selection */}
    <div>
      <label className="text-xs text-zinc-400 block mb-1">AI Model</label>
      <select
        value={primaryModel}
        onChange={(e) => setPrimaryModel(e.target.value)}
        className="w-full bg-zinc-900 border border-zinc-700 rounded px-3 py-2 text-sm text-white"
      >
        {AI_MODELS.map((m) => (
          <option key={m.value} value={m.value}>{m.label}</option>
        ))}
      </select>
    </div>

    {/* Data Sources */}
    <div>
      <label className="text-xs text-zinc-400 block mb-2">Data Sources</label>
      <div className="grid grid-cols-2 gap-2">
        {DATA_SOURCE_OPTIONS.map((src) => (
          <label
            key={src.value}
            className={`flex items-start gap-2 p-2 rounded border cursor-pointer transition-colors ${
              dataSources.includes(src.value)
                ? "border-blue-500 bg-blue-500/10"
                : "border-zinc-700 bg-zinc-900"
            }`}
          >
            <input
              type="checkbox"
              checked={dataSources.includes(src.value)}
              onChange={(e) => {
                setDataSources(
                  e.target.checked
                    ? [...dataSources, src.value]
                    : dataSources.filter((s) => s !== src.value)
                );
              }}
              className="mt-0.5"
            />
            <div>
              <span className="text-sm text-white">{src.label}</span>
              <p className="text-xs text-zinc-500">{src.desc}</p>
            </div>
          </label>
        ))}
      </div>
    </div>

    {/* Trading Thesis */}
    <div>
      <label className="text-xs text-zinc-400 block mb-1">Trading Thesis</label>
      <textarea
        value={tradingThesis}
        onChange={(e) => setTradingThesis(e.target.value)}
        placeholder="e.g., Trade large-cap tech stocks based on earnings surprises..."
        className="w-full bg-zinc-900 border border-zinc-700 rounded px-3 py-2 text-sm text-white h-20 resize-none"
      />
    </div>

    {/* Advanced Toggle */}
    <button
      type="button"
      onClick={() => setShowAdvanced(!showAdvanced)}
      className="text-xs text-blue-400 hover:text-blue-300"
    >
      {showAdvanced ? "Hide" : "Show"} Advanced Options
    </button>

    {showAdvanced && (
      <div className="space-y-3">
        <div>
          <label className="text-xs text-zinc-400 block mb-1">Comparison Models (shadow paper runs)</label>
          <div className="space-y-1">
            {AI_MODELS.filter((m) => m.value !== primaryModel).map((m) => (
              <label key={m.value} className="flex items-center gap-2 text-sm text-zinc-300">
                <input
                  type="checkbox"
                  checked={comparisonModels.includes(m.value)}
                  onChange={(e) => {
                    setComparisonModels(
                      e.target.checked
                        ? [...comparisonModels, m.value]
                        : comparisonModels.filter((v) => v !== m.value)
                    );
                  }}
                />
                {m.label}
              </label>
            ))}
          </div>
        </div>
      </div>
    )}
  </div>
)}
```

- [ ] **Step 3: Update deploy handler to include ai_brain_config**

In the onDeploy callback, when overrideLevel === "full", include:
```typescript
const deployConfig: DeployConfig = {
  universeConfig: { /* existing */ },
  overrideLevel,
  allocatedCapital,
  extendedHours,
};

// Add AI Brain config when Full Autonomy
if (overrideLevel === "full") {
  (deployConfig as any).aiBrainConfig = {
    execution_mode: "ai_driven",
    data_sources: dataSources,
    trading_thesis: tradingThesis,
    model_config: {
      primary_model: primaryModel,
      ensemble_mode: false,
      ensemble_models: [],
      auto_route: false,
    },
    comparison_models: comparisonModels,
    universe: {
      mode: universeMode,
      symbols: universeMode === "fixed" ? symbolsText.split(",").map(s => s.trim()).filter(Boolean) : [],
      blacklist: blacklistText.split(",").map(s => s.trim()).filter(Boolean),
    },
    constraints: {
      max_trades_per_day: 10,
      max_position_pct: 10,
      allowed_sides: ["long", "short"],
    },
  };
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/bots/DeployConfigModal.tsx
git commit -m "feat(ui): add AI Brain controls to DeployConfigModal — model, data sources, thesis"
```

---

## Task 7: Frontend — AIReasoningPanel & ModelLeaderboard

**Files:**
- Create: `frontend/src/components/bots/AIReasoningPanel.tsx`
- Create: `frontend/src/components/bots/ModelLeaderboard.tsx`
- Create: `frontend/src/components/bots/AIPreviewButton.tsx`

- [ ] **Step 1: Create AIReasoningPanel**

`frontend/src/components/bots/AIReasoningPanel.tsx` — shows Tier B summary by default with expandable Tier C node breakdown. Confidence badge, reasoning summary, data contribution bars. Expandable section shows each analyst node's output.

- [ ] **Step 2: Create ModelLeaderboard**

`frontend/src/components/bots/ModelLeaderboard.tsx` — fetches `/bots/{id}/model-comparison`, renders table with model name, total decisions, win rate, avg confidence, total P&L, "Use This Model" button.

- [ ] **Step 3: Create AIPreviewButton**

`frontend/src/components/bots/AIPreviewButton.tsx` — button that calls `/bots/{id}/ai-preview`, shows loading spinner, then renders result in AIReasoningPanel.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/bots/AIReasoningPanel.tsx frontend/src/components/bots/ModelLeaderboard.tsx frontend/src/components/bots/AIPreviewButton.tsx
git commit -m "feat(ui): add AIReasoningPanel, ModelLeaderboard, and AIPreviewButton components"
```

---

## Task 8: Shadow P&L Resolver

**Files:**
- Create: `services/ai_brain/shadow_resolver.py`

- [ ] **Step 1: Create shadow resolver background task**

Background task that runs every 5 minutes to resolve shadow model P&L via mark-to-market:
- Find unresolved BUY/SELL shadow decisions
- Fetch current prices
- Apply time-based exit (resolve after bot's timeframe interval)
- Calculate P&L and set resolved_at

- [ ] **Step 2: Wire into BotRunner startup**

Add shadow resolver as a background task that starts when BotRunner starts.

- [ ] **Step 3: Commit**

```bash
git add services/ai_brain/shadow_resolver.py services/bot_engine/runner.py
git commit -m "feat: add shadow P&L resolver background task for model comparison"
```

---

## Task 9: Integration Testing & Final Verification

- [ ] **Step 1: Run backend**

```bash
cd ~/adaptive-trading-ecosystem && python3 -m uvicorn api.main:app --port 8000
```

Verify: server starts without import errors.

- [ ] **Step 2: Run migration**

```bash
cd ~/adaptive-trading-ecosystem && alembic upgrade head
```

Verify: migration applies cleanly.

- [ ] **Step 3: Test API endpoints**

```bash
# Create a bot with AI Brain config
curl -X PATCH http://localhost:8000/api/bots/<bot_id>/ai-config \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"execution_mode":"ai_driven","data_sources":["technical"],"model_config":{"primary_model":"gpt-5.4"}}'

# Preview
curl -X POST http://localhost:8000/api/bots/<bot_id>/ai-preview \
  -H "Authorization: Bearer <token>"

# Model comparison
curl http://localhost:8000/api/bots/<bot_id>/model-comparison \
  -H "Authorization: Bearer <token>"
```

- [ ] **Step 4: Run frontend**

```bash
cd ~/adaptive-trading-ecosystem/frontend && npm run dev
```

Verify: no build errors, DeployConfigModal shows AI Brain controls when Full Autonomy selected.

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "feat: AI Brain feature — complete Phase 1 implementation"
```
