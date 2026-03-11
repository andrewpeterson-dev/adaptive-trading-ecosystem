"""Tests for paper trading engine constants."""

from dashboard.paper_engine import INITIAL_CAPITAL


def test_initial_capital_is_one_million():
    assert INITIAL_CAPITAL == 1_000_000.0
