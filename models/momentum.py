"""
Momentum-based trading model.
Trend-following with adaptive MA crossovers, RSI confirmation, MACD histogram,
and a proper position management system with entry/exit logic.
"""

import pandas as pd
import numpy as np

from models.base import ModelBase, ModelMetrics, Signal


class MomentumModel(ModelBase):
    """
    Trend-following model with selective entries:
    - Enters long on bullish crossover confirmed by RSI + MACD
    - Enters short on bearish crossover confirmed by RSI + MACD
    - Exits when trend weakens (RSI diverges or MA gap narrows)
    - Position sizing by signal strength (conviction-weighted)
    """

    def __init__(
        self,
        name: str = "momentum_v1",
        fast_window: int = 10,
        slow_window: int = 50,
        rsi_period: int = 14,
        rsi_upper: float = 65.0,
        rsi_lower: float = 35.0,
        trend_filter_window: int = 100,
    ):
        super().__init__(name=name)
        self.fast_window = fast_window
        self.slow_window = slow_window
        self.rsi_period = rsi_period
        self.rsi_upper = rsi_upper
        self.rsi_lower = rsi_lower
        self.trend_filter_window = trend_filter_window

    def _compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute all indicators needed for signal generation."""
        d = df.copy()
        d["fast_ma"] = d["close"].rolling(self.fast_window).mean()
        d["slow_ma"] = d["close"].rolling(self.slow_window).mean()
        d["trend_ma"] = d["close"].rolling(self.trend_filter_window).mean()

        # MA spread normalized by price
        d["ma_spread"] = (d["fast_ma"] - d["slow_ma"]) / d["close"]

        # RSI
        delta = d["close"].diff()
        gain = delta.where(delta > 0, 0.0).rolling(self.rsi_period).mean()
        loss = (-delta.where(delta < 0, 0.0)).rolling(self.rsi_period).mean()
        rs = gain / loss.replace(0, np.nan)
        d["rsi"] = 100 - (100 / (1 + rs))

        # MACD
        ema12 = d["close"].ewm(span=12, adjust=False).mean()
        ema26 = d["close"].ewm(span=26, adjust=False).mean()
        d["macd"] = ema12 - ema26
        d["macd_signal"] = d["macd"].ewm(span=9, adjust=False).mean()
        d["macd_hist"] = d["macd"] - d["macd_signal"]

        # Rate of change
        d["roc_10"] = d["close"].pct_change(10)
        d["roc_20"] = d["close"].pct_change(20)

        return d

    def train(self, df: pd.DataFrame, **kwargs) -> None:
        """Grid search over parameters to maximize Sharpe on training data."""
        best_sharpe = -np.inf
        best_params = {"fast": self.fast_window, "slow": self.slow_window}

        # Search around initial params to maintain model diversity
        fast_range = [max(3, self.fast_window - 5), self.fast_window, self.fast_window + 5, self.fast_window + 10]
        slow_range = [max(15, self.slow_window - 15), self.slow_window, self.slow_window + 15, self.slow_window + 30]

        for fast in fast_range:
            for slow in slow_range:
                if fast >= slow - 5:
                    continue
                signals = self._backtest_signals(df, fast, slow)
                rets = self._signal_returns(signals, df)
                if len(rets) < 20:
                    continue
                sharpe = (rets.mean() / rets.std()) * np.sqrt(252) if rets.std() > 0 else 0
                if sharpe > best_sharpe:
                    best_sharpe = sharpe
                    best_params = {"fast": fast, "slow": slow}

        self.fast_window = best_params["fast"]
        self.slow_window = best_params["slow"]
        self.is_trained = True
        self._artifact = {**best_params, "train_sharpe": best_sharpe}

    def predict(self, df: pd.DataFrame) -> list[Signal]:
        """Generate signal from latest data."""
        if len(df) < self.trend_filter_window + 5:
            return []

        d = self._compute_indicators(df)
        i = len(d) - 1
        symbol = df["symbol"].iloc[0] if "symbol" in df.columns else "UNKNOWN"

        spread = d["ma_spread"].iloc[i]
        rsi = d["rsi"].iloc[i]
        macd_h = d["macd_hist"].iloc[i]
        roc = d["roc_10"].iloc[i]
        above_trend = d["close"].iloc[i] > d["trend_ma"].iloc[i]

        signals = []

        # Long: fast > slow, RSI confirms momentum without being overbought, MACD bullish
        if spread > 0 and rsi > self.rsi_lower and rsi < 75 and macd_h > 0 and above_trend:
            # Strength from spread magnitude + RSI momentum + MACD
            strength = min(1.0, abs(spread) * 50 + (rsi - 50) / 100 + min(abs(macd_h) * 5, 0.3))
            strength = max(0.1, strength)
            signals.append(Signal(symbol=symbol, direction="long", strength=round(strength, 3), model_name=self.name))

        # Short: fast < slow, RSI confirms weakness, MACD bearish, below trend
        elif spread < 0 and rsi < self.rsi_upper and rsi > 25 and macd_h < 0 and not above_trend:
            strength = min(1.0, abs(spread) * 50 + (50 - rsi) / 100 + min(abs(macd_h) * 5, 0.3))
            strength = max(0.1, strength)
            signals.append(Signal(symbol=symbol, direction="short", strength=round(strength, 3), model_name=self.name))

        # Flat: conflicting signals or no clear trend
        elif abs(spread) < 0.001 or (40 < rsi < 60 and abs(macd_h) < 0.5):
            signals.append(Signal(symbol=symbol, direction="flat", strength=0.0, model_name=self.name))

        return signals

    def evaluate(self, df: pd.DataFrame) -> ModelMetrics:
        """Evaluate on held-out data."""
        signals = self._backtest_signals(df, self.fast_window, self.slow_window)
        rets = self._signal_returns(signals, df)
        return self.update_metrics(rets)

    def _backtest_signals(self, df: pd.DataFrame, fast: int, slow: int) -> pd.Series:
        """Generate position signals with entry/exit logic for backtesting."""
        fast_ma = df["close"].rolling(fast).mean()
        slow_ma = df["close"].rolling(slow).mean()
        spread = (fast_ma - slow_ma) / df["close"]

        # Adaptive spread threshold: slower MAs produce smaller spreads
        spread_threshold = 0.001 * (slow / 50.0)  # scales with slowness

        # RSI
        delta = df["close"].diff()
        gain = delta.where(delta > 0, 0.0).rolling(self.rsi_period).mean()
        loss = (-delta.where(delta < 0, 0.0)).rolling(self.rsi_period).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))

        # MACD histogram
        macd = df["close"].ewm(span=12).mean() - df["close"].ewm(span=26).mean()
        macd_sig = macd.ewm(span=9).mean()
        macd_hist = macd - macd_sig

        # Rate of change for trend confirmation
        roc = df["close"].pct_change(fast)

        position = pd.Series(0.0, index=df.index)
        in_position = 0.0
        bars_in_trade = 0
        entry_price = 0.0
        max_hold = max(20, slow // 3)  # longer MAs → longer hold

        for i in range(max(slow, 30), len(df)):
            s = spread.iloc[i]
            r = rsi.iloc[i]
            m = macd_hist.iloc[i]
            price = df["close"].iloc[i]

            if np.isnan(s) or np.isnan(r) or np.isnan(m):
                position.iloc[i] = in_position
                continue

            if in_position == 0:
                # Entry: spread crosses threshold + RSI in range + MACD confirms
                if s > spread_threshold and r > 35 and r < 75 and m > 0:
                    in_position = min(1.0, abs(s) * 30 + 0.3)
                    bars_in_trade = 0
                    entry_price = price
                elif s < -spread_threshold and r < 65 and r > 25 and m < 0:
                    in_position = -min(1.0, abs(s) * 30 + 0.3)
                    bars_in_trade = 0
                    entry_price = price
            else:
                bars_in_trade += 1
                # Trailing stop: exit if price moves 2% against entry
                pnl_pct = (price - entry_price) / entry_price if entry_price > 0 else 0

                # Exit conditions
                exit_signal = False
                if in_position > 0:
                    # Spread flipped, RSI exhausted, or stop-loss
                    exit_signal = s < -0.001 or r > 80 or pnl_pct < -0.02
                elif in_position < 0:
                    exit_signal = s > 0.001 or r < 20 or pnl_pct > 0.02

                # Max hold period exit
                if exit_signal or bars_in_trade > max_hold:
                    in_position = 0.0
                    bars_in_trade = 0
                    entry_price = 0.0

            position.iloc[i] = in_position

        return position

    def _signal_returns(self, positions: pd.Series, df: pd.DataFrame) -> pd.Series:
        """Compute strategy returns from position series."""
        price_rets = df["close"].pct_change()
        strat_rets = positions.shift(1) * price_rets
        return strat_rets.dropna()
