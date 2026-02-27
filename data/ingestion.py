"""
Historical and incremental data ingestion via Alpaca Markets API.
Supports rolling-window storage and walk-forward dataset preparation.
"""

from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
import structlog
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

from config.settings import get_settings

logger = structlog.get_logger(__name__)


class DataIngestor:
    """Fetches and stores historical OHLCV data from Alpaca."""

    def __init__(self):
        settings = get_settings()
        self.client = StockHistoricalDataClient(
            api_key=settings.alpaca_api_key,
            secret_key=settings.alpaca_secret_key,
        )
        self._cache: dict[str, pd.DataFrame] = {}

    def fetch_bars(
        self,
        symbols: list[str],
        start: datetime,
        end: Optional[datetime] = None,
        timeframe: TimeFrame = TimeFrame.Day,
    ) -> pd.DataFrame:
        """Fetch OHLCV bars for a list of symbols."""
        end = end or datetime.utcnow()
        request = StockBarsRequest(
            symbol_or_symbols=symbols,
            start=start,
            end=end,
            timeframe=timeframe,
        )
        bars = self.client.get_stock_bars(request)
        df = bars.df.reset_index()
        logger.info("fetched_bars", symbols=symbols, rows=len(df), start=str(start), end=str(end))
        return df

    def fetch_and_cache(
        self,
        symbol: str,
        lookback_days: int = 252,
        timeframe: TimeFrame = TimeFrame.Day,
    ) -> pd.DataFrame:
        """Fetch bars for a single symbol with local caching."""
        cache_key = f"{symbol}_{timeframe}_{lookback_days}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        start = datetime.utcnow() - timedelta(days=lookback_days)
        df = self.fetch_bars([symbol], start=start, timeframe=timeframe)
        if "symbol" in df.columns:
            df = df[df["symbol"] == symbol].copy()
        self._cache[cache_key] = df
        return df

    def prepare_walk_forward_splits(
        self,
        df: pd.DataFrame,
        train_window: int = 200,
        test_window: int = 20,
    ) -> list[tuple[pd.DataFrame, pd.DataFrame]]:
        """
        Generate walk-forward train/test splits.
        Each split uses `train_window` bars for training and `test_window` for testing,
        rolling forward by `test_window` each step.
        """
        splits = []
        total = len(df)
        start = 0

        while start + train_window + test_window <= total:
            train = df.iloc[start : start + train_window].copy()
            test = df.iloc[start + train_window : start + train_window + test_window].copy()
            splits.append((train, test))
            start += test_window

        logger.info("walk_forward_splits", num_splits=len(splits), train_window=train_window, test_window=test_window)
        return splits

    def clear_cache(self):
        self._cache.clear()
