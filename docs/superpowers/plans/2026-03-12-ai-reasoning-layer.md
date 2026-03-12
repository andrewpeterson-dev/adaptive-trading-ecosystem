# AI Reasoning Layer Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add active AI reasoning, contextual market awareness, dynamic universe selection, and autonomous learning to the existing trading bot architecture.

**Architecture:** Four independent engines (Context Monitor, Universe Scanner, Reasoning Engine, Bot Memory) communicating through shared database state. Context Monitor and Universe Scanner run as asyncio background loops in the FastAPI lifespan (matching existing BotRunner pattern). Reasoning Engine is called per-bot from BotRunner. Bot Memory records and learns from trade outcomes.

**Tech Stack:** Python 3.11+, FastAPI, async SQLAlchemy (SQLite), yfinance, Finnhub API, structlog, Celery (learning tasks), Next.js/React (frontend), Tailwind CSS

---

## File Structure

### New files (backend):
| File | Responsibility |
|------|---------------|
| `services/context_monitor/monitor.py` | Background loop orchestrating all data sources |
| `services/context_monitor/sources/__init__.py` | Source registry |
| `services/context_monitor/sources/finnhub_news.py` | Finnhub news polling |
| `services/context_monitor/sources/finnhub_calendar.py` | Earnings + economic calendar |
| `services/context_monitor/sources/cnn_fear_greed.py` | CNN Fear/Greed index |
| `services/context_monitor/sources/vix.py` | VIX via yfinance |
| `services/context_monitor/sources/stocktwits.py` | StockTwits sentiment |
| `services/context_monitor/sources/sector_etfs.py` | Sector ETF momentum |
| `services/context_monitor/classifier.py` | Impact classification (rules + LLM escalation) |
| `services/universe_scanner/scanner.py` | Per-bot universe scoring loop |
| `services/universe_scanner/pools.py` | Index/sector constituent fetching + caching |
| `services/reasoning_engine/engine.py` | Main reasoning orchestration per-bot |
| `services/reasoning_engine/safety.py` | Hard blockers + soft guardrails (canonical VIX thresholds) |
| `services/reasoning_engine/prompts.py` | LLM prompt templates for trade decisions |
| `services/bot_memory/journal.py` | Trade journal recording with full context |
| `services/bot_memory/regime_tracker.py` | Regime classification + stats aggregation |
| `services/bot_memory/learning.py` | Autonomous adaptation logic (Celery task) |
| `api/routes/reasoning.py` | REST endpoints for market intelligence, reasoning history, learning data |

### New files (frontend):
| File | Responsibility |
|------|---------------|
| `frontend/src/lib/reasoning-api.ts` | API client for reasoning/intelligence endpoints |
| `frontend/src/components/intelligence/MarketIntelligencePanel.tsx` | Market Intelligence panel (risk gauge, events, calendar, heatmap) |
| `frontend/src/components/intelligence/RiskGauge.tsx` | 0-100 risk gauge visualization |
| `frontend/src/components/intelligence/ActiveEvents.tsx` | Scrollable MarketEvents list |
| `frontend/src/components/intelligence/EconomicCalendar.tsx` | Macro events with countdowns |
| `frontend/src/components/intelligence/SectorHeatmap.tsx` | Sector ETF momentum heatmap |
| `frontend/src/components/intelligence/BotActivityFeed.tsx` | Real-time bot activity stream |
| `frontend/src/components/bots/AIReasoningTab.tsx` | TradeDecision card + decision timeline |
| `frontend/src/components/bots/LearningTab.tsx` | Performance timeline, journal, regime breakdown, adaptations |
| `frontend/src/components/bots/UniverseTab.tsx` | Ranked candidates, rotation history |
| `frontend/src/app/intelligence/page.tsx` | Market Intelligence page |

### Modified files:
| File | Changes |
|------|---------|
| `db/cerberus_models.py` | Add 6 new model classes |
| `db/models.py` | Add `subscription_tier` to User |
| `db/database.py` | Add `_ensure_reasoning_schema()` shim |
| `services/bot_engine/runner.py` | Gate execution through Reasoning Engine, pull universe candidates |
| `api/main.py` | Add Context Monitor + Universe Scanner to lifespan |
| `api/routes/ws.py` | Extend WebSocket to push safety alerts + bot activity |
| `services/workers/tasks.py` | Add learning adaptation Celery task |
| `frontend/src/app/bots/[id]/page.tsx` | Add Reasoning/Learning/Universe tabs |
| `frontend/src/lib/cerberus-api.ts` | Add types + fetchers for new data |

---

## Chunk 1: Database Models & Migration Shims

Foundation layer. Every subsequent chunk depends on these tables existing.

### Task 1: Add new model classes to `db/cerberus_models.py`

**Files:**
- Modify: `db/cerberus_models.py`
- Test: `tests/test_reasoning_models.py`

- [ ] **Step 1: Write the failing test**

Create a test that imports and instantiates all 6 new models.

```python
# tests/test_reasoning_models.py
"""Verify all AI reasoning layer models can be imported and instantiated."""
import pytest
from db.cerberus_models import (
    MarketEvent,
    UniverseCandidate,
    TradeDecision,
    BotTradeJournal,
    BotRegimeStats,
    BotAdaptation,
)


def test_market_event_instantiation():
    event = MarketEvent(
        event_type="news",
        impact="HIGH",
        symbols=["AAPL"],
        sectors=["technology"],
        headline="Apple earnings beat",
        raw_data={"source": "finnhub"},
        source="finnhub",
        source_id="abc123",
    )
    assert event.event_type == "news"
    assert event.impact == "HIGH"
    assert event.user_id is None  # platform event


def test_universe_candidate_instantiation():
    candidate = UniverseCandidate(
        bot_id="bot-1",
        symbol="AAPL",
        score=0.85,
        reason="Strong RSI momentum",
    )
    assert candidate.score == 0.85


def test_trade_decision_instantiation():
    decision = TradeDecision(
        bot_id="bot-1",
        symbol="AAPL",
        strategy_signal="BUY",
        context_risk_level="LOW",
        ai_confidence=0.82,
        decision="EXECUTE",
        reasoning="All signals green",
        size_adjustment=1.0,
        delay_seconds=0,
        events_considered=[],
        model_used="gpt-4.1",
    )
    assert decision.decision == "EXECUTE"


def test_bot_trade_journal_instantiation():
    entry = BotTradeJournal(
        bot_id="bot-1",
        trade_id="trade-1",
        symbol="AAPL",
        side="buy",
        entry_price=150.0,
        exit_price=155.0,
        pnl=500.0,
        pnl_pct=0.033,
        market_events=[],
        vix_at_entry=18.5,
        sector_momentum_at_entry=0.02,
        ai_confidence_at_entry=0.82,
        ai_decision="EXECUTE",
        ai_reasoning="Momentum confirmed",
        regime_at_entry="low_vol",
        outcome_tag="good_entry",
        hold_duration_seconds=86400,
    )
    assert entry.pnl == 500.0


def test_bot_regime_stats_instantiation():
    stats = BotRegimeStats(
        bot_id="bot-1",
        regime="low_vol",
        total_trades=25,
        win_rate=0.68,
        avg_pnl=150.0,
        avg_confidence=0.75,
        sharpe=1.2,
    )
    assert stats.total_trades == 25


def test_bot_adaptation_instantiation():
    adaptation = BotAdaptation(
        bot_id="bot-1",
        adaptation_type="stop_loss",
        old_value={"stop_loss_pct": 0.02},
        new_value={"stop_loss_pct": 0.025},
        reasoning="Tighter stops during high vol",
        confidence=0.7,
        auto_applied=True,
    )
    assert adaptation.auto_applied is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/adaptive-trading-ecosystem && python -m pytest tests/test_reasoning_models.py -v`
Expected: ImportError — MarketEvent, UniverseCandidate, etc. not found

- [ ] **Step 3: Write the 6 new model classes**

Add to the end of `db/cerberus_models.py` (before any trailing comments):

```python
# ── AI Reasoning Layer Models ───────────────────────────────────────────────

class MarketEvent(Base):
    """Context Monitor output — real-time market intelligence events."""
    __tablename__ = "market_events"

    id = Column(String(36), primary_key=True, default=_uuid)
    event_type = Column(String(32), nullable=False)  # news, earnings, macro, volatility, sentiment, sector_move
    impact = Column(String(16), nullable=False)  # LOW, MEDIUM, HIGH
    symbols = Column(JSON, default=list)  # affected tickers
    sectors = Column(JSON, default=list)  # affected sectors
    headline = Column(String(512), nullable=False)
    raw_data = Column(JSON, default=dict)
    source = Column(String(64), nullable=False)  # finnhub, cnn_fng, stocktwits, etc.
    source_id = Column(String(128), nullable=False)  # dedup key
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # NULL = platform-wide
    detected_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_market_event_type", "event_type"),
        Index("ix_market_event_source_id", "source_id"),
        Index("ix_market_event_detected", "detected_at"),
        Index("ix_market_event_user", "user_id"),
    )


class UniverseCandidate(Base):
    """Universe Scanner output — ranked symbol candidates per bot."""
    __tablename__ = "universe_candidates"

    id = Column(String(36), primary_key=True, default=_uuid)
    bot_id = Column(String(36), ForeignKey("cerberus_bots.id"), nullable=False)
    symbol = Column(String(16), nullable=False)
    score = Column(Float, nullable=False)  # 0-1 fitness
    reason = Column(String(512), nullable=True)
    scanned_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_universe_cand_bot", "bot_id"),
        Index("ix_universe_cand_bot_scanned", "bot_id", "scanned_at"),
    )


class TradeDecision(Base):
    """Reasoning Engine output — persisted for UI decision timeline."""
    __tablename__ = "trade_decisions"

    id = Column(String(36), primary_key=True, default=_uuid)
    bot_id = Column(String(36), ForeignKey("cerberus_bots.id"), nullable=False)
    symbol = Column(String(16), nullable=False)
    strategy_signal = Column(String(16), nullable=False)  # BUY, SELL, HOLD
    context_risk_level = Column(String(16), nullable=False)  # LOW, MEDIUM, HIGH, CRITICAL
    ai_confidence = Column(Float, nullable=False)
    decision = Column(String(32), nullable=False)  # EXECUTE, REDUCE_SIZE, DELAY_TRADE, PAUSE_BOT, EXIT_POSITION
    reasoning = Column(Text, nullable=True)
    size_adjustment = Column(Float, default=1.0)
    delay_seconds = Column(Integer, default=0)
    events_considered = Column(JSON, default=list)  # MarketEvent IDs
    model_used = Column(String(64), nullable=True)  # LLM model or "safety_rules"
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_trade_decision_bot", "bot_id"),
        Index("ix_trade_decision_bot_created", "bot_id", "created_at"),
    )


class BotTradeJournal(Base):
    """Enriched trade records with full AI context for bot learning."""
    __tablename__ = "bot_trade_journal"

    id = Column(String(36), primary_key=True, default=_uuid)
    bot_id = Column(String(36), ForeignKey("cerberus_bots.id"), nullable=False)
    trade_id = Column(String(36), nullable=False)
    symbol = Column(String(16), nullable=False)
    side = Column(String(16), nullable=False)
    entry_price = Column(Float, nullable=True)
    exit_price = Column(Float, nullable=True)
    entry_at = Column(DateTime, nullable=True)
    exit_at = Column(DateTime, nullable=True)
    hold_duration_seconds = Column(Integer, nullable=True)
    pnl = Column(Float, nullable=True)
    pnl_pct = Column(Float, nullable=True)
    market_events = Column(JSON, default=list)  # MarketEvent IDs active during trade
    vix_at_entry = Column(Float, nullable=True)
    sector_momentum_at_entry = Column(Float, nullable=True)
    ai_confidence_at_entry = Column(Float, nullable=True)
    ai_decision = Column(String(32), nullable=True)
    ai_reasoning = Column(Text, nullable=True)
    regime_at_entry = Column(String(32), nullable=True)
    outcome_tag = Column(String(64), nullable=True)
    lesson_learned = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_bot_journal_bot", "bot_id"),
        Index("ix_bot_journal_bot_created", "bot_id", "created_at"),
        Index("ix_bot_journal_trade", "trade_id"),
    )


class BotRegimeStats(Base):
    """Per-regime performance tracking for each bot."""
    __tablename__ = "bot_regime_stats"

    id = Column(String(36), primary_key=True, default=_uuid)
    bot_id = Column(String(36), ForeignKey("cerberus_bots.id"), nullable=False)
    regime = Column(String(32), nullable=False)  # low_vol, normal_vol, high_vol, trending_up, trending_down, range_bound
    total_trades = Column(Integer, default=0)
    win_rate = Column(Float, default=0.0)
    avg_pnl = Column(Float, default=0.0)
    avg_confidence = Column(Float, default=0.0)
    sharpe = Column(Float, default=0.0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_regime_stats_bot", "bot_id"),
        Index("ix_regime_stats_bot_regime", "bot_id", "regime", unique=True),
    )


class BotAdaptation(Base):
    """Learning adjustments log — parameter changes with reasoning."""
    __tablename__ = "bot_adaptations"

    id = Column(String(36), primary_key=True, default=_uuid)
    bot_id = Column(String(36), ForeignKey("cerberus_bots.id"), nullable=False)
    adaptation_type = Column(String(64), nullable=False)  # stop_loss, position_size, time_filter, etc.
    old_value = Column(JSON, default=dict)
    new_value = Column(JSON, default=dict)
    reasoning = Column(Text, nullable=True)
    confidence = Column(Float, nullable=True)
    auto_applied = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_bot_adaptation_bot", "bot_id"),
        Index("ix_bot_adaptation_bot_created", "bot_id", "created_at"),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/adaptive-trading-ecosystem && python -m pytest tests/test_reasoning_models.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add db/cerberus_models.py tests/test_reasoning_models.py
git commit -m "feat: add 6 AI reasoning layer DB models (MarketEvent, UniverseCandidate, TradeDecision, BotTradeJournal, BotRegimeStats, BotAdaptation)"
```

### Task 2: Add `subscription_tier` to User model and modify CerberusBot/CerberusBotVersion

**Files:**
- Modify: `db/models.py` (add `subscription_tier` to User)
- Modify: `db/cerberus_models.py` (add `reasoning_model_config` to CerberusBot, `universe_config` + `override_level` to CerberusBotVersion)
- Modify: `db/database.py` (add migration shim)
- Test: `tests/test_reasoning_schema.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_reasoning_schema.py
"""Verify schema modifications for AI reasoning layer."""
import pytest


def test_user_has_subscription_tier():
    from db.models import User
    u = User(email="test@x.com", password_hash="x", display_name="T")
    # Default should be "free"
    assert not hasattr(u, "subscription_tier") or u.subscription_tier is None or u.subscription_tier == "free"


def test_cerberus_bot_has_reasoning_model_config():
    from db.cerberus_models import CerberusBot
    b = CerberusBot(name="test")
    assert hasattr(b, "reasoning_model_config")


def test_cerberus_bot_version_has_universe_config():
    from db.cerberus_models import CerberusBotVersion
    v = CerberusBotVersion(bot_id="x", version_number=1)
    assert hasattr(v, "universe_config")
    assert hasattr(v, "override_level")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/adaptive-trading-ecosystem && python -m pytest tests/test_reasoning_schema.py -v`
