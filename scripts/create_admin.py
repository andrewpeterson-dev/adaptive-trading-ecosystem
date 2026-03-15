"""Create database tables and an initial admin user."""

import os
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine
from config.settings import get_settings
from db.database import Base
from db.models import User, EmailVerification, BrokerCredential, PaperPortfolio, PaperPosition, PaperTrade  # noqa: F401
import bcrypt

settings = get_settings()


def main():
    engine = create_engine(settings.database_url_sync, echo=True)
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@example.com").strip().lower()
    admin_password = os.environ.get("ADMIN_PASSWORD", "").strip() or secrets.token_urlsafe(18)
    admin_display_name = os.environ.get("ADMIN_DISPLAY_NAME", "Admin").strip() or "Admin"

    # Create all tables
    Base.metadata.create_all(engine)
    print("All tables created.")

    # Create admin user
    from sqlalchemy.orm import Session
    with Session(engine) as db:
        existing = db.query(User).filter(User.email == admin_email).first()
        if existing:
            print("Admin user already exists.")
            return

        admin = User(
            email=admin_email,
            password_hash=bcrypt.hashpw(admin_password.encode(), bcrypt.gensalt(12)).decode(),
            display_name=admin_display_name,
            is_active=True,
            is_admin=True,
            email_verified=True,
        )
        db.add(admin)
        db.commit()
        print(f"Admin user created: {admin_email}")
        print(f"Temporary password: {admin_password}")
        print("IMPORTANT: Store this password securely and rotate it after first login.")


if __name__ == "__main__":
    main()
