"""
data.webull — clean Webull integration.

Public API:
  create_webull_clients(mode)  → WebullClients
  WebullClients.market_data    → MarketDataClient
  WebullClients.trading        → TradingClient
  WebullClients.account        → AccountClient

Quick start:
  from data.webull import create_webull_clients

  clients = create_webull_clients("paper")               # safe default
  quote   = clients.market_data.get_quote("SPY")
  acct    = clients.account.get_summary()

  from data.webull.trading import OrderRequest
  result  = clients.trading.place_order(
      OrderRequest(symbol="SPY", side="BUY", qty=1, order_type="MKT"),
      user_confirmed=True,
  )

For real (production) trading you must set:
  ALLOW_PROD_TRADING=true
  CONFIRM_PROD_TRADING=YES_REAL_TRADES
  WEBULL_APP_KEY_REAL=<key>
  WEBULL_APP_SECRET_REAL=<secret>
"""

from .account     import AccountClient, AccountSummary, Order, Position
from .config      import (
    WebullClients,
    WebullEnv,
    WebullHosts,
    WebullMode,
    create_webull_clients,
)
from .market_data import MarketDataClient, Quote
from .trading     import OrderRequest, OrderResult, TradingClient

__all__ = [
    "create_webull_clients",
    "WebullClients",
    "WebullEnv",
    "WebullHosts",
    "WebullMode",
    # Sub-clients
    "MarketDataClient",
    "TradingClient",
    "AccountClient",
    # Types
    "Quote",
    "AccountSummary",
    "Position",
    "Order",
    "OrderRequest",
    "OrderResult",
]
