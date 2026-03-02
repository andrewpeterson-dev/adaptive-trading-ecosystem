"""Tests for the confidence aggregation model."""

import pytest

from intelligence.confidence_model import ConfidenceModel


@pytest.fixture
def model():
    return ConfidenceModel(min_confidence=40.0)


@pytest.fixture
def good_metrics():
    return {"sharpe_ratio": 1.5, "win_rate": 0.65, "max_drawdown": -0.05}


class TestComputeConfidence:
    def test_all_inputs_high(self, model, good_metrics):
        result = model.compute_confidence(
            llm_confidence=80.0,
            model_signal_strength=0.8,
            model_metrics=good_metrics,
            regime="low_vol_bull",
        )
        assert result["overall_confidence"] > 60
        assert result["passes_threshold"] is True
        assert result["regime_adjustment"] == 0.0
        assert "llm" in result["components"]
        assert "model" in result["components"]
        assert "track_record" in result["components"]

    def test_confidence_interval_present(self, model, good_metrics):
        result = model.compute_confidence(
            llm_confidence=80.0,
            model_signal_strength=0.8,
            model_metrics=good_metrics,
            regime="low_vol_bull",
        )
        ci = result["confidence_interval"]
        assert len(ci) == 2
        assert ci[0] <= result["overall_confidence"]
        assert ci[1] >= result["overall_confidence"]

    def test_low_inputs_fail_threshold(self, model):
        result = model.compute_confidence(
            llm_confidence=10.0,
            model_signal_strength=0.1,
            model_metrics={"sharpe_ratio": -1.0, "win_rate": 0.3, "max_drawdown": -0.20},
            regime="high_vol_bear",
        )
        assert result["overall_confidence"] < 40
        assert result["passes_threshold"] is False


class TestMissingLLM:
    def test_zero_llm_redistributes_weight(self, model, good_metrics):
        result = model.compute_confidence(
            llm_confidence=0.0,
            model_signal_strength=0.8,
            model_metrics=good_metrics,
            regime="low_vol_bull",
        )
        assert result["components"]["llm"]["weight"] == 0.0
        assert result["components"]["model"]["weight"] > model.model_weight
        assert result["components"]["track_record"]["weight"] > model.track_record_weight
        # Should still produce a valid confidence
        assert 0 <= result["overall_confidence"] <= 100


class TestRegimeAdjustments:
    def test_bear_penalty(self, model, good_metrics):
        bull = model.compute_confidence(
            llm_confidence=60.0,
            model_signal_strength=0.6,
            model_metrics=good_metrics,
            regime="low_vol_bull",
        )
        bear = model.compute_confidence(
            llm_confidence=60.0,
            model_signal_strength=0.6,
            model_metrics=good_metrics,
            regime="high_vol_bear",
        )
        assert bear["overall_confidence"] < bull["overall_confidence"]
        assert bear["regime_adjustment"] == -10.0

    def test_sideways_penalty(self, model, good_metrics):
        result = model.compute_confidence(
            llm_confidence=60.0,
            model_signal_strength=0.6,
            model_metrics=good_metrics,
            regime="sideways",
        )
        assert result["regime_adjustment"] == -3.0

    def test_high_vol_bull_penalty(self, model, good_metrics):
        result = model.compute_confidence(
            llm_confidence=60.0,
            model_signal_strength=0.6,
            model_metrics=good_metrics,
            regime="high_vol_bull",
        )
        assert result["regime_adjustment"] == -5.0

    def test_no_penalty_low_vol_bull(self, model, good_metrics):
        result = model.compute_confidence(
            llm_confidence=60.0,
            model_signal_strength=0.6,
            model_metrics=good_metrics,
            regime="low_vol_bull",
        )
        assert result["regime_adjustment"] == 0.0


class TestShouldTrade:
    def test_passes_threshold(self, model, good_metrics):
        result = model.compute_confidence(
            llm_confidence=80.0,
            model_signal_strength=0.8,
            model_metrics=good_metrics,
            regime="low_vol_bull",
        )
        should, reason = model.should_trade(result)
        assert should is True
        assert "passes" in reason.lower()

    def test_fails_threshold(self, model):
        result = model.compute_confidence(
            llm_confidence=10.0,
            model_signal_strength=0.1,
            model_metrics={"sharpe_ratio": -1.0, "win_rate": 0.3, "max_drawdown": -0.20},
            regime="high_vol_bear",
        )
        should, reason = model.should_trade(result)
        assert should is False
        assert "below" in reason.lower() or "wide" in reason.lower()

    def test_clamped_to_0_100(self, model):
        result = model.compute_confidence(
            llm_confidence=0.0,
            model_signal_strength=0.0,
            model_metrics={"sharpe_ratio": -5.0, "win_rate": 0.0, "max_drawdown": -0.50},
            regime="high_vol_bear",
        )
        assert result["overall_confidence"] >= 0.0
        assert result["overall_confidence"] <= 100.0
