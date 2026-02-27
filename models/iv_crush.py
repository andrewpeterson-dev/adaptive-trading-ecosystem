"""
Options IV Crush trading model.
Exploits implied volatility collapse using BB width / ATR ratio as an IV proxy.
Enters when simulated IV peaks, profits from vol contraction.
"""

import numpy as np
import pandas as pd

from models.base import ModelBase, ModelMetrics, Signal


class IVCrushModel(ModelBase):
    """
    Simulated IV crush strategy:
    - IV proxy = BB width / (ATR / close) — captures relative vol expansion
    - Enter when IV percentile > threshold, direction from trend EMA
    - Exit when IV drops below exit percentile, max hold, or stop-loss
    """

    def __init__(
        self,
        name: str = "iv_crush_v1",
        iv_lookback: int = 20,
        iv_percentile_threshold: float = 0.85,
        exit_percentile: float = 0.50,
        bb_window: int = 20,
        bb_std: float = 2.0,
        atr_period: int = 14,
        trend_window: int = 20,
    ):
        super().__init__(name=name)
        self.iv_lookback = iv_lookback
        self.iv_percentile_threshold = iv_percentile_threshold
        self.exit_percentile = exit_percentile
        self.bb_window = bb_window
        self.bb_std = bb_std
        self.atr_period = atr_period
        self.trend_window = trend_window

    def _compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        d = df.copy()

        # Bollinger Band width
        bb_mid = d["close"].rolling(self.bb_window).mean()
        bb_std = d["close"].rolling(self.bb_window).std()
        d["bb_upper"] = bb_mid + self.bb_std * bb_std
        d["bb_lower"] = bb_mid - self.bb_std * bb_std
        d["bb_width"] = (d["bb_upper"] - d["bb_lower"]) / bb_mid

        # ATR
        high_low = d["high"] - d["low"]
        high_close = (d["high"] - d["close"].shift()).abs()
        low_close = (d["low"] - d["close"].shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        d["atr"] = tr.rolling(self.atr_period).mean()
        d["atr_pct"] = d["atr"] / d["close"]

        # Simulated IV: BB width relative to ATR-based vol
        # When BB width is high relative to ATR, IV is elevated
        d["sim_iv"] = d["bb_width"] / d["atr_pct"].replace(0, np.nan)
        d["iv_pct"] = d["sim_iv"].rolling(100).rank(pct=True)

        # Trend direction
        d["trend_ema"] = d["close"].ewm(span=self.trend_window).mean()
        d["trend_dir"] = np.where(d["close"] > d["trend_ema"], 1.0, -1.0)

        # RSI for additional confirmation
        delta = d["close"].diff()
        gain = delta.where(delta > 0, 0.0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0.0)).rolling(14).mean()
        rs = gain / loss.replace(0, np.nan)
        d["rsi"] = 100 - (100 / (1 + rs))

        return d

    def train(self, df: pd.DataFrame, **kwargs) -> None:
        best_sharpe = -np.inf
        best_params = {
            "iv_lookback": self.iv_lookback,
            "iv_percentile_threshold": self.iv_percentile_threshold,
            "exit_percentile": self.exit_percentile,
        }

        for ivl in [15, 20, 30]:
            for ivt in [0.75, 0.80, 0.85, 0.90]:
                for ep in [0.40, 0.50, 0.60]:
                    if ep >= ivt:
                        continue
                    positions = self._backtest_signals(df, ivl, ivt, ep)
                    rets = self._signal_returns(positions, df)
                    if len(rets) < 20:
                        continue
                    sharpe = (rets.mean() / rets.std()) * np.sqrt(252) if rets.std() > 0 else 0.0
                    if sharpe > best_sharpe:
                        best_sharpe = sharpe
                        best_params = {"iv_lookback": ivl, "iv_percentile_threshold": ivt, "exit_percentile": ep}

        self.iv_lookback = best_params["iv_lookback"]
        self.iv_percentile_threshold = best_params["iv_percentile_threshold"]
        self.exit_percentile = best_params["exit_percentile"]
        self.is_trained = True
        self._artifact = {**best_params, "train_sharpe": best_sharpe}

    def predict(self, df: pd.DataFrame) -> list[Signal]:
        if len(df) < 120:
            return []

        d = self._compute_indicators(df)
        i = len(d) - 1
        symbol = df["symbol"].iloc[0] if "symbol" in df.columns else "UNKNOWN"

        iv_pct = d["iv_pct"].iloc[i]
        trend = d["trend_dir"].iloc[i]

        if np.isnan(iv_pct):
            return []

        signals = []

        # IV is elevated — enter expecting contraction
        if iv_pct > self.iv_percentile_threshold:
            elevation = iv_pct - self.iv_percentile_threshold
            strength = min(0.8, elevation * 3 + 0.2)
            strength = max(0.15, strength)
            direction = "long" if trend > 0 else "short"
            signals.append(Signal(symbol=symbol, direction=direction, strength=round(strength, 3), model_name=self.name))

        # IV dropped back to normal — flatten
        elif iv_pct < self.exit_percentile:
            signals.append(Signal(symbol=symbol, direction="flat", strength=0.0, model_name=self.name))

        return signals

    def evaluate(self, df: pd.DataFrame) -> ModelMetrics:
        positions = self._backtest_signals(df, self.iv_lookback, self.iv_percentile_threshold, self.exit_percentile)
        rets = self._signal_returns(positions, df)
        return self.update_metrics(rets)

    def _backtest_signals(self, df: pd.DataFrame, iv_lookback: int, iv_thresh: float, exit_pct: float) -> pd.Series:
        d = self._compute_indicators(df)

        position = pd.Series(0.0, index=df.index)
        in_position = 0.0
        bars_in_trade = 0
        entry_price = 0.0
        max_hold = 25
        warmup = max(self.bb_window, 100) + 1

        for i in range(warmup, len(df)):
            iv_pct = d["iv_pct"].iloc[i]
            trend = d["trend_dir"].iloc[i]
            price = df["close"].iloc[i]

            if np.isnan(iv_pct):
                position.iloc[i] = in_position
                continue

            if in_position == 0.0:
                if iv_pct > iv_thresh:
                    elevation = iv_pct - iv_thresh
                    size = min(0.7, elevation * 3 + 0.2)
                    in_position = trend * size
                    bars_in_trade = 0
                    entry_price = price
            else:
                bars_in_trade += 1
                pnl_pct = (price - entry_price) / entry_price if entry_price > 0 else 0
                if in_position < 0:
                    pnl_pct = -pnl_pct

                # Exit: IV crushed back down, max hold, or stop-loss
                if iv_pct < exit_pct or bars_in_trade > max_hold or pnl_pct < -0.02:
                    in_position = 0.0
                    bars_in_trade = 0
                    entry_price = 0.0

            position.iloc[i] = in_position

        return position

    def _signal_returns(self, positions: pd.Series, df: pd.DataFrame) -> pd.Series:
        price_rets = df["close"].pct_change()
        strat_rets = positions.shift(1) * price_rets
        return strat_rets.dropna()
