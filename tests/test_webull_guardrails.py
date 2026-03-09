"""
Unit tests for Webull client host selection and safety guardrails.

No SDK calls are made — all external dependencies are mocked.
Run with: pytest tests/test_webull_guardrails.py -v
"""

import os
from unittest.mock import MagicMock, patch

import pytest


# ── Host selection ────────────────────────────────────────────────────────────

def test_paper_mode_uses_uat_host():
    from data.webull.config import _resolve_env, WebullHosts, WebullMode
    env = _resolve_env(WebullMode.PAPER)
    assert env.trading_host == WebullHosts.UAT_TRADING
    assert env.mode == WebullMode.PAPER


def test_real_mode_uses_prod_host():
    from data.webull.config import _resolve_env, WebullHosts, WebullMode
    env = _resolve_env(WebullMode.REAL)
    assert env.trading_host == WebullHosts.PROD_TRADING
    assert env.mode == WebullMode.REAL


def test_push_hosts_are_always_production_regardless_of_mode():
    from data.webull.config import _resolve_env, WebullHosts, WebullMode
    for mode in WebullMode:
        env = _resolve_env(mode)
        assert env.push_events_host == WebullHosts.PUSH_TRADING_EVENTS
        assert env.push_quotes_host == WebullHosts.PUSH_MARKET_QUOTES


def test_env_describe_is_safe_to_log():
    """describe() must never contain credential values."""
    from data.webull.config import _resolve_env, WebullMode
    env = _resolve_env(WebullMode.PAPER)
    desc = env.describe()
    assert "app_key"    not in desc.lower()
    assert "app_secret" not in desc.lower()
    assert "secret"     not in desc.lower()


# ── Credential resolution ─────────────────────────────────────────────────────

def test_missing_credentials_raises_value_error(monkeypatch):
    from data.webull.config import _load_credentials, WebullMode
    monkeypatch.delenv("WEBULL_APP_KEY",    raising=False)
    monkeypatch.delenv("WEBULL_APP_SECRET", raising=False)
    with pytest.raises(ValueError, match="WEBULL_APP_KEY"):
        _load_credentials(WebullMode.PAPER, None, None)


def test_explicit_credentials_bypass_env():
    from data.webull.config import _load_credentials, WebullMode
    key, secret = _load_credentials(WebullMode.PAPER, "explicit_key", "explicit_secret")
    assert key    == "explicit_key"
    assert secret == "explicit_secret"


def test_real_mode_prefers_real_specific_env_vars(monkeypatch):
    from data.webull.config import _load_credentials, WebullMode
    monkeypatch.setenv("WEBULL_APP_KEY",        "paper_key")
    monkeypatch.setenv("WEBULL_APP_SECRET",     "paper_secret")
    monkeypatch.setenv("WEBULL_APP_KEY_REAL",   "real_key")
    monkeypatch.setenv("WEBULL_APP_SECRET_REAL","real_secret")
    key, secret = _load_credentials(WebullMode.REAL, None, None)
    assert key    == "real_key"
    assert secret == "real_secret"


def test_real_mode_falls_back_to_generic_env_when_no_real_specific(monkeypatch):
    from data.webull.config import _load_credentials, WebullMode
    monkeypatch.setenv("WEBULL_APP_KEY",    "generic_key")
    monkeypatch.setenv("WEBULL_APP_SECRET", "generic_secret")
    monkeypatch.delenv("WEBULL_APP_KEY_REAL",    raising=False)
    monkeypatch.delenv("WEBULL_APP_SECRET_REAL", raising=False)
    key, secret = _load_credentials(WebullMode.REAL, None, None)
    assert key    == "generic_key"
    assert secret == "generic_secret"


# ── Real trading guardrails ───────────────────────────────────────────────────

