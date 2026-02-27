"""
Volatility-based trading model.
Exploits volatility squeeze breakouts and vol regime transitions.
Uses Bollinger Band width, ATR, and multiple entry conditions for robust signal generation.
"""

import numpy as np
import pandas as pd

from models.base import ModelBase, ModelMetrics, Signal


class VolatilityModel(ModelBase):
    """
    Multi-signal volatility strategy:
    - BB width compression relative to its own history (20th percentile threshold)
    - ATR breakout: price moves > 1.5x ATR from prior close
    - Range expansion: current bar range vs average range
    - Volatility mean reversion: when vol percentile > 85th, reduce exposure
    - Squeeze detection retained but made relative (BB width vs its own rolling min)
    - Exits on momentum reversal, max hold (15 bars), or vol spike
    """

    def __init__(
        self,
        name: str = "volatility_v1",
        bb_window: int = 20,
        bb_std: float = 2.0,
        kc_window: int = 20,
        kc_mult: float = 1.5,
        atr_period: int = 14,
        momentum_window: int = 12,
        compression_pct: float = 0.20,   # BB width below this percentile = compression
        atr_breakout_mult: float = 1.5,  # price move > mult * ATR triggers entry
        range_expansion_mult: float = 1.5,  # bar range > mult * avg range triggers entry
        vol_mean_rev_pct: float = 0.85,  # above this vol percentile → go flat
    ):
        super().__init__(name=name)
        self.bb_window = bb_window
        self.bb_std = bb_std
        self.kc_window = kc_window
        self.kc_mult = kc_mult
        self.atr_period = atr_period
        self.momentum_window = momentum_window
        self.compression_pct = compression_pct
        self.atr_breakout_mult = atr_breakout_mult
        self.range_expansion_mult = range_expansion_mult
        self.vol_mean_rev_pct = vol_mean_rev_pct

    # ── Indicators ────────────────────────────────────────────────────────

    def _compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        d = df.copy()

        # Bollinger Bands
        d["bb_mid"] = d["close"].rolling(self.bb_window).mean()
        bb_std = d["close"].rolling(self.bb_window).std()
        d["bb_upper"] = d["bb_mid"] + self.bb_std * bb_std
        d["bb_lower"] = d["bb_mid"] - self.bb_std * bb_std
        d["bb_width"] = (d["bb_upper"] - d["bb_lower"]) / d["bb_mid"]

        # ATR
        high_low = d["high"] - d["low"]
        high_close = (d["high"] - d["close"].shift()).abs()
        low_close = (d["low"] - d["close"].shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        d["atr"] = tr.rolling(self.atr_period).mean()
        d["tr"] = tr

        # Keltner Channels (kept for legacy squeeze compatibility)
        kc_mid = d["close"].ewm(span=self.kc_window).mean()
        d["kc_upper"] = kc_mid + self.kc_mult * d["atr"]
        d["kc_lower"] = kc_mid - self.kc_mult * d["atr"]

        # Classic squeeze (BB inside KC) — kept but supplemented
        d["squeeze_on"] = (d["bb_lower"] > d["kc_lower"]) & (d["bb_upper"] < d["kc_upper"])

        # Relative squeeze: BB width at or below its own rolling 20th percentile
        # This fires far more often than the absolute BB-inside-KC condition
        d["bb_width_pct"] = d["bb_width"].rolling(100).rank(pct=True)
        d["compression_on"] = d["bb_width_pct"] <= self.compression_pct

        # Track when compression just ended (was compressed, now expanding)
        d["compression_release"] = (~d["compression_on"]) & d["compression_on"].shift(1, fill_value=False)

        # Classic squeeze release
        d["squeeze_release"] = (~d["squeeze_on"]) & d["squeeze_on"].shift(1, fill_value=False)

        # ATR breakout: |close - prev_close| > mult * atr
        d["price_move"] = d["close"].diff().abs()
        d["atr_breakout"] = d["price_move"] > self.atr_breakout_mult * d["atr"]
        d["atr_breakout_dir"] = np.sign(d["close"].diff())  # +1 up, -1 down

        # Range expansion: current bar range vs rolling avg range
        d["bar_range"] = d["high"] - d["low"]
        d["avg_range"] = d["bar_range"].rolling(20).mean()
        d["range_expansion"] = d["bar_range"] > self.range_expansion_mult * d["avg_range"]

        # Momentum: simple rate-of-change over window (faster and more reliable than polyfit)
        d["momentum_roc"] = d["close"].pct_change(self.momentum_window)
        d["momentum_norm"] = d["momentum_roc"]  # already normalised (fraction)

        # Volatility percentile (bb_width rank)
        d["vol_pct"] = d["bb_width_pct"]  # reuse already-computed rank

        return d

    # ── Entry / exit helpers ──────────────────────────────────────────────

    @staticmethod
    def _entry_direction(
        squeeze_release: bool,
        compression_release: bool,
        atr_breakout: bool,
        atr_breakout_dir: float,
        range_expansion: bool,
        mom: float,
    ) -> float:
        """
        Return +1 (long), -1 (short), or 0 (no entry).

        Priority order:
        1. ATR breakout — strongest directional signal, use breakout direction.
        2. Squeeze / compression release — use momentum direction.
        3. Range expansion with clear momentum — use momentum direction.
        """
        if atr_breakout and not np.isnan(atr_breakout_dir):
            return float(atr_breakout_dir)

        if squeeze_release or compression_release:
            if mom > 0:
                return 1.0
            elif mom < 0:
                return -1.0

        if range_expansion and abs(mom) > 0.005:
            return 1.0 if mom > 0 else -1.0

        return 0.0

    @staticmethod
    def _position_size(mom: float, base: float = 0.3, scale: float = 100.0, cap: float = 0.8) -> float:
        """Size position proportionally to momentum magnitude, capped at cap."""
        return min(cap, abs(mom) * scale + base)

    # ── ModelBase interface ───────────────────────────────────────────────

    def train(self, df: pd.DataFrame, **kwargs) -> None:
        """Calibrate kc_mult by backtesting across a grid."""
        best_sharpe = -np.inf
        best_kc = self.kc_mult

        for kc in [1.0, 1.25, 1.5, 2.0]:
            self.kc_mult = kc
            positions = self._backtest_signals(df)
            rets = self._signal_returns(positions, df)
            if len(rets) < 20:
                continue
            sharpe = (rets.mean() / rets.std()) * np.sqrt(252) if rets.std() > 0 else 0.0
            if sharpe > best_sharpe:
                best_sharpe = sharpe
                best_kc = kc

        self.kc_mult = best_kc
        self.is_trained = True
        self._artifact = {"kc_mult": best_kc, "train_sharpe": best_sharpe}

    def predict(self, df: pd.DataFrame) -> list[Signal]:
        if len(df) < 120:
            return []

        d = self._compute_indicators(df)
        i = len(d) - 1
        symbol = df["symbol"].iloc[0] if "symbol" in df.columns else "UNKNOWN"

        mom = d["momentum_norm"].iloc[i]
        vol_pct = d["vol_pct"].iloc[i]

        if np.isnan(mom) or np.isnan(vol_pct):
            return []

        signals: list[Signal] = []

        # Vol mean reversion — exit / go flat when vol is very high and momentum stalls
        if vol_pct > self.vol_mean_rev_pct and abs(mom) < 0.005:
            signals.append(
                Signal(symbol=symbol, direction="flat", strength=0.0, model_name=self.name)
            )
            return signals

        direction = self._entry_direction(
            squeeze_release=bool(d["squeeze_release"].iloc[i]),
            compression_release=bool(d["compression_release"].iloc[i]),
            atr_breakout=bool(d["atr_breakout"].iloc[i]),
            atr_breakout_dir=float(d["atr_breakout_dir"].iloc[i]),
            range_expansion=bool(d["range_expansion"].iloc[i]),
            mom=mom,
        )

        if direction > 0:
            strength = self._position_size(mom)
            signals.append(
                Signal(symbol=symbol, direction="long", strength=round(strength, 3), model_name=self.name)
            )
        elif direction < 0:
            strength = self._position_size(mom)
            signals.append(
                Signal(symbol=symbol, direction="short", strength=round(strength, 3), model_name=self.name)
            )

        return signals

    def evaluate(self, df: pd.DataFrame) -> ModelMetrics:
        positions = self._backtest_signals(df)
        rets = self._signal_returns(positions, df)
        return self.update_metrics(rets)

    def _backtest_signals(self, df: pd.DataFrame) -> pd.Series:
        d = self._compute_indicators(df)
        position = pd.Series(0.0, index=df.index)
        in_position = 0.0
        bars_in_trade = 0
        warmup = max(self.bb_window, 100) + 1

        for i in range(warmup, len(df)):
            mom = d["momentum_norm"].iloc[i]
            vol_pct = d["vol_pct"].iloc[i]

            if np.isnan(mom) or np.isnan(vol_pct):
                position.iloc[i] = in_position
                continue

            if in_position == 0.0:
                direction = self._entry_direction(
                    squeeze_release=bool(d["squeeze_release"].iloc[i]),
                    compression_release=bool(d["compression_release"].iloc[i]),
                    atr_breakout=bool(d["atr_breakout"].iloc[i]),
                    atr_breakout_dir=float(d["atr_breakout_dir"].iloc[i]),
                    range_expansion=bool(d["range_expansion"].iloc[i]),
                    mom=mom,
                )
                # Skip entry if vol is very high (mean-reversion regime)
                if vol_pct > self.vol_mean_rev_pct:
                    direction = 0.0

                if direction != 0.0:
                    size = self._position_size(mom)
                    in_position = direction * size
                    bars_in_trade = 0
            else:
                bars_in_trade += 1
                mom_fading = (in_position > 0 and mom < 0) or (in_position < 0 and mom > 0)
                # Exit on momentum reversal, max hold, or extreme vol spike
                if mom_fading or bars_in_trade > 15 or vol_pct > 0.95:
                    in_position = 0.0
                    bars_in_trade = 0

            position.iloc[i] = in_position

        return position

    def _signal_returns(self, positions: pd.Series, df: pd.DataFrame) -> pd.Series:
        price_rets = df["close"].pct_change()
        strat_rets = positions.shift(1) * price_rets
        return strat_rets.dropna()
