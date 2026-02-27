"""
Mean reversion model.
Trades statistical deviations from equilibrium using z-scores, Bollinger Bands,
and RSI extremes. Selective entries with defined exit targets.
"""

import numpy as np
import pandas as pd

from models.base import ModelBase, ModelMetrics, Signal


class MeanReversionModel(ModelBase):
    """
    Generates signals when price deviates significantly from its rolling mean.
    Entries at extreme z-scores, exits at mean reversion or stop-out.
    """

    def __init__(
        self,
        name: str = "mean_reversion_v1",
        lookback: int = 20,
        entry_z: float = 1.8,
        exit_z: float = 0.3,
        rsi_period: int = 14,
        rsi_extreme: float = 25.0,
    ):
        super().__init__(name=name)
        self.lookback = lookback
        self.entry_z = entry_z
        self.exit_z = exit_z
        self.rsi_period = rsi_period
        self.rsi_extreme = rsi_extreme

    def _compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        d = df.copy()
        d["rolling_mean"] = d["close"].rolling(self.lookback).mean()
        d["rolling_std"] = d["close"].rolling(self.lookback).std()
        d["z_score"] = (d["close"] - d["rolling_mean"]) / d["rolling_std"].replace(0, np.nan)

        # BB
        d["bb_upper"] = d["rolling_mean"] + 2 * d["rolling_std"]
        d["bb_lower"] = d["rolling_mean"] - 2 * d["rolling_std"]
        d["bb_pct"] = (d["close"] - d["bb_lower"]) / (d["bb_upper"] - d["bb_lower"])

        # RSI
        delta = d["close"].diff()
        gain = delta.where(delta > 0, 0.0).rolling(self.rsi_period).mean()
        loss = (-delta.where(delta < 0, 0.0)).rolling(self.rsi_period).mean()
        rs = gain / loss.replace(0, np.nan)
        d["rsi"] = 100 - (100 / (1 + rs))

        # Volume spike (mean reversion works better on volume spikes)
        d["vol_ratio"] = d["volume"] / d["volume"].rolling(20).mean()

        return d

    def train(self, df: pd.DataFrame, **kwargs) -> None:
        """Optimize parameters via grid search, centered around initial params."""
        best_sharpe = -np.inf
        best_params = {"lookback": self.lookback, "entry_z": self.entry_z, "exit_z": self.exit_z}

        # Search around initial params to maintain diversity between Tight/Wide variants
        lb_base = self.lookback
        ez_base = self.entry_z
        lb_range = [max(5, lb_base - 10), max(5, lb_base - 5), lb_base, lb_base + 10]
        ez_range = [max(0.8, ez_base - 0.5), max(0.8, ez_base - 0.3), ez_base, ez_base + 0.3]
        xz_range = [0.2, 0.5, 0.8]

        for lb in lb_range:
            for ez in ez_range:
                for xz in xz_range:
                    if xz >= ez:
                        continue
                    positions = self._backtest_signals(df, lb, ez, xz)
                    rets = self._signal_returns(positions, df)
                    if len(rets) < 20:
                        continue
                    sharpe = (rets.mean() / rets.std()) * np.sqrt(252) if rets.std() > 0 else 0
                    if sharpe > best_sharpe:
                        best_sharpe = sharpe
                        best_params = {"lookback": lb, "entry_z": ez, "exit_z": xz}

        self.lookback = best_params["lookback"]
        self.entry_z = best_params["entry_z"]
        self.exit_z = best_params["exit_z"]
        self.is_trained = True
        self._artifact = {**best_params, "train_sharpe": best_sharpe}

    def predict(self, df: pd.DataFrame) -> list[Signal]:
        if len(df) < self.lookback + 10:
            return []

        d = self._compute_indicators(df)
        i = len(d) - 1
        z = d["z_score"].iloc[i]
        rsi = d["rsi"].iloc[i]
        vol_ratio = d["vol_ratio"].iloc[i]
        symbol = df["symbol"].iloc[0] if "symbol" in df.columns else "UNKNOWN"

        signals = []

        # Oversold: long entry — price far below mean, RSI confirming oversold
        if z < -self.entry_z and rsi < (50 + self.rsi_extreme):
            strength = min(1.0, abs(z) / 4.0 + (1.0 if vol_ratio > 1.5 else 0.0) * 0.2)
            strength = max(0.15, strength)
            signals.append(Signal(symbol=symbol, direction="long", strength=round(strength, 3), model_name=self.name))

        # Overbought: short entry — price far above mean, RSI confirming overbought
        elif z > self.entry_z and rsi > (50 - self.rsi_extreme):
            strength = min(1.0, abs(z) / 4.0 + (1.0 if vol_ratio > 1.5 else 0.0) * 0.2)
            strength = max(0.15, strength)
            signals.append(Signal(symbol=symbol, direction="short", strength=round(strength, 3), model_name=self.name))

        # Near mean — flatten
        elif abs(z) < self.exit_z:
            signals.append(Signal(symbol=symbol, direction="flat", strength=0.0, model_name=self.name))

        return signals

    def evaluate(self, df: pd.DataFrame) -> ModelMetrics:
        positions = self._backtest_signals(df, self.lookback, self.entry_z, self.exit_z)
        rets = self._signal_returns(positions, df)
        return self.update_metrics(rets)

    def _backtest_signals(self, df: pd.DataFrame, lookback: int, entry_z: float, exit_z: float) -> pd.Series:
        """Generate positions with proper entry/exit for backtesting."""
        rolling_mean = df["close"].rolling(lookback).mean()
        rolling_std = df["close"].rolling(lookback).std()
        z_score = (df["close"] - rolling_mean) / rolling_std.replace(0, np.nan)

        # RSI for confirmation
        delta = df["close"].diff()
        gain = delta.where(delta > 0, 0.0).rolling(self.rsi_period).mean()
        loss = (-delta.where(delta < 0, 0.0)).rolling(self.rsi_period).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))

        position = pd.Series(0.0, index=df.index)
        in_position = 0.0

        for i in range(lookback + self.rsi_period, len(df)):
            z = z_score.iloc[i]
            r = rsi.iloc[i]

            if np.isnan(z) or np.isnan(r):
                position.iloc[i] = in_position
                continue

            if in_position == 0:
                # Entry: extreme z-score + RSI not contradicting
                # Oversold: z very negative, RSI should be low (confirming oversold)
                if z < -entry_z and r < 55:
                    in_position = min(0.8, abs(z) / 3.0 + 0.1)
                # Overbought: z very positive, RSI should be high
                elif z > entry_z and r > 45:
                    in_position = -min(0.8, abs(z) / 3.0 + 0.1)
            else:
                # Exit: reversion to mean or stop-out
                if in_position > 0:
                    if z > -exit_z or z > 0.5:  # Reverted or overshot
                        in_position = 0.0
                    elif z < -(entry_z + 1.5):  # Stop-out: went further against us
                        in_position = 0.0
                elif in_position < 0:
                    if z < exit_z or z < -0.5:
                        in_position = 0.0
                    elif z > (entry_z + 1.5):
                        in_position = 0.0

            position.iloc[i] = in_position

        return position

    def _signal_returns(self, positions: pd.Series, df: pd.DataFrame) -> pd.Series:
        price_rets = df["close"].pct_change()
        strat_rets = positions.shift(1) * price_rets
        return strat_rets.dropna()
