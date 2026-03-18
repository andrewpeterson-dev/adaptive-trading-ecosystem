# AI Brain Feature — Design Specification

**Date:** 2026-03-18
**Status:** Draft
**Author:** Andrew Peterson + Claude

## Overview

Transform the Adaptive Trading Ecosystem's AI from a passive gatekeeper (ReasoningEngine blocks/delays trades) into an active trading brain that analyzes markets, decides entries/exits/sizing, and manages positions autonomously. Add per-bot model selection, side-by-side model comparison, and a tiered reasoning UI.

## Success Criteria (Phase 1)

1. Create a bot in the AI Builder, pick an LLM, define a trading thesis + data sources, deploy in paper mode, and see it making autonomous trade decisions with full reasoning
2. Deploy the same bot with 2-3 different models in paper mode and see a comparison dashboard/leaderboard
3. "Full Autonomy" in DeployConfigModal means "AI is the trader" — not just "remove guardrails"

## Current State

- Bots are rule-based: conditions trigger → ReasoningEngine rubber-stamps or blocks → trade executes
- AI is only a risk filter — it can BLOCK trades but never INITIATE them
- `_ai_evaluate_bot()` in BotRunner exists for ai_generated strategies but still routes through ReasoningEngine as gatekeeper
- LangGraph 7-node multi-agent pipeline exists but only for analysis reports, not live trading
- DeployConfigModal has 3 override levels but "Full Autonomy" only lets AI block/delay/reduce
- `reasoning_model_config` JSON field exists on CerberusBot but is underutilized

## Architecture: Approach 2 — AITradingEngine (Parallel Service)

### Why This Approach

A new `AITradingEngine` service sits parallel to ReasoningEngine. When a bot's execution mode is `ai_driven`, BotRunner routes to AITradingEngine instead of the condition evaluator. ReasoningEngine still applies as a safety layer after the AI makes its decision.

Rejected alternatives:
- **Extend existing (Approach 1):** runner.py is 71KB — can't absorb more logic. Model comparison requires calling decision logic independently from BotRunner's loop, which means extracting it anyway.
- **Microservice split (Approach 3):** Overengineered for a solo developer. Adds latency, deployment complexity, and failure modes without proportional benefit.

### Execution Flow

```
BotRunner._evaluate_bot()
  ├── mode="manual"      → evaluate_conditions() → ReasoningEngine (gatekeeper) → execute
  ├── mode="ai_assisted"  → evaluate_conditions() → AITradingEngine (enhance) → ReasoningEngine → execute
  └── mode="ai_driven"    → AITradingEngine (full decision) → ReasoningEngine (safety only) → execute
```

---

## 1. Execution Modes

Three execution modes replace the current override level semantics:

| Mode | Who Decides | AI Role | Current Mapping |
|------|------------|---------|-----------------|
| `manual` | Rule conditions | None (or advisory logging) | override_level="advisory" |
| `ai_assisted` | Rules trigger, AI enhances | Skip weak signals, adjust sizing, suggest exits | override_level="soft" |
| `ai_driven` | AI decides everything | Picks entries, exits, sizing, timing | override_level="full" |

Backward compatibility: existing bots with override_level="full" continue to work as before. Only bots with `ai_brain_config` populated use the new AI-driven path.

---

## 2. Bot Configuration — ai_brain_config

New JSON field on `CerberusBot`:

```json
{
    "execution_mode": "ai_driven",
    "data_sources": ["technical", "sentiment", "fundamental", "macro", "portfolio"],
    "trading_thesis": "Trade large-cap tech stocks based on earnings surprises and options flow",
    "model_config": {
        "primary_model": "gpt-5.4",
        "ensemble_mode": false,
        "ensemble_models": [],
        "auto_route": false
    },
    "comparison_models": ["claude-sonnet-4-6", "deepseek-r1"],
    "universe": {
        "mode": "fixed",
        "symbols": ["NVDA", "AAPL", "MSFT", "GOOGL"],
        "sectors": [],
        "blacklist": []
    },
    "constraints": {
        "max_trades_per_day": 5,
        "max_position_pct": 10,
        "allowed_sides": ["long", "short"]
    }
}
```

### Focus Profile (Data Sources)

Each bot declares which data sources the AI sees. Available sources:

| Source | What It Provides | Pipeline Node |
|--------|-----------------|---------------|
| `technical` | Price, volume, RSI, MACD, BBands, support/resistance | `technical_analyst` |
| `sentiment` | News sentiment, social media, options flow | `sentiment_analyst` |
| `fundamental` | Earnings, P/E, revenue, dividends | `fundamental_analyst` |
| `macro` | VIX, Fed calendar, market breadth, sector rotation | Injected into pipeline state (no dedicated node — data added to shared state dict before pipeline runs) |
| `portfolio` | Current positions, sector exposure, recent P&L, drawdown | Injected into pipeline state (no dedicated node — data added to shared state dict before pipeline runs) |

A "News Trader" bot might only have `["sentiment", "macro"]`. A "Technical Scalper" might only have `["technical", "portfolio"]`. The AI only sees data from selected sources — nodes for unselected sources are skipped entirely.

### Universe (Symbol Scoping)

Every ai_brain_config includes a `universe` field that constrains which symbols the AI can trade. This mirrors the existing `universe_config` on `CerberusBotVersion`:

- `mode: "fixed"` — explicit symbol list (e.g., `["NVDA", "AAPL"]`)
- `mode: "sector"` — symbols from specified sectors
- `mode: "index"` — S&P 500 / Nasdaq 100 constituents
- `mode: "ai"` — AI scans for opportunities (still limited by `blacklist`)

AITradingEngine validates every decision's symbol against the resolved universe. Decisions for out-of-universe symbols are rejected.

### Configuration Sources

- **AI Builder tab:** User picks data source checkboxes + writes a trading thesis prompt. System produces `ai_brain_config`.
- **Template tab:** Pre-built templates ("News Trader", "Momentum Scalper", "Earnings Player") produce pre-filled `ai_brain_config`. User can customize.
- **Manual tab:** Produces traditional `config_json` with rigid conditions. No `ai_brain_config` — bot runs in `manual` mode.

---

## 3. AITradingEngine Service

**Location:** `services/ai_brain/engine.py`

### Public Interface

```python
class AITradingEngine:
    async def evaluate(
        self,
        bot: CerberusBot,
        market_state: dict,
        model_override: Optional[str] = None
    ) -> AITradeDecision:
        """
        Main entry point. Gathers data based on bot's focus profile,
        runs the multi-agent pipeline with the bot's selected model,
        returns a structured trade decision.
        """
```

### Internal Flow

1. Read `bot.ai_brain_config` → determine `data_sources`, `model_config`, `trading_thesis`, `constraints`
1b. **Resolve universe:** Convert `universe` config to a concrete symbol set:
   - `mode: "fixed"` → use `symbols` list directly
   - `mode: "sector"` → query sector constituents from market data service
   - `mode: "index"` → query index constituents (S&P 500 / Nasdaq 100)
   - `mode: "ai"` → no pre-filter (AI picks freely, subject to `blacklist`)
   - Cache resolved universe for the duration of this evaluation cycle
2. Gather data (only requested sources):
   - `technical` → call indicators service (existing)
   - `sentiment` → call sentiment endpoint (flesh out stubbed node)
   - `fundamental` → call financial data service (flesh out stubbed node)
   - `macro` → fetch VIX, Fed calendar, breadth (existing data in ReasoningEngine)
   - `portfolio` → query current positions, sector exposure, recent P&L (existing)
3. Pack gathered data into LangGraph multi-agent pipeline state
4. Configure pipeline: skip nodes for absent data sources, set model per bot config
5. Run pipeline: `technical_analyst → sentiment_analyst → fundamental_analyst → bull/bear researchers → risk_assessor → decision_synthesizer`
6. Parse `decision_synthesizer` output into `AITradeDecision`
7. **Validate decision symbol** against resolved universe (from step 1b). Reject if out-of-universe (return HOLD with reasoning: "Symbol not in configured universe").
8. Return decision

### AITradeDecision

```python
@dataclass
class AITradeDecision:
    action: str              # "BUY", "SELL", "HOLD", "EXIT"
    symbol: str
    quantity: float          # Float to support fractional shares
    confidence: float        # 0.0 - 1.0
    reasoning_summary: str   # 2-3 sentences (Tier B display)
    reasoning_full: dict     # Node-by-node breakdown (Tier C expandable)
    data_contributions: dict # Which data sources drove the decision and their weight
    model_used: str
    timestamp: datetime
```

### Design Properties

