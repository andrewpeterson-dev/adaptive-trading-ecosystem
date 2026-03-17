"""Hard blockers and soft guardrails for trade safety."""
from __future__ import annotations
import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import structlog
from sqlalchemy import select, and_, func
from db.database import get_session

logger = structlog.get_logger(__name__)
VIX_THRESHOLDS = {"normal": (0, 18), "elevated": (18, 25), "high": (25, 40), "extreme": (40, float("inf"))}

def classify_vix(vix: float) -> str:
    for label, (lo, hi) in VIX_THRESHOLDS.items():
        if lo <= vix < hi:
            return label
    return "extreme"

DRAWDOWN_LEVEL_NONE = "none"
DRAWDOWN_LEVEL_REDUCE = "reduce"
DRAWDOWN_LEVEL_HALT = "halt"
DRAWDOWN_LEVEL_KILL_DAILY = "kill_daily"
DRAWDOWN_LEVEL_KILL_WEEKLY = "kill_weekly"

@dataclass
class DrawdownStatus:
    level: str = DRAWDOWN_LEVEL_NONE
    daily_pnl_pct: float = 0.0
    weekly_pnl_pct: float = 0.0
    size_multiplier: float = 1.0
    restrictions: List[str] = field(default_factory=list)

@dataclass
class SafetyResult:
    blocked: bool = False
    exits_only: bool = False
    reduce_size: float = 1.0
    delay_seconds: int = 0
    reasons: List[str] = field(default_factory=list)
    model_used: str = "safety_rules"
    drawdown_level: str = DRAWDOWN_LEVEL_NONE

async def get_drawdown_thresholds(user_id: int, mode: Optional[str] = None) -> Dict[str, float]:
    from db.models import UserRiskLimits, TradingModeEnum
    defaults: Dict[str, float] = {"drawdown_reduce_pct": -2.0, "drawdown_halt_pct": -4.0, "drawdown_kill_pct": -7.0, "weekly_drawdown_kill_pct": -10.0}
    try:
        mode_enum = TradingModeEnum.PAPER
        if isinstance(mode, str) and mode == "live":
            mode_enum = TradingModeEnum.LIVE
        elif mode is not None and not isinstance(mode, str):
            mode_enum = mode
        async with get_session() as session:
            result = await session.execute(select(UserRiskLimits).where(UserRiskLimits.user_id == user_id, UserRiskLimits.mode == mode_enum))
            limits = result.scalar_one_or_none()
            if limits:
                return {k: getattr(limits, k) if getattr(limits, k) is not None else defaults[k] for k in defaults}
    except Exception as e:
        logger.warning("drawdown_thresholds_fetch_error", user_id=user_id, error=str(e))
    return defaults

async def compute_weekly_pnl_pct(user_id: int) -> float:
    from db.models import PaperPortfolio, PaperTrade
    try:
        now = datetime.utcnow()
        start_of_week = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        async with get_session() as session:
            portfolio = (await session.execute(select(PaperPortfolio).where(PaperPortfolio.user_id == user_id))).scalar_one_or_none()
            if not portfolio or not portfolio.initial_capital:
                return 0.0
            result = await session.execute(select(func.sum(PaperTrade.pnl)).where(PaperTrade.user_id == user_id, PaperTrade.exit_time.is_not(None), PaperTrade.exit_time >= start_of_week))
            return float(result.scalar() or 0.0) / float(portfolio.initial_capital) * 100.0
    except Exception as e:
        logger.warning("weekly_pnl_calc_error", user_id=user_id, error=str(e))
        return 0.0

