"""
AI-powered entry evaluator for bot execution engine.

Instead of rigid indicator threshold checks (AND logic), this module sends
the full market picture to an LLM and asks it to make a holistic trade
decision — using the strategy description as guidance, not as hard rules.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

import structlog

from config.settings import get_settings
from services.ai_core.model_router import ModelRouter
from services.ai_core.providers.base import ProviderMessage

logger = structlog.get_logger(__name__)

_router: ModelRouter | None = None


def _get_router() -> ModelRouter:
    global _router
    if _router is None:
        _router = ModelRouter()
    return _router


@dataclass
class AIEntrySignal:
    symbol: str
    action: str  # "enter" or "hold"
    confidence: int  # 0-100
    reasoning: str


def _get_system_prompt(mode: str = "paper") -> str:
    """Return the system prompt tailored for the bot's trading mode.

    Parameters
    ----------
    mode : str
        "paper" or "live". Defaults to "paper".
    """
    if mode == "live":
        mode_label = "live trading bot"
        selectivity_line = (
            "3. Be HIGHLY selective — only enter with strong conviction. "
            "This is LIVE capital at risk. Prefer fewer, higher-quality setups over volume."
        )
        risk_line = (
            "11. This is LIVE MODE — real money is on the line. Err on the side of caution. "
            "If in doubt, hold. A missed trade is better than a losing one."
        )
    else:
        mode_label = "paper trading bot"
        selectivity_line = (
            "3. Be selective but not impossible — 1-3 entries per evaluation is ideal for paper trading."
        )
        risk_line = ""

    risk_section = f"\n{risk_line}" if risk_line else ""

    return f"""\
You are an AI trading analyst making entry decisions for a {mode_label}.
You receive the bot's strategy description, current indicator values, and price
data for each symbol in its universe.

Your job: decide which symbols (if any) to ENTER a position on RIGHT NOW.

IMPORTANT RULES:
1. The strategy description is GUIDANCE — use your judgment, not rigid thresholds.
2. Consider the FULL picture: trend, momentum, volatility, and price levels.
{selectivity_line}
4. For BUY strategies: look for upward momentum, trend support, favorable risk/reward.
5. For SELL strategies: look for weakness, breakdowns, bearish divergences.
6. Confidence >= 60 means you'd take the trade. Below 60 means hold.
7. Think about the risk/reward relative to the stop loss and take profit levels.
8. If a symbol is near a key support/resistance, that can be a catalyst.
9. Volume and ATR indicate conviction and opportunity size.
10. Don't require ALL indicators to be perfect — real trading is about edge, not perfection.{risk_section}

Return ONLY valid JSON (no markdown, no explanation outside JSON):
{{
  "decisions": [
    {{"symbol": "SPY", "action": "enter", "confidence": 72, "reasoning": "RSI recovering from oversold with bullish MACD crossover forming"}},
    {{"symbol": "QQQ", "action": "hold", "confidence": 40, "reasoning": "Momentum still deteriorating, wait for stabilization"}}
  ]
}}

