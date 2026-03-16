#!/usr/bin/env python3
"""
Seed the api_providers table with known data providers.

Safe to re-run — uses INSERT OR IGNORE logic (skips existing slugs).
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from db.database import get_session
from db.models import ApiProvider, ApiProviderType


PROVIDERS = [
    # ── BROKERAGE ─────────────────────────────────────────────────────────
    dict(
        slug="alpaca",
        name="Alpaca",
        api_type=ApiProviderType.BROKERAGE,
        supports_trading=True,
        supports_paper=True,
        supports_market_data=True,
        supports_stocks=True,
        supports_order_placement=True,
        supports_positions_streaming=False,
        unified_mode=True,
        credential_note=(
            "Set Base URL to https://paper-api.alpaca.markets for paper trading or "
            "https://api.alpaca.markets for live trading. The same key pair works for "
            "both, and also provides market data."
        ),
        credential_fields=[
            {"key": "api_key", "label": "API Key", "secret": False},
            {"key": "api_secret", "label": "API Secret", "secret": True},
            {"key": "base_url", "label": "Base URL", "secret": False},
        ],
        docs_url="https://docs.alpaca.markets/reference/authentication-2",
    ),
    dict(
        slug="interactive_brokers",
        name="Interactive Brokers",
        api_type=ApiProviderType.BROKERAGE,
        supports_trading=True,
        supports_paper=True,
        supports_stocks=True,
        supports_order_placement=True,
        supports_positions_streaming=False,
        credential_fields=[
            {"key": "host", "label": "TWS Host", "secret": False},
            {"key": "port", "label": "TWS Port", "secret": False},
            {"key": "client_id", "label": "Client ID", "secret": False},
        ],
    ),
    dict(
        slug="tradier",
        name="Tradier",
        api_type=ApiProviderType.BROKERAGE,
        supports_trading=True,
        supports_paper=True,
        supports_market_data=True,
        supports_options=True,
        supports_stocks=True,
        supports_order_placement=True,
        supports_positions_streaming=False,
        credential_fields=[
            {"key": "access_token", "label": "Access Token", "secret": True},
        ],
    ),
    dict(
        slug="tradestation",
        name="TradeStation",
        api_type=ApiProviderType.BROKERAGE,
        supports_trading=True,
        supports_paper=True,
        supports_stocks=True,
        supports_order_placement=True,
        supports_positions_streaming=False,
        credential_fields=[
            {"key": "api_key", "label": "API Key", "secret": False},
            {"key": "api_secret", "label": "API Secret", "secret": True},
        ],
    ),
    dict(
        slug="robinhood",
        name="Robinhood",
        api_type=ApiProviderType.BROKERAGE,
        supports_trading=True,
        supports_market_data=True,
        supports_stocks=True,
        supports_order_placement=True,
        supports_positions_streaming=False,
        credential_fields=[
            {"key": "username", "label": "Username", "secret": False},
            {"key": "password", "label": "Password", "secret": True},
        ],
    ),
    dict(
        slug="webull",
        name="Webull",
        api_type=ApiProviderType.BROKERAGE,
        supports_trading=True,
        supports_paper=True,
        supports_market_data=True,
        supports_options=False,
        supports_stocks=True,
        supports_order_placement=True,
        supports_positions_streaming=False,
        unified_mode=True,
        credential_note=(
            "One App Key / App Secret covers paper trading, live trading, and market data quotes. "
            "Trading mode (paper vs live) is selected per trade in the app — not here."
        ),
        credential_fields=[
            {"key": "app_key", "label": "App Key", "secret": False},
            {"key": "app_secret", "label": "App Secret", "secret": True},
        ],
        docs_url="https://developer.webull.com/en/docs",
    ),
    # ── CRYPTO_BROKER ─────────────────────────────────────────────────────
    dict(
        slug="binance",
        name="Binance",
        api_type=ApiProviderType.CRYPTO_BROKER,
        supports_trading=True,
        supports_crypto=True,
        supports_stocks=False,
        supports_order_placement=True,
        supports_positions_streaming=False,
        credential_fields=[
            {"key": "api_key", "label": "API Key", "secret": False},
            {"key": "api_secret", "label": "API Secret", "secret": True},
        ],
    ),
    dict(
        slug="coinbase",
        name="Coinbase Advanced Trade",
        api_type=ApiProviderType.CRYPTO_BROKER,
        supports_trading=True,
        supports_crypto=True,
        supports_stocks=False,
        supports_order_placement=True,
        supports_positions_streaming=False,
        credential_fields=[
            {"key": "api_key", "label": "API Key", "secret": False},
            {"key": "api_secret", "label": "API Secret", "secret": True},
        ],
    ),
    # ── MARKET_DATA ───────────────────────────────────────────────────────
    dict(
        slug="polygon",
        name="Polygon.io",
        api_type=ApiProviderType.MARKET_DATA,
        supports_market_data=True,
        supports_options=True,
        supports_stocks=False,
        supports_order_placement=False,
        supports_positions_streaming=False,
        credential_fields=[
            {"key": "api_key", "label": "API Key", "secret": False},
        ],
    ),
    dict(
        slug="finnhub",
        name="Finnhub",
        api_type=ApiProviderType.MARKET_DATA,
        supports_market_data=True,
        supports_stocks=False,
        supports_order_placement=False,
        supports_positions_streaming=False,
        credential_fields=[
            {"key": "api_key", "label": "API Key", "secret": False},
        ],
    ),
    dict(
        slug="alpha_vantage",
        name="Alpha Vantage",
        api_type=ApiProviderType.MARKET_DATA,
        supports_market_data=True,
        supports_stocks=False,
        supports_order_placement=False,
        supports_positions_streaming=False,
        credential_fields=[
            {"key": "api_key", "label": "API Key", "secret": False},
        ],
    ),
    dict(
        slug="twelve_data",
        name="Twelve Data",
        api_type=ApiProviderType.MARKET_DATA,
        supports_market_data=True,
        supports_stocks=False,
        supports_order_placement=False,
        supports_positions_streaming=False,
        credential_fields=[
            {"key": "api_key", "label": "API Key", "secret": False},
        ],
    ),
    dict(
        slug="iex_cloud",
        name="IEX Cloud",
        api_type=ApiProviderType.MARKET_DATA,
        supports_market_data=True,
        supports_stocks=False,
        supports_order_placement=False,
        supports_positions_streaming=False,
        credential_fields=[
            {"key": "api_key", "label": "API Key", "secret": False},
        ],
    ),
    # ── OPTIONS_DATA ──────────────────────────────────────────────────────
    dict(
        slug="orats",
        name="ORATS",
        api_type=ApiProviderType.OPTIONS_DATA,
        supports_options=True,
        supports_stocks=False,
        supports_order_placement=False,
        supports_positions_streaming=False,
        credential_fields=[
            {"key": "api_key", "label": "API Key", "secret": False},
        ],
    ),
    dict(
        slug="cboe",
        name="CBOE LiveVol",
        api_type=ApiProviderType.OPTIONS_DATA,
        supports_options=True,
        supports_stocks=False,
        supports_order_placement=False,
        supports_positions_streaming=False,
        credential_fields=[
            {"key": "api_key", "label": "API Key", "secret": False},
            {"key": "api_secret", "label": "API Secret", "secret": True},
        ],
    ),
    dict(
        slug="tradier_options",
        name="Tradier Options",
        api_type=ApiProviderType.OPTIONS_DATA,
        supports_options=True,
        supports_market_data=True,
        supports_stocks=False,
        supports_order_placement=False,
        supports_positions_streaming=False,
        credential_fields=[
            {"key": "access_token", "label": "Access Token", "secret": True},
        ],
    ),
    # ── NEWS ──────────────────────────────────────────────────────────────
    dict(
        slug="benzinga",
        name="Benzinga Pro",
        api_type=ApiProviderType.NEWS,
        supports_stocks=False,
        supports_order_placement=False,
        supports_positions_streaming=False,
        credential_fields=[
            {"key": "api_key", "label": "API Key", "secret": False},
        ],
    ),
    dict(
        slug="marketaux",
        name="MarketAux",
        api_type=ApiProviderType.NEWS,
        supports_stocks=False,
        supports_order_placement=False,
        supports_positions_streaming=False,
        credential_fields=[
            {"key": "api_key", "label": "API Key", "secret": False},
        ],
    ),
    dict(
        slug="finnhub_news",
        name="Finnhub News",
        api_type=ApiProviderType.NEWS,
        supports_stocks=False,
        supports_order_placement=False,
        supports_positions_streaming=False,
        credential_fields=[
            {"key": "api_key", "label": "API Key", "secret": False},
        ],
    ),
    # ── FUNDAMENTALS ──────────────────────────────────────────────────────
    dict(
        slug="fmp",
        name="Financial Modeling Prep",
        api_type=ApiProviderType.FUNDAMENTALS,
        supports_stocks=False,
        supports_order_placement=False,
        supports_positions_streaming=False,
        credential_fields=[
            {"key": "api_key", "label": "API Key", "secret": False},
        ],
    ),
    dict(
        slug="intrinio",
        name="Intrinio",
        api_type=ApiProviderType.FUNDAMENTALS,
        supports_stocks=False,
        supports_order_placement=False,
        supports_positions_streaming=False,
        credential_fields=[
            {"key": "api_key", "label": "API Key", "secret": False},
            {"key": "api_secret", "label": "API Secret", "secret": True},
        ],
    ),
    # ── MACRO ─────────────────────────────────────────────────────────────
    dict(
        slug="fred",
        name="FRED (Federal Reserve)",
        api_type=ApiProviderType.MACRO,
        requires_secret=False,
        supports_stocks=False,
        supports_order_placement=False,
        supports_positions_streaming=False,
        credential_fields=[
            {"key": "api_key", "label": "API Key", "secret": False},
        ],
    ),
]


async def seed():
    # Tables are created by init_db() before seed() is called — do not call init_db() here
    async with get_session() as db:
        result = await db.execute(select(ApiProvider))
        existing = {p.slug: p for p in result.scalars().all()}

        added = updated = 0
        for data in PROVIDERS:
            if data["slug"] not in existing:
                db.add(ApiProvider(**data))
                added += 1
            else:
                # Sync fields that may have been added after initial seed
                p = existing[data["slug"]]
                for field in ("unified_mode", "credential_note", "docs_url",
                              "supports_stocks", "supports_order_placement", "supports_positions_streaming"):
                    new_val = data.get(field)
                    if new_val is not None and getattr(p, field, None) != new_val:
                        setattr(p, field, new_val)
                        updated += 1

        await db.commit()

    parts = []
    if added:
        parts.append(f"added {added}")
    if updated:
        parts.append(f"updated {updated} fields")
    print(f"Providers: {', '.join(parts) or 'already up to date'}.")


if __name__ == "__main__":
    asyncio.run(seed())