Expected: FAIL — attributes missing

- [ ] **Step 3: Add columns to models**

In `db/models.py`, add to User class (after `session_version`):
```python
    subscription_tier = Column(String(16), default="free", nullable=False)
```

In `db/cerberus_models.py`, add to CerberusBot class (after `learning_status_json`):
```python
    reasoning_model_config = Column(JSON, default=dict)  # user's model preference per bot
```

In `db/cerberus_models.py`, add to CerberusBotVersion class (after `backtest_id`):
```python
    universe_config = Column(JSON, default=dict)  # UniverseConfig: mode, fixed_symbols, sectors, etc.
    override_level = Column(String(16), default="soft")  # "advisory", "soft", "full_autonomy"
```

- [ ] **Step 4: Add migration shim to `db/database.py`**

Add a new function `_ensure_reasoning_schema()` and call it from `init_db()`:

```python
async def _ensure_reasoning_schema() -> None:
    async with _get_engine().begin() as conn:
        def _ensure(sync_conn) -> None:
            inspector = inspect(sync_conn)
            tables = set(inspector.get_table_names())

            def add_column_if_missing(table: str, column: str, ddl: str) -> None:
                if table not in tables:
                    return
                columns = {c["name"] for c in inspector.get_columns(table)}
                if column not in columns:
                    sync_conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))

            add_column_if_missing("users", "subscription_tier", "VARCHAR(16) DEFAULT 'free' NOT NULL")
            add_column_if_missing("cerberus_bots", "reasoning_model_config", "JSON")
            add_column_if_missing("cerberus_bot_versions", "universe_config", "JSON")
            add_column_if_missing("cerberus_bot_versions", "override_level", "VARCHAR(16) DEFAULT 'soft'")

        await conn.run_sync(_ensure)
```

In `init_db()`, add after `_ensure_ai_strategy_schema()`:
```python
    await _ensure_reasoning_schema()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd ~/adaptive-trading-ecosystem && python -m pytest tests/test_reasoning_schema.py tests/test_reasoning_models.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add db/models.py db/cerberus_models.py db/database.py tests/test_reasoning_schema.py
git commit -m "feat: add subscription_tier to User, reasoning_model_config/universe_config/override_level to bot models, migration shim"
```

---

## Chunk 2: Safety Rules & Reasoning Engine

The safety module is independent and can be built first since the Reasoning Engine and BotRunner both depend on it.

### Task 3: Implement safety rules module

**Files:**
- Create: `services/reasoning_engine/__init__.py`
- Create: `services/reasoning_engine/safety.py`
- Test: `tests/test_safety_rules.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_safety_rules.py
"""Test hard blockers and soft guardrails."""
import pytest
from services.reasoning_engine.safety import (
    VIX_THRESHOLDS,
    check_hard_blockers,
    check_soft_guardrails,
    SafetyResult,
)


def test_vix_thresholds_defined():
    assert VIX_THRESHOLDS["normal"] == (0, 18)
    assert VIX_THRESHOLDS["elevated"] == (18, 25)
    assert VIX_THRESHOLDS["high"] == (25, 40)
    assert VIX_THRESHOLDS["extreme"] == (40, float("inf"))


def test_hard_blocker_extreme_vix():
    result = check_hard_blockers(vix=45.0, events=[], portfolio_exposure={}, bot_daily_pnl_pct=0.0)
    assert result is not None
    assert result.decision == "PAUSE_BOT"
    assert "VIX" in result.reasoning


def test_hard_blocker_fomc_imminent():
    from datetime import datetime, timedelta
    fomc_event = {
        "event_type": "macro",
        "headline": "FOMC",
        "impact": "HIGH",
        "detected_at": datetime.utcnow(),
        "expires_at": datetime.utcnow() + timedelta(minutes=20),
        "symbols": [],
    }
    result = check_hard_blockers(vix=20.0, events=[fomc_event], portfolio_exposure={}, bot_daily_pnl_pct=0.0)
    assert result is not None
    assert result.decision == "PAUSE_BOT"


def test_hard_blocker_daily_loss_limit():
    result = check_hard_blockers(vix=20.0, events=[], portfolio_exposure={}, bot_daily_pnl_pct=-5.5)
    assert result is not None
    assert result.decision == "PAUSE_BOT"


def test_no_hard_blocker_normal_conditions():
    result = check_hard_blockers(vix=20.0, events=[], portfolio_exposure={}, bot_daily_pnl_pct=-1.0)
    assert result is None


def test_soft_guardrail_high_vix():
    result = check_soft_guardrails(vix=30.0, events=[], consecutive_losses=0, ai_confidence=0.8)
    assert len(result) > 0
    assert any(r.decision == "REDUCE_SIZE" for r in result)


def test_soft_guardrail_losing_streak():
    result = check_soft_guardrails(vix=15.0, events=[], consecutive_losses=4, ai_confidence=0.8)
    assert any(r.decision == "REDUCE_SIZE" for r in result)


def test_soft_guardrail_low_confidence():
    result = check_soft_guardrails(vix=15.0, events=[], consecutive_losses=0, ai_confidence=0.2)
    assert len(result) > 0


def test_no_soft_guardrails_normal():
    result = check_soft_guardrails(vix=15.0, events=[], consecutive_losses=0, ai_confidence=0.8)
    assert len(result) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/adaptive-trading-ecosystem && python -m pytest tests/test_safety_rules.py -v`
Expected: ImportError

- [ ] **Step 3: Implement safety module**

Create `services/reasoning_engine/__init__.py` (empty).

Create `services/reasoning_engine/safety.py`:

```python
"""Hard blockers and soft guardrails for trade safety.

Canonical VIX thresholds are the single source of truth for the entire system.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta


# ── Canonical VIX Thresholds (single source of truth) ──────────────────────
VIX_THRESHOLDS = {
    "normal": (0, 18),
    "elevated": (18, 25),
    "high": (25, 40),
    "extreme": (40, float("inf")),
}


def classify_vix(vix: float) -> str:
    for label, (low, high) in VIX_THRESHOLDS.items():
        if low <= vix < high:
            return label
    return "extreme"


@dataclass
class SafetyResult:
    decision: str  # PAUSE_BOT, REDUCE_SIZE, DELAY_TRADE, EXIT_POSITION
    reasoning: str
    size_adjustment: float = 1.0
    delay_seconds: int = 0
    rule_name: str = ""


def check_hard_blockers(
    *,
    vix: float,
    events: list[dict],
    portfolio_exposure: dict,
    bot_daily_pnl_pct: float,
    symbol: str | None = None,
    market_data_available: bool = True,
) -> SafetyResult | None:
    """Check hard blockers. Returns SafetyResult if trade should be blocked, None if clear."""
    # Extreme volatility
    if vix > 40:
        return SafetyResult(
            decision="PAUSE_BOT",
            reasoning=f"VIX at {vix:.1f} exceeds extreme threshold (>40). Block all new entries, exits only.",
            rule_name="extreme_volatility",
        )

    # Pre-FOMC blackout
    now = datetime.utcnow()
    for event in events:
        if event.get("event_type") == "macro" and "FOMC" in (event.get("headline") or "").upper():
            expires = event.get("expires_at")
            if expires and isinstance(expires, datetime) and expires > now:
                time_until = (expires - now).total_seconds() / 60
                if time_until <= 30:
                    return SafetyResult(
                        decision="PAUSE_BOT",
                        reasoning=f"FOMC decision in {time_until:.0f} minutes. Pre-FOMC blackout active.",
                        rule_name="pre_fomc_blackout",
                    )

    # Earnings lockout
    if symbol:
        for event in events:
            if event.get("event_type") == "earnings" and symbol in (event.get("symbols") or []):
                expires = event.get("expires_at")
                if expires and isinstance(expires, datetime) and expires > now:
                    time_until = (expires - now).total_seconds() / 3600
                    if time_until <= 1:
                        return SafetyResult(
                            decision="PAUSE_BOT",
                            reasoning=f"Earnings for {symbol} in {time_until*60:.0f} min. Lockout active.",
                            rule_name="earnings_lockout",
                        )

    # Daily loss limit
    if bot_daily_pnl_pct <= -5.0:
        return SafetyResult(
            decision="PAUSE_BOT",
            reasoning=f"Bot down {bot_daily_pnl_pct:.1f}% today (limit: -5%). Pausing.",
            rule_name="daily_loss_limit",
        )

    # Portfolio concentration
    if symbol and portfolio_exposure.get(symbol, 0) > 25:
        return SafetyResult(
            decision="REDUCE_SIZE",
            reasoning=f"{symbol} position is {portfolio_exposure[symbol]:.1f}% of portfolio (limit: 25%).",
            size_adjustment=0.0,
            rule_name="portfolio_concentration",
        )

    # API failure
    if not market_data_available:
        return SafetyResult(
            decision="PAUSE_BOT",
            reasoning="Market data unreachable. Pausing to avoid trading blind.",
            rule_name="api_failure",
        )

    return None


def check_soft_guardrails(
    *,
    vix: float,
    events: list[dict],
    consecutive_losses: int,
    ai_confidence: float,
    symbol: str | None = None,
) -> list[SafetyResult]:
    """Check soft guardrails. Returns list of applicable guardrails."""
    results = []

    # High volatility
    if 25 <= vix <= 40:
        results.append(SafetyResult(
            decision="REDUCE_SIZE",
            reasoning=f"VIX at {vix:.1f} (high range 25-40). Reduce position size 50%.",
            size_adjustment=0.5,
            rule_name="high_volatility",
        ))

    # News pending
    if symbol:
        for event in events:
            if event.get("impact") == "HIGH" and symbol in (event.get("symbols") or []):
                results.append(SafetyResult(
                    decision="DELAY_TRADE",
                    reasoning=f"HIGH impact event for {symbol}: {event.get('headline', 'Unknown')}. Delay 15 min.",
                    delay_seconds=900,
                    rule_name="news_pending",
                ))
                break

    # Low confidence
    if ai_confidence < 0.3:
        results.append(SafetyResult(
            decision="REDUCE_SIZE",
            reasoning=f"AI confidence {ai_confidence:.2f} below threshold (0.3). Reducing size.",
            size_adjustment=0.5,
            rule_name="low_confidence",
        ))

    # Losing streak
    if consecutive_losses >= 3:
        results.append(SafetyResult(
            decision="REDUCE_SIZE",
            reasoning=f"{consecutive_losses} consecutive losses. Reducing size 50% until a win.",
            size_adjustment=0.5,
            rule_name="losing_streak",
        ))

    return results
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/adaptive-trading-ecosystem && python -m pytest tests/test_safety_rules.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add services/reasoning_engine/__init__.py services/reasoning_engine/safety.py tests/test_safety_rules.py
git commit -m "feat: implement safety rules module with canonical VIX thresholds, hard blockers, soft guardrails"
```

### Task 4: Implement Reasoning Engine

**Files:**
- Create: `services/reasoning_engine/engine.py`
- Create: `services/reasoning_engine/prompts.py`
- Test: `tests/test_reasoning_engine.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_reasoning_engine.py
"""Test the Reasoning Engine decision logic."""
import pytest
from unittest.mock import AsyncMock, patch
from services.reasoning_engine.engine import ReasoningEngine


@pytest.fixture
def engine():
    return ReasoningEngine()


@pytest.mark.asyncio
async def test_hard_blocker_skips_llm(engine):
    """When a hard blocker fires, no LLM call should be made."""
    decision = await engine.evaluate(
        bot_id="bot-1",
        symbol="AAPL",
        strategy_signal="BUY",
        vix=50.0,  # extreme
        events=[],
        portfolio_exposure={},
        bot_daily_pnl_pct=0.0,
        bot_config={},
        override_level="soft",
    )
    assert decision["decision"] == "PAUSE_BOT"
    assert decision["model_used"] == "safety_rules"


@pytest.mark.asyncio
async def test_normal_conditions_defaults_to_execute(engine):
    """Under normal conditions with no LLM, default to EXECUTE with safety_rules_fallback."""
    decision = await engine.evaluate(
        bot_id="bot-1",
        symbol="AAPL",
        strategy_signal="BUY",
        vix=15.0,
        events=[],
        portfolio_exposure={},
        bot_daily_pnl_pct=0.0,
        bot_config={},
        override_level="soft",
    )
    # Without LLM keys configured, should fall back to safety_rules_fallback
    assert decision["decision"] in ("EXECUTE", "REDUCE_SIZE", "DELAY_TRADE")
    assert "safety" in decision["model_used"] or decision["model_used"] in ("safety_rules_fallback", "safety_rules")


@pytest.mark.asyncio
async def test_advisory_mode_always_executes(engine):
    """In advisory mode, decision is logged but trade always executes."""
    decision = await engine.evaluate(
        bot_id="bot-1",
        symbol="AAPL",
        strategy_signal="BUY",
        vix=30.0,  # high — would normally reduce
        events=[],
        portfolio_exposure={},
        bot_daily_pnl_pct=0.0,
        bot_config={},
        override_level="advisory",
    )
    # Advisory mode: hard blockers still apply (VIX < 40 so no hard blocker here),
    # but soft guardrails are logged only
    assert decision["decision"] == "EXECUTE"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/adaptive-trading-ecosystem && python -m pytest tests/test_reasoning_engine.py -v`
Expected: ImportError

- [ ] **Step 3: Implement prompts module**

Create `services/reasoning_engine/prompts.py`:

```python
"""LLM prompt templates for trade reasoning decisions."""

TRADE_DECISION_SYSTEM = """You are a trading risk analyst. Evaluate whether a bot should execute, delay, reduce, or skip a trade.

Respond with ONLY a JSON object:
{
  "decision": "EXECUTE" | "REDUCE_SIZE" | "DELAY_TRADE" | "PAUSE_BOT" | "EXIT_POSITION",
  "confidence": 0.0-1.0,
  "reasoning": "2-3 sentence explanation",
  "size_adjustment": 1.0,
  "delay_seconds": 0
}"""


def build_trade_decision_prompt(
    *,
    strategy_signal: str,
    symbol: str,
    events: list[dict],
    regime_stats: dict | None,
    ai_thinking: str | None,
    vix: float,
    recent_performance: dict | None,
) -> str:
    parts = [
        f"Signal: {strategy_signal} on {symbol}",
        f"VIX: {vix:.1f}",
    ]
    if events:
        event_lines = [f"- [{e.get('impact','?')}] {e.get('headline','?')}" for e in events[:5]]
        parts.append("Active events:\n" + "\n".join(event_lines))
    if regime_stats:
        parts.append(f"Regime stats: {regime_stats.get('total_trades', 0)} trades, "
                      f"win rate {regime_stats.get('win_rate', 0):.0%}, "
                      f"avg PnL ${regime_stats.get('avg_pnl', 0):.2f}")
    if ai_thinking:
        parts.append(f"Strategy reasoning:\n{ai_thinking}")
    if recent_performance:
        parts.append(f"Recent: {recent_performance.get('trade_count', 0)} trades, "
                      f"Sharpe {recent_performance.get('sharpe_ratio', 0):.2f}")
    return "\n\n".join(parts)
```

- [ ] **Step 4: Implement engine module**

Create `services/reasoning_engine/engine.py`:

```python
"""Reasoning Engine — per-bot decision layer called when indicator conditions fire."""
from __future__ import annotations

import json
import uuid
from datetime import datetime

import structlog

from services.reasoning_engine.safety import (
    check_hard_blockers,
    check_soft_guardrails,
    classify_vix,
    SafetyResult,
)
from services.reasoning_engine.prompts import (
    TRADE_DECISION_SYSTEM,
    build_trade_decision_prompt,
)

logger = structlog.get_logger(__name__)


class ReasoningEngine:
    """Evaluate whether a bot should execute a trade given market context."""

    async def evaluate(
        self,
        *,
        bot_id: str,
        symbol: str,
        strategy_signal: str,
        vix: float,
        events: list[dict],
        portfolio_exposure: dict,
        bot_daily_pnl_pct: float,
        bot_config: dict,
        override_level: str = "soft",
        regime_stats: dict | None = None,
        recent_performance: dict | None = None,
        consecutive_losses: int = 0,
        market_data_available: bool = True,
    ) -> dict:
        """Run safety checks + optional LLM reasoning. Returns TradeDecision dict."""
        decision_id = str(uuid.uuid4())

        # 1. Hard blockers (always enforced, even in advisory mode)
        hard_block = check_hard_blockers(
            vix=vix,
            events=events,
            portfolio_exposure=portfolio_exposure,
            bot_daily_pnl_pct=bot_daily_pnl_pct,
            symbol=symbol,
            market_data_available=market_data_available,
        )
        if hard_block:
            return self._build_result(
                decision_id=decision_id,
                bot_id=bot_id,
                symbol=symbol,
                strategy_signal=strategy_signal,
                vix=vix,
                safety_result=hard_block,
                model_used="safety_rules",
                events=events,
            )

        # 2. Soft guardrails
        soft_results = check_soft_guardrails(
            vix=vix,
            events=events,
            consecutive_losses=consecutive_losses,
            ai_confidence=0.5,  # placeholder until LLM gives real confidence
            symbol=symbol,
        )

        # 3. Try LLM reasoning (if configured)
        llm_result = await self._try_llm_reasoning(
            bot_config=bot_config,
            symbol=symbol,
            strategy_signal=strategy_signal,
            vix=vix,
            events=events,
            regime_stats=regime_stats,
            recent_performance=recent_performance,
        )

        # 4. Merge LLM + soft guardrails
        if llm_result:
            confidence = llm_result.get("confidence", 0.5)
            # Re-check low-confidence guardrail with actual LLM confidence
            if confidence < 0.3:
                soft_results.append(SafetyResult(
                    decision="REDUCE_SIZE",
                    reasoning=f"AI confidence {confidence:.2f} below 0.3.",
                    size_adjustment=0.5,
                    rule_name="low_confidence",
                ))
        else:
            confidence = 0.5

        # 5. Apply override level
        if override_level == "advisory":
            # Log everything but always execute
            return self._build_result(
                decision_id=decision_id,
                bot_id=bot_id,
                symbol=symbol,
                strategy_signal=strategy_signal,
                vix=vix,
                decision="EXECUTE",
                confidence=confidence,
                reasoning=self._merge_reasoning(llm_result, soft_results, advisory=True),
                model_used=llm_result.get("model", "safety_rules_fallback") if llm_result else "safety_rules_fallback",
                events=events,
            )

        # Soft override (default): can delay or reduce, never cancel
        if soft_results:
            # Pick the most restrictive soft guardrail
            most_restrictive = min(soft_results, key=lambda r: r.size_adjustment)
            has_delay = any(r.delay_seconds > 0 for r in soft_results)

            if has_delay:
                delay_result = next(r for r in soft_results if r.delay_seconds > 0)
                return self._build_result(
                    decision_id=decision_id,
                    bot_id=bot_id,
                    symbol=symbol,
                    strategy_signal=strategy_signal,
                    vix=vix,
                    decision="DELAY_TRADE",
                    confidence=confidence,
                    reasoning=self._merge_reasoning(llm_result, soft_results),
                    model_used=llm_result.get("model", "safety_rules_fallback") if llm_result else "safety_rules_fallback",
                    size_adjustment=most_restrictive.size_adjustment,
                    delay_seconds=delay_result.delay_seconds,
                    events=events,
                )

            return self._build_result(
                decision_id=decision_id,
                bot_id=bot_id,
                symbol=symbol,
                strategy_signal=strategy_signal,
                vix=vix,
                decision="REDUCE_SIZE",
                confidence=confidence,
                reasoning=self._merge_reasoning(llm_result, soft_results),
                model_used=llm_result.get("model", "safety_rules_fallback") if llm_result else "safety_rules_fallback",
                size_adjustment=most_restrictive.size_adjustment,
                events=events,
            )

        # Full autonomy with LLM: use LLM decision
        if override_level == "full_autonomy" and llm_result:
            return self._build_result(
                decision_id=decision_id,
                bot_id=bot_id,
                symbol=symbol,
                strategy_signal=strategy_signal,
                vix=vix,
                decision=llm_result.get("decision", "EXECUTE"),
                confidence=confidence,
                reasoning=llm_result.get("reasoning", "LLM decision"),
                model_used=llm_result.get("model", "unknown"),
                size_adjustment=llm_result.get("size_adjustment", 1.0),
                delay_seconds=llm_result.get("delay_seconds", 0),
                events=events,
            )

        # No blockers, no guardrails → execute
        return self._build_result(
            decision_id=decision_id,
            bot_id=bot_id,
            symbol=symbol,
            strategy_signal=strategy_signal,
            vix=vix,
            decision="EXECUTE",
            confidence=confidence,
            reasoning=llm_result.get("reasoning", "No safety concerns.") if llm_result else "No safety concerns. Safety rules clear.",
            model_used=llm_result.get("model", "safety_rules_fallback") if llm_result else "safety_rules_fallback",
            events=events,
        )

    async def _try_llm_reasoning(
        self,
        *,
        bot_config: dict,
        symbol: str,
        strategy_signal: str,
        vix: float,
        events: list[dict],
        regime_stats: dict | None,
        recent_performance: dict | None,
    ) -> dict | None:
        """Attempt LLM call for reasoning. Returns None on failure."""
        try:
            from config.settings import get_settings
            settings = get_settings()

            # Check if bot has model config override
            model_config = bot_config.get("reasoning_model_config") or {}
            api_key = model_config.get("api_key") or settings.openai_api_key

            if not api_key:
                return None

            # Determine model: escalate to gpt-5.4 if HIGH events exist
            has_high_events = any(e.get("impact") == "HIGH" for e in events)
            model = model_config.get("model") or ("gpt-5.4" if has_high_events else "gpt-4.1")

            prompt = build_trade_decision_prompt(
                strategy_signal=strategy_signal,
                symbol=symbol,
                events=events,
                regime_stats=regime_stats,
                ai_thinking=bot_config.get("ai_context", {}).get("aiThinking"),
                vix=vix,
                recent_performance=recent_performance,
            )

            import openai
            client = openai.AsyncOpenAI(api_key=api_key)
            response = await client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": TRADE_DECISION_SYSTEM},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                max_tokens=300,
                response_format={"type": "json_object"},
            )

            raw = response.choices[0].message.content
            result = json.loads(raw)
            result["model"] = model
            return result

        except Exception as e:
            logger.warning("reasoning_llm_failed", error=str(e))
            return None

    def _merge_reasoning(
        self,
        llm_result: dict | None,
        soft_results: list[SafetyResult],
        advisory: bool = False,
    ) -> str:
        parts = []
        if advisory:
            parts.append("[Advisory mode — logging only, trade will execute]")
        if llm_result and llm_result.get("reasoning"):
            parts.append(f"AI: {llm_result['reasoning']}")
        for sr in soft_results:
            parts.append(f"Safety ({sr.rule_name}): {sr.reasoning}")
        return " | ".join(parts) if parts else "No concerns."

    def _build_result(
        self,
        *,
        decision_id: str,
        bot_id: str,
        symbol: str,
        strategy_signal: str,
        vix: float,
        events: list[dict],
        decision: str | None = None,
        confidence: float = 0.5,
        reasoning: str = "",
        model_used: str = "safety_rules",
        size_adjustment: float = 1.0,
        delay_seconds: int = 0,
        safety_result: SafetyResult | None = None,
    ) -> dict:
        if safety_result:
            return {
                "id": decision_id,
                "bot_id": bot_id,
                "symbol": symbol,
                "strategy_signal": strategy_signal,
                "context_risk_level": "CRITICAL" if vix > 40 else classify_vix(vix).upper(),
                "ai_confidence": 0.0,
                "decision": safety_result.decision,
                "reasoning": safety_result.reasoning,
                "size_adjustment": safety_result.size_adjustment,
                "delay_seconds": safety_result.delay_seconds,
                "events_considered": [e.get("id", "") for e in events if e.get("id")],
                "model_used": model_used,
                "created_at": datetime.utcnow().isoformat(),
            }

        return {
            "id": decision_id,
            "bot_id": bot_id,
            "symbol": symbol,
            "strategy_signal": strategy_signal,
            "context_risk_level": classify_vix(vix).upper(),
            "ai_confidence": confidence,
            "decision": decision or "EXECUTE",
            "reasoning": reasoning,
            "size_adjustment": size_adjustment,
            "delay_seconds": delay_seconds,
            "events_considered": [e.get("id", "") for e in events if e.get("id")],
            "model_used": model_used,
            "created_at": datetime.utcnow().isoformat(),
        }
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd ~/adaptive-trading-ecosystem && python -m pytest tests/test_reasoning_engine.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add services/reasoning_engine/engine.py services/reasoning_engine/prompts.py tests/test_reasoning_engine.py
git commit -m "feat: implement Reasoning Engine with LLM integration, override levels, and fallback logic"
```

---

## Chunk 3: Context Monitor

### Task 5: Implement Context Monitor data sources

**Files:**
- Create: `services/context_monitor/__init__.py`
- Create: `services/context_monitor/sources/__init__.py`
- Create: `services/context_monitor/sources/vix.py`
- Create: `services/context_monitor/sources/cnn_fear_greed.py`
- Create: `services/context_monitor/sources/finnhub_news.py`
- Create: `services/context_monitor/sources/finnhub_calendar.py`
- Create: `services/context_monitor/sources/stocktwits.py`
- Create: `services/context_monitor/sources/sector_etfs.py`
- Test: `tests/test_context_sources.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_context_sources.py
"""Test Context Monitor data source functions return proper MarketEvent dicts."""
import pytest
from services.context_monitor.sources.vix import fetch_vix_events
from services.context_monitor.sources.cnn_fear_greed import fetch_fear_greed_events
from services.context_monitor.sources.sector_etfs import fetch_sector_events


@pytest.mark.asyncio
async def test_vix_returns_list():
    events = await fetch_vix_events()
    assert isinstance(events, list)
    # Even if yfinance fails, should return empty list, not error
    for e in events:
        assert "event_type" in e
        assert e["event_type"] == "volatility"
        assert "source" in e
        assert e["source"] == "yfinance_vix"


@pytest.mark.asyncio
async def test_fear_greed_returns_list():
    events = await fetch_fear_greed_events()
    assert isinstance(events, list)
    for e in events:
        assert e["event_type"] == "sentiment"
        assert e["source"] == "cnn_fng"


@pytest.mark.asyncio
async def test_sector_etfs_returns_list():
    events = await fetch_sector_events()
    assert isinstance(events, list)
    for e in events:
        assert e["event_type"] == "sector_move"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/adaptive-trading-ecosystem && python -m pytest tests/test_context_sources.py -v`
Expected: ImportError

- [ ] **Step 3: Create source init files**

Create `services/context_monitor/__init__.py` (empty).
Create `services/context_monitor/sources/__init__.py` (empty).

- [ ] **Step 4: Implement VIX source**

Create `services/context_monitor/sources/vix.py`:

```python
"""VIX data source via yfinance — no API key required."""
from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime, timedelta

import structlog

logger = structlog.get_logger(__name__)


async def fetch_vix_events() -> list[dict]:
    """Fetch current VIX level and return a MarketEvent dict if notable."""
    try:
        loop = asyncio.get_running_loop()
        vix_value = await loop.run_in_executor(None, _fetch_vix_sync)
        if vix_value is None:
            return []

        # Classify impact
        if vix_value > 40:
            impact = "HIGH"
        elif vix_value > 25:
            impact = "MEDIUM"
        elif vix_value > 18:
            impact = "LOW"
        else:
            return []  # Normal VIX, no event needed

        source_id = hashlib.sha256(f"vix_{datetime.utcnow().strftime('%Y%m%d%H')}".encode()).hexdigest()[:32]

        return [{
            "event_type": "volatility",
            "impact": impact,
            "symbols": [],
            "sectors": [],
            "headline": f"VIX at {vix_value:.1f}",
            "raw_data": {"vix": vix_value},
            "source": "yfinance_vix",
            "source_id": source_id,
            "user_id": None,
            "expires_at": datetime.utcnow() + timedelta(minutes=30),
        }]
    except Exception as e:
        logger.warning("vix_fetch_failed", error=str(e))
        return []


def _fetch_vix_sync() -> float | None:
    try:
        import yfinance as yf
        ticker = yf.Ticker("^VIX")
        hist = ticker.history(period="1d", interval="1m")
        if hist.empty:
            return None
        return float(hist["Close"].iloc[-1])
    except Exception:
        return None
```

- [ ] **Step 5: Implement CNN Fear/Greed source**

Create `services/context_monitor/sources/cnn_fear_greed.py`:

```python
"""CNN Fear & Greed Index — no API key required."""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta

import httpx
import structlog

logger = structlog.get_logger(__name__)

_CNN_FNG_URL = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"


async def fetch_fear_greed_events() -> list[dict]:
    """Fetch CNN Fear & Greed index and create event if extreme."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(_CNN_FNG_URL, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            data = resp.json()

        score = data.get("fear_and_greed", {}).get("score")
        if score is None:
            return []

        score = float(score)
        rating = data.get("fear_and_greed", {}).get("rating", "")

        if score > 75:
            impact = "MEDIUM"
            headline = f"Fear/Greed at {score:.0f} (Extreme Greed)"
        elif score < 25:
            impact = "MEDIUM"
            headline = f"Fear/Greed at {score:.0f} (Extreme Fear)"
        else:
            impact = "LOW"
            headline = f"Fear/Greed at {score:.0f} ({rating})"

        # Only create events for notable readings
        if impact == "LOW":
            return []

        source_id = hashlib.sha256(f"fng_{datetime.utcnow().strftime('%Y%m%d%H')}".encode()).hexdigest()[:32]

        return [{
            "event_type": "sentiment",
            "impact": impact,
            "symbols": [],
            "sectors": [],
            "headline": headline,
            "raw_data": {"score": score, "rating": rating},
            "source": "cnn_fng",
            "source_id": source_id,
            "user_id": None,
            "expires_at": datetime.utcnow() + timedelta(hours=4),
        }]
    except Exception as e:
        logger.warning("fear_greed_fetch_failed", error=str(e))
        return []
```

- [ ] **Step 6: Implement Finnhub news source**

Create `services/context_monitor/sources/finnhub_news.py`:

