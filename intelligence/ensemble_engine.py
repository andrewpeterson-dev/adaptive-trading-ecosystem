"""
Multi-model prediction aggregation with disagreement detection.

Collects predictions from multiple models (including LLM advisory signals),
detects disagreement, and produces a consensus with a confidence-weighted vote.
Blocks trades when models disagree beyond a threshold.

ADVISORY ONLY -- this engine produces aggregated predictions that must still
pass through RiskManager.validate_signal_quality() before any execution.
"""

from collections import defaultdict
from datetime import datetime
from typing import Optional

import structlog

logger = structlog.get_logger(__name__)


class EnsembleEngine:
    """
    Multi-model prediction aggregation with disagreement detection.
    """

    def __init__(self, disagreement_threshold: float = 0.6):
        """
        Args:
            disagreement_threshold: minimum agreement ratio required to allow
                a trade. If agreement_ratio < this value, the trade is blocked.
        """
        self.disagreement_threshold = disagreement_threshold
        self._prediction_log: list[dict] = []

    def aggregate_predictions(
        self,
        predictions: list[dict],
    ) -> dict:
        """
        Aggregate predictions via weighted confidence.

        Each prediction dict should have:
            model: str -- model name
            direction: str -- "long", "short", or "flat"
            confidence: float -- 0-100
            symbol: str

        Returns dict with consensus_direction, weighted_confidence,
        agreement_ratio, blocked, block_reason, and model_predictions.
        """
        if not predictions:
            return {
                "consensus_direction": "flat",
                "weighted_confidence": 0.0,
                "agreement_ratio": 0.0,
                "blocked": True,
                "block_reason": "No predictions provided",
                "model_predictions": [],
            }

        # Group by symbol -- typically we aggregate per symbol
        by_symbol: dict[str, list[dict]] = defaultdict(list)
        for pred in predictions:
            by_symbol[pred.get("symbol", "unknown")].append(pred)

        # If multiple symbols, aggregate each separately and return the first
        # (caller should call once per symbol in practice)
        all_results = []
        for symbol, preds in by_symbol.items():
            result = self._aggregate_symbol(symbol, preds)
            all_results.append(result)

        # Return first symbol result (most common use case is single-symbol)
        return all_results[0] if len(all_results) == 1 else {
            "consensus_direction": "flat",
            "weighted_confidence": 0.0,
            "agreement_ratio": 0.0,
            "blocked": True,
            "block_reason": "Multi-symbol aggregation -- call per-symbol instead",
            "model_predictions": predictions,
            "per_symbol": all_results,
        }

    def _aggregate_symbol(self, symbol: str, predictions: list[dict]) -> dict:
        """Aggregate predictions for a single symbol."""
        total_confidence = sum(p.get("confidence", 0) for p in predictions)
        if total_confidence <= 0:
            return {
                "consensus_direction": "flat",
                "weighted_confidence": 0.0,
                "agreement_ratio": 0.0,
                "blocked": True,
                "block_reason": "All models report zero confidence",
                "model_predictions": predictions,
            }

        # Weighted vote by confidence
        direction_scores: dict[str, float] = defaultdict(float)
        direction_counts: dict[str, int] = defaultdict(int)

        for pred in predictions:
            direction = pred.get("direction", "flat")
            confidence = pred.get("confidence", 0)
            direction_scores[direction] += confidence
            direction_counts[direction] += 1

        # Find consensus direction (highest weighted score)
        consensus_direction = max(direction_scores, key=direction_scores.get)
        consensus_score = direction_scores[consensus_direction]

        # Weighted confidence: consensus score / total, normalized to 0-100
        weighted_confidence = (consensus_score / total_confidence) * 100.0

        # Agreement ratio: fraction of models agreeing with consensus
        total_models = len(predictions)
        agreeing_models = direction_counts.get(consensus_direction, 0)
        agreement_ratio = agreeing_models / total_models if total_models > 0 else 0.0

        # Block if agreement is below threshold
        blocked = agreement_ratio < self.disagreement_threshold
        block_reason = None
        if blocked:
            block_reason = (
                f"Model disagreement: {agreement_ratio:.0%} agreement "
                f"(need {self.disagreement_threshold:.0%}). "
                f"Votes: {dict(direction_counts)}"
            )

        # If consensus is "flat", also block
        if consensus_direction == "flat":
            blocked = True
            block_reason = block_reason or "Consensus direction is flat"

        result = {
            "consensus_direction": consensus_direction,
            "weighted_confidence": round(weighted_confidence, 1),
            "agreement_ratio": round(agreement_ratio, 3),
            "blocked": blocked,
            "block_reason": block_reason,
            "model_predictions": predictions,
            "symbol": symbol,
        }

        logger.info(
            "ensemble_aggregated",
            symbol=symbol,
            consensus=consensus_direction,
            confidence=round(weighted_confidence, 1),
            agreement=round(agreement_ratio, 3),
            blocked=blocked,
            num_models=total_models,
        )

        return result

    def log_prediction(
        self,
        model_name: str,
        symbol: str,
        prediction: dict,
        actual_outcome: Optional[dict] = None,
    ) -> None:
        """
        Log a prediction for performance tracking.

        Args:
            model_name: name of the predicting model.
            symbol: ticker symbol.
            prediction: dict with direction, confidence, etc.
            actual_outcome: optional dict with actual_direction, actual_return, etc.
                            Can be filled in later via update.
        """
        entry = {
            "model_name": model_name,
            "symbol": symbol,
            "prediction": prediction,
            "actual_outcome": actual_outcome,
            "timestamp": datetime.utcnow().isoformat(),
        }
        self._prediction_log.append(entry)

    def update_outcome(self, index: int, actual_outcome: dict) -> None:
        """Update a logged prediction with the actual outcome."""
        if 0 <= index < len(self._prediction_log):
            self._prediction_log[index]["actual_outcome"] = actual_outcome

    def get_model_accuracy(self, model_name: str, window: int = 50) -> dict:
        """
        Get recent prediction accuracy for a model.

        Returns dict with total_predictions, correct, accuracy, and
        avg_confidence for predictions that have actual_outcome filled in.
        """
        # Filter to this model's predictions with outcomes
        relevant = [
            entry for entry in self._prediction_log[-window * 5:]
            if entry["model_name"] == model_name and entry.get("actual_outcome")
        ][-window:]

        if not relevant:
            return {
                "model_name": model_name,
                "total_predictions": 0,
                "correct": 0,
                "accuracy": 0.0,
                "avg_confidence": 0.0,
            }

        correct = 0
        confidences = []

        for entry in relevant:
            pred_dir = entry["prediction"].get("direction", "flat")
            actual_dir = entry["actual_outcome"].get("actual_direction", "flat")
            if pred_dir == actual_dir:
                correct += 1
            confidences.append(entry["prediction"].get("confidence", 0))

        total = len(relevant)
        return {
            "model_name": model_name,
            "total_predictions": total,
            "correct": correct,
            "accuracy": round(correct / total, 3) if total > 0 else 0.0,
            "avg_confidence": round(sum(confidences) / len(confidences), 1) if confidences else 0.0,
        }

    def get_all_model_accuracies(self, window: int = 50) -> list[dict]:
        """Get accuracy stats for all models that have logged predictions."""
        model_names = set(entry["model_name"] for entry in self._prediction_log)
        return [self.get_model_accuracy(name, window) for name in sorted(model_names)]

    def get_prediction_log(self, limit: int = 100) -> list[dict]:
        """Get recent prediction log entries."""
        return self._prediction_log[-limit:]