- **Stateless:** All config comes from the bot, all data comes from services. No instance state.
- **Model-agnostic:** `model_override` parameter enables shadow/comparison runs with different models using the same data.
- **Fail-closed:** If any required data source is unavailable, return HOLD with reasoning. If model is unreachable, skip the cycle entirely.

---

## 4. BotRunner Integration

### Modified Evaluation Loop

In `BotRunner._evaluate_bot()`:

```python
if bot.ai_brain_config:
    mode = bot.ai_brain_config["execution_mode"]

    if mode == "ai_driven":
        # AI makes the full decision
        decision = await self.ai_engine.evaluate(bot, market_state)

        # Record every AI decision unconditionally (for leaderboard accuracy)
        await self._record_ai_decision(bot, decision, is_shadow=False)

        # Only route actionable decisions to execution
        # (Universe validation already done inside AITradingEngine — see Section 3, step 7)
        if decision.action in ("BUY", "SELL", "EXIT"):
            safety = await self.reasoning_engine.evaluate(decision, bot)
            if safety.action != "PAUSE_BOT":
                await self._execute_trade(decision, safety_adjustments=safety)

        # Run shadow models for comparison (fire-and-forget, non-blocking)
        # Store task references in self._background_tasks to prevent GC mid-run
        for model in bot.ai_brain_config.get("comparison_models", []):
            task = asyncio.create_task(self._run_shadow_evaluation(bot, market_state, model))
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)

    elif mode == "ai_assisted":
        # Rules trigger first, AI enhances
        signal = await self._evaluate_conditions(bot, market_state)
        if signal:
            decision = await self.ai_engine.evaluate(bot, market_state)
            # Record decision regardless of outcome (HOLD counts for leaderboard)
            await self._record_ai_decision(bot, decision, is_shadow=False)
            if decision.action in ("BUY", "SELL", "EXIT"):
                safety = await self.reasoning_engine.evaluate(decision, bot)
                if safety.action != "PAUSE_BOT":
                    await self._execute_trade(decision, safety_adjustments=safety)
else:
    # Existing manual path — unchanged
    await self._evaluate_conditions_and_execute(bot, market_state)
```

### Shadow Model Execution

- Shadow models run as `asyncio.create_task()` (fire-and-forget) — they do not block the main evaluation loop
- Shadow decisions are recorded with `is_shadow=True` — they never execute trades
- All shadow runs use the same market data snapshot as the primary (fair comparison)
- If a shadow task fails (model timeout, etc.), the error is logged but does not affect the primary bot

---

## 5. Multi-Agent Pipeline Updates

### Node Skipping

Pipeline accepts a `skip_nodes` set derived from bot's `data_sources`:

```python
# Mapping: if data source is missing, skip these nodes
SOURCE_TO_NODES = {
    "technical": ["technical_analyst"],
    "sentiment": ["sentiment_analyst"],
    "fundamental": ["fundamental_analyst"],
}
# bull/bear researchers, risk_assessor, decision_synthesizer always run
```

Skipped nodes return empty output — downstream nodes handle missing data gracefully.

### Stubbed Node Implementation

**`sentiment_analyst`** — wire to:
- FinGPT sentiment endpoint (already in ModelRouter)
- News API for headline sentiment
- Options flow data if available

**`fundamental_analyst`** — wire to:
- Earnings calendar (next earnings date, recent surprises)
- Basic ratios (P/E, revenue growth) from financial data API

### Model Selection Per Node

Each node uses the bot's configured model instead of the hardcoded default:

```python
model = bot.ai_brain_config["model_config"]["primary_model"]
# or model_override if running a shadow comparison
```

### Decision Synthesizer Output Change

Currently outputs a report. Must output a structured decision:

```python
{
    "action": "BUY",
    "symbol": "NVDA",
    "quantity": 50.0,
    "confidence": 0.82,
    "reasoning_summary": "Strong earnings beat + bullish options flow + technical breakout above resistance",
    "data_contributions": {
        "technical": 0.3,
        "sentiment": 0.5,
        "fundamental": 0.2
    }
}
```

---

## 6. Database Changes

### Modified: CerberusBot

```python
# New field
ai_brain_config = Column(JSON, nullable=True)  # Full focus profile (Section 2)
```

Existing `reasoning_model_config` stays for backward compatibility. For AI-driven bots, `ai_brain_config.model_config` is the source of truth.

### New Table: bot_model_performance

Tracks every AI decision (primary and shadow) for the comparison leaderboard:

