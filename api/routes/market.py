"""
Market data REST routes.

GET /api/market/quote/{symbol}          — live quote (Redis-cached, 5s TTL)
GET /api/market/bars/{symbol}           — OHLCV bars  (Redis-cached, 60s TTL)
POST /api/market/batch-quotes           — multiple quotes in one call
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from data.market_data import market_data

router = APIRouter()


class BatchQuoteRequest(BaseModel):
    symbols: list[str]


@router.get("/quote/{symbol}")
async def get_quote(symbol: str):
    quote = await market_data.get_quote(symbol.upper())
    if not quote:
        raise HTTPException(status_code=503, detail=f"No price data available for {symbol}")
    return quote


@router.get("/bars/{symbol}")
async def get_bars(
    symbol: str,
    timeframe: str = Query("1D", description="1m 5m 15m 30m 1h 1D 1W"),
    limit: int = Query(100, ge=1, le=500),
):
    bars = await market_data.get_bars(symbol.upper(), timeframe, limit)
    if not bars:
        raise HTTPException(status_code=503, detail=f"No bar data available for {symbol}")
    return {"symbol": symbol.upper(), "timeframe": timeframe, "bars": bars}


@router.post("/batch-quotes")
async def batch_quotes(req: BatchQuoteRequest):
    if len(req.symbols) > 50:
        raise HTTPException(status_code=400, detail="Max 50 symbols per request")
    quotes = await market_data.get_batch_quotes(req.symbols)
    return {"quotes": quotes}