async def evaluate_drawdown_level(user_id: int, daily_pnl_pct: float = 0.0, mode: Optional[str] = None) -> DrawdownStatus:
    thresholds = await get_drawdown_thresholds(user_id, mode=mode)
    weekly_pnl_pct = await compute_weekly_pnl_pct(user_id)
    status = DrawdownStatus(daily_pnl_pct=daily_pnl_pct, weekly_pnl_pct=weekly_pnl_pct)
    if weekly_pnl_pct <= thresholds["weekly_drawdown_kill_pct"]:
        status.level, status.size_multiplier = DRAWDOWN_LEVEL_KILL_WEEKLY, 0.0
        status.restrictions.append(f"Weekly P&L {weekly_pnl_pct:.1f}% breached {thresholds['weekly_drawdown_kill_pct']:.1f}%")
        return status
    if daily_pnl_pct <= thresholds["drawdown_kill_pct"]:
        status.level, status.size_multiplier = DRAWDOWN_LEVEL_KILL_DAILY, 0.0
        status.restrictions.append(f"Daily P&L {daily_pnl_pct:.1f}% breached {thresholds['drawdown_kill_pct']:.1f}%")
        return status
    if daily_pnl_pct <= thresholds["drawdown_halt_pct"]:
        status.level, status.size_multiplier = DRAWDOWN_LEVEL_HALT, 0.0
        status.restrictions.append(f"Daily P&L {daily_pnl_pct:.1f}% breached {thresholds['drawdown_halt_pct']:.1f}%")
        return status
    if daily_pnl_pct <= thresholds["drawdown_reduce_pct"]:
        status.level, status.size_multiplier = DRAWDOWN_LEVEL_REDUCE, 0.5
        status.restrictions.append(f"Daily P&L {daily_pnl_pct:.1f}% breached {thresholds['drawdown_reduce_pct']:.1f}%")
        return status
    return status

_SECTOR_MAP: Dict[str, str] = {"AAPL": "Technology", "MSFT": "Technology", "GOOGL": "Technology", "GOOG": "Technology", "META": "Technology", "AMZN": "Consumer Cyclical", "TSLA": "Consumer Cyclical", "NVDA": "Technology", "AMD": "Technology", "INTC": "Technology", "CRM": "Technology", "NFLX": "Communication Services", "JPM": "Financial Services", "BAC": "Financial Services", "GS": "Financial Services", "JNJ": "Healthcare", "PFE": "Healthcare", "UNH": "Healthcare", "XOM": "Energy", "CVX": "Energy", "PG": "Consumer Defensive", "KO": "Consumer Defensive", "WMT": "Consumer Defensive", "CAT": "Industrials", "BA": "Industrials", "SPY": "ETF", "QQQ": "ETF", "IWM": "ETF", "DIA": "ETF"}

async def get_sector_for_symbol(symbol: str) -> str:
    upper = symbol.upper()
    if upper in _SECTOR_MAP:
        return _SECTOR_MAP[upper]
    try:
        import yfinance as yf
        loop = asyncio.get_event_loop()
        sector = await loop.run_in_executor(None, lambda s=upper: (yf.Ticker(s).info or {}).get("sector", "Unknown"))
        _SECTOR_MAP[upper] = sector
        return sector
    except Exception:
        return "Unknown"

async def check_sector_concentration(user_id: int, symbol: str, proposed_value: float, total_equity: float, sector_limit: float = 0.30) -> Tuple[bool, float, str]:
    if total_equity <= 0:
        return (True, proposed_value, "")
    target_sector = await get_sector_for_symbol(symbol)
    if target_sector in ("Unknown", "ETF"):
        return (True, proposed_value, "")
    from db.cerberus_models import CerberusTrade
    try:
        async with get_session() as session:
            rows = (await session.execute(select(CerberusTrade.symbol, CerberusTrade.quantity, CerberusTrade.entry_price).where(and_(CerberusTrade.user_id == user_id, CerberusTrade.exit_ts.is_(None))))).all()
        sector_value = sum(abs(float(qty or 0)) * float(price or 0) for sym, qty, price in rows if await get_sector_for_symbol(sym) == target_sector)
        remaining = total_equity * sector_limit - sector_value
        if sector_value + proposed_value > total_equity * sector_limit:
            if remaining <= 0:
                return (False, 0.0, f"Sector block: {target_sector} at {sector_value/total_equity:.0%}")
            return (False, remaining, f"Sector cap: {target_sector}, reduced to ${remaining:,.0f}")
        return (True, proposed_value, "")
    except Exception as e:
        logger.warning("sector_check_error", error=str(e))
        return (True, proposed_value, "")

