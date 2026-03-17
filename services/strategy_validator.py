"""
Centralized strategy/bot config validation gate.

Every creation path (API, AI chat tool, AI strategy service) MUST call
``validate_strategy_config`` before persisting. If it returns
``(False, errors)``, the config MUST NOT be saved.

Pure config validation -- no DB queries, no API calls, no side effects.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Canonical sets — derived from what compute_indicators and evaluator support
# ---------------------------------------------------------------------------

RUNTIME_INDICATORS: Set[str] = {
    "RSI", "SMA", "EMA", "MACD", "BBANDS", "ATR",
    "STOCHASTIC", "VWAP", "VOLUME",
}

# Aliases that the indicator engine and evaluator both resolve at runtime.
INDICATOR_ALIASES: Dict[str, str] = {
    "BOLLINGER_BANDS": "BBANDS",
    "BOLLINGER": "BBANDS",
    "BB": "BBANDS",
    "STOCH": "STOCHASTIC",
    "STOCH_RSI": "STOCHASTIC",
    "MOVING_AVERAGE": "SMA",
    "EXPONENTIAL_MOVING_AVERAGE": "EMA",
    # Common lowercase / human-friendly names
    "rsi": "RSI",
    "sma": "SMA",
    "ema": "EMA",
    "macd": "MACD",
    "bbands": "BBANDS",
    "bollinger_bands": "BBANDS",
    "bollinger": "BBANDS",
    "bb": "BBANDS",
    "atr": "ATR",
    "stochastic": "STOCHASTIC",
    "stoch": "STOCHASTIC",
    "stoch_rsi": "STOCHASTIC",
    "vwap": "VWAP",
    "volume": "VOLUME",
    "moving_average": "SMA",
    "exponential_moving_average": "EMA",
    # OBV gets proxied to VOLUME in _normalize_condition
    "obv": "VOLUME",
}

VALID_OPERATORS: Set[str] = {
    ">", "<", ">=", "<=", "==",
    "crosses_above", "crosses_below",
}

VALID_ACTIONS: Set[str] = {"BUY", "SELL", "SHORT"}

VALID_TIMEFRAMES: Set[str] = {"1m", "5m", "15m", "1H", "4H", "1D", "1W"}

# ---------------------------------------------------------------------------
# Per-indicator threshold ranges
# ---------------------------------------------------------------------------

_THRESHOLD_RANGES: Dict[str, Tuple[Optional[float], Optional[float]]] = {
    "RSI": (0, 100),
    "SMA": (0, None),        # price-based, must be > 0 (unless compare_to)
    "EMA": (0, None),
    "MACD": (-50, 50),
    "ATR": (0, 100),
    "VOLUME": (0, None),
    "STOCHASTIC": (0, 100),
    "VWAP": (0, None),
    "BBANDS": (0, None),     # price-based
}

# Indicators where a threshold of exactly 0 with ">" is suspect (price-based)
_ZERO_SUSPECT_INDICATORS: Set[str] = {"SMA", "EMA", "VWAP", "BBANDS"}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def validate_strategy_config(config: Dict[str, Any]) -> Tuple[bool, List[str], List[str]]:
    """Validate a strategy/bot config before saving.

    Returns ``(is_valid, errors, warnings)`` where:
    - ``errors`` is a list of hard-block error strings.
      If non-empty, the config MUST NOT be saved.
    - ``warnings`` is a list of advisory strings (semantic coherence, etc.).
      Warnings do not block saving.
    """
    errors: List[str] = []
    warnings: List[str] = []

    _validate_structure(config, errors)
    _validate_conditions(config, errors, warnings)
    _validate_parameters(config, errors)

    if errors:
        logger.warning(
            "strategy_config_validation_failed",
            extra={"error_count": len(errors), "errors": errors[:10]},
        )

    return (len(errors) == 0, errors, warnings)


# ---------------------------------------------------------------------------
# Structural validation
# ---------------------------------------------------------------------------

def _validate_structure(config: Dict[str, Any], errors: List[str]) -> None:
    # Action
    action = str(config.get("action", "") or "").strip().upper()
    if action not in VALID_ACTIONS:
        errors.append(
            f"action '{config.get('action')}' is invalid — must be one of: {', '.join(sorted(VALID_ACTIONS))}"
        )

    # Timeframe
    timeframe = str(config.get("timeframe", "") or "").strip()
    if not timeframe:
        errors.append("timeframe is required")
    elif timeframe not in VALID_TIMEFRAMES:
        errors.append(
            f"timeframe '{timeframe}' is invalid — must be one of: {', '.join(sorted(VALID_TIMEFRAMES))}"
        )

    # Symbols
    symbols = config.get("symbols")
    if not isinstance(symbols, list) or not symbols:
        errors.append("must have at least 1 symbol")
    elif not any(str(s or "").strip() for s in symbols):
        errors.append("must have at least 1 non-empty symbol")

    # At least 1 entry condition
    conditions = _collect_conditions(config)
    if not conditions:
        errors.append("must have at least 1 entry condition with an indicator and operator")

    # stop_loss_pct
    sl = config.get("stop_loss_pct")
    if sl is not None:
        try:
            sl_val = float(sl)
            if sl_val <= 0:
                errors.append(f"stop_loss_pct ({sl_val}) must be > 0")
            elif sl_val >= 1:
                errors.append(
                    f"stop_loss_pct ({sl_val}) must be < 1 (expressed as a decimal, e.g. 0.03 for 3%)"
                )
        except (TypeError, ValueError):
            errors.append(f"stop_loss_pct '{sl}' is not a valid number")

    # take_profit_pct
    tp = config.get("take_profit_pct")
    if tp is not None:
        try:
            tp_val = float(tp)
            if tp_val <= 0:
                errors.append(f"take_profit_pct ({tp_val}) must be > 0")
        except (TypeError, ValueError):
            errors.append(f"take_profit_pct '{tp}' is not a valid number")

    # position_size_pct
    ps = config.get("position_size_pct")
    if ps is not None:
        try:
            ps_val = float(ps)
            if ps_val <= 0:
                errors.append(f"position_size_pct ({ps_val}) must be > 0")
            elif ps_val > 1:
                errors.append(
                    f"position_size_pct ({ps_val}) must be <= 1 (expressed as a decimal, e.g. 0.10 for 10%)"
                )
        except (TypeError, ValueError):
            errors.append(f"position_size_pct '{ps}' is not a valid number")


# ---------------------------------------------------------------------------
# Condition-level validation (indicator, operator, threshold)
# ---------------------------------------------------------------------------

def _validate_conditions(
    config: Dict[str, Any],
    errors: List[str],
    warnings: List[str],
) -> None:
    action = str(config.get("action", "") or "").strip().upper()
    conditions = _collect_conditions(config)

    for idx, cond in enumerate(conditions, start=1):
        label = f"condition #{idx}"
        raw_indicator = str(cond.get("indicator", "") or "").strip()
        if not raw_indicator:
            errors.append(f"{label}: indicator is missing")
            continue

        # Resolve aliases
        resolved = _resolve_indicator(raw_indicator)
        if resolved is None:
            errors.append(
                f"{label}: indicator '{raw_indicator}' is not supported — "
                f"valid indicators: {', '.join(sorted(RUNTIME_INDICATORS))}"
            )
            continue

        # Operator
        operator = str(cond.get("operator", "") or "").strip()
        if operator not in VALID_OPERATORS:
            errors.append(
                f"{label}: operator '{operator}' is invalid — "
                f"must be one of: {', '.join(sorted(VALID_OPERATORS))}"
            )

        # Threshold range
        raw_value = cond.get("value")
        compare_to = cond.get("compare_to")
        if raw_value is not None and not compare_to:
            try:
                value = float(raw_value)
                _check_threshold(resolved, value, operator, label, errors, warnings)
            except (TypeError, ValueError):
                errors.append(f"{label}: value '{raw_value}' is not a valid number")

        # Semantic coherence (warnings only)
        if resolved == "RSI" and raw_value is not None and not compare_to:
            try:
                value = float(raw_value)
                if action == "BUY" and operator == ">" and value >= 70:
                    warnings.append(
                        f"{label}: RSI > {value} for BUY is unusual — RSI above 70 indicates "
                        f"overbought conditions, which typically signals a sell, not a buy"
                    )
                elif action in ("SELL", "SHORT") and operator == "<" and value <= 30:
                    warnings.append(
                        f"{label}: RSI < {value} for {action} is unusual — RSI below 30 indicates "
                        f"oversold conditions, which typically signals a buy, not a sell/short"
                    )
            except (TypeError, ValueError):
                pass


def _check_threshold(
    indicator: str,
    value: float,
    operator: str,
    label: str,
    errors: List[str],
    warnings: List[str],
) -> None:
    bounds = _THRESHOLD_RANGES.get(indicator)
    if bounds is None:
        return

    lo, hi = bounds

    if lo is not None and value < lo:
        errors.append(
            f"{label}: {indicator} threshold {value} is below the valid minimum {lo}"
        )
    if hi is not None and value > hi:
        errors.append(
            f"{label}: {indicator} threshold {value} is outside valid range {lo}-{hi}"
        )

    # Warn on suspect zero-threshold for price-based indicators
    if indicator in _ZERO_SUSPECT_INDICATORS and value == 0 and operator == ">":
        warnings.append(
            f"{label}: {indicator} > 0 is likely always true for price-based indicators — "
            f"consider using a meaningful threshold or 'crosses_above'/'crosses_below' operator"
        )


# ---------------------------------------------------------------------------
# Parameter validation
# ---------------------------------------------------------------------------

def _validate_parameters(config: Dict[str, Any], errors: List[str]) -> None:
    conditions = _collect_conditions(config)
    for idx, cond in enumerate(conditions, start=1):
        label = f"condition #{idx}"
        raw_indicator = str(cond.get("indicator", "") or "").strip()
        resolved = _resolve_indicator(raw_indicator)
        if resolved is None:
            continue  # already reported in _validate_conditions

        params = cond.get("params") or {}
        if not isinstance(params, dict):
            continue

        # Period / length must be positive integer < 500
        for key in ("period", "length", "k_period", "d_period", "fast", "slow", "signal"):
            if key in params:
                try:
                    pval = int(float(params[key]))
                    if pval <= 0:
                        errors.append(
                            f"{label}: {resolved} param '{key}' = {pval} must be a positive integer"
                        )
                    elif pval >= 500:
                        errors.append(
                            f"{label}: {resolved} param '{key}' = {pval} is unreasonably large (must be < 500)"
                        )
                except (TypeError, ValueError):
                    errors.append(
                        f"{label}: {resolved} param '{key}' = '{params[key]}' is not a valid integer"
                    )

        # MACD: fast < slow
        if resolved == "MACD":
            fast = params.get("fast")
            slow = params.get("slow")
            if fast is not None and slow is not None:
                try:
                    fast_val = int(float(fast))
                    slow_val = int(float(slow))
                    if fast_val >= slow_val:
                        errors.append(
                            f"{label}: MACD fast period ({fast_val}) must be less than "
                            f"slow period ({slow_val})"
                        )
                except (TypeError, ValueError):
                    pass  # already caught above


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_indicator(raw: str) -> Optional[str]:
    """Resolve a raw indicator name to its canonical RUNTIME_INDICATORS name.

    Returns None if the indicator is not recognized.
    """
    upper = raw.strip().upper()
    # Direct match
    if upper in RUNTIME_INDICATORS:
        return upper
    # Alias lookup (upper)
    resolved = INDICATOR_ALIASES.get(upper)
    if resolved and resolved in RUNTIME_INDICATORS:
        return resolved
    # Alias lookup (original casing)
    resolved = INDICATOR_ALIASES.get(raw.strip())
    if resolved and resolved in RUNTIME_INDICATORS:
        return resolved
    # Lowercase alias
    resolved = INDICATOR_ALIASES.get(raw.strip().lower())
    if resolved and resolved in RUNTIME_INDICATORS:
        return resolved
    return None


def _collect_conditions(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract all condition dicts from flat conditions list and condition_groups."""
    found: List[Dict[str, Any]] = []

    raw_conditions = config.get("conditions")
    if isinstance(raw_conditions, list):
        for c in raw_conditions:
            if isinstance(c, dict) and str(c.get("indicator", "") or "").strip():
                found.append(c)

    raw_groups = config.get("condition_groups")
    if isinstance(raw_groups, list):
        for group in raw_groups:
            if not isinstance(group, dict):
                continue
            group_conditions = group.get("conditions")
            if not isinstance(group_conditions, list):
                continue
            for c in group_conditions:
                if isinstance(c, dict) and str(c.get("indicator", "") or "").strip():
                    found.append(c)

    # Also check entry_conditions (used in some code paths)
    raw_entry = config.get("entry_conditions")
    if isinstance(raw_entry, list):
        for c in raw_entry:
            if isinstance(c, dict) and str(c.get("indicator", "") or "").strip():
                found.append(c)

    return found
