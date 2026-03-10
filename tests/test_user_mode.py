"""Tests for user trading mode endpoints (GET /mode, POST /set-mode)."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from db.models import TradingModeEnum, UserTradingSession


def _make_request(user_id: int = 1):
    """Build a fake Request with state.user_id set."""
    req = MagicMock()
    req.state.user_id = user_id
    return req


def _mock_session(scalar_return=None):
    """Return an async context-manager mock for get_session()."""
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = scalar_return
    db.execute = AsyncMock(return_value=result)
    db.__aenter__ = AsyncMock(return_value=db)
    db.__aexit__ = AsyncMock(return_value=False)
    return db


# ── GET /mode ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_mode_returns_paper_when_no_session():
    from api.routes.user_mode import get_mode

    db = _mock_session(scalar_return=None)
    with patch("api.routes.user_mode.get_session", return_value=db):
        resp = await get_mode(_make_request())
    assert resp == {"mode": "paper"}


@pytest.mark.asyncio
async def test_get_mode_returns_existing_mode():
    from api.routes.user_mode import get_mode

    session_row = MagicMock()
    session_row.active_mode = TradingModeEnum.LIVE

    db = _mock_session(scalar_return=session_row)
    with patch("api.routes.user_mode.get_session", return_value=db):
        resp = await get_mode(_make_request())
    assert resp == {"mode": "live"}


# ── POST /set-mode ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_set_mode_creates_new_session():
    from api.routes.user_mode import set_mode, SetModeRequest

    db = _mock_session(scalar_return=None)
    with (
        patch("api.routes.user_mode.get_session", return_value=db),
        patch("api.routes.user_mode.log_event", new_callable=AsyncMock) as mock_log,
    ):
        resp = await set_mode(SetModeRequest(mode="live"), _make_request())

    assert resp["mode"] == "live"
    assert resp["previous"] == "paper"
    db.add.assert_called_once()
    mock_log.assert_awaited_once()


@pytest.mark.asyncio
async def test_set_mode_updates_existing_session():
    from api.routes.user_mode import set_mode, SetModeRequest

    session_row = MagicMock()
    session_row.active_mode = TradingModeEnum.PAPER

    db = _mock_session(scalar_return=session_row)
    with (
        patch("api.routes.user_mode.get_session", return_value=db),
        patch("api.routes.user_mode.log_event", new_callable=AsyncMock),
    ):
        resp = await set_mode(SetModeRequest(mode="live"), _make_request())

    assert resp["mode"] == "live"
    assert resp["previous"] == "paper"
    assert session_row.active_mode == TradingModeEnum.LIVE


@pytest.mark.asyncio
async def test_set_mode_rejects_invalid_mode():
    from api.routes.user_mode import set_mode, SetModeRequest
    from fastapi import HTTPException

    db = _mock_session()
    with (
        patch("api.routes.user_mode.get_session", return_value=db),
        patch("api.routes.user_mode.log_event", new_callable=AsyncMock),
        pytest.raises(HTTPException) as exc_info,
    ):
        await set_mode(SetModeRequest(mode="yolo"), _make_request())

    assert exc_info.value.status_code == 400
    assert "Invalid mode" in exc_info.value.detail


@pytest.mark.asyncio
async def test_set_mode_rejects_backtest():
    from api.routes.user_mode import set_mode, SetModeRequest
    from fastapi import HTTPException

    db = _mock_session()
    with (
        patch("api.routes.user_mode.get_session", return_value=db),
        patch("api.routes.user_mode.log_event", new_callable=AsyncMock),
        pytest.raises(HTTPException) as exc_info,
    ):
        await set_mode(SetModeRequest(mode="backtest"), _make_request())

    assert exc_info.value.status_code == 400
    assert "backtest" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_set_mode_logs_event():
    from api.routes.user_mode import set_mode, SetModeRequest
    from db.models import SystemEventType

    db = _mock_session(scalar_return=None)
    with (
        patch("api.routes.user_mode.get_session", return_value=db),
        patch("api.routes.user_mode.log_event", new_callable=AsyncMock) as mock_log,
    ):
        await set_mode(SetModeRequest(mode="live"), _make_request(user_id=42))

    mock_log.assert_awaited_once()
    call_kwargs = mock_log.call_args.kwargs
    assert call_kwargs["user_id"] == 42
    assert call_kwargs["event_type"] == SystemEventType.MODE_SWITCH
    assert call_kwargs["mode"] == TradingModeEnum.LIVE
