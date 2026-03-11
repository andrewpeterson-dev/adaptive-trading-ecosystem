"""Targeted reliability tests for legacy trading routes."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_request(user_id: int | None = 1):
    req = MagicMock()
    req.state.user_id = user_id
    return req


@pytest.mark.asyncio
async def test_switch_mode_delegates_to_user_mode_for_authenticated_users():
    from api.routes.trading import SwitchModeRequest, switch_mode

    with patch("api.routes.user_mode.set_mode", new_callable=AsyncMock) as mock_set_mode:
        mock_set_mode.return_value = {"mode": "live", "previous": "paper"}
        response = await switch_mode(SwitchModeRequest(mode="live"), _make_request())

    assert response == {"status": "switched", "mode": "live", "previous": "paper"}
    mock_set_mode.assert_awaited_once()
