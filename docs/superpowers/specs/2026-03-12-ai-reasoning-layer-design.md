# AI Reasoning Layer — Design Spec

## Overview

Redesign the trading bot architecture so bots use active AI reasoning instead of only scripted indicator conditions. Bots must think contextually about the market, recognize events that could affect their strategy, dynamically select which stocks to trade, and learn from their own performance over time.

The system adds four new engines on top of the existing rule-based strategy execution, without breaking any current features.

## Architecture

Four independent engines communicating through shared database state:

```
Context Monitor (background) → MarketEvent records
Universe Scanner (background) → UniverseCandidate records
Reasoning Engine (per-bot)    → TradeDecision records
BotRunner (existing, enhanced)→ gates execution through Reasoning Engine
```

The Context Monitor and Universe Scanner run continuously. Every bot benefits from shared market intelligence. The Reasoning Engine is called per-bot only when indicator conditions are being evaluated.

### Background Task Execution

The Context Monitor and Universe Scanner run as **asyncio background loops** inside the FastAPI lifespan, matching the existing BotRunner pattern (`api/main.py` lifespan). This avoids adding Celery beat infrastructure. Existing Celery workers remain for on-demand tasks (backtests, document ingestion, learning adaptation reviews).

---

## 1. Context Monitor

Always-on background service building a real-time picture of market conditions.

### Execution

Asyncio background loop in FastAPI lifespan. Every 2 minutes during market hours (9:00-16:30 ET), every 15 minutes outside hours.

### Data Sources

| Source | Cadence | Free? | What it catches |
|--------|---------|-------|-----------------|
| Finnhub `/news` | 2 min | Yes (existing key) | Breaking news, company events |
| Finnhub `/calendar/earnings` | 1 hour | Yes | Upcoming earnings dates |
| Finnhub `/calendar/economic` | 1 hour | Yes | FOMC, CPI, GDP, jobs |
| CNN Fear/Greed endpoint | 15 min | Yes (no key) | Market-wide risk sentiment |
| VIX via yfinance | 2 min | Yes (no key) | Volatility level |
| StockTwits public API | 5 min | Yes (no key) | Retail sentiment spikes |
| Sector ETFs (SPY, QQQ, XLF, etc.) | 2 min | Yes (yfinance) | Sector momentum, correlation |
| User-connected providers | Varies | User's key | Options flow, dark pool, premium news |

Pre-configured sources (CNN F/G, StockTwits, VIX, sector ETFs, NASDAQ earnings calendar) require zero user setup. Finnhub requires a free API key (already in the provider catalog). Premium sources (options flow, dark pool) are available if users connect paid providers or subscribe to Cerberus Pro.

All data comes from live APIs. Zero demo/fabricated data. If an API call fails, no event is created.

### Output: MarketEvent table

```python
class MarketEvent(Base):
    id: str (UUID)
    event_type: str              # "news", "earnings", "macro", "volatility", "sentiment", "sector_move"
    impact: str                  # "LOW", "MEDIUM", "HIGH"
    symbols: JSON[list[str]]     # affected tickers (empty = market-wide)
    sectors: JSON[list[str]]     # affected sectors
    headline: str                # human-readable summary
    raw_data: JSON               # full API response
    source: str                  # "finnhub", "cnn_fng", "stocktwits", etc.
    source_id: str               # dedup key: hash of source + headline + primary symbol
    user_id: int | None          # NULL for platform sources, set for user-premium sources
    detected_at: datetime
    expires_at: datetime         # news: 4h, earnings: 24h, FOMC: 1h after, volatility: 30m
```

**Multi-tenant rule:** Events from free/platform sources have `user_id=NULL` and are visible to all bots. Events from a user's premium API keys (e.g., their paid dark pool feed) have `user_id` set and are only visible to that user's bots.

**Deduplication:** Before inserting, check for existing non-expired event with same `source_id`. Skip if found. This prevents duplicate events from the 2-minute polling cycle.

### Impact Classification

Rules-based first pass handles 90% of events. Canonical VIX thresholds are defined once in Section 5 (Safety Rules) and referenced here.

