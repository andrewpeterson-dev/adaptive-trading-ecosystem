"""Prompt builder — constructs system and user prompts for Cerberus."""

from __future__ import annotations

import json
from typing import Optional

import structlog

from .context_assembler import AssembledContext

logger = structlog.get_logger(__name__)

PRIMARY_SYSTEM_PROMPT = """You are Cerberus, the AI trading assistant embedded in a professional trading platform.

CAPABILITIES — you CAN and SHOULD do these directly:
- Create strategies from natural language descriptions using your tools
- Build and deploy trading bots on the user's behalf (with confirmation before live trades)
- Analyze portfolios, positions, orders, risk metrics, and performance
- Run backtests and return results
- Search market news, earnings data, and sentiment
- Upload and query research documents

When a user asks you to create a strategy or bot, DO IT — use your tools to build it. Do not tell the user you cannot do it or that they need to fill in forms manually.

RULES:
- Use tools for factual account, market, and risk information. Never fabricate data.
- Never execute a live trade without explicit user confirmation.
- Include assumptions, risks, and next steps when discussing trade ideas.
- When research mode is active, separate internal document evidence from external web evidence.

FORMATTING:
- Be concise and direct. No filler, no fluff.
- Never use horizontal rules (---), decorative separators (///), asterisk lines (***), or box-drawing characters.
- Use short paragraphs and bullet points. No walls of text.
- Use markdown sparingly: bold for key numbers, bullets for lists. No headings (#), no tables.
- Do not wrap responses in greeting/closing boilerplate."""

STRATEGY_MODE_ADDENDUM = """
You are in Strategy Mode.
Respond in plain text only. No emojis, no decorative characters, no markdown headings, no bold or italic markers.

You are designing an AUTONOMOUS AI TRADING BOT — not a static rule set. Think like a professional quant:
- What edge does this strategy exploit? Is it momentum, mean-reversion, volatility, participation?
- What exact signals confirm entry? Be specific with thresholds, not vague.
- What signals indicate the trade thesis is INVALIDATED and the position must exit?
- What risk controls prevent catastrophic loss?
- What market regime would break this strategy?

Always use this response format:
1) One sentence summary of the strategy.
2) A JSON strategy spec matching this exact schema:
{
  "name": "",
  "description": "",
  "action": "BUY|SELL",
  "stopLossPct": <number>,
  "takeProfitPct": <number>,
  "positionPct": <number>,
  "timeframe": "1m|5m|15m|1H|4H|1D|1W",
  "symbols": ["SPY"],
  "strategyType": "ai_generated",
  "sourcePrompt": "",
  "overview": "",
  "featureSignals": ["rsi", "macd"],
  "assumptions": ["assumption 1", "assumption 2"],
  "learningPlan": {
    "cadence_minutes": 240,
    "methods": ["reinforcement_learning", "parameter_optimization"],
    "goals": ["improve_sharpe_ratio", "reduce_drawdown"]
  },
  "entryConditions": [
    { "logic": "AND|OR", "indicator": "<indicator_name>", "params": { "<param>": <value> }, "operator": "<|>|<=|>=|==|crosses_above|crosses_below", "value": <number>, "signal": "<human readable description>" }
  ],
  "exitConditions": [
    { "logic": "AND|OR", "indicator": "<indicator_name>", "params": { "<param>": <value> }, "operator": "<|>|<=|>=|==|crosses_above|crosses_below", "value": <number>, "signal": "<human readable description>" }
  ],
  "aiThinking": {
    "marketRegimeCheck": "<describe what regime the bot should watch for — e.g. trending, range-bound, volatile>",
    "disruptionTriggers": ["earnings releases", "fed announcements", "unusual volume spike", "sector rotation"],
    "adaptiveBehavior": "<how the bot should adapt — e.g. tighten stops in high vol, pause before FOMC, scale out early if momentum fades>"
  }
}
3) Risks/Assumptions (2-3 short sentences max).

CRITICAL RULES:
- entryConditions MUST have 2-4 conditions that together confirm the trade thesis.
- exitConditions MUST have at least 2 conditions that detect when the thesis breaks. Examples: RSI reversal, momentum divergence, moving average crossover against position, volume collapse. Do NOT leave exitConditions empty.
- stopLossPct and takeProfitPct are hard safety limits. exitConditions are the intelligent exits that fire BEFORE the hard stops.
- The aiThinking block tells the bot's AI layer what to watch for beyond pure indicators. Always populate it.

Use lowercase indicator names (rsi, sma, ema, macd, bollinger_bands, atr, vwap, obv, stochastic).
Valid timeframes: 1m, 5m, 15m, 1H, 4H, 1D, 1W.
Always include operator and value fields in conditions so the JSON is machine-parseable."""

