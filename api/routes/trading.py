"""
Trading endpoints — execute signals, manage positions, view orders.

Routes delegate to the user's Webull client when Webull credentials exist,
otherwise fall back to the Alpaca-based ExecutionEngine.
"""

from typing import Optional

import structlog
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from sqlalchemy import select

from config.settings import get_settings, TradingMode
from db.database import get_session
from db.models import PaperPortfolio, PaperPosition, Trade, TradingModeEnum, SystemEventType
from risk.manager import RiskManager
from services.event_logger import log_event

# Webull per-user client loader (from our webull routes)
from api.routes.webull import _get_user_clients as _get_user_webull_client

logger = structlog.get_logger(__name__)

router = APIRouter()

_risk_manager = RiskManager()
_executor = None


def _get_executor():
    """Lazy-init the Alpaca ExecutionEngine (fallback when no Webull creds)."""
    global _executor
    if _executor is None:
        from engine.executor import ExecutionEngine
        _executor = ExecutionEngine(risk_manager=_risk_manager)
    return _executor


class ExecuteSignalRequest(BaseModel):
    symbol: str
    direction: str  # "long", "short", "flat" or "BUY", "SELL"
    strength: float = 1.0
    quantity: float = 10.0
    model_name: str = "manual"
    order_type: str = "market"
    limit_price: Optional[float] = None
    user_confirmed: bool = False


class SwitchModeRequest(BaseModel):
    mode: str  # "paper", "live", "backtest"


# ── Core trading routes (Webull-aware) ───────────────────────────────────


@router.get("/account")
async def get_account(request: Request):
    """Get current account information — routes by active trading mode."""
    user_id = getattr(request.state, "user_id", None)
    mode = getattr(request.state, "trading_mode", TradingModeEnum.PAPER)

    if user_id and mode == TradingModeEnum.LIVE:
        # Live mode — use Webull broker
        client = await _get_user_webull_client(user_id)
        if client:
            summary = client.get_account_summary()
            if summary:
                return {
                    "equity": summary.get("net_liquidation", 0),
                    "cash": summary.get("cash_balance", 0),
                    "buying_power": summary.get("buying_power", 0),
                    "portfolio_value": summary.get("total_market_value", 0),
                    "unrealized_pnl": summary.get("unrealized_pnl", 0),
                    "realized_pnl": summary.get("realized_pnl", 0),
                    "account_id": summary.get("account_id"),
                    "mode": "LIVE",
                    "broker": "webull",
                }
            # Evict stale cache so next request re-authenticates with current DB credentials
            from api.routes.webull import _client_cache
            _client_cache.pop(user_id, None)
            logger.warning("webull_account_fetch_failed_evicting_cache", user_id=user_id)
            raise HTTPException(status_code=503, detail="Could not fetch Webull account. Your API key may be invalid — please re-enter it in Settings.")

    # Paper mode or no broker — use paper portfolio
    if user_id:
        async with get_session() as session:
            result = await session.execute(
                select(PaperPortfolio).where(PaperPortfolio.user_id == user_id)
            )
            portfolio = result.scalar_one_or_none()

            if not portfolio:
                # Auto-create paper portfolio for users without a broker
                portfolio = PaperPortfolio(
                    user_id=user_id,
                    cash=1_000_000.0,
                    initial_capital=1_000_000.0,
                )
                session.add(portfolio)
                await session.flush()

            # Sum positions value
            pos_result = await session.execute(
                select(PaperPosition).where(PaperPosition.portfolio_id == portfolio.id)
            )
            positions = pos_result.scalars().all()
            positions_value = sum(
                (p.current_price or p.avg_entry_price) * p.quantity for p in positions
            )

            return {
                "equity": portfolio.cash + positions_value,
                "cash": portfolio.cash,
                "buying_power": portfolio.cash,
                "portfolio_value": positions_value,
                "broker": "paper",
                "mode": mode.value.upper(),
            }

    try:
        return _get_executor().get_account()
    except Exception:
        raise HTTPException(status_code=503, detail="No broker connected")


