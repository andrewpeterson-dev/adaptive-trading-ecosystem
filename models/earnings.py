"""
Earnings Momentum trading model.
Trades around earnings-like events detected via volume spikes and price gaps.
Pre-earnings drift, post-earnings fade or continuation.
"""

import numpy as np
import pandas as pd

from models.base import ModelBase, ModelMetrics, Signal


class EarningsMomentumModel(ModelBase):
    """
    Event-driven strategy around earnings-like events:
    - Detects events via volume spikes (>2x avg) combined with price gaps (>2%)
    - Pre-event: ride drift momentum in the bars leading up
    - Post-event: fade overextended gaps or ride confirmed breakouts
    """

    def __init__(
        self,
        name: str = "earnings_momentum_v1",
        pre_days: int = 10,
        post_days: int = 5,
        gap_threshold: float = 0.02,
        fade_threshold: float = 0.04,
        vol_spike_mult: float = 2.0,
    ):
        super().__init__(name=name)
        self.pre_days = pre_days
        self.post_days = post_days
        self.gap_threshold = gap_threshold
        self.fade_threshold = fade_threshold
        self.vol_spike_mult = vol_spike_mult

    def _detect_events(self, df: pd.DataFrame) -> pd.DataFrame:
        """Detect earnings-like events from volume spikes + price gaps."""
        d = df.copy()

        # Gap: open vs previous close
        d["gap"] = d["open"] / d["close"].shift(1) - 1
        d["abs_gap"] = d["gap"].abs()

        # Volume spike
        d["vol_avg"] = d["volume"].rolling(20).mean()
        d["vol_ratio"] = d["volume"] / d["vol_avg"]

        # Event = volume spike + meaningful gap
        d["is_event"] = (d["vol_ratio"] > self.vol_spike_mult) & (d["abs_gap"] > self.gap_threshold)

        # Label bars relative to events
        d["event_phase"] = "normal"
        d["event_gap"] = 0.0
        d["bars_to_event"] = np.nan
        d["bars_after_event"] = np.nan

        event_indices = d.index[d["is_event"]].tolist()

        for ev_idx in event_indices:
            ev_pos = d.index.get_loc(ev_idx)
            gap_val = d["gap"].iloc[ev_pos]

            # Mark event bar
            d.iloc[ev_pos, d.columns.get_loc("event_phase")] = "event"
            d.iloc[ev_pos, d.columns.get_loc("event_gap")] = gap_val

            # Mark pre-event bars
            for offset in range(1, self.pre_days + 1):
                pre_pos = ev_pos - offset
                if pre_pos >= 0 and d["event_phase"].iloc[pre_pos] == "normal":
                    d.iloc[pre_pos, d.columns.get_loc("event_phase")] = "pre"
                    d.iloc[pre_pos, d.columns.get_loc("bars_to_event")] = offset
                    d.iloc[pre_pos, d.columns.get_loc("event_gap")] = gap_val

            # Mark post-event bars
            for offset in range(1, self.post_days + 1):
                post_pos = ev_pos + offset
                if post_pos < len(d) and d["event_phase"].iloc[post_pos] == "normal":
                    d.iloc[post_pos, d.columns.get_loc("event_phase")] = "post"
                    d.iloc[post_pos, d.columns.get_loc("bars_after_event")] = offset
                    d.iloc[post_pos, d.columns.get_loc("event_gap")] = gap_val

        return d

    def _compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        d = self._detect_events(df)

        # Pre-event drift (cumulative return over pre_days window)
        d["pre_drift"] = d["close"].pct_change(self.pre_days)

        # RSI for overbought/oversold confirmation
        delta = d["close"].diff()
        gain = delta.where(delta > 0, 0.0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0.0)).rolling(14).mean()
        rs = gain / loss.replace(0, np.nan)
        d["rsi"] = 100 - (100 / (1 + rs))

        # Momentum (5-bar ROC)
        d["roc_5"] = d["close"].pct_change(5)

        return d

    def train(self, df: pd.DataFrame, **kwargs) -> None:
        best_sharpe = -np.inf
        best_params = {
            "pre_days": self.pre_days,
            "post_days": self.post_days,
            "gap_threshold": self.gap_threshold,
        }

        for pd_ in [5, 8, 10, 15]:
            for post in [3, 5, 7]:
                for gt in [0.015, 0.02, 0.025, 0.03]:
                    self.pre_days = pd_
                    self.post_days = post
                    self.gap_threshold = gt
                    positions = self._backtest_signals(df)
                    rets = self._signal_returns(positions, df)
                    if len(rets) < 20:
                        continue
                    sharpe = (rets.mean() / rets.std()) * np.sqrt(252) if rets.std() > 0 else 0.0
                    if sharpe > best_sharpe:
                        best_sharpe = sharpe
                        best_params = {"pre_days": pd_, "post_days": post, "gap_threshold": gt}

        self.pre_days = best_params["pre_days"]
        self.post_days = best_params["post_days"]
        self.gap_threshold = best_params["gap_threshold"]
        self.is_trained = True
        self._artifact = {**best_params, "train_sharpe": best_sharpe}

    def predict(self, df: pd.DataFrame) -> list[Signal]:
        if len(df) < 50:
            return []

        d = self._compute_indicators(df)
        i = len(d) - 1
        symbol = df["symbol"].iloc[0] if "symbol" in df.columns else "UNKNOWN"

        phase = d["event_phase"].iloc[i]
        gap = d["event_gap"].iloc[i]
        d["rsi"].iloc[i]
        roc = d["roc_5"].iloc[i]

        signals = []

        if phase == "pre":
            # Pre-earnings drift: ride momentum into event
            drift = d["pre_drift"].iloc[i]
            if not np.isnan(drift) and abs(drift) > 0.005:
                direction = "long" if drift > 0 else "short"
                strength = min(0.6, abs(drift) * 10 + 0.15)
                signals.append(Signal(symbol=symbol, direction=direction, strength=round(strength, 3), model_name=self.name))

        elif phase == "post":
            bars_after = d["bars_after_event"].iloc[i]
            if abs(gap) > self.fade_threshold and bars_after <= 2:
                # Fade overextended gap (mean reversion)
                direction = "short" if gap > 0 else "long"
                strength = min(0.7, abs(gap) * 8 + 0.2)
                signals.append(Signal(symbol=symbol, direction=direction, strength=round(strength, 3), model_name=self.name))
            elif not np.isnan(roc) and abs(roc) > 0.01 and bars_after <= self.post_days:
                # Ride post-earnings momentum continuation
                direction = "long" if roc > 0 else "short"
                strength = min(0.6, abs(roc) * 10 + 0.15)
                signals.append(Signal(symbol=symbol, direction=direction, strength=round(strength, 3), model_name=self.name))

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
        entry_price = 0.0

        for i in range(max(self.pre_days, 20) + 1, len(df)):
            phase = d["event_phase"].iloc[i]
            gap = d["event_gap"].iloc[i]
            rsi = d["rsi"].iloc[i]
            roc = d["roc_5"].iloc[i]
            price = df["close"].iloc[i]

            if np.isnan(rsi):
                position.iloc[i] = in_position
                continue

            if in_position == 0.0:
                if phase == "pre":
                    drift = d["pre_drift"].iloc[i]
                    if not np.isnan(drift) and abs(drift) > 0.005:
                        size = min(0.5, abs(drift) * 8 + 0.1)
                        in_position = size if drift > 0 else -size
                        bars_in_trade = 0
                        entry_price = price

                elif phase == "post":
                    bars_after = d["bars_after_event"].iloc[i]
                    if abs(gap) > self.fade_threshold and bars_after <= 2:
                        # Fade the gap
                        size = min(0.6, abs(gap) * 6 + 0.15)
                        in_position = -size if gap > 0 else size
                        bars_in_trade = 0
                        entry_price = price
                    elif not np.isnan(roc) and abs(roc) > 0.01:
                        # Ride continuation
                        size = min(0.5, abs(roc) * 8 + 0.1)
                        in_position = size if roc > 0 else -size
                        bars_in_trade = 0
                        entry_price = price
            else:
                bars_in_trade += 1
                pnl = (price - entry_price) / entry_price if entry_price > 0 else 0
                if in_position < 0:
                    pnl = -pnl

                # Exit: phase ended, stop-loss, or max hold
                max_hold = self.pre_days if phase == "pre" else self.post_days
                if phase == "normal" or bars_in_trade > max_hold or pnl < -0.025:
                    in_position = 0.0
                    bars_in_trade = 0
                    entry_price = 0.0

            position.iloc[i] = in_position

        return position

    def _signal_returns(self, positions: pd.Series, df: pd.DataFrame) -> pd.Series:
        price_rets = df["close"].pct_change()
        strat_rets = positions.shift(1) * price_rets
        return strat_rets.dropna()
