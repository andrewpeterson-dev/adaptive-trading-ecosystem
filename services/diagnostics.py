"""
Strategy diagnostic engine.
Detects common strategy construction errors, overfitting risks, and logical issues.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import structlog

logger = structlog.get_logger(__name__)


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class Diagnostic:
    code: str
    severity: Severity
    title: str
    message: str
    suggestion: str


@dataclass
class DiagnosticReport:
    diagnostics: list[Diagnostic] = field(default_factory=list)
    score: int = 100  # 0-100 health score

    @property
    def has_critical(self) -> bool:
        return any(d.severity == Severity.CRITICAL for d in self.diagnostics)

    def to_dict(self) -> dict:
        return {
            "score": self.score,
            "has_critical": self.has_critical,
            "total_issues": len(self.diagnostics),
            "diagnostics": [
                {
                    "code": d.code,
                    "severity": d.severity.value,
                    "title": d.title,
                    "message": d.message,
                    "suggestion": d.suggestion,
                }
                for d in self.diagnostics
            ],
        }


# Correlation groups — indicators that measure similar things.
# MACD is separated from raw trend indicators because MACD + SMA/EMA trend
# filter is a standard, valid combination (oscillator + moving average).
CORRELATION_GROUPS = {
    "momentum_oscillators": {"rsi", "stochastic", "cci", "williams_r"},
    "trend_averages": {"sma", "ema"},
    "macd_family": {"macd"},
    "trend_direction": {"adx", "aroon"},
    "volatility": {"bollinger_bands", "atr", "keltner", "donchian"},
    "volume": {"obv", "vwap", "mfi", "ad_line", "cmf"},
}

# Parameters with common over-optimization ranges
PARAMETER_BOUNDS = {
    "rsi": {"length": (5, 50)},
    "sma": {"length": (5, 200)},
    "ema": {"length": (5, 200)},
    "macd": {"fast": (5, 20), "slow": (15, 50), "signal": (5, 15)},
    "bollinger_bands": {"length": (10, 50), "std_dev": (1.0, 3.5)},
    "atr": {"length": (5, 50)},
    "stochastic": {"k_period": (5, 30), "d_period": (2, 10)},
}

# Operators that indicate crossover signals rather than directional bias
CROSSOVER_OPERATORS = {"crosses_above", "crosses_below", "cross_above", "cross_below"}


class StrategyDiagnostics:
    """Run diagnostic checks on strategy definitions."""

    @classmethod
    def run_all(
        cls,
        conditions: list[dict],
        parameters: dict[str, dict],
        *,
        has_stop_loss: bool = False,
        has_take_profit: bool = False,
    ) -> DiagnosticReport:
        """
        conditions: list of {"indicator": str, "operator": str, "value": Any, "params": dict}
        parameters: dict of indicator_name -> {param_name: value}
        has_stop_loss: whether the strategy has a stop-loss configured
        has_take_profit: whether the strategy has a take-profit configured
        """
        report = DiagnosticReport()

        cls._check_correlated_indicators(conditions, report)
        cls._check_conflicting_signals(conditions, report)
        cls._check_parameter_extremes(parameters, report)
        cls._check_condition_count(conditions, report)
        cls._check_lookahead_bias(conditions, report)
        cls._check_redundant_conditions(conditions, report)
        cls._check_missing_exit(conditions, report, has_stop_loss=has_stop_loss, has_take_profit=has_take_profit)

        # Compute score
        deductions = sum(
            30 if d.severity == Severity.CRITICAL else 15 if d.severity == Severity.WARNING else 5
            for d in report.diagnostics
        )
        report.score = max(0, 100 - deductions)

        logger.info("diagnostics_complete", score=report.score, issues=len(report.diagnostics))
        return report

    @classmethod
    def _check_correlated_indicators(cls, conditions: list[dict], report: DiagnosticReport):
        used = {c["indicator"].lower() for c in conditions}
        for group_name, members in CORRELATION_GROUPS.items():
            overlap = used & members
            if len(overlap) >= 2:
                report.diagnostics.append(Diagnostic(
                    code="CORR_001",
                    severity=Severity.WARNING,
                    title="Correlated Indicators",
                    message=f"Indicators {', '.join(sorted(overlap))} belong to the same category ({group_name}). They measure similar market properties and provide redundant information.",
                    suggestion=f"Remove one of {', '.join(sorted(overlap))} or replace with an indicator from a different category (e.g., combine momentum with volume).",
                ))

    @classmethod
    def _check_conflicting_signals(cls, conditions: list[dict], report: DiagnosticReport):
        bullish = []
        bearish = []
        for c in conditions:
            ind = c["indicator"].lower()
            op = c.get("operator", "")
            val = c.get("value", 0)

            # Skip crossover operators — they are directional signals, not
            # simple above/below comparisons, and are inherently consistent
            # with the strategy direction.
            if op in CROSSOVER_OPERATORS:
                continue

            # Skip conditions that compare to another indicator (e.g., EMA > SMA)
            if c.get("compare_to"):
                continue

            if ind == "rsi":
                if op == "<" and isinstance(val, (int, float)) and val < 40:
                    bullish.append("RSI oversold (buy signal)")
                elif op == ">" and isinstance(val, (int, float)) and val > 60:
                    bearish.append("RSI overbought (sell signal)")
            elif ind == "macd":
                if op == ">":
                    bullish.append("MACD bullish")
                elif op == "<":
                    bearish.append("MACD bearish")
            elif ind in ("sma", "ema"):
                # Only flag as directional when comparing price to the MA
                # with a meaningful threshold. EMA < 0 is ambiguous and
                # often means "EMA slope is negative" which is actually a
                # valid filter, not a conflicting signal.
                if isinstance(val, (int, float)) and val > 0:
                    if op == ">":
                        bullish.append(f"Price above {ind.upper()} (bullish)")
                    elif op == "<":
                        bearish.append(f"Price below {ind.upper()} (bearish)")

        if bullish and bearish:
            report.diagnostics.append(Diagnostic(
                code="CONFLICT_001",
                severity=Severity.CRITICAL,
                title="Conflicting Signals",
                message=f"Strategy contains both bullish signals ({', '.join(bullish)}) and bearish signals ({', '.join(bearish)}) as entry conditions. These will rarely align.",
                suggestion="Ensure all conditions agree on direction. For a BUY strategy, all indicators should confirm bullish bias.",
            ))

    @classmethod
    def _check_parameter_extremes(cls, parameters: dict[str, dict], report: DiagnosticReport):
        for ind_name, params in parameters.items():
            bounds = PARAMETER_BOUNDS.get(ind_name.lower(), {})
            for param_name, value in params.items():
                if param_name in bounds and isinstance(value, (int, float)):
                    lo, hi = bounds[param_name]
                    if value < lo or value > hi:
                        report.diagnostics.append(Diagnostic(
                            code="PARAM_001",
                            severity=Severity.WARNING,
                            title="Extreme Parameter Value",
                            message=f"{ind_name.upper()}({param_name}={value}) is outside the typical range [{lo}, {hi}]. Extreme values often indicate overfitting to historical data.",
                            suggestion=f"Use {ind_name.upper()}({param_name}={bounds[param_name][0]}-{bounds[param_name][1]}) unless you have a specific quantitative reason.",
                        ))

    @classmethod
    def _check_condition_count(cls, conditions: list[dict], report: DiagnosticReport):
        if len(conditions) > 5:
            report.diagnostics.append(Diagnostic(
                code="COMPLEXITY_001",
                severity=Severity.WARNING,
                title="Excessive Conditions",
                message=f"Strategy has {len(conditions)} conditions. More conditions reduce trade frequency exponentially and increase curve-fitting risk.",
                suggestion="Limit entry conditions to 2-4 indicators from different categories. Each additional condition should add orthogonal information.",
            ))
        if len(conditions) == 1:
            report.diagnostics.append(Diagnostic(
                code="COMPLEXITY_002",
                severity=Severity.INFO,
                title="Single Condition",
                message="Strategy relies on a single indicator. This can generate many false signals.",
                suggestion="Add a confirmation indicator from a different category (e.g., add volume confirmation to a momentum signal).",
            ))

    @classmethod
    def _check_lookahead_bias(cls, conditions: list[dict], report: DiagnosticReport):
        for c in conditions:
            ind = c["indicator"].lower()
            if ind == "vwap" and c.get("timeframe", "") in ("", "daily"):
                report.diagnostics.append(Diagnostic(
                    code="LOOKAHEAD_001",
                    severity=Severity.WARNING,
                    title="Potential Lookahead Bias",
                    message="VWAP is a cumulative intraday indicator. Using end-of-day VWAP in a daily strategy introduces lookahead bias since the full-day VWAP is not known until market close.",
                    suggestion="Use VWAP only on intraday timeframes, or use prior-day VWAP as a reference level.",
                ))

    @classmethod
    def _check_redundant_conditions(cls, conditions: list[dict], report: DiagnosticReport):
        seen = {}
        for c in conditions:
            key = c["indicator"].lower()
            if key in seen:
                report.diagnostics.append(Diagnostic(
                    code="REDUNDANT_001",
                    severity=Severity.INFO,
                    title="Duplicate Indicator",
                    message=f"{c['indicator']} appears multiple times with different parameters. While valid (e.g., dual SMA crossover), ensure this is intentional.",
                    suggestion="If using the same indicator twice, make sure parameters create meaningful signal differentiation.",
                ))
            seen[key] = True

    @classmethod
    def _check_missing_exit(
        cls,
        conditions: list[dict],
        report: DiagnosticReport,
        *,
        has_stop_loss: bool = False,
        has_take_profit: bool = False,
    ):
        has_exit_condition = any(c.get("action", "").upper() in ("SELL", "EXIT", "CLOSE") for c in conditions)

        # If the strategy has stop-loss and take-profit configured, that counts
        # as valid exit logic — don't flag EXIT_001.
        if has_exit_condition or (has_stop_loss and has_take_profit):
            return

        # Only flag if there's truly no exit mechanism at all
        if has_stop_loss or has_take_profit:
            # Has partial exit config — downgrade to info
            report.diagnostics.append(Diagnostic(
                code="EXIT_002",
                severity=Severity.INFO,
                title="Partial Exit Logic",
                message="Strategy has stop-loss or take-profit but not both. Consider adding the missing component for balanced risk management.",
                suggestion="Add both a stop-loss (to limit downside) and a take-profit (to lock in gains).",
            ))
        else:
            report.diagnostics.append(Diagnostic(
                code="EXIT_001",
                severity=Severity.WARNING,
                title="No Exit Conditions",
                message="Strategy defines entry conditions but no explicit exit logic. Without exit rules, the strategy relies solely on stop-loss or time-based exits.",
                suggestion="Define exit conditions (e.g., RSI > 70 for a mean-reversion buy strategy) or configure stop-loss and take-profit.",
            ))
