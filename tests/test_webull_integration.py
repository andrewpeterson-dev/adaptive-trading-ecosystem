"""
Integration harness for Webull paper mode (UAT host).

Tests make real network calls to the Webull UAT host:
  http://us-openapi-alb.uat.webullbroker.com/

Skipped automatically when WEBULL_APP_KEY / WEBULL_APP_SECRET are absent.

To run:
  WEBULL_APP_KEY=xxx WEBULL_APP_SECRET=yyy pytest tests/test_webull_integration.py -v

What is verified:
  - create_webull_clients("paper") points at UAT host (not prod)
  - SDK connect() succeeds against UAT
  - Quote fetching works for at least one symbol
  - Account reads don't raise (may return None if account not linked)
  - Order placement WITHOUT user_confirmed is blocked
  - Real-mode clients are refused without guardrail env vars
  - MarketDataClient exposes documented push hosts
"""

import os
import pytest

# Skip entire module if credentials are missing
pytestmark = pytest.mark.skipif(
    not (os.getenv("WEBULL_APP_KEY") and os.getenv("WEBULL_APP_SECRET")),
    reason="WEBULL_APP_KEY and WEBULL_APP_SECRET not set — skipping integration tests",
)


@pytest.fixture(scope="module")
def paper_clients():
    from data.webull import create_webull_clients
    from data.webull.config import WebullHosts
    clients = create_webull_clients("paper")
    assert clients.env.trading_host == WebullHosts.UAT_TRADING, (
        "paper mode must connect to UAT, not production"
    )
    return clients


# ── Environment / host assertions ─────────────────────────────────────────────

def test_uat_host_selected(paper_clients):
    from data.webull.config import WebullHosts
    assert paper_clients.env.trading_host == WebullHosts.UAT_TRADING


def test_mode_is_paper(paper_clients):
    from data.webull.config import WebullMode
    assert paper_clients.mode                == WebullMode.PAPER
    assert paper_clients.trading.mode        == WebullMode.PAPER


def test_push_hosts_are_documented(paper_clients):
    from data.webull.config import WebullHosts
    assert paper_clients.market_data.push_events_host == WebullHosts.PUSH_TRADING_EVENTS
    assert paper_clients.market_data.push_quotes_host == WebullHosts.PUSH_MARKET_QUOTES


# ── SDK connectivity ──────────────────────────────────────────────────────────

def test_connect_to_uat(paper_clients):
    result = paper_clients.account._h.connect()
    if "SDK not installed" in result.get("error", ""):
        pytest.skip("Webull SDK not installed in this environment")
    assert result["success"], f"UAT connect failed: {result.get('error')}"


# ── Market data ───────────────────────────────────────────────────────────────

def test_get_quote_returns_price(paper_clients):
    quote = paper_clients.market_data.get_quote("SPY")
    assert quote is not None, "SPY quote returned None"
    assert quote["symbol"] == "SPY"
    assert quote["price"]  >  0, "price must be positive"


def test_get_quotes_returns_dict(paper_clients):
    quotes = paper_clients.market_data.get_quotes(["SPY", "QQQ"])
    assert isinstance(quotes, dict)
    # At least one symbol should resolve
    assert len(quotes) >= 1


def test_get_bars_returns_ohlcv(paper_clients):
    bars = paper_clients.market_data.get_bars("AAPL", interval="d1", count=5)
    if bars is None:
        pytest.skip("Bars unavailable — SDK or market hours issue")
    assert len(bars)        >= 1
    assert "close"  in bars.columns
    assert "volume" in bars.columns


# ── Account reads ─────────────────────────────────────────────────────────────

def test_account_summary_does_not_raise(paper_clients):
    """May return None if UAT account is not linked — must not raise."""
    summary = paper_clients.account.get_summary()
    if summary is not None:
        assert summary["mode"]            == "paper"
        assert "net_liquidation"         in summary
        assert "cash_balance"            in summary


def test_positions_returns_list(paper_clients):
    positions = paper_clients.account.get_positions()
    assert isinstance(positions, list)


def test_open_orders_returns_list(paper_clients):
    orders = paper_clients.account.get_open_orders()
    assert isinstance(orders, list)


# ── Order safety gates ────────────────────────────────────────────────────────

def test_order_blocked_without_user_confirmed(paper_clients):
    from data.webull.trading import OrderRequest
    req    = OrderRequest(symbol="SPY", side="BUY", qty=1, order_type="MKT")
    result = paper_clients.trading.place_order(req, user_confirmed=False)
    assert not result.success
    assert "user_confirmed" in result.error


def test_order_client_has_paper_mode(paper_clients):
    from data.webull.config import WebullMode
    assert paper_clients.trading.mode == WebullMode.PAPER


# ── Real-mode refused without guardrails ──────────────────────────────────────

def test_real_clients_refused_without_guardrail_env_vars(monkeypatch):
    from data.webull import create_webull_clients
    monkeypatch.delenv("ALLOW_PROD_TRADING",   raising=False)
    monkeypatch.delenv("CONFIRM_PROD_TRADING", raising=False)
    with pytest.raises(RuntimeError, match="ALLOW_PROD_TRADING|CONFIRM_PROD_TRADING"):
        create_webull_clients("real", app_key="k", app_secret="s")
