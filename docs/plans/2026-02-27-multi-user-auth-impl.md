# Multi-User Authentication Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add email+password authentication, per-user data isolation, encrypted broker key storage, email verification, and an admin dashboard to the Streamlit trading platform.

**Architecture:** Streamlit-native auth using `st.session_state` for session management, bcrypt for password hashing, Fernet for broker key encryption. All new tables in existing PostgreSQL database via SQLAlchemy. The dashboard `app.py` gets an auth gate at the top — nothing renders until the user is authenticated.

**Tech Stack:** Streamlit, SQLAlchemy 2.0 (async), PostgreSQL, bcrypt, cryptography (Fernet), smtplib

**Design doc:** `docs/plans/2026-02-27-multi-user-auth-design.md`

---

### Task 1: Add Dependencies

**Files:**
- Modify: `requirements.txt:1-62`
- Modify: `config/settings.py:20-103`
- Modify: `.env.example:1-64`

**Step 1: Add bcrypt and cryptography to requirements.txt**

Add these two lines after the existing `# Utilities` section (after line 53):

```
# Auth & Security
bcrypt==4.1.2
cryptography==42.0.2
```

**Step 2: Add auth settings to config/settings.py**

Add these fields inside the `Settings` class, after the `dashboard_port` field (after line 102):

```python
    # --- Auth ---
    encryption_key: str = ""  # Fernet key for broker credential encryption
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""  # Gmail app password
    base_url: str = "http://localhost:8501"  # Dashboard URL for email links
```

**Step 3: Add auth env vars to .env.example**

Append after the `DASHBOARD_PORT=8501` line:

```
# --- Auth & Security ---
# Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
ENCRYPTION_KEY=GENERATE_A_FERNET_KEY
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_gmail_app_password
BASE_URL=http://localhost:8501
```

**Step 4: Install dependencies**

Run: `cd /Users/andrewpeterson/adaptive-trading-ecosystem && pip install bcrypt cryptography`

**Step 5: Commit**

```bash
cd /Users/andrewpeterson/adaptive-trading-ecosystem
git add requirements.txt config/settings.py .env.example
git commit -m "feat: add auth dependencies and settings (bcrypt, cryptography, SMTP)"
```

---

### Task 2: Create User and BrokerCredential Database Models

**Files:**
- Modify: `db/models.py:1-207`
- Create: `db/encryption.py`

**Step 1: Write the encryption utility**

Create `db/encryption.py`:

```python
"""Fernet symmetric encryption for broker API credentials."""

from cryptography.fernet import Fernet

from config.settings import get_settings


def _get_fernet() -> Fernet:
    key = get_settings().encryption_key
    if not key:
        raise RuntimeError(
            "ENCRYPTION_KEY not set. Generate one with: "
            "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    return Fernet(key.encode())


def encrypt_value(plaintext: str) -> str:
    """Encrypt a string and return base64-encoded ciphertext."""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_value(ciphertext: str) -> str:
    """Decrypt a base64-encoded ciphertext back to plaintext."""
    return _get_fernet().decrypt(ciphertext.encode()).decode()
```

**Step 2: Add new enums and models to db/models.py**

Add a new enum after `RiskEventType` (after line 62):

```python
class BrokerType(str, enum.Enum):
    ALPACA = "alpaca"
    WEBULL = "webull"
```

Add these three new models after the `RiskEvent` class (after line 206):

```python
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    display_name = Column(String(100), nullable=False)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    email_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    broker_credentials = relationship("BrokerCredential", back_populates="user", cascade="all, delete-orphan")
    email_verifications = relationship("EmailVerification", back_populates="user", cascade="all, delete-orphan")


class EmailVerification(Base):
    __tablename__ = "email_verifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    token = Column(String(255), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="email_verifications")


class BrokerCredential(Base):
    __tablename__ = "broker_credentials"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    broker_type = Column(Enum(BrokerType), nullable=False)
    encrypted_api_key = Column(Text, nullable=False)
    encrypted_api_secret = Column(Text, nullable=False)
    is_paper = Column(Boolean, default=True)
    nickname = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="broker_credentials")

    __table_args__ = (
        Index("ix_broker_cred_user", "user_id"),
    )
```

**Step 3: Commit**

```bash
cd /Users/andrewpeterson/adaptive-trading-ecosystem
git add db/models.py db/encryption.py
git commit -m "feat: add User, EmailVerification, BrokerCredential models and encryption util"
```

---

