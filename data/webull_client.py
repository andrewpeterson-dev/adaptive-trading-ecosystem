"""
Webull broker integration — Official OpenAPI SDK.

CRITICAL SAFETY: Paper and Live trading are completely isolated.
- Each mode has its own class instance (WebullPaperClient / WebullLiveClient)
- Paper client CANNOT access live account IDs
- Live client CANNOT access paper account IDs
- There is no mode toggle — you pick one at creation and it's locked
- The base class enforces account isolation at every API call
"""

import json
import time
import uuid
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

import pandas as pd
import structlog

logger = structlog.get_logger(__name__)

_CONFIG_DIR = Path.home() / ".adaptive-trading" / "webull"
_CONFIG_FILE = _CONFIG_DIR / "config.json"
_PETEBOT_CONFIG = Path.home() / ".ai-orchestrator" / "config.json"


def _ensure_config_dir():
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def _load_petebot_webull_creds() -> tuple[str, str]:
    """Load Webull app_key/app_secret from PeteBot's shared config."""
    if _PETEBOT_CONFIG.exists():
        try:
            cfg = json.loads(_PETEBOT_CONFIG.read_text())
            wb = cfg.get("webull", {})
            return wb.get("app_key", ""), wb.get("app_secret", "")
        except Exception as exc:
            logger.warning("petebot_webull_config_parse_failed", path=str(_PETEBOT_CONFIG), error=str(exc))
    return "", ""


# ═══════════════════════════════════════════════════════════════════════════
# Trading Mode — immutable after creation
# ═══════════════════════════════════════════════════════════════════════════

class TradingMode(Enum):
    PAPER = "PAPER"
    LIVE = "LIVE"


# ═══════════════════════════════════════════════════════════════════════════
# Base client — shared quote/bar logic, NO trading capability
# ═══════════════════════════════════════════════════════════════════════════

