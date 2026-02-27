"""
Real-time market data stream listener using Alpaca WebSocket.
Pushes bar/quote updates to Redis for consumption by models and execution engine.
"""

import asyncio
import json
from datetime import datetime

import redis.asyncio as aioredis
import structlog
from alpaca.data.live import StockDataStream

from config.settings import get_settings

logger = structlog.get_logger(__name__)

STREAM_CHANNEL = "market:bars"
QUOTE_CHANNEL = "market:quotes"


class MarketStreamListener:
    """Subscribes to Alpaca real-time data and republishes to Redis pub/sub."""

    def __init__(self, symbols: list[str]):
        settings = get_settings()
        self.symbols = symbols
        self.stream = StockDataStream(
            api_key=settings.alpaca_api_key,
            secret_key=settings.alpaca_secret_key,
        )
        self.redis = aioredis.from_url(settings.redis_url)
        self._running = False

    async def _on_bar(self, bar):
        """Handler for incoming bar data."""
        payload = {
            "symbol": bar.symbol,
            "open": float(bar.open),
            "high": float(bar.high),
            "low": float(bar.low),
            "close": float(bar.close),
            "volume": int(bar.volume),
            "timestamp": bar.timestamp.isoformat(),
            "received_at": datetime.utcnow().isoformat(),
        }
        await self.redis.publish(STREAM_CHANNEL, json.dumps(payload))
        logger.debug("bar_published", symbol=bar.symbol)

    async def _on_quote(self, quote):
        """Handler for incoming quote data."""
        payload = {
            "symbol": quote.symbol,
            "bid": float(quote.bid_price),
            "ask": float(quote.ask_price),
            "bid_size": int(quote.bid_size),
            "ask_size": int(quote.ask_size),
            "timestamp": quote.timestamp.isoformat(),
        }
        await self.redis.publish(QUOTE_CHANNEL, json.dumps(payload))

    def start(self):
        """Start the stream listener (blocking). Run in a dedicated thread/process."""
        self._running = True
        self.stream.subscribe_bars(self._on_bar, *self.symbols)
        self.stream.subscribe_quotes(self._on_quote, *self.symbols)
        logger.info("stream_started", symbols=self.symbols)
        self.stream.run()

    async def stop(self):
        """Gracefully shut down the stream."""
        self._running = False
        await self.stream.stop_ws()
        await self.redis.close()
        logger.info("stream_stopped")
