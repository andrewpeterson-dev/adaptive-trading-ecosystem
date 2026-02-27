"""Tests for yfinance market data wrapper."""

import sys
from unittest.mock import MagicMock

# Mock streamlit before importing
sys.modules.setdefault("streamlit", MagicMock())

from dashboard.market_data import DEFAULT_WATCHLIST


def test_default_watchlist_includes_crypto():
    assert "BTC-USD" in DEFAULT_WATCHLIST
    assert "ETH-USD" in DEFAULT_WATCHLIST
    assert "SOL-USD" in DEFAULT_WATCHLIST


def test_default_watchlist_includes_stocks():
    assert "SPY" in DEFAULT_WATCHLIST
    assert "QQQ" in DEFAULT_WATCHLIST
    assert "AAPL" in DEFAULT_WATCHLIST


def test_default_watchlist_has_reasonable_size():
    assert len(DEFAULT_WATCHLIST) >= 8
    assert len(DEFAULT_WATCHLIST) <= 20