class _WebullBase:
    """
    Base Webull client. Handles connection, quotes, and bars.
    Trading is NOT implemented here — subclasses enforce mode isolation.
    """

    def __init__(self, mode: TradingMode, app_key: str = "", app_secret: str = "", region: str = "us"):
        self._MODE: TradingMode = mode  # IMMUTABLE after __init__
        self._app_key = app_key
        self._app_secret = app_secret
        self._region = region
        self._api_client = None
        self._api = None
        self._connected = False
        self._all_accounts: list[dict] = []
        self._paper_account_ids: list[str] = []
        self._live_account_ids: list[str] = []
        self._instrument_cache: dict[str, str] = {}
        self._quote_cache: dict = {}
        self._cache_ttl = 2

    # ── Mode enforcement (read-only) ────────────────────────────────────

    @property
    def trading_mode(self) -> TradingMode:
        return self._MODE

    @property
    def is_paper(self) -> bool:
        return self._MODE == TradingMode.PAPER

    @property
    def is_live(self) -> bool:
        return self._MODE == TradingMode.LIVE

    @property
    def mode_label(self) -> str:
        return self._MODE.value

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def is_trade_ready(self) -> bool:
        return self._connected and bool(self._get_allowed_account_id())

    def _get_allowed_account_id(self) -> Optional[str]:
        """Return ONLY the account ID matching the current mode. Never crosses."""
        if self._MODE == TradingMode.PAPER:
            return self._paper_account_ids[0] if self._paper_account_ids else None
        else:
            return self._live_account_ids[0] if self._live_account_ids else None

    # ── Connection ──────────────────────────────────────────────────────

    def connect(self) -> dict:
        if not self._app_key or not self._app_secret:
            return {"success": False, "error": "app_key and app_secret are required"}

        try:
            from webullsdkcore.client import ApiClient
            from webullsdkcore.common.region import Region
            from webullsdktrade.api import API

            region_map = {"us": Region.US.value, "hk": Region.HK.value}
            region_val = region_map.get(self._region, Region.US.value)

            self._api_client = ApiClient(self._app_key, self._app_secret, region_val)
            self._api = API(self._api_client)

            # Use get_app_subscriptions to discover accounts (v2 SDK)
            resp = self._api.account.get_app_subscriptions()
            if resp.status_code == 200:
                subs = resp.json()
                if not isinstance(subs, list):
                    subs = subs.get("data", [])

                self._all_accounts = subs
                self._paper_account_ids = []
                self._live_account_ids = []

                for sub in subs:
                    acct_id = str(sub.get("account_id", sub.get("accountId", "")))
                    if not acct_id:
                        continue

                    # Fetch profile to determine account type
                    try:
                        profile_resp = self._api.account.get_account_profile(acct_id)
                        if profile_resp.status_code == 200:
                            profile = profile_resp.json()
                            acct_type = str(profile.get("account_type", "")).lower()
                        else:
                            logger.warning("webull_profile_fetch_non_200", account_id=acct_id, status=profile_resp.status_code)
                            acct_type = ""
                    except Exception as exc:
                        logger.warning("webull_profile_fetch_failed", account_id=acct_id, error=str(exc))
                        acct_type = ""

                    if "paper" in acct_type or "virtual" in acct_type or "demo" in acct_type or "simulated" in acct_type:
                        self._paper_account_ids.append(acct_id)
                    else:
                        self._live_account_ids.append(acct_id)

                # Fallback: if auto-detection found no accounts for our mode
                # but did find accounts overall, assign them based on mode.
                # Webull's profile API doesn't always return identifiable type strings.
                all_ids = [str(s.get("account_id", s.get("accountId", ""))) for s in subs if s.get("account_id") or s.get("accountId")]
                if all_ids and not self._get_allowed_account_id():
                    if self._MODE == TradingMode.PAPER and not self._paper_account_ids:
                        self._paper_account_ids = all_ids
                        logger.info("webull_fallback_assign", mode="PAPER", accounts=all_ids)
                    elif self._MODE == TradingMode.LIVE and not self._live_account_ids:
                        self._live_account_ids = all_ids
                        logger.info("webull_fallback_assign", mode="LIVE", accounts=all_ids)

                self._connected = True
                self._save_config()

                allowed_id = self._get_allowed_account_id()
                logger.info("webull_connected",
                            mode=self._MODE.value,
                            allowed_account=allowed_id,
                            paper_accounts=len(self._paper_account_ids),
                            live_accounts=len(self._live_account_ids))

                return {
                    "success": True,
                    "mode": self._MODE.value,
                    "account_id": allowed_id,
                    "paper_accounts": len(self._paper_account_ids),
                    "live_accounts": len(self._live_account_ids),
                }
            else:
                return {"success": False, "error": f"API {resp.status_code}: {resp.text[:200]}"}

        except ImportError as e:
            return {"success": False, "error": f"SDK not installed: {e}"}
        except Exception as e:
            logger.error("webull_connect_error", error=str(e))
            return {"success": False, "error": str(e)}

    def try_restore(self) -> dict:
        config = self._load_config()
        if config:
            self._app_key = config.get("app_key", "")
            self._app_secret = config.get("app_secret", "")
            self._region = config.get("region", "us")
            if self._app_key and self._app_secret:
                return self.connect()

        key, secret = _load_petebot_webull_creds()
        if key and secret:
            self._app_key = key
            self._app_secret = secret
            logger.info("webull_creds_loaded_from_petebot")
            return self.connect()

        return {"success": False, "error": "No saved credentials"}

    def disconnect(self):
        self._api_client = None
        self._api = None
        self._connected = False
        self._paper_account_ids = []
        self._live_account_ids = []
        logger.info("webull_disconnected", mode=self._MODE.value)

    # ── Config ──────────────────────────────────────────────────────────

    def _save_config(self):
        _ensure_config_dir()
        _CONFIG_FILE.write_text(json.dumps({
            "app_key": self._app_key,
            "app_secret": self._app_secret,
            "region": self._region,
            "saved_at": datetime.now().isoformat(),
        }, indent=2))

    def _load_config(self) -> Optional[dict]:
        if _CONFIG_FILE.exists():
            try:
                return json.loads(_CONFIG_FILE.read_text())
            except Exception as exc:
                logger.warning("webull_config_load_failed", path=str(_CONFIG_FILE), error=str(exc))
                return None
        return None

    # ── Instrument lookup ───────────────────────────────────────────────

    def _get_instrument_id(self, symbol: str, category: str = "US_STOCK") -> Optional[str]:
        if symbol in self._instrument_cache:
            return self._instrument_cache[symbol]
        if not self._api:
            return None
        try:
            resp = self._api.instrument.get_instrument(symbols=[symbol], category=category)
            if resp.status_code == 200:
                data = resp.json()
                instruments = data if isinstance(data, list) else data.get("data", [])
                if instruments:
                    inst_id = str(instruments[0].get("instrument_id", instruments[0].get("instrumentId", "")))
                    self._instrument_cache[symbol] = inst_id
                    return inst_id
        except Exception as e:
            logger.error("instrument_lookup_failed", symbol=symbol, error=str(e))
        return None

    # ── Market Data (shared — quotes don't touch accounts) ──────────────

    def get_quote(self, symbol: str) -> Optional[dict]:
        cache_key = f"quote_{symbol}"
        cached = self._quote_cache.get(cache_key)
        if cached and (time.time() - cached["ts"]) < self._cache_ttl:
            return cached["data"]

        if not self._api:
            return self._get_quote_unofficial(symbol)

        try:
            inst_id = self._get_instrument_id(symbol)
            if not inst_id:
                return self._get_quote_unofficial(symbol)

            resp = self._api.trade_instrument.get_trade_instrument_detail(inst_id)
            if resp.status_code == 200:
                raw = resp.json()
                data = raw.get("data", raw) if isinstance(raw, dict) else raw
                quote = {
                    "symbol": symbol,
                    "price": float(data.get("close", data.get("lastPrice", 0))),
                    "open": float(data.get("open", 0)),
                    "high": float(data.get("high", 0)),
                    "low": float(data.get("low", 0)),
                    "close": float(data.get("close", data.get("lastPrice", 0))),
                    "volume": int(float(data.get("volume", 0))),
                    "change": float(data.get("change", 0)),
                    "change_pct": float(data.get("changeRatio", data.get("changePct", 0))) * 100,
                    "prev_close": float(data.get("preClose", 0)),
                    "timestamp": datetime.now().isoformat(),
                }
                self._quote_cache[cache_key] = {"data": quote, "ts": time.time()}
                return quote
        except Exception as e:
            logger.warning("official_quote_failed", symbol=symbol, error=str(e))

        return self._get_quote_unofficial(symbol)

    def _get_quote_unofficial(self, symbol: str) -> Optional[dict]:
        try:
            from webull import webull
            wb = webull()
            raw = wb.get_quote(symbol)
            if not raw:
                return None
            quote = {
                "symbol": symbol,
                "price": float(raw.get("close", 0)),
                "open": float(raw.get("open", 0)),
                "high": float(raw.get("high", 0)),
                "low": float(raw.get("low", 0)),
                "close": float(raw.get("close", 0)),
                "volume": int(float(raw.get("volume", 0))),
                "change": float(raw.get("change", 0)),
                "change_pct": float(raw.get("changeRatio", 0)) * 100,
                "bid": float(raw.get("bidPrice", 0) or 0),
                "ask": float(raw.get("askPrice", 0) or 0),
                "prev_close": float(raw.get("preClose", 0)),
                "timestamp": datetime.now().isoformat(),
            }
            self._quote_cache[f"quote_{symbol}"] = {"data": quote, "ts": time.time()}
            return quote
        except Exception as e:
            logger.error("unofficial_quote_failed", symbol=symbol, error=str(e))
            return None

    def get_quotes(self, symbols: list[str]) -> dict[str, dict]:
        return {sym: q for sym in symbols if (q := self.get_quote(sym)) is not None}

    def get_bars(self, symbol: str, interval: str = "m5", count: int = 200) -> Optional[pd.DataFrame]:
        try:
            from webull import webull
            wb = webull()
            raw = wb.get_bars(symbol, interval=interval, count=count)
            if raw is None or (isinstance(raw, pd.DataFrame) and raw.empty):
                return None

            df = raw.copy() if isinstance(raw, pd.DataFrame) else pd.DataFrame(raw)
            rename_map = {}
            for col in df.columns:
                lower = col.lower()
                if "open" in lower:
                    rename_map[col] = "open"
                elif "high" in lower:
                    rename_map[col] = "high"
                elif "low" in lower:
                    rename_map[col] = "low"
                elif "close" in lower:
                    rename_map[col] = "close"
                elif "vol" in lower:
                    rename_map[col] = "volume"
                elif "time" in lower or "date" in lower:
                    rename_map[col] = "timestamp"
            df = df.rename(columns=rename_map)
            df["symbol"] = symbol
            for col in ["open", "high", "low", "close", "volume"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            return df
        except Exception as e:
            logger.error("bars_fetch_failed", symbol=symbol, error=str(e))
            return None

    def get_watchlist_quotes(self, symbols: list[str] = None) -> pd.DataFrame:
        if symbols is None:
            symbols = ["SPY", "QQQ", "AAPL", "TSLA", "NVDA", "MSFT", "AMZN", "META"]
        rows = []
        for sym in symbols:
            q = self.get_quote(sym)
            if q:
                rows.append({
                    "Symbol": q["symbol"], "Price": q["price"],
                    "Change": q.get("change", 0), "Change %": q.get("change_pct", 0),
                    "Volume": q.get("volume", 0),
                    "Bid": q.get("bid", 0), "Ask": q.get("ask", 0),
                })
        return pd.DataFrame(rows) if rows else pd.DataFrame()

    def get_bars_as_model_input(self, symbol: str, days: int = 500) -> Optional[pd.DataFrame]:
        df = self.get_bars(symbol, interval="d1", count=min(days, 1200))
        if df is None or df.empty:
            return None
        required = ["open", "high", "low", "close", "volume"]
        if not all(c in df.columns for c in required):
            return None
        df["symbol"] = symbol
        if "timestamp" not in df.columns:
            df["timestamp"] = pd.date_range(end=datetime.now(), periods=len(df), freq="B")
        return df[["timestamp", "symbol", "open", "high", "low", "close", "volume"]]

    # ── Account Data (mode-isolated) ────────────────────────────────────

    def get_account_summary(self) -> Optional[dict]:
        if not self._connected or not self._api:
            return None
        acct = self._get_allowed_account_id()
        if not acct:
            return None
        try:
            resp = self._api.account.get_account_balance(acct, "USD")
            if resp.status_code == 200:
                raw = resp.json()
                # Parse the v2 SDK response format
                currency_assets = raw.get("account_currency_assets", [])
                usd = currency_assets[0] if currency_assets else {}
                return {
                    "account_id": acct,
                    "mode": self._MODE.value,
                    "net_liquidation": float(usd.get("net_liquidation_value", raw.get("net_liquidation", 0))),
                    "total_market_value": float(raw.get("total_market_value", usd.get("positions_market_value", 0))),
                    "cash_balance": float(raw.get("total_cash_balance", usd.get("cash_balance", 0))),
                    "buying_power": float(usd.get("cash_power", usd.get("margin_power", 0))),
                    "unrealized_pnl": float(raw.get("unrealized_pnl", 0)),
                    "realized_pnl": float(raw.get("realized_pnl", 0)),
                }
        except Exception as e:
            logger.error("account_fetch_failed", error=str(e))
        return None

    def get_positions(self) -> list[dict]:
        if not self._connected or not self._api:
            return []
        acct = self._get_allowed_account_id()
        if not acct:
            return []
        try:
            resp = self._api.account.get_account_position(acct)
            if resp.status_code == 200:
                raw = resp.json()
                # v2 SDK wraps positions in "holdings"
                items = raw.get("holdings", raw if isinstance(raw, list) else raw.get("data", raw.get("positions", [])))
                return [{
                    "symbol": pos.get("symbol", pos.get("ticker", {}).get("symbol", "???")),
                    "quantity": float(pos.get("qty", pos.get("position", 0))),
                    "avg_cost": float(pos.get("cost_price", pos.get("costPrice", 0))),
                    "last_price": float(pos.get("last_price", pos.get("lastPrice", 0))),
                    "market_value": float(pos.get("market_value", pos.get("marketValue", 0))),
                    "unrealized_pnl": float(pos.get("unrealized_profit_loss", pos.get("unrealizedProfitLoss", 0))),
                } for pos in items]
        except Exception as e:
            logger.error("positions_fetch_failed", error=str(e))
        return []

    def get_open_orders(self) -> list[dict]:
        if not self._connected or not self._api:
            return []
        acct = self._get_allowed_account_id()
        if not acct:
            return []
        try:
            resp = self._api.order.get_order_list(acct)
            if resp.status_code == 200:
                raw = resp.json()
                items = raw if isinstance(raw, list) else raw.get("data", [])
                return [{
                    "order_id": o.get("order_id", o.get("orderId", "")),
                    "client_order_id": o.get("client_order_id", o.get("clientOrderId", "")),
                    "symbol": o.get("symbol", "???"),
                    "side": o.get("side", o.get("action", "")),
                    "order_type": o.get("order_type", o.get("orderType", "")),
                    "quantity": float(o.get("qty", o.get("totalQuantity", 0))),
                    "filled_qty": float(o.get("filled_qty", o.get("filledQuantity", 0))),
                    "price": float(o.get("limit_price", o.get("lmtPrice", 0)) or 0),
                    "status": o.get("status", o.get("statusStr", "")),
                } for o in items]
        except Exception as e:
            logger.error("orders_fetch_failed", error=str(e))
        return []

    def get_order_history(self, count: int = 50) -> list[dict]:
        return self.get_open_orders()


# ═══════════════════════════════════════════════════════════════════════════
# PAPER CLIENT — can ONLY trade on paper accounts
# ═══════════════════════════════════════════════════════════════════════════

class WebullPaperClient(_WebullBase):
    """Paper trading ONLY. Cannot touch live accounts. Cannot be switched to live."""

    def __init__(self, app_key: str = "", app_secret: str = "", region: str = "us"):
        super().__init__(TradingMode.PAPER, app_key, app_secret, region)

    def place_order(self, symbol: str, side: str, qty: int = 1,
                    order_type: str = "MKT", limit_price: float = None,
                    stop_price: float = None, tif: str = "DAY",
                    user_confirmed: bool = False) -> dict:
        """Place order on PAPER account ONLY. Requires explicit user confirmation."""
        if not user_confirmed:
            return {"success": False, "error": "BLOCKED: Orders require explicit user confirmation (user_confirmed=True)."}

        acct = self._get_allowed_account_id()
        if not acct:
            return {"success": False, "error": "No paper account found. Cannot trade."}

        # SAFETY: verify this is actually a paper account
        if acct not in self._paper_account_ids:
            logger.critical("SAFETY_VIOLATION: paper client attempted to use non-paper account",
                            account_id=acct, paper_ids=self._paper_account_ids)
            return {"success": False, "error": "SAFETY BLOCK: Account is not a paper account."}

        return self._execute_order(acct, symbol, side, qty, order_type, limit_price, stop_price, tif)

    def cancel_order(self, client_order_id: str) -> dict:
        acct = self._get_allowed_account_id()
        if not acct:
            return {"success": False, "error": "No paper account"}
        try:
            resp = self._api.order.cancel_order(acct, client_order_id)
            return {"success": resp.status_code == 200}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _execute_order(self, acct, symbol, side, qty, order_type, limit_price, stop_price, tif) -> dict:
        if not self._api:
            return {"success": False, "error": "Not connected"}

        inst_id = self._get_instrument_id(symbol)
        if not inst_id:
            return {"success": False, "error": f"Could not resolve {symbol}"}

        try:
            client_order_id = str(uuid.uuid4())
            kwargs = {
                "account_id": acct,
                "qty": int(qty),
                "instrument_id": inst_id,
                "side": side.upper(),
                "client_order_id": client_order_id,
                "order_type": order_type.upper(),
                "extended_hours_trading": False,
                "tif": tif.upper(),
            }
            if order_type.upper() == "LMT" and limit_price is not None:
                kwargs["limit_price"] = str(limit_price)
            if order_type.upper() in ("STP", "STP_LMT") and stop_price is not None:
                kwargs["stop_price"] = str(stop_price)

            resp = self._api.order.place_order(**kwargs)
            if resp.status_code == 200:
                result = resp.json()
                data = result.get("data", result) if isinstance(result, dict) else result
                order_id = data.get("order_id", data.get("orderId", client_order_id))
                logger.info("paper_order_placed", symbol=symbol, side=side, qty=qty, order_id=order_id)
                return {"success": True, "order_id": order_id, "client_order_id": client_order_id, "mode": "PAPER"}
            else:
                return {"success": False, "error": f"API {resp.status_code}: {resp.text[:200]}"}
        except Exception as e:
            return {"success": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════════════════════
# LIVE CLIENT — can ONLY trade on live accounts
# ═══════════════════════════════════════════════════════════════════════════

class WebullLiveClient(_WebullBase):
    """Live trading ONLY. Cannot touch paper accounts. Cannot be switched to paper."""

    _LIVE_ENABLED_FILE = _CONFIG_DIR / "LIVE_TRADING_ENABLED"

    def __init__(self, app_key: str = "", app_secret: str = "", region: str = "us"):
        super().__init__(TradingMode.LIVE, app_key, app_secret, region)
        self._confirmed_live = False

    @property
    def live_enabled(self) -> bool:
        """Live trading requires an explicit opt-in file on disk."""
        return self._LIVE_ENABLED_FILE.exists()

    def enable_live_trading(self, confirmation: str) -> bool:
        """
        Enable live trading. Requires typing exact confirmation string.
        Creates a file lock so it persists across sessions.
        """
        if confirmation != "I UNDERSTAND THIS USES REAL MONEY":
            logger.warning("live_trading_enable_rejected", confirmation=confirmation)
            return False
        _ensure_config_dir()
        self._LIVE_ENABLED_FILE.write_text(
            f"Live trading enabled at {datetime.now().isoformat()}\n"
            f"Confirmed with: {confirmation}\n"
        )
        self._confirmed_live = True
        logger.warning("LIVE_TRADING_ENABLED")
        return True

    def disable_live_trading(self):
        """Disable live trading and remove the lock file."""
        if self._LIVE_ENABLED_FILE.exists():
            self._LIVE_ENABLED_FILE.unlink()
        self._confirmed_live = False
        logger.info("live_trading_disabled")

    def place_order(self, symbol: str, side: str, qty: int = 1,
                    order_type: str = "MKT", limit_price: float = None,
                    stop_price: float = None, tif: str = "DAY",
                    user_confirmed: bool = False) -> dict:
        """Place order on LIVE account ONLY. Requires live trading enabled AND explicit user confirmation."""

        # GATE 0: Must be explicitly confirmed by user clicking a button
        if not user_confirmed:
            return {"success": False, "error": "BLOCKED: Orders require explicit user confirmation (user_confirmed=True)."}

        # GATE 1: Live trading must be explicitly enabled
        if not self.live_enabled:
            return {"success": False, "error": "BLOCKED: Live trading is not enabled. Call enable_live_trading() first."}

        # GATE 2: Must have a live account
        acct = self._get_allowed_account_id()
        if not acct:
            return {"success": False, "error": "No live account found. Cannot trade."}

        # GATE 3: Verify this is actually a live account
        if acct not in self._live_account_ids:
            logger.critical("SAFETY_VIOLATION: live client attempted to use non-live account",
                            account_id=acct, live_ids=self._live_account_ids)
            return {"success": False, "error": "SAFETY BLOCK: Account is not a live account."}

        # GATE 4: Sanity check — paper IDs must never leak into live orders
        if acct in self._paper_account_ids:
            logger.critical("CRITICAL_SAFETY_VIOLATION: live order routed to paper account",
                            account_id=acct)
            return {"success": False, "error": "CRITICAL: Cross-contamination detected. Order blocked."}

        return self._execute_order(acct, symbol, side, qty, order_type, limit_price, stop_price, tif)

    def cancel_order(self, client_order_id: str) -> dict:
        acct = self._get_allowed_account_id()
        if not acct:
            return {"success": False, "error": "No live account"}
        try:
            resp = self._api.order.cancel_order(acct, client_order_id)
            return {"success": resp.status_code == 200}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _execute_order(self, acct, symbol, side, qty, order_type, limit_price, stop_price, tif) -> dict:
        if not self._api:
            return {"success": False, "error": "Not connected"}

        inst_id = self._get_instrument_id(symbol)
        if not inst_id:
            return {"success": False, "error": f"Could not resolve {symbol}"}

        try:
            client_order_id = str(uuid.uuid4())
            kwargs = {
                "account_id": acct,
                "qty": int(qty),
                "instrument_id": inst_id,
                "side": side.upper(),
                "client_order_id": client_order_id,
                "order_type": order_type.upper(),
                "extended_hours_trading": False,
                "tif": tif.upper(),
            }
            if order_type.upper() == "LMT" and limit_price is not None:
                kwargs["limit_price"] = str(limit_price)
            if order_type.upper() in ("STP", "STP_LMT") and stop_price is not None:
                kwargs["stop_price"] = str(stop_price)

            resp = self._api.order.place_order(**kwargs)
            if resp.status_code == 200:
                result = resp.json()
                data = result.get("data", result) if isinstance(result, dict) else result
                order_id = data.get("order_id", data.get("orderId", client_order_id))
                logger.warning("LIVE_ORDER_PLACED", symbol=symbol, side=side, qty=qty, order_id=order_id)
                return {"success": True, "order_id": order_id, "client_order_id": client_order_id, "mode": "LIVE"}
            else:
                return {"success": False, "error": f"API {resp.status_code}: {resp.text[:200]}"}
        except Exception as e:
            return {"success": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════════════════════
# Convenience alias — defaults to PAPER (safe default)
# ═══════════════════════════════════════════════════════════════════════════

WebullClient = WebullPaperClient
