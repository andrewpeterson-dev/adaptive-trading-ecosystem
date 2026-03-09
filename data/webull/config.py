"""
Webull client configuration, host selection, and factory.

Environment variables
─────────────────────
  WEBULL_APP_KEY          — App key (paper / fallback for real)
  WEBULL_APP_SECRET       — App secret (paper / fallback for real)
  WEBULL_APP_KEY_REAL     — App key for real trading (takes priority over WEBULL_APP_KEY)
  WEBULL_APP_SECRET_REAL  — App secret for real trading (takes priority over WEBULL_APP_SECRET)
  ALLOW_PROD_TRADING      — Must be exactly "true" to allow real order placement
  CONFIRM_PROD_TRADING    — Must be exactly "YES_REAL_TRADES" to allow real order placement

Documented hosts
────────────────
  HTTP / Trading:
    Production  → https://api.webull.com/
    UAT / Paper → http://us-openapi-alb.uat.webullbroker.com/

  Push (WebSocket — real-time streaming, HTTP market-data not supported per Webull docs):
    Trading events → events-api.webull.com
    Market quotes  → usquotes-api.webullfintech.com

Usage
─────
  from data.webull import create_webull_clients

  clients = create_webull_clients("paper")          # UAT host, no guardrails
  clients = create_webull_clients("real", ...)      # prod host, env guardrails enforced

  quote  = clients.market_data.get_quote("SPY")
  acct   = clients.account.get_summary()
  result = clients.trading.place_order(req, user_confirmed=True)
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Literal, Optional

import structlog

if TYPE_CHECKING:
    from .account import AccountClient
    from .market_data import MarketDataClient
    from .trading import TradingClient

logger = structlog.get_logger(__name__)


# ── Documented host constants ─────────────────────────────────────────────────

class WebullHosts:
    """Documented Webull API endpoints.

    NOTE: HTTP market-data requests are not supported per Webull docs.
    Real-time data must be consumed via the documented push/WebSocket hosts.
    """
    # REST / Trading
    PROD_TRADING = "https://api.webull.com/"
    UAT_TRADING  = "http://us-openapi-alb.uat.webullbroker.com/"

    # WebSocket push (streaming only)
    PUSH_TRADING_EVENTS = "events-api.webull.com"          # order fills, risk alerts
    PUSH_MARKET_QUOTES  = "usquotes-api.webullfintech.com" # real-time quotes, news push


# ── Trading mode ──────────────────────────────────────────────────────────────

class WebullMode(str, Enum):
    """
    Explicit Webull trading mode.
    Use "paper" (default, safe) unless you truly intend to place real-money orders.
    """
    PAPER = "paper"
    REAL  = "real"


# ── Resolved runtime environment (safe to log — no secrets) ──────────────────

@dataclass(frozen=True)
class WebullEnv:
    mode: WebullMode
    trading_host: str
    push_events_host: str
    push_quotes_host: str

    def describe(self) -> str:
        """Human-readable summary. Safe to log — never contains secrets."""
        return (
            f"mode={self.mode.value} "
            f"trading_host={self.trading_host} "
            f"push_events={self.push_events_host} "
            f"push_quotes={self.push_quotes_host}"
        )


def _resolve_env(mode: WebullMode) -> WebullEnv:
    return WebullEnv(
        mode=mode,
        trading_host=(
            WebullHosts.PROD_TRADING if mode == WebullMode.REAL
            else WebullHosts.UAT_TRADING
        ),
        push_events_host=WebullHosts.PUSH_TRADING_EVENTS,
        push_quotes_host=WebullHosts.PUSH_MARKET_QUOTES,
    )


# ── Credential resolution ─────────────────────────────────────────────────────

def _load_credentials(
    mode: WebullMode,
    app_key: Optional[str],
    app_secret: Optional[str],
) -> tuple[str, str]:
    """
    Resolve app_key / app_secret for the given mode.
    Priority order:
      1. Explicit args (e.g. decrypted from DB per-user)
      2. Mode-specific env vars (WEBULL_APP_KEY_REAL for real mode)
      3. Generic env vars (WEBULL_APP_KEY)

    Raises ValueError with clear message if credentials are missing.
    Never logs key or secret values.
    """
    if mode == WebullMode.REAL:
        key    = app_key    or os.getenv("WEBULL_APP_KEY_REAL")    or os.getenv("WEBULL_APP_KEY",    "")
        secret = app_secret or os.getenv("WEBULL_APP_SECRET_REAL") or os.getenv("WEBULL_APP_SECRET", "")
    else:
        key    = app_key    or os.getenv("WEBULL_APP_KEY",    "")
        secret = app_secret or os.getenv("WEBULL_APP_SECRET", "")

    missing = []
    if not key:
        missing.append("WEBULL_APP_KEY" + ("_REAL" if mode == WebullMode.REAL else ""))
    if not secret:
        missing.append("WEBULL_APP_SECRET" + ("_REAL" if mode == WebullMode.REAL else ""))

    if missing:
        raise ValueError(
            f"Missing required Webull credentials for mode={mode.value}: "
            + ", ".join(missing)
        )

    return key, secret  # type: ignore[return-value]


# ── Real-trading guardrails ───────────────────────────────────────────────────

def _check_real_trading_guardrails() -> None:
    """
    Fail fast if production trading env vars are not explicitly and correctly set.
    Called by the factory before creating real-mode clients.
    Raises RuntimeError listing all unmet conditions.
    """
    allow   = os.getenv("ALLOW_PROD_TRADING",   "").strip().lower()
    confirm = os.getenv("CONFIRM_PROD_TRADING", "").strip()

    errors: list[str] = []
    if allow != "true":
        errors.append(
            f"ALLOW_PROD_TRADING must be 'true' "
            f"(got: {os.getenv('ALLOW_PROD_TRADING', '<not set>')!r})"
        )
    if confirm != "YES_REAL_TRADES":
        errors.append(
            f"CONFIRM_PROD_TRADING must be 'YES_REAL_TRADES' "
            f"(got: {os.getenv('CONFIRM_PROD_TRADING', '<not set>')!r})"
        )

    if errors:
        raise RuntimeError(
            "Real trading is not authorized. Resolve the following:\n"
            + "\n".join(f"  ✗ {e}" for e in errors)
        )


# ── Shared SDK handle (one auth connection, three client views) ───────────────

class _SDKHandle:
    """
    Internal: holds the live SDK connection and account discovery results.
    Shared by reference across MarketDataClient, AccountClient, and TradingClient
    so auth happens once.

    Secrets (app_key, app_secret) are stored but NEVER logged.
    """

    def __init__(
        self,
        *,
        app_key: str,
        app_secret: str,
        region: str,
        env: WebullEnv,
    ) -> None:
        self._app_key    = app_key    # never log
        self._app_secret = app_secret  # never log
        self._region     = region
        self.env         = env

        # SDK objects — populated on first connect()
        self.api_client  = None
        self.api         = None
        self.connected   = False

        # Account ID lists — mode-isolated after discovery
        self._paper_account_ids: list[str] = []
        self._real_account_ids:  list[str] = []

        # Instrument symbol → instrument_id cache
        self._instrument_cache: dict[str, str] = {}

    @property
    def allowed_account(self) -> Optional[str]:
        """Return the first account matching the current mode. Never crosses modes."""
        if self.env.mode == WebullMode.PAPER:
            return self._paper_account_ids[0] if self._paper_account_ids else None
        return self._real_account_ids[0] if self._real_account_ids else None

    def connect(self) -> dict:
        """
        Initialize SDK and discover accounts.
        Called lazily by sub-clients on first use.
        Logs resolved env (no secrets).
        """
        logger.info("webull_connecting", env=self.env.describe())

        try:
            from webullsdkcore.client import ApiClient
            from webullsdkcore.common.region import Region
            from webullsdktrade.api import API
        except ImportError as exc:
            return {"success": False, "error": f"Webull SDK not installed: {exc}"}

        try:
            region_map = {"us": Region.US.value, "hk": Region.HK.value}
            region_val = region_map.get(self._region, Region.US.value)

            # Pass host to ApiClient if the SDK version supports it;
            # older builds fall back to default (prod) host.
            try:
                self.api_client = ApiClient(
                    self._app_key, self._app_secret, region_val,
                    host=self.env.trading_host,
                )
            except TypeError:
                self.api_client = ApiClient(self._app_key, self._app_secret, region_val)

            self.api = API(self.api_client)

            # Discover account subscriptions
            resp = self.api.account.get_app_subscriptions()
            if resp.status_code != 200:
                return {"success": False, "error": f"HTTP {resp.status_code}: {resp.text[:200]}"}

            subs = resp.json()
            if not isinstance(subs, list):
                subs = subs.get("data", [])

            self._paper_account_ids = []
            self._real_account_ids  = []

            for sub in subs:
                acct_id = str(sub.get("account_id", sub.get("accountId", "")))
                if not acct_id:
                    continue

                # Classify by account profile type
                try:
                    pr = self.api.account.get_account_profile(acct_id)
                    acct_type = (
                        pr.json().get("account_type", "").lower()
                        if pr.status_code == 200 else ""
                    )
                except Exception:
                    acct_type = ""

                if any(kw in acct_type for kw in ("paper", "virtual", "demo", "simulated")):
                    self._paper_account_ids.append(acct_id)
                else:
                    self._real_account_ids.append(acct_id)

            # Fallback: if profile classification was ambiguous, assign by mode
            all_ids = [
                str(s.get("account_id", s.get("accountId", "")))
                for s in subs
                if s.get("account_id") or s.get("accountId")
            ]
            if all_ids and not self.allowed_account:
                if self.env.mode == WebullMode.PAPER:
                    self._paper_account_ids = all_ids
                else:
                    self._real_account_ids = all_ids
                logger.info(
                    "webull_account_fallback_assigned",
                    mode=self.env.mode.value,
                    count=len(all_ids),
                )

            self.connected = True
            logger.info(
                "webull_connected",
                mode=self.env.mode.value,
                host=self.env.trading_host,
                allowed_account=self.allowed_account,
                paper_accounts=len(self._paper_account_ids),
                real_accounts=len(self._real_account_ids),
                # app_key and app_secret intentionally omitted
            )
            return {"success": True, "account": self.allowed_account}

        except Exception as exc:
            logger.error("webull_connect_error", mode=self.env.mode.value, error=str(exc))
            return {"success": False, "error": str(exc)}

    def get_instrument_id(self, symbol: str) -> Optional[str]:
        """Resolve symbol → instrument_id with in-memory cache."""
        if symbol in self._instrument_cache:
            return self._instrument_cache[symbol]
        if not self.api:
            return None
        try:
            resp = self.api.instrument.get_instrument(symbols=[symbol], category="US_STOCK")
            if resp.status_code == 200:
                data  = resp.json()
                items = data if isinstance(data, list) else data.get("data", [])
                if items:
                    inst_id = str(
                        items[0].get("instrument_id", items[0].get("instrumentId", ""))
                    )
                    self._instrument_cache[symbol] = inst_id
                    return inst_id
        except Exception as exc:
            logger.error("instrument_lookup_failed", symbol=symbol, error=str(exc))
        return None


# ── Factory return type ───────────────────────────────────────────────────────

@dataclass
class WebullClients:
    """Container returned by create_webull_clients()."""
    market_data: "MarketDataClient"
    trading:     "TradingClient"
    account:     "AccountClient"
    env:         WebullEnv

    @property
    def mode(self) -> WebullMode:
        return self.env.mode


# ── Public factory ────────────────────────────────────────────────────────────

def create_webull_clients(
    mode: Literal["paper", "real"] = "paper",
    *,
    app_key: Optional[str]    = None,
    app_secret: Optional[str] = None,
    region: str = "us",
) -> WebullClients:
    """
    Create all three Webull clients sharing a single authenticated connection.

    Args:
        mode:       "paper" (default, safe) or "real" (real money).
        app_key:    Override env-based credential lookup (e.g. decrypted from DB).
        app_secret: Override env-based credential lookup.
        region:     "us" (default) or "hk".

    Returns:
        WebullClients(market_data, trading, account, env)

    Raises:
        ValueError:     if required credentials are missing.
        RuntimeError:   if mode="real" and ALLOW_PROD_TRADING / CONFIRM_PROD_TRADING
                        are not correctly set.

    Host selection (automatic):
        paper → UAT:  http://us-openapi-alb.uat.webullbroker.com/
        real  → prod: https://api.webull.com/
    """
    webull_mode = WebullMode(mode)

    # Fail fast for real mode — before touching any credentials
    if webull_mode == WebullMode.REAL:
        _check_real_trading_guardrails()

    key, secret = _load_credentials(webull_mode, app_key, app_secret)
    env = _resolve_env(webull_mode)

    logger.info("webull_clients_created", env=env.describe())  # safe: no secrets

    # Lazy imports to avoid circular refs at module load time
    from .account     import AccountClient
    from .market_data import MarketDataClient
    from .trading     import TradingClient

    handle = _SDKHandle(
        app_key=key,
        app_secret=secret,
        region=region,
        env=env,
    )

    return WebullClients(
        market_data=MarketDataClient(handle),
        trading=TradingClient(handle),
        account=AccountClient(handle),
        env=env,
    )
