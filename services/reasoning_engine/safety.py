"""Hard blockers and soft guardrails for trade safety."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timedelta

VIX_THRESHOLDS = {
    "normal": (0, 18),
    "elevated": (18, 25),
    "high": (25, 40),
    "extreme": (40, float("inf")),
}

def classify_vix(vix: float) -> str:
    for label, (lo, hi) in VIX_THRESHOLDS.items():
        if lo <= vix < hi:
            return label
    return "extreme"

@dataclass
class SafetyResult:
    blocked: bool = False
    reduce_size: float = 1.0
    delay_seconds: int = 0
    reasons: list[str] = field(default_factory=list)
    model_used: str = "safety_rules"

def check_hard_blockers(
    vix: float | None,
    events: list[dict],
    symbol: str,
    portfolio_exposure: float = 0.0,
    daily_pnl_pct: float = 0.0,
) -> SafetyResult:
    """Check hard blockers — always enforced, no override."""
    result = SafetyResult()

    if vix is not None and vix > 40:
        result.blocked = True
        result.reasons.append(f"VIX extreme ({vix:.1f}) — new entries blocked")

    now = datetime.utcnow()
    for evt in events:
        if evt.get("event_type") == "macro":
            raw = evt.get("raw_data", {})
            event_time_str = raw.get("event_time")
            if event_time_str and "FOMC" in evt.get("headline", "").upper():
                try:
                    event_time = datetime.fromisoformat(event_time_str)
                    if 0 < (event_time - now).total_seconds() < 1800:
                        result.blocked = True
                        result.reasons.append("FOMC within 30 minutes — entries blocked")
                except (ValueError, TypeError):
                    pass

        if evt.get("event_type") == "earnings":
            evt_symbols = evt.get("symbols", [])
            if symbol.upper() in [s.upper() for s in evt_symbols]:
                raw = evt.get("raw_data", {})
                report_time_str = raw.get("report_time")
                if report_time_str:
                    try:
                        report_time = datetime.fromisoformat(report_time_str)
                        if 0 < (report_time - now).total_seconds() < 3600:
                            result.blocked = True
                            result.reasons.append(f"Earnings for {symbol} within 1 hour")
                    except (ValueError, TypeError):
                        pass

    if portfolio_exposure > 0.25:
        result.blocked = True
        result.reasons.append(f"Position concentration {portfolio_exposure:.0%} exceeds 25%")

    if daily_pnl_pct < -5.0:
        result.blocked = True
        result.reasons.append(f"Daily loss {daily_pnl_pct:.1f}% exceeds -5% limit — bot paused")

    return result

def check_soft_guardrails(
    vix: float | None,
    events: list[dict],
    symbol: str,
    ai_confidence: float = 1.0,
    consecutive_losses: int = 0,
    override_level: str = "soft",
) -> SafetyResult:
    """Check soft guardrails — respect bot's override_level."""
    result = SafetyResult()

    if override_level == "advisory":
        return result  # Log only, don't modify

    if vix is not None and 25 <= vix <= 40:
        result.reduce_size = min(result.reduce_size, 0.5)
        result.reasons.append(f"VIX high ({vix:.1f}) — size reduced 50%")

    for evt in events:
        if evt.get("impact") == "HIGH":
            evt_symbols = evt.get("symbols", [])
            if symbol.upper() in [s.upper() for s in evt_symbols] or not evt_symbols:
                result.delay_seconds = max(result.delay_seconds, 900)
                result.reasons.append(f"HIGH impact event pending: {evt.get('headline', 'unknown')}")

    if ai_confidence < 0.3:
        result.reduce_size = min(result.reduce_size, 0.5)
        result.delay_seconds = max(result.delay_seconds, 300)
        result.reasons.append(f"Low AI confidence ({ai_confidence:.2f})")

    if consecutive_losses >= 3:
        result.reduce_size = min(result.reduce_size, 0.5)
        result.reasons.append(f"Losing streak ({consecutive_losses} consecutive losses)")

    return result