### Task 3: Create the Auth Module

**Files:**
- Create: `dashboard/auth.py`

**Step 1: Create dashboard/auth.py**

This module handles login, signup, password hashing, session management, and email verification.

```python
"""
Authentication module for the Streamlit dashboard.
Handles login, signup, email verification, and session management.
"""

import re
import secrets
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import bcrypt
import streamlit as st
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session as SyncSession, sessionmaker

from config.settings import get_settings
from db.models import User, EmailVerification

settings = get_settings()

# Sync engine for Streamlit (Streamlit doesn't support async natively)
_sync_engine = create_engine(settings.database_url_sync, pool_pre_ping=True)
_SyncSessionLocal = sessionmaker(bind=_sync_engine, expire_on_commit=False)


def get_db() -> SyncSession:
    """Get a synchronous database session."""
    return _SyncSessionLocal()


def hash_password(password: str) -> str:
    """Hash a password with bcrypt."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against its bcrypt hash."""
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def is_valid_email(email: str) -> bool:
    """Basic email format validation."""
    return bool(re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email))


def send_verification_email(email: str, token: str) -> bool:
    """Send a verification email. Returns True on success."""
    if not settings.smtp_user or not settings.smtp_password:
        return False

    verify_url = f"{settings.base_url}?verify={token}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Verify your Adaptive Trading Ecosystem account"
    msg["From"] = settings.smtp_user
    msg["To"] = email

    html = f"""
    <html>
    <body style="font-family: -apple-system, sans-serif; background: #0a0e14; color: #d4dae3; padding: 40px;">
        <div style="max-width: 500px; margin: 0 auto; background: #12161f; border: 1px solid #1c2333; border-radius: 8px; padding: 32px;">
            <h2 style="color: #d4dae3; margin-top: 0;">Verify Your Email</h2>
            <p>Click the button below to verify your email address and activate your trading account.</p>
            <a href="{verify_url}" style="display: inline-block; background: #2563eb; color: white; padding: 12px 24px; border-radius: 6px; text-decoration: none; font-weight: 500;">Verify Email</a>
            <p style="margin-top: 24px; font-size: 0.85rem; color: #6b7b8d;">This link expires in 24 hours. If you didn't create this account, ignore this email.</p>
        </div>
    </body>
    </html>
    """
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(settings.smtp_user, email, msg.as_string())
        return True
    except Exception:
        return False


def create_user(email: str, password: str, display_name: str) -> tuple[bool, str]:
    """
    Create a new user account.
    Returns (success: bool, message: str).
    """
    if not is_valid_email(email):
        return False, "Invalid email format."
    if len(password) < 8:
        return False, "Password must be at least 8 characters."
    if not display_name.strip():
        return False, "Display name is required."

    db = get_db()
    try:
        existing = db.execute(select(User).where(User.email == email.lower())).scalar_one_or_none()
        if existing:
            return False, "An account with this email already exists."

        user = User(
            email=email.lower(),
            password_hash=hash_password(password),
            display_name=display_name.strip(),
        )
        db.add(user)
        db.flush()

        # Create verification token
        token = secrets.token_urlsafe(32)
        verification = EmailVerification(
            user_id=user.id,
            token=token,
            expires_at=datetime.utcnow() + timedelta(hours=24),
        )
        db.add(verification)
        db.commit()

        # Send verification email (non-blocking — account works without it)
        send_verification_email(email, token)

        return True, user.id
    except Exception as e:
        db.rollback()
        return False, f"Registration failed: {str(e)}"
    finally:
        db.close()


def authenticate(email: str, password: str) -> tuple[bool, str | dict]:
    """
    Authenticate a user.
    Returns (success, user_dict | error_message).
    """
    db = get_db()
    try:
        user = db.execute(select(User).where(User.email == email.lower())).scalar_one_or_none()
        if not user:
            return False, "Invalid email or password."
        if not user.is_active:
            return False, "Account is disabled. Contact support."
        if not verify_password(password, user.password_hash):
            return False, "Invalid email or password."

        return True, {
            "user_id": user.id,
            "email": user.email,
            "display_name": user.display_name,
            "is_admin": user.is_admin,
            "email_verified": user.email_verified,
        }
    finally:
        db.close()


def verify_email_token(token: str) -> tuple[bool, str]:
    """Verify an email verification token. Returns (success, message)."""
    db = get_db()
    try:
        verification = db.execute(
            select(EmailVerification).where(
                EmailVerification.token == token,
                EmailVerification.used == False,
                EmailVerification.expires_at > datetime.utcnow(),
            )
        ).scalar_one_or_none()

        if not verification:
            return False, "Invalid or expired verification link."

        user = db.execute(select(User).where(User.id == verification.user_id)).scalar_one_or_none()
        if not user:
            return False, "User not found."

        user.email_verified = True
        verification.used = True
        db.commit()
        return True, "Email verified successfully! You can now log in."
    except Exception as e:
        db.rollback()
        return False, f"Verification failed: {str(e)}"
    finally:
        db.close()


def init_session_state():
    """Initialize auth-related session state."""
    defaults = {
        "authenticated": False,
        "user_id": None,
        "user_email": None,
        "user_display_name": None,
        "is_admin": False,
        "email_verified": False,
        "auth_page": "login",  # "login" or "signup"
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


def logout():
    """Clear session and log out."""
    for key in ["authenticated", "user_id", "user_email", "user_display_name", "is_admin", "email_verified"]:
        st.session_state[key] = None if key != "authenticated" else False
    st.session_state["auth_page"] = "login"


def render_auth_page():
    """Render login or signup page. Returns True if user is authenticated."""
    init_session_state()

    # Check for email verification token in query params
    params = st.query_params
    if "verify" in params:
        token = params["verify"]
        success, msg = verify_email_token(token)
        if success:
            st.success(msg)
        else:
            st.error(msg)
        st.query_params.clear()

    if st.session_state["authenticated"]:
        return True

    # Center the auth form
    col_left, col_center, col_right = st.columns([1, 2, 1])

    with col_center:
        st.markdown("# Adaptive Trading Ecosystem")
        st.markdown("---")

        if st.session_state["auth_page"] == "login":
            _render_login()
        else:
            _render_signup()

    return False


def _render_login():
    """Render the login form."""
    st.markdown("### Sign In")

    with st.form("login_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign In", use_container_width=True)

        if submitted:
            if not email or not password:
                st.error("Please fill in all fields.")
            else:
                success, result = authenticate(email, password)
                if success:
                    st.session_state["authenticated"] = True
                    st.session_state["user_id"] = result["user_id"]
                    st.session_state["user_email"] = result["email"]
                    st.session_state["user_display_name"] = result["display_name"]
                    st.session_state["is_admin"] = result["is_admin"]
                    st.session_state["email_verified"] = result["email_verified"]
                    st.rerun()
                else:
                    st.error(result)

    st.markdown("---")
    if st.button("Don't have an account? Sign up", use_container_width=True):
        st.session_state["auth_page"] = "signup"
        st.rerun()


def _render_signup():
    """Render the signup form."""
    st.markdown("### Create Account")

    with st.form("signup_form"):
        display_name = st.text_input("Display Name")
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        confirm = st.text_input("Confirm Password", type="password")
        submitted = st.form_submit_button("Create Account", use_container_width=True)

        if submitted:
            if not all([display_name, email, password, confirm]):
                st.error("Please fill in all fields.")
            elif password != confirm:
                st.error("Passwords don't match.")
            else:
                success, result = create_user(email, password, display_name)
                if success:
                    # Auto-login after signup
                    ok, user_data = authenticate(email, password)
                    if ok:
                        st.session_state["authenticated"] = True
                        st.session_state["user_id"] = user_data["user_id"]
                        st.session_state["user_email"] = user_data["email"]
                        st.session_state["user_display_name"] = user_data["display_name"]
                        st.session_state["is_admin"] = user_data["is_admin"]
                        st.session_state["email_verified"] = user_data["email_verified"]
                        st.success("Account created! Check your email for verification.")
                        st.rerun()
                else:
                    st.error(result)

    st.markdown("---")
    if st.button("Already have an account? Sign in", use_container_width=True):
        st.session_state["auth_page"] = "login"
        st.rerun()
```

