"""Tests for paper trading engine constants."""

import sys
from unittest.mock import MagicMock

# Mock heavy deps before importing
sys.modules.setdefault("streamlit", MagicMock())
mock_settings = MagicMock()
mock_settings.return_value.database_url_sync = "sqlite://"
sys.modules.setdefault("config.settings", MagicMock(get_settings=mock_settings))
sys.modules.setdefault("db.database", MagicMock())
sys.modules.setdefault("db.models", MagicMock())
sys.modules.setdefault("dashboard.auth", MagicMock())
sys.modules.setdefault("dashboard.market_data", MagicMock())

from dashboard.paper_engine import INITIAL_CAPITAL


def test_initial_capital_is_one_million():
    assert INITIAL_CAPITAL == 1_000_000.0
