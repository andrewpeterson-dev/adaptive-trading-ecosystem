"""
Strategy explainer — structured analysis of strategy logic.
Uses rule-based reasoning with optional LLM enhancement.
"""

from fastapi import APIRouter
from pydantic import BaseModel
import re
import structlog

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/explain", tags=["explainer"])


class ExplainRequest(BaseModel):
    strategy_logic: str


class ExplainResponse(BaseModel):
    summary: str
    market_regime: str
    strengths: list[str]
    weaknesses: list[str]
    risk_profile: str
    overfitting_warning: bool


# Indicator properties for reasoning
INDICATOR_TRAITS = {
    "rsi": {"type": "momentum", "mean_reverting": True, "lag": "low", "category": "oscillator"},
    "sma": {"type": "trend", "mean_reverting": False, "lag": "high", "category": "moving_average"},
    "ema": {"type": "trend", "mean_reverting": False, "lag": "medium", "category": "moving_average"},
    "macd": {"type": "momentum", "mean_reverting": False, "lag": "medium", "category": "trend_momentum"},
    "bollinger_bands": {"type": "volatility", "mean_reverting": True, "lag": "medium", "category": "volatility"},
    "atr": {"type": "volatility", "mean_reverting": False, "lag": "low", "category": "volatility"},
    "vwap": {"type": "volume", "mean_reverting": True, "lag": "low", "category": "volume_price"},
    "stochastic": {"type": "momentum", "mean_reverting": True, "lag": "low", "category": "oscillator"},
    "obv": {"type": "volume", "mean_reverting": False, "lag": "low", "category": "volume"},
}


def _parse_indicators(logic: str) -> list[dict]:
    """Extract indicators and their conditions from strategy logic string."""
    indicators = []
    # Match patterns like RSI(14), EMA(200), MACD, Bollinger Bands, etc.
    pattern = r'(RSI|SMA|EMA|MACD|Bollinger[_ ]?Bands?|ATR|VWAP|Stochastic|OBV)\s*\(?\s*(\d+)?\s*\)?\s*(>|<|>=|<=|==|crosses?\s*(?:above|below))?\s*([\d.]+)?'
    matches = re.finditer(pattern, logic, re.IGNORECASE)
    for m in matches:
        name = m.group(1).lower().replace(" ", "_").replace("bands", "bands")
        if "bollinger" in name:
            name = "bollinger_bands"
        param = int(m.group(2)) if m.group(2) else None
        operator = m.group(3) or ""
        value = float(m.group(4)) if m.group(4) else None
        indicators.append({"name": name, "param": param, "operator": operator.strip(), "value": value})
    return indicators


def _detect_regime(indicators: list[dict], action: str) -> str:
    types = set()
    for ind in indicators:
        traits = INDICATOR_TRAITS.get(ind["name"], {})
        types.add(traits.get("type", "unknown"))

    if action.upper() == "BUY":
        if "momentum" in types and "trend" in types:
            return "Trending bullish — strategy seeks confirmed upward momentum with trend alignment"
        if "momentum" in types:
            return "Mean-reverting oversold — strategy looks for bounce opportunities"
        if "volatility" in types:
            return "Low volatility breakout — strategy targets compression-to-expansion transitions"
    elif action.upper() == "SELL":
        if "momentum" in types:
            return "Overbought reversal — strategy targets exhaustion in upward moves"
    return "Mixed regime — strategy combines multiple signal types"


def _analyze_strengths(indicators: list[dict]) -> list[str]:
    strengths = []
    categories = set()
    for ind in indicators:
        traits = INDICATOR_TRAITS.get(ind["name"], {})
        categories.add(traits.get("category", "unknown"))

    if len(categories) >= 2:
        strengths.append("Uses indicators from multiple categories, providing signal diversification")
    if any(INDICATOR_TRAITS.get(i["name"], {}).get("type") == "volume" for i in indicators):
        strengths.append("Includes volume confirmation, which reduces false breakout signals")
    if any(INDICATOR_TRAITS.get(i["name"], {}).get("mean_reverting") for i in indicators):
        strengths.append("Incorporates mean-reversion logic, effective in ranging markets")
    if any(INDICATOR_TRAITS.get(i["name"], {}).get("lag") == "low" for i in indicators):
        strengths.append("Uses low-lag indicators for faster signal generation")
    if len(indicators) >= 2:
        strengths.append("Multi-indicator confirmation reduces false signal rate")
    if not strengths:
        strengths.append("Simple strategy with clear, interpretable logic")
    return strengths