**Step 2: Commit**

```bash
cd /Users/andrewpeterson/adaptive-trading-ecosystem
git add dashboard/auth.py
git commit -m "feat: add auth module with login, signup, email verification, session mgmt"
```

---

### Task 4: Create the Broker Settings Page

**Files:**
- Create: `dashboard/broker_settings.py`

**Step 1: Create dashboard/broker_settings.py**

```python
"""
Broker credential management page.
Users add/edit/remove their encrypted broker API keys here.
"""

import streamlit as st
from sqlalchemy import select, delete

from dashboard.auth import get_db
from db.models import BrokerCredential, BrokerType
from db.encryption import encrypt_value, decrypt_value


def render_broker_settings():
    """Render the broker settings management page."""
    user_id = st.session_state.get("user_id")
    if not user_id:
        return

    st.subheader("Broker Connections")
    st.markdown("Connect your brokerage accounts. API keys are encrypted at rest.")

    # Load existing credentials
    db = get_db()
    try:
        creds = db.execute(
            select(BrokerCredential).where(BrokerCredential.user_id == user_id)
        ).scalars().all()
    finally:
        db.close()

    # Display existing connections
    if creds:
        st.markdown("#### Your Connected Brokers")
        for cred in creds:
            with st.expander(f"{cred.broker_type.value.title()} — {cred.nickname or 'Unnamed'} ({'Paper' if cred.is_paper else 'Live'})"):
                st.markdown(f"**Type:** {cred.broker_type.value.title()}")
                st.markdown(f"**Mode:** {'Paper' if cred.is_paper else 'Live'}")
                st.markdown(f"**Added:** {cred.created_at.strftime('%Y-%m-%d')}")

                # Show masked key
                try:
                    key_preview = decrypt_value(cred.encrypted_api_key)
                    st.markdown(f"**API Key:** `{key_preview[:6]}...{key_preview[-4:]}`")
                except Exception:
                    st.markdown("**API Key:** `[encrypted]`")

                if st.button(f"Remove", key=f"remove_{cred.id}"):
                    db = get_db()
                    try:
                        db.execute(delete(BrokerCredential).where(BrokerCredential.id == cred.id))
                        db.commit()
                        st.success("Broker removed.")
                        st.rerun()
                    except Exception as e:
                        db.rollback()
                        st.error(f"Failed to remove: {e}")
                    finally:
                        db.close()

    # Add new broker
    st.markdown("---")
    st.markdown("#### Add Broker Connection")

    with st.form("add_broker_form"):
        broker_type = st.selectbox("Broker", ["Alpaca", "Webull"])
        nickname = st.text_input("Nickname (optional)", placeholder="e.g. My Paper Account")
        api_key = st.text_input("API Key", type="password")
        api_secret = st.text_input("API Secret", type="password")
        is_paper = st.checkbox("Paper Trading", value=True)
        submitted = st.form_submit_button("Save Broker", use_container_width=True)

        if submitted:
            if not api_key or not api_secret:
                st.error("API Key and Secret are required.")
            else:
                db = get_db()
                try:
                    cred = BrokerCredential(
                        user_id=user_id,
                        broker_type=BrokerType.ALPACA if broker_type == "Alpaca" else BrokerType.WEBULL,
                        encrypted_api_key=encrypt_value(api_key),
                        encrypted_api_secret=encrypt_value(api_secret),
                        is_paper=is_paper,
                        nickname=nickname.strip() or None,
                    )
                    db.add(cred)
                    db.commit()
                    st.success(f"{broker_type} credentials saved (encrypted).")
                    st.rerun()
                except Exception as e:
                    db.rollback()
                    st.error(f"Failed to save: {e}")
                finally:
                    db.close()
```

