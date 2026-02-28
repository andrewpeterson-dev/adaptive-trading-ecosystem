"""Tests for paper trading engine constants."""

import sys
from unittest.mock import MagicMock

# Mock heavy deps before importing
sys.modules.setdefault("streamlit", MagicMock())
_mock_settings_obj = MagicMock()
_mock_settings_obj.database_url_sync = "sqlite://"
_mock_settings_obj.max_position_size_pct = 0.10
_mock_settings_obj.max_portfolio_exposure_pct = 0.80
_mock_settings_obj.max_drawdown_pct = 0.15
_mock_settings_obj.stop_loss_pct = 0.03
_mock_settings_obj.max_trades_per_hour = 20
_mock_settings_obj.initial_capital = 100_000.0
_mock_settings_obj.trading_mode.value = "paper"
mock_settings = MagicMock(return_value=_mock_settings_obj)
sys.modules.setdefault("config.settings", MagicMock(get_settings=mock_settings))
sys.modules.setdefault("db.database", MagicMock())
sys.modules.setdefault("db.models", MagicMock())
sys.modules.setdefault("dashboard.auth", MagicMock())
sys.modules.setdefault("dashboard.market_data", MagicMock())

from dashboard.paper_engine import INITIAL_CAPITAL


def test_initial_capital_is_one_million():
    assert INITIAL_CAPITAL == 1_000_000.0
