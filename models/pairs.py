"""
Pairs / Statistical Arbitrage model.
Trades the spread between two correlated assets using z-score mean reversion.
"""

import numpy as np
import pandas as pd

from models.base import ModelBase, ModelMetrics, Signal


class PairsModel(ModelBase):
    """
    Statistical arbitrage on correlated asset pairs (e.g. SPY/QQQ):
    - Computes rolling hedge ratio via covariance method
    - Calculates z-score of the log spread
    - Enters at extreme deviations, exits at mean reversion
    - Stop-out if spread diverges further
    """

    def __init__(
        self,
        name: str = "pairs_statarb_v1",
        spread_lookback: int = 30,
        entry_sigma: float = 2.0,
        exit_sigma: float = 0.5,
        max_hold: int = 60,
    ):
        super().__init__(name=name)
        self.spread_lookback = spread_lookback
        self.entry_sigma = entry_sigma
        self.exit_sigma = exit_sigma
        self.max_hold = max_hold
        self._paired_df: pd.DataFrame = pd.DataFrame()

    def _compute_hedge_ratio(self, primary: pd.Series, paired: pd.Series, window: int) -> pd.Series:
        """Rolling hedge ratio via covariance / variance."""
        log_p = np.log(primary)
        log_q = np.log(paired)
        cov = log_p.rolling(window).cov(log_q)
        var = log_q.rolling(window).var()
        return cov / var.replace(0, np.nan)

    def _compute_spread(self, primary: pd.Series, paired: pd.Series, hedge: pd.Series) -> pd.Series:
        """Log spread = log(primary) - hedge * log(paired)."""
        return np.log(primary) - hedge * np.log(paired)

    def _compute_indicators(self, df: pd.DataFrame, paired_df: pd.DataFrame = None) -> pd.DataFrame:
        if paired_df is None:
            paired_df = self._paired_df

        d = df.copy()

        if paired_df.empty or len(paired_df) < len(df):
            d["z_score"] = np.nan
            d["hedge_ratio"] = np.nan
            d["spread"] = np.nan
            return d

        # Align by position (both should have same length/dates)
        primary_close = df["close"].reset_index(drop=True)
        paired_close = paired_df["close"].iloc[:len(df)].reset_index(drop=True)

        hedge = self._compute_hedge_ratio(primary_close, paired_close, self.spread_lookback)
        spread = self._compute_spread(primary_close, paired_close, hedge)

        spread_mean = spread.rolling(self.spread_lookback).mean()
        spread_std = spread.rolling(self.spread_lookback).std()
        z_score = (spread - spread_mean) / spread_std.replace(0, np.nan)

        # Map back to original index
        d["hedge_ratio"] = hedge.values
        d["spread"] = spread.values
        d["z_score"] = z_score.values
        d["spread_mean"] = spread_mean.values
        d["spread_std"] = spread_std.values

        return d

    def train(self, df: pd.DataFrame, **kwargs) -> None:
        paired_df = kwargs.get("paired_df", self._paired_df)
        if isinstance(paired_df, pd.DataFrame) and not paired_df.empty:
            self._paired_df = paired_df

        if self._paired_df.empty:
            self.is_trained = True
            self._artifact = {"error": "no paired data"}
            return

        best_sharpe = -np.inf
        best_params = {
            "spread_lookback": self.spread_lookback,
            "entry_sigma": self.entry_sigma,
            "exit_sigma": self.exit_sigma,
        }

        for sl in [20, 30, 40, 60]:
            for es in [1.5, 2.0, 2.5]:
                for xs in [0.3, 0.5, 0.8]:
                    if xs >= es:
                        continue
                    positions = self._backtest_signals(df, self._paired_df, sl, es, xs)
                    rets = self._signal_returns(positions, df)
                    if len(rets) < 20:
                        continue
                    sharpe = (rets.mean() / rets.std()) * np.sqrt(252) if rets.std() > 0 else 0.0
                    if sharpe > best_sharpe:
                        best_sharpe = sharpe
                        best_params = {"spread_lookback": sl, "entry_sigma": es, "exit_sigma": xs}

        self.spread_lookback = best_params["spread_lookback"]
        self.entry_sigma = best_params["entry_sigma"]
        self.exit_sigma = best_params["exit_sigma"]
        self.is_trained = True
        self._artifact = {**best_params, "train_sharpe": best_sharpe}

    def predict(self, df: pd.DataFrame) -> list[Signal]:
        if self._paired_df.empty or len(df) < self.spread_lookback + 10:
            return []

        d = self._compute_indicators(df)
        i = len(d) - 1
        z = d["z_score"].iloc[i]
        symbol = df["symbol"].iloc[0] if "symbol" in df.columns else "UNKNOWN"

        if np.isnan(z):
            return []

        signals = []

        # Spread too wide (primary expensive vs paired) — short primary
        if z > self.entry_sigma:
            strength = min(0.8, abs(z) / 4.0 + 0.15)
            signals.append(Signal(
                symbol=symbol, direction="short", strength=round(strength, 3),
                model_name=self.name,
                metadata={"z_score": round(z, 3), "hedge_ratio": round(d["hedge_ratio"].iloc[i], 4)}
            ))

        # Spread too narrow (primary cheap vs paired) — long primary
        elif z < -self.entry_sigma:
            strength = min(0.8, abs(z) / 4.0 + 0.15)
            signals.append(Signal(
                symbol=symbol, direction="long", strength=round(strength, 3),
                model_name=self.name,
                metadata={"z_score": round(z, 3), "hedge_ratio": round(d["hedge_ratio"].iloc[i], 4)}
            ))

        # Spread reverted — flatten
        elif abs(z) < self.exit_sigma:
            signals.append(Signal(symbol=symbol, direction="flat", strength=0.0, model_name=self.name))

        return signals

    def evaluate(self, df: pd.DataFrame) -> ModelMetrics:
        if self._paired_df.empty:
            return self.metrics
        positions = self._backtest_signals(df, self._paired_df, self.spread_lookback, self.entry_sigma, self.exit_sigma)
        rets = self._signal_returns(positions, df)
        return self.update_metrics(rets)

    def _backtest_signals(
        self, df: pd.DataFrame, paired_df: pd.DataFrame,
        lookback: int, entry_z: float, exit_z: float
    ) -> pd.Series:
        # Save and restore
        orig_lb = self.spread_lookback
        self.spread_lookback = lookback
        d = self._compute_indicators(df, paired_df)
        self.spread_lookback = orig_lb

        position = pd.Series(0.0, index=df.index)
        in_position = 0.0
        bars_in_trade = 0

        warmup = lookback + 10

        for i in range(warmup, len(df)):
            z = d["z_score"].iloc[i]

            if np.isnan(z):
                position.iloc[i] = in_position
                continue

            if in_position == 0.0:
                if z > entry_z:
                    in_position = -min(0.7, abs(z) / 3.0 + 0.1)
                    bars_in_trade = 0
                elif z < -entry_z:
                    in_position = min(0.7, abs(z) / 3.0 + 0.1)
                    bars_in_trade = 0
            else:
                bars_in_trade += 1

                # Exit: reversion, stop-out, or max hold
                if in_position > 0:
                    if z > -exit_z or z > 0.5:
                        in_position = 0.0
                    elif z < -(entry_z + 1.5):
                        in_position = 0.0
                elif in_position < 0:
                    if z < exit_z or z < -0.5:
                        in_position = 0.0
                    elif z > (entry_z + 1.5):
                        in_position = 0.0

                if bars_in_trade > self.max_hold:
                    in_position = 0.0
                    bars_in_trade = 0

            position.iloc[i] = in_position

        return position

    def _signal_returns(self, positions: pd.Series, df: pd.DataFrame) -> pd.Series:
        price_rets = df["close"].pct_change()
        strat_rets = positions.shift(1) * price_rets
        return strat_rets.dropna()
