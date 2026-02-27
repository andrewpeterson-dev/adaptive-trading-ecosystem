"""
Authentication module for the Streamlit dashboard.
Handles login, signup, email verification, and session management.
"""
from __future__ import annotations

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