**Step 2: Commit**

```bash
cd /Users/andrewpeterson/adaptive-trading-ecosystem
git add dashboard/broker_settings.py
git commit -m "feat: add broker settings page with encrypted credential management"
```

---

### Task 5: Create the Admin Dashboard

**Files:**
- Create: `dashboard/admin.py`

**Step 1: Create dashboard/admin.py**

```python
"""
Admin dashboard — only visible to users with is_admin=True.
Shows platform stats, user management, and system overview.
"""

import streamlit as st
from sqlalchemy import select, func, update
from datetime import datetime, timedelta

from dashboard.auth import get_db
from db.models import User, BrokerCredential


def render_admin_dashboard():
    """Render the admin panel. Only call if user is admin."""
    if not st.session_state.get("is_admin"):
        st.error("Access denied.")
        return

    st.subheader("Admin Dashboard")

    db = get_db()
    try:
        # Platform stats
        total_users = db.execute(select(func.count(User.id))).scalar()
        active_users = db.execute(select(func.count(User.id)).where(User.is_active == True)).scalar()
        verified_users = db.execute(select(func.count(User.id)).where(User.email_verified == True)).scalar()

        week_ago = datetime.utcnow() - timedelta(days=7)
        month_ago = datetime.utcnow() - timedelta(days=30)
        new_7d = db.execute(select(func.count(User.id)).where(User.created_at >= week_ago)).scalar()
        new_30d = db.execute(select(func.count(User.id)).where(User.created_at >= month_ago)).scalar()
        total_broker_connections = db.execute(select(func.count(BrokerCredential.id))).scalar()

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Users", total_users)
        col2.metric("Active", active_users)
        col3.metric("Verified", verified_users)
        col4.metric("Broker Connections", total_broker_connections)

        col5, col6 = st.columns(2)
        col5.metric("New (7d)", new_7d)
        col6.metric("New (30d)", new_30d)

        # User list
        st.markdown("---")
        st.markdown("#### User Management")

        users = db.execute(
            select(User).order_by(User.created_at.desc())
        ).scalars().all()

        for user in users:
            with st.expander(f"{user.display_name} ({user.email})"):
                col_a, col_b, col_c = st.columns(3)
                col_a.markdown(f"**ID:** {user.id}")
                col_b.markdown(f"**Joined:** {user.created_at.strftime('%Y-%m-%d')}")
                col_c.markdown(f"**Verified:** {'Yes' if user.email_verified else 'No'}")

                # Toggle active
                new_active = st.checkbox(
                    "Account Active",
                    value=user.is_active,
                    key=f"active_{user.id}",
                )
                if new_active != user.is_active:
                    db.execute(
                        update(User).where(User.id == user.id).values(is_active=new_active)
                    )
                    db.commit()
                    st.success(f"{'Enabled' if new_active else 'Disabled'} {user.email}")
                    st.rerun()
    finally:
        db.close()
```