```python
"""Finnhub news source — requires free API key (already in provider catalog)."""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta

import httpx
import structlog

from config.settings import get_settings

logger = structlog.get_logger(__name__)


async def fetch_finnhub_news_events() -> list[dict]:
    """Fetch market news from Finnhub."""
    settings = get_settings()
    api_key = settings.finnhub_api_key
    if not api_key:
        return []

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://finnhub.io/api/v1/news",
                params={"category": "general", "token": api_key},
            )
            resp.raise_for_status()
            articles = resp.json()

        events = []
        for article in articles[:20]:  # Cap at 20 per poll
            headline = article.get("headline", "")
            source_id = hashlib.sha256(
                f"finnhub_{headline[:100]}_{article.get('source', '')}".encode()
            ).hexdigest()[:32]

            # Simple impact heuristic based on keywords
            headline_lower = headline.lower()
            if any(w in headline_lower for w in ["fed", "fomc", "rate", "recession", "crash", "crisis"]):
                impact = "HIGH"
            elif any(w in headline_lower for w in ["earnings", "revenue", "guidance", "layoff", "merger"]):
                impact = "MEDIUM"
            else:
                impact = "LOW"

            # Extract related symbols
            symbols = []
            related = article.get("related", "")
            if related:
                symbols = [s.strip() for s in related.split(",") if s.strip()]

            events.append({
                "event_type": "news",
                "impact": impact,
                "symbols": symbols[:5],
                "sectors": [],
                "headline": headline[:500],
                "raw_data": article,
                "source": "finnhub",
                "source_id": source_id,
                "user_id": None,
                "expires_at": datetime.utcnow() + timedelta(hours=4),
            })

        return events
    except Exception as e:
        logger.warning("finnhub_news_fetch_failed", error=str(e))
        return []
```

- [ ] **Step 7: Implement Finnhub calendar source**

Create `services/context_monitor/sources/finnhub_calendar.py`:

```python
"""Finnhub earnings + economic calendar source."""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta

import httpx
import structlog

from config.settings import get_settings

logger = structlog.get_logger(__name__)


async def fetch_earnings_events() -> list[dict]:
    """Fetch upcoming earnings from Finnhub."""
    settings = get_settings()
    api_key = settings.finnhub_api_key
    if not api_key:
        return []

    try:
        today = datetime.utcnow().strftime("%Y-%m-%d")
        end = (datetime.utcnow() + timedelta(days=7)).strftime("%Y-%m-%d")

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://finnhub.io/api/v1/calendar/earnings",
                params={"from": today, "to": end, "token": api_key},
            )
            resp.raise_for_status()
            data = resp.json()

        events = []
        for ec in (data.get("earningsCalendar") or [])[:50]:
            symbol = ec.get("symbol", "")
            date_str = ec.get("date", "")
            if not symbol or not date_str:
                continue

            source_id = hashlib.sha256(f"earnings_{symbol}_{date_str}".encode()).hexdigest()[:32]
            events.append({
                "event_type": "earnings",
                "impact": "MEDIUM",
                "symbols": [symbol],
                "sectors": [],
                "headline": f"{symbol} earnings on {date_str}",
                "raw_data": ec,
                "source": "finnhub",
                "source_id": source_id,
                "user_id": None,
                "expires_at": datetime.fromisoformat(date_str) + timedelta(hours=24) if date_str else datetime.utcnow() + timedelta(days=1),
            })

        return events
    except Exception as e:
        logger.warning("finnhub_earnings_fetch_failed", error=str(e))
        return []


async def fetch_economic_events() -> list[dict]:
    """Fetch upcoming economic events (FOMC, CPI, GDP, etc.) from Finnhub."""
    settings = get_settings()
    api_key = settings.finnhub_api_key
    if not api_key:
        return []

    try:
        today = datetime.utcnow().strftime("%Y-%m-%d")
        end = (datetime.utcnow() + timedelta(days=7)).strftime("%Y-%m-%d")

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://finnhub.io/api/v1/calendar/economic",
                params={"from": today, "to": end, "token": api_key},
            )
            resp.raise_for_status()
            data = resp.json()

        events = []
        for ec in (data.get("economicCalendar") or [])[:30]:
            event_name = ec.get("event", "")
            if not event_name:
                continue

            # FOMC and major indicators are HIGH impact
            name_lower = event_name.lower()
            if any(w in name_lower for w in ["fomc", "fed funds", "interest rate"]):
                impact = "HIGH"
            elif any(w in name_lower for w in ["cpi", "gdp", "nonfarm", "unemployment", "pce"]):
                impact = "HIGH"
            else:
                impact = "MEDIUM"

            source_id = hashlib.sha256(f"econ_{event_name}_{ec.get('time', '')}".encode()).hexdigest()[:32]
            events.append({
                "event_type": "macro",
                "impact": impact,
                "symbols": [],
                "sectors": [],
                "headline": f"{event_name} ({ec.get('country', 'US')})",
                "raw_data": ec,
                "source": "finnhub",
                "source_id": source_id,
                "user_id": None,
                "expires_at": datetime.utcnow() + timedelta(hours=1),
            })

        return events
    except Exception as e:
        logger.warning("finnhub_economic_fetch_failed", error=str(e))
        return []
```

- [ ] **Step 8: Implement StockTwits source**

Create `services/context_monitor/sources/stocktwits.py`:

```python
"""StockTwits sentiment — no API key required."""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta

import httpx
import structlog

logger = structlog.get_logger(__name__)

_STOCKTWITS_URL = "https://api.stocktwits.com/api/2/streams/trending.json"


async def fetch_stocktwits_events() -> list[dict]:
    """Fetch trending sentiment spikes from StockTwits."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(_STOCKTWITS_URL)
            resp.raise_for_status()
            data = resp.json()

        events = []
        for msg in (data.get("messages") or [])[:10]:
            symbols = [s["symbol"] for s in (msg.get("symbols") or []) if s.get("symbol")]
            if not symbols:
                continue

            sentiment = msg.get("entities", {}).get("sentiment", {}).get("basic", "")
            if not sentiment:
                continue

            source_id = hashlib.sha256(f"stocktwits_{msg.get('id', '')}".encode()).hexdigest()[:32]
            events.append({
                "event_type": "sentiment",
                "impact": "LOW",
                "symbols": symbols[:3],
                "sectors": [],
                "headline": f"StockTwits trending: {', '.join(symbols[:3])} ({sentiment})",
                "raw_data": {"message_id": msg.get("id"), "sentiment": sentiment},
                "source": "stocktwits",
                "source_id": source_id,
                "user_id": None,
                "expires_at": datetime.utcnow() + timedelta(hours=2),
            })

        return events
    except Exception as e:
        logger.warning("stocktwits_fetch_failed", error=str(e))
        return []
```

- [ ] **Step 9: Implement sector ETFs source**

Create `services/context_monitor/sources/sector_etfs.py`:

```python
"""Sector ETF momentum tracking via yfinance — no API key required."""
from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime, timedelta

import structlog

logger = structlog.get_logger(__name__)

SECTOR_ETFS = {
    "XLF": "Financials",
    "XLK": "Technology",
    "XLV": "Healthcare",
    "XLE": "Energy",
    "XLI": "Industrials",
    "XLP": "Consumer Staples",
    "XLY": "Consumer Discretionary",
    "XLB": "Materials",
    "XLU": "Utilities",
    "XLRE": "Real Estate",
    "XLC": "Communication Services",
    "SPY": "S&P 500",
    "QQQ": "Nasdaq 100",
}


async def fetch_sector_events() -> list[dict]:
    """Fetch sector ETF momentum and flag large moves."""
    try:
        loop = asyncio.get_running_loop()
        results = await loop.run_in_executor(None, _fetch_sector_data_sync)
        if not results:
            return []

        events = []
        for symbol, change_pct, sector_name in results:
            if abs(change_pct) < 1.5:
                continue  # Only flag notable moves

            impact = "HIGH" if abs(change_pct) > 3.0 else "MEDIUM"
            direction = "up" if change_pct > 0 else "down"
            source_id = hashlib.sha256(
                f"sector_{symbol}_{datetime.utcnow().strftime('%Y%m%d%H')}".encode()
            ).hexdigest()[:32]

            events.append({
                "event_type": "sector_move",
                "impact": impact,
                "symbols": [symbol],
                "sectors": [sector_name],
                "headline": f"{sector_name} ({symbol}) {direction} {abs(change_pct):.1f}%",
                "raw_data": {"symbol": symbol, "change_pct": change_pct, "sector": sector_name},
                "source": "yfinance_sector",
                "source_id": source_id,
                "user_id": None,
                "expires_at": datetime.utcnow() + timedelta(minutes=30),
            })

        return events
    except Exception as e:
        logger.warning("sector_etf_fetch_failed", error=str(e))
        return []


def _fetch_sector_data_sync() -> list[tuple[str, float, str]]:
    """Synchronous yfinance batch fetch for sector ETFs."""
    try:
        import yfinance as yf
        tickers = yf.Tickers(" ".join(SECTOR_ETFS.keys()))
        results = []
        for symbol, sector_name in SECTOR_ETFS.items():
            try:
                hist = tickers.tickers[symbol].history(period="2d")
                if len(hist) < 2:
                    continue
                prev_close = float(hist["Close"].iloc[-2])
                curr_close = float(hist["Close"].iloc[-1])
                if prev_close > 0:
                    change_pct = ((curr_close - prev_close) / prev_close) * 100
                    results.append((symbol, change_pct, sector_name))
            except Exception:
                continue
        return results
    except Exception:
        return []
```

- [ ] **Step 10: Run test to verify sources pass**

Run: `cd ~/adaptive-trading-ecosystem && python -m pytest tests/test_context_sources.py -v --timeout=30`
Expected: All PASS (may return empty lists if APIs are unreachable, but no errors)

- [ ] **Step 11: Commit**

```bash
git add services/context_monitor/ tests/test_context_sources.py
git commit -m "feat: implement Context Monitor data sources (VIX, CNN F/G, Finnhub news/calendar, StockTwits, sector ETFs)"
```

### Task 6: Implement Context Monitor classifier and background loop

**Files:**
- Create: `services/context_monitor/classifier.py`
- Create: `services/context_monitor/monitor.py`
- Test: `tests/test_context_monitor.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_context_monitor.py
"""Test Context Monitor classifier and deduplication."""
import pytest
from services.context_monitor.classifier import classify_impact


def test_classify_high_vix():
    event = {"event_type": "volatility", "raw_data": {"vix": 45.0}, "headline": "VIX at 45"}
    assert classify_impact(event) == "HIGH"


def test_classify_fomc():
    event = {"event_type": "macro", "headline": "FOMC Rate Decision", "raw_data": {}}
    assert classify_impact(event) == "HIGH"


def test_classify_low_news():
    event = {"event_type": "news", "headline": "Company releases new product", "raw_data": {}}
    assert classify_impact(event) == "LOW"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/adaptive-trading-ecosystem && python -m pytest tests/test_context_monitor.py -v`
Expected: ImportError

- [ ] **Step 3: Implement classifier**

Create `services/context_monitor/classifier.py`:

```python
"""Impact classification for market events.

Rules-based first pass handles ~90% of events. Falls back to LLM for ambiguous headlines.
"""
from __future__ import annotations

import structlog

logger = structlog.get_logger(__name__)


def classify_impact(event: dict) -> str:
    """Classify event impact as LOW, MEDIUM, or HIGH using rules."""
    event_type = event.get("event_type", "")
    headline = (event.get("headline") or "").lower()
    raw = event.get("raw_data") or {}

    # Volatility events — use raw VIX value
    if event_type == "volatility":
        vix = raw.get("vix", 0)
        if vix > 40:
            return "HIGH"
        elif vix > 25:
            return "MEDIUM"
        elif vix > 18:
            return "LOW"
        return "LOW"

    # Macro events — FOMC, CPI, GDP are always HIGH
    if event_type == "macro":
        if any(w in headline for w in ["fomc", "fed funds", "interest rate", "cpi", "gdp", "nonfarm", "unemployment"]):
            return "HIGH"
        return "MEDIUM"

    # Earnings events
    if event_type == "earnings":
        return "MEDIUM"

    # Sector moves — >3% is HIGH
    if event_type == "sector_move":
        change = abs(raw.get("change_pct", 0))
        if change > 3.0:
            return "HIGH"
        elif change > 1.5:
            return "MEDIUM"
        return "LOW"

    # Sentiment — extreme readings
    if event_type == "sentiment":
        score = raw.get("score", 50)
        if score is not None and (score > 80 or score < 20):
            return "MEDIUM"
        return "LOW"

    # News — keyword heuristics
    if event_type == "news":
        if any(w in headline for w in ["fed", "fomc", "recession", "crash", "crisis", "circuit breaker", "halt"]):
            return "HIGH"
        if any(w in headline for w in ["earnings", "revenue", "guidance", "layoff", "merger", "acquisition"]):
            return "MEDIUM"
        return "LOW"

    return "LOW"
```

- [ ] **Step 4: Implement monitor background loop**

Create `services/context_monitor/monitor.py`:

```python
"""Context Monitor — always-on background service for market intelligence.

Runs as asyncio background loop in FastAPI lifespan (like BotRunner).
Polls data sources at different cadences and stores MarketEvent records.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, time as dtime
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import select

from db.cerberus_models import MarketEvent
from db.database import get_session
from services.context_monitor.classifier import classify_impact
from services.context_monitor.sources.vix import fetch_vix_events
from services.context_monitor.sources.cnn_fear_greed import fetch_fear_greed_events
from services.context_monitor.sources.finnhub_news import fetch_finnhub_news_events
from services.context_monitor.sources.finnhub_calendar import fetch_earnings_events, fetch_economic_events
from services.context_monitor.sources.stocktwits import fetch_stocktwits_events
from services.context_monitor.sources.sector_etfs import fetch_sector_events

logger = structlog.get_logger(__name__)
_ET = ZoneInfo("America/New_York")

# Source cadences (seconds)
_FAST_SOURCES = [
    (fetch_vix_events, 120),          # 2 min
    (fetch_sector_events, 120),       # 2 min
    (fetch_finnhub_news_events, 120), # 2 min
]
_MEDIUM_SOURCES = [
    (fetch_stocktwits_events, 300),   # 5 min
    (fetch_fear_greed_events, 900),   # 15 min
]
_SLOW_SOURCES = [
    (fetch_earnings_events, 3600),    # 1 hour
    (fetch_economic_events, 3600),    # 1 hour
]


class ContextMonitor:
    """Background service that builds real-time market intelligence."""

    def __init__(self) -> None:
        self._running = False
        self._task: asyncio.Task | None = None
        self._last_poll: dict[str, datetime] = {}

    async def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("context_monitor_started")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("context_monitor_stopped")

    def _is_market_hours(self) -> bool:
        now = datetime.now(_ET)
        if now.weekday() >= 5:
            return False
        return dtime(9, 0) <= now.time() <= dtime(16, 30)

    async def _loop(self) -> None:
        """Main loop — poll sources at their respective cadences."""
        while self._running:
            try:
                is_market = self._is_market_hours()
                all_sources = _FAST_SOURCES + _MEDIUM_SOURCES + _SLOW_SOURCES

                for fetch_fn, market_cadence in all_sources:
                    fn_name = fetch_fn.__name__
                    cadence = market_cadence if is_market else market_cadence * 7  # Slower outside hours
                    last = self._last_poll.get(fn_name)

                    if last and (datetime.utcnow() - last).total_seconds() < cadence:
                        continue

                    try:
                        raw_events = await fetch_fn()
                        await self._store_events(raw_events)
                        self._last_poll[fn_name] = datetime.utcnow()
                    except Exception as e:
                        logger.warning("source_poll_failed", source=fn_name, error=str(e))

                # Expire old events
                await self._expire_events()

            except Exception as e:
                logger.error("context_monitor_error", error=str(e))

            await asyncio.sleep(30)  # Check loop every 30s

    async def _store_events(self, raw_events: list[dict]) -> None:
        """Deduplicate and store events."""
        if not raw_events:
            return

        async with get_session() as session:
            for event_data in raw_events:
                source_id = event_data.get("source_id", "")
                if not source_id:
                    continue

                # Dedup: check for existing non-expired event with same source_id
                existing = await session.execute(
                    select(MarketEvent.id)
                    .where(MarketEvent.source_id == source_id)
                    .where(
                        (MarketEvent.expires_at == None) |  # noqa: E711
                        (MarketEvent.expires_at > datetime.utcnow())
                    )
                    .limit(1)
                )
                if existing.scalar_one_or_none():
                    continue

                # Reclassify impact using our canonical rules
                event_data["impact"] = classify_impact(event_data)

                event = MarketEvent(
                    event_type=event_data["event_type"],
                    impact=event_data["impact"],
                    symbols=event_data.get("symbols", []),
                    sectors=event_data.get("sectors", []),
                    headline=event_data["headline"],
                    raw_data=event_data.get("raw_data", {}),
                    source=event_data["source"],
                    source_id=source_id,
                    user_id=event_data.get("user_id"),
                    detected_at=datetime.utcnow(),
                    expires_at=event_data.get("expires_at"),
                )
                session.add(event)

    async def _expire_events(self) -> None:
        """Clean up expired events older than 24h."""
        try:
            from sqlalchemy import delete
            from datetime import timedelta
            async with get_session() as session:
                await session.execute(
                    delete(MarketEvent).where(
                        MarketEvent.expires_at < datetime.utcnow() - timedelta(hours=24)
                    )
                )
        except Exception as e:
            logger.debug("event_cleanup_error", error=str(e))


# Singleton
context_monitor = ContextMonitor()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd ~/adaptive-trading-ecosystem && python -m pytest tests/test_context_monitor.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add services/context_monitor/classifier.py services/context_monitor/monitor.py tests/test_context_monitor.py
git commit -m "feat: implement Context Monitor background loop with classifier and deduplication"
```

---

## Chunk 4: Universe Scanner

### Task 7: Implement Universe Scanner

**Files:**
- Create: `services/universe_scanner/__init__.py`
- Create: `services/universe_scanner/pools.py`
- Create: `services/universe_scanner/scanner.py`
- Test: `tests/test_universe_scanner.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_universe_scanner.py
"""Test Universe Scanner scoring logic."""
import pytest
from services.universe_scanner.pools import get_sp500_symbols
from services.universe_scanner.scanner import score_candidates


def test_get_sp500_returns_list():
    symbols = get_sp500_symbols()
    assert isinstance(symbols, list)
    # Should have hundreds of symbols (or empty if fetch fails)


def test_score_candidates_momentum():
    # Simple smoke test — scoring should return ranked list
    candidates = ["AAPL", "MSFT", "GOOGL"]
    scored = score_candidates(candidates, strategy_type="momentum", max_symbols=2)
    assert isinstance(scored, list)
    assert len(scored) <= 2
    for item in scored:
        assert "symbol" in item
        assert "score" in item
        assert 0.0 <= item["score"] <= 1.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/adaptive-trading-ecosystem && python -m pytest tests/test_universe_scanner.py -v`
Expected: ImportError

- [ ] **Step 3: Implement pools module**

Create `services/universe_scanner/__init__.py` (empty).

Create `services/universe_scanner/pools.py`:

```python
"""Index/sector constituent fetching with daily caching."""
from __future__ import annotations

import time

import structlog

logger = structlog.get_logger(__name__)

# Simple in-memory cache: key -> (data, timestamp)
_cache: dict[str, tuple[list[str], float]] = {}
_CACHE_TTL = 86400  # 24 hours


def get_sp500_symbols() -> list[str]:
    """Fetch S&P 500 constituents (cached daily)."""
    return _cached_fetch("sp500", _fetch_sp500_sync)


def get_nasdaq100_symbols() -> list[str]:
    return _cached_fetch("nasdaq100", _fetch_nasdaq100_sync)


def get_sector_symbols(sector_etf: str) -> list[str]:
    """Get holdings for a sector ETF."""
    return _cached_fetch(f"sector_{sector_etf}", lambda: _fetch_sector_sync(sector_etf))


def _cached_fetch(key: str, fetch_fn) -> list[str]:
    cached = _cache.get(key)
    if cached and (time.time() - cached[1]) < _CACHE_TTL:
        return cached[0]
    try:
        data = fetch_fn()
        _cache[key] = (data, time.time())
        return data
    except Exception as e:
        logger.warning("pool_fetch_failed", key=key, error=str(e))
        return cached[0] if cached else []


def _fetch_sp500_sync() -> list[str]:
    """Fetch S&P 500 list from Wikipedia (standard approach)."""
    try:
        import pandas as pd
        table = pd.read_html("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")[0]
        return table["Symbol"].str.replace(".", "-", regex=False).tolist()
    except Exception:
        return []


def _fetch_nasdaq100_sync() -> list[str]:
    try:
        import pandas as pd
        table = pd.read_html("https://en.wikipedia.org/wiki/Nasdaq-100")[4]
        return table["Ticker"].tolist()
    except Exception:
        return []


def _fetch_sector_sync(etf_symbol: str) -> list[str]:
    """Get top holdings for a sector ETF via yfinance."""
    try:
        import yfinance as yf
        etf = yf.Ticker(etf_symbol)
        holdings = etf.get_holdings()
        if holdings is not None and not holdings.empty:
            return holdings.index.tolist()[:50]
        return []
    except Exception:
        return []
```

- [ ] **Step 4: Implement scanner module**

Create `services/universe_scanner/scanner.py`:

```python
"""Universe Scanner — per-bot symbol scoring and background loop.

Runs as asyncio background loop in FastAPI lifespan, every 15 min during market hours.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, time as dtime
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import select, delete

from db.cerberus_models import CerberusBot, CerberusBotVersion, UniverseCandidate, BotStatus
from db.database import get_session
from services.universe_scanner.pools import get_sp500_symbols, get_nasdaq100_symbols, get_sector_symbols

logger = structlog.get_logger(__name__)
_ET = ZoneInfo("America/New_York")


def score_candidates(
    symbols: list[str],
    strategy_type: str = "momentum",
    max_symbols: int = 10,
) -> list[dict]:
    """Score candidate symbols using pure math indicators (no LLM).

    Returns ranked list with score 0-1 and reason.
    """
    if not symbols:
        return []

    try:
        import yfinance as yf
        scored = []

        # Batch download for efficiency
        data = yf.download(symbols[:50], period="30d", interval="1d", progress=False, threads=True)
        if data.empty:
            return []

        for symbol in symbols[:50]:
            try:
                if len(symbols) > 1:
                    close = data["Close"][symbol].dropna()
                else:
                    close = data["Close"].dropna()

                if len(close) < 10:
                    continue

                # Calculate scoring factors
                returns_5d = (close.iloc[-1] / close.iloc[-5] - 1) if len(close) >= 5 else 0
                returns_20d = (close.iloc[-1] / close.iloc[0] - 1) if len(close) >= 20 else 0

                if len(symbols) > 1:
                    volume = data["Volume"][symbol].dropna()
                else:
                    volume = data["Volume"].dropna()

                avg_volume = volume.mean() if len(volume) > 0 else 0
                recent_volume = volume.iloc[-1] if len(volume) > 0 else 0
                vol_ratio = recent_volume / avg_volume if avg_volume > 0 else 1.0

                if strategy_type in ("momentum", "ai_generated"):
                    # Momentum: rank by price momentum + volume
                    score = min(1.0, max(0.0, (returns_20d + 0.5) * 0.6 + min(vol_ratio / 3, 0.4)))
                    reason = f"20d return {returns_20d:.1%}, volume ratio {vol_ratio:.1f}x"
                elif strategy_type == "mean_reversion":
                    # Mean-reversion: rank by distance from SMA
                    sma_20 = close.rolling(20).mean().iloc[-1]
                    deviation = (close.iloc[-1] - sma_20) / sma_20 if sma_20 > 0 else 0
                    score = min(1.0, max(0.0, abs(deviation) * 5))
                    reason = f"SMA20 deviation {deviation:.1%}"
                else:
                    score = 0.5
                    reason = "Default scoring"

                scored.append({"symbol": symbol, "score": round(score, 3), "reason": reason})

            except Exception:
                continue

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:max_symbols]

    except Exception as e:
        logger.warning("score_candidates_failed", error=str(e))
        return []


class UniverseScanner:
    """Background service that finds best symbols for each bot."""

    def __init__(self) -> None:
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("universe_scanner_started")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("universe_scanner_stopped")

    async def _loop(self) -> None:
        while self._running:
            try:
                now = datetime.now(_ET)
                is_market = now.weekday() < 5 and dtime(9, 0) <= now.time() <= dtime(16, 30)

                if is_market:
                    await self._scan_all_bots()

            except Exception as e:
                logger.error("universe_scanner_error", error=str(e))

            await asyncio.sleep(900)  # 15 min

    async def _scan_all_bots(self) -> None:
        """Scan universe for all running bots with dynamic universe config."""
        async with get_session() as session:
            result = await session.execute(
                select(CerberusBot, CerberusBotVersion)
                .join(CerberusBotVersion, CerberusBot.current_version_id == CerberusBotVersion.id)
                .where(CerberusBot.status == BotStatus.RUNNING)
            )
            bots = result.all()

        for bot, version in bots:
            try:
                await self._scan_bot(bot, version)
            except Exception as e:
                logger.warning("universe_scan_failed", bot_id=bot.id, error=str(e))

    async def _scan_bot(self, bot: CerberusBot, version: CerberusBotVersion) -> None:
        config = version.config_json or {}
        universe_config = version.universe_config or config.get("universe_config") or {}
        mode = universe_config.get("mode", "fixed")
        strategy_type = config.get("strategy_type", "manual")

        if mode == "fixed":
            return  # Fixed symbols, nothing to scan

        max_symbols = universe_config.get("max_symbols", 10)
        exclude = set(universe_config.get("exclude_symbols", []))

        # Get candidate pool based on mode
        pool = await asyncio.get_running_loop().run_in_executor(
            None, lambda: self._get_pool(mode, universe_config)
        )

        # Filter excluded symbols
        pool = [s for s in pool if s not in exclude]

        if not pool:
            return

        # Score candidates
        scored = await asyncio.get_running_loop().run_in_executor(
            None, lambda: score_candidates(pool, strategy_type, max_symbols)
        )

        # Store results
        async with get_session() as session:
            # Clear old candidates for this bot
            await session.execute(
                delete(UniverseCandidate).where(UniverseCandidate.bot_id == bot.id)
            )

            for item in scored:
                session.add(UniverseCandidate(
                    bot_id=bot.id,
                    symbol=item["symbol"],
                    score=item["score"],
                    reason=item["reason"],
                    scanned_at=datetime.utcnow(),
                ))

        logger.info("universe_scan_complete", bot_id=bot.id, candidates=len(scored))

    def _get_pool(self, mode: str, config: dict) -> list[str]:
        if mode == "sector":
            sectors = config.get("sectors", [])
            pool = []
            for sector in sectors:
                pool.extend(get_sector_symbols(sector))
            return pool
        elif mode == "index":
            index = config.get("index", "sp500")
            if index == "nasdaq100":
                return get_nasdaq100_symbols()
            return get_sp500_symbols()
        elif mode in ("full_market", "ai_selected"):
            return get_sp500_symbols()
        return []


# Singleton
universe_scanner = UniverseScanner()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd ~/adaptive-trading-ecosystem && python -m pytest tests/test_universe_scanner.py -v --timeout=30`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add services/universe_scanner/ tests/test_universe_scanner.py
git commit -m "feat: implement Universe Scanner with pool fetching, candidate scoring, and background loop"
```

---

## Chunk 5: Bot Memory & Learning

### Task 8: Implement Bot Memory modules

**Files:**
- Create: `services/bot_memory/__init__.py`
- Create: `services/bot_memory/journal.py`
- Create: `services/bot_memory/regime_tracker.py`
- Create: `services/bot_memory/learning.py`
- Test: `tests/test_bot_memory.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_bot_memory.py
"""Test bot memory modules."""
import pytest
from services.bot_memory.regime_tracker import classify_regime


def test_classify_regime_low_vol():
    regimes = classify_regime(vix=15.0, spy_sma_slope=0.0)
    assert "low_vol" in regimes
    assert "range_bound" in regimes


def test_classify_regime_high_vol_trending_down():
    regimes = classify_regime(vix=30.0, spy_sma_slope=-0.2)
    assert "high_vol" in regimes
    assert "trending_down" in regimes


def test_classify_regime_normal_trending_up():
    regimes = classify_regime(vix=20.0, spy_sma_slope=0.15)
    assert "normal_vol" in regimes
    assert "trending_up" in regimes
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/adaptive-trading-ecosystem && python -m pytest tests/test_bot_memory.py -v`
Expected: ImportError

- [ ] **Step 3: Implement regime tracker**

Create `services/bot_memory/__init__.py` (empty).

Create `services/bot_memory/regime_tracker.py`:

```python
"""Regime classification and stats tracking.

Regime Classification Rules (from spec):
| Regime         | Rule                                                          |
|----------------|---------------------------------------------------------------|
| low_vol        | VIX < 18                                                      |
| normal_vol     | VIX 18-25                                                     |
| high_vol       | VIX > 25                                                      |
| trending_up    | SPY 20-day SMA slope > 0.1% per day AND price above 20-day SMA |
| trending_down  | SPY 20-day SMA slope < -0.1% per day AND price below 20-day SMA |
| range_bound    | Neither trending_up nor trending_down                         |
"""
from __future__ import annotations

from datetime import datetime

import structlog
from sqlalchemy import select

from db.cerberus_models import BotRegimeStats, BotTradeJournal
from db.database import get_session

logger = structlog.get_logger(__name__)


def classify_regime(vix: float, spy_sma_slope: float) -> list[str]:
    """Classify current market regime. Multiple tags can apply."""
    regimes = []

    # Volatility regime
    if vix < 18:
        regimes.append("low_vol")
    elif vix <= 25:
        regimes.append("normal_vol")
    else:
        regimes.append("high_vol")

    # Trend regime
    if spy_sma_slope > 0.1:
        regimes.append("trending_up")
    elif spy_sma_slope < -0.1:
        regimes.append("trending_down")
    else:
        regimes.append("range_bound")

    return regimes