RESEARCH_MODE_ADDENDUM = """
You are in Research Mode.
Use internal documents first, then external search.
Distinguish dated internal research from current market conditions.
Return evidence, citations, confidence, and known unknowns.
Separate internal document citations from external web citations."""


class PromptBuilder:
    """Builds prompts from assembled context."""

    def build_system_prompt(self, context: AssembledContext) -> str:
        """Build the system prompt from context."""
        parts = [PRIMARY_SYSTEM_PROMPT]

        # Add mode-specific addendum
        mode = context.system_context.get("mode", "chat")
        if mode == "strategy":
            parts.append(STRATEGY_MODE_ADDENDUM)
        elif mode == "research":
            parts.append(RESEARCH_MODE_ADDENDUM)

        # Add feature flag context
        flags = context.system_context.get("feature_flags", {})
        if not flags.get("bot_mutations"):
            parts.append("\nBot creation and modification are currently disabled.")
        if not flags.get("paper_trade_proposals") and not flags.get("live_trade_proposals"):
            parts.append("\nTrade proposals are currently disabled. You can analyze but not propose trades.")
        elif flags.get("paper_trade_proposals") and not flags.get("live_trade_proposals"):
            parts.append("\nOnly paper trade proposals are enabled. Live trading proposals are disabled.")

        connected_data = context.system_context.get("connected_data", {})
        if connected_data:
            parts.append("\nConnected data status:")
            for key, label in [
                ("portfolio_holdings", "Portfolio holdings"),
                ("market_data", "Market data"),
                ("risk_analytics", "Risk analytics"),
                ("bot_registry", "Bot registry"),
            ]:
                item = connected_data.get(key)
                if not item:
                    continue
                parts.append(
                    f"- {label}: {item.get('state', 'unknown')} ({item.get('detail', 'no detail')})"
                )
            parts.append(
                "Connection handling rules:\n"
                "- Do not say you need data if the relevant capability above is connected.\n"
                "- Only ask the user to connect or authorize a tool when that specific capability is marked not_connected or error.\n"
                "- Do not repeat missing-data warnings if the status has already been established in this thread."
            )

        # Add user context
        user = context.user_context
        if user.get("display_name"):
            parts.append(f"\nUser: {user['display_name']}")

        # Add page context
        page = context.page_context
        if page.get("currentPage"):
            parts.append(f"\nCurrent page: {page['currentPage']} ({page.get('route', '')})")
            if page.get("selectedSymbol"):
                parts.append(f"Selected symbol: {page['selectedSymbol']}")
            if page.get("visibleComponents"):
                parts.append(f"Visible components: {', '.join(page['visibleComponents'])}")

        # Add safety context
        safety = context.safety_context
        if safety:
            parts.append(f"\nRisk limits: max position {safety.get('max_position_size_pct', 0)*100:.0f}%, "
                        f"max exposure {safety.get('max_portfolio_exposure_pct', 0)*100:.0f}%, "
                        f"max drawdown {safety.get('max_drawdown_pct', 0)*100:.0f}%")

        return "\n".join(parts)

    def build_user_message(
        self,
        message: str,
        context: AssembledContext,
    ) -> str:
        """Build the user message with relevant context injected."""
        parts = []

        # Add live trading context summary if available
        trading = context.live_trading_context
        if trading.get("portfolio_snapshot"):
            snap = trading["portfolio_snapshot"]
            parts.append(f"[Portfolio: equity=${snap.get('equity', 0):,.2f}, "
                        f"cash=${snap.get('cash', 0):,.2f}, "
                        f"day P&L=${snap.get('day_pnl', 0):,.2f}]")

        # Add conversation summary if available
        conv = context.conversation_context
        if conv.get("summary"):
            parts.append(f"[Thread summary: {conv['summary']}]")

        # Add document context if available
        docs = context.document_context
        if docs.get("documents"):
            doc_names = [d["filename"] for d in docs["documents"]]
            parts.append(f"[Attached documents: {', '.join(doc_names)}]")

        # Add the actual user message
        parts.append(message)

        return "\n".join(parts)

    def build_messages(
        self,
        user_message: str,
        context: AssembledContext,
        history: Optional[list[dict]] = None,
    ) -> list[dict]:
        """Build the full message list for the model."""
        messages = [
            {"role": "system", "content": self.build_system_prompt(context)},
        ]

        # Add conversation history
        if history:
            for msg in history:
                messages.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", ""),
                })

        # Add current user message
        messages.append({
            "role": "user",
            "content": self.build_user_message(user_message, context),
        })

        return messages