- **HIGH:** VIX in hard-blocker zone (>40), FOMC within 30 min, earnings within 1 hour for a held symbol, circuit breaker (index down >7%), sector move >3%
- **MEDIUM:** VIX in soft-guardrail zone (25-40), earnings within 24h, unusual volume (>3x avg), Fear/Greed < 25 or > 75, major news on held sector
- **LOW:** Everything else

When the rules-based classifier has low confidence (ambiguous news headline), it escalates to GPT-4.1 for a quick classification call.

---

## 2. Universe Scanner

Background service that finds the best symbols for each bot to trade.

### Execution

Asyncio background loop in FastAPI lifespan, every 15 minutes during market hours.

### Universe Configuration

New field on CerberusBotVersion config:

```python
class UniverseConfig:
    mode: str              # "fixed", "sector", "index", "full_market", "ai_selected"
    fixed_symbols: list[str]    # only used in "fixed" mode
    sectors: list[str]          # for "sector" mode
    index: str                  # "sp500", "nasdaq100", "russell2000" — for "index" mode
    max_symbols: int            # cap (default 10)
    min_market_cap: float       # filter penny stocks
    exclude_symbols: list[str]  # user blacklist
```

### Per-bot flow

1. Read the bot's `universe_config`
2. Fetch candidate pool based on mode:
   - `"fixed"` — use symbols as-is (backwards compatible, current behavior)
   - `"sector"` — sector constituents via yfinance ETF holdings or Finnhub peers
   - `"index"` — index constituents (S&P 500 list cached daily)
   - `"full_market"` — scan across major indices
   - `"ai_selected"` — AI picks universe during strategy generation, scanner refines over time
3. Score each candidate against the bot's strategy type using indicators (no LLM, pure math):
   - Momentum → rank by recent price momentum + volume
   - Mean-reversion → rank by distance from moving average
   - Volatility → rank by ATR / implied vol
4. Store top N as UniverseCandidate records

### Output: UniverseCandidate table

```python
class UniverseCandidate(Base):
    bot_id: str
    symbol: str
    score: float           # 0-1 fitness for this strategy
    reason: str            # "Strong RSI momentum + above-average volume"
    scanned_at: datetime
```

### Defaults

- AI-generated strategies → `mode: "ai_selected"`
- User-created strategies → `mode: "fixed"` with their specified symbols
- User can change mode anytime from bot settings

---

## 3. Reasoning Engine

Per-bot decision layer called when indicator conditions are evaluated. Determines whether to execute, delay, reduce, or block.

### Output: TradeDecision table

TradeDecision is persisted in the database to power the AI Reasoning tab's decision timeline.

```python
class TradeDecision(Base):
    id: str (UUID)
    bot_id: str
    symbol: str
    strategy_signal: str        # "BUY", "SELL", "HOLD"
    context_risk_level: str     # "LOW", "MEDIUM", "HIGH", "CRITICAL"
    ai_confidence: float        # 0.0 - 1.0
    decision: str               # "EXECUTE", "REDUCE_SIZE", "DELAY_TRADE", "PAUSE_BOT", "EXIT_POSITION"
    reasoning: str              # human-readable explanation
    size_adjustment: float      # 1.0 = full size, 0.5 = half, etc.
    delay_seconds: int          # how long to wait before re-evaluating
    events_considered: JSON[list[str]]  # MarketEvent IDs that influenced the decision
    model_used: str             # which LLM made the call, or "safety_rules" if no LLM needed
    created_at: datetime
```

### Evaluation Flow

