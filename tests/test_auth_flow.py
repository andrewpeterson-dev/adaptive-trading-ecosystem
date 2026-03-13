"""Route-level tests for account onboarding, session security, and recovery."""

from __future__ import annotations

from contextlib import asynccontextmanager
from urllib.parse import parse_qs, urlparse

import pytest
import pytest_asyncio
from cryptography.fernet import Fernet
from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from unittest.mock import patch

from api.middleware.auth import JWTAuthMiddleware
from api.routes.api_connections import (
    _sanitize_credentials,
    _sanitized_connection_test_error,
)
from api.routes.auth import hash_password, router as auth_router
from api.routes.strategies import router as strategies_router
from config.settings import get_settings
from db.database import Base
from db.models import ApiProvider, ApiProviderType, Strategy, User
from services.security.jwt_utils import decode_jwt
from services.security.rate_limit import rate_limiter

TEST_DB_URL = "sqlite+aiosqlite:///"


@pytest.fixture(autouse=True)
def _auth_test_settings(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "unit-test-secret-0123456789abcdef")
    monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("BASE_URL", "http://localhost:3000")
    monkeypatch.setenv("USE_SQLITE", "true")
    get_settings.cache_clear()
    rate_limiter._buckets.clear()
    yield
    rate_limiter._buckets.clear()
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def engine():
    engine = create_async_engine(
        TEST_DB_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def session_factory(engine):
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


def _extract_preview_token(preview_url: str | None, param: str = "token") -> str:
    assert preview_url
    query = parse_qs(urlparse(preview_url).query)
    values = query.get(param)
    assert values
    return values[0]


def _build_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(JWTAuthMiddleware)
    app.include_router(auth_router, prefix="/api/auth")

    @app.get("/api/protected")
    async def protected_get(request: Request):
        return {
            "user_id": request.state.user_id,
            "email": request.state.email,
        }

    @app.post("/api/protected")
    async def protected_post(request: Request):
        return {"ok": True, "user_id": request.state.user_id}

    return app


def _session_override(session_factory):
    @asynccontextmanager
    async def _mock_get_session():
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    return _mock_get_session


def _client(session_factory):
    app = _build_app()
    override = _session_override(session_factory)
    patches = (
        patch("api.routes.auth.get_session", override),
        patch("services.security.request_auth.get_session", override),
    )
    return app, patches


def _strategy_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(JWTAuthMiddleware)
    app.include_router(auth_router, prefix="/api/auth")
    app.include_router(strategies_router, prefix="/api")
    return app


def _strategy_client(session_factory):
    app = _strategy_app()
    override = _session_override(session_factory)
    patches = (
        patch("api.routes.auth.get_session", override),
        patch("services.security.request_auth.get_session", override),
        patch("api.routes.strategies.get_session", override),
    )
    return app, patches


def test_register_verify_login_logout_and_csrf(session_factory):
    app, patches = _client(session_factory)
    with patches[0], patches[1], TestClient(app) as client:
        register_response = client.post(
            "/api/auth/register",
            json={
                "email": "newuser@example.com",
                "password": "Strong-pass1!",
                "display_name": "New User",
            },
        )
        assert register_response.status_code == 202
        register_data = register_response.json()
        assert register_data["verification_required"] is True
        assert register_response.cookies.get("access_token") is None

        token = _extract_preview_token(register_data.get("development_verification_url"))
        verify_response = client.post("/api/auth/verify-email", json={"token": token})
        assert verify_response.status_code == 200

        login_response = client.post(
            "/api/auth/login",
            json={"email": "newuser@example.com", "password": "Strong-pass1!"},
        )
        assert login_response.status_code == 200
        access_token = client.cookies.get("access_token")
        csrf_token = client.cookies.get("csrf_token")
        assert access_token
        assert csrf_token

        protected_get = client.get("/api/protected")
        assert protected_get.status_code == 200
        assert protected_get.json()["email"] == "newuser@example.com"

        protected_post = client.post("/api/protected")
        assert protected_post.status_code == 403
        assert protected_post.json()["detail"] == "CSRF validation failed"

        protected_post_ok = client.post(
            "/api/protected",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert protected_post_ok.status_code == 200

        ws_token_response = client.post(
            "/api/auth/websocket-token",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert ws_token_response.status_code == 200
        ws_token = ws_token_response.json()["token"]
        assert decode_jwt(ws_token)["scope"] == "websocket"

        logout_response = client.post(
            "/api/auth/logout",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert logout_response.status_code == 200

        revoked_response = client.get(
            "/api/protected",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert revoked_response.status_code == 401
        assert revoked_response.json()["detail"] == "Session has expired"


def test_login_requires_verified_email(session_factory):
    app, patches = _client(session_factory)
    with patches[0], patches[1], TestClient(app) as client:
        register_response = client.post(
            "/api/auth/register",
            json={
                "email": "pending@example.com",
                "password": "Pending-pass1!",
                "display_name": "Pending User",
            },
        )
        assert register_response.status_code == 202

        login_response = client.post(
            "/api/auth/login",
            json={"email": "pending@example.com", "password": "Pending-pass1!"},
        )
        assert login_response.status_code == 403
        assert "verify your email" in login_response.json()["detail"].lower()


def test_password_reset_rotates_password_and_sessions(session_factory):
    app, patches = _client(session_factory)
    with patches[0], patches[1], TestClient(app) as client:
        register_response = client.post(
            "/api/auth/register",
            json={
                "email": "reset@example.com",
                "password": "Original-pass1!",
                "display_name": "Reset User",
            },
        )
        verify_token = _extract_preview_token(register_response.json().get("development_verification_url"))
        assert client.post("/api/auth/verify-email", json={"token": verify_token}).status_code == 200

        login_response = client.post(
            "/api/auth/login",
            json={"email": "reset@example.com", "password": "Original-pass1!"},
        )
        old_access_token = login_response.cookies.get("access_token")
        assert old_access_token

        reset_request = client.post(
            "/api/auth/password-reset/request",
            json={"email": "reset@example.com"},
        )
        assert reset_request.status_code == 200
        reset_token = _extract_preview_token(reset_request.json().get("development_reset_url"))

        confirm_response = client.post(
            "/api/auth/password-reset/confirm",
            json={"token": reset_token, "password": "Updated-pass1!"},
        )
        assert confirm_response.status_code == 200

        old_login = client.post(
            "/api/auth/login",
            json={"email": "reset@example.com", "password": "Original-pass1!"},
        )
        assert old_login.status_code == 401

        new_login = client.post(
            "/api/auth/login",
            json={"email": "reset@example.com", "password": "Updated-pass1!"},
        )
        assert new_login.status_code == 200

        revoked_response = client.get(
            "/api/protected",
            headers={"Authorization": f"Bearer {old_access_token}"},
        )
        assert revoked_response.status_code == 401
        assert revoked_response.json()["detail"] == "Session has expired"


@pytest.mark.asyncio
async def test_inactive_user_token_is_rejected(session_factory):
    app, patches = _client(session_factory)
    with patches[0], patches[1], TestClient(app) as client:
        register_response = client.post(
            "/api/auth/register",
            json={
                "email": "inactive@example.com",
                "password": "Inactive-pass1!",
                "display_name": "Inactive User",
            },
        )
        verify_token = _extract_preview_token(register_response.json().get("development_verification_url"))
        assert client.post("/api/auth/verify-email", json={"token": verify_token}).status_code == 200

        login_response = client.post(
            "/api/auth/login",
            json={"email": "inactive@example.com", "password": "Inactive-pass1!"},
        )
        access_token = login_response.cookies.get("access_token")
        assert access_token

        async with session_factory() as session:
            result = await session.get(User, 1)
            assert result is not None
            result.is_active = False
            await session.commit()

        rejected = client.get(
            "/api/protected",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert rejected.status_code == 403
        assert rejected.json()["detail"] == "Account is disabled"


def test_register_requires_email_delivery_when_preview_is_unavailable(session_factory, monkeypatch):
    monkeypatch.setenv("BASE_URL", "https://app.example.com")
    monkeypatch.setenv("USE_SQLITE", "false")
    monkeypatch.delenv("SMTP_USER", raising=False)
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)
    get_settings.cache_clear()

    app, patches = _client(session_factory)
    with patches[0], patches[1], TestClient(app) as client:
        response = client.post(
            "/api/auth/register",
            json={
                "email": "prod-user@example.com",
                "password": "Strong-pass1!",
                "display_name": "Prod User",
            },
        )
        assert response.status_code == 503
        assert "Email delivery" in response.json()["detail"]


def test_strategy_config_requires_admin(session_factory):
    app, patches = _strategy_client(session_factory)
    with patches[0], patches[1], patches[2], TestClient(app) as client:
        import asyncio

        async def seed_user():
            async with session_factory() as session:
                user = User(
                    email="member@example.com",
                    password_hash=hash_password("Member-pass1!"),
                    display_name="Member",
                    email_verified=True,
                    is_active=True,
                    is_admin=False,
                )
                session.add(user)
                await session.commit()

        asyncio.run(seed_user())

        login_response = client.post(
            "/api/auth/login",
            json={"email": "member@example.com", "password": "Member-pass1!"},
        )
        token = login_response.cookies.get("access_token")
        assert token

        response = client.get(
            "/api/strategies/trading/strategy-config",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403
        assert response.json()["detail"] == "Admin access required"


def test_backtest_rejects_other_users_legacy_strategy(session_factory):
    app, patches = _strategy_client(session_factory)
    with patches[0], patches[1], patches[2], TestClient(app) as client:
        import asyncio

        async def seed_data():
            async with session_factory() as session:
                owner = User(
                    email="owner@example.com",
                    password_hash=hash_password("Owner-pass1!"),
                    display_name="Owner",
                    email_verified=True,
                    is_active=True,
                )
                attacker = User(
                    email="attacker@example.com",
                    password_hash=hash_password("Attacker-pass1!"),
                    display_name="Attacker",
                    email_verified=True,
                    is_active=True,
                )
                session.add_all([owner, attacker])
                await session.flush()
                strategy = Strategy(
                        user_id=owner.id,
                        name="Private Legacy Strategy",
                        conditions=[],
                        action="BUY",
                        timeframe="1D",
                    )
                session.add(strategy)
                await session.flush()
                await session.commit()
                return strategy.id

        strategy_id = asyncio.run(seed_data())

        login_response = client.post(
            "/api/auth/login",
            json={"email": "attacker@example.com", "password": "Attacker-pass1!"},
        )
        token = login_response.cookies.get("access_token")
        assert token

        response = client.post(
            "/api/strategies/backtest",
            json={"strategy_id": strategy_id, "symbol": "SPY"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404


def test_connection_credentials_are_validated_and_error_messages_are_sanitized():
    provider = ApiProvider(
        slug="alpaca",
        name="Alpaca",
        api_type=ApiProviderType.BROKERAGE,
        credential_fields=[
            {"key": "api_key", "label": "API Key", "secret": False},
            {"key": "api_secret", "label": "API Secret", "secret": True},
        ],
        is_available=True,
    )

    with pytest.raises(HTTPException) as exc_info:
        _sanitize_credentials(
            provider,
            {
                "api_key": "key-123",
                "api_secret": {"nested": "nope"},
            },
        )
    assert "api_secret must be a string value" in str(exc_info.value)

    sanitized_message = _sanitized_connection_test_error(
        "polygon",
        RuntimeError("boom apiKey=secret-12345"),
    )
    assert "secret-12345" not in sanitized_message
    assert sanitized_message == "Polygon connection test failed"