async def calculate_kelly_position_size(bot_id: str, total_equity: float, kelly_fraction: float = 0.25, min_trades: int = 20, default_pct: float = 0.01) -> Tuple[float, str]:
    from db.cerberus_models import CerberusTrade
    if total_equity <= 0:
        return (0.0, "No equity")
    try:
        async with get_session() as session:
            trades = list((await session.execute(select(CerberusTrade).where(and_(CerberusTrade.bot_id == bot_id, CerberusTrade.exit_ts.is_not(None), CerberusTrade.return_pct.is_not(None))).order_by(CerberusTrade.exit_ts.desc()).limit(100))).scalars().all())
        if len(trades) < min_trades:
            return (default_pct, f"Insufficient history ({len(trades)}/{min_trades})")
        wins = [t for t in trades if (t.return_pct or 0) > 0]
        losses = [t for t in trades if (t.return_pct or 0) < 0]
        if not wins or not losses:
            return (default_pct, "Missing wins or losses")
        win_rate = len(wins) / len(trades)
        avg_win = sum(abs(t.return_pct) for t in wins) / len(wins)
        avg_loss = sum(abs(t.return_pct) for t in losses) / len(losses)
        if avg_loss <= 0:
            return (default_pct, "Avg loss zero")
        full_kelly = win_rate - ((1.0 - win_rate) / (avg_win / avg_loss))
        clamped = max(0.005, min(0.05, full_kelly * kelly_fraction))
        return (clamped, f"Kelly: wr={win_rate:.2f}, full={full_kelly:.3f}, clamped={clamped:.3f}")
    except Exception as e:
        logger.warning("kelly_error", bot_id=bot_id, error=str(e))
        return (default_pct, f"Kelly error")

async def update_category_scores(user_id: int, strategy_type: Optional[str] = None) -> None:
    from db.models import StrategyTypeScore, UserRiskLimits, TradingModeEnum
    from db.cerberus_models import CerberusTrade, CerberusBot, CerberusBotVersion
    try:
        block_threshold = 30.0
        try:
            async with get_session() as session:
                limits = (await session.execute(select(UserRiskLimits).where(UserRiskLimits.user_id == user_id, UserRiskLimits.mode == TradingModeEnum.PAPER))).scalar_one_or_none()
                if limits and limits.category_block_threshold is not None:
                    block_threshold = limits.category_block_threshold
        except Exception:
            pass
        async with get_session() as session:
            bot_configs = (await session.execute(select(CerberusBot.id, CerberusBotVersion.config_json).join(CerberusBotVersion, CerberusBot.current_version_id == CerberusBotVersion.id).where(CerberusBot.user_id == user_id))).all()
        bot_map = {bid: (cfg or {}).get("strategy_type", "manual") for bid, cfg in bot_configs}
        async with get_session() as session:
            all_trades = list((await session.execute(select(CerberusTrade).where(and_(CerberusTrade.user_id == user_id, CerberusTrade.exit_ts.is_not(None), CerberusTrade.return_pct.is_not(None))).order_by(CerberusTrade.exit_ts.desc()))).scalars().all())
        type_trades: Dict[str, List] = {}
        for t in all_trades:
            st = bot_map.get(t.bot_id, t.strategy_tag or "manual")
            if strategy_type and st != strategy_type:
                continue
            type_trades.setdefault(st, []).append(t)
        for st, trades in type_trades.items():
            if not trades:
                continue
            total = len(trades)
            wins = [t for t in trades if (t.return_pct or 0) > 0]
            wr = len(wins) / total if total else 0
            avg_ret = sum(t.return_pct or 0 for t in trades) / total
            roi_c = max(0, min(100, (avg_ret + 10) * 5)) * 0.40
            recent = trades[:10]
            trend_c = max(0, min(100, (sum(t.return_pct or 0 for t in recent) / len(recent) + 10) * 5)) * 0.25 if recent else 0
            sample_c = min(100, total / 50 * 100) * 0.20
            wr_c = wr * 100 * 0.15
            score = max(0, min(100, roi_c + trend_c + sample_c + wr_c))
            blocked = score < block_threshold
            async with get_session() as session:
                existing = (await session.execute(select(StrategyTypeScore).where(StrategyTypeScore.user_id == user_id, StrategyTypeScore.strategy_type == st))).scalar_one_or_none()
                if existing:
                    existing.score, existing.roi_component, existing.trend_component = score, roi_c, trend_c
                    existing.sample_size_component, existing.win_rate_component = sample_c, wr_c
                    existing.total_trades, existing.is_blocked, existing.updated_at = total, blocked, datetime.utcnow()
                else:
                    session.add(StrategyTypeScore(user_id=user_id, strategy_type=st, score=score, roi_component=roi_c, trend_component=trend_c, sample_size_component=sample_c, win_rate_component=wr_c, total_trades=total, is_blocked=blocked))
        logger.info("category_scores_updated", user_id=user_id, types=list(type_trades.keys()))
    except Exception as e:
        logger.warning("category_score_update_error", user_id=user_id, error=str(e))

