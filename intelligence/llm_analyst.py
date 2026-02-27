"""
LLM Market Intelligence Layer.
Uses Claude or GPT to analyze market conditions and produce structured
assessments that feed into regime detection and model weighting.

This is NOT a replacement for quantitative models — it's an additional
signal source that captures qualitative factors (news sentiment, macro context,
cross-asset correlations) that rule-based models miss.
"""

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd
import structlog

from config.settings import get_settings

logger = structlog.get_logger(__name__)


@dataclass
class MarketAnalysis:
    """Structured output from LLM market analysis."""
    timestamp: str
    regime_assessment: str       # bull, bear, sideways, volatile, crisis
    confidence: float            # 0.0 to 1.0
    bias: str                    # long, short, neutral
    bias_strength: float         # 0.0 to 1.0
    key_factors: list[str]       # Top 3-5 factors driving the assessment
    risk_level: str              # low, moderate, elevated, high, extreme
    sector_rotation: dict        # sector -> sentiment
    recommended_adjustments: dict  # model_type -> weight_modifier
    reasoning: str               # Full chain-of-thought
    raw_response: str = ""
    model_used: str = ""
    latency_ms: int = 0

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "regime_assessment": self.regime_assessment,
            "confidence": self.confidence,
            "bias": self.bias,
            "bias_strength": self.bias_strength,
            "key_factors": self.key_factors,
            "risk_level": self.risk_level,
            "sector_rotation": self.sector_rotation,
            "recommended_adjustments": self.recommended_adjustments,
            "reasoning": self.reasoning,
            "model_used": self.model_used,
            "latency_ms": self.latency_ms,
        }