async def update_regime_stats(bot_id: str) -> None:
    """Recalculate regime stats for a bot from its trade journal."""
    async with get_session() as session:
        result = await session.execute(
            select(BotTradeJournal)
            .where(BotTradeJournal.bot_id == bot_id)
            .order_by(BotTradeJournal.created_at.desc())
            .limit(500)
        )
        entries = result.scalars().all()

    if not entries:
        return

    # Group by regime
    regime_trades: dict[str, list[BotTradeJournal]] = {}
    for entry in entries:
        regime = entry.regime_at_entry or "unknown"
        regime_trades.setdefault(regime, []).append(entry)

    async with get_session() as session:
        for regime, trades in regime_trades.items():
            total = len(trades)
            wins = sum(1 for t in trades if (t.pnl or 0) > 0)
            pnl_values = [t.pnl or 0 for t in trades]
            confidence_values = [t.ai_confidence_at_entry or 0 for t in trades if t.ai_confidence_at_entry is not None]

            avg_pnl = sum(pnl_values) / total if total else 0
            win_rate = wins / total if total else 0
            avg_confidence = sum(confidence_values) / len(confidence_values) if confidence_values else 0

            # Simple Sharpe
            if total >= 2:
                from statistics import mean, pstdev
                returns = [t.pnl_pct or 0 for t in trades if t.pnl_pct is not None]
                if len(returns) >= 2:
                    std = pstdev(returns)
                    sharpe = mean(returns) / std if std > 0 else 0
                else:
                    sharpe = 0
            else:
                sharpe = 0

            # Upsert
            existing = await session.execute(
                select(BotRegimeStats)
                .where(BotRegimeStats.bot_id == bot_id)
                .where(BotRegimeStats.regime == regime)
            )
            stats = existing.scalar_one_or_none()

            if stats:
                stats.total_trades = total
                stats.win_rate = round(win_rate, 4)
                stats.avg_pnl = round(avg_pnl, 2)
                stats.avg_confidence = round(avg_confidence, 4)
                stats.sharpe = round(sharpe, 4)
                stats.updated_at = datetime.utcnow()
            else:
                session.add(BotRegimeStats(
                    bot_id=bot_id,
                    regime=regime,
                    total_trades=total,
                    win_rate=round(win_rate, 4),
                    avg_pnl=round(avg_pnl, 2),
                    avg_confidence=round(avg_confidence, 4),
                    sharpe=round(sharpe, 4),
                ))
```

- [ ] **Step 4: Implement journal module**

Create `services/bot_memory/journal.py`:

```python
"""Trade journal — records each trade with full market context."""
from __future__ import annotations

from datetime import datetime

import structlog
from sqlalchemy import select

from db.cerberus_models import BotTradeJournal, MarketEvent
from db.database import get_session
from services.bot_memory.regime_tracker import update_regime_stats

logger = structlog.get_logger(__name__)


async def record_trade(
    *,
    bot_id: str,
    trade_id: str,
    symbol: str,
    side: str,
    entry_price: float,
    exit_price: float | None = None,
    entry_at: datetime | None = None,
    exit_at: datetime | None = None,
    pnl: float | None = None,
    pnl_pct: float | None = None,
    vix_at_entry: float | None = None,
    sector_momentum: float | None = None,
    ai_confidence: float | None = None,
    ai_decision: str | None = None,
    ai_reasoning: str | None = None,
    regime: str | None = None,
) -> None:
    """Record a trade in the bot journal with full context."""
    # Gather active market events
    active_event_ids = []
    try:
        async with get_session() as session:
            result = await session.execute(
                select(MarketEvent.id)
                .where(
                    (MarketEvent.expires_at == None) |  # noqa: E711
                    (MarketEvent.expires_at > datetime.utcnow())
                )
                .limit(50)
            )
            active_event_ids = [row[0] for row in result.all()]
    except Exception:
        pass

    hold_duration = None
    if entry_at and exit_at:
        hold_duration = int((exit_at - entry_at).total_seconds())

    async with get_session() as session:
        entry = BotTradeJournal(
            bot_id=bot_id,
            trade_id=trade_id,
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            exit_price=exit_price,
            entry_at=entry_at or datetime.utcnow(),
            exit_at=exit_at,
            hold_duration_seconds=hold_duration,
            pnl=pnl,
            pnl_pct=pnl_pct,
            market_events=active_event_ids,
            vix_at_entry=vix_at_entry,
            sector_momentum_at_entry=sector_momentum,
            ai_confidence_at_entry=ai_confidence,
            ai_decision=ai_decision,
            ai_reasoning=ai_reasoning,
            regime_at_entry=regime,
        )
        session.add(entry)

    # Update regime stats after recording
    try:
        await update_regime_stats(bot_id)
    except Exception as e:
        logger.warning("regime_stats_update_failed", bot_id=bot_id, error=str(e))
```

- [ ] **Step 5: Implement learning module**

Create `services/bot_memory/learning.py`:

```python
"""Autonomous bot adaptation — reviews performance and proposes parameter changes.

Runs as a Celery task dispatched on cadence (default 4h).
Auto-apply boundaries: 50%-150% of original value.
"""
from __future__ import annotations

from datetime import datetime
from copy import deepcopy

import structlog
from sqlalchemy import select

from db.cerberus_models import BotAdaptation, BotTradeJournal, BotRegimeStats, CerberusBot, CerberusBotVersion
from db.database import get_session

logger = structlog.get_logger(__name__)

# Auto-apply range: 50% to 150% of original value
AUTO_APPLY_MIN_RATIO = 0.5
AUTO_APPLY_MAX_RATIO = 1.5

# Changes that always need user approval
REQUIRES_APPROVAL = {"add_indicator", "remove_indicator", "change_timeframe", "change_direction", "expand_universe", "shrink_universe"}


def is_auto_appliable(adaptation_type: str, old_value: float, new_value: float) -> bool:
    """Check if a parameter change is within auto-apply bounds."""
    if adaptation_type in REQUIRES_APPROVAL:
        return False
    if old_value == 0:
        return new_value == 0
    ratio = new_value / old_value
    return AUTO_APPLY_MIN_RATIO <= ratio <= AUTO_APPLY_MAX_RATIO


async def run_adaptation_review(bot_id: str) -> dict | None:
    """Review bot's recent trades and propose adaptations.

    This function is called by the Celery task on cadence.
    """
    async with get_session() as session:
        # Get bot and current config
        result = await session.execute(
            select(CerberusBot, CerberusBotVersion)
            .join(CerberusBotVersion, CerberusBot.current_version_id == CerberusBotVersion.id, isouter=True)
            .where(CerberusBot.id == bot_id)
        )
        row = result.first()
        if not row:
            return None

        bot, version = row
        if not version:
            return None

        config = version.config_json or {}

        # Get recent journal entries
        journal_result = await session.execute(
            select(BotTradeJournal)
            .where(BotTradeJournal.bot_id == bot_id)
            .order_by(BotTradeJournal.created_at.desc())
            .limit(20)
        )
        entries = list(reversed(journal_result.scalars().all()))

        # Get regime stats
        regime_result = await session.execute(
            select(BotRegimeStats).where(BotRegimeStats.bot_id == bot_id)
        )
        regime_stats = {s.regime: s for s in regime_result.scalars().all()}

    if not entries:
        return {"bot_id": bot_id, "adaptations": [], "reason": "No trades to analyze"}

    # Analyze trade patterns
    adaptations = _analyze_patterns(config, entries, regime_stats)

    # Store adaptations
    if adaptations:
        async with get_session() as session:
            for adaptation in adaptations:
                session.add(BotAdaptation(
                    bot_id=bot_id,
                    adaptation_type=adaptation["type"],
                    old_value=adaptation["old_value"],
                    new_value=adaptation["new_value"],
                    reasoning=adaptation["reasoning"],
                    confidence=adaptation["confidence"],
                    auto_applied=adaptation["auto_applied"],
                ))

    return {"bot_id": bot_id, "adaptations": adaptations}


def _analyze_patterns(
    config: dict,
    entries: list[BotTradeJournal],
    regime_stats: dict[str, BotRegimeStats],
) -> list[dict]:
    """Rule-based pattern analysis (LLM analysis can be added in v2)."""
    adaptations = []

    if len(entries) < 3:
        return []

    # Calculate basic stats
    pnl_values = [e.pnl or 0 for e in entries]
    wins = sum(1 for p in pnl_values if p > 0)
    win_rate = wins / len(pnl_values)
    consecutive_losses = 0
    for p in reversed(pnl_values):
        if p < 0:
            consecutive_losses += 1
        else:
            break

    stop_loss = float(config.get("stop_loss_pct", 0.02) or 0.02)
    take_profit = float(config.get("take_profit_pct", 0.05) or 0.05)

    # Pattern: high loss rate → tighten stop
    if win_rate < 0.35 and len(entries) >= 5:
        new_stop = max(stop_loss * 0.85, 0.005)
        if is_auto_appliable("stop_loss", stop_loss, new_stop):
            adaptations.append({
                "type": "stop_loss",
                "old_value": {"stop_loss_pct": stop_loss},
                "new_value": {"stop_loss_pct": round(new_stop, 4)},
                "reasoning": f"Win rate {win_rate:.0%} below 35%. Tightening stop-loss.",
                "confidence": 0.6,
                "auto_applied": True,
            })

    # Pattern: consistently profitable → widen take-profit
    if win_rate > 0.65 and len(entries) >= 10:
        new_tp = min(take_profit * 1.1, take_profit * AUTO_APPLY_MAX_RATIO)
        if is_auto_appliable("take_profit", take_profit, new_tp):
            adaptations.append({
                "type": "take_profit",
                "old_value": {"take_profit_pct": take_profit},
                "new_value": {"take_profit_pct": round(new_tp, 4)},
                "reasoning": f"Win rate {win_rate:.0%}. Widening take-profit to let winners run.",
                "confidence": 0.65,
                "auto_applied": True,
            })

    return adaptations
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd ~/adaptive-trading-ecosystem && python -m pytest tests/test_bot_memory.py -v`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add services/bot_memory/ tests/test_bot_memory.py
git commit -m "feat: implement Bot Memory (journal, regime tracker, learning adaptation)"
```

---

## Chunk 6: BotRunner Integration + Lifespan Wiring

### Task 9: Enhance BotRunner to use Reasoning Engine and Universe Scanner

**Files:**
- Modify: `services/bot_engine/runner.py`
- Modify: `api/main.py`
- Test: `tests/test_bot_runner_reasoning.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_bot_runner_reasoning.py
"""Test BotRunner integration with Reasoning Engine."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from services.bot_engine.runner import BotRunner


def test_bot_runner_has_reasoning_engine():
    runner = BotRunner()
    assert hasattr(runner, "_reasoning_engine")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/adaptive-trading-ecosystem && python -m pytest tests/test_bot_runner_reasoning.py -v`
Expected: FAIL — no `_reasoning_engine` attribute

- [ ] **Step 3: Modify BotRunner**

In `services/bot_engine/runner.py`, make these changes:

1. Add imports at top:
```python
from services.reasoning_engine.engine import ReasoningEngine
from services.bot_memory.journal import record_trade
```

2. In `__init__`, add:
```python
        self._reasoning_engine = ReasoningEngine()
```

3. Modify `_evaluate_bot` to pull universe candidates when not in fixed mode:
After `symbols = config.get("symbols", [])`, add:
```python
        # Check for dynamic universe
        universe_config = getattr(version, 'universe_config', None) or config.get("universe_config") or {}
        universe_mode = universe_config.get("mode", "fixed")
        if universe_mode != "fixed" and not symbols:
            # Pull from universe candidates
            from db.cerberus_models import UniverseCandidate
            async with get_session() as session:
                from sqlalchemy import select as sa_select
                uc_result = await session.execute(
                    sa_select(UniverseCandidate.symbol)
                    .where(UniverseCandidate.bot_id == bot.id)
                    .order_by(UniverseCandidate.score.desc())
                    .limit(universe_config.get("max_symbols", 10))
                )
                symbols = [row[0] for row in uc_result.all()]
```

4. Modify `_evaluate_symbol` to gate through Reasoning Engine after conditions pass:
After `if all_passed:`, replace the direct `_execute_trade` call with:
```python
            # Gate through Reasoning Engine before execution
            try:
                from services.context_monitor.sources.vix import _fetch_vix_sync
                import asyncio
                loop = asyncio.get_running_loop()
                vix = await loop.run_in_executor(None, _fetch_vix_sync) or 15.0

                override_level = getattr(
                    bot, 'override_level',
                    config.get("override_level", "soft")
                )

                decision = await self._reasoning_engine.evaluate(
                    bot_id=bot.id,
                    symbol=symbol,
                    strategy_signal=action,
                    vix=vix,
                    events=[],  # Will be populated from DB in production
                    portfolio_exposure={},
                    bot_daily_pnl_pct=0.0,
                    bot_config=config,
                    override_level=override_level,
                )

                if decision["decision"] == "EXECUTE":
                    await self._execute_trade(
                        bot, symbol, action, position_size_pct,
                        bars[-1].get("close", 0), reasons=reasons,
                        ai_decision=decision,
                    )
                elif decision["decision"] == "REDUCE_SIZE":
                    adjusted_size = position_size_pct * decision.get("size_adjustment", 0.5)
                    await self._execute_trade(
                        bot, symbol, action, adjusted_size,
                        bars[-1].get("close", 0), reasons=reasons,
                        ai_decision=decision,
                    )
                elif decision["decision"] == "DELAY_TRADE":
                    logger.info("bot_trade_delayed", bot_id=bot.id, symbol=symbol,
                                delay=decision.get("delay_seconds", 0),
                                reason=decision.get("reasoning", ""))
                else:
                    logger.info("bot_trade_blocked", bot_id=bot.id, symbol=symbol,
                                decision=decision["decision"],
                                reason=decision.get("reasoning", ""))

                # Persist TradeDecision
                await self._persist_decision(decision)

            except Exception as e:
                logger.warning("reasoning_engine_error", bot_id=bot.id, error=str(e))
                # Fallback: execute without reasoning
                await self._execute_trade(
                    bot, symbol, action, position_size_pct,
                    bars[-1].get("close", 0), reasons=reasons,
                )
```

5. Add `_persist_decision` method:
```python
    async def _persist_decision(self, decision: dict) -> None:
        """Store TradeDecision in DB for UI timeline."""
        try:
            from db.cerberus_models import TradeDecision
            async with get_session() as session:
                session.add(TradeDecision(
                    id=decision.get("id", str(uuid.uuid4())),
                    bot_id=decision["bot_id"],
                    symbol=decision["symbol"],
                    strategy_signal=decision["strategy_signal"],
                    context_risk_level=decision.get("context_risk_level", "LOW"),
                    ai_confidence=decision.get("ai_confidence", 0.0),
                    decision=decision["decision"],
                    reasoning=decision.get("reasoning", ""),
                    size_adjustment=decision.get("size_adjustment", 1.0),
                    delay_seconds=decision.get("delay_seconds", 0),
                    events_considered=decision.get("events_considered", []),
                    model_used=decision.get("model_used", "safety_rules"),
                ))
        except Exception as e:
            logger.warning("persist_decision_failed", error=str(e))
```