```python
class BotModelPerformance(Base):
    __tablename__ = "bot_model_performance"

    id = Column(String(36), primary_key=True, default=_uuid)
    bot_id = Column(String(36), ForeignKey("cerberus_bots.id"))
    cerberus_trade_id = Column(String(36), ForeignKey("cerberus_trades.id"), nullable=True)  # Links to actual trade (primary only)
    model_used = Column(String, nullable=False)      # "gpt-5.4", "claude-sonnet-4-6"
    symbol = Column(String, nullable=False)
    action = Column(String, nullable=False)           # BUY, SELL, HOLD, EXIT
    confidence = Column(Float)
    reasoning_summary = Column(Text)
    entry_price = Column(Float)                       # Price at decision time
    exit_price = Column(Float, nullable=True)          # Filled when position closes or mark-to-market resolves
    pnl = Column(Float, nullable=True)                 # Filled when resolved
    is_shadow = Column(Boolean, default=False)         # True = comparison run
    decided_at = Column(DateTime, nullable=False)
    resolved_at = Column(DateTime, nullable=True)      # When P&L calculated

    __table_args__ = (
        Index("ix_bmp_bot_model", "bot_id", "model_used"),
        Index("ix_bmp_bot_resolved", "bot_id", "resolved_at"),
    )
```

### New Table: ai_trade_reasoning

Full reasoning chain for audit — the Tier C expandable data:

```python
class AITradeReasoning(Base):
    __tablename__ = "ai_trade_reasoning"

    id = Column(String(36), primary_key=True, default=_uuid)
    performance_id = Column(String(36), ForeignKey("bot_model_performance.id"))
    node_name = Column(String, nullable=False)         # "technical_analyst", etc.
    node_output = Column(JSON)                          # Full analysis from node
    model_used = Column(String)                         # Which model ran this node
    tokens_used = Column(Integer)
    latency_ms = Column(Integer)
    created_at = Column(DateTime)
```

### Why Two Tables

`bot_model_performance` stays lean for dashboard queries and leaderboard aggregation (frequent reads). `ai_trade_reasoning` is the heavy audit log — queried only when someone expands a specific decision's full reasoning.

### P&L Attribution

**Primary decisions (is_shadow=False):** When a trade executes, the resulting `CerberusTrade.id` is written to `cerberus_trade_id`. When the trade closes, `exit_price` and `pnl` are copied from the CerberusTrade record.

**Shadow decisions (is_shadow=True):** Shadow models never execute trades, so P&L uses mark-to-market. A background task runs every 5 minutes:
1. For open shadow BUY/SELL decisions without `resolved_at`, fetch current price
2. Apply a time-based exit rule: resolve after the bot's configured timeframe (e.g., 60min for a 1H bot) or when the primary model's corresponding position closes — whichever comes first
3. Calculate `pnl = (exit_price - entry_price) * quantity * direction` and set `resolved_at`

This ensures the leaderboard has comparable P&L data across primary and shadow models.

---

## 7. API Routes

### New Endpoints

| Endpoint | Method | Purpose | Request/Response |
|----------|--------|---------|-----------------|
| `/bots/{id}/ai-config` | PATCH | Update ai_brain_config | `{ data_sources, trading_thesis, model_config, comparison_models, constraints }` |
| `/bots/{id}/ai-preview` | POST | Run AITradingEngine without executing | Returns `AITradeDecision` |
| `/bots/{id}/model-comparison` | GET | Leaderboard for this bot | Returns aggregated metrics per model |
| `/bots/{id}/ai-reasoning/{decision_id}` | GET | Full Tier C reasoning | Returns `AITradeReasoning[]` for decision |

### Modified Endpoints

- `POST /bots/{id}/deploy` — accepts optional `ai_brain_config` in request body. If present, stores on bot and sets execution mode accordingly.
- `PATCH /bots/{id}/override-level` — backward compat: setting "full" on a bot with `ai_brain_config` maps to `execution_mode: "ai_driven"`.

### Leaderboard Response Shape

```json
{
    "bot_id": "abc-123",
    "models": [
        {
            "model": "gpt-5.4",
            "is_primary": true,
            "total_decisions": 142,
            "win_rate": 0.63,
            "avg_return_pct": 1.2,
            "sharpe_ratio": 1.8,
            "avg_confidence": 0.74,
            "confidence_calibration": 0.91,
            "total_pnl": 4280.50
        },
        {
            "model": "claude-sonnet-4-6",
            "is_primary": false,
            "total_decisions": 142,
            "win_rate": 0.58,
            "avg_return_pct": 0.9,
            "sharpe_ratio": 1.4,
            "avg_confidence": 0.81,
            "confidence_calibration": 0.72,
            "total_pnl": 2910.20
        }
    ]
}
```

