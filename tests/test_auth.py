"""Tests for the authentication module."""

import sys
from unittest.mock import MagicMock

import pytest

# The import chain is:
#   dashboard.auth -> streamlit, config.settings.get_settings, sqlalchemy, db.models
#   db.models -> db.database -> config.settings.get_settings, create_async_engine
#
# All of these execute at module level. To test the pure functions
# (hash_password, verify_password, is_valid_email) we mock the heavy deps
# before importing dashboard.auth.

# 1) Mock streamlit
sys.modules.setdefault("streamlit", MagicMock())

# 2) Mock db.database so db.models can import Base without hitting a real DB
_mock_database = MagicMock()
_mock_database.Base = type("FakeBase", (), {})  # minimal declarative base stand-in
sys.modules["db.database"] = _mock_database

# 3) Mock db.models (User, EmailVerification)
_mock_models = MagicMock()
sys.modules["db.models"] = _mock_models

# 4) Mock config.settings.get_settings so module-level settings = get_settings() works
_mock_settings_obj = MagicMock()
_mock_settings_obj.database_url_sync = "sqlite://"
_mock_settings_obj.smtp_user = ""
_mock_settings_obj.smtp_password = ""
# Risk-management fields (prevent MagicMock leaking into RiskManager)
_mock_settings_obj.max_position_size_pct = 0.10
_mock_settings_obj.max_portfolio_exposure_pct = 0.80
_mock_settings_obj.max_drawdown_pct = 0.15
_mock_settings_obj.stop_loss_pct = 0.03
_mock_settings_obj.max_trades_per_hour = 20
_mock_settings_obj.initial_capital = 100_000.0
_mock_settings_obj.trading_mode.value = "paper"

_mock_settings_mod = MagicMock()
_mock_settings_mod.get_settings = MagicMock(return_value=_mock_settings_obj)
sys.modules.setdefault("config.settings", _mock_settings_mod)

# Now import the auth module -- only bcrypt and re are real
from dashboard.auth import hash_password, verify_password, is_valid_email


def test_hash_password_returns_bcrypt_string():
    hashed = hash_password("testpassword")
    assert hashed.startswith("$2b$")
    assert len(hashed) > 50


def test_verify_password_correct():
    hashed = hash_password("mypassword")
    assert verify_password("mypassword", hashed) is True


def test_verify_password_incorrect():
    hashed = hash_password("mypassword")
    assert verify_password("wrongpassword", hashed) is False


def test_is_valid_email_accepts_valid():
    assert is_valid_email("user@example.com") is True
    assert is_valid_email("first.last@company.co.uk") is True


def test_is_valid_email_rejects_invalid():
    assert is_valid_email("not-an-email") is False
    assert is_valid_email("@missing.com") is False
    assert is_valid_email("user@") is False
    assert is_valid_email("") is False