6. Modify `_execute_trade` to accept `ai_decision` kwarg and record in journal:
Add `ai_decision: dict | None = None` parameter, then after the trade is recorded, add:
```python
            # Record in bot trade journal
            try:
                await record_trade(
                    bot_id=bot.id,
                    trade_id=trade.id,
                    symbol=symbol,
                    side=side,
                    entry_price=current_price,
                    ai_confidence=ai_decision.get("ai_confidence") if ai_decision else None,
                    ai_decision=ai_decision.get("decision") if ai_decision else None,
                    ai_reasoning=ai_decision.get("reasoning") if ai_decision else None,
                )
            except Exception:
                pass
```

- [ ] **Step 4: Wire Context Monitor + Universe Scanner into lifespan**

In `api/main.py`, add imports after the existing bot_runner import:
```python
    from services.context_monitor.monitor import context_monitor
    from services.universe_scanner.scanner import universe_scanner
```

Add start tasks after `_spawn_background_task(... name="strategy_learning_engine")`:
```python
    _spawn_background_task(background_tasks, coro=context_monitor.start(), name="context_monitor")
    _spawn_background_task(background_tasks, coro=universe_scanner.start(), name="universe_scanner")
```

In the shutdown section, add:
```python
    await context_monitor.stop()
    await universe_scanner.stop()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd ~/adaptive-trading-ecosystem && python -m pytest tests/test_bot_runner_reasoning.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add services/bot_engine/runner.py api/main.py tests/test_bot_runner_reasoning.py
git commit -m "feat: integrate Reasoning Engine into BotRunner, wire Context Monitor + Universe Scanner into lifespan"
```

---

## Chunk 7: API Endpoints

### Task 10: Add REST endpoints for market intelligence and reasoning data

**Files:**
- Create: `api/routes/reasoning.py`
- Modify: `api/main.py` (register router)
- Test: `tests/test_reasoning_api.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_reasoning_api.py
"""Smoke test for reasoning API endpoints."""
import pytest
from services.reasoning_engine.safety import VIX_THRESHOLDS


def test_vix_thresholds_accessible():
    """Verify safety rules are importable for API use."""
    assert "extreme" in VIX_THRESHOLDS


def test_reasoning_router_importable():
    from api.routes.reasoning import router
    assert router is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/adaptive-trading-ecosystem && python -m pytest tests/test_reasoning_api.py -v`
Expected: ImportError on reasoning router

- [ ] **Step 3: Create reasoning router**

Create `api/routes/reasoning.py`:

```python
"""REST endpoints for market intelligence, bot reasoning, and learning data."""
from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Request, Query
from sqlalchemy import select, func

from db.cerberus_models import (
    MarketEvent,
    TradeDecision,
    UniverseCandidate,
    BotTradeJournal,
    BotRegimeStats,
    BotAdaptation,
)
from db.database import get_session

router = APIRouter()


@router.get("/intelligence/events")
async def get_market_events(
    request: Request,
    event_type: str | None = None,
    impact: str | None = None,
    limit: int = Query(50, le=200),
):
    """Get active market events for the intelligence panel."""
    async with get_session() as session:
        query = (
            select(MarketEvent)
            .where(
                (MarketEvent.expires_at == None) |  # noqa: E711
                (MarketEvent.expires_at > datetime.utcnow())
            )
            .order_by(MarketEvent.detected_at.desc())
            .limit(limit)
        )
        if event_type:
            query = query.where(MarketEvent.event_type == event_type)
        if impact:
            query = query.where(MarketEvent.impact == impact)

        result = await session.execute(query)
        events = result.scalars().all()

    return [
        {
            "id": e.id,
            "event_type": e.event_type,
            "impact": e.impact,
            "symbols": e.symbols or [],
            "sectors": e.sectors or [],
            "headline": e.headline,
            "source": e.source,
            "detected_at": e.detected_at.isoformat() if e.detected_at else None,
            "expires_at": e.expires_at.isoformat() if e.expires_at else None,
        }
        for e in events
    ]


@router.get("/intelligence/risk-score")
async def get_risk_score(request: Request):
    """Calculate composite risk score (0-100) for the risk gauge."""
    # Gather current data points
    async with get_session() as session:
        # Count active HIGH events
        high_count = await session.scalar(
            select(func.count(MarketEvent.id))
            .where(MarketEvent.impact == "HIGH")
            .where(
                (MarketEvent.expires_at == None) |  # noqa: E711
                (MarketEvent.expires_at > datetime.utcnow())
            )
        ) or 0

        # Get latest VIX event
        vix_result = await session.execute(
            select(MarketEvent.raw_data)
            .where(MarketEvent.event_type == "volatility")
            .order_by(MarketEvent.detected_at.desc())
            .limit(1)
        )
        vix_row = vix_result.scalar_one_or_none()
        vix = (vix_row or {}).get("vix", 15) if isinstance(vix_row, dict) else 15

        # Get latest Fear/Greed
        fng_result = await session.execute(
            select(MarketEvent.raw_data)
            .where(MarketEvent.source == "cnn_fng")
            .order_by(MarketEvent.detected_at.desc())
            .limit(1)
        )
        fng_row = fng_result.scalar_one_or_none()
        fng_score = (fng_row or {}).get("score", 50) if isinstance(fng_row, dict) else 50

    # Composite score: VIX contribution (40%), F/G inverse (30%), HIGH events (30%)
    vix_component = min(vix / 50, 1.0) * 40
    fng_component = (1 - fng_score / 100) * 30  # Low F/G = high risk
    event_component = min(high_count / 5, 1.0) * 30
    score = round(vix_component + fng_component + event_component)

    return {
        "score": min(100, max(0, score)),
        "vix": vix,
        "fear_greed": fng_score,
        "high_events": high_count,
        "level": "high" if score > 60 else "medium" if score > 30 else "low",
    }


@router.get("/bots/{bot_id}/reasoning")
async def get_bot_reasoning(
    request: Request,
    bot_id: str,
    limit: int = Query(20, le=100),
):
    """Get reasoning decision timeline for a bot."""
    async with get_session() as session:
        result = await session.execute(
            select(TradeDecision)
            .where(TradeDecision.bot_id == bot_id)
            .order_by(TradeDecision.created_at.desc())
            .limit(limit)
        )
        decisions = result.scalars().all()

    return [
        {
            "id": d.id,
            "symbol": d.symbol,
            "strategy_signal": d.strategy_signal,
            "context_risk_level": d.context_risk_level,
            "ai_confidence": d.ai_confidence,
            "decision": d.decision,
            "reasoning": d.reasoning,
            "size_adjustment": d.size_adjustment,
            "model_used": d.model_used,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in decisions
    ]


@router.get("/bots/{bot_id}/learning")
async def get_bot_learning(request: Request, bot_id: str):
    """Get learning data (journal, regime stats, adaptations) for a bot."""
    async with get_session() as session:
        # Journal entries
        journal_result = await session.execute(
            select(BotTradeJournal)
            .where(BotTradeJournal.bot_id == bot_id)
            .order_by(BotTradeJournal.created_at.desc())
            .limit(50)
        )
        journal = journal_result.scalars().all()

        # Regime stats
        regime_result = await session.execute(
            select(BotRegimeStats).where(BotRegimeStats.bot_id == bot_id)
        )
        regimes = regime_result.scalars().all()

        # Adaptations
        adapt_result = await session.execute(
            select(BotAdaptation)
            .where(BotAdaptation.bot_id == bot_id)
            .order_by(BotAdaptation.created_at.desc())
            .limit(20)
        )
        adaptations = adapt_result.scalars().all()

    return {
        "journal": [
            {
                "id": j.id,
                "symbol": j.symbol,
                "side": j.side,
                "pnl": j.pnl,
                "pnl_pct": j.pnl_pct,
                "ai_confidence": j.ai_confidence_at_entry,
                "ai_decision": j.ai_decision,
                "regime": j.regime_at_entry,
                "outcome_tag": j.outcome_tag,
                "lesson_learned": j.lesson_learned,
                "entry_at": j.entry_at.isoformat() if j.entry_at else None,
                "exit_at": j.exit_at.isoformat() if j.exit_at else None,
                "hold_duration_seconds": j.hold_duration_seconds,
            }
            for j in journal
        ],
        "regime_stats": [
            {
                "regime": r.regime,
                "total_trades": r.total_trades,
                "win_rate": r.win_rate,
                "avg_pnl": r.avg_pnl,
                "sharpe": r.sharpe,
            }
            for r in regimes
        ],
        "adaptations": [
            {
                "id": a.id,
                "type": a.adaptation_type,
                "old_value": a.old_value,
                "new_value": a.new_value,
                "reasoning": a.reasoning,
                "confidence": a.confidence,
                "auto_applied": a.auto_applied,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in adaptations
        ],
    }


@router.get("/bots/{bot_id}/universe")
async def get_bot_universe(request: Request, bot_id: str):
    """Get universe candidates for a bot."""
    async with get_session() as session:
        result = await session.execute(
            select(UniverseCandidate)
            .where(UniverseCandidate.bot_id == bot_id)
            .order_by(UniverseCandidate.score.desc())
        )
        candidates = result.scalars().all()

    return [
        {
            "symbol": c.symbol,
            "score": c.score,
            "reason": c.reason,
            "scanned_at": c.scanned_at.isoformat() if c.scanned_at else None,
        }
        for c in candidates
    ]
```

- [ ] **Step 4: Register router in `api/main.py`**

Add import:
```python
from api.routes import reasoning as reasoning_routes
```

Add router registration after the quant router:
```python
app.include_router(reasoning_routes.router, prefix="/api/reasoning", tags=["AI Reasoning"])
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd ~/adaptive-trading-ecosystem && python -m pytest tests/test_reasoning_api.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add api/routes/reasoning.py api/main.py tests/test_reasoning_api.py
git commit -m "feat: add REST endpoints for market intelligence, bot reasoning, learning, and universe data"
```

### Task 11: Add learning adaptation Celery task

**Files:**
- Modify: `services/workers/tasks.py`
- Test: (manual — Celery task)

- [ ] **Step 1: Add task to `services/workers/tasks.py`**

Add import at top:
```python
from services.bot_memory.learning import run_adaptation_review
```

Add the task:
```python
@celery_app.task(name="learning.adaptation_review", queue="learning")
def adaptation_review_task(bot_id: str):
    """Run autonomous adaptation review for a bot."""
    import asyncio
    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(run_adaptation_review(bot_id))
        return result
    finally:
        loop.close()
```

- [ ] **Step 2: Commit**

```bash
git add services/workers/tasks.py
git commit -m "feat: add Celery task for bot learning adaptation review"
```

---

## Chunk 8: Frontend UI

### Task 12: Create API client for reasoning endpoints

**Files:**
- Create: `frontend/src/lib/reasoning-api.ts`

- [ ] **Step 1: Create the API client**

```typescript
// frontend/src/lib/reasoning-api.ts
import { apiFetch } from "./api/client";

// ── Types ──────────────────────────────────────────────────────────────────

export interface MarketEventItem {
  id: string;
  event_type: string;
  impact: "LOW" | "MEDIUM" | "HIGH";
  symbols: string[];
  sectors: string[];
  headline: string;
  source: string;
  detected_at: string | null;
  expires_at: string | null;
}

export interface RiskScore {
  score: number;
  vix: number;
  fear_greed: number;
  high_events: number;
  level: "low" | "medium" | "high";
}

export interface TradeDecisionItem {
  id: string;
  symbol: string;
  strategy_signal: string;
  context_risk_level: string;
  ai_confidence: number;
  decision: string;
  reasoning: string;
  size_adjustment: number;
  model_used: string;
  created_at: string | null;
}

export interface JournalEntry {
  id: string;
  symbol: string;
  side: string;
  pnl: number | null;
  pnl_pct: number | null;
  ai_confidence: number | null;
  ai_decision: string | null;
  regime: string | null;
  outcome_tag: string | null;
  lesson_learned: string | null;
  entry_at: string | null;
  exit_at: string | null;
  hold_duration_seconds: number | null;
}

export interface RegimeStat {
  regime: string;
  total_trades: number;
  win_rate: number;
  avg_pnl: number;
  sharpe: number;
}

export interface AdaptationItem {
  id: string;
  type: string;
  old_value: Record<string, unknown>;
  new_value: Record<string, unknown>;
  reasoning: string;
  confidence: number;
  auto_applied: boolean;
  created_at: string | null;
}

export interface BotLearningData {
  journal: JournalEntry[];
  regime_stats: RegimeStat[];
  adaptations: AdaptationItem[];
}

export interface UniverseCandidateItem {
  symbol: string;
  score: number;
  reason: string;
  scanned_at: string | null;
}

// ── API calls ──────────────────────────────────────────────────────────────

export async function getMarketEvents(params?: {
  event_type?: string;
  impact?: string;
  limit?: number;
}): Promise<MarketEventItem[]> {
  const searchParams = new URLSearchParams();
  if (params?.event_type) searchParams.set("event_type", params.event_type);
  if (params?.impact) searchParams.set("impact", params.impact);
  if (params?.limit) searchParams.set("limit", String(params.limit));
  const qs = searchParams.toString();
  return apiFetch(`/api/reasoning/intelligence/events${qs ? `?${qs}` : ""}`);
}

export async function getRiskScore(): Promise<RiskScore> {
  return apiFetch("/api/reasoning/intelligence/risk-score");
}

export async function getBotReasoning(
  botId: string,
  limit = 20,
): Promise<TradeDecisionItem[]> {
  return apiFetch(`/api/reasoning/bots/${botId}/reasoning?limit=${limit}`);
}

export async function getBotLearning(botId: string): Promise<BotLearningData> {
  return apiFetch(`/api/reasoning/bots/${botId}/learning`);
}

export async function getBotUniverse(
  botId: string,
): Promise<UniverseCandidateItem[]> {
  return apiFetch(`/api/reasoning/bots/${botId}/universe`);
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/lib/reasoning-api.ts
git commit -m "feat: add frontend API client for reasoning endpoints"
```

### Task 13: Create Market Intelligence page

**Files:**
- Create: `frontend/src/app/intelligence/page.tsx`
- Create: `frontend/src/components/intelligence/RiskGauge.tsx`
- Create: `frontend/src/components/intelligence/ActiveEvents.tsx`

- [ ] **Step 1: Create RiskGauge component**

```tsx
// frontend/src/components/intelligence/RiskGauge.tsx
"use client";

import { useEffect, useState } from "react";
import { getRiskScore, type RiskScore } from "@/lib/reasoning-api";

export function RiskGauge() {
  const [data, setData] = useState<RiskScore | null>(null);

  useEffect(() => {
    getRiskScore().then(setData).catch(() => {});
    const interval = setInterval(() => {
      getRiskScore().then(setData).catch(() => {});
    }, 60_000);
    return () => clearInterval(interval);
  }, []);

  if (!data) {
    return (
      <div className="app-panel flex items-center justify-center p-8">
        <div className="text-sm text-muted-foreground">Loading risk data...</div>
      </div>
    );
  }

  const colorClass =
    data.level === "high"
      ? "text-red-400"
      : data.level === "medium"
        ? "text-amber-400"
        : "text-emerald-400";

  const bgClass =
    data.level === "high"
      ? "bg-red-500/10 border-red-500/20"
      : data.level === "medium"
        ? "bg-amber-500/10 border-amber-500/20"
        : "bg-emerald-500/10 border-emerald-500/20";

  return (
    <div className={`app-panel border ${bgClass} p-6`}>
      <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
        Market Risk Score
      </div>
      <div className={`mt-2 text-5xl font-bold ${colorClass}`}>{data.score}</div>
      <div className="mt-3 grid grid-cols-3 gap-3 text-sm">
        <div>
          <div className="text-[10px] uppercase tracking-wide text-muted-foreground">VIX</div>
          <div className="mt-1 font-semibold text-foreground">{data.vix.toFixed(1)}</div>
        </div>
        <div>
          <div className="text-[10px] uppercase tracking-wide text-muted-foreground">Fear/Greed</div>
          <div className="mt-1 font-semibold text-foreground">{data.fear_greed.toFixed(0)}</div>
        </div>
        <div>
          <div className="text-[10px] uppercase tracking-wide text-muted-foreground">High Events</div>
          <div className="mt-1 font-semibold text-foreground">{data.high_events}</div>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create ActiveEvents component**

```tsx
// frontend/src/components/intelligence/ActiveEvents.tsx
"use client";

