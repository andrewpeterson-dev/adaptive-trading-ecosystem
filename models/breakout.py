"""
Breakout / Support-Resistance trading model.
Identifies S/R levels using rolling highs/lows and trades confirmed breakouts
with volume surge confirmation and trailing stops.
"""

import numpy as np
import pandas as pd

from models.base import ModelBase, ModelMetrics, Signal


class BreakoutModel(ModelBase):
    """
    Rolling channel breakout strategy:
    - Resistance = rolling high, Support = rolling low (shifted to avoid lookahead)
    - Enter long on close > resistance with volume > mult * avg volume
    - Enter short on close < support with volume confirmation
    - Trail stop at channel midpoint; max hold = 2x channel window
    """

    def __init__(
        self,
        name: str = "breakout_sr_v1",
        channel_window: int = 20,
        volume_mult: float = 1.5,
        atr_stop_mult: float = 2.0,
        confirmation_bars: int = 1,
    ):
        super().__init__(name=name)
        self.channel_window = channel_window
        self.volume_mult = volume_mult
        self.atr_stop_mult = atr_stop_mult
        self.confirmation_bars = confirmation_bars

    def _compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        d = df.copy()

        # S/R levels from rolling channel (shifted to prevent lookahead)
        d["resistance"] = d["high"].rolling(self.channel_window).max().shift(1)
        d["support"] = d["low"].rolling(self.channel_window).min().shift(1)
        d["channel_mid"] = (d["resistance"] + d["support"]) / 2
        d["channel_width"] = (d["resistance"] - d["support"]) / d["close"]

        # ATR for stop sizing
        high_low = d["high"] - d["low"]
        high_close = (d["high"] - d["close"].shift()).abs()
        low_close = (d["low"] - d["close"].shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        d["atr"] = tr.rolling(14).mean()

        # Volume confirmation
        d["vol_avg"] = d["volume"].rolling(20).mean()
        d["vol_ratio"] = d["volume"] / d["vol_avg"]

        # Breakout signals
        d["breakout_up"] = (d["close"] > d["resistance"]) & (d["vol_ratio"] > self.volume_mult)
        d["breakout_down"] = (d["close"] < d["support"]) & (d["vol_ratio"] > self.volume_mult)

        return d

    def train(self, df: pd.DataFrame, **kwargs) -> None:
        best_sharpe = -np.inf
        best_params = {
            "channel_window": self.channel_window,
            "volume_mult": self.volume_mult,
            "atr_stop_mult": self.atr_stop_mult,
        }

        for cw in [15, 20, 25, 30]:
            for vm in [1.2, 1.5, 2.0]:
                for asm in [1.5, 2.0, 2.5, 3.0]:
                    positions = self._backtest_signals(df, cw, vm, asm)
                    rets = self._signal_returns(positions, df)
                    if len(rets) < 20:
                        continue
                    sharpe = (rets.mean() / rets.std()) * np.sqrt(252) if rets.std() > 0 else 0.0
                    if sharpe > best_sharpe:
                        best_sharpe = sharpe
                        best_params = {"channel_window": cw, "volume_mult": vm, "atr_stop_mult": asm}

        self.channel_window = best_params["channel_window"]
        self.volume_mult = best_params["volume_mult"]
        self.atr_stop_mult = best_params["atr_stop_mult"]
        self.is_trained = True
        self._artifact = {**best_params, "train_sharpe": best_sharpe}

    def predict(self, df: pd.DataFrame) -> list[Signal]:
        if len(df) < self.channel_window + 20:
            return []

        d = self._compute_indicators(df)
        i = len(d) - 1
        symbol = df["symbol"].iloc[0] if "symbol" in df.columns else "UNKNOWN"

        signals = []

        if d["breakout_up"].iloc[i]:
            vol_r = d["vol_ratio"].iloc[i]
            cw = d["channel_width"].iloc[i]
            strength = min(1.0, (vol_r - 1.0) / 3.0 + cw * 10 + 0.2)
            strength = max(0.15, min(0.9, strength))
            signals.append(Signal(symbol=symbol, direction="long", strength=round(strength, 3), model_name=self.name))

        elif d["breakout_down"].iloc[i]:
            vol_r = d["vol_ratio"].iloc[i]
            cw = d["channel_width"].iloc[i]
            strength = min(1.0, (vol_r - 1.0) / 3.0 + cw * 10 + 0.2)
            strength = max(0.15, min(0.9, strength))
            signals.append(Signal(symbol=symbol, direction="short", strength=round(strength, 3), model_name=self.name))

        return signals

    def evaluate(self, df: pd.DataFrame) -> ModelMetrics:
        positions = self._backtest_signals(df, self.channel_window, self.volume_mult, self.atr_stop_mult)
        rets = self._signal_returns(positions, df)
        return self.update_metrics(rets)

    def _backtest_signals(self, df: pd.DataFrame, channel_win: int, vol_mult: float, atr_mult: float) -> pd.Series:
        # Precompute indicators
        resistance = df["high"].rolling(channel_win).max().shift(1)
        support = df["low"].rolling(channel_win).min().shift(1)
        channel_mid = (resistance + support) / 2

        high_low = df["high"] - df["low"]
        high_close = (df["high"] - df["close"].shift()).abs()
        low_close = (df["low"] - df["close"].shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(14).mean()

        vol_avg = df["volume"].rolling(20).mean()
        vol_ratio = df["volume"] / vol_avg

        position = pd.Series(0.0, index=df.index)
        in_position = 0.0
        bars_in_trade = 0
        entry_price = 0.0
        trailing_stop = 0.0
        max_hold = channel_win * 2

        warmup = max(channel_win, 20) + 1

        for i in range(warmup, len(df)):
            price = df["close"].iloc[i]
            res = resistance.iloc[i]
            sup = support.iloc[i]
            mid = channel_mid.iloc[i]
            a = atr.iloc[i]
            vr = vol_ratio.iloc[i]

            if np.isnan(res) or np.isnan(a) or np.isnan(vr):
                position.iloc[i] = in_position
                continue

            if in_position == 0.0:
                # Breakout up
                if price > res and vr > vol_mult:
                    size = min(0.7, (vr - 1.0) / 3.0 + 0.2)
                    in_position = size
                    bars_in_trade = 0
                    entry_price = price
                    trailing_stop = mid
                # Breakout down
                elif price < sup and vr > vol_mult:
                    size = min(0.7, (vr - 1.0) / 3.0 + 0.2)
                    in_position = -size
                    bars_in_trade = 0
                    entry_price = price
                    trailing_stop = mid
            else:
                bars_in_trade += 1

                if in_position > 0:
                    # Update trailing stop: max of channel mid and entry - atr*mult
                    new_stop = max(mid, entry_price - atr_mult * a)
                    trailing_stop = max(trailing_stop, new_stop)
                    if price < trailing_stop or bars_in_trade > max_hold:
                        in_position = 0.0
                        bars_in_trade = 0
                else:
                    # Short trailing stop
                    new_stop = min(mid, entry_price + atr_mult * a)
                    trailing_stop = min(trailing_stop, new_stop)
                    if price > trailing_stop or bars_in_trade > max_hold:
                        in_position = 0.0
                        bars_in_trade = 0

            position.iloc[i] = in_position

        return position

    def _signal_returns(self, positions: pd.Series, df: pd.DataFrame) -> pd.Series:
        price_rets = df["close"].pct_change()
        strat_rets = positions.shift(1) * price_rets
        return strat_rets.dropna()
