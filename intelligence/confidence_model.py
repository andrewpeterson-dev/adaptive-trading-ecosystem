"""
Confidence aggregation model.
Combines LLM analysis, model signal strength, and track record metrics
into a single confidence score with regime-aware adjustments.

ADVISORY ONLY -- confidence scores inform trade decisions but do not
execute trades directly. The confidence output feeds into the ensemble
engine, which must pass risk management before any execution occurs.
"""

from datetime import datetime

import structlog

from intelligence.regime import Regime

logger = structlog.get_logger(__name__)

# Regimes where we apply a confidence penalty due to higher uncertainty
_UNCERTAIN_REGIMES: dict[str, float] = {
    Regime.HIGH_VOL_BEAR.value: -10.0,
    Regime.HIGH_VOL_BULL.value: -5.0,
    Regime.SIDEWAYS.value: -3.0,
}


class ConfidenceModel:
    """
    Aggregate confidence from multiple signal sources.
    Combines: LLM analysis score, technical indicator signals, model predictions.

    All inputs are normalized to a 0-100 scale internally.
    """

    def __init__(
        self,
        min_confidence: float = 40.0,
        llm_weight: float = 0.3,
        model_weight: float = 0.4,
        track_record_weight: float = 0.3,
    ):
        self.min_confidence = min_confidence
        self.llm_weight = llm_weight
        self.model_weight = model_weight
        self.track_record_weight = track_record_weight
        self._history: list[dict] = []

    def compute_confidence(
        self,
        llm_confidence: float,
        model_signal_strength: float,
        model_metrics: dict,
        regime: str,
    ) -> dict:
        """
        Weighted confidence scoring.

        Args:
            llm_confidence: 0-100 from LLM analyst (or 0 if unavailable).
            model_signal_strength: 0-1 from trading model signal.
            model_metrics: dict with keys like sharpe_ratio, win_rate, max_drawdown.
            regime: regime string from RegimeDetector (e.g. "low_vol_bull").

        Returns dict with overall_confidence, components, confidence_interval,
        passes_threshold, and regime_adjustment.
        """
        # Normalize model signal strength from 0-1 to 0-100
        model_score = model_signal_strength * 100.0

        # Compute track record score from model metrics
        track_score = self._compute_track_record_score(model_metrics)

        # Handle missing LLM data: redistribute weight to model + track record
        if llm_confidence <= 0:
            effective_llm_weight = 0.0
            redistribute = self.llm_weight
            effective_model_weight = self.model_weight + redistribute * 0.6
            effective_track_weight = self.track_record_weight + redistribute * 0.4
        else:
            effective_llm_weight = self.llm_weight
            effective_model_weight = self.model_weight
            effective_track_weight = self.track_record_weight

        # Weighted combination
        raw_confidence = (
            llm_confidence * effective_llm_weight
            + model_score * effective_model_weight
            + track_score * effective_track_weight
        )

        # Regime adjustment
        regime_adjustment = _UNCERTAIN_REGIMES.get(regime, 0.0)
        adjusted_confidence = max(0.0, min(100.0, raw_confidence + regime_adjustment))

        # Confidence interval: wider when components disagree
        scores = [s for s in [llm_confidence, model_score, track_score] if s > 0]
        if len(scores) >= 2:
            spread = max(scores) - min(scores)
            half_width = max(5.0, spread * 0.4)
        else:
            half_width = 15.0

        ci_low = max(0.0, adjusted_confidence - half_width)
        ci_high = min(100.0, adjusted_confidence + half_width)

        passes = adjusted_confidence >= self.min_confidence

        result = {
            "overall_confidence": round(adjusted_confidence, 1),
            "components": {
                "llm": {"score": round(llm_confidence, 1), "weight": round(effective_llm_weight, 3)},
                "model": {"score": round(model_score, 1), "weight": round(effective_model_weight, 3)},
                "track_record": {"score": round(track_score, 1), "weight": round(effective_track_weight, 3)},
            },
            "confidence_interval": [round(ci_low, 1), round(ci_high, 1)],
            "passes_threshold": passes,
            "regime_adjustment": regime_adjustment,
            "timestamp": datetime.utcnow().isoformat(),
        }

        self._history.append(result)
        logger.info(
            "confidence_computed",
            overall=result["overall_confidence"],
            passes=passes,
            regime=regime,
            regime_adj=regime_adjustment,
        )
        return result

    def should_trade(self, confidence_result: dict) -> tuple[bool, str]:
        """
        Check if confidence passes threshold.
        Returns (should_trade, reason).
        """
        overall = confidence_result["overall_confidence"]
        passes = confidence_result["passes_threshold"]

        if not passes:
            return False, (
                f"Confidence {overall:.1f} below threshold {self.min_confidence:.1f}"
            )

        # Extra caution: if confidence interval lower bound is well below threshold
        ci_low = confidence_result["confidence_interval"][0]
        if ci_low < self.min_confidence * 0.7:
            return False, (
                f"Confidence interval too wide: CI low {ci_low:.1f} "
                f"is below 70% of threshold ({self.min_confidence * 0.7:.1f})"
            )

        return True, f"Confidence {overall:.1f} passes threshold {self.min_confidence:.1f}"

    def _compute_track_record_score(self, model_metrics: dict) -> float:
        """
        Convert model performance metrics into a 0-100 track record score.
        Uses Sharpe, win rate, and drawdown.
        """
        if not model_metrics:
            return 50.0  # Neutral when no metrics available

        sharpe = model_metrics.get("sharpe_ratio", 0.0)
        win_rate = model_metrics.get("win_rate", 0.5)
        max_dd = abs(model_metrics.get("max_drawdown", 0.0))

        # Sharpe contribution: map [-2, 3] to [0, 100], clamped
        sharpe_score = max(0.0, min(100.0, (sharpe + 2.0) * 20.0))

        # Win rate contribution: direct mapping (0-1 -> 0-100)
        win_score = win_rate * 100.0

        # Drawdown penalty: lower drawdown is better
        # 0% DD -> 100, 15%+ DD -> 0
        dd_score = max(0.0, 100.0 - (max_dd / 0.15) * 100.0)

        # Weighted blend of sub-scores
        return sharpe_score * 0.5 + win_score * 0.3 + dd_score * 0.2

    def get_history(self, limit: int = 50) -> list[dict]:
        """Get recent confidence computation history."""
        return self._history[-limit:]
