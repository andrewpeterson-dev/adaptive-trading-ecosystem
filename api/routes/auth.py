"""Authentication routes — login, register, profile, broker credentials."""

import re
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import structlog
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from config.settings import get_settings
from db.database import get_session
from db.encryption import encrypt_value, decrypt_value
from db.models import User, BrokerCredential, BrokerType
from services.security.jwt_utils import JWTConfigurationError, encode_jwt

logger = structlog.get_logger(__name__)
router = APIRouter()

# Simple in-memory rate limiter for auth endpoints
_login_attempts: dict = defaultdict(list)  # ip -> [timestamps]
_RATE_LIMIT_WINDOW = 300  # 5 minutes
_RATE_LIMIT_MAX = 10  # max attempts per window
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _check_rate_limit(ip: str) -> None:
    """Raise 429 if too many login attempts from this IP."""
    now = time.time()
    _login_attempts[ip] = [t for t in _login_attempts[ip] if now - t < _RATE_LIMIT_WINDOW]
    if len(_login_attempts[ip]) >= _RATE_LIMIT_MAX:
        raise HTTPException(status_code=429, detail="Too many attempts. Try again in a few minutes.")
    _login_attempts[ip].append(now)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        return False


def is_valid_email(email: str) -> bool:
    normalized = _normalize_email(email)
    return bool(normalized and len(normalized) <= 255 and _EMAIL_RE.match(normalized))


def _hash_password(password: str) -> str:
    return hash_password(password)


def _check_password(password: str, hashed: str) -> bool:
    return verify_password(password, hashed)


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _validate_email(email: str) -> str:
    normalized = _normalize_email(email)
    if not is_valid_email(normalized):
        raise HTTPException(status_code=400, detail="Invalid email address")
    return normalized


def _validate_display_name(display_name: str) -> str:
    normalized = display_name.strip()
    if not normalized:
        raise HTTPException(status_code=400, detail="Display name is required")
    if len(normalized) > 120:
        raise HTTPException(status_code=400, detail="Display name is too long")
    return normalized


def _validate_password(password: str, *, field_name: str = "Password") -> str:
    normalized = password.strip()
    if len(normalized) < 8:
        raise HTTPException(status_code=400, detail=f"{field_name} must be at least 8 characters")
    if len(normalized) > 512:
        raise HTTPException(status_code=400, detail=f"{field_name} is too long")
    return normalized


def _create_token(user_id: int, email: str, is_admin: bool) -> str:
    settings = get_settings()
    payload = {
        "user_id": user_id,
        "email": email,
        "is_admin": is_admin,
        "exp": datetime.now(timezone.utc) + timedelta(days=settings.jwt_expiry_days),
        "iat": datetime.now(timezone.utc),
    }
    try:
        return encode_jwt(payload, settings)
    except JWTConfigurationError as exc:
        logger.error("jwt_secret_missing_for_token_issue")
        raise HTTPException(
            status_code=503,
            detail="Authentication is temporarily unavailable",
        ) from exc


def _user_dict(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "is_admin": user.is_admin,
        "is_verified": user.email_verified,
    }


# ── Request/Response Models ──────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    email: str
    password: str
    display_name: str


class ProfileUpdateRequest(BaseModel):
    display_name: Optional[str] = None
    password: Optional[str] = None
    current_password: Optional[str] = None
    new_password: Optional[str] = None


class BrokerCredentialRequest(BaseModel):
    broker_type: str  # "alpaca" or "webull"
    api_key: str
    api_secret: str
    is_paper: bool = True
    nickname: Optional[str] = None
    base_url: Optional[str] = None


# ── Routes ───────────────────────────────────────────────────────────────

@router.post("/login")
async def login(req: LoginRequest, request: Request):
    client_ip = request.client.host if request.client else "unknown"
    _check_rate_limit(client_ip)
    email = _validate_email(req.email)

    async with get_session() as db:
        result = await db.execute(select(User).where(func.lower(User.email) == email))
        user = result.scalar_one_or_none()

        if not user or not _check_password(req.password, user.password_hash):
            logger.warning("login_failed", email=email, client_ip=client_ip, reason="invalid_credentials")
            raise HTTPException(status_code=401, detail="Invalid email or password")

        if not user.is_active:
            logger.warning("login_failed", user_id=user.id, email=user.email, client_ip=client_ip, reason="inactive")
            raise HTTPException(status_code=403, detail="Account is disabled")

        token = _create_token(user.id, user.email, user.is_admin)
        logger.info("user_logged_in", user_id=user.id, email=user.email)
        return {"token": token, "user": _user_dict(user)}


@router.post("/register")
async def register(req: RegisterRequest, request: Request):
    client_ip = request.client.host if request.client else "unknown"
    _check_rate_limit(client_ip)
    email = _validate_email(req.email)
    password = _validate_password(req.password)
    display_name = _validate_display_name(req.display_name)

    async with get_session() as db:
        existing = await db.execute(select(User).where(func.lower(User.email) == email))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Email already registered")

        user = User(
            email=email,
            password_hash=_hash_password(password),
            display_name=display_name,
            email_verified=True,  # Skip email verification for local dev
        )
        db.add(user)
        try:
            await db.flush()
        except IntegrityError:
            logger.warning("registration_conflict", email=email, client_ip=client_ip)
            raise HTTPException(status_code=409, detail="Email already registered")

        token = _create_token(user.id, user.email, user.is_admin)
        logger.info("user_registered", user_id=user.id, email=user.email)
        return {"token": token, "user": _user_dict(user)}