Include ALL symbols in your response. "enter" means open a new position. "hold" means wait."""


def _build_evaluation_prompt(
    *,
    strategy_name: str,
    strategy_description: str,
    action: str,
    stop_loss_pct: float,
    take_profit_pct: float,
    position_size_pct: float,
    timeframe: str,
    symbol_data: list[dict],
    open_positions: list[str],
) -> str:
    """Build the user prompt with all market data for the LLM."""
    lines = [
        f"## Strategy: {strategy_name}",
        f"Description: {strategy_description}",
        f"Direction: {action} | Timeframe: {timeframe}",
        f"Stop Loss: {stop_loss_pct:.1%} | Take Profit: {take_profit_pct:.1%} | Position Size: {position_size_pct:.1%}",
        "",
        "## Current Market Data",
    ]

    for sd in symbol_data:
        sym = sd["symbol"]
        price = sd["price"]
        indicators = sd["indicators"]

        lines.append(f"\n### {sym} — ${price:.2f}")

        # Core indicators
        for key in ["RSI_14", "RSI_7"]:
            val = indicators.get(key)
            if val is not None:
                lines.append(f"  RSI({key.split('_')[1]}): {val:.2f}")

        for key in ["SMA_20", "SMA_50", "SMA_200"]:
            val = indicators.get(key)
            if val is not None:
                pct_diff = ((price - val) / val) * 100
                above_below = "above" if price > val else "below"
                lines.append(f"  {key}: {val:.2f} (price {above_below} by {abs(pct_diff):.1f}%)")

        for key in ["EMA_20", "EMA_50", "EMA_200"]:
            val = indicators.get(key)
            if val is not None:
                pct_diff = ((price - val) / val) * 100
                above_below = "above" if price > val else "below"
                lines.append(f"  {key}: {val:.2f} (price {above_below} by {abs(pct_diff):.1f}%)")

        macd = indicators.get("MACD")
        if isinstance(macd, dict):
            lines.append(
                f"  MACD: {macd.get('macd', 0):.4f}, Signal: {macd.get('signal', 0):.4f}, "
                f"Histogram: {macd.get('histogram', 0):.4f}"
            )
            prev_hist = macd.get("prev_histogram")
            if prev_hist is not None:
                hist = macd.get("histogram", 0)
                direction = "improving" if (hist or 0) > (prev_hist or 0) else "deteriorating"
                lines.append(f"  MACD Histogram Trend: {direction}")

        bbands = indicators.get("BBANDS")
        if isinstance(bbands, dict):
            upper = bbands.get("upper", 0)
            lower = bbands.get("lower", 0)
            mid = bbands.get("middle", 0)
            if upper and lower:
                bb_pct = ((price - lower) / (upper - lower)) * 100 if (upper - lower) > 0 else 50
                lines.append(f"  Bollinger Bands: {lower:.2f} / {mid:.2f} / {upper:.2f} (price at {bb_pct:.0f}%)")

        stoch = indicators.get("STOCHASTIC")
        if isinstance(stoch, dict):
            k_val = stoch.get("k")
            d_val = stoch.get("d")
            if k_val is not None:
                lines.append(f"  Stochastic: K={k_val:.1f}, D={d_val or 0:.1f}")

        for key in ["ATR_14"]:
            val = indicators.get(key)
            if val is not None:
                atr_pct = (val / price) * 100 if price > 0 else 0
                lines.append(f"  ATR(14): {val:.2f} ({atr_pct:.2f}% of price)")

        vol = indicators.get("VOLUME")
        if vol is not None:
            lines.append(f"  Volume: {vol:,.0f}")

        vwap = indicators.get("VWAP")
        if vwap is not None:
            lines.append(f"  VWAP: {vwap:.2f}")

    if open_positions:
        lines.append(f"\n## Open Positions (SKIP these symbols): {', '.join(open_positions)}")
    else:
        lines.append("\n## Open Positions: None")

    lines.append("\nEvaluate each symbol and return your decisions as JSON.")
    return "\n".join(lines)


async def ai_evaluate_entries(
    *,
    strategy_name: str,
    strategy_description: str,
    action: str,
    stop_loss_pct: float,
    take_profit_pct: float,
    position_size_pct: float,
    timeframe: str,
    symbol_data: list[dict],
    open_positions: list[str] | None = None,
    mode: str = "paper",
) -> list[AIEntrySignal]:
    """
    Use an LLM to evaluate which symbols should be entered.

    Parameters
    ----------
    symbol_data : list[dict]
        Each dict has: {"symbol": str, "price": float, "indicators": dict}
    open_positions : list[str]
        Symbols with existing open positions (AI will skip these).

    Returns
    -------
    list[AIEntrySignal]
        One signal per symbol, with action="enter" or "hold".
    """
    settings = get_settings()
    if not settings.openai_api_key and not settings.anthropic_api_key:
        logger.warning("ai_evaluator_no_api_key")
        return []

    open_positions = open_positions or []
    prompt = _build_evaluation_prompt(
        strategy_name=strategy_name,
        strategy_description=strategy_description,
        action=action,
        stop_loss_pct=stop_loss_pct,
        take_profit_pct=take_profit_pct,
        position_size_pct=position_size_pct,
        timeframe=timeframe,
        symbol_data=symbol_data,
        open_positions=open_positions,
    )

    router = _get_router()

    # Pick the right provider and model based on available API keys
    if settings.openai_api_key:
        routing = router.route(mode="strategy", message="evaluate entries", has_tools=False)
        model = settings.openai_low_latency_model or routing.model
        provider = routing.provider
    else:
        # Fall back to Anthropic when OpenAI isn't configured
        routing = router.route(
            mode="strategy", message="evaluate entries",
            has_tools=False, openai_failed=True,
        )
        model = settings.anthropic_fallback_model or "claude-sonnet-4-6-20250514"
        provider = routing.provider

    try:
        response = await provider.complete(
            messages=[
                ProviderMessage(role="system", content=_get_system_prompt(mode)),
                ProviderMessage(role="user", content=prompt),
            ],
            model=model,
            temperature=0.4,
            max_tokens=800,
            store=False,
        )

        raw = response.content.strip()
        parsed = _extract_json(raw)
        if parsed is None:
            logger.warning("ai_evaluator_parse_failed", raw=raw[:200])
            return []

        decisions = parsed.get("decisions", [])
        signals = []
        for d in decisions:
            sym = str(d.get("symbol", "")).upper()
            act = str(d.get("action", "hold")).lower()
            conf = int(d.get("confidence", 0))
            reasoning = str(d.get("reasoning", ""))

            # Skip symbols with open positions
            if sym in open_positions:
                act = "hold"

            signals.append(AIEntrySignal(
                symbol=sym,
                action=act,
                confidence=conf,
                reasoning=reasoning,
            ))

        logger.info(
            "ai_evaluator_complete",
            strategy=strategy_name,
            model=model,
            signals={s.symbol: f"{s.action}({s.confidence})" for s in signals},
        )
        return signals

    except Exception as e:
        logger.error("ai_evaluator_error", error=str(e), exc_info=True)
        return []


def _extract_json(text: str) -> dict | None:
    """Extract JSON from LLM response, handling markdown fences."""
    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try fenced JSON
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Try finding first JSON object
    start = text.find("{")
    if start >= 0:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i + 1])
                    except json.JSONDecodeError:
                        break
    return None
