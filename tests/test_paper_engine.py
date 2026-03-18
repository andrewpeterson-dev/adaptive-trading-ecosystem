"""Tests for paper trading engine constants."""

from dashboard.paper_engine import INITIAL_CAPITAL


def test_initial_capital_is_one_hundred_thousand():
    assert INITIAL_CAPITAL == 100_000.0