---

## 8. Frontend Changes

### DeployConfigModal Updates

When "Full Autonomy" is selected:
- Description changes to: "AI analyzes markets and makes all trading decisions autonomously"
- **AI Model dropdown** appears — select primary model (GPT-5.4, Claude, Gemini, DeepSeek, etc.)
- **Data Sources checkboxes** — Technical, Sentiment, Fundamental, Macro, Portfolio
- **Advanced toggle** reveals:
  - Ensemble mode checkbox + model multi-select
  - Comparison models multi-select (for shadow paper runs)
  - Constraints (max trades/day, max position %, allowed sides)

### New Components

**`AIReasoningPanel`**
- Default view (Tier B): confidence badge + 2-3 sentence summary + data source contribution bars
- Expandable (Tier C): node-by-node breakdown showing each analyst's output, model used, tokens, latency

**`ModelLeaderboard`**
- Table comparing models on: win rate, avg return, Sharpe, total trades, confidence calibration, total P&L
- "Use This Model" button to promote a shadow model to primary
- Visual indicators (green/red) for relative performance

**`AIPreviewButton`**
- "What would AI do?" button on bot detail page
- Calls `/bots/{id}/ai-preview`, shows result in AIReasoningPanel
- Useful for testing config before deploying

### Bot Activity Feed Changes

- Each AI decision shows reasoning summary inline with model tag
- Shadow decisions shown in a separate "Model Comparison" tab
- Filter by model, confidence level, action type

---

## 9. Safety Constraints (Non-Negotiable)

All existing safety gates apply regardless of execution mode:

| Gate | Behavior | Applies To |
|------|----------|-----------|
| Kill switch | Immediate halt | All modes |
| Graduated drawdown | Pause bot | All modes |
| Sector concentration caps | Reject trade | All modes |
| Position size caps (25% max) | Enforce | All modes |
| Paper mode for new AI models | Required: min 50 decisions in `bot_model_performance` before live deploy allowed | AI-driven only |
| Full reasoning audit log | Every decision logged | AI-driven + AI-assisted |

### AI-Specific Safety

- **Token budget:** Max 50,000 tokens per evaluation cycle per bot. If exceeded mid-pipeline, truncate context and proceed with available data. If the model call itself exceeds budget, skip the cycle and log a warning. Configurable via `config/settings.py`.
- **Fail-closed:** If AI model is unreachable, skip cycle entirely (bots never trade blind)
- **Rate limit:** The 60s evaluation loop naturally limits to 1 eval/min/bot. The `/ai-preview` endpoint is rate-limited to 10 calls/min/user to prevent abuse.
- **Sentiment required in live mode:** Existing rule — if sentiment data unavailable in live mode, delay trade
- **Paper mode enforcement:** API layer rejects `POST /bots/{id}/deploy` with `execution_mode=ai_driven` in live mode if the selected model has fewer than 50 resolved decisions in `bot_model_performance` for this bot. Returns 400 with message directing user to paper mode.
- **Universe enforcement:** AITradingEngine validates every decision's symbol against `ai_brain_config.universe.symbols` (if set). Decisions for symbols outside the universe are rejected before reaching ReasoningEngine.
- **Ensemble fields in Phase 1:** `ensemble_mode` and `ensemble_models` fields are accepted and stored in `ai_brain_config` but silently ignored. If `ensemble_mode=true`, the engine uses only `primary_model` and logs a notice. Full ensemble support ships in Phase 2.

### Model Promotion Safety

When a user clicks "Use This Model" on the leaderboard to promote a shadow model to primary:
- Promotion takes effect at the start of the **next** evaluation cycle (not mid-cycle)
- The switch is recorded in `CerberusAuditLog` with old and new model
- If the bot is in live mode, a confirmation modal is shown: "Changing AI model on a live bot. This takes effect next cycle. Continue?"
- The promoted model must meet the same 50-decision paper threshold if switching to a model with insufficient history

### Confidence Calibration Metric

`confidence_calibration` in the leaderboard is computed as:

