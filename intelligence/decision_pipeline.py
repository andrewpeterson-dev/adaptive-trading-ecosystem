"""
Full decision pipeline: integrates LLM analysis, confidence scoring,
ensemble aggregation, and risk validation into a single flow.

Decision flow:
    Signal
    -> LLMAnalyst.analyze()              (advisory input)
    -> ConfidenceModel.compute_confidence()
    -> EnsembleEngine.aggregate_predictions()
    -> RiskManager.validate_signal_quality()
    -> ExecutionEngine.execute_signal()   (only if all gates pass)

The LLM is NEVER in the execution path directly. It is one input
to the confidence model, which feeds the ensemble, which must pass
risk management before any order is placed.
"""

from typing import Optional

import structlog

from intelligence.confidence_model import ConfidenceModel
from intelligence.ensemble_engine import EnsembleEngine
from models.base import Signal
from risk.manager import RiskManager

logger = structlog.get_logger(__name__)


class DecisionPipeline:
    """
    Orchestrates the full signal-to-decision flow.
    Does NOT execute trades -- returns a decision dict that the execution
    engine can act on.
    """

    def __init__(
        self,
        confidence_model: Optional[ConfidenceModel] = None,
        ensemble_engine: Optional[EnsembleEngine] = None,
        risk_manager: Optional[RiskManager] = None,
    ):
        self.confidence = confidence_model or ConfidenceModel()
        self.ensemble = ensemble_engine or EnsembleEngine()
        self.risk = risk_manager or RiskManager()
        self._decision_log: list[dict] = []

    def evaluate(
        self,
        signal: Signal,
        llm_confidence: float,
        model_metrics: dict,
        regime: str,
        all_model_predictions: list[dict],
        model_weight: float = 0.1,
        ensemble_signals: Optional[list[Signal]] = None,
    ) -> dict:
        """
        Run the full decision pipeline for a signal.

        Args:
            signal: the trading Signal to evaluate.
            llm_confidence: 0-100 LLM confidence (0 if LLM unavailable).
            model_metrics: dict with sharpe_ratio, win_rate, max_drawdown, etc.
            regime: regime string from RegimeDetector.
            all_model_predictions: list of prediction dicts for EnsembleEngine.
            model_weight: current weight of the signal's model in the ensemble.
            ensemble_signals: other model signals for consensus check.

        Returns a decision dict:
            {
                "approved": bool,
                "signal": Signal,
                "confidence_result": {...},
                "ensemble_result": {...},
                "risk_result": (bool, str),
                "rejection_stage": None | "confidence" | "ensemble" | "risk",
                "rejection_reason": None | str,
            }
        """
        # Stage 1: Confidence scoring
        confidence_result = self.confidence.compute_confidence(
            llm_confidence=llm_confidence,
            model_signal_strength=signal.strength,
            model_metrics=model_metrics,
            regime=regime,
        )

        should_trade, conf_reason = self.confidence.should_trade(confidence_result)
        if not should_trade:
            decision = self._make_decision(
                approved=False,
                signal=signal,
                confidence_result=confidence_result,
                rejection_stage="confidence",
                rejection_reason=conf_reason,
            )
            self._log_decision(decision)
            return decision

        # Stage 2: Ensemble aggregation
        ensemble_result = self.ensemble.aggregate_predictions(all_model_predictions)

        if ensemble_result["blocked"]:
            decision = self._make_decision(
                approved=False,
                signal=signal,
                confidence_result=confidence_result,
                ensemble_result=ensemble_result,
                rejection_stage="ensemble",
                rejection_reason=ensemble_result["block_reason"],
            )
            self._log_decision(decision)
            return decision

        # Stage 3: Risk validation
        risk_passed, risk_reason = self.risk.validate_signal_quality(
            signal=signal,
            model_metrics=model_metrics,
            model_weight=model_weight,
            ensemble_signals=ensemble_signals,
        )

        if not risk_passed:
            decision = self._make_decision(
                approved=False,
                signal=signal,
                confidence_result=confidence_result,
                ensemble_result=ensemble_result,
                risk_result=(risk_passed, risk_reason),
                rejection_stage="risk",
                rejection_reason=risk_reason,
            )
            self._log_decision(decision)
            return decision

        # All stages passed
        decision = self._make_decision(
            approved=True,
            signal=signal,
            confidence_result=confidence_result,
            ensemble_result=ensemble_result,
            risk_result=(True, "passed"),
        )
        self._log_decision(decision)

        # Log the prediction for accuracy tracking
        self.ensemble.log_prediction(
            model_name=signal.model_name,
            symbol=signal.symbol,
            prediction={
                "direction": signal.direction,
                "confidence": confidence_result["overall_confidence"],
                "strength": signal.strength,
            },
        )

        return decision

    def _make_decision(
        self,
        approved: bool,
        signal: Signal,
        confidence_result: dict,
        ensemble_result: Optional[dict] = None,
        risk_result: Optional[tuple] = None,
        rejection_stage: Optional[str] = None,
        rejection_reason: Optional[str] = None,
    ) -> dict:
        return {
            "approved": approved,
            "signal": signal,
            "confidence_result": confidence_result,
            "ensemble_result": ensemble_result,
            "risk_result": risk_result,
            "rejection_stage": rejection_stage,
            "rejection_reason": rejection_reason,
        }

    def _log_decision(self, decision: dict) -> None:
        log_entry = {
            "approved": decision["approved"],
            "symbol": decision["signal"].symbol,
            "direction": decision["signal"].direction,
            "model": decision["signal"].model_name,
            "overall_confidence": decision["confidence_result"]["overall_confidence"],
            "rejection_stage": decision["rejection_stage"],
            "rejection_reason": decision["rejection_reason"],
        }
        self._decision_log.append(log_entry)

        if decision["approved"]:
            logger.info("decision_approved", **log_entry)
        else:
            logger.info("decision_rejected", **log_entry)

    def get_decision_log(self, limit: int = 100) -> list[dict]:
        return self._decision_log[-limit:]
