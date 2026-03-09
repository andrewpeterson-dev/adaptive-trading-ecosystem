"""
Webull trading client — order placement and cancellation.

Safety gates (checked in strict sequence before any SDK call):
  Gate 0 — user_confirmed=True must be passed explicitly.
            Prevents any programmatic / accidental order submission.
  Gate 1 — For real mode only: ALLOW_PROD_TRADING=true AND
            CONFIRM_PROD_TRADING=YES_REAL_TRADES must both be set.
            Re-checked at call time, not just at factory construction.
  Gate 2 — Mode-scoped account must exist.
  Gate 3 — account_id must be in the correct mode's discovered list.
  Gate 4 — (Real mode only) account_id must NOT appear in the paper list.
            Detects and blocks cross-contamination.

Resolved mode and host are always logged before the SDK call.
Secrets (app_key, app_secret) are never logged.
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

import structlog

from .config import WebullMode

if TYPE_CHECKING:
    from .config import _SDKHandle

logger = structlog.get_logger(__name__)


# ── Request / response types ──────────────────────────────────────────────────

@dataclass
class OrderRequest:
    symbol:      str
    side:        str               # "BUY" | "SELL"
    qty:         int
    order_type:  str               # "MKT" | "LMT" | "STP" | "STP_LMT"
    tif:         str = "DAY"       # "DAY" | "GTC" | "IOC" | "OPG"
    limit_price: Optional[float] = None
    stop_price:  Optional[float] = None


@dataclass
class OrderResult:
    success:         bool
    order_id:        str = ""
    client_order_id: str = ""
    mode:            str = ""
    error:           str = ""


# ── Client ────────────────────────────────────────────────────────────────────

class TradingClient:
    """
    Order placement client. Hard-wired to one mode (paper or real) at creation.
    A paper-mode client cannot touch real accounts, and a real-mode client
    cannot touch paper accounts — enforced at every order call.
    """

    def __init__(self, handle: _SDKHandle) -> None:
        self._h = handle

    @property
    def mode(self) -> WebullMode:
        return self._h.env.mode

    # ── Public API ────────────────────────────────────────────────────────

    def place_order(
        self,
        req: OrderRequest,
        *,
        user_confirmed: bool = False,
    ) -> OrderResult:
        """
        Place an order after passing all safety gates.

        Args:
            req:            Order parameters (symbol, side, qty, type, prices, tif).
            user_confirmed: Must be True. The UI submit button is the only
                            legitimate place to set this. Never default True
                            in application code.

        Returns:
            OrderResult with success flag, server order_id, client_order_id,
            resolved mode tag, and error message if any gate blocked.
        """
        # ── Gate 0: explicit user confirmation ───────────────────────────
        if not user_confirmed:
            return OrderResult(
                success=False,
                error=(
                    "BLOCKED: user_confirmed=True is required. "
                    "This gate must never be bypassed programmatically."
                ),
            )

        # ── Gate 1: real-mode env guardrails (re-checked at call time) ───
        if self.mode == WebullMode.REAL:
            env_error = self._check_real_env_gates()
            if env_error:
                return OrderResult(success=False, error=env_error)

        # ── Ensure connection ────────────────────────────────────────────
        if not self._ensure_connected() or not self._h.api:
            return OrderResult(success=False, error="Not connected to Webull")

        acct = self._h.allowed_account
        if not acct:
            return OrderResult(
                success=False,
                error=f"No {self.mode.value} account found — cannot place order",
            )

        paper_ids = self._h._paper_account_ids
        real_ids  = self._h._real_account_ids

        # ── Gate 2 + 3: account must be in the correct mode list ─────────
        if self.mode == WebullMode.PAPER:
            if acct not in paper_ids:
                logger.critical(
                    "SAFETY_VIOLATION_paper_mode_non_paper_account",
                    account=acct,
                    paper_ids=paper_ids,
                )
                return OrderResult(
                    success=False,
                    error="SAFETY BLOCK: account is not a paper account",
                )
        else:
            if acct not in real_ids:
                logger.critical(
                    "SAFETY_VIOLATION_real_mode_non_real_account",
                    account=acct,
                    real_ids=real_ids,
                )
                return OrderResult(
                    success=False,
                    error="SAFETY BLOCK: account is not a real account",
                )

            # ── Gate 4: cross-contamination check ────────────────────────
            if acct in paper_ids:
                logger.critical(
                    "CRITICAL_SAFETY_VIOLATION_cross_contamination",
                    account=acct,
                )
                return OrderResult(
                    success=False,
                    error=(
                        "CRITICAL: cross-contamination detected — "
                        "real account ID appears in paper list. Order blocked."
                    ),
                )

        # ── Log resolved context BEFORE SDK call (no secrets) ────────────
        log_fn = logger.warning if self.mode == WebullMode.REAL else logger.info
        log_fn(
            "order_pre_submission",
            mode=self.mode.value,
            host=self._h.env.trading_host,
            symbol=req.symbol,
            side=req.side,
            qty=req.qty,
            order_type=req.order_type,
            account=acct,
        )

        return self._execute(acct, req)

    def cancel_order(self, client_order_id: str) -> OrderResult:
        """Cancel an open order by client_order_id."""
        if not self._ensure_connected() or not self._h.api:
            return OrderResult(success=False, error="Not connected to Webull")

        acct = self._h.allowed_account
        if not acct:
            return OrderResult(
                success=False,
                error=f"No {self.mode.value} account found",
            )

        try:
            resp = self._h.api.order.cancel_order(acct, client_order_id)
            if resp.status_code == 200:
                logger.info(
                    "order_cancelled",
                    mode=self.mode.value,
                    client_order_id=client_order_id,
                )
                return OrderResult(
                    success=True,
                    client_order_id=client_order_id,
                    mode=self.mode.value,
                )
            return OrderResult(
                success=False,
                error=f"API {resp.status_code}: {resp.text[:200]}",
            )
        except Exception as exc:
            return OrderResult(success=False, error=str(exc))

    # ── Private helpers ───────────────────────────────────────────────────

    def _ensure_connected(self) -> bool:
        if not self._h.connected:
            return self._h.connect().get("success", False)
        return True

    @staticmethod
    def _check_real_env_gates() -> str:
        """
        Returns a human-readable error string if real-trading env vars are wrong,
        or an empty string if all gates pass.
        Re-evaluated at every call so a config change takes effect without restart.
        """
        allow   = os.getenv("ALLOW_PROD_TRADING",   "").strip().lower()
        confirm = os.getenv("CONFIRM_PROD_TRADING", "").strip()

        if allow != "true":
            return "BLOCKED: ALLOW_PROD_TRADING env var must be 'true'"
        if confirm != "YES_REAL_TRADES":
            return "BLOCKED: CONFIRM_PROD_TRADING env var must be 'YES_REAL_TRADES'"
        return ""

    def _execute(self, acct: str, req: OrderRequest) -> OrderResult:
        """Internal: resolve instrument ID and submit the order via SDK."""
        inst_id = self._h.get_instrument_id(req.symbol)
        if not inst_id:
            return OrderResult(
                success=False,
                error=f"Cannot resolve instrument ID for {req.symbol}",
            )

        client_order_id = str(uuid.uuid4())
        kwargs: dict = {
            "account_id":               acct,
            "qty":                      int(req.qty),
            "instrument_id":            inst_id,
            "side":                     req.side.upper(),
            "client_order_id":          client_order_id,
            "order_type":               req.order_type.upper(),
            "extended_hours_trading":   False,
            "tif":                      req.tif.upper(),
        }

        ot = req.order_type.upper()
        if ot == "LMT" and req.limit_price is not None:
            kwargs["limit_price"] = str(req.limit_price)
        if ot in ("STP", "STP_LMT") and req.stop_price is not None:
            kwargs["stop_price"] = str(req.stop_price)

        try:
            resp = self._h.api.order.place_order(**kwargs)
            if resp.status_code == 200:
                result   = resp.json()
                data     = result.get("data", result) if isinstance(result, dict) else result
                order_id = data.get("order_id", data.get("orderId", client_order_id))

                log_fn = logger.warning if self.mode == WebullMode.REAL else logger.info
                log_fn(
                    "order_placed",
                    mode=self.mode.value,
                    symbol=req.symbol,
                    side=req.side,
                    qty=req.qty,
                    order_id=order_id,
                )
                return OrderResult(
                    success=True,
                    order_id=order_id,
                    client_order_id=client_order_id,
                    mode=self.mode.value,
                )

            return OrderResult(
                success=False,
                error=f"API {resp.status_code}: {resp.text[:200]}",
            )

        except Exception as exc:
            return OrderResult(success=False, error=str(exc))
