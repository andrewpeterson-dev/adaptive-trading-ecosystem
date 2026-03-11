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
                    ],
                },
            }

        system_prompt = (
            "You are generating structured trading strategies for an autonomous AI bot platform. "
            "Return JSON only. Convert plain-language ideas into indicator-driven rules that can "
            "run in the existing strategy builder. Use only these indicators: rsi, sma, ema, macd, "
            "atr, stochastic, vwap, volume. If a prompt references macro, earnings, options, or news "
            "that the schema cannot encode directly, translate it into a reasonable technical proxy and "
            "explain that proxy in overview/assumptions. Use strategyType='ai_generated'."
        )
        user_prompt = (
            f"User request: {prompt}\n"
            "Generate a strategy spec with concise, practical risk settings. "
            "Favor 2-4 entry conditions max. Symbols should be the underlying ticker(s) only."
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

    def _generate_heuristic(self, prompt: str) -> GeneratedStrategySpec:
        prompt_lower = prompt.lower()
        tickers = _extract_symbols(prompt)
        action = "SELL" if any(token in prompt_lower for token in ["short", "sell", "bearish", "fade"]) else "BUY"

        if "earnings" in prompt_lower:
            template = {
                "name": "AI Earnings Surprise Momentum",
                "description": "Targets post-earnings continuation using momentum and participation proxies.",
                "timeframe": "1D",
                "stopLossPct": 2.8,
                "takeProfitPct": 7.5,
                "positionPct": 12,
                "entryConditions": [
                    {"logic": "AND", "indicator": "volume", "params": {}, "operator": ">", "value": 2000000, "signal": "Unusually strong participation"},
                    {"logic": "AND", "indicator": "rsi", "params": {"period": 14}, "operator": ">", "value": 58 if action == "BUY" else 42, "signal": "Momentum confirms post-event direction"},
                    {"logic": "AND", "indicator": "macd", "params": {"fast": 12, "slow": 26, "signal": 9}, "operator": ">", "value": 0 if action == "BUY" else -0.1, "signal": "Trend acceleration remains favorable"},
                ],
                "assumptions": [
                    "Earnings data is proxied through price, volume, and momentum because the builder schema is indicator-based.",
                ],
            }
        elif "volatility breakout" in prompt_lower or "breakout" in prompt_lower or "volatility" in prompt_lower:
            template = {
                "name": "AI Volatility Breakout Bot",
                "description": "Looks for volatility expansion with momentum confirmation after a compressed regime.",
                "timeframe": "15m" if "options" in prompt_lower or "intraday" in prompt_lower else "1H",
                "stopLossPct": 1.8,
                "takeProfitPct": 4.5,
                "positionPct": 8,
                "entryConditions": [
                    {"logic": "AND", "indicator": "atr", "params": {"period": 14}, "operator": ">", "value": 2.0, "signal": "Range expansion is underway"},
                    {"logic": "AND", "indicator": "rsi", "params": {"period": 14}, "operator": ">", "value": 60 if action == "BUY" else 40, "signal": "Momentum aligns with the breakout"},
                    {"logic": "AND", "indicator": "volume", "params": {}, "operator": ">", "value": 1500000, "signal": "Breakout is backed by participation"},
                ],
                "assumptions": [
                    "Options intent is mapped to the underlying symbol because the builder schema currently encodes underlying trade logic only.",
                ],
            }
        elif "fed" in prompt_lower or "rate cut" in prompt_lower or "rates" in prompt_lower:
            template = {
                "name": "AI Fed Easing Trend Follower",
                "description": "Maps an easing-policy thesis into trend and momentum confirmation rules on liquid index exposure.",
                "timeframe": "1D",
                "stopLossPct": 2.2,
                "takeProfitPct": 6.0,
                "positionPct": 10,
                "entryConditions": [
                    {"logic": "AND", "indicator": "rsi", "params": {"period": 14}, "operator": ">", "value": 55 if action == "BUY" else 45, "signal": "Momentum confirms the macro thesis"},
                    {"logic": "AND", "indicator": "macd", "params": {"fast": 12, "slow": 26, "signal": 9}, "operator": ">", "value": 0 if action == "BUY" else -0.1, "signal": "Trend acceleration is positive"},
                    {"logic": "AND", "indicator": "volume", "params": {}, "operator": ">", "value": 1200000, "signal": "Participation remains elevated"},
                ],
                "assumptions": [
                    "Fed language is translated into price and momentum proxies because the current schema does not encode macro event feeds directly.",
                ],
            }
        else:
            template = {
                "name": "AI Momentum Allocation Bot",
                "description": "General AI-generated momentum strategy with clear trend, confirmation, and risk parameters.",
                "timeframe": "1D",
                "stopLossPct": 2.0,
                "takeProfitPct": 5.5,
                "positionPct": 10,
                "entryConditions": [
                    {"logic": "AND", "indicator": "rsi", "params": {"period": 14}, "operator": ">", "value": 56 if action == "BUY" else 44, "signal": "Momentum bias is favorable"},
                    {"logic": "AND", "indicator": "macd", "params": {"fast": 12, "slow": 26, "signal": 9}, "operator": ">", "value": 0 if action == "BUY" else -0.1, "signal": "Trend acceleration confirms the move"},
                    {"logic": "AND", "indicator": "volume", "params": {}, "operator": ">", "value": 1000000, "signal": "Participation is sufficient for follow-through"},
                ],
                "assumptions": [
                    "Plain-language intent was mapped into a momentum/trend proxy because no more specific event feed was available in the builder schema.",
                ],
            }

        if action == "SELL":
            template["description"] = template["description"].replace("strategy", "short strategy")
            for condition in template["entryConditions"]:
                if condition["indicator"] == "rsi":
                    condition["operator"] = "<"
                elif condition["indicator"] == "macd":
                    condition["operator"] = "<"
                elif condition["indicator"] == "volume":
                    condition["operator"] = ">"

        spec_dict = {
            **template,
            "action": action,
            "exitConditions": [],
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