class LLMAnalyst:
    """
    Calls an LLM API with real market data context and returns structured
    analysis. Designed to be used alongside (not replacing) the quantitative
    regime detector.
    """

    def __init__(self):
        self.settings = get_settings()
        self._history: list[MarketAnalysis] = []
        self._last_analysis_time: float = 0
        self._client = None

    def _get_client(self):
        """Lazy-init the API client."""
        if self._client is not None:
            return self._client

        provider = self.settings.llm_provider.lower()

        if provider == "anthropic":
            if not self.settings.anthropic_api_key:
                raise ValueError(
                    "ANTHROPIC_API_KEY not set. Add it to your .env file."
                )
            import anthropic
            self._client = anthropic.Anthropic(
                api_key=self.settings.anthropic_api_key
            )
        elif provider == "openai":
            if not self.settings.openai_api_key:
                raise ValueError(
                    "OPENAI_API_KEY not set. Add it to your .env file."
                )
            import openai
            self._client = openai.OpenAI(
                api_key=self.settings.openai_api_key
            )
        else:
            raise ValueError(f"Unknown LLM provider: {provider}")

        return self._client

    def _build_market_context(self, df: pd.DataFrame, regime_data: dict) -> str:
        """Build a rich market context string from real data."""
        if len(df) < 60:
            return "Insufficient data for analysis."

        close = df["close"]
        volume = df["volume"]

        # Price action summary
        current_price = close.iloc[-1]
        price_1d = close.iloc[-2] if len(close) > 1 else current_price
        price_5d = close.iloc[-5] if len(close) > 5 else current_price
        price_20d = close.iloc[-20] if len(close) > 20 else current_price
        price_50d = close.iloc[-50] if len(close) > 50 else current_price

        ret_1d = (current_price / price_1d - 1) * 100
        ret_5d = (current_price / price_5d - 1) * 100
        ret_20d = (current_price / price_20d - 1) * 100
        ret_50d = (current_price / price_50d - 1) * 100

        # Technical indicators
        sma_20 = close.rolling(20).mean().iloc[-1]
        sma_50 = close.rolling(50).mean().iloc[-1]
        sma_200 = close.rolling(200).mean().iloc[-1] if len(close) >= 200 else np.nan

        log_rets = np.log(close / close.shift(1)).dropna()
        vol_20d = log_rets.rolling(20).std().iloc[-1] * np.sqrt(252)
        vol_hist = log_rets.rolling(20).std() * np.sqrt(252)
        vol_percentile = (vol_hist.rank(pct=True).iloc[-1] * 100) if len(vol_hist) > 20 else 50

        # RSI
        delta = close.diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain.iloc[-1] / loss.iloc[-1] if loss.iloc[-1] > 0 else 100
        rsi = 100 - (100 / (1 + rs))

        # MACD
        ema12 = close.ewm(span=12).mean()
        ema26 = close.ewm(span=26).mean()
        macd = ema12.iloc[-1] - ema26.iloc[-1]
        signal_line = (ema12 - ema26).ewm(span=9).mean().iloc[-1]
        macd_hist = macd - signal_line

        # Volume analysis
        avg_vol_20 = volume.rolling(20).mean().iloc[-1]
        vol_ratio = volume.iloc[-1] / avg_vol_20 if avg_vol_20 > 0 else 1.0

        # Bollinger Bands
        bb_mid = sma_20
        bb_std = close.rolling(20).std().iloc[-1]
        bb_upper = bb_mid + 2 * bb_std
        bb_lower = bb_mid - 2 * bb_std
        bb_pct = (current_price - bb_lower) / (bb_upper - bb_lower) if (bb_upper - bb_lower) > 0 else 0.5

        # Recent price action (last 5 days)
        recent = df.tail(5)
        recent_str = "\n".join([
            f"  {row['timestamp'].strftime('%Y-%m-%d') if hasattr(row['timestamp'], 'strftime') else str(row['timestamp'])}: "
            f"O={row['open']:.2f} H={row['high']:.2f} L={row['low']:.2f} C={row['close']:.2f} V={row['volume']:,.0f}"
            for _, row in recent.iterrows()
        ])

        # Regime context
        regime_str = regime_data.get("regime", "unknown")
        if hasattr(regime_str, "value"):
            regime_str = regime_str.value

        context = f"""MARKET DATA SNAPSHOT
Symbol: SPY (S&P 500 ETF)
Current Price: ${current_price:.2f}
Timestamp: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}

RETURNS:
  1-day:  {ret_1d:+.2f}%
  5-day:  {ret_5d:+.2f}%
  20-day: {ret_20d:+.2f}%
  50-day: {ret_50d:+.2f}%

MOVING AVERAGES:
  SMA 20:  ${sma_20:.2f} (price {'above' if current_price > sma_20 else 'below'})
  SMA 50:  ${sma_50:.2f} (price {'above' if current_price > sma_50 else 'below'})
  SMA 200: {'${:.2f}'.format(sma_200) if not np.isnan(sma_200) else 'N/A'} {('(price ' + ('above' if current_price > sma_200 else 'below') + ')') if not np.isnan(sma_200) else ''}

VOLATILITY:
  20-day annualized: {vol_20d:.1%}
  Percentile (vs history): {vol_percentile:.0f}th

MOMENTUM INDICATORS:
  RSI(14): {rsi:.1f} ({'overbought' if rsi > 70 else 'oversold' if rsi < 30 else 'neutral'})
  MACD: {macd:.2f} (signal: {signal_line:.2f}, histogram: {macd_hist:.2f})
  Bollinger %B: {bb_pct:.2f} ({'above upper' if bb_pct > 1 else 'below lower' if bb_pct < 0 else 'within bands'})

VOLUME:
  Latest: {volume.iloc[-1]:,.0f}
  20-day avg: {avg_vol_20:,.0f}
  Ratio: {vol_ratio:.2f}x {'(ELEVATED)' if vol_ratio > 1.5 else '(subdued)' if vol_ratio < 0.7 else ''}

QUANTITATIVE REGIME DETECTOR OUTPUT:
  Classification: {regime_str}
  Confidence: {regime_data.get('confidence', 0):.1%}
  Trend Strength: {regime_data.get('trend_strength', 0):.6f}

RECENT PRICE ACTION (last 5 bars):
{recent_str}
"""
        return context

    def _build_prompt(self, market_context: str, model_performance: list[dict]) -> str:
        """Build the analysis prompt with market data and model performance."""
        perf_str = ""
        if model_performance:
            perf_lines = []
            for mp in model_performance:
                perf_lines.append(
                    f"  {mp['name']}: Sharpe={mp['sharpe']:.3f}, "
                    f"WinRate={mp['win_rate']:.1%}, "
                    f"DD={mp['max_drawdown']:.2%}, "
                    f"Weight={mp['weight']:.1%}"
                )
            perf_str = "CURRENT MODEL PERFORMANCE:\n" + "\n".join(perf_lines)

        return f"""{market_context}

{perf_str}

ACTIVE STRATEGY TYPES:
- Momentum (fast/slow MA crossovers)
- Mean Reversion (z-score based)
- Volatility Squeeze (BB compression breakouts)
- Event-Driven (earnings momentum)
- IV Crush (implied vol contraction)
- Pairs Stat-Arb (SPY/QQQ spread)
- Breakout (support/resistance channel)
- ML Classifiers (XGBoost, Random Forest)

You are a quantitative market analyst for an automated multi-model trading system.
Analyze the provided market data and produce a structured assessment.

Your output MUST be valid JSON matching this exact schema:
{{
    "regime_assessment": "bull|bear|sideways|volatile|crisis",
    "confidence": 0.0-1.0,
    "bias": "long|short|neutral",
    "bias_strength": 0.0-1.0,
    "key_factors": ["factor1", "factor2", "factor3"],
    "risk_level": "low|moderate|elevated|high|extreme",
    "sector_rotation": {{
        "momentum": "overweight|neutral|underweight",
        "mean_reversion": "overweight|neutral|underweight",
        "volatility": "overweight|neutral|underweight",
        "breakout": "overweight|neutral|underweight"
    }},
    "recommended_adjustments": {{
        "momentum_models": 0.8-1.2,
        "mean_reversion_models": 0.8-1.2,
        "volatility_models": 0.8-1.2,
        "breakout_models": 0.8-1.2,
        "ml_models": 0.8-1.2
    }},
    "reasoning": "2-4 sentence explanation of your analysis"
}}

Rules:
- recommended_adjustments are MULTIPLIERS on current weights (1.0 = no change, 1.2 = 20% increase, 0.8 = 20% decrease)
- Be conservative: only deviate from 1.0 when you have clear evidence
- If data is ambiguous, set confidence low and keep adjustments near 1.0
- key_factors should reference specific data points from the snapshot above
- Output ONLY the JSON object, no markdown, no explanation outside the JSON"""

    def analyze(
        self,
        df: pd.DataFrame,
        regime_data: dict,
        model_performance: Optional[list[dict]] = None,
    ) -> MarketAnalysis:
        """
        Run LLM analysis on current market conditions.
        Returns a structured MarketAnalysis object.
        """
        start_ms = int(time.time() * 1000)
        market_context = self._build_market_context(df, regime_data)
        prompt = self._build_prompt(market_context, model_performance or [])

        client = self._get_client()
        provider = self.settings.llm_provider.lower()
        model = self.settings.llm_model
        raw_response = ""

        for attempt in range(self.settings.llm_max_retries + 1):
            try:
                if provider == "anthropic":
                    response = client.messages.create(
                        model=model,
                        max_tokens=1024,
                        temperature=self.settings.llm_temperature,
                        messages=[{"role": "user", "content": prompt}],
                    )
                    raw_response = response.content[0].text
                elif provider == "openai":
                    response = client.chat.completions.create(
                        model=model,
                        max_tokens=1024,
                        temperature=self.settings.llm_temperature,
                        messages=[{"role": "user", "content": prompt}],
                    )
                    raw_response = response.choices[0].message.content

                break
            except Exception as e:
                logger.warning("llm_call_failed", attempt=attempt, error=str(e))
                if attempt == self.settings.llm_max_retries:
                    return self._fallback_analysis(regime_data, str(e), start_ms)

        # Parse JSON response
        analysis = self._parse_response(raw_response, regime_data, model, start_ms)
        self._history.append(analysis)
        self._last_analysis_time = time.time()

        logger.info(
            "llm_analysis_complete",
            regime=analysis.regime_assessment,
            confidence=analysis.confidence,
            bias=analysis.bias,
            latency_ms=analysis.latency_ms,
        )
        return analysis

    def _parse_response(
        self,
        raw: str,
        regime_data: dict,
        model_name: str,
        start_ms: int,
    ) -> MarketAnalysis:
        """Parse LLM JSON response into MarketAnalysis."""
        latency = int(time.time() * 1000) - start_ms

        # Strip markdown code fences if present
        text = raw.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # Try to extract JSON from surrounding text
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                try:
                    data = json.loads(text[start:end])
                except json.JSONDecodeError:
                    logger.error("llm_json_parse_failed", raw=text[:200])
                    return self._fallback_analysis(regime_data, "JSON parse failed", start_ms)
            else:
                logger.error("llm_no_json_found", raw=text[:200])
                return self._fallback_analysis(regime_data, "No JSON in response", start_ms)

        # Validate and extract with safe defaults
        valid_regimes = {"bull", "bear", "sideways", "volatile", "crisis"}
        valid_biases = {"long", "short", "neutral"}
        valid_risks = {"low", "moderate", "elevated", "high", "extreme"}

        regime = data.get("regime_assessment", "sideways")
        if regime not in valid_regimes:
            regime = "sideways"

        bias = data.get("bias", "neutral")
        if bias not in valid_biases:
            bias = "neutral"

        risk = data.get("risk_level", "moderate")
        if risk not in valid_risks:
            risk = "moderate"

        return MarketAnalysis(
            timestamp=datetime.utcnow().isoformat(),
            regime_assessment=regime,
            confidence=max(0.0, min(1.0, float(data.get("confidence", 0.5)))),
            bias=bias,
            bias_strength=max(0.0, min(1.0, float(data.get("bias_strength", 0.5)))),
            key_factors=data.get("key_factors", [])[:5],
            risk_level=risk,
            sector_rotation=data.get("sector_rotation", {}),
            recommended_adjustments=self._validate_adjustments(
                data.get("recommended_adjustments", {})
            ),
            reasoning=data.get("reasoning", ""),
            raw_response=raw,
            model_used=model_name,
            latency_ms=latency,
        )

    def _validate_adjustments(self, adj: dict) -> dict:
        """Clamp adjustment multipliers to safe range [0.5, 1.5]."""
        validated = {}
        for key, val in adj.items():
            try:
                v = float(val)
                validated[key] = max(0.5, min(1.5, v))
            except (ValueError, TypeError):
                validated[key] = 1.0
        return validated

    def _fallback_analysis(
        self,
        regime_data: dict,
        error_msg: str,
        start_ms: int,
    ) -> MarketAnalysis:
        """Return a neutral analysis when LLM fails."""
        latency = int(time.time() * 1000) - start_ms
        regime_str = regime_data.get("regime", "sideways")
        if hasattr(regime_str, "value"):
            regime_str = regime_str.value

        # Map quantitative regime to LLM regime vocabulary
        regime_map = {
            "low_vol_bull": "bull",
            "high_vol_bull": "volatile",
            "low_vol_bear": "bear",
            "high_vol_bear": "crisis",
            "sideways": "sideways",
        }

        return MarketAnalysis(
            timestamp=datetime.utcnow().isoformat(),
            regime_assessment=regime_map.get(regime_str, "sideways"),
            confidence=regime_data.get("confidence", 0.3),
            bias="neutral",
            bias_strength=0.0,
            key_factors=[f"LLM unavailable: {error_msg}", "Falling back to quantitative regime"],
            risk_level="moderate",
            sector_rotation={},
            recommended_adjustments={
                "momentum_models": 1.0,
                "mean_reversion_models": 1.0,
                "volatility_models": 1.0,
                "breakout_models": 1.0,
                "ml_models": 1.0,
            },
            reasoning=f"Fallback analysis due to LLM error: {error_msg}. Using quantitative regime detector output.",
            raw_response="",
            model_used="fallback",
            latency_ms=latency,
        )

    def should_reanalyze(self) -> bool:
        """Check if enough time has passed for a new analysis."""
        if self._last_analysis_time == 0:
            return True
        elapsed = time.time() - self._last_analysis_time
        return elapsed >= self.settings.llm_analysis_interval_minutes * 60

    def get_latest(self) -> Optional[MarketAnalysis]:
        """Get the most recent analysis."""
        return self._history[-1] if self._history else None

    def get_history(self, limit: int = 20) -> list[dict]:
        """Get analysis history as dicts."""
        return [a.to_dict() for a in self._history[-limit:]]

    def apply_adjustments_to_weights(
        self,
        current_weights: dict[str, float],
        analysis: MarketAnalysis,
    ) -> dict[str, float]:
        """
        Apply LLM-recommended weight adjustments to current model weights.
        Maps model names to adjustment categories and applies multipliers.
        """
        adj = analysis.recommended_adjustments
        if not adj:
            return current_weights

        # Map model names to adjustment categories
        category_map = {
            "Momentum Fast": "momentum_models",
            "Momentum Slow": "momentum_models",
            "Mean Rev Tight": "mean_reversion_models",
            "Mean Rev Wide": "mean_reversion_models",
            "Vol Squeeze": "volatility_models",
            "IV Crush": "volatility_models",
            "Earnings Momentum": "volatility_models",
            "Pairs StatArb": "mean_reversion_models",
            "Breakout S/R": "breakout_models",
        }

        adjusted = {}
        for model_name, weight in current_weights.items():
            category = category_map.get(model_name, "ml_models")
            multiplier = adj.get(category, 1.0)
            adjusted[model_name] = weight * multiplier

        # Re-normalize to sum to 1.0
        total = sum(adjusted.values())
        if total > 0:
            adjusted = {k: v / total for k, v in adjusted.items()}

        logger.info("llm_weights_adjusted", adjustments=adj, result=adjusted)
        return adjusted
