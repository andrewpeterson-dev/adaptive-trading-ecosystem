# tests/test_performance_tracker.py
import pytest
from services.ai_brain.performance_tracker import compute_model_metrics

def test_compute_model_metrics_basic():
    """Given resolved decisions with P&L, compute win_rate, avg_return, sharpe, drawdown."""
    mock_rows = [
        {"pnl": 10.0, "confidence": 0.8, "decided_at": "2026-03-20T10:00:00"},
        {"pnl": -5.0, "confidence": 0.6, "decided_at": "2026-03-20T11:00:00"},
        {"pnl": 15.0, "confidence": 0.9, "decided_at": "2026-03-20T12:00:00"},
        {"pnl": -3.0, "confidence": 0.5, "decided_at": "2026-03-20T13:00:00"},
        {"pnl": 8.0, "confidence": 0.7, "decided_at": "2026-03-20T14:00:00"},
    ]
    metrics = compute_model_metrics(mock_rows)
    assert metrics["trades_count"] == 5
    assert metrics["win_rate"] == 0.6  # 3 wins out of 5
    assert round(metrics["avg_return"], 2) == 5.0  # (10 - 5 + 15 - 3 + 8) / 5
    assert metrics["max_drawdown"] < 0  # should be negative
    assert "sharpe_ratio" in metrics

def test_compute_model_metrics_empty():
    metrics = compute_model_metrics([])
    assert metrics["trades_count"] == 0
    assert metrics["win_rate"] == 0.0
    assert metrics["sharpe_ratio"] == 0.0

def test_compute_model_metrics_all_wins():
    mock_rows = [
        {"pnl": 10.0, "confidence": 0.8, "decided_at": "2026-03-20T10:00:00"},
        {"pnl": 5.0, "confidence": 0.9, "decided_at": "2026-03-20T11:00:00"},
    ]
    metrics = compute_model_metrics(mock_rows)
    assert metrics["win_rate"] == 1.0
    assert metrics["max_drawdown"] == 0.0