def test_real_trading_blocked_without_allow_flag(monkeypatch):
    from data.webull.config import _check_real_trading_guardrails
    monkeypatch.setenv("ALLOW_PROD_TRADING",   "false")
    monkeypatch.setenv("CONFIRM_PROD_TRADING", "YES_REAL_TRADES")
    with pytest.raises(RuntimeError, match="ALLOW_PROD_TRADING"):
        _check_real_trading_guardrails()


def test_real_trading_blocked_without_confirm(monkeypatch):
    from data.webull.config import _check_real_trading_guardrails
    monkeypatch.setenv("ALLOW_PROD_TRADING",   "true")
    monkeypatch.setenv("CONFIRM_PROD_TRADING", "wrong")
    with pytest.raises(RuntimeError, match="CONFIRM_PROD_TRADING"):
        _check_real_trading_guardrails()


def test_real_trading_blocked_when_both_missing(monkeypatch):
    from data.webull.config import _check_real_trading_guardrails
    monkeypatch.delenv("ALLOW_PROD_TRADING",   raising=False)
    monkeypatch.delenv("CONFIRM_PROD_TRADING", raising=False)
    with pytest.raises(RuntimeError):
        _check_real_trading_guardrails()


def test_real_trading_passes_with_correct_env(monkeypatch):
    from data.webull.config import _check_real_trading_guardrails
    monkeypatch.setenv("ALLOW_PROD_TRADING",   "true")
    monkeypatch.setenv("CONFIRM_PROD_TRADING", "YES_REAL_TRADES")
    _check_real_trading_guardrails()  # must not raise


# ── Factory ───────────────────────────────────────────────────────────────────

def test_factory_defaults_to_paper_mode():
    from data.webull.config import WebullMode, create_webull_clients
    clients = create_webull_clients(app_key="k", app_secret="s")
    assert clients.mode == WebullMode.PAPER


def test_factory_paper_uses_uat_host():
    from data.webull.config import WebullHosts, create_webull_clients
    clients = create_webull_clients("paper", app_key="k", app_secret="s")
    assert clients.env.trading_host == WebullHosts.UAT_TRADING


def test_factory_real_mode_fails_fast_without_guardrails(monkeypatch):
    from data.webull.config import create_webull_clients
    monkeypatch.delenv("ALLOW_PROD_TRADING",   raising=False)
    monkeypatch.delenv("CONFIRM_PROD_TRADING", raising=False)
    with pytest.raises(RuntimeError):
        create_webull_clients("real", app_key="k", app_secret="s")


def test_factory_real_mode_succeeds_with_guardrails(monkeypatch):
    from data.webull.config import WebullMode, create_webull_clients
    monkeypatch.setenv("ALLOW_PROD_TRADING",   "true")
    monkeypatch.setenv("CONFIRM_PROD_TRADING", "YES_REAL_TRADES")
    clients = create_webull_clients("real", app_key="k", app_secret="s")
    assert clients.mode == WebullMode.REAL


def test_factory_real_mode_uses_prod_host(monkeypatch):
    from data.webull.config import WebullHosts, create_webull_clients
    monkeypatch.setenv("ALLOW_PROD_TRADING",   "true")
    monkeypatch.setenv("CONFIRM_PROD_TRADING", "YES_REAL_TRADES")
    clients = create_webull_clients("real", app_key="k", app_secret="s")
    assert clients.env.trading_host == WebullHosts.PROD_TRADING


# ── TradingClient order guardrails ────────────────────────────────────────────

def _make_trading_client(
    mode: str,
    paper_ids=None,
    real_ids=None,
):
    """Build a TradingClient with a fully mocked SDK handle."""
    from data.webull.config import WebullMode, _SDKHandle, _resolve_env
    from data.webull.trading import TradingClient

    wm = WebullMode(mode)

    handle = MagicMock(spec=_SDKHandle)
    handle.connected           = True
    handle.api                 = MagicMock()
    handle.env                 = _resolve_env(wm)
    handle._paper_account_ids  = paper_ids or ["paper_1"]
    handle._real_account_ids   = real_ids  or ["real_1"]
    handle.allowed_account     = (
        (paper_ids or ["paper_1"])[0] if wm == WebullMode.PAPER
        else (real_ids or ["real_1"])[0]
    )
    handle.get_instrument_id.return_value = "inst_abc"
    return TradingClient(handle)