@router.get("/positions")
async def get_positions(request: Request):
    """Get all open positions — routes by active trading mode."""
    user_id = getattr(request.state, "user_id", None)
    mode = getattr(request.state, "trading_mode", TradingModeEnum.PAPER)

    if user_id and mode == TradingModeEnum.LIVE:
        client = await _get_user_webull_client(user_id)
        if client:
            raw = client.get_positions()
            positions = []
            for p in raw:
                positions.append({
                    "symbol": p.get("symbol", ""),
                    "quantity": p.get("quantity", 0),
                    "avg_entry_price": p.get("avg_cost", p.get("cost_price", 0)),
                    "current_price": p.get("last_price", p.get("market_price", 0)),
                    "market_value": p.get("market_value", 0),
                    "unrealized_pnl": p.get("unrealized_pnl", 0),
                    "unrealized_pnl_pct": p.get("unrealized_pnl_pct", 0),
                })
            return {"positions": positions, "mode": "live"}

    # Paper/backtest mode — paper positions for authenticated users
    if user_id:
        from api.routes.paper_trading import get_paper_positions
        result = await get_paper_positions(request)
        if isinstance(result, dict):
            result["mode"] = mode.value
        return result

    try:
        return _get_executor().get_positions()
    except Exception:
        raise HTTPException(status_code=503, detail="No broker connected")


@router.get("/orders")
async def get_orders(request: Request, status: str = "open"):
    """Get orders — routes by active trading mode."""
    user_id = getattr(request.state, "user_id", None)
    mode = getattr(request.state, "trading_mode", TradingModeEnum.PAPER)

    if user_id and mode == TradingModeEnum.LIVE:
        client = await _get_user_webull_client(user_id)
        if client:
            raw = client.get_open_orders()
            orders = []
            for o in raw:
                orders.append({
                    "id": o.get("client_order_id", o.get("order_id", "")),
                    "symbol": o.get("symbol", ""),
                    "direction": o.get("side", "").lower(),
                    "quantity": o.get("quantity", o.get("total_quantity", 0)),
                    "order_type": o.get("order_type", "MKT"),
                    "status": o.get("status", "unknown"),
                    "filled_price": o.get("filled_price"),
                    "submitted_at": o.get("place_time", o.get("created_at", "")),
                })
            return {"orders": orders, "mode": "live"}

    # Paper mode — no open orders mechanism yet, return empty
    if user_id and mode == TradingModeEnum.PAPER:
        return {"orders": [], "mode": "paper"}

    try:
        return _get_executor().get_orders(status=status)
    except Exception as e:
        logger.warning("get_orders_failed", error=str(e))
        return {"orders": []}


@router.get("/quotes")
async def get_quotes(
    request: Request,
    symbols: str = Query(default="SPY,QQQ,AAPL,TSLA,NVDA,MSFT"),
):
    """Get stock quotes — uses Webull if connected, fallback to unofficial SDK."""
    symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    user_id = getattr(request.state, "user_id", None)

    if user_id:
        client = await _get_user_webull_client(user_id)
        if client:
            raw = client.get_quotes(symbol_list)
            quotes = []
            for sym in symbol_list:
                q = raw.get(sym, {})
                if q:
                    quotes.append({
                        "symbol": sym,
                        "price": q.get("price", q.get("close", 0)),
                        "change": q.get("change", 0),
                        "change_pct": q.get("change_pct", 0),
                        "volume": q.get("volume", 0),
                        "high": q.get("high", 0),
                        "low": q.get("low", 0),
                        "open": q.get("open", 0),
                        "prev_close": q.get("prev_close", 0),
                    })
            return {"quotes": quotes}

    # Fallback: unofficial webull SDK (no auth needed)
    try:
        from webull import webull
        wb = webull()
        quotes = []
        for sym in symbol_list:
            raw = wb.get_quote(sym)
            if raw:
                quotes.append({
                    "symbol": sym,
                    "price": float(raw.get("close", 0)),
                    "change": float(raw.get("change", 0)),
                    "change_pct": float(raw.get("changeRatio", 0)) * 100,
                    "volume": int(float(raw.get("volume", 0))),
                    "high": float(raw.get("high", 0)),
                    "low": float(raw.get("low", 0)),
                    "open": float(raw.get("open", 0)),
                    "prev_close": float(raw.get("preClose", 0)),
                })
        return {"quotes": quotes}
    except Exception as e:
        logger.warning("quote_fallback_failed", error=str(e))
        return {"quotes": []}


@router.get("/quote")
async def get_single_quote(request: Request, symbol: str = Query(...)):
    """Get a single stock quote (used by the order form)."""
    result = await get_quotes(request, symbols=symbol)
    quotes = result.get("quotes", [])
    if quotes:
        return quotes[0]
    return {"symbol": symbol, "price": 0}