def _analyze_weaknesses(indicators: list[dict]) -> list[str]:
    weaknesses = []
    categories = [INDICATOR_TRAITS.get(i["name"], {}).get("category", "") for i in indicators]

    if len(set(categories)) == 1 and len(indicators) > 1:
        weaknesses.append(f"All indicators are from the same category ({categories[0]}), creating redundant signals")
    if all(INDICATOR_TRAITS.get(i["name"], {}).get("lag") == "high" for i in indicators):
        weaknesses.append("All indicators have high lag — signals may arrive too late in fast-moving markets")
    if len(indicators) > 4:
        weaknesses.append("High condition count reduces trade frequency and increases curve-fitting risk")
    if not any(INDICATOR_TRAITS.get(i["name"], {}).get("type") == "volume" for i in indicators):
        weaknesses.append("No volume confirmation — vulnerable to low-volume false signals")
    for ind in indicators:
        if ind["name"] == "rsi" and ind.get("param") and ind["param"] < 7:
            weaknesses.append(f"RSI({ind['param']}) is very short-period, generating noisy signals")
    if not weaknesses:
        weaknesses.append("No significant structural weaknesses detected")
    return weaknesses


def _assess_risk(indicators: list[dict], action: str) -> str:
    mean_rev_count = sum(1 for i in indicators if INDICATOR_TRAITS.get(i["name"], {}).get("mean_reverting"))
    trend_count = sum(1 for i in indicators if INDICATOR_TRAITS.get(i["name"], {}).get("type") == "trend")

    if mean_rev_count > trend_count:
        return "Moderate — mean-reversion strategies perform well in ranges but face significant risk during strong trends. Use stop-losses and avoid during news events."
    if trend_count > mean_rev_count:
        return "Moderate-High — trend-following strategies can suffer whipsaw losses in choppy markets. Size positions conservatively and use trailing stops."
    return "Moderate — balanced approach between trend and mean-reversion. Risk depends heavily on market regime and parameter selection."


def _check_overfitting(indicators: list[dict]) -> bool:
    for ind in indicators:
        if ind.get("param"):
            bounds = {
                "rsi": (5, 50), "sma": (5, 200), "ema": (5, 200),
                "stochastic": (5, 30), "atr": (5, 50),
            }
            b = bounds.get(ind["name"])
            if b and (ind["param"] < b[0] or ind["param"] > b[1]):
                return True
    if len(indicators) > 5:
        return True
    return False


@router.post("/strategy", response_model=ExplainResponse)
async def explain_strategy(req: ExplainRequest):
    logic = req.strategy_logic
    indicators = _parse_indicators(logic)

    # Detect action
    action = "BUY"
    if re.search(r'\bSELL\b|\bSHORT\b', logic, re.IGNORECASE):
        action = "SELL"

    if not indicators:
        return ExplainResponse(
            summary="Could not parse any recognized indicators from the strategy logic. Supported indicators: RSI, SMA, EMA, MACD, Bollinger Bands, ATR, VWAP, Stochastic, OBV.",
            market_regime="Unknown",
            strengths=[],
            weaknesses=["No recognizable indicator patterns found"],
            risk_profile="Cannot assess",
            overfitting_warning=False,
        )

    ind_names = [f"{i['name'].upper()}({i['param']})" if i.get('param') else i['name'].upper() for i in indicators]
    summary = (
        f"This strategy uses {len(indicators)} indicator(s): {', '.join(ind_names)}. "
        f"It generates a {action} signal when all conditions are met simultaneously. "
    )

    regime = _detect_regime(indicators, action)
    strengths = _analyze_strengths(indicators)
    weaknesses = _analyze_weaknesses(indicators)
    risk = _assess_risk(indicators, action)
    overfitting = _check_overfitting(indicators)

    if overfitting:
        summary += "Warning: parameter values or condition count suggest potential overfitting to historical data."

    logger.info("strategy_explained", indicators=len(indicators), action=action, overfitting=overfitting)

    return ExplainResponse(
        summary=summary,
        market_regime=regime,
        strengths=strengths,
        weaknesses=weaknesses,
        risk_profile=risk,
        overfitting_warning=overfitting,
    )
