"""Tests for the full decision pipeline."""

import os

os.environ.setdefault("ALPACA_API_KEY", "test")
os.environ.setdefault("ALPACA_SECRET_KEY", "test")

from unittest.mock import MagicMock

import pytest

from intelligence.decision_pipeline import DecisionPipeline
from models.base import Signal
from risk.manager import RiskManager


@pytest.fixture
def signal():
    return Signal(symbol="AAPL", direction="long", strength=0.8, model_name="test_model")


@pytest.fixture
def good_metrics():
    return {"sharpe_ratio": 1.5, "win_rate": 0.65, "max_drawdown": -0.05, "num_trades": 100}


@pytest.fixture
def unanimous_predictions():
    return [
        {"model": "m1", "direction": "long", "confidence": 80, "symbol": "AAPL"},
        {"model": "m2", "direction": "long", "confidence": 75, "symbol": "AAPL"},
        {"model": "m3", "direction": "long", "confidence": 70, "symbol": "AAPL"},
    ]


@pytest.fixture
def pipeline():
    return DecisionPipeline()


class TestDecisionPipelineApproval:
    def test_signal_approved_high_confidence_unanimous(
        self, pipeline, signal, good_metrics, unanimous_predictions
    ):
        decision = pipeline.evaluate(
            signal=signal,
            llm_confidence=75.0,
            model_metrics=good_metrics,
            regime="low_vol_bull",
            all_model_predictions=unanimous_predictions,
        )
        assert decision["approved"] is True
        assert decision["rejection_stage"] is None
        assert decision["rejection_reason"] is None
        assert decision["confidence_result"]["passes_threshold"] is True
        assert decision["ensemble_result"]["blocked"] is False

    def test_decision_log_populated(
        self, pipeline, signal, good_metrics, unanimous_predictions
    ):
        pipeline.evaluate(
            signal=signal,
            llm_confidence=75.0,
            model_metrics=good_metrics,
            regime="low_vol_bull",
            all_model_predictions=unanimous_predictions,
        )
        log = pipeline.get_decision_log()
        assert len(log) == 1
        assert log[0]["approved"] is True
        assert log[0]["symbol"] == "AAPL"


class TestDecisionPipelineRejectionConfidence:
    def test_rejected_low_confidence(
        self, pipeline, signal, unanimous_predictions
    ):
        bad_metrics = {"sharpe_ratio": -1.0, "win_rate": 0.3, "max_drawdown": -0.20}
        decision = pipeline.evaluate(
            signal=Signal(symbol="AAPL", direction="long", strength=0.2, model_name="weak"),
            llm_confidence=10.0,
            model_metrics=bad_metrics,
            regime="high_vol_bear",
            all_model_predictions=unanimous_predictions,
        )
        assert decision["approved"] is False
        assert decision["rejection_stage"] == "confidence"
        assert decision["ensemble_result"] is None

    def test_rejected_bear_regime_penalty(self, pipeline, signal):
        borderline_metrics = {"sharpe_ratio": 0.5, "win_rate": 0.5, "max_drawdown": -0.10}
        borderline_signal = Signal(symbol="AAPL", direction="long", strength=0.45, model_name="test")
        decision = pipeline.evaluate(
            signal=borderline_signal,
            llm_confidence=30.0,
            model_metrics=borderline_metrics,
            regime="high_vol_bear",
            all_model_predictions=[
                {"model": "m1", "direction": "long", "confidence": 50, "symbol": "AAPL"},
            ],
        )
        assert decision["approved"] is False
        assert decision["rejection_stage"] == "confidence"


class TestDecisionPipelineRejectionEnsemble:
    def test_rejected_model_disagreement(self, pipeline, signal, good_metrics):
        split_predictions = [
            {"model": "m1", "direction": "long", "confidence": 80, "symbol": "AAPL"},
            {"model": "m2", "direction": "short", "confidence": 75, "symbol": "AAPL"},
            {"model": "m3", "direction": "flat", "confidence": 70, "symbol": "AAPL"},
        ]
        decision = pipeline.evaluate(
            signal=signal,
            llm_confidence=75.0,
            model_metrics=good_metrics,
            regime="low_vol_bull",
            all_model_predictions=split_predictions,
        )
        assert decision["approved"] is False
        assert decision["rejection_stage"] == "ensemble"
        assert "disagreement" in decision["rejection_reason"].lower() or "agreement" in decision["rejection_reason"].lower()


class TestDecisionPipelineRejectionRisk:
    def test_rejected_by_risk_manager(self, signal, good_metrics, unanimous_predictions):
        risk = MagicMock(spec=RiskManager)
        risk.validate_signal_quality.return_value = (False, "Risk limit exceeded")
        pipeline = DecisionPipeline(risk_manager=risk)
        decision = pipeline.evaluate(
            signal=signal,
            llm_confidence=75.0,
            model_metrics=good_metrics,
            regime="low_vol_bull",
            all_model_predictions=unanimous_predictions,
        )
        assert decision["approved"] is False
        assert decision["rejection_stage"] == "risk"
        assert "Risk limit" in decision["rejection_reason"]


class TestDecisionPipelineMissingLLM:
    def test_works_without_llm(self, pipeline, signal, good_metrics, unanimous_predictions):
        decision = pipeline.evaluate(
            signal=signal,
            llm_confidence=0.0,
            model_metrics=good_metrics,
            regime="low_vol_bull",
            all_model_predictions=unanimous_predictions,
        )
        # Should still produce a decision (approved or not) without crashing
        assert "approved" in decision
        assert decision["confidence_result"]["components"]["llm"]["weight"] == 0.0