@router.post("/execute")
async def execute_signal(request: Request, req: ExecuteSignalRequest):
    """Execute a trade — routes by active trading mode."""
    user_id = getattr(request.state, "user_id", None)
    mode = getattr(request.state, "trading_mode", TradingModeEnum.PAPER)

    if user_id and mode == TradingModeEnum.LIVE:
        # Live mode — route to Webull
        client = await _get_user_webull_client(user_id)
        if client:
            # Map direction to Webull side
            side = req.direction.upper()
            if side in ("LONG", "BUY"):
                side = "BUY"
            elif side in ("SHORT", "SELL", "FLAT"):
                side = "SELL"

            order_type = "MKT" if req.order_type.lower() == "market" else "LMT"

            result = client.place_order(
                symbol=req.symbol.upper(),
                side=side,
                qty=int(req.quantity),
                order_type=order_type,
                limit_price=req.limit_price,
                user_confirmed=req.user_confirmed,
            )

            if result.get("blocked"):
                return {
                    "executed": False,
                    "blocked": True,
                    "reason": result.get("error", "Order requires user_confirmed=true"),
                    "mode": "live",
                }

            if result.get("success"):
                # Log the trade event
                await log_event(
                    user_id=user_id,
                    event_type=SystemEventType.TRADE_EXECUTED,
                    mode=TradingModeEnum.LIVE,
                    description=f"LIVE {side} {int(req.quantity)} {req.symbol.upper()}",
                )
                return {"executed": True, "mode": "live", **result}

            await log_event(
                user_id=user_id,
                event_type=SystemEventType.TRADE_FAILED,
                mode=TradingModeEnum.LIVE,
                description=f"LIVE order failed: {result.get('error', 'unknown')}",
            )
            raise HTTPException(
                status_code=400,
                detail=result.get("error", "Order failed"),
            )

    # Paper mode — route through paper trading for authenticated users
    if user_id and mode in (TradingModeEnum.PAPER, TradingModeEnum.BACKTEST):
        from api.routes.paper_trading import PaperTradeRequest, execute_paper_trade

        side = req.direction.upper()
        if side in ("LONG", "BUY"):
            side = "BUY"
        elif side in ("SHORT", "SELL", "FLAT"):
            side = "SELL"

        paper_req = PaperTradeRequest(
            symbol=req.symbol,
            side=side,
            quantity=req.quantity,
            user_confirmed=req.user_confirmed,
        )
        result = await execute_paper_trade(request, paper_req)

        await log_event(
            user_id=user_id,
            event_type=SystemEventType.TRADE_EXECUTED,
            mode=mode,
            description=f"PAPER {side} {int(req.quantity)} {req.symbol.upper()}",
        )

        if isinstance(result, dict):
            result["mode"] = mode.value
        return result

    # Last resort: Alpaca executor (no user context)
    from models.base import Signal
    from engine.executor import OrderType

    signal = Signal(
        symbol=req.symbol,
        direction=req.direction,
        strength=req.strength,
        model_name=req.model_name,
    )

    try:
        account = _get_executor().get_account()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Broker unavailable: {str(e)}")

    current_equity = account["equity"]
    positions = _get_executor().get_positions()
    current_exposure = sum(abs(float(p["market_value"])) for p in positions)

    current_price = req.limit_price or 0
    if current_price == 0:
        raise HTTPException(status_code=400, detail="Price required for execution")

    result = _get_executor().execute_signal(
        signal=signal,
        quantity=req.quantity,
        current_price=current_price,
        current_equity=current_equity,
        current_exposure=current_exposure,
        order_type=OrderType(req.order_type),
        limit_price=req.limit_price,
    )

    if result is None:
        raise HTTPException(status_code=422, detail="Trade rejected by risk management")

    return result


# ── Risk & utility routes ────────────────────────────────────────────────


@router.get("/risk-summary")
async def get_risk_summary(request: Request):
    """Get current risk status — scoped to active trading mode."""
    user_id = getattr(request.state, "user_id", None)
    mode = getattr(request.state, "trading_mode", TradingModeEnum.PAPER)

    if user_id and mode == TradingModeEnum.LIVE:
        client = await _get_user_webull_client(user_id)
        if client:
            summary = client.get_account_summary()
            equity = summary.get("net_liquidation", 0) if summary else 0
            settings = get_settings()
            return {
                "is_halted": False,
                "current_drawdown_pct": 0.0,
                "max_drawdown_limit_pct": settings.max_drawdown_pct,
                "current_exposure_pct": 0.0,
                "max_exposure_limit_pct": settings.max_portfolio_exposure_pct,
                "trades_this_hour": 0,
                "max_trades_per_hour": settings.max_trades_per_hour,
                "equity": equity,
                "mode": "live",
            }
    try:
        account = _get_executor().get_account()
        summary = _risk_manager.get_risk_summary(account["equity"])
        summary["mode"] = mode.value
        return summary
    except Exception:
        settings = get_settings()
        return {
            "is_halted": False,
            "halt_reason": None,
            "current_drawdown_pct": 0.0,
            "max_drawdown_limit": settings.max_drawdown_pct,
            "max_drawdown_limit_pct": settings.max_drawdown_pct,
            "current_exposure_pct": 0.0,
            "max_exposure_limit_pct": settings.max_portfolio_exposure_pct,
            "trades_last_hour": 0,
            "trades_this_hour": 0,
            "max_trades_per_hour": settings.max_trades_per_hour,
            "peak_equity": 0,
            "open_positions": 0,
            "recent_risk_events": 0,
            "mode": mode.value,
        }


