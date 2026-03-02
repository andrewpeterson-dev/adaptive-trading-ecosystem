"""Tests for portfolio risk analytics (pure math, no external calls)."""

import json
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from risk.analytics import PortfolioRiskAnalyzer


@pytest.fixture
def analyzer():
    return PortfolioRiskAnalyzer()


@pytest.fixture
def daily_returns():
    """50 days of synthetic daily returns with known properties."""
    np.random.seed(42)
    return pd.Series(np.random.normal(0.001, 0.02, 50))


@pytest.fixture
def market_returns():
    np.random.seed(99)
    return pd.Series(np.random.normal(0.0005, 0.015, 50))


@pytest.fixture
def price_history():
    """Price history DataFrame for 3 stocks + SPY over 60 days."""
    np.random.seed(42)
    dates = pd.date_range("2024-01-01", periods=60)
    data = {
        "AAPL": 150 * (1 + np.random.normal(0.001, 0.02, 60)).cumprod(),
        "MSFT": 300 * (1 + np.random.normal(0.0008, 0.018, 60)).cumprod(),
        "SPY": 450 * (1 + np.random.normal(0.0005, 0.012, 60)).cumprod(),
    }
    return pd.DataFrame(data, index=dates)


@pytest.fixture
def positions():
    return [
        {"symbol": "AAPL", "market_value": 50000},
        {"symbol": "MSFT", "market_value": 30000},
    ]


class TestCalculateVaR:
    def test_historical_var(self, analyzer, daily_returns):
        var = analyzer.calculate_var(daily_returns, confidence=0.95, method="historical")
        assert var < 0  # VaR should be negative (loss)
        assert var > -0.10  # Sanity: not absurdly large

    def test_parametric_var(self, analyzer, daily_returns):
        var = analyzer.calculate_var(daily_returns, confidence=0.95, method="parametric")
        assert var < 0
        assert var > -0.10

    def test_var_empty_returns(self, analyzer):
        var = analyzer.calculate_var(pd.Series(dtype=float), confidence=0.95)
        assert var == 0.0

    def test_var_single_return(self, analyzer):
        var = analyzer.calculate_var(pd.Series([0.01]), confidence=0.95)
        assert var == 0.0


class TestCalculateBeta:
    def test_beta_known_correlation(self, analyzer):
        np.random.seed(42)
        market = pd.Series(np.random.normal(0.001, 0.02, 100))
        # Asset = 1.5 * market + noise
        asset = market * 1.5 + pd.Series(np.random.normal(0, 0.005, 100))
        beta = analyzer.calculate_beta(asset, market)
        assert beta > 1.0
        assert beta < 2.0

    def test_beta_empty_series(self, analyzer):
        beta = analyzer.calculate_beta(pd.Series(dtype=float), pd.Series(dtype=float))
        assert beta == 0.0

    def test_beta_short_series(self, analyzer):
        beta = analyzer.calculate_beta(pd.Series([0.01]), pd.Series([0.02]))
        assert beta == 0.0


class TestConcentrationRisk:
    def test_single_position(self, analyzer):
        hhi = analyzer.calculate_concentration_risk([{"market_value": 100000}])
        assert hhi == 1.0  # Single position = max concentration

    def test_equal_positions(self, analyzer):
        positions = [
            {"market_value": 25000},
            {"market_value": 25000},
            {"market_value": 25000},
            {"market_value": 25000},
        ]
        hhi = analyzer.calculate_concentration_risk(positions)
        assert hhi == pytest.approx(0.25, abs=0.01)  # 1/N = 0.25

    def test_empty_positions(self, analyzer):
        hhi = analyzer.calculate_concentration_risk([])
        assert hhi == 0.0

    def test_zero_value_positions(self, analyzer):
        positions = [{"market_value": 0}, {"market_value": 0}]
        hhi = analyzer.calculate_concentration_risk(positions)
        assert hhi == 0.0


class TestGenerateRiskReport:
    def test_report_has_all_fields(self, analyzer, positions, price_history):
        with patch.object(analyzer, "_write_report"):
            report = analyzer.generate_risk_report(positions, price_history)

        required_keys = [
            "timestamp", "portfolio_volatility", "correlation_matrix",
            "betas", "var_95_pct", "var_95_dollar", "expected_shortfall_95",
            "concentration_hhi", "risk_rating", "max_drawdown_current", "warnings",
        ]
        for key in required_keys:
            assert key in report, f"Missing key: {key}"

        assert report["risk_rating"] in ("low", "moderate", "high", "critical")
        assert isinstance(report["warnings"], list)

    def test_report_with_spy_beta(self, analyzer, positions, price_history):
        with patch.object(analyzer, "_write_report"):
            report = analyzer.generate_risk_report(positions, price_history)

        # SPY is in price_history, so betas should be computed
        assert "AAPL" in report["betas"]
        assert "MSFT" in report["betas"]

    def test_report_empty_portfolio(self, analyzer):
        with patch.object(analyzer, "_write_report"):
            report = analyzer.generate_risk_report([], pd.DataFrame())

        assert report["portfolio_volatility"] == 0.0
        assert report["risk_rating"] == "low"
        assert "Empty portfolio" in report["warnings"][0]

    def test_report_concentration_warning(self, analyzer, price_history):
        # Single large position should trigger concentration warning
        positions = [{"symbol": "AAPL", "market_value": 100000}]
        with patch.object(analyzer, "_write_report"):
            report = analyzer.generate_risk_report(positions, price_history)

        assert report["concentration_hhi"] == 1.0
        assert any("concentration" in w.lower() for w in report["warnings"])


class TestExpectedShortfall:
    def test_es_more_negative_than_var(self, analyzer, daily_returns):
        var = analyzer.calculate_var(daily_returns, confidence=0.95)
        es = analyzer.calculate_expected_shortfall(daily_returns, confidence=0.95)
        assert es <= var  # ES is always worse (more negative) than VaR

    def test_es_empty(self, analyzer):
        es = analyzer.calculate_expected_shortfall(pd.Series(dtype=float))
        assert es == 0.0
