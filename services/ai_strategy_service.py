"""AI-assisted strategy generation that compiles into the existing builder schema."""

from __future__ import annotations

import json
import re
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Literal

import structlog
from pydantic import BaseModel, Field, ValidationError

from config.settings import get_settings
from services.ai_core.model_router import ModelRouter
from services.ai_core.providers.base import ProviderMessage

logger = structlog.get_logger(__name__)

VALID_TIMEFRAMES = {"1m", "5m", "15m", "1H", "4H", "1D", "1W"}
VALID_ACTIONS = {"BUY", "SELL"}
VALID_OPERATORS = {">", "<", ">=", "<=", "==", "crosses_above", "crosses_below"}
SUPPORTED_INDICATORS = {"rsi", "sma", "ema", "macd", "atr", "stochastic", "vwap", "volume"}
DEFAULT_METHODS = [
    "reinforcement_learning",
    "parameter_optimization",
    "bayesian_tuning",
    "walk_forward_backtesting",
]
DEFAULT_GOALS = [
    "improve_sharpe_ratio",
    "reduce_drawdown",
    "adapt_risk_controls",
]


class GeneratedCondition(BaseModel):
    logic: Literal["AND", "OR"] = "AND"
    indicator: str
    params: dict[str, float] = Field(default_factory=dict)
    operator: str = ">"
    value: float = 0
    signal: str = ""


class LearningPlan(BaseModel):
    cadence_minutes: int = 240
    methods: list[str] = Field(default_factory=lambda: list(DEFAULT_METHODS))
    goals: list[str] = Field(default_factory=lambda: list(DEFAULT_GOALS))


class AIThinking(BaseModel):
    """Defines what the bot's AI layer should actively monitor beyond indicators."""
    marketRegimeCheck: str = "Monitor for regime changes — trending vs range-bound vs volatile."
    disruptionTriggers: list[str] = Field(default_factory=lambda: [
        "earnings releases on held symbols",
        "FOMC or Fed announcements",
        "unusual volume spike (>3x average)",
        "broad market circuit breaker events",
    ])
    adaptiveBehavior: str = "Tighten stops in high volatility, pause new entries before major events, scale out early if momentum deteriorates."


class GeneratedStrategySpec(BaseModel):
    name: str
    description: str = ""
    action: Literal["BUY", "SELL"]
    stopLossPct: float
    takeProfitPct: float
    positionPct: float
    timeframe: str
    entryConditions: list[GeneratedCondition]
    exitConditions: list[GeneratedCondition] = Field(default_factory=list)
    symbols: list[str] = Field(default_factory=lambda: ["SPY"])
    strategyType: Literal["manual", "ai_generated", "custom"] = "ai_generated"
    sourcePrompt: str = ""
    overview: str = ""
    featureSignals: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    learningPlan: LearningPlan = Field(default_factory=LearningPlan)
    aiThinking: AIThinking = Field(default_factory=AIThinking)


def extract_json(text: str) -> str | None:
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fenced:
        return fenced.group(1).strip()

    start = text.find("{")
    if start == -1:
        return None

    depth = 0
    for index in range(start, len(text)):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