@router.get("/me")
async def get_me(request: Request):
    user_id = request.state.user_id
    async with get_session() as db:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Also check if user has broker credentials
        creds = await db.execute(
            select(BrokerCredential).where(BrokerCredential.user_id == user_id)
        )
        broker_list = creds.scalars().all()

        return {
            **_user_dict(user),
            "has_broker": len(broker_list) > 0,
            "brokers": [
                {
                    "id": c.id,
                    "broker_type": c.broker_type.value if isinstance(c.broker_type, BrokerType) else c.broker_type,
                    "is_paper": c.is_paper,
                    "nickname": c.nickname,
                }
                for c in broker_list
            ],
        }


@router.put("/profile")
async def update_profile(req: ProfileUpdateRequest, request: Request):
    user_id = request.state.user_id
    async with get_session() as db:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        if req.display_name:
            user.display_name = _validate_display_name(req.display_name)

        requested_new_password = req.new_password or req.password
        if requested_new_password:
            new_password = _validate_password(
                requested_new_password,
                field_name="New password" if req.new_password else "Password",
            )
            if not req.current_password:
                raise HTTPException(status_code=400, detail="Current password is required")
            if not _check_password(req.current_password, user.password_hash):
                raise HTTPException(status_code=400, detail="Current password is incorrect")
            user.password_hash = _hash_password(new_password)

        if not req.display_name and not requested_new_password:
            raise HTTPException(status_code=400, detail="No profile changes provided")

        logger.info(
            "profile_updated",
            user_id=user.id,
            changed_display_name=bool(req.display_name),
            changed_password=bool(requested_new_password),
        )

        return {"success": True, "user": _user_dict(user)}


@router.post("/broker-credentials")
async def save_broker_credentials(req: BrokerCredentialRequest, request: Request):
    user_id = request.state.user_id
    api_key = req.api_key.strip()
    api_secret = req.api_secret.strip()
    if not api_key or not api_secret:
        raise HTTPException(status_code=400, detail="API key and secret are required")

    broker_type_value = req.broker_type.strip().lower()
    if broker_type_value == "alpaca":
        broker_type = BrokerType.ALPACA
    elif broker_type_value == "webull":
        broker_type = BrokerType.WEBULL
    else:
        raise HTTPException(
            status_code=400,
            detail="Invalid broker_type. Must be 'alpaca' or 'webull'.",
        )

    async with get_session() as db:
        # Check for existing credential of same type
        existing = await db.execute(
            select(BrokerCredential).where(
                BrokerCredential.user_id == user_id,
                BrokerCredential.broker_type == broker_type,
            )
        )
        cred = existing.scalar_one_or_none()

        if cred:
            # Update existing
            cred.encrypted_api_key = encrypt_value(api_key)
            cred.encrypted_api_secret = encrypt_value(api_secret)
            cred.is_paper = req.is_paper
            cred.nickname = req.nickname.strip() if req.nickname else None
        else:
            # Create new
            cred = BrokerCredential(
                user_id=user_id,
                broker_type=broker_type,
                encrypted_api_key=encrypt_value(api_key),
                encrypted_api_secret=encrypt_value(api_secret),
                is_paper=req.is_paper,
                nickname=req.nickname.strip() if req.nickname else None,
            )
            db.add(cred)

        logger.info("broker_credentials_saved", user_id=user_id, broker=req.broker_type)

        # Invalidate cached Webull client so the new credentials are picked up immediately
        if broker_type == BrokerType.WEBULL:
            try:
                from api.routes.webull import invalidate_user_client_cache

                invalidated = invalidate_user_client_cache(user_id)
                logger.info(
                    "webull_cache_invalidated",
                    user_id=user_id,
                    invalidated=invalidated,
                    source="broker_credentials",
                )
            except Exception as exc:
                logger.warning("broker_cache_invalidation_failed", user_id=user_id, error=str(exc))

        return {"success": True, "broker_type": req.broker_type}


@router.delete("/logout")
async def logout(request: Request):
    """Logout endpoint — stateless JWT, just signals the client to clear the token."""
    return {"success": True, "message": "Logged out"}


@router.delete("/broker-credentials/{cred_id}")
async def delete_broker_credentials(cred_id: int, request: Request):
    user_id = request.state.user_id
    async with get_session() as db:
        result = await db.execute(
            select(BrokerCredential).where(
                BrokerCredential.id == cred_id,
                BrokerCredential.user_id == user_id,
            )
        )
        cred = result.scalar_one_or_none()
        if not cred:
            raise HTTPException(status_code=404, detail="Credential not found")

        should_invalidate_webull = cred.broker_type == BrokerType.WEBULL
        await db.delete(cred)

    if should_invalidate_webull:
        try:
            from api.routes.webull import invalidate_user_client_cache

            invalidated = invalidate_user_client_cache(user_id)
            logger.info(
                "webull_cache_invalidated",
                user_id=user_id,
                invalidated=invalidated,
                source="broker_credential_delete",
            )
        except Exception as exc:
            logger.warning("broker_cache_invalidation_failed", user_id=user_id, error=str(exc))

    return {"success": True}
