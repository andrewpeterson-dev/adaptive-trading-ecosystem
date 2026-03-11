"""Shared options market-data helpers for trading routes."""
from __future__ import annotations

import asyncio
import math
import re
from datetime import datetime
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

_OCC_PATTERN = re.compile(r"^([A-Z.]{1,6})(\d{6})([CP])(\d{8})$")


def _clean_number(value: Any) -> float | int | None:
    if value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(numeric) or math.isinf(numeric):
        return None
    return numeric


def parse_occ_contract_symbol(symbol: str | None) -> dict[str, Any] | None:
    if not symbol:
        return None
    match = _OCC_PATTERN.match(symbol.strip().upper())
    if not match:
        return None

    underlying, expiry_raw, type_raw, strike_raw = match.groups()
    expiry = datetime.strptime(expiry_raw, "%y%m%d").date()
    strike = int(strike_raw) / 1000.0
    return {
        "contract_symbol": symbol.strip().upper(),
        "underlying": underlying,
        "expiration": expiry.isoformat(),
        "strike": strike,
        "option_type": "call" if type_raw == "C" else "put",
    }


def build_occ_contract_symbol(
    underlying: str,
    expiration: str,
    option_type: str,
    strike: float,
) -> str:
    underlying_clean = underlying.strip().upper()
    expiry = datetime.fromisoformat(expiration).strftime("%y%m%d")
    type_char = "C" if option_type.lower() == "call" else "P"
    strike_component = f"{int(round(strike * 1000)):08d}"
    return f"{underlying_clean}{expiry}{type_char}{strike_component}"


async def fetch_options_chain(
    symbol: str,
    expiration: str | None = None,
) -> dict[str, Any]:
    """Fetch a normalized options chain snapshot via yfinance."""
    import yfinance as yf

    symbol = symbol.strip().upper()

    def _fetch() -> dict[str, Any]:
        ticker = yf.Ticker(symbol)
        expirations = list(ticker.options or [])
        if not expirations:
            return {
                "symbol": symbol,
                "expirations": [],
                "selected_expiration": expiration,
                "strikes": [],
                "contracts": [],
            }

        selected_expiration = expiration if expiration in expirations else expirations[0]
        chain = ticker.option_chain(selected_expiration)
        contracts: list[dict[str, Any]] = []
        strikes: set[float] = set()

        def _append_contracts(rows: Any, option_type: str) -> None:
            if rows is None or getattr(rows, "empty", False):
                return
            for _, row in rows.iterrows():
                strike = _clean_number(row.get("strike"))
                if strike is None:
                    continue
                strike_float = float(strike)
                strikes.add(strike_float)
                contract_symbol = str(row.get("contractSymbol") or "").strip().upper()
                contracts.append(
                    {
                        "symbol": contract_symbol
                        or build_occ_contract_symbol(
                            symbol, selected_expiration, option_type, strike_float
                        ),
                        "underlying": symbol,
                        "expiration": selected_expiration,
                        "strike": strike_float,
                        "type": option_type,
                        "bid": _clean_number(row.get("bid")),
                        "ask": _clean_number(row.get("ask")),
                        "last": _clean_number(row.get("lastPrice")),
                        "volume": _clean_number(row.get("volume")),
                        "open_interest": _clean_number(row.get("openInterest")),
                        "implied_volatility": _clean_number(row.get("impliedVolatility")),
                        "delta": None,
                        "gamma": None,
                        "theta": None,
                        "vega": None,
                    }
                )

        _append_contracts(chain.calls, "call")
        _append_contracts(chain.puts, "put")

        return {
            "symbol": symbol,
            "expirations": expirations,
            "selected_expiration": selected_expiration,
            "strikes": sorted(strikes),
            "contracts": contracts,
        }

    return await asyncio.to_thread(_fetch)


async def fetch_option_snapshot(
    *,
    underlying: str,
    expiration: str,
    strike: float,
    option_type: str,
    contract_symbol: str | None = None,
) -> dict[str, Any] | None:
    chain = await fetch_options_chain(underlying, expiration=expiration)
    contracts = chain.get("contracts", [])
    normalized_symbol = (contract_symbol or "").strip().upper()

    for contract in contracts:
        if normalized_symbol and contract.get("symbol") == normalized_symbol:
            return contract
        if (
            float(contract.get("strike", 0)) == float(strike)
            and contract.get("type") == option_type
        ):
            return contract

    logger.warning(
        "option_contract_not_found",
        underlying=underlying,
        expiration=expiration,
        strike=strike,
        option_type=option_type,
        contract_symbol=normalized_symbol or None,
    )
    return None