```
calibration = 1 - mean(abs(confidence - outcome))
```

Where `outcome = 1.0` if `pnl > 0`, `outcome = 0.0` otherwise. Computed over all resolved decisions for that model+bot pair. A score of 1.0 means the model's confidence perfectly predicts win/loss probability. Only computed when a model has >= 20 resolved decisions; otherwise returns `null`.

### AI Preview Endpoint

`POST /bots/{id}/ai-preview` uses **live market data** (not cached). The response includes a disclaimer: `"note": "Preview uses live data. Actual bot decisions may differ due to timing."` Rate-limited to 10 calls/min/user.

### Multi-Bot Collision

If two ai_driven bots target the same symbol, both may decide to BUY simultaneously. This is handled by existing sector concentration caps in ReasoningEngine — the second trade will be rejected if it would exceed the cap. Portfolio data source reflects **confirmed positions only** (not in-flight AI decisions from sibling bots). This is an acceptable simplification for Phase 1; Phase 2 can add an in-flight position lock if needed.

### Backtesting AI-Driven Bots

AI-driven bots **cannot be backtested** in Phase 1 because the multi-agent pipeline makes live API calls. The `backtest_required` flag is set to `false` for ai_driven bots. Paper mode serves as the validation mechanism instead. Phase 2 may add historical replay support with cached data.

---

## 10. Phased Implementation

### Phase 1 (This Build)

- [ ] AITradingEngine service (`services/ai_brain/engine.py`)
- [ ] `ai_brain_config` field on CerberusBot + Alembic migration
- [ ] `bot_model_performance` + `ai_trade_reasoning` tables + migration
- [ ] BotRunner integration (ai_driven + ai_assisted execution paths)
- [ ] Multi-agent pipeline: flesh out sentiment + fundamental nodes
- [ ] Multi-agent pipeline: node skipping + per-bot model selection
- [ ] Decision synthesizer: structured output (not report format)
- [ ] API routes: ai-config, ai-preview, model-comparison, ai-reasoning
- [ ] DeployConfigModal: model selection, data sources, advanced toggle
- [ ] AIReasoningPanel component (Tier B + expandable Tier C)
- [ ] ModelLeaderboard component
- [ ] AIPreviewButton component
- [ ] Bot activity feed: AI decision display with model tags
- [ ] Shadow P&L resolution background task (mark-to-market for shadow decisions)
- [ ] Paper mode enforcement gate (50-decision minimum before live deploy)
- [ ] Universe validation in AITradingEngine
- [ ] Alembic migration: fix BotStatus check constraint to include 'deleted'

### Phase 2 (Future)

- Ensemble voting (multiple models consensus before executing)
- Shadow mode (one model trades live, others shadow alongside)

### Phase 3 (Future)

- Auto-routing: system tracks per-model performance and routes new bots to the best performer
- Capital split: allocate capital across models proportional to performance

---

## Key Files (Existing)

| File | Role | Changes Needed |
|------|------|---------------|
| `services/bot_engine/runner.py` | Bot evaluation loop | Add ai_driven/ai_assisted routing |
| `services/reasoning_engine/engine.py` | Safety gatekeeper | No changes — stays as safety layer |
| `services/ai_core/model_router.py` | Model routing | Add TRADING_DECISION intent |
| `services/ai_core/multi_agent/graph.py` | LangGraph topology | Add skip_nodes support |
| `services/ai_core/multi_agent/nodes.py` | Pipeline nodes | Flesh out sentiment + fundamental |
| `services/ai_core/multi_agent/state.py` | Pipeline state | Add trading_thesis, model fields |
| `db/cerberus_models.py` | Bot ORM models | Add ai_brain_config field |
| `api/routes/ai_tools.py` | Bot API routes | Add new endpoints |
| `frontend/src/components/bots/DeployConfigModal.tsx` | Deploy UI | Add model/data source controls |

## New Files

| File | Purpose |
|------|---------|
| `services/ai_brain/__init__.py` | Package init |
| `services/ai_brain/engine.py` | AITradingEngine orchestrator |
| `services/ai_brain/types.py` | AITradeDecision, AIBrainConfig dataclasses |
| `frontend/src/components/bots/AIReasoningPanel.tsx` | Tiered reasoning display |
| `frontend/src/components/bots/ModelLeaderboard.tsx` | Model comparison table |
| `frontend/src/components/bots/AIPreviewButton.tsx` | Preview button component |
