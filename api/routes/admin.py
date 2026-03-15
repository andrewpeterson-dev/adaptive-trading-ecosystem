"""Admin routes — restricted to users with is_admin=True."""

from fastapi import APIRouter, Request
from sqlalchemy import select

from db.database import get_session
from db.models import User
from services.security.access_control import require_admin

router = APIRouter()


@router.get("/users")
async def list_users(request: Request):
    """Return all users. Admin only."""
    await require_admin(request)

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
