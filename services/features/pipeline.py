"""
Feature engineering pipeline — main orchestrator.

Transforms raw market data into model-ready FeatureSet objects by
coordinating TechnicalFeatures, SentimentFeatures, and FundamentalFeatures.
"""
from __future__ import annotations

import asyncio
import time

import structlog

from services.features.feature_set import FeatureSet
from services.features.technical import TechnicalFeatures
from services.features.sentiment import SentimentFeatures
from services.features.fundamental import FundamentalFeatures

logger = structlog.get_logger(__name__)

# Cache: symbol -> (timestamp, FeatureSet)
_feature_cache: dict[str, tuple[float, FeatureSet]] = {}
_CACHE_TTL = 60  # 1 minute default cache for computed features


class FeaturePipeline:
    """Transforms raw market data into model-ready features."""

    def __init__(self, cache_ttl: float = _CACHE_TTL) -> None:
        self._sentiment = SentimentFeatures()
        self._fundamental = FundamentalFeatures()
        self._cache_ttl = cache_ttl

    async def compute(
        self,
        symbol: str,
        bars: list[dict] | None = None,
    ) -> FeatureSet:
        """
        Compute all features for a symbol.

        Parameters
        ----------
        symbol : str
            Ticker symbol (e.g. "AAPL").
        bars : list[dict] | None
            OHLCV bars. If None, fetches via MarketDataService.

        Returns
        -------
        FeatureSet with technical, sentiment, and fundamental features.
        """
        symbol = symbol.upper()

        # Check cache
        cached = _feature_cache.get(symbol)
        if cached and (time.time() - cached[0]) < self._cache_ttl:
            logger.debug("feature_cache_hit", symbol=symbol)
            return cached[1]

        # Fetch bars if not provided
        if bars is None:
            bars = await self._fetch_bars(symbol)

        # Compute technical features synchronously (pure numpy, fast)
        technical: dict = {}
        if bars:
            try:
                technical = TechnicalFeatures.compute(bars)
            except Exception as e:
                logger.warning("technical_compute_failed", symbol=symbol, error=str(e))

        # Compute sentiment and fundamental features in parallel (I/O-bound)
        sentiment: dict = {}
        fundamental: dict = {}
        try:
            sent_task = self._sentiment.compute(symbol)
            fund_task = self._fundamental.compute(symbol)
            sentiment, fundamental = await asyncio.gather(
                sent_task, fund_task, return_exceptions=False,
            )
        except Exception as e:
            logger.warning("async_features_failed", symbol=symbol, error=str(e))
            # Ensure we have dicts even on failure
            if not isinstance(sentiment, dict):
                sentiment = {}
            if not isinstance(fundamental, dict):
                fundamental = {}

        feature_set = FeatureSet(
            symbol=symbol,
            timestamp=time.time(),
            technical=technical,
            sentiment=sentiment if isinstance(sentiment, dict) else {},
            fundamental=fundamental if isinstance(fundamental, dict) else {},
        )

        # Cache the result
        _feature_cache[symbol] = (time.time(), feature_set)

        logger.info(
            "features_computed",
            symbol=symbol,
            quality=round(feature_set.quality_score, 2),
            tech_keys=len(technical),
            sent_keys=len(sentiment) if isinstance(sentiment, dict) else 0,
            fund_keys=len(fundamental) if isinstance(fundamental, dict) else 0,
        )

        return feature_set

    async def compute_batch(self, symbols: list[str]) -> dict[str, FeatureSet]:
        """
        Compute features for multiple symbols in parallel.

        Parameters
        ----------
        symbols : list[str]
            List of ticker symbols.

        Returns
        -------
        dict mapping symbol to FeatureSet. Symbols that fail are omitted.
        """
        tasks = [self.compute(s) for s in symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        output: dict[str, FeatureSet] = {}
        for sym, result in zip(symbols, results):
            sym = sym.upper()
            if isinstance(result, FeatureSet):
                output[sym] = result
            elif isinstance(result, BaseException):
                logger.warning("batch_feature_failed", symbol=sym, error=str(result))

        logger.info("batch_features_computed", total=len(symbols), success=len(output))
        return output

    def invalidate_cache(self, symbol: str | None = None) -> None:
        """Clear cached features. If symbol is None, clears all."""
        if symbol:
            _feature_cache.pop(symbol.upper(), None)
        else:
            _feature_cache.clear()

    @staticmethod
    async def _fetch_bars(symbol: str, timeframe: str = "1D", limit: int = 200) -> list[dict]:
        """Fetch bars from MarketDataService."""
        try:
            from data.market_data import market_data
            bars = await market_data.get_bars(symbol, timeframe=timeframe, limit=limit)
            return bars or []
        except Exception as e:
            logger.warning("bar_fetch_failed", symbol=symbol, error=str(e))
            return []
