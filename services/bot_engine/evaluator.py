"""
Condition evaluator for bot execution engine.

Evaluates a list of conditions (AND logic) against computed indicator values
and returns whether all conditions passed, plus human-readable reasons.
"""

from __future__ import annotations

import math

_INDICATOR_ALIASES = {
    "BOLLINGER_BANDS": "BBANDS",
    "BOLLINGER": "BBANDS",
    "BB": "BBANDS",
    "STOCH": "STOCHASTIC",
    "STOCH_RSI": "STOCHASTIC",
    "MOVING_AVERAGE": "SMA",
    "EXPONENTIAL_MOVING_AVERAGE": "EMA",
}


def _resolve_indicator_value(
    condition: dict, indicator_values: dict
) -> tuple[float | None, float | None, str]:
    """
    Resolve the current and previous indicator value for a condition.

    Returns (current, previous, key_used).
    """
    name = condition["indicator"].upper()
    name = _INDICATOR_ALIASES.get(name, name)
    params = condition.get("params") or {}

    # Build the lookup key the same way compute_indicators does
    if name == "RSI":
        period = int(params.get("period", 14))
        key = f"RSI_{period}"
    elif name == "SMA":
        period = int(params.get("period", 20))
        key = f"SMA_{period}"
    elif name == "EMA":
        period = int(params.get("period", 20))
        key = f"EMA_{period}"
    elif name == "ATR":
        period = int(params.get("period", 14))
        key = f"ATR_{period}"
    elif name == "VWAP":
        key = "VWAP"
    elif name == "VOLUME":
        key = "VOLUME"
    elif name == "MACD":
        # MACD is a composite — figure out which sub-field the condition targets
        sub = condition.get("field", "macd").lower()
        macd_data = indicator_values.get("MACD", {})
        if isinstance(macd_data, dict):
            current = macd_data.get(sub)
            previous = macd_data.get(f"prev_{sub}")
            return (
                float(current) if current is not None else None,
                float(previous) if previous is not None else None,
                f"MACD.{sub}",
            )
        return (None, None, "MACD")
    elif name == "BBANDS":
        sub = condition.get("field", "middle").lower()
        bb_data = indicator_values.get("BBANDS", {})
        if isinstance(bb_data, dict):
            current = bb_data.get(sub)
            previous = bb_data.get(f"prev_{sub}")
            return (
                float(current) if current is not None else None,
                float(previous) if previous is not None else None,
                f"BBANDS.{sub}",
            )
        return (None, None, "BBANDS")
    elif name == "STOCHASTIC":
        sub = condition.get("field", "k").lower()
        stoch_data = indicator_values.get("STOCHASTIC", {})
        if isinstance(stoch_data, dict):
            current = stoch_data.get(sub)
            previous = stoch_data.get(f"prev_{sub}")
            return (
                float(current) if current is not None else None,
                float(previous) if previous is not None else None,
                f"STOCHASTIC.{sub}",
            )
        return (None, None, "STOCHASTIC")
    else:
        key = name

    current = indicator_values.get(key)
    previous = indicator_values.get(f"{key}_prev")

    return (
        float(current) if current is not None else None,
        float(previous) if previous is not None else None,
        key,
    )


def _compare(current: float, operator: str, threshold: float, previous: float | None) -> bool:
    """Evaluate a single comparison."""
    if math.isnan(current):
        return False

    if operator == "<":
        return current < threshold
    elif operator == ">":
        return current > threshold
    elif operator == "<=":
        return current <= threshold
    elif operator == ">=":
        return current >= threshold
    elif operator == "==":
        return abs(current - threshold) < 1e-9
    elif operator == "crosses_above":
        if previous is None or math.isnan(previous):
            return False
        return previous <= threshold and current > threshold
    elif operator == "crosses_below":
        if previous is None or math.isnan(previous):
            return False
        return previous >= threshold and current < threshold
    else:
        return False


def evaluate_conditions(
    conditions: list[dict], indicator_values: dict
) -> tuple[bool, list[str]]:
    """
    Evaluate all conditions using AND logic.

    Parameters
    ----------
    conditions : list[dict]
        Each condition has:
        - ``indicator``: str (e.g. "RSI", "SMA", "MACD")
        - ``operator``: str ("<", ">", "<=", ">=", "==", "crosses_above", "crosses_below")
        - ``value``: float (threshold)
        - ``params``: dict (indicator parameters, e.g. {"period": 14})
        - ``field``: str (optional, for composite indicators like MACD — "macd", "signal", "histogram")
    indicator_values : dict
        Output from ``compute_indicators``.

    Returns
    -------
    tuple[bool, list[str]]
        (all_passed, reasons) where reasons list describes each condition result.
    """
    if not conditions:
        return (False, ["No conditions defined"])

    reasons: list[str] = []
    all_passed = True

    for cond in conditions:
        cond.get("indicator", "UNKNOWN")
        operator = cond.get("operator", ">")
        compare_to = cond.get("compare_to", "").upper()

        current, previous, key = _resolve_indicator_value(cond, indicator_values)

        if current is None:
            reasons.append(f"{key}: no data available")
            all_passed = False
            continue

        # Resolve threshold: static value or dynamic (PRICE, another indicator)
        if compare_to == "PRICE":
            threshold = float(indicator_values.get("CLOSE", 0))
        elif compare_to and compare_to in indicator_values:
            threshold = float(indicator_values[compare_to])
        else:
            threshold = float(cond.get("value", 0))

        passed = _compare(current, operator, threshold, previous)

        if passed:
            reasons.append(f"{key} {operator} {threshold} -> {current:.4f} PASS")
        else:
            reasons.append(f"{key} {operator} {threshold} -> {current:.4f} FAIL")
            all_passed = False

    return (all_passed, reasons)
