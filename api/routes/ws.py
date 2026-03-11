"""
WebSocket endpoint for real-time market data streaming.

ws://localhost:8000/ws/market?token=<JWT>

Protocol:
  Client → Server:  {"subscribe": ["AAPL", "TSLA"]}
                    {"unsubscribe": ["AAPL"]}
  Server → Client:  {"type": "price_update", "data": {symbol, price, bid, ask, ...}}
                    {"type": "connected", "message": "..."}
                    {"type": "error", "message": "..."}

On connect, the server immediately fetches quotes for subscribed symbols
then streams Redis pub/sub updates as they arrive.
"""

import asyncio
import json
from typing import Optional

import jwt
import redis.asyncio as aioredis
import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from config.settings import get_settings
from data.market_data import market_data

logger = structlog.get_logger(__name__)
router = APIRouter()

# Active subscriptions: ws_id -> set of symbols
_subscriptions: dict[int, set] = {}


def _decode_token(token: str) -> Optional[int]:
    try:
        settings = get_settings()
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        return payload.get("user_id")
    except Exception:
        return None


@router.websocket("/market")
async def ws_market(websocket: WebSocket, token: str = Query("")):
    # Auth
    user_id = _decode_token(token)
    if not user_id:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    await websocket.accept()
    ws_id = id(websocket)
    subscribed: set[str] = set()
    _subscriptions[ws_id] = subscribed
    settings = get_settings()
    stop_event = asyncio.Event()

    await websocket.send_json({"type": "connected", "message": "Market data stream ready"})
    logger.info("ws_client_connected", user_id=user_id)

    async def redis_listener():
        """Subscribe to Redis market:price_updates and forward to this WebSocket."""
        r = None
        pubsub = None
        try:
            r = aioredis.from_url(settings.redis_url, decode_responses=True)
            pubsub = r.pubsub()
            await pubsub.subscribe("market:price_updates")
            while not stop_event.is_set():
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=1.0,
                )
                if not message:
                    continue
                try:
                    data = json.loads(message["data"])
                    symbol = data.get("symbol", "")
                    if symbol in subscribed:
                        await websocket.send_json({"type": "price_update", "data": data})
                except Exception:
                    pass
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.debug("ws_redis_listener_error", error=str(e))
        finally:
            if pubsub is not None:
                try:
                    await pubsub.unsubscribe("market:price_updates")
                    await pubsub.aclose()
                except Exception:
                    pass
            if r is not None:
                try:
                    await r.aclose()
                except Exception:
                    pass

    async def message_handler():
        """Handle subscription messages from the client."""
        try:
            while not stop_event.is_set():
                raw = await websocket.receive_text()
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                if "subscribe" in msg:
                    new_symbols = [s.upper() for s in msg["subscribe"] if s]
                    subscribed.update(new_symbols)
                    # Immediately push current quotes for newly subscribed symbols
                    for sym in new_symbols:
                        quote = await market_data.get_quote(sym)
                        if quote:
                            await websocket.send_json({"type": "price_update", "data": quote})

                if "unsubscribe" in msg:
                    for sym in msg["unsubscribe"]:
                        subscribed.discard(sym.upper())

        except WebSocketDisconnect:
            stop_event.set()
        except Exception as e:
            stop_event.set()
            logger.debug("ws_message_handler_error", error=str(e))

    async def poll_subscribed():
        """For symbols without a streaming source, poll every 10 seconds."""
        while not stop_event.is_set():
            await asyncio.sleep(10)
            if stop_event.is_set() or not subscribed:
                continue
            for sym in list(subscribed):
                try:
                    quote = await market_data.get_quote(sym)
                    if quote:
                        await websocket.send_json({"type": "price_update", "data": quote})
                except Exception:
                    pass

    try:
        listener_task = asyncio.create_task(redis_listener())
        poll_task = asyncio.create_task(poll_subscribed())
        await message_handler()
    except WebSocketDisconnect:
        pass
    finally:
        stop_event.set()
        for task in (listener_task, poll_task):
            task.cancel()
        await asyncio.gather(listener_task, poll_task, return_exceptions=True)
        _subscriptions.pop(ws_id, None)
        logger.info("ws_client_disconnected", user_id=user_id)