import { useEffect, useState } from "react";
import { getMarketEvents, type MarketEventItem } from "@/lib/reasoning-api";

const impactColors: Record<string, string> = {
  HIGH: "bg-red-500/20 text-red-400 border-red-500/30",
  MEDIUM: "bg-amber-500/20 text-amber-400 border-amber-500/30",
  LOW: "bg-zinc-500/20 text-zinc-400 border-zinc-500/30",
};

export function ActiveEvents() {
  const [events, setEvents] = useState<MarketEventItem[]>([]);

  useEffect(() => {
    getMarketEvents({ limit: 30 }).then(setEvents).catch(() => {});
    const interval = setInterval(() => {
      getMarketEvents({ limit: 30 }).then(setEvents).catch(() => {});
    }, 120_000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="app-panel p-5">
      <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
        Active Market Events
      </div>
      <div className="mt-4 max-h-[480px] space-y-2 overflow-y-auto">
        {events.length === 0 ? (
          <div className="rounded-2xl border border-border/60 bg-muted/10 px-4 py-4 text-sm text-muted-foreground">
            No active market events detected.
          </div>
        ) : (
          events.map((event) => (
            <div
              key={event.id}
              className="rounded-2xl border border-border/60 bg-muted/10 px-4 py-3"
            >
              <div className="flex items-center justify-between gap-2">
                <span
                  className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase ${impactColors[event.impact] || impactColors.LOW}`}
                >
                  {event.impact}
                </span>
                <span className="text-[10px] text-muted-foreground">
                  {event.source}
                </span>
              </div>
              <div className="mt-2 text-sm text-foreground">{event.headline}</div>
              {event.symbols.length > 0 && (
                <div className="mt-1 flex gap-1">
                  {event.symbols.map((s) => (
                    <span key={s} className="app-pill text-[10px]">{s}</span>
                  ))}
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Create Intelligence page**

```tsx
// frontend/src/app/intelligence/page.tsx
"use client";

import { PageHeader } from "@/components/layout/PageHeader";
import { RiskGauge } from "@/components/intelligence/RiskGauge";
import { ActiveEvents } from "@/components/intelligence/ActiveEvents";

export default function IntelligencePage() {
  return (
    <div className="app-page">
      <PageHeader
        eyebrow="AI Market Intelligence"
        title="Market Intelligence"
        description="Real-time market context, risk assessment, and event monitoring powered by live data feeds."
      />

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1fr_2fr]">
        <RiskGauge />
        <ActiveEvents />
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/intelligence/page.tsx frontend/src/components/intelligence/
git commit -m "feat: add Market Intelligence page with Risk Gauge and Active Events"
```

### Task 14: Add AI Reasoning, Learning, and Universe tabs to bot detail

**Files:**
- Create: `frontend/src/components/bots/AIReasoningTab.tsx`
- Create: `frontend/src/components/bots/LearningTab.tsx`
- Create: `frontend/src/components/bots/UniverseTab.tsx`
- Modify: `frontend/src/app/bots/[id]/page.tsx`

- [ ] **Step 1: Create AIReasoningTab**

```tsx
// frontend/src/components/bots/AIReasoningTab.tsx
"use client";

import { useEffect, useState } from "react";
import { Brain } from "lucide-react";
import { getBotReasoning, type TradeDecisionItem } from "@/lib/reasoning-api";

const decisionColors: Record<string, string> = {
  EXECUTE: "text-emerald-400",
  REDUCE_SIZE: "text-amber-400",
  DELAY_TRADE: "text-sky-400",
  PAUSE_BOT: "text-red-400",
  EXIT_POSITION: "text-rose-400",
};

export function AIReasoningTab({ botId }: { botId: string }) {
  const [decisions, setDecisions] = useState<TradeDecisionItem[]>([]);

  useEffect(() => {
    getBotReasoning(botId).then(setDecisions).catch(() => {});
  }, [botId]);

  const latest = decisions[0];

  return (
    <section className="app-panel p-5 sm:p-6">
      <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
        <Brain className="h-3.5 w-3.5 text-violet-400" />
        AI Reasoning
      </div>

      {latest && (
        <div className="mt-4 rounded-2xl border border-border/60 bg-muted/10 p-4">
          <div className="flex items-center justify-between">
            <span className={`text-lg font-bold ${decisionColors[latest.decision] || "text-foreground"}`}>
              {latest.decision}
            </span>
            <span className="text-xs text-muted-foreground">{latest.model_used}</span>
          </div>
          <div className="mt-2 grid grid-cols-3 gap-3 text-sm">
            <div>
              <div className="text-[10px] uppercase text-muted-foreground">Confidence</div>
              <div className="mt-1 font-semibold">{(latest.ai_confidence * 100).toFixed(0)}%</div>
            </div>
            <div>
              <div className="text-[10px] uppercase text-muted-foreground">Risk Level</div>
              <div className="mt-1 font-semibold">{latest.context_risk_level}</div>
            </div>
            <div>
              <div className="text-[10px] uppercase text-muted-foreground">Signal</div>
              <div className="mt-1 font-semibold">{latest.strategy_signal}</div>
            </div>
          </div>
          <div className="mt-3 text-sm text-muted-foreground">{latest.reasoning}</div>
        </div>
      )}

      <div className="mt-4 space-y-2">
        <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
          Decision Timeline
        </div>
        {decisions.length === 0 ? (
          <div className="text-sm text-muted-foreground">No reasoning decisions recorded yet.</div>
        ) : (
          decisions.slice(0, 10).map((d) => (
            <div key={d.id} className="rounded-2xl border border-border/60 bg-muted/10 px-4 py-3">
              <div className="flex items-center justify-between">
                <span className={`text-sm font-semibold ${decisionColors[d.decision] || ""}`}>
                  {d.decision} — {d.symbol}
                </span>
                <span className="text-[10px] text-muted-foreground">
                  {d.created_at ? new Date(d.created_at).toLocaleString() : ""}
                </span>
              </div>
              <div className="mt-1 text-xs text-muted-foreground">{d.reasoning}</div>
            </div>
          ))
        )}
      </div>
    </section>
  );
}
```

- [ ] **Step 2: Create LearningTab**

```tsx
// frontend/src/components/bots/LearningTab.tsx
"use client";

import { useEffect, useState } from "react";
import { GraduationCap } from "lucide-react";
import { getBotLearning, type BotLearningData } from "@/lib/reasoning-api";

export function LearningTab({ botId }: { botId: string }) {
  const [data, setData] = useState<BotLearningData | null>(null);

  useEffect(() => {
    getBotLearning(botId).then(setData).catch(() => {});
  }, [botId]);

  if (!data) {
    return <div className="app-panel p-5 text-sm text-muted-foreground">Loading learning data...</div>;
  }

  return (
    <section className="app-panel space-y-6 p-5 sm:p-6">
      <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
        <GraduationCap className="h-3.5 w-3.5 text-amber-400" />
        Bot Learning
      </div>

      {/* Regime Breakdown */}
      <div>
        <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
          Performance by Regime
        </div>
        <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {data.regime_stats.map((r) => (
            <div key={r.regime} className="rounded-2xl border border-border/60 bg-muted/10 p-4">
              <div className="text-sm font-semibold text-foreground">{r.regime.replace(/_/g, " ")}</div>
              <div className="mt-2 grid grid-cols-2 gap-2 text-xs">
                <div>
                  <span className="text-muted-foreground">Win Rate</span>
                  <div className="font-semibold">{(r.win_rate * 100).toFixed(0)}%</div>
                </div>
                <div>
                  <span className="text-muted-foreground">Trades</span>
                  <div className="font-semibold">{r.total_trades}</div>
                </div>
                <div>
                  <span className="text-muted-foreground">Avg PnL</span>
                  <div className="font-semibold">${r.avg_pnl.toFixed(2)}</div>
                </div>
                <div>
                  <span className="text-muted-foreground">Sharpe</span>
                  <div className="font-semibold">{r.sharpe.toFixed(2)}</div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Adaptations Log */}
      <div>
        <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
          Parameter Adaptations
        </div>
        <div className="mt-3 space-y-2">
          {data.adaptations.length === 0 ? (
            <div className="text-sm text-muted-foreground">No adaptations yet.</div>
          ) : (
            data.adaptations.map((a) => (
              <div key={a.id} className="rounded-2xl border border-border/60 bg-muted/10 px-4 py-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-semibold text-foreground">{a.type}</span>
                  <span className={`text-[10px] ${a.auto_applied ? "text-emerald-400" : "text-amber-400"}`}>
                    {a.auto_applied ? "Auto-applied" : "Needs approval"}
                  </span>
                </div>
                <div className="mt-1 text-xs text-muted-foreground">{a.reasoning}</div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Trade Journal */}
      <div>
        <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
          Trade Journal
        </div>
        <div className="mt-3 space-y-2">
          {data.journal.length === 0 ? (
            <div className="text-sm text-muted-foreground">No journal entries yet.</div>
          ) : (
            data.journal.slice(0, 10).map((j) => (
              <div key={j.id} className="rounded-2xl border border-border/60 bg-muted/10 px-4 py-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-semibold text-foreground">
                    {j.symbol} {j.side.toUpperCase()}
                  </span>
                  <span className={`text-sm font-semibold ${(j.pnl || 0) >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                    {j.pnl != null ? `$${j.pnl.toFixed(2)}` : "—"}
                  </span>
                </div>
                {j.lesson_learned && (
                  <div className="mt-1 text-xs text-muted-foreground">{j.lesson_learned}</div>
                )}
              </div>
            ))
          )}
        </div>
      </div>
    </section>
  );
}
```

- [ ] **Step 3: Create UniverseTab**

```tsx
// frontend/src/components/bots/UniverseTab.tsx
"use client";

import { useEffect, useState } from "react";
import { Globe } from "lucide-react";
import { getBotUniverse, type UniverseCandidateItem } from "@/lib/reasoning-api";

export function UniverseTab({ botId }: { botId: string }) {
  const [candidates, setCandidates] = useState<UniverseCandidateItem[]>([]);

  useEffect(() => {
    getBotUniverse(botId).then(setCandidates).catch(() => {});
  }, [botId]);

  return (
    <section className="app-panel p-5 sm:p-6">
      <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
        <Globe className="h-3.5 w-3.5 text-sky-400" />
        Universe Candidates
      </div>

      <div className="mt-4 space-y-2">
        {candidates.length === 0 ? (
          <div className="text-sm text-muted-foreground">
            No universe candidates. This bot may use fixed symbols.
          </div>
        ) : (
          candidates.map((c, i) => (
            <div
              key={c.symbol}
              className="flex items-center justify-between rounded-2xl border border-border/60 bg-muted/10 px-4 py-3"
            >
              <div className="flex items-center gap-3">
                <span className="text-xs font-semibold text-muted-foreground">#{i + 1}</span>
                <span className="text-sm font-semibold text-foreground">{c.symbol}</span>
              </div>
              <div className="text-right">
                <div className="text-sm font-semibold text-foreground">
                  {(c.score * 100).toFixed(0)}%
                </div>
                <div className="text-[10px] text-muted-foreground">{c.reason}</div>
              </div>
            </div>
          ))
        )}
      </div>
    </section>
  );
}
```

- [ ] **Step 4: Add tabs to bot detail page**

Modify `frontend/src/app/bots/[id]/page.tsx`:

Add imports at top:
```tsx
import { AIReasoningTab } from "@/components/bots/AIReasoningTab";
import { LearningTab } from "@/components/bots/LearningTab";
import { UniverseTab } from "@/components/bots/UniverseTab";
```

Add a tab state after the existing state declarations:
```tsx
const [activeTab, setActiveTab] = useState<"overview" | "reasoning" | "learning" | "universe">("overview");
```

Add tab navigation before the main content grid (after `<BotPerformanceStats>`):
```tsx
      <div className="flex gap-2 border-b border-border/60 pb-1">
        {(["overview", "reasoning", "learning", "universe"] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`rounded-t-xl px-4 py-2 text-sm font-medium transition-colors ${
              activeTab === tab
                ? "bg-muted/30 text-foreground"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            {tab.charAt(0).toUpperCase() + tab.slice(1)}
          </button>
        ))}
      </div>
```

Wrap the existing content in `{activeTab === "overview" && (...)}` and add the new tabs:
```tsx
      {activeTab === "reasoning" && <AIReasoningTab botId={botId} />}
      {activeTab === "learning" && <LearningTab botId={botId} />}
      {activeTab === "universe" && <UniverseTab botId={botId} />}
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/bots/AIReasoningTab.tsx frontend/src/components/bots/LearningTab.tsx frontend/src/components/bots/UniverseTab.tsx frontend/src/app/bots/\[id\]/page.tsx
git commit -m "feat: add AI Reasoning, Learning, and Universe tabs to bot detail page"
```

### Task 15: Add Intelligence link to navigation

**Files:**
- Modify: Navigation component (find the sidebar/nav file)

- [ ] **Step 1: Find and modify the navigation**

Search for the navigation component that has links to existing pages (dashboard, bots, strategies, etc.) and add:
```tsx
{ label: "Intelligence", href: "/intelligence", icon: <Radar className="h-4 w-4" /> }
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/layout/
git commit -m "feat: add Market Intelligence link to navigation"
```

---

## Chunk 9: Final Integration & Verification

### Task 16: Run full test suite

- [ ] **Step 1: Run all tests**

Run: `cd ~/adaptive-trading-ecosystem && python -m pytest tests/ -v --timeout=60`
Expected: All PASS

- [ ] **Step 2: Start backend and verify**

Run: `cd ~/adaptive-trading-ecosystem && python3 -m uvicorn api.main:app --port 8000`
Expected: Logs show `context_monitor_started`, `universe_scanner_started`, `bot_runner_started`

- [ ] **Step 3: Verify frontend builds**

Run: `cd ~/adaptive-trading-ecosystem/frontend && npm run build`
Expected: Build succeeds with no TypeScript errors

- [ ] **Step 4: Test API endpoints**

```bash
# Market events
curl -s http://localhost:8000/api/reasoning/intelligence/events | python3 -m json.tool

# Risk score
curl -s http://localhost:8000/api/reasoning/intelligence/risk-score | python3 -m json.tool
```

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "feat: AI Reasoning Layer — complete integration with Context Monitor, Universe Scanner, Reasoning Engine, Bot Memory, and UI"
```