1. **Gather inputs:** Bot config + aiThinking block, active MarketEvents (filtered to bot's symbols/sectors, respecting user_id visibility), bot trade history + regime stats, current portfolio exposure, universe candidates
2. **Hard safety rules first (no LLM) — see Section 5 for canonical thresholds**
3. **If no hard rule triggered, call LLM:**
   - Model selection: check bot's `reasoning_model_config` first. If set, use that model directly (bypass ModelRouter). If unset, use tiered default: GPT-4.1 for routine, escalate to GPT-5.4 when HIGH impact MarketEvents exist.
   - For Cerberus Pro subscribers: use platform API keys with tiered routing
   - Prompt includes: strategy assumptions, current events, bot's past performance in similar conditions, aiThinking block
4. **LLM returns confidence + reasoning**
5. **Apply bot's override setting:**
   - Advisory → log decision, execute anyway
   - Soft override (default) → can delay or reduce, never cancel
   - Full autonomy → can do anything including exit positions

### Cost Control

Hard safety rules catch obvious cases without LLM. Quiet market days = cheap GPT-4.1 calls. LLM escalated only when real events detected.

### Fallback

If LLM call fails (timeout, API error), fall back to rule-based safety checks only. Never block a trade because the AI is down. The `model_used` field records "safety_rules_fallback" so the user sees what happened.

---

## 4. Bot Memory & Learning

Three layers, all transparent to the user.

### Layer 1: Trade Journal

Every trade is recorded with full context:

```python
class BotTradeJournal(Base):
    bot_id: str
    trade_id: str
    symbol: str
    side: str
    entry_price: float
    exit_price: float
    entry_at: datetime
    exit_at: datetime
    hold_duration_seconds: int
    pnl: float
    pnl_pct: float
    market_events: JSON[list[str]]     # MarketEvent IDs active during trade
    vix_at_entry: float
    sector_momentum_at_entry: float
    ai_confidence_at_entry: float
    ai_decision: str
    ai_reasoning: str
    regime_at_entry: str               # "low_vol", "high_vol", etc.
    outcome_tag: str                   # "good_entry", "bad_timing", "stopped_out_by_event"
    lesson_learned: str                # AI-generated post-trade analysis
```

### Layer 2: Regime Performance Tracker

Regime stats update continuously as trades close. No minimum trade count gates updates — stats reflect all available data. The Reasoning Engine uses regime stats when 20+ trades exist in a regime for statistically meaningful adjustments.

**Regime Classification Rules:**

| Regime | Classification Rule |
|--------|-------------------|
| `low_vol` | VIX < 18 |
| `normal_vol` | VIX 18-25 |
| `high_vol` | VIX > 25 |
| `trending_up` | SPY 20-day SMA slope > 0.1% per day AND price above 20-day SMA |
| `trending_down` | SPY 20-day SMA slope < -0.1% per day AND price below 20-day SMA |
| `range_bound` | Neither trending_up nor trending_down (20-day SMA slope between -0.1% and 0.1%) |

A trade's regime is determined at entry time. Multiple tags can apply (e.g., `high_vol` + `trending_down`).

```python
class BotRegimeStats(Base):
    bot_id: str
    regime: str           # see table above
    total_trades: int
    win_rate: float
    avg_pnl: float
    avg_confidence: float
    sharpe: float
    updated_at: datetime
```

### Layer 3: Autonomous Adaptation

Runs as a Celery task dispatched every N hours (from `learning_plan.cadence_minutes`, default 4h). The 4-hour cadence applies to this layer only — Layer 2 updates on every trade close.

The adaptation review runs regardless of trade count, but the LLM prompt includes the trade count so it can decide whether there's enough data to draw conclusions. With <5 trades, the LLM will typically return no adjustment.

1. Review last 20 trades from journal
2. LLM identifies patterns: "Lost 4/5 trades during afternoon sessions" or "Stop-loss too tight"
3. Generate concrete adjustment:

```python
class BotAdaptation(Base):
    bot_id: str
    adaptation_type: str    # "stop_loss", "position_size", "time_filter", "indicator_param", "regime_behavior"
    old_value: JSON
    new_value: JSON
    reasoning: str
    confidence: float
    auto_applied: bool      # True for minor, False for major
    created_at: datetime
```

**Auto-apply boundaries for stop-loss/take-profit:** The new value must be between 50% and 150% of the original value. Example: if original stop-loss is 2%, auto-apply allows changes between 1% and 3%. Any change beyond that range requires user approval.

**Auto-applies:** Stop-loss/take-profit (within 50%-150% of original), position size scaling (within 50%-150%), time-of-day filters, regime-based behavior changes.

**Needs user approval:** Adding/removing indicators, changing timeframe, changing direction (BUY→SELL), expanding/shrinking universe, any parameter change beyond the 50%-150% range.

---

## 5. Safety Rules

### Canonical VIX Thresholds

All sections reference this single source of truth:

| VIX Range | Classification | Effect |
|-----------|---------------|--------|
| < 18 | Normal | No action |
| 18-25 | Elevated | Context Monitor tags as MEDIUM |
| 25-40 | High | Soft guardrail: reduce position size 50% |
| > 40 | Extreme | Hard blocker: block all new entries, exits only |

### Hard Blockers (always enforced, not configurable)

| Rule | Trigger | Action |
|------|---------|--------|
| Extreme volatility | VIX > 40 | Block new entries, exits only |
| Pre-FOMC blackout | FOMC < 30 min away | Block new entries |
| Earnings lockout | Symbol earnings < 1 hour | Block entries on that symbol |
| Circuit breaker | Major index down > 7% intraday | Block all new entries |
| Liquidity check | Spread > 2% or volume < 10k | Block that symbol |
| Portfolio concentration | Single position > 25% of portfolio | Reduce to limit |
| Daily loss limit | Bot down > 5% in one day | Pause bot, notify user |
| API failure | Market data unreachable | Pause evaluation, don't trade blind |

### Soft Guardrails (per-bot override setting applies)

| Rule | Trigger | Action |
|------|---------|--------|
| High volatility | VIX 25-40 | Reduce position size 50% |
| News pending | HIGH impact event for symbol | Delay 15 min |
| Low confidence | AI confidence < 0.3 | Reduce or delay |
| Losing streak | 3+ consecutive losses | Reduce size 50% until a win |
| Correlation risk | Multiple bots entering same sector | Alert, cap exposure |

### Notifications

Safety interventions that say "notify user" or "alert" use WebSocket push to the frontend (existing WebSocket infrastructure in `api/routes/ws.py`). The frontend shows these as toast notifications and in the Bot Activity Feed. No email notifications in v1.

Every safety intervention is logged in the trade journal with reasoning. Bots learn from safety events.

---

## 6. Cerberus Subscription & Model Access

### Free Tier (all users)
- Bring your own API keys
- Bot reasoning uses user's connected models
- Max 10 active bots per user (prevents database/encryption abuse)
- Max 200 reasoning calls/hour per user

### Cerberus Pro ($29/mo)
- Platform-hosted models via platform API keys
- User needs no API keys for bot reasoning
- Tiered routing included
- Cap: 50 reasoning calls/hour across all bots (platform cost protection)
- Max 25 active bots per user
- Full Context Monitor + Universe Scanner + Learning system

### Admin (user_id=2, Andrew's account)
- Cerberus Pro features, always free
- No rate caps, no bot limits

Implementation: `subscription_tier` field on User model (VARCHAR, default "free", values: "free", "pro", "admin"). Reasoning Engine checks tier before LLM calls. Free → user's decrypted keys via existing `api_connection_manager.get_credentials()`. Pro → platform keys from `.env` with rate limit. Admin → platform keys, no limit.

---

## 7. UI Changes

### New: Market Intelligence Panel

Accessible from main nav or as a tab in the Cerberus widget.

- **Risk Gauge** — 0-100 combining VIX + Fear/Greed + active HIGH events. Green/amber/red.
- **Active Events** — scrollable MarketEvents list with impact badges, headlines, affected symbols, countdowns.
- **Economic Calendar** — upcoming macro events with countdown timers. FOMC, CPI, held-symbol earnings highlighted.
- **Sector Heatmap** — sector ETF grid with momentum color intensity.
- **Bot Activity Feed** — real-time stream: "AAPL-Momentum delayed — FOMC in 25 min", "Tech-Scanner found 3 candidates."

### Enhanced Bot Detail Page

New tabs:

**"AI Reasoning" tab:**
- Latest TradeDecision card with confidence gauge, risk level, reasoning, events considered
- Decision timeline history (from persisted TradeDecision records)

**"Learning" tab:**
- Performance timeline with adaptation markers on equity curve
- Trade journal with per-trade AI reasoning and lesson learned
- Regime breakdown chart (win rate by market condition)
- Adaptations log (chronological parameter changes with before/after)
- Failure analysis (worst trades with AI explanation of what went wrong)

**"Universe" tab (dynamic-universe bots):**
- Ranked candidate symbols with scores and reasons
- Symbol rotation history

### Existing page additions:

- **Strategies page** — universe mode badge ("Sector: Tech", "S&P 500", "AI Selected")
- **Bots list** — AI confidence and risk level badges per bot
- **Deploy modal** — universe config section (mode, sectors, blacklist) + override level selector

---

## 8. Database Changes Summary

### New tables:
- `market_events` — Context Monitor output
- `universe_candidates` — Universe Scanner output
- `trade_decisions` — Reasoning Engine output (persisted for UI timeline)
- `bot_trade_journal` — enriched trade records with AI context
- `bot_regime_stats` — per-regime performance tracking
- `bot_adaptations` — learning adjustments log

### Modified tables:
- `users` — add `subscription_tier` VARCHAR default "free"
- `cerberus_bot_versions` — add `universe_config` JSON, `override_level` VARCHAR default "soft"
- `cerberus_bots` — add `reasoning_model_config` JSON (user's model preference per bot)

### Migration strategy:
New tables use `Base.metadata.create_all` (existing pattern in `init_db()`). Modified tables use `ALTER TABLE ADD COLUMN` in `_ensure_*` compat shims (existing pattern in `database.py`). No Alembic required — matches current approach.

---

## 9. New Files (estimated)

| File | Purpose |
|------|---------|
| `services/context_monitor/monitor.py` | Main polling loop, source aggregation |
| `services/context_monitor/sources/` | One file per data source (finnhub_news.py, cnn_fear_greed.py, vix.py, stocktwits.py, sector_etfs.py, earnings_calendar.py, economic_calendar.py) |
| `services/context_monitor/classifier.py` | Impact classification (rules + LLM escalation) |
| `services/universe_scanner/scanner.py` | Per-bot universe scoring |
| `services/universe_scanner/pools.py` | Index/sector constituent fetching |
| `services/reasoning_engine/engine.py` | Main reasoning orchestration |
| `services/reasoning_engine/safety.py` | Hard blockers + soft guardrails (canonical thresholds) |
| `services/reasoning_engine/prompts.py` | LLM prompts for trade decisions |
| `services/bot_memory/journal.py` | Trade journal recording |
| `services/bot_memory/regime_tracker.py` | Regime classification + stats |
| `services/bot_memory/learning.py` | Autonomous adaptation logic (dispatched as Celery task) |
| `frontend/src/components/intelligence/` | Market Intelligence panel components |
| `frontend/src/app/bots/[id]/reasoning/` | AI Reasoning tab |
| `frontend/src/app/bots/[id]/learning/` | Learning tab |
| `frontend/src/app/bots/[id]/universe/` | Universe tab |

---

## 10. Integration Points with Existing Code

- `services/bot_engine/runner.py` — enhanced to call Reasoning Engine before execution, pull Universe Candidates instead of hardcoded symbols
- `services/bot_engine/evaluator.py` — unchanged (indicator evaluation stays the same)
- `services/ai_strategy_service.py` — strategy generation includes universe_config and enhanced aiThinking
- `services/ai_core/model_router.py` — unchanged; Reasoning Engine uses bot-level model config directly when set, falls back to tiered defaults (not ModelRouter) when unset
- `services/ai_core/tools/` — new tools for context queries (getMarketEvents, getBotLearning, etc.)
- `services/workers/tasks.py` — new Celery task for learning adaptation review
- `api/main.py` — add Context Monitor and Universe Scanner to FastAPI lifespan alongside BotRunner
- `api/routes/ai_tools.py` — new endpoints for market intelligence, bot reasoning history, learning data
- `api/routes/ws.py` — extend WebSocket to push safety alerts and bot activity events
- `db/cerberus_models.py` — new models added alongside existing ones
- `db/database.py` — new `_ensure_*` shims for ALTER TABLE on modified tables