**Step 2: Commit**

```bash
cd /Users/andrewpeterson/adaptive-trading-ecosystem
git add dashboard/admin.py
git commit -m "feat: add admin dashboard with user management and platform stats"
```

---

### Task 6: Create Database Init Script

**Files:**
- Create: `scripts/create_admin.py`

**Step 1: Create scripts/create_admin.py**

This script creates tables and an initial admin user.

```python
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
```

**Step 2: Commit**

```bash
cd /Users/andrewpeterson/adaptive-trading-ecosystem
git add scripts/create_admin.py
git commit -m "feat: add database init script with admin user creation"
```

---

### Task 7: Integrate Auth Gate into Dashboard app.py

This is the critical task — wrapping the entire existing dashboard behind the auth gate.

**Files:**
- Modify: `dashboard/app.py:1-1598`

**Step 1: Add auth imports at the top of app.py**

After the existing imports (after line 21, after `import streamlit as st`), add:

```python
from dashboard.auth import render_auth_page, logout, init_session_state
```

**Step 2: Add auth gate after st.set_page_config (after line 30)**

Insert immediately after `st.set_page_config(...)` and before the CSS block:

```python
# ── Auth Gate ───────────────────────────────────────────────────────────
init_session_state()

if not render_auth_page():
    st.stop()

# Show email verification banner if needed
if not st.session_state.get("email_verified"):
    st.warning("Please verify your email address. Check your inbox for a verification link.")
```

**Step 3: Add user info and logout to sidebar**

Find the sidebar section (around line 382):
```python
st.sidebar.markdown("## Adaptive Trading Ecosystem")
```

Replace that line with:

```python
st.sidebar.markdown("## Adaptive Trading Ecosystem")
st.sidebar.markdown(f"**{st.session_state['user_display_name']}**")
st.sidebar.caption(st.session_state["user_email"])
if st.sidebar.button("Logout", use_container_width=True):
    logout()
    st.rerun()
st.sidebar.divider()
```

**Step 4: Add Broker Settings and Admin tabs**

Find where tabs are created (search for `st.tabs`). Add "Broker Settings" tab, and conditionally add "Admin" tab.

After the existing tab creation, add imports and rendering:

```python
from dashboard.broker_settings import render_broker_settings
from dashboard.admin import render_admin_dashboard
```

The exact tab integration depends on how tabs are structured. The key pattern:
- Add `"Broker Settings"` to the tabs list
- If `st.session_state.get("is_admin")`: add `"Admin"` to the tabs list
- In the broker settings tab content: call `render_broker_settings()`
- In the admin tab content: call `render_admin_dashboard()`

**Step 5: Verify the dashboard runs**

Run: `cd /Users/andrewpeterson/adaptive-trading-ecosystem && python3 -m streamlit run dashboard/app.py`

