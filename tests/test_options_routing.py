"""
Unit tests for order routing logic.
All external dependencies are mocked — no DB calls, no broker API calls.
"""
import pytest
from unittest.mock import MagicMock

def _mock_provider(supports_options: bool, supports_paper: bool = True):
    p = MagicMock()
    p.supports_options = supports_options
    p.supports_paper = supports_paper
    p.slug = "tradier" if supports_options else "webull"
    p.name = "Tradier" if supports_options else "Webull"
    return p

def _mock_connection(provider, connection_id: int = 1):
    c = MagicMock()
    c.id = connection_id
    c.provider = provider
    return c

def _mock_settings(active_conn, options_fallback_enabled=False, options_provider_conn=None):
    s = MagicMock()
    s.active_equity_broker_id = active_conn.id if active_conn else None
    s.options_fallback_enabled = options_fallback_enabled
    s.options_provider_connection_id = options_provider_conn.id if options_provider_conn else None
    return s


def test_stock_order_always_routes_to_active_broker():
    from services.order_router import resolve_route, OrderRequest
    webull_conn = _mock_connection(_mock_provider(supports_options=False), connection_id=1)
    tradier_conn = _mock_connection(_mock_provider(supports_options=True), connection_id=2)
    settings = _mock_settings(webull_conn, options_fallback_enabled=True, options_provider_conn=tradier_conn)
    req = OrderRequest(symbol="AAPL", side="BUY", qty=10, instrument_type="stock")
    result = resolve_route(req, active_connection=webull_conn, settings=settings, options_connection=tradier_conn)
    assert result.connection_id == webull_conn.id
    assert result.is_options_sim is False


def test_options_order_blocked_without_fallback():
    from services.order_router import resolve_route, OrderRequest, OptionsNotSupportedError
    webull_conn = _mock_connection(_mock_provider(supports_options=False), connection_id=1)
    settings = _mock_settings(webull_conn, options_fallback_enabled=False)
    req = OrderRequest(symbol="AAPL", side="BUY", qty=1, instrument_type="option",
                       option_type="call", strike=150.0, expiry="2027-01-20")
    with pytest.raises(OptionsNotSupportedError) as exc:
        resolve_route(req, active_connection=webull_conn, settings=settings, options_connection=None)
    assert exc.value.active_broker_name == "Webull"


def test_options_order_routes_to_fallback_when_enabled():
    from services.order_router import resolve_route, OrderRequest
    webull_conn = _mock_connection(_mock_provider(supports_options=False), connection_id=1)
    tradier_conn = _mock_connection(_mock_provider(supports_options=True), connection_id=2)
    settings = _mock_settings(webull_conn, options_fallback_enabled=True, options_provider_conn=tradier_conn)
    req = OrderRequest(symbol="SPY", side="BUY", qty=5, instrument_type="option",
                       option_type="put", strike=500.0, expiry="2027-03-21")
    result = resolve_route(req, active_connection=webull_conn, settings=settings, options_connection=tradier_conn)
    assert result.connection_id == tradier_conn.id
    assert result.is_options_sim is True


def test_options_order_goes_to_broker_when_it_supports_options():
    from services.order_router import resolve_route, OrderRequest
    alpaca_conn = _mock_connection(_mock_provider(supports_options=True), connection_id=3)
    settings = _mock_settings(alpaca_conn, options_fallback_enabled=False)
    req = OrderRequest(symbol="SPY", side="SELL", qty=2, instrument_type="option",
                       option_type="call", strike=450.0, expiry="2027-06-20")
    result = resolve_route(req, active_connection=alpaca_conn, settings=settings, options_connection=None)
    assert result.connection_id == alpaca_conn.id
    assert result.is_options_sim is False


def test_saving_fallback_with_non_options_provider_raises():
    from services.order_router import validate_options_provider
    non_options_provider = _mock_provider(supports_options=False)
    conn = _mock_connection(non_options_provider, connection_id=5)
    with pytest.raises(ValueError, match="does not support options"):
        validate_options_provider(conn)