def test_order_blocked_without_user_confirmed():
    from data.webull.trading import OrderRequest
    client = _make_trading_client("paper")
    req    = OrderRequest(symbol="AAPL", side="BUY", qty=1, order_type="MKT")
    result = client.place_order(req, user_confirmed=False)
    assert not result.success
    assert "user_confirmed" in result.error


def test_paper_order_blocked_when_account_not_in_paper_list():
    from data.webull.trading import OrderRequest
    client = _make_trading_client("paper", paper_ids=["paper_1"])
    client._h.allowed_account = "not_paper_1"
    req    = OrderRequest(symbol="AAPL", side="BUY", qty=1, order_type="MKT")
    result = client.place_order(req, user_confirmed=True)
    assert not result.success
    assert "SAFETY BLOCK" in result.error


def test_real_order_blocked_without_env_flags(monkeypatch):
    from data.webull.trading import OrderRequest
    monkeypatch.delenv("ALLOW_PROD_TRADING",   raising=False)
    monkeypatch.delenv("CONFIRM_PROD_TRADING", raising=False)
    client = _make_trading_client("real")
    req    = OrderRequest(symbol="AAPL", side="BUY", qty=1, order_type="MKT")
    result = client.place_order(req, user_confirmed=True)
    assert not result.success
    assert "BLOCKED" in result.error


def test_real_order_blocked_by_cross_contamination(monkeypatch):
    """Account appearing in both paper and real lists must be blocked."""
    from data.webull.trading import OrderRequest
    monkeypatch.setenv("ALLOW_PROD_TRADING",   "true")
    monkeypatch.setenv("CONFIRM_PROD_TRADING", "YES_REAL_TRADES")
    shared = "shared_acct"
    client = _make_trading_client("real", paper_ids=[shared], real_ids=[shared])
    req    = OrderRequest(symbol="AAPL", side="BUY", qty=1, order_type="MKT")
    result = client.place_order(req, user_confirmed=True)
    assert not result.success
    assert "cross-contamination" in result.error.lower()


def test_paper_order_succeeds_with_mocked_sdk():
    from data.webull.trading import OrderRequest
    client     = _make_trading_client("paper")
    mock_resp  = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"data": {"order_id": "ORD_PAPER_001"}}
    client._h.api.order.place_order.return_value = mock_resp

    req    = OrderRequest(symbol="AAPL", side="BUY", qty=1, order_type="MKT")
    result = client.place_order(req, user_confirmed=True)
    assert result.success
    assert result.order_id == "ORD_PAPER_001"
    assert result.mode == "paper"


def test_real_order_succeeds_with_guardrails_and_mocked_sdk(monkeypatch):
    from data.webull.trading import OrderRequest
    monkeypatch.setenv("ALLOW_PROD_TRADING",   "true")
    monkeypatch.setenv("CONFIRM_PROD_TRADING", "YES_REAL_TRADES")
    client     = _make_trading_client("real")
    mock_resp  = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"data": {"order_id": "ORD_REAL_001"}}
    client._h.api.order.place_order.return_value = mock_resp

    req    = OrderRequest(symbol="SPY", side="SELL", qty=5, order_type="LMT", limit_price=500.0)
    result = client.place_order(req, user_confirmed=True)
    assert result.success
    assert result.order_id == "ORD_REAL_001"
    assert result.mode == "real"


def test_cancel_order_delegates_to_sdk():
    client     = _make_trading_client("paper")
    mock_resp  = MagicMock()
    mock_resp.status_code = 200
    client._h.api.order.cancel_order.return_value = mock_resp

    result = client.cancel_order("client-order-id-123")
    assert result.success
    client._h.api.order.cancel_order.assert_called_once_with("paper_1", "client-order-id-123")