Expected: Login page appears instead of the dashboard. Sign up → redirects to dashboard.

**Step 6: Commit**

```bash
cd /Users/andrewpeterson/adaptive-trading-ecosystem
git add dashboard/app.py
git commit -m "feat: integrate auth gate, user sidebar, broker settings, and admin tabs into dashboard"
```

---

### Task 8: Initialize Database and Test End-to-End

**Step 1: Generate an encryption key**

Run: `cd /Users/andrewpeterson/adaptive-trading-ecosystem && python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`

Copy the output and add it to `.env` as `ENCRYPTION_KEY=<the key>`.

**Step 2: Ensure PostgreSQL is running**

Run: `pg_isready -h localhost -p 5432`

If not running, start it: `brew services start postgresql@16` (or whichever version is installed).

**Step 3: Create the database (if it doesn't exist)**

Run: `createdb trading_ecosystem 2>/dev/null; echo "DB ready"`

**Step 4: Run the init script**

Run: `cd /Users/andrewpeterson/adaptive-trading-ecosystem && python scripts/create_admin.py`

Expected: "All tables created." and "Admin user created: admin@example.com / changeme123"

**Step 5: Start the dashboard and test**

Run: `cd /Users/andrewpeterson/adaptive-trading-ecosystem && python3 -m streamlit run dashboard/app.py`

Test these flows:
1. Login page appears on first visit
2. Sign up with a new email → account created → auto-login → dashboard visible
3. Logout → back to login page
4. Login with admin@example.com / changeme123 → see Admin tab
5. Broker Settings tab → add Alpaca paper credentials → credentials saved
6. Admin tab → see user list and stats

**Step 6: Final commit**

```bash
cd /Users/andrewpeterson/adaptive-trading-ecosystem
git add -A
git commit -m "feat: complete multi-user auth system with email verification, broker encryption, admin dashboard"
```

---

### Task 9: Write Tests

**Files:**
- Create: `tests/test_auth.py`

**Step 1: Write auth tests**

```python
"""Tests for the authentication module."""

import pytest
from unittest.mock import patch, MagicMock
from dashboard.auth import hash_password, verify_password, is_valid_email


def test_hash_password_returns_bcrypt_string():
    hashed = hash_password("testpassword")
    assert hashed.startswith("$2b$")
    assert len(hashed) > 50


def test_verify_password_correct():
    hashed = hash_password("mypassword")
    assert verify_password("mypassword", hashed) is True


def test_verify_password_incorrect():
    hashed = hash_password("mypassword")
    assert verify_password("wrongpassword", hashed) is False


def test_is_valid_email_accepts_valid():
    assert is_valid_email("user@example.com") is True
    assert is_valid_email("first.last@company.co.uk") is True


def test_is_valid_email_rejects_invalid():
    assert is_valid_email("not-an-email") is False
    assert is_valid_email("@missing.com") is False
    assert is_valid_email("user@") is False
    assert is_valid_email("") is False
```

**Step 2: Write encryption tests**

Create `tests/test_encryption.py`:

```python
"""Tests for broker credential encryption."""

import pytest
from unittest.mock import patch
from cryptography.fernet import Fernet


# Generate a test key
TEST_KEY = Fernet.generate_key().decode()


@patch("db.encryption.get_settings")
def test_encrypt_decrypt_roundtrip(mock_settings):
    mock_settings.return_value.encryption_key = TEST_KEY
    from db.encryption import encrypt_value, decrypt_value

    original = "sk-test-api-key-12345"
    encrypted = encrypt_value(original)
    assert encrypted != original
    decrypted = decrypt_value(encrypted)
    assert decrypted == original


@patch("db.encryption.get_settings")
def test_encrypt_produces_different_ciphertext(mock_settings):
    mock_settings.return_value.encryption_key = TEST_KEY
    from db.encryption import encrypt_value

    ct1 = encrypt_value("same-input")
    ct2 = encrypt_value("same-input")
    # Fernet uses random IV, so ciphertexts should differ
    assert ct1 != ct2
```

**Step 3: Run tests**

Run: `cd /Users/andrewpeterson/adaptive-trading-ecosystem && python -m pytest tests/test_auth.py tests/test_encryption.py -v`

Expected: All tests pass.

**Step 4: Commit**

```bash
cd /Users/andrewpeterson/adaptive-trading-ecosystem
git add tests/test_auth.py tests/test_encryption.py
git commit -m "test: add auth and encryption unit tests"
```
