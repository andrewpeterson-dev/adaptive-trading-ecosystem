"""Tests for the ensemble prediction aggregation engine."""

import pytest

from intelligence.ensemble_engine import EnsembleEngine


@pytest.fixture
def engine():
    return EnsembleEngine(disagreement_threshold=0.6)


class TestAggregateUnanimous:
    def test_all_long(self, engine):
        predictions = [
            {"model": "m1", "direction": "long", "confidence": 80, "symbol": "SPY"},
            {"model": "m2", "direction": "long", "confidence": 70, "symbol": "SPY"},
            {"model": "m3", "direction": "long", "confidence": 90, "symbol": "SPY"},
        ]
        result = engine.aggregate_predictions(predictions)
        assert result["consensus_direction"] == "long"
        assert result["agreement_ratio"] == 1.0
        assert result["blocked"] is False
        assert result["block_reason"] is None
        assert result["weighted_confidence"] == 100.0

    def test_all_short(self, engine):
        predictions = [
            {"model": "m1", "direction": "short", "confidence": 60, "symbol": "SPY"},
            {"model": "m2", "direction": "short", "confidence": 55, "symbol": "SPY"},
        ]
        result = engine.aggregate_predictions(predictions)
        assert result["consensus_direction"] == "short"
        assert result["agreement_ratio"] == 1.0
        assert result["blocked"] is False


class TestAggregateSplit:
    def test_split_blocks_trade(self, engine):
        predictions = [
            {"model": "m1", "direction": "long", "confidence": 80, "symbol": "SPY"},
            {"model": "m2", "direction": "short", "confidence": 75, "symbol": "SPY"},
            {"model": "m3", "direction": "flat", "confidence": 70, "symbol": "SPY"},
        ]
        result = engine.aggregate_predictions(predictions)
        assert result["blocked"] is True
        # Each model disagrees: agreement ratio is 1/3 = 0.333
        assert result["agreement_ratio"] < 0.6

    def test_two_vs_one_passes(self, engine):
        predictions = [
            {"model": "m1", "direction": "long", "confidence": 80, "symbol": "SPY"},
            {"model": "m2", "direction": "long", "confidence": 70, "symbol": "SPY"},
            {"model": "m3", "direction": "short", "confidence": 60, "symbol": "SPY"},
        ]
        result = engine.aggregate_predictions(predictions)
        assert result["consensus_direction"] == "long"
        assert result["agreement_ratio"] == pytest.approx(0.667, abs=0.01)
        assert result["blocked"] is False


class TestAggregateEmpty:
    def test_empty_returns_blocked(self, engine):
        result = engine.aggregate_predictions([])
        assert result["consensus_direction"] == "flat"
        assert result["blocked"] is True
        assert result["weighted_confidence"] == 0.0

    def test_zero_confidence_returns_blocked(self, engine):
        predictions = [
            {"model": "m1", "direction": "long", "confidence": 0, "symbol": "SPY"},
            {"model": "m2", "direction": "long", "confidence": 0, "symbol": "SPY"},
        ]
        result = engine.aggregate_predictions(predictions)
        assert result["blocked"] is True


class TestAggregateSingle:
    def test_single_long_prediction(self, engine):
        predictions = [
            {"model": "m1", "direction": "long", "confidence": 85, "symbol": "SPY"},
        ]
        result = engine.aggregate_predictions(predictions)
        assert result["consensus_direction"] == "long"
        assert result["agreement_ratio"] == 1.0
        assert result["blocked"] is False

    def test_single_flat_prediction_blocked(self, engine):
        predictions = [
            {"model": "m1", "direction": "flat", "confidence": 50, "symbol": "SPY"},
        ]
        result = engine.aggregate_predictions(predictions)
        assert result["consensus_direction"] == "flat"
        assert result["blocked"] is True


class TestModelAccuracy:
    def test_accuracy_with_outcomes(self, engine):
        engine.log_prediction("model_a", "AAPL", {"direction": "long", "confidence": 80})
        engine.log_prediction("model_a", "AAPL", {"direction": "long", "confidence": 70})
        engine.log_prediction("model_a", "AAPL", {"direction": "short", "confidence": 60})

        engine.update_outcome(0, {"actual_direction": "long", "actual_return": 0.02})
        engine.update_outcome(1, {"actual_direction": "short", "actual_return": -0.01})
        engine.update_outcome(2, {"actual_direction": "short", "actual_return": -0.03})

        acc = engine.get_model_accuracy("model_a")
        assert acc["total_predictions"] == 3
        assert acc["correct"] == 2  # index 0 and 2
        assert acc["accuracy"] == pytest.approx(0.667, abs=0.01)

    def test_accuracy_no_outcomes(self, engine):
        engine.log_prediction("model_b", "AAPL", {"direction": "long", "confidence": 80})
        acc = engine.get_model_accuracy("model_b")
        assert acc["total_predictions"] == 0
        assert acc["accuracy"] == 0.0

    def test_accuracy_unknown_model(self, engine):
        acc = engine.get_model_accuracy("nonexistent")
        assert acc["total_predictions"] == 0