def derive_feature_signals(conditions: list[dict[str, Any]]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for condition in conditions:
        indicator = str(condition.get("indicator", "")).strip().lower()
        if indicator and indicator not in seen:
            seen.add(indicator)
            ordered.append(indicator)
    return ordered


def default_learning_plan(strategy_type: str = "manual") -> dict[str, Any]:
    enabled = strategy_type in {"ai_generated", "custom"}
    return {
        "enabled": enabled,
        "cadence_minutes": 240 if enabled else 1440,
        "methods": list(DEFAULT_METHODS),
        "goals": list(DEFAULT_GOALS),
        "status": "learning" if enabled else "monitoring",
        "last_optimization_at": None,
        "last_summary": "Awaiting enough trade history to begin optimization.",
        "parameter_adjustments": [],
    }


def _normalize_condition(condition: GeneratedCondition) -> dict[str, Any]:
    indicator = condition.indicator.strip().lower()
    indicator = {
        "bollinger_bands": "atr",
        "obv": "volume",
    }.get(indicator, indicator)

    if indicator not in SUPPORTED_INDICATORS:
        raise ValueError(f"Unsupported indicator '{condition.indicator}'")

    operator = condition.operator if condition.operator in VALID_OPERATORS else ">"
    params = {str(key): float(value) for key, value in (condition.params or {}).items()}
    return {
        "indicator": indicator,
        "operator": operator,
        "value": float(condition.value),
        "params": params,
        "action": "BUY",  # overwritten during compilation
    }


def _build_condition_groups(spec: GeneratedStrategySpec) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    groups: list[dict[str, Any]] = []
    flattened: list[dict[str, Any]] = []
    current_group: list[dict[str, Any]] = []

    for raw in spec.entryConditions:
        condition = _normalize_condition(raw)
        condition["action"] = spec.action
        if raw.logic == "OR" and current_group:
            groups.append(
                {
                    "id": f"ai_group_{len(groups) + 1}",
                    "label": f"Group {chr(65 + len(groups))}",
                    "conditions": current_group,
                }
            )
            current_group = []
        current_group.append(condition)
        flattened.append(condition)

    if current_group:
        groups.append(
            {
                "id": f"ai_group_{len(groups) + 1}",
                "label": f"Group {chr(65 + len(groups))}",
                "conditions": current_group,
            }
        )

    if not groups:
        raise ValueError("AI strategy must contain at least one entry condition")

    return groups, flattened


def compile_strategy_payload(spec: GeneratedStrategySpec) -> dict[str, Any]:
    groups, flattened = _build_condition_groups(spec)
    feature_signals = spec.featureSignals or derive_feature_signals(flattened)
    learning_plan = default_learning_plan(spec.strategyType)
    learning_plan.update(spec.learningPlan.model_dump())
    learning_plan["enabled"] = spec.strategyType in {"ai_generated", "custom"}

    ai_context = {
        "overview": spec.overview or spec.description,
        "feature_signals": feature_signals,
        "assumptions": spec.assumptions,
        "learning_plan": learning_plan,
        "exit_conditions": [condition.model_dump() for condition in spec.exitConditions],
        "ai_thinking": spec.aiThinking.model_dump(),
        "generation": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
    }

    return {
        "name": spec.name,
        "description": spec.description,
        "conditions": flattened,
        "condition_groups": groups,
        "action": spec.action,
        "stop_loss_pct": round(spec.stopLossPct / 100, 4),
        "take_profit_pct": round(spec.takeProfitPct / 100, 4),
        "position_size_pct": round(spec.positionPct / 100, 4),
        "timeframe": spec.timeframe,
        "symbols": spec.symbols or ["SPY"],
        "commission_pct": 0.001,
        "slippage_pct": 0.0005,
        "trailing_stop_pct": None,
        "exit_after_bars": None,
        "cooldown_bars": 0,
        "max_trades_per_day": 0,
        "max_exposure_pct": 1.0,
        "max_loss_pct": 0.0,
        "strategy_type": spec.strategyType,
        "source_prompt": spec.sourcePrompt,
        "ai_context": ai_context,
        "universe_config": {
            "mode": "ai_selected",
            "fixed_symbols": list(spec.symbols or ["SPY"]),
            "max_symbols": 10,
        },
    }


def compile_builder_draft(spec: GeneratedStrategySpec) -> dict[str, Any]:
    payload = compile_strategy_payload(spec)
    return {
        "name": payload["name"],
        "description": payload["description"],
        "action": payload["action"],
        "stopLoss": spec.stopLossPct,
        "takeProfit": spec.takeProfitPct,
        "positionSize": spec.positionPct,
        "timeframe": payload["timeframe"],
        "conditions": deepcopy(payload["conditions"]),
        "conditionGroups": deepcopy(payload["condition_groups"]),
        "symbols": deepcopy(payload["symbols"]),
        "strategyType": payload["strategy_type"],
        "sourcePrompt": payload["source_prompt"],
        "aiContext": deepcopy(payload["ai_context"]),
    }


def strategy_record_to_bot_config(strategy_record: dict[str, Any]) -> dict[str, Any]:
    ai_context = deepcopy(strategy_record.get("ai_context") or {})
    feature_signals = ai_context.get("feature_signals") or derive_feature_signals(
        strategy_record.get("conditions") or []
    )
    learning = deepcopy(ai_context.get("learning_plan") or default_learning_plan(strategy_record.get("strategy_type", "manual")))
    learning["enabled"] = bool(learning.get("enabled", strategy_record.get("strategy_type") in {"ai_generated", "custom"}))

    return {
        "strategy_id": strategy_record.get("id"),
        "name": strategy_record.get("name"),
        "description": strategy_record.get("description") or "",
        "overview": ai_context.get("overview") or strategy_record.get("description") or "",
        "strategy_type": strategy_record.get("strategy_type", "manual"),
        "source_prompt": strategy_record.get("source_prompt"),
        "action": strategy_record.get("action", "BUY"),
        "timeframe": strategy_record.get("timeframe", "1D"),
        "stop_loss_pct": strategy_record.get("stop_loss_pct", 0.02),
        "take_profit_pct": strategy_record.get("take_profit_pct", 0.05),
        "position_size_pct": strategy_record.get("position_size_pct", 0.1),
        "symbols": deepcopy(strategy_record.get("symbols") or ["SPY"]),
        "conditions": deepcopy(strategy_record.get("conditions") or []),
        "condition_groups": deepcopy(strategy_record.get("condition_groups") or []),
        "feature_signals": feature_signals,
        "ai_context": ai_context,
        "learning": learning,
    }


class AIStrategyService:
    """Generate and validate structured strategies from natural language."""

    def __init__(self):
        self._settings = get_settings()
        self._router = ModelRouter()

    async def generate(self, prompt: str) -> dict[str, Any]:
        prompt = prompt.strip()
        if not prompt:
            raise ValueError("Prompt is required")

        spec, generation = await self._generate_spec(prompt)
        payload = compile_strategy_payload(spec)
        builder_draft = compile_builder_draft(spec)
        payload["ai_context"]["generation"].update(generation)

        return {
            "prompt": prompt,
            "strategy_spec": spec.model_dump(),
            "builder_draft": builder_draft,
            "compiled_strategy": payload,
            "generation": generation,
        }

    async def _generate_spec(self, prompt: str) -> tuple[GeneratedStrategySpec, dict[str, Any]]:
        if self._settings.openai_api_key or self._settings.anthropic_api_key:
            try:
                spec, generation = await self._generate_with_model(prompt)
                return spec, generation
            except Exception as exc:
                logger.warning("ai_strategy_generation_fallback", error=str(exc))

        spec = self._generate_heuristic(prompt)
        return spec, {"provider": "heuristic", "model": None, "validated": True}

    async def _generate_with_model(self, prompt: str) -> tuple[GeneratedStrategySpec, dict[str, Any]]:
        routing = self._router.route(mode="strategy", message=prompt, has_tools=False)
        response_format = None
        if routing.provider_name == "openai":
            response_format = {
                "type": "json_schema",
                "name": "ai_strategy_spec",
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "name": {"type": "string"},
                        "description": {"type": "string"},
                        "action": {"type": "string", "enum": ["BUY", "SELL"]},
                        "stopLossPct": {"type": "number"},
                        "takeProfitPct": {"type": "number"},
                        "positionPct": {"type": "number"},
                        "timeframe": {"type": "string"},
                        "entryConditions": {
                            "type": "array",
                            "minItems": 1,
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {
                                    "logic": {"type": "string", "enum": ["AND", "OR"]},
                                    "indicator": {"type": "string"},
                                    "params": {"type": "object"},
                                    "operator": {"type": "string"},
                                    "value": {"type": "number"},
                                    "signal": {"type": "string"},
                                },
                                "required": ["logic", "indicator", "params", "operator", "value", "signal"],
                            },
                        },
                        "exitConditions": {
                            "type": "array",
                            "minItems": 2,
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {
                                    "logic": {"type": "string", "enum": ["AND", "OR"]},
                                    "indicator": {"type": "string"},
                                    "params": {"type": "object"},
                                    "operator": {"type": "string"},
                                    "value": {"type": "number"},
                                    "signal": {"type": "string"},
                                },
                                "required": ["logic", "indicator", "params", "operator", "value", "signal"],
                            },
                        },
                        "aiThinking": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "marketRegimeCheck": {"type": "string"},
                                "disruptionTriggers": {"type": "array", "items": {"type": "string"}},
                                "adaptiveBehavior": {"type": "string"},
                            },
                            "required": ["marketRegimeCheck", "disruptionTriggers", "adaptiveBehavior"],
                        },
                        "symbols": {"type": "array", "items": {"type": "string"}},
                        "strategyType": {"type": "string", "enum": ["ai_generated"]},
                        "sourcePrompt": {"type": "string"},
                        "overview": {"type": "string"},
                        "featureSignals": {"type": "array", "items": {"type": "string"}},
                        "assumptions": {"type": "array", "items": {"type": "string"}},
                        "learningPlan": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "cadence_minutes": {"type": "integer"},
                                "methods": {"type": "array", "items": {"type": "string"}},
                                "goals": {"type": "array", "items": {"type": "string"}},
                            },
                            "required": ["cadence_minutes", "methods", "goals"],
                        },
                    },
                    "required": [
                        "name",
                        "description",
                        "action",
                        "stopLossPct",
                        "takeProfitPct",
                        "positionPct",
                        "timeframe",
                        "entryConditions",
                        "exitConditions",
                        "symbols",
                        "strategyType",
                        "sourcePrompt",
                        "overview",
                        "featureSignals",
                        "assumptions",
                        "learningPlan",
                        "aiThinking",
                    ],
                },
            }

        system_prompt = (
            "You are generating structured trading strategies for an autonomous AI bot platform. "
            "Return JSON only. Convert plain-language ideas into indicator-driven rules that can "
            "run in the existing strategy builder. Use only these indicators: rsi, sma, ema, macd, "
            "atr, stochastic, vwap, volume. If a prompt references macro, earnings, options, or news "
            "that the schema cannot encode directly, translate it into a reasonable technical proxy and "
            "explain that proxy in overview/assumptions. Use strategyType='ai_generated'.\n\n"
            "CRITICAL: Every strategy MUST include:\n"
            "1) 2-4 entryConditions that confirm the trade thesis\n"
            "2) 2-3 exitConditions that detect when the thesis breaks (RSI reversal, MACD crossover against position, trend break, etc.) — NEVER leave exitConditions empty\n"
            "3) An aiThinking block with marketRegimeCheck (what regime to watch), disruptionTriggers (events that could invalidate the strategy), and adaptiveBehavior (how the bot should adapt)\n"
            "stopLossPct and takeProfitPct are hard safety limits. exitConditions are the intelligent exits that fire BEFORE the hard stops."
        )
        user_prompt = (
            f"User request: {prompt}\n"
            "Generate a complete strategy spec. Favor 2-4 entry conditions, 2-3 exit conditions, "
            "and a thoughtful aiThinking block. Symbols should be the underlying ticker(s) only."
        )
        response = await routing.provider.complete(
            messages=[
                ProviderMessage(role="system", content=system_prompt),
                ProviderMessage(role="user", content=user_prompt),
            ],
            model=routing.model,
            temperature=0.2,
            max_tokens=1600,
            response_format=response_format,
            store=False,
        )
        raw = response.content.strip()
        json_str = extract_json(raw) or raw
        spec = GeneratedStrategySpec.model_validate(json.loads(json_str))
        spec = self._validate_and_normalize(spec, prompt)
        return spec, {
            "provider": routing.provider_name,
            "model": routing.model,
            "validated": True,
        }

    def _validate_and_normalize(self, spec: GeneratedStrategySpec, prompt: str) -> GeneratedStrategySpec:
        if spec.action not in VALID_ACTIONS:
            raise ValueError("Invalid action in AI-generated strategy")
        if spec.timeframe not in VALID_TIMEFRAMES:
            raise ValueError("Invalid timeframe in AI-generated strategy")
        if spec.stopLossPct <= 0 or spec.takeProfitPct <= 0 or spec.positionPct <= 0:
            raise ValueError("Risk fields must be positive")
        if not spec.entryConditions:
            raise ValueError("AI-generated strategy is missing entry conditions")

        # Ensure exit conditions exist — synthesize from entry signals if AI omitted them
        if not spec.exitConditions:
            spec.exitConditions = self._synthesize_exit_conditions(spec)

        spec.strategyType = "ai_generated"
        spec.sourcePrompt = prompt
        spec.symbols = [symbol.upper() for symbol in (spec.symbols or ["SPY"])][:5]
        spec.featureSignals = [
            signal.lower()
            for signal in (spec.featureSignals or derive_feature_signals([c.model_dump() for c in spec.entryConditions]))
            if signal.lower() in SUPPORTED_INDICATORS
        ]
        if not spec.featureSignals:
            spec.featureSignals = derive_feature_signals([c.model_dump() for c in spec.entryConditions])
        if not spec.overview:
            spec.overview = spec.description or f"AI-generated strategy derived from: {prompt}"
        return spec

    @staticmethod
    def _synthesize_exit_conditions(spec: GeneratedStrategySpec) -> list[GeneratedCondition]:
        """Generate intelligent exit conditions from entry signal inversions."""
        exits: list[GeneratedCondition] = []
        is_long = spec.action == "BUY"

        # Scan entry conditions for key indicators and create inverted exits
        has_rsi = False
        has_momentum = False
        for entry in spec.entryConditions:
            ind = entry.indicator.strip().lower()
            if ind == "rsi" and not has_rsi:
                has_rsi = True
                exits.append(GeneratedCondition(
                    logic="OR",
                    indicator="rsi",
                    params=entry.params,
                    operator=">" if is_long else "<",
                    value=75 if is_long else 25,
                    signal="RSI reached exhaustion — exit before reversal",
                ))
            elif ind == "macd" and not has_momentum:
                has_momentum = True
                exits.append(GeneratedCondition(
                    logic="OR",
                    indicator="macd",
                    params=entry.params,
                    operator="<" if is_long else ">",
                    value=0,
                    signal="MACD crossed against position direction — momentum lost",
                ))

        # Always add a moving average trend break exit
        exits.append(GeneratedCondition(
            logic="OR",
            indicator="ema",
            params={"period": 20},
            operator=">" if is_long else "<",
            value=0,
            signal="Price broke below EMA-20 — trend support lost" if is_long else "Price broke above EMA-20 — trend resistance broken",
        ))

        if not exits:
            # Fallback: simple RSI exhaustion exit
            exits.append(GeneratedCondition(
                logic="OR",
                indicator="rsi",
                params={"period": 14},
                operator=">" if is_long else "<",
                value=72 if is_long else 28,
                signal="RSI approaching overbought/oversold — take profit zone",
            ))

        return exits

    def _generate_heuristic(self, prompt: str) -> GeneratedStrategySpec:
        prompt_lower = prompt.lower()
        tickers = _extract_symbols(prompt)
        action = "SELL" if any(token in prompt_lower for token in ["short", "sell", "bearish", "fade"]) else "BUY"

        # Exit conditions that invert entry signals (long exits shown; SELL variants flipped below)
        _rsi_exit = {"logic": "OR", "indicator": "rsi", "params": {"period": 14}, "operator": ">", "value": 74, "signal": "RSI overbought — momentum exhaustion, exit before reversal"}
        _macd_exit = {"logic": "OR", "indicator": "macd", "params": {"fast": 12, "slow": 26, "signal": 9}, "operator": "<", "value": 0, "signal": "MACD crossed below zero — trend acceleration lost"}
        _ema_exit = {"logic": "OR", "indicator": "ema", "params": {"period": 20}, "operator": ">", "value": 0, "signal": "Price broke below EMA-20 — near-term trend support lost"}

        if "earnings" in prompt_lower:
            template = {
                "name": "AI Earnings Surprise Momentum",
                "description": "Targets post-earnings continuation using momentum and participation proxies. AI monitors for follow-through failure and abnormal reversals.",
                "timeframe": "1D",
                "stopLossPct": 2.8,
                "takeProfitPct": 7.5,
                "positionPct": 12,
                "entryConditions": [
                    {"logic": "AND", "indicator": "volume", "params": {}, "operator": ">", "value": 2000000, "signal": "Unusually strong participation confirms post-earnings move"},
                    {"logic": "AND", "indicator": "rsi", "params": {"period": 14}, "operator": ">", "value": 58 if action == "BUY" else 42, "signal": "Momentum confirms post-event direction"},
                    {"logic": "AND", "indicator": "macd", "params": {"fast": 12, "slow": 26, "signal": 9}, "operator": ">", "value": 0 if action == "BUY" else -0.1, "signal": "Trend acceleration remains favorable"},
                ],
                "exitConditions": [_rsi_exit, _macd_exit],
                "assumptions": [
                    "Earnings data is proxied through price, volume, and momentum because the builder schema is indicator-based.",
                    "AI layer will monitor for earnings revision and guidance changes that indicators cannot capture.",
                ],
                "aiThinking": {
                    "marketRegimeCheck": "Monitor if post-earnings move is continuation or exhaustion gap. Watch for volume collapse on day 2-3 as reversal signal.",
                    "disruptionTriggers": ["analyst revision against position", "sector-wide earnings miss", "guidance cut after initial beat", "unusual options activity in opposite direction"],
                    "adaptiveBehavior": "If volume collapses below average within 2 sessions of entry, tighten stops aggressively. Pause new entries during earnings blackout windows for correlated names.",
                },
            }
        elif "volatility breakout" in prompt_lower or "breakout" in prompt_lower or "volatility" in prompt_lower:
            template = {
                "name": "AI Volatility Breakout Bot",
                "description": "Detects volatility expansion with momentum confirmation after compression. AI watches for false breakouts and regime changes.",
                "timeframe": "15m" if "options" in prompt_lower or "intraday" in prompt_lower else "1H",
                "stopLossPct": 1.8,
                "takeProfitPct": 4.5,
                "positionPct": 8,
                "entryConditions": [
                    {"logic": "AND", "indicator": "atr", "params": {"period": 14}, "operator": ">", "value": 2.0, "signal": "Range expansion is underway — volatility breakout detected"},
                    {"logic": "AND", "indicator": "rsi", "params": {"period": 14}, "operator": ">", "value": 60 if action == "BUY" else 40, "signal": "Momentum aligns with the breakout direction"},
                    {"logic": "AND", "indicator": "volume", "params": {}, "operator": ">", "value": 1500000, "signal": "Breakout backed by institutional participation"},
                ],
                "exitConditions": [
                    {"logic": "OR", "indicator": "atr", "params": {"period": 14}, "operator": "<", "value": 1.0, "signal": "Volatility contracting — breakout losing steam"},
                    _rsi_exit,
                    _ema_exit,
                ],
                "assumptions": [
                    "Options intent is mapped to the underlying symbol because the builder schema encodes underlying trade logic only.",
                    "AI evaluates whether the breakout is genuine by checking volume persistence and follow-through.",
                ],
                "aiThinking": {
                    "marketRegimeCheck": "Distinguish genuine breakouts (sustained expansion + volume) from false breakouts (spike then immediate reversion). Track ATR trend over 3-5 bars.",
                    "disruptionTriggers": ["VIX spike >25%", "sudden volume collapse after breakout", "sector divergence from broad market", "FOMC meeting within 24 hours"],
                    "adaptiveBehavior": "If breakout fails to sustain volume for 2+ bars, exit immediately. Before known macro events, reduce position size by 50% or pause.",
                },
            }
        elif "fed" in prompt_lower or "rate cut" in prompt_lower or "rates" in prompt_lower:
            template = {
                "name": "AI Fed Easing Trend Follower",
                "description": "Maps an easing-policy thesis into trend and momentum confirmation. AI monitors policy language shifts and cross-asset signals.",
                "timeframe": "1D",
                "stopLossPct": 2.2,
                "takeProfitPct": 6.0,
                "positionPct": 10,
                "entryConditions": [
                    {"logic": "AND", "indicator": "rsi", "params": {"period": 14}, "operator": ">", "value": 55 if action == "BUY" else 45, "signal": "Momentum confirms the macro-driven thesis"},
                    {"logic": "AND", "indicator": "macd", "params": {"fast": 12, "slow": 26, "signal": 9}, "operator": ">", "value": 0 if action == "BUY" else -0.1, "signal": "Trend acceleration supports easing thesis"},
                    {"logic": "AND", "indicator": "ema", "params": {"period": 50}, "operator": "<", "value": 0, "signal": "Price above 50-EMA — structural uptrend intact"},
                ],
                "exitConditions": [_macd_exit, _ema_exit],
                "assumptions": [
                    "Fed language is translated into price and momentum proxies since the schema does not encode macro event feeds.",
                    "AI layer will watch for hawkish surprises that would invalidate the easing thesis.",
                ],
                "aiThinking": {
                    "marketRegimeCheck": "Track whether the rate-sensitive rally is broad-based or narrow. Monitor bond yields (TLT proxy) for divergence from equity positioning.",
                    "disruptionTriggers": ["hawkish Fed dot plot surprise", "inflation print above consensus", "employment report overshoot", "geopolitical escalation"],
                    "adaptiveBehavior": "Pause all new entries 24 hours before FOMC. If yields spike sharply against the thesis, exit 50% immediately. Resume full sizing only after market digests the event.",
                },
            }
        else:
            template = {
                "name": "AI Momentum Allocation Bot",
                "description": "AI-driven momentum strategy with trend confirmation, participation filters, and adaptive risk controls.",
                "timeframe": "1D",
                "stopLossPct": 2.0,
                "takeProfitPct": 5.5,
                "positionPct": 10,
                "entryConditions": [
                    {"logic": "AND", "indicator": "rsi", "params": {"period": 14}, "operator": ">", "value": 56 if action == "BUY" else 44, "signal": "Momentum bias is favorable for entry"},
                    {"logic": "AND", "indicator": "macd", "params": {"fast": 12, "slow": 26, "signal": 9}, "operator": ">", "value": 0 if action == "BUY" else -0.1, "signal": "Trend acceleration confirms directional move"},
                    {"logic": "AND", "indicator": "volume", "params": {}, "operator": ">", "value": 1000000, "signal": "Sufficient participation for follow-through"},
                ],
                "exitConditions": [_rsi_exit, _macd_exit, _ema_exit],
                "assumptions": [
                    "Plain-language intent mapped to momentum/trend proxy using supported indicators.",
                    "AI layer continuously evaluates whether the momentum regime persists or is degrading.",
                ],
                "aiThinking": {
                    "marketRegimeCheck": "Track whether momentum is trending or mean-reverting. If RSI oscillates between 40-60 for 5+ bars, regime has shifted to range-bound — reduce sizing.",
                    "disruptionTriggers": ["earnings release on held symbol", "macro data surprise", "sector rotation detected", "unusual put/call ratio shift"],
                    "adaptiveBehavior": "In choppy/range-bound regimes, reduce position size by 50% and widen stops. Before major events, tighten trailing stops. If multiple exit signals fire simultaneously, exit full position immediately.",
                },
            }

        if action == "SELL":
            template["description"] = template["description"].replace("strategy", "short strategy")
            for condition in template["entryConditions"]:
                if condition["indicator"] == "rsi":
                    condition["operator"] = "<"
                elif condition["indicator"] == "macd":
                    condition["operator"] = "<"
            # Flip exit conditions for short side
            for condition in template.get("exitConditions", []):
                if condition["indicator"] == "rsi":
                    condition["operator"] = "<"
                    condition["value"] = 26
                    condition["signal"] = "RSI oversold — short exhaustion, cover before reversal"
                elif condition["indicator"] == "macd":
                    condition["operator"] = ">"
                    condition["signal"] = "MACD crossed above zero — downward momentum lost"
                elif condition["indicator"] == "ema":
                    condition["operator"] = "<"
                    condition["signal"] = "Price broke above EMA-20 — short-term trend resistance broken"

        spec_dict = {
            **template,
            "action": action,
            "symbols": tickers,
            "strategyType": "ai_generated",
            "sourcePrompt": prompt,
            "overview": template["description"],
            "featureSignals": derive_feature_signals(template["entryConditions"]),
            "learningPlan": LearningPlan().model_dump(),
        }

        try:
            spec = GeneratedStrategySpec.model_validate(spec_dict)
        except ValidationError as exc:
            logger.error("heuristic_strategy_validation_failed", error=str(exc))
            raise
        return self._validate_and_normalize(spec, prompt)


def _extract_symbols(prompt: str) -> list[str]:
    uppercase = re.findall(r"\b[A-Z]{1,5}\b", prompt)
    stopwords = {"AI", "AND", "OR", "THE", "FED", "SPY"}
    symbols: list[str] = []
    for token in uppercase:
        if token in stopwords:
            if token == "SPY" and token not in symbols:
                symbols.append(token)
            continue
        if token not in symbols:
            symbols.append(token)
    return symbols[:5] or ["SPY"]