async def get_category_scores(user_id: int) -> List[Dict]:
    from db.models import StrategyTypeScore
    try:
        async with get_session() as session:
            scores = list((await session.execute(select(StrategyTypeScore).where(StrategyTypeScore.user_id == user_id).order_by(StrategyTypeScore.score.desc()))).scalars().all())
        return [{"strategy_type": s.strategy_type, "score": round(s.score, 1), "roi_component": round(s.roi_component, 2), "trend_component": round(s.trend_component, 2), "sample_size_component": round(s.sample_size_component, 2), "win_rate_component": round(s.win_rate_component, 2), "total_trades": s.total_trades, "is_blocked": s.is_blocked, "updated_at": s.updated_at.isoformat() if s.updated_at else None} for s in scores]
    except Exception as e:
        logger.warning("category_scores_fetch_error", user_id=user_id, error=str(e))
        return []

async def is_strategy_type_blocked(user_id: int, strategy_type: str) -> Tuple[bool, Optional[float]]:
    from db.models import StrategyTypeScore
    try:
        async with get_session() as session:
            row = (await session.execute(select(StrategyTypeScore).where(StrategyTypeScore.user_id == user_id, StrategyTypeScore.strategy_type == strategy_type))).scalar_one_or_none()
        if row and row.is_blocked:
            return (True, row.score)
        return (False, row.score if row else None)
    except Exception:
        return (False, None)

async def check_hard_blockers(vix=None, events=None, symbol="", portfolio_exposure=0.0, daily_pnl_pct=0.0, user_id=None, weekly_pnl_pct=None, drawdown_thresholds=None):
    if events is None:
        events = []
    result = SafetyResult()
    if vix is not None and vix > 40:
        result.blocked = True
        result.reasons.append(f"VIX extreme ({vix:.1f})")
    now = datetime.utcnow()
    for evt in events:
        if evt.get("event_type") == "macro":
            ets = (evt.get("raw_data") or {}).get("event_time")
            if ets and "FOMC" in evt.get("headline", "").upper():
                try:
                    if 0 < (datetime.fromisoformat(ets) - now).total_seconds() < 1800:
                        result.blocked = True
                        result.reasons.append("FOMC within 30 minutes")
                except (ValueError, TypeError):
                    pass
        if evt.get("event_type") == "earnings" and symbol.upper() in [s.upper() for s in evt.get("symbols", [])]:
            rts = (evt.get("raw_data") or {}).get("report_time")
            if rts:
                try:
                    if 0 < (datetime.fromisoformat(rts) - now).total_seconds() < 3600:
                        result.blocked = True
                        result.reasons.append(f"Earnings for {symbol} within 1 hour")
                except (ValueError, TypeError):
                    pass
    if portfolio_exposure > 0.25:
        result.blocked = True
        result.reasons.append(f"Position concentration {portfolio_exposure:.0%} exceeds 25%")
    thresholds = drawdown_thresholds or {"drawdown_reduce_pct": -2.0, "drawdown_halt_pct": -4.0, "drawdown_kill_pct": -7.0, "weekly_drawdown_kill_pct": -10.0}
    if weekly_pnl_pct is not None and weekly_pnl_pct <= thresholds["weekly_drawdown_kill_pct"]:
        result.blocked, result.drawdown_level = True, DRAWDOWN_LEVEL_KILL_WEEKLY
        result.reasons.append(f"Weekly loss {weekly_pnl_pct:.1f}% exceeds {thresholds['weekly_drawdown_kill_pct']:.1f}%")
        return result
    if daily_pnl_pct <= thresholds["drawdown_kill_pct"]:
        result.blocked, result.drawdown_level = True, DRAWDOWN_LEVEL_KILL_DAILY
        result.reasons.append(f"Daily loss {daily_pnl_pct:.1f}% exceeds {thresholds['drawdown_kill_pct']:.1f}%")
        return result
    if daily_pnl_pct <= thresholds["drawdown_halt_pct"]:
        result.blocked, result.exits_only, result.drawdown_level = True, True, DRAWDOWN_LEVEL_HALT
        result.reasons.append(f"Daily loss {daily_pnl_pct:.1f}% exceeds {thresholds['drawdown_halt_pct']:.1f}%")
        return result
    if daily_pnl_pct <= thresholds["drawdown_reduce_pct"]:
        result.reduce_size, result.drawdown_level = min(result.reduce_size, 0.5), DRAWDOWN_LEVEL_REDUCE
        result.reasons.append(f"Daily loss {daily_pnl_pct:.1f}% exceeds {thresholds['drawdown_reduce_pct']:.1f}%")
    loop = asyncio.get_event_loop()
    try:
        import yfinance as yf
        hist = await loop.run_in_executor(None, lambda: yf.Ticker("SPY").history(period="1d", interval="1m"))
        if len(hist) >= 2:
            chg = ((hist["Close"].iloc[-1] - hist["Open"].iloc[0]) / hist["Open"].iloc[0]) * 100
            if chg < -7.0:
                result.blocked = True
                result.reasons.append(f"Circuit breaker: SPY down {abs(chg):.1f}%")
    except Exception:
        pass
    try:
        import yfinance as yf
        info, full = await loop.run_in_executor(None, lambda s=symbol: (yf.Ticker(s).fast_info, yf.Ticker(s).info or {}))
        vol = getattr(info, "last_volume", None)
        if vol is not None and vol < 10_000:
            result.blocked = True
            result.reasons.append(f"Low volume: {symbol} {vol:,}")
        bid = getattr(info, "bid", None) or full.get("bid")
        ask = getattr(info, "ask", None) or full.get("ask")
        if bid and ask and bid > 0 and ((ask - bid) / bid) * 100 > 2.0:
            result.blocked = True
            result.reasons.append(f"Wide spread: {symbol}")
    except Exception:
        pass
    try:
        import yfinance as yf
        hist = await loop.run_in_executor(None, lambda s=symbol: yf.Ticker(s).history(period="1d"))
        if hist.empty:
            result.blocked = True
            result.reasons.append(f"API failure: no data for {symbol}")
    except Exception as e:
        result.blocked = True
        result.reasons.append(f"API failure: {symbol} ({e})")
    return result

