"""Authentication routes — register, verify, login, session, recovery, and broker credentials."""

from __future__ import annotations

import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import structlog
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from config.settings import get_settings
from db.database import get_session
from db.encryption import encrypt_value
from db.models import (
    BrokerCredential,
    BrokerType,
    EmailVerification,
    PasswordResetToken,
    User,
)
from services.auth_email import (
    EmailDispatchResult,
    auth_email_flow_available,
    send_password_reset_email,
    send_verification_email,
)
from services.security.auth_session import (
    clear_auth_cookies,
    hash_token,
    issue_csrf_token,
    set_auth_cookies,
)
from services.security.jwt_utils import JWTConfigurationError, encode_jwt
from services.security.rate_limit import RateLimitExceeded, rate_limiter

logger = structlog.get_logger(__name__)
router = APIRouter()

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PASSWORD_MIN_LENGTH = 10
_MAX_SECRET_FIELD_LENGTH = 2048
_VERIFICATION_EXPIRY_HOURS = 24
_PASSWORD_RESET_EXPIRY_MINUTES = 30
# Dummy hash for constant-time comparison when user doesn't exist (prevents timing oracle)
_DUMMY_HASH = bcrypt.hashpw(b"timing-attack-dummy", bcrypt.gensalt()).decode()


def _client_ip(request: Request) -> str:
    settings = get_settings()
    if settings.trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _apply_rate_limit(
    bucket: str,
    key: str,
    *,
    limit: int,
    window_seconds: int,
) -> None:
    try:
        rate_limiter.check(bucket, key, limit=limit, window_seconds=window_seconds)
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=429,
            detail=f"Too many attempts. Try again in {exc.retry_after} seconds.",
            headers={"Retry-After": str(exc.retry_after)},
        ) from exc


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
    if len(normalized) > 100:
        raise HTTPException(status_code=400, detail="Display name is too long")
    return normalized


def _validate_password(password: str, *, field_name: str = "Password") -> str:
    if len(password) < _PASSWORD_MIN_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} must be at least {_PASSWORD_MIN_LENGTH} characters",
        )
    if len(password) > 512:
        raise HTTPException(status_code=400, detail=f"{field_name} is too long")
    if password != password.strip():
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} cannot start or end with whitespace",
        )

    categories = sum(
        (
            any(char.islower() for char in password),
            any(char.isupper() for char in password),
            any(char.isdigit() for char in password),
            any(not char.isalnum() for char in password),
        )
    )
    if categories < 3:
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} must include at least three of: lowercase, uppercase, number, symbol",
        )
    return password