@router.get("/trade-log")
async def get_trade_log(request: Request, limit: int = 100):
    """Get execution audit trail — filtered by active trading mode."""
    mode = getattr(request.state, "trading_mode", TradingModeEnum.PAPER)

    # Try database Trade records first (mode-scoped)
    async with get_session() as session:
        result = await session.execute(
            select(Trade)
            .where(Trade.mode == mode)
            .order_by(Trade.entry_time.desc())
            .limit(limit)
        )
        trades = result.scalars().all()

        if trades:
            return {
                "trades": [
                    {
                        "id": t.id,
                        "symbol": t.symbol,
                        "direction": t.direction.value if hasattr(t.direction, "value") else str(t.direction),
                        "quantity": t.quantity,
                        "entry_price": t.entry_price,
                        "exit_price": t.exit_price,
                        "pnl": t.pnl,
                        "pnl_pct": t.pnl_pct,
                        "status": t.status.value if hasattr(t.status, "value") else str(t.status),
                        "entry_time": t.entry_time.isoformat() if t.entry_time else None,
                        "exit_time": t.exit_time.isoformat() if t.exit_time else None,
                    }
                    for t in trades
                ],
                "mode": mode.value,
            }

    # Fallback to executor log
    try:
        return _get_executor().get_trade_log(limit=limit)
    except Exception:
        return {"trades": [], "mode": mode.value}


@router.post("/switch-mode")
async def switch_mode(req: SwitchModeRequest):
    """Switch trading mode (paper/live)."""
    try:
        mode = TradingMode(req.mode)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid mode: {req.mode}")
    _get_executor().switch_mode(mode)
    return {"status": "switched", "mode": mode.value}


@router.get("/risk-events")
async def get_risk_events(limit: int = 50):
    """Get recent risk events."""
    return _risk_manager.get_risk_events(limit=limit)


@router.post("/resume-trading")
async def resume_trading():
    """Resume trading after a halt."""
    _risk_manager.resume_trading()
    return {"status": "resumed"}


@router.get("/verify")
async def verify_transactions():
    """Run transaction verification."""
    from services.security.verification import TransactionVerifier
    verifier = TransactionVerifier()
    try:
        report = verifier.verify_execution(_executor)
        return report
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Verification failed: {str(e)}")


@router.get("/bars")
async def get_bars(symbol: str, timeframe: str = "1D", limit: int = 100, request: Request = None):
    """OHLCV bar data for a symbol. Returns yfinance data as fallback when broker unavailable."""
    try:
        import yfinance as yf
        period_map = {"1m": "1d", "5m": "5d", "15m": "5d", "1h": "1mo", "1D": "1y", "1W": "5y"}
        interval_map = {"1m": "1m", "5m": "5m", "15m": "15m", "1h": "1h", "1D": "1d", "1W": "1wk"}
        period = period_map.get(timeframe, "1y")
        interval = interval_map.get(timeframe, "1d")
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period=period, interval=interval)
        if hist.empty:
            return {"symbol": symbol, "bars": []}
        bars = []
        for ts, row in hist.iterrows():
            bars.append({
                "time": int(ts.timestamp()),
                "open": round(float(row["Open"]), 4),
                "high": round(float(row["High"]), 4),
                "low": round(float(row["Low"]), 4),
                "close": round(float(row["Close"]), 4),
                "volume": int(row["Volume"]),
            })
        return {"symbol": symbol, "timeframe": timeframe, "bars": bars[-limit:]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/portfolio-analytics")
async def get_portfolio_analytics(request: Request, symbols: Optional[str] = None):
    """Generate portfolio risk analytics report."""
    import pandas as pd
    from risk.analytics import PortfolioRiskAnalyzer
    analyzer = PortfolioRiskAnalyzer()

    # Get positions (Webull-aware)
    pos_data = await get_positions(request)
    positions = pos_data.get("positions", pos_data) if isinstance(pos_data, dict) else pos_data

    if symbols:
        requested = {s.strip().upper() for s in symbols.split(",")}
        positions = [p for p in positions if p.get("symbol", "").upper() in requested]

    if not positions:
        return analyzer.generate_risk_report([], pd.DataFrame())

    return analyzer.generate_risk_report(positions, pd.DataFrame())
