"""Legacy auth helpers kept for compatibility with older imports."""

from __future__ import annotations

import re

import bcrypt

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def hash_password(password: str) -> str:
    """Return a bcrypt hash for the provided password."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    """Check a plain password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        return False


def is_valid_email(email: str) -> bool:
    """Validate the repository's simple email format requirements."""
    normalized = email.strip().lower()
    return bool(normalized) and len(normalized) <= 255 and bool(_EMAIL_RE.match(normalized))

