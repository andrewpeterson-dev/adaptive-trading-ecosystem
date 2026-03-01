"""
Portfolio-level risk analytics.
Calculates VaR, Expected Shortfall, Beta, correlation, concentration,
and generates comprehensive risk reports.

Pure numpy/pandas math — no LLM calls, no external APIs for calculations.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import structlog

logger = structlog.get_logger(__name__)

# Try scipy for parametric VaR; fall back to pure numpy
try:
    from scipy import stats as scipy_stats
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False


class PortfolioRiskAnalyzer:
    """Portfolio-level risk analytics. Pure math — no LLM, no broker calls."""

    REPORT_PATH = Path(__file__).parent / "portfolio-risk.json"

    # ── Volatility ────────────────────────────────────────────────────────

    def calculate_historical_volatility(
        self, returns: pd.Series, window: int = 252
    ) -> float:
        """Annualized historical volatility from daily returns."""
        if returns.empty or len(returns) < 2:
            return 0.0
        tail = returns.iloc[-window:]
        return float(tail.std() * np.sqrt(252))

    # ── Correlation ───────────────────────────────────────────────────────

    def calculate_correlation_matrix(
        self, price_data: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Correlation matrix between all holdings.
        Expects a DataFrame with columns = tickers, rows = dates, values = prices.
        Converts to returns internally.
        """
        if price_data.empty or price_data.shape[1] < 2:
            return pd.DataFrame()
        returns = price_data.pct_change().dropna()
        if returns.empty:
            return pd.DataFrame()
        return returns.corr()

    # ── Beta ──────────────────────────────────────────────────────────────

    def calculate_beta(
        self, asset_returns: pd.Series, market_returns: pd.Series
    ) -> float:
        """Beta of an asset vs a market benchmark (e.g. SPY)."""
        if len(asset_returns) < 2 or len(market_returns) < 2:
            return 0.0
        # Align indices
        aligned = pd.concat(
            [asset_returns, market_returns], axis=1, join="inner"
        ).dropna()
        if len(aligned) < 2:
            return 0.0
        asset_col = aligned.iloc[:, 0]
        market_col = aligned.iloc[:, 1]
        cov = np.cov(asset_col, market_col)
        market_var = cov[1, 1]
        if market_var == 0:
            return 0.0
        return float(cov[0, 1] / market_var)

    # ── Value at Risk ─────────────────────────────────────────────────────

    def calculate_var(
        self,
        returns: pd.Series,
        confidence: float = 0.95,
        method: str = "historical",
    ) -> float:
        """
        Value at Risk (as a negative number representing loss).
        Methods: 'historical', 'parametric'.
        Returns the loss threshold at the given confidence level.
        """
        if returns.empty or len(returns) < 2:
            return 0.0

        if method == "parametric":
            mu = returns.mean()
            sigma = returns.std()
            if sigma == 0:
                return 0.0
            if HAS_SCIPY:
                z = scipy_stats.norm.ppf(1 - confidence)
            else:
                # Approximate z-scores for common confidence levels
                z_table = {0.90: -1.2816, 0.95: -1.6449, 0.99: -2.3263}
                z = z_table.get(confidence, -1.6449)
            return float(mu + z * sigma)
        else:
            # Historical simulation
            return float(np.percentile(returns.dropna(), (1 - confidence) * 100))

    # ── Expected Shortfall (CVaR) ─────────────────────────────────────────

    def calculate_expected_shortfall(
        self, returns: pd.Series, confidence: float = 0.95
    ) -> float:
        """
        CVaR / Expected Shortfall — average loss beyond VaR.
        Always more negative than VaR.
        """
        if returns.empty or len(returns) < 2:
            return 0.0
        var = self.calculate_var(returns, confidence, method="historical")
        tail = returns[returns <= var]
        if tail.empty:
            return var
        return float(tail.mean())

    # ── Concentration Risk ────────────────────────────────────────────────

    def calculate_concentration_risk(self, positions: list[dict]) -> float:
        """
        Herfindahl-Hirschman Index for portfolio concentration.
        Range: 1/N (perfectly diversified) to 1.0 (single position).
        Uses absolute market value weights.
        """
        if not positions:
            return 0.0
        values = [abs(float(p.get("market_value", 0))) for p in positions]
        total = sum(values)
        if total == 0:
            return 0.0
        weights = [v / total for v in values]
        return float(sum(w ** 2 for w in weights))

    # ── Risk Rating ───────────────────────────────────────────────────────

    @staticmethod
    def _risk_rating(
        vol: float, var_95: float, hhi: float, drawdown: float
    ) -> str:
        """Classify overall portfolio risk as low / moderate / high / critical."""
        score = 0
        if vol > 0.30:
            score += 2
        elif vol > 0.20:
            score += 1
        if var_95 < -0.03:
            score += 2
        elif var_95 < -0.02:
            score += 1
        if hhi > 0.25:
            score += 2
        elif hhi > 0.15:
            score += 1
        if drawdown > 0.15:
            score += 2
        elif drawdown > 0.08:
            score += 1
        if score >= 6:
            return "critical"
        if score >= 4:
            return "high"
        if score >= 2:
            return "moderate"
        return "low"

    # ── Full Report ───────────────────────────────────────────────────────

    def generate_risk_report(
        self,
        positions: list[dict],
        price_history: pd.DataFrame,
        portfolio_value: Optional[float] = None,
    ) -> dict:
        """
        Generate complete risk report and write to risk/portfolio-risk.json.

        Args:
            positions: list of dicts with at least 'symbol' and 'market_value' keys.
            price_history: DataFrame with columns = ticker symbols, rows = dates,
                           values = closing prices. Must include a 'SPY' column
                           for beta calculations (if available).
            portfolio_value: total portfolio value for dollar VaR. If None,
                             computed from position market values.
        """
        warnings: list[str] = []

        # Handle empty portfolio
        if not positions or price_history.empty:
            report = {
                "timestamp": datetime.utcnow().isoformat(),
                "portfolio_volatility": 0.0,
                "correlation_matrix": {},
                "betas": {},
                "var_95_pct": 0.0,
                "var_95_dollar": 0.0,
                "expected_shortfall_95": 0.0,
                "concentration_hhi": 0.0,
                "risk_rating": "low",
                "max_drawdown_current": 0.0,
                "warnings": ["Empty portfolio or no price history"],
            }
            self._write_report(report)
            return report

        # Derive portfolio value
        if portfolio_value is None:
            portfolio_value = sum(
                abs(float(p.get("market_value", 0))) for p in positions
            )

        # Build returns from price history
        returns_df = price_history.pct_change().dropna()

        # Symbols in both positions and price history
        position_symbols = [p["symbol"] for p in positions if p.get("symbol")]
        available_symbols = [
            s for s in position_symbols if s in returns_df.columns
        ]
        missing = set(position_symbols) - set(available_symbols)
        if missing:
            warnings.append(f"No price history for: {', '.join(sorted(missing))}")

        # Portfolio-weighted returns
        if available_symbols and portfolio_value > 0:
            weight_map = {}
            for p in positions:
                sym = p.get("symbol")
                if sym in available_symbols:
                    weight_map[sym] = abs(float(p.get("market_value", 0))) / portfolio_value

            portfolio_returns = pd.Series(0.0, index=returns_df.index)
            for sym, w in weight_map.items():
                portfolio_returns += returns_df[sym] * w
        else:
            portfolio_returns = pd.Series(dtype=float)

        # Volatility
        vol = self.calculate_historical_volatility(portfolio_returns)

        # Correlation matrix (only for available symbols)
        if len(available_symbols) >= 2:
            corr = self.calculate_correlation_matrix(
                price_history[available_symbols]
            )
            corr_dict = {
                col: {
                    row: round(corr.loc[row, col], 4)
                    for row in corr.index
                    if row != col
                }
                for col in corr.columns
            }
        else:
            corr_dict = {}

        # Betas
        betas = {}
        market_col = "SPY"
        if market_col in returns_df.columns:
            market_returns = returns_df[market_col]
            for sym in available_symbols:
                if sym == market_col:
                    betas[sym] = 1.0
                else:
                    betas[sym] = round(
                        self.calculate_beta(returns_df[sym], market_returns), 4
                    )
        else:
            warnings.append("SPY not in price history — beta calculation skipped")

        # VaR
        var_95 = self.calculate_var(portfolio_returns, confidence=0.95)
        var_95_dollar = var_95 * portfolio_value if portfolio_value else 0.0

        # Expected Shortfall
        es_95 = self.calculate_expected_shortfall(portfolio_returns, confidence=0.95)
        es_95_dollar = es_95 * portfolio_value if portfolio_value else 0.0

        # Concentration
        hhi = self.calculate_concentration_risk(positions)
        if hhi > 0.25:
            warnings.append(f"High concentration risk (HHI={hhi:.2f})")

        # Current max drawdown (from portfolio returns)
        if not portfolio_returns.empty and len(portfolio_returns) >= 2:
            cumulative = (1 + portfolio_returns).cumprod()
            rolling_max = cumulative.cummax()
            drawdown_series = (cumulative - rolling_max) / rolling_max
            max_dd = float(drawdown_series.min())
        else:
            max_dd = 0.0

        # Risk rating
        rating = self._risk_rating(vol, var_95, hhi, abs(max_dd))

        report = {
            "timestamp": datetime.utcnow().isoformat(),
            "portfolio_volatility": round(vol, 6),
            "correlation_matrix": corr_dict,
            "betas": betas,
            "var_95_pct": round(var_95, 6),
            "var_95_dollar": round(var_95_dollar, 2),
            "expected_shortfall_95": round(es_95_dollar, 2),
            "concentration_hhi": round(hhi, 4),
            "risk_rating": rating,
            "max_drawdown_current": round(max_dd, 6),
            "warnings": warnings,
        }

        self._write_report(report)
        return report

    def _write_report(self, report: dict) -> None:
        """Persist report to risk/portfolio-risk.json."""
        try:
            self.REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(self.REPORT_PATH, "w") as f:
                json.dump(report, f, indent=2, default=str)
            logger.info("risk_report_written", path=str(self.REPORT_PATH))
        except Exception as e:
            logger.error("risk_report_write_failed", error=str(e))