def _validate_secret_field(value: str, *, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise HTTPException(status_code=400, detail=f"{field_name} is required")
    if len(normalized) > _MAX_SECRET_FIELD_LENGTH:
        raise HTTPException(status_code=400, detail=f"{field_name} is too long")
    return normalized


def _require_auth_email_flow() -> None:
    settings = get_settings()
    if auth_email_flow_available(settings):
        return
    raise HTTPException(
        status_code=503,
        detail="Email delivery is temporarily unavailable. Please try again later.",
    )


def _create_token(
    user: User,
    *,
    scope: str = "access",
    expires_delta: timedelta | None = None,
) -> str:
    settings = get_settings()
    payload = {
        "user_id": user.id,
        "email": user.email,
        "is_admin": user.is_admin,
        "scope": scope,
        "session_version": int(user.session_version or 0),
        "exp": datetime.now(timezone.utc) + (expires_delta or timedelta(days=settings.jwt_expiry_days)),
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


def _verification_response(
    email: str,
    dispatch: EmailDispatchResult,
    *,
    message: str,
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={
            "success": True,
            "verification_required": True,
            "email": email,
            "email_sent": dispatch.delivered,
            "development_verification_url": dispatch.preview_url,
            "message": message,
        },
    )


async def _invalidate_existing_email_tokens(db, user_id: int) -> None:
    await db.execute(
        update(EmailVerification)
        .where(EmailVerification.user_id == user_id, EmailVerification.used == False)
        .values(used=True)
    )


async def _create_email_verification_token(db, user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    await _invalidate_existing_email_tokens(db, user_id)
    db.add(
        EmailVerification(
            user_id=user_id,
            token=hash_token(token),
            expires_at=datetime.utcnow() + timedelta(hours=_VERIFICATION_EXPIRY_HOURS),
            used=False,
        )
    )
    return token


async def _invalidate_existing_reset_tokens(db, user_id: int) -> None:
    await db.execute(
        update(PasswordResetToken)
        .where(PasswordResetToken.user_id == user_id, PasswordResetToken.used == False)
        .values(used=True)
    )


async def _create_password_reset_token(db, user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    await _invalidate_existing_reset_tokens(db, user_id)
    db.add(
        PasswordResetToken(
            user_id=user_id,
            token_hash=hash_token(token),
            expires_at=datetime.utcnow() + timedelta(minutes=_PASSWORD_RESET_EXPIRY_MINUTES),
            used=False,
        )
    )
    return token


def _issue_auth_response(user: User, *, status_code: int = 200, content: dict | None = None) -> JSONResponse:
    token = _create_token(user)
    response = JSONResponse(status_code=status_code, content=content or {"user": _user_dict(user)})
    set_auth_cookies(response, token=token, csrf_token=issue_csrf_token())
    return response


def _clear_auth_response() -> JSONResponse:
    response = JSONResponse(status_code=200, content={"success": True, "message": "Logged out"})
    clear_auth_cookies(response)
    return response


def _current_user_from_request(request: Request) -> User | None:
    user = getattr(request.state, "user", None)
    return user if isinstance(user, User) else None


class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    email: str
    password: str
    display_name: str


class VerifyEmailRequest(BaseModel):
    token: str


class ResendVerificationRequest(BaseModel):
    email: str


class PasswordResetRequest(BaseModel):
    email: str


class PasswordResetConfirmRequest(BaseModel):
    token: str
    password: str


class ProfileUpdateRequest(BaseModel):
    display_name: Optional[str] = None
    password: Optional[str] = None
    current_password: Optional[str] = None
    new_password: Optional[str] = None


class BrokerCredentialRequest(BaseModel):
    broker_type: str
    api_key: str
    api_secret: str
    is_paper: bool = True
    nickname: Optional[str] = None
    base_url: Optional[str] = None


class WebsocketTokenResponse(BaseModel):
    token: str
    expires_in: int


@router.post("/login")
async def login(req: LoginRequest, request: Request):
    client_ip = _client_ip(request)
    email = _validate_email(req.email)
    _apply_rate_limit("auth:login:ip", client_ip, limit=10, window_seconds=300)
    _apply_rate_limit("auth:login:email", email, limit=10, window_seconds=300)

    async with get_session() as db:
        result = await db.execute(select(User).where(func.lower(User.email) == email))
        user = result.scalar_one_or_none()

        if not user:
            # Constant-time: always run bcrypt even when user is missing to prevent timing oracle
            _check_password(req.password, _DUMMY_HASH)
            logger.warning("login_failed", email=email, client_ip=client_ip, reason="invalid_credentials")
            raise HTTPException(status_code=401, detail="Invalid email or password")
        if not _check_password(req.password, user.password_hash):
            logger.warning("login_failed", email=email, client_ip=client_ip, reason="invalid_credentials")
            raise HTTPException(status_code=401, detail="Invalid email or password")

        if not user.is_active:
            logger.warning("login_failed", user_id=user.id, email=user.email, client_ip=client_ip, reason="inactive")
            raise HTTPException(status_code=403, detail="Account is disabled")
        if not user.email_verified:
            logger.info("login_blocked_unverified", user_id=user.id, email=user.email)
            raise HTTPException(
                status_code=403,
                detail="Please verify your email before signing in.",
            )

        logger.info("user_logged_in", user_id=user.id, email=user.email)
        return _issue_auth_response(user, content={"user": _user_dict(user)})


@router.post("/register")
async def register(req: RegisterRequest, request: Request):
    client_ip = _client_ip(request)
    email = _validate_email(req.email)
    password = _validate_password(req.password)
    display_name = _validate_display_name(req.display_name)
    _apply_rate_limit("auth:register:ip", client_ip, limit=5, window_seconds=900)
    _apply_rate_limit("auth:register:email", email, limit=3, window_seconds=3600)
    _require_auth_email_flow()

    verification_token: str | None = None
    target_email = email

    async with get_session() as db:
        existing = await db.execute(select(User).where(func.lower(User.email) == email))
        user = existing.scalar_one_or_none()

        if user is None:
            user = User(
                email=email,
                password_hash=_hash_password(password),
                display_name=display_name,
                email_verified=False,
                session_version=0,
            )
            db.add(user)
            try:
                await db.flush()
            except IntegrityError as exc:
                logger.warning("registration_conflict", email=email, client_ip=client_ip)
                raise HTTPException(
                    status_code=409,
                    detail="Unable to create that account right now.",
                ) from exc
            verification_token = await _create_email_verification_token(db, user.id)
            logger.info("user_registered_pending_verification", user_id=user.id, email=user.email)
        elif user.is_active and not user.email_verified:
            verification_token = await _create_email_verification_token(db, user.id)
            logger.info("verification_resent_for_existing_user", user_id=user.id, email=user.email)
        else:
            logger.info("registration_request_for_existing_account", email=email, active=user.is_active, verified=user.email_verified)

    dispatch = EmailDispatchResult(delivered=False, preview_url=None)
    if verification_token:
        dispatch = await send_verification_email(target_email, verification_token)

    return _verification_response(
        target_email,
        dispatch,
        message="If that email can be used to finish setup, we have sent verification instructions.",
    )


async def _verify_email_token(token: str) -> dict:
    token_value = token.strip()
    if not token_value:
        raise HTTPException(status_code=400, detail="Verification token is required")

    async with get_session() as db:
        result = await db.execute(
            select(EmailVerification).where(
                EmailVerification.token == hash_token(token_value),
                EmailVerification.used == False,
                EmailVerification.expires_at > datetime.utcnow(),
            )
        )
        verification = result.scalar_one_or_none()
        if not verification:
            raise HTTPException(status_code=400, detail="Invalid or expired verification link")

        user_result = await db.execute(select(User).where(User.id == verification.user_id))
        user = user_result.scalar_one_or_none()
        if not user or not user.is_active:
            raise HTTPException(status_code=400, detail="Verification link is no longer valid")

        user.email_verified = True
        verification.used = True
        await _invalidate_existing_email_tokens(db, user.id)

    logger.info("email_verified", user_id=user.id, email=user.email)
    return {"success": True, "message": "Email verified. You can now sign in."}


@router.get("/verify-email")
async def verify_email_get(token: str):
    return await _verify_email_token(token)


@router.post("/verify-email")
async def verify_email_post(body: VerifyEmailRequest):
    return await _verify_email_token(body.token)


@router.post("/resend-verification")
async def resend_verification(body: ResendVerificationRequest, request: Request):
    client_ip = _client_ip(request)
    email = _validate_email(body.email)
    _apply_rate_limit("auth:verify-resend:ip", client_ip, limit=5, window_seconds=900)
    _apply_rate_limit("auth:verify-resend:email", email, limit=3, window_seconds=3600)
    _require_auth_email_flow()

    verification_token: str | None = None
    async with get_session() as db:
        result = await db.execute(select(User).where(func.lower(User.email) == email))
        user = result.scalar_one_or_none()
        if user and user.is_active and not user.email_verified:
            verification_token = await _create_email_verification_token(db, user.id)

    dispatch = EmailDispatchResult(delivered=False, preview_url=None)
    if verification_token:
        dispatch = await send_verification_email(email, verification_token)

    return _verification_response(
        email,
        dispatch,
        message="If a verification email is still needed, we have sent a fresh link.",
    )


@router.post("/password-reset/request")
async def request_password_reset(body: PasswordResetRequest, request: Request):
    client_ip = _client_ip(request)
    email = _validate_email(body.email)
    _apply_rate_limit("auth:password-reset:ip", client_ip, limit=5, window_seconds=900)
    _apply_rate_limit("auth:password-reset:email", email, limit=3, window_seconds=3600)
    _require_auth_email_flow()

    reset_token: str | None = None
    async with get_session() as db:
        result = await db.execute(select(User).where(func.lower(User.email) == email))
        user = result.scalar_one_or_none()
        if user and user.is_active and user.email_verified:
            reset_token = await _create_password_reset_token(db, user.id)

    dispatch = EmailDispatchResult(delivered=False, preview_url=None)
    if reset_token:
        dispatch = await send_password_reset_email(email, reset_token)

    return {
        "success": True,
        "email_sent": dispatch.delivered,
        "development_reset_url": dispatch.preview_url,
        "message": "If an account matches that email, password reset instructions have been sent.",
    }


@router.post("/password-reset/confirm")
async def confirm_password_reset(body: PasswordResetConfirmRequest, request: Request):
    client_ip = _client_ip(request)
    _apply_rate_limit("auth:password-reset-confirm:ip", client_ip, limit=10, window_seconds=900)
    password = _validate_password(body.password, field_name="New password")
    token_value = body.token.strip()
    if not token_value:
        raise HTTPException(status_code=400, detail="Reset token is required")

    async with get_session() as db:
        result = await db.execute(
            select(PasswordResetToken).where(
                PasswordResetToken.token_hash == hash_token(token_value),
                PasswordResetToken.used == False,
                PasswordResetToken.expires_at > datetime.utcnow(),
            )
        )
        reset_record = result.scalar_one_or_none()
        if not reset_record:
            raise HTTPException(status_code=400, detail="Invalid or expired reset link")

        user_result = await db.execute(select(User).where(User.id == reset_record.user_id))
        user = user_result.scalar_one_or_none()
        if not user or not user.is_active:
            raise HTTPException(status_code=400, detail="Reset link is no longer valid")

        user.password_hash = _hash_password(password)
        user.session_version = int(user.session_version or 0) + 1
        reset_record.used = True
        await _invalidate_existing_reset_tokens(db, user.id)

    logger.info("password_reset_completed", user_id=user.id, email=user.email)
    return {"success": True, "message": "Password updated. Sign in with your new password."}


@router.post("/websocket-token", response_model=WebsocketTokenResponse)
async def issue_websocket_token(request: Request):
    user = _current_user_from_request(request)
    user_id = request.state.user_id
    client_ip = _client_ip(request)

    _apply_rate_limit("auth:websocket-token:user", str(user_id), limit=60, window_seconds=60)
    _apply_rate_limit("auth:websocket-token:ip", client_ip, limit=120, window_seconds=60)

    async with get_session() as db:
        if user is None:
            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="Not authenticated")

    expires_in = 90
    token = _create_token(
        user,
        scope="websocket",
        expires_delta=timedelta(seconds=expires_in),
    )
    return {"token": token, "expires_in": expires_in}


@router.get("/me")
async def get_me(request: Request):
    user_id = request.state.user_id
    user = _current_user_from_request(request)

    async with get_session() as db:
        if user is None:
            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        creds = await db.execute(
            select(BrokerCredential).where(BrokerCredential.user_id == user_id)
        )
        broker_list = creds.scalars().all()

    return {
        **_user_dict(user),
        "has_broker": len(broker_list) > 0,
        "brokers": [
            {
                "id": cred.id,
                "broker_type": cred.broker_type.value if isinstance(cred.broker_type, BrokerType) else cred.broker_type,
                "is_paper": cred.is_paper,
                "nickname": cred.nickname,
            }
            for cred in broker_list
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

        changed_display_name = False
        changed_password = False

        if req.display_name is not None:
            user.display_name = _validate_display_name(req.display_name)
            changed_display_name = True

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
            user.session_version = int(user.session_version or 0) + 1
            changed_password = True

        if not changed_display_name and not changed_password:
            raise HTTPException(status_code=400, detail="No profile changes provided")

        logger.info(
            "profile_updated",
            user_id=user.id,
            changed_display_name=changed_display_name,
            changed_password=changed_password,
        )

        if changed_password:
            return _issue_auth_response(user, content={"success": True, "user": _user_dict(user)})

        return {"success": True, "user": _user_dict(user)}


@router.post("/broker-credentials")
async def save_broker_credentials(req: BrokerCredentialRequest, request: Request):
    user_id = request.state.user_id
    api_key = _validate_secret_field(req.api_key, field_name="API key")
    api_secret = _validate_secret_field(req.api_secret, field_name="API secret")

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

    nickname = req.nickname.strip() if req.nickname and req.nickname.strip() else None
    if nickname and len(nickname) > 100:
        raise HTTPException(status_code=400, detail="Nickname is too long")

    async with get_session() as db:
        existing = await db.execute(
            select(BrokerCredential).where(
                BrokerCredential.user_id == user_id,
                BrokerCredential.broker_type == broker_type,
            )
        )
        cred = existing.scalar_one_or_none()

        if cred:
            cred.encrypted_api_key = encrypt_value(api_key)
            cred.encrypted_api_secret = encrypt_value(api_secret)
            cred.is_paper = req.is_paper
            cred.nickname = nickname
        else:
            cred = BrokerCredential(
                user_id=user_id,
                broker_type=broker_type,
                encrypted_api_key=encrypt_value(api_key),
                encrypted_api_secret=encrypt_value(api_secret),
                is_paper=req.is_paper,
                nickname=nickname,
            )
            db.add(cred)

        logger.info("broker_credentials_saved", user_id=user_id, broker=req.broker_type)

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
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning("broker_cache_invalidation_failed", user_id=user_id, error=str(exc))

    return {"success": True, "broker_type": req.broker_type}


@router.post("/logout")
@router.delete("/logout")
async def logout(request: Request):
    user_id = request.state.user_id
    async with get_session() as db:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user:
            user.session_version = int(user.session_version or 0) + 1
            logger.info("user_logged_out", user_id=user.id, email=user.email)

    return _clear_auth_response()


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
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning("broker_cache_invalidation_failed", user_id=user_id, error=str(exc))

    return {"success": True}
