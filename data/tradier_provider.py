"""Async Tradier API client for options data (greeks, chains, expirations).

Uses httpx for non-blocking HTTP calls. Supports both sandbox and live
environments based on ``settings.tradier_sandbox``.
"""

from __future__ import annotations

from typing import Optional

import structlog

from config.settings import get_settings

logger = structlog.get_logger(__name__)

_SANDBOX_URL = "https://sandbox.tradier.com/v1/"
_LIVE_URL = "https://api.tradier.com/v1/"


class TradierProvider:
    """Async Tradier API client for options data (greeks, chains)."""

    def __init__(self) -> None:
        settings = get_settings()
        self._api_key: str = settings.tradier_api_key
        self._base_url: str = _SANDBOX_URL if settings.tradier_sandbox else _LIVE_URL

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Accept": "application/json",
        }

    def _available(self) -> bool:
        if not self._api_key:
            logger.debug("tradier_not_configured")
            return False
        return True

    # ── Options Chain ─────────────────────────────────────────────────────────

    async def get_options_chain(
        self, symbol: str, expiry: str | None = None
    ) -> list[dict]:
        """Fetch the options chain for *symbol*.

        Args:
            symbol: Underlying ticker (e.g. ``"AAPL"``).
            expiry: Expiration date in ``YYYY-MM-DD`` format.  If ``None``,
                    the nearest available expiration is used.

        Returns:
            List of option contract dicts, each containing at minimum:
            ``symbol``, ``strike``, ``option_type``, ``bid``, ``ask``,
            ``last``, ``volume``, ``open_interest``, ``expiration_date``.
        """
        if not self._available():
            return []

        if expiry is None:
            expirations = await self.get_expirations(symbol)
            if not expirations:
                logger.warning("tradier_no_expirations", symbol=symbol)
                return []
            expiry = expirations[0]

        try:
            import httpx
            async with httpx.AsyncClient(
                base_url=self._base_url, headers=self._headers, timeout=10
            ) as client:
                resp = await client.get(
                    "markets/options/chains",
                    params={"symbol": symbol.upper(), "expiration": expiry, "greeks": "true"},
                )
                if resp.status_code == 429:
                    logger.warning("tradier_rate_limited", endpoint="chains", symbol=symbol)
                    return []
                if resp.status_code != 200:
                    logger.debug(
                        "tradier_chain_bad_status",
                        symbol=symbol, status=resp.status_code, body=resp.text[:200],
                    )
                    return []
                data = resp.json()

            options = data.get("options", {})
            if not options:
                return []

            raw_options = options.get("option", [])
            # Tradier returns a single dict instead of a list when there's one result
            if isinstance(raw_options, dict):
                raw_options = [raw_options]

            result = []
            for opt in raw_options:
                greeks = opt.get("greeks") or {}
                result.append({
                    "symbol": opt.get("symbol", ""),
                    "underlying": opt.get("underlying", symbol.upper()),
                    "strike": float(opt.get("strike", 0)),
                    "option_type": opt.get("option_type", ""),
                    "expiration_date": opt.get("expiration_date", expiry),
                    "bid": float(opt.get("bid") or 0),
                    "ask": float(opt.get("ask") or 0),
                    "last": float(opt.get("last") or 0),
                    "volume": int(opt.get("volume") or 0),
                    "open_interest": int(opt.get("open_interest") or 0),
                    "greeks": {
                        "delta": float(greeks.get("delta") or 0),
                        "gamma": float(greeks.get("gamma") or 0),
                        "theta": float(greeks.get("theta") or 0),
                        "vega": float(greeks.get("vega") or 0),
                        "rho": float(greeks.get("rho") or 0),
                        "mid_iv": float(greeks.get("mid_iv") or 0),
                    },
                })
            logger.debug("tradier_chain_fetched", symbol=symbol, expiry=expiry, count=len(result))
            return result

        except Exception as e:
            logger.warning("tradier_chain_error", symbol=symbol, error=str(e))
            return []

    # ── Greeks ────────────────────────────────────────────────────────────────

    async def get_greeks(
        self, symbol: str, expiry: str, strike: float, option_type: str
    ) -> dict:
        """Fetch greeks for a specific option contract.

        Args:
            symbol: Underlying ticker.
            expiry: Expiration date ``YYYY-MM-DD``.
            strike: Strike price.
            option_type: ``"call"`` or ``"put"``.

        Returns:
            Dict with ``delta``, ``gamma``, ``theta``, ``vega``, ``rho``,
            ``mid_iv`` (implied volatility), plus the contract ``bid``,
            ``ask``, ``last``.  Empty dict on failure.
        """
        chain = await self.get_options_chain(symbol, expiry=expiry)
        if not chain:
            return {}

        option_type_lower = option_type.lower()
        for opt in chain:
            if (
                abs(opt["strike"] - strike) < 0.01
                and opt["option_type"].lower() == option_type_lower
            ):
                return {
                    **opt.get("greeks", {}),
                    "bid": opt["bid"],
                    "ask": opt["ask"],
                    "last": opt["last"],
                    "volume": opt["volume"],
                    "open_interest": opt["open_interest"],
                }

        logger.debug(
            "tradier_greeks_not_found",
            symbol=symbol, expiry=expiry, strike=strike, option_type=option_type,
        )
        return {}

    # ── Expirations ───────────────────────────────────────────────────────────

    async def get_expirations(self, symbol: str) -> list[str]:
        """Fetch available option expiration dates for *symbol*.

        Returns:
            Sorted list of expiration date strings (``YYYY-MM-DD``).
        """
        if not self._available():
            return []

        try:
            import httpx
            async with httpx.AsyncClient(
                base_url=self._base_url, headers=self._headers, timeout=10
            ) as client:
                resp = await client.get(
                    "markets/options/expirations",
                    params={"symbol": symbol.upper(), "includeAllRoots": "true"},
                )
                if resp.status_code == 429:
                    logger.warning("tradier_rate_limited", endpoint="expirations", symbol=symbol)
                    return []
                if resp.status_code != 200:
                    logger.debug(
                        "tradier_expirations_bad_status",
                        symbol=symbol, status=resp.status_code,
                    )
                    return []
                data = resp.json()

            expirations = data.get("expirations", {})
            if not expirations:
                return []

            dates = expirations.get("date", [])
            # Tradier returns a single string instead of list when there's one result
            if isinstance(dates, str):
                dates = [dates]

            return sorted(dates)

        except Exception as e:
            logger.warning("tradier_expirations_error", symbol=symbol, error=str(e))
            return []
