"""Focused tests for the current FastAPI auth helpers and profile route."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from api.routes.auth import (
    ProfileUpdateRequest,
    _check_password,
    _hash_password,
    _validate_email,
    _validate_password,
    update_profile,
)


def _make_request(user_id: int = 1):
    req = MagicMock()
    req.state.user_id = user_id
    return req


def _mock_session(user):
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = user
    db.execute = AsyncMock(return_value=result)
    db.__aenter__ = AsyncMock(return_value=db)
    db.__aexit__ = AsyncMock(return_value=False)
    return db


def test_hash_password_returns_bcrypt_string():
    hashed = _hash_password("testpassword")
    assert hashed.startswith("$2")
    assert len(hashed) > 50


def test_check_password_correct():
    hashed = _hash_password("mypassword")
    assert _check_password("mypassword", hashed) is True


def test_check_password_incorrect():
    hashed = _hash_password("mypassword")
    assert _check_password("wrongpassword", hashed) is False


def test_validate_email_normalizes_case():
    assert _validate_email(" User@Example.com ") == "user@example.com"


def test_validate_email_rejects_invalid():
    with pytest.raises(HTTPException) as exc_info:
        _validate_email("not-an-email")
    assert exc_info.value.status_code == 400


def test_validate_password_rejects_short_values():
    with pytest.raises(HTTPException) as exc_info:
        _validate_password("short")
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_update_profile_requires_current_password_for_password_change():
    user = MagicMock()
    user.id = 1
    user.email = "user@example.com"
    user.display_name = "User"
    user.is_admin = False
    user.email_verified = True
    user.password_hash = _hash_password("CurPass123!x")

    db = _mock_session(user)
    with (
        patch("api.routes.auth.get_session", return_value=db),
        pytest.raises(HTTPException) as exc_info,
    ):
        await update_profile(
            ProfileUpdateRequest(password="NewPass123!x"),
            _make_request(),
        )

    assert exc_info.value.status_code == 400
    assert "Current password is required" in exc_info.value.detail


@pytest.mark.asyncio
async def test_update_profile_changes_password_with_current_password():
    user = MagicMock()
    user.id = 1
    user.email = "user@example.com"
    user.display_name = "User"
    user.is_admin = False
    user.email_verified = True
    user.password_hash = _hash_password("CurPass123!x")

    db = _mock_session(user)
    with patch("api.routes.auth.get_session", return_value=db), \
         patch("api.routes.auth.encode_jwt", return_value="mock-jwt-token"):
        response = await update_profile(
            ProfileUpdateRequest(
                current_password="CurPass123!x",
                new_password="NewPass123!x",
            ),
            _make_request(),
        )

    # Response may be a JSONResponse (when password changes) or a dict
    import json
    if hasattr(response, "body"):
        body = json.loads(response.body)
        assert body["success"] is True
    else:
        assert response["success"] is True
    assert _check_password("NewPass123!x", user.password_hash) is True
