"""Hard blockers and soft guardrails for trade safety."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime

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

    # Circuit breaker: market-wide crash protection
    try:
        import yfinance as yf
        spy = yf.Ticker("SPY")
        hist = spy.history(period="1d", interval="1m")
        if len(hist) >= 2:
            open_price = hist["Open"].iloc[0]
            current_price = hist["Close"].iloc[-1]
            intraday_change_pct = ((current_price - open_price) / open_price) * 100
            if intraday_change_pct < -7.0:
                result.blocked = True
                result.reasons.append(
                    f"Circuit breaker: SPY down {abs(intraday_change_pct):.1f}% intraday (>7% threshold). All new entries blocked."
                )
    except Exception:
        pass  # Don't block on data fetch failure — handled by API failure gate

    # Liquidity check
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        info = ticker.fast_info
        volume = getattr(info, "last_volume", None)
        if volume is not None and volume < 10_000:
            result.blocked = True
            result.reasons.append(
                f"Liquidity block: {symbol} volume {volume:,} is below 10,000 minimum."
            )
        # Check bid-ask spread if available
        bid = getattr(info, "bid", None) or (ticker.info or {}).get("bid")
        ask = getattr(info, "ask", None) or (ticker.info or {}).get("ask")
        if bid and ask and bid > 0:
            spread_pct = ((ask - bid) / bid) * 100
            if spread_pct > 2.0:
                result.blocked = True
                result.reasons.append(
                    f"Liquidity block: {symbol} spread {spread_pct:.1f}% exceeds 2% maximum."
                )
    except Exception:
        pass

    # API failure gate: don't trade blind
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="1d")
        if hist.empty:
            result.blocked = True
            result.reasons.append(
                f"API failure: Cannot fetch market data for {symbol}. Pausing evaluation."
            )
    except Exception as e:
        result.blocked = True
        result.reasons.append(
            f"API failure: Market data unreachable for {symbol} ({e}). Pausing evaluation."
        )

    return result

def check_soft_guardrails(
    vix: float | None,
    events: list[dict],
    symbol: str,
    ai_confidence: float = 1.0,
    consecutive_losses: int = 0,
    override_level: str = "soft",
    open_positions: list[dict] | None = None,
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

    # Correlation risk: check cross-bot sector exposure
    if open_positions:
        try:
            import yfinance as yf
            ticker_info = yf.Ticker(symbol).info or {}
            sector = ticker_info.get("sector", "")
            if sector:
                # Count distinct bots with open positions in the same sector
                bots_in_sector: set[str] = set()
                for pos in open_positions:
                    pos_sector = pos.get("sector", "")
                    pos_bot_id = pos.get("bot_id", "")
                    if pos_sector == sector and pos_bot_id:
                        bots_in_sector.add(pos_bot_id)
                if len(bots_in_sector) >= 2:
                    result.reduce_size = min(result.reduce_size, 0.5)
                    result.reasons.append(
                        f"Correlation risk: {len(bots_in_sector)} bots already have open positions in {sector}. Size capped at 50%."
                    )
        except Exception:
            pass  # Don't penalize on lookup failure

    return result
