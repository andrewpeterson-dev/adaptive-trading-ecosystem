"""Prompt templates for AI reasoning decisions."""
from __future__ import annotations

TRADE_DECISION_SYSTEM = """You are an AI trading analyst evaluating whether a bot should execute a trade signal.

You receive:
- The bot's strategy and its current signal
- Active market events and conditions
- The bot's historical performance in similar conditions
- Current portfolio state

Your job: Decide whether to EXECUTE, REDUCE_SIZE, DELAY_TRADE, PAUSE_BOT, or EXIT_POSITION.

Return JSON:
{
  "decision": "EXECUTE" | "REDUCE_SIZE" | "DELAY_TRADE" | "PAUSE_BOT" | "EXIT_POSITION",
  "confidence": 0.0-1.0,
  "reasoning": "2-3 sentence explanation",
  "size_adjustment": 0.0-1.0,
  "delay_seconds": 0
}

Be conservative. When uncertain, reduce size rather than block entirely."""

def build_trade_decision_prompt(
    *,
    bot_name: str,
    symbol: str,
    signal: str,
    strategy_config: dict,
    active_events: list[dict],
    regime_stats: dict | None = None,
    recent_trades: list[dict] | None = None,
    vix: float | None = None,
    ai_thinking: str | None = None,
) -> str:
    parts = [f"## Trade Signal\nBot: {bot_name}\nSymbol: {symbol}\nSignal: {signal}"]

    if ai_thinking:
        parts.append(f"## Strategy Context\n{ai_thinking}")

    if vix is not None:
        parts.append(f"## Market Conditions\nVIX: {vix:.1f}")

    if active_events:
        event_lines = []
        for e in active_events[:10]:
            event_lines.append(f"- [{e.get('impact', '?')}] {e.get('headline', 'unknown')} (source: {e.get('source', '?')})")
        parts.append("## Active Market Events\n" + "\n".join(event_lines))

    if regime_stats:
        parts.append(f"## Regime Performance\n{regime_stats}")

    if recent_trades:
        trade_lines = []
        for t in recent_trades[:5]:
            trade_lines.append(f"- {t.get('symbol')} {t.get('side')} PnL: {t.get('pnl_pct', 0):.1f}%")
        parts.append("## Recent Trades\n" + "\n".join(trade_lines))

    return "\n\n".join(parts)
