"""Admin routes — restricted to users with is_admin=True."""

import structlog
from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select

from db.database import get_session
from db.models import User

logger = structlog.get_logger(__name__)
router = APIRouter()


def _require_admin(request: Request) -> int:
    """Return user_id if caller is admin, else raise 403."""
    user_id = getattr(request.state, "user_id", None)
    is_admin = getattr(request.state, "is_admin", False)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if not is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user_id


@router.get("/users")
async def list_users(request: Request):
    """Return all users. Admin only."""
    _require_admin(request)

    async with get_session() as db:
        result = await db.execute(select(User).order_by(User.id))
        users = result.scalars().all()

    return {
        "users": [
            {
                "id": u.id,
                "email": u.email,
                "display_name": u.display_name,
                "is_active": u.is_active,
                "is_admin": u.is_admin,
                "email_verified": u.email_verified,
                "created_at": u.created_at.isoformat() if u.created_at else None,
            }
            for u in users
        ],
        "total": len(users),
    }
