"""
Feature engineering pipeline.
Generates technical indicators and derived features from OHLCV data
for consumption by trading models.
"""

import numpy as np
import pandas as pd
import structlog

logger = structlog.get_logger(__name__)


class FeatureEngineer:
    """Transforms raw OHLCV data into a feature matrix for model training."""

    @staticmethod
    def compute_returns(df: pd.DataFrame, periods: list[int] = None) -> pd.DataFrame:
        """Log returns over multiple periods."""
        periods = periods or [1, 5, 10, 20]
        for p in periods:
            df[f"return_{p}d"] = np.log(df["close"] / df["close"].shift(p))
        return df

    @staticmethod
    def compute_moving_averages(df: pd.DataFrame, windows: list[int] = None) -> pd.DataFrame:
        """Simple and exponential moving averages."""
        windows = windows or [10, 20, 50, 200]
        for w in windows:
            df[f"sma_{w}"] = df["close"].rolling(w).mean()
            df[f"ema_{w}"] = df["close"].ewm(span=w, adjust=False).mean()
        return df

    @staticmethod
    def compute_volatility(df: pd.DataFrame, windows: list[int] = None) -> pd.DataFrame:
        """Rolling volatility (annualized std of log returns)."""
        windows = windows or [10, 20, 60]
        log_ret = np.log(df["close"] / df["close"].shift(1))
        for w in windows:
            df[f"volatility_{w}d"] = log_ret.rolling(w).std() * np.sqrt(252)
        return df

    @staticmethod
    def compute_rsi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        """Relative Strength Index."""
        delta = df["close"].diff()
        gain = delta.where(delta > 0, 0.0).rolling(period).mean()
        loss = (-delta.where(delta < 0, 0.0)).rolling(period).mean()
        rs = gain / loss.replace(0, np.nan)
        df[f"rsi_{period}"] = 100 - (100 / (1 + rs))
        return df

    @staticmethod
    def compute_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
        """MACD line, signal line, and histogram."""
        ema_fast = df["close"].ewm(span=fast, adjust=False).mean()
        ema_slow = df["close"].ewm(span=slow, adjust=False).mean()
        df["macd"] = ema_fast - ema_slow
        df["macd_signal"] = df["macd"].ewm(span=signal, adjust=False).mean()
        df["macd_hist"] = df["macd"] - df["macd_signal"]
        return df

    @staticmethod
    def compute_bollinger_bands(df: pd.DataFrame, window: int = 20, num_std: float = 2.0) -> pd.DataFrame:
        """Bollinger Bands."""
        sma = df["close"].rolling(window).mean()
        std = df["close"].rolling(window).std()
        df["bb_upper"] = sma + num_std * std
        df["bb_lower"] = sma - num_std * std
        df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / sma
        df["bb_position"] = (df["close"] - df["bb_lower"]) / (df["bb_upper"] - df["bb_lower"])
        return df

    @staticmethod
    def compute_atr(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        """Average True Range."""
        high_low = df["high"] - df["low"]
        high_close = (df["high"] - df["close"].shift()).abs()
        low_close = (df["low"] - df["close"].shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df[f"atr_{period}"] = tr.rolling(period).mean()
        return df

    @staticmethod
    def compute_volume_features(df: pd.DataFrame) -> pd.DataFrame:
        """Volume-based features."""
        df["volume_sma_20"] = df["volume"].rolling(20).mean()
        df["volume_ratio"] = df["volume"] / df["volume_sma_20"]
        df["vwap"] = (df["close"] * df["volume"]).cumsum() / df["volume"].cumsum()
        return df

    @staticmethod
    def compute_price_patterns(df: pd.DataFrame) -> pd.DataFrame:
        """Candlestick-derived features."""
        df["body_size"] = (df["close"] - df["open"]).abs() / df["open"]
        df["upper_shadow"] = (df["high"] - df[["close", "open"]].max(axis=1)) / df["open"]
        df["lower_shadow"] = (df[["close", "open"]].min(axis=1) - df["low"]) / df["open"]
        df["is_bullish"] = (df["close"] > df["open"]).astype(int)
        return df

    def build_feature_matrix(self, df: pd.DataFrame, dropna: bool = True) -> pd.DataFrame:
        """Run the full feature pipeline and return a clean feature matrix."""
        df = df.copy()
        df = self.compute_returns(df)
        df = self.compute_moving_averages(df)
        df = self.compute_volatility(df)
        df = self.compute_rsi(df)
        df = self.compute_macd(df)
        df = self.compute_bollinger_bands(df)
        df = self.compute_atr(df)
        df = self.compute_volume_features(df)
        df = self.compute_price_patterns(df)

        if dropna:
            df = df.dropna().reset_index(drop=True)

        logger.info("features_built", shape=df.shape, columns=list(df.columns))
        return df

    @staticmethod
    def get_feature_columns(df: pd.DataFrame) -> list[str]:
        """Return only computed feature columns (exclude OHLCV and metadata)."""
        exclude = {"open", "high", "low", "close", "volume", "symbol", "timestamp", "trade_count", "vwap"}
        return [c for c in df.columns if c not in exclude and not c.startswith("_")]
