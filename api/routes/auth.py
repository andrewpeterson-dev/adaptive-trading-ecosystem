"""Authentication routes — login, register, profile, broker credentials."""

import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
import structlog
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select

from config.settings import get_settings
from db.database import get_session
from db.encryption import encrypt_value, decrypt_value
from db.models import User, BrokerCredential, BrokerType

logger = structlog.get_logger(__name__)
router = APIRouter()

# Simple in-memory rate limiter for auth endpoints
_login_attempts: dict = defaultdict(list)  # ip -> [timestamps]
_RATE_LIMIT_WINDOW = 300  # 5 minutes
_RATE_LIMIT_MAX = 10  # max attempts per window


def _check_rate_limit(ip: str) -> None:
    """Raise 429 if too many login attempts from this IP."""
    now = time.time()
    _login_attempts[ip] = [t for t in _login_attempts[ip] if now - t < _RATE_LIMIT_WINDOW]
    if len(_login_attempts[ip]) >= _RATE_LIMIT_MAX:
        raise HTTPException(status_code=429, detail="Too many attempts. Try again in a few minutes.")
    _login_attempts[ip].append(now)

def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _check_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def _create_token(user_id: int, email: str, is_admin: bool) -> str:
    settings = get_settings()
    payload = {
        "user_id": user_id,
        "email": email,
        "is_admin": is_admin,
        "exp": datetime.now(timezone.utc) + timedelta(days=settings.jwt_expiry_days),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


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

    async with get_session() as db:
        result = await db.execute(select(User).where(User.email == req.email))
        user = result.scalar_one_or_none()

        if not user or not _check_password(req.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid email or password")

        if not user.is_active:
            raise HTTPException(status_code=403, detail="Account is disabled")

        token = _create_token(user.id, user.email, user.is_admin)
        logger.info("user_logged_in", user_id=user.id, email=user.email)
        return {"token": token, "user": _user_dict(user)}


@router.post("/register")
async def register(req: RegisterRequest, request: Request):
    client_ip = request.client.host if request.client else "unknown"
    _check_rate_limit(client_ip)
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    async with get_session() as db:
        existing = await db.execute(select(User).where(User.email == req.email))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Email already registered")

        user = User(
            email=req.email,
            password_hash=_hash_password(req.password),
            display_name=req.display_name,
            email_verified=True,  # Skip email verification for local dev
        )
        db.add(user)
        await db.flush()

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
            user.display_name = req.display_name
        if req.password:
            if len(req.password) < 6:
                raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
            user.password_hash = _hash_password(req.password)

        return {"success": True, "user": _user_dict(user)}


@router.post("/broker-credentials")
async def save_broker_credentials(req: BrokerCredentialRequest, request: Request):
    user_id = request.state.user_id

    broker_type = BrokerType.ALPACA if req.broker_type.lower() == "alpaca" else BrokerType.WEBULL

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
            cred.encrypted_api_key = encrypt_value(req.api_key)
            cred.encrypted_api_secret = encrypt_value(req.api_secret)
            cred.is_paper = req.is_paper
            cred.nickname = req.nickname
        else:
            # Create new
            cred = BrokerCredential(
                user_id=user_id,
                broker_type=broker_type,
                encrypted_api_key=encrypt_value(req.api_key),
                encrypted_api_secret=encrypt_value(req.api_secret),
                is_paper=req.is_paper,
                nickname=req.nickname,
            )
            db.add(cred)

        logger.info("broker_credentials_saved", user_id=user_id, broker=req.broker_type)
        return {"success": True, "broker_type": req.broker_type}


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

        await db.delete(cred)
        return {"success": True}
