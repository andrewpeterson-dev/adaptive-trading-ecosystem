"""Create database tables and an initial admin user."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine
from config.settings import get_settings
from db.database import Base
from db.models import User, EmailVerification, BrokerCredential  # noqa: F401 — registers models
import bcrypt

settings = get_settings()


def main():
    engine = create_engine(settings.database_url_sync, echo=True)

    # Create all tables
    Base.metadata.create_all(engine)
    print("All tables created.")

    # Create admin user
    from sqlalchemy.orm import Session
    with Session(engine) as db:
        existing = db.query(User).filter(User.email == "admin@example.com").first()
        if existing:
            print("Admin user already exists.")
            return

        admin = User(
            email="admin@example.com",
            password_hash=bcrypt.hashpw(b"changeme123", bcrypt.gensalt(12)).decode(),
            display_name="Admin",
            is_active=True,
            is_admin=True,
            email_verified=True,
        )
        db.add(admin)
        db.commit()
        print(f"Admin user created: admin@example.com / changeme123")
        print("IMPORTANT: Change the admin password after first login!")


if __name__ == "__main__":
    main()