async def check_soft_guardrails(vix=None, events=None, symbol="", ai_confidence=1.0, consecutive_losses=0, override_level="soft", open_positions=None):
    if events is None:
        events = []
    result = SafetyResult()
    if override_level == "advisory":
        return result
    if vix is not None and 25 <= vix <= 40:
        result.reduce_size = min(result.reduce_size, 0.5)
        result.reasons.append(f"VIX high ({vix:.1f})")
    for evt in events:
        if evt.get("impact") == "HIGH":
            syms = evt.get("symbols", [])
            if symbol.upper() in [s.upper() for s in syms]:
                result.delay_seconds = max(result.delay_seconds, 900)
                result.reasons.append(f"HIGH impact: {evt.get('headline', '?')}")
            elif not syms:
                result.reduce_size = min(result.reduce_size, 0.75)
                result.reasons.append(f"HIGH impact (untargeted): {evt.get('headline', '?')}")
    if ai_confidence < 0.3:
        result.reduce_size = min(result.reduce_size, 0.5)
        result.delay_seconds = max(result.delay_seconds, 300)
        result.reasons.append(f"Low AI confidence ({ai_confidence:.2f})")
    if consecutive_losses >= 3:
        result.reduce_size = min(result.reduce_size, 0.5)
        result.reasons.append(f"Losing streak ({consecutive_losses})")
    if open_positions:
        try:
            import yfinance as yf
            ticker_info = await asyncio.get_event_loop().run_in_executor(None, lambda s=symbol: yf.Ticker(s).info or {})
            sector = ticker_info.get("sector", "")
            if sector:
                bots = {p["bot_id"] for p in open_positions if p.get("sector") == sector and p.get("bot_id")}
                if len(bots) >= 2:
                    result.reduce_size = min(result.reduce_size, 0.5)
                    result.reasons.append(f"Correlation: {len(bots)} bots in {sector}")
        except Exception:
            pass
    return result
