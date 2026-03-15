"""Transactional email helpers for account verification and password reset."""

from __future__ import annotations

import asyncio
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from urllib.parse import quote, urlsplit

import structlog

from config.settings import Settings, get_settings

logger = structlog.get_logger(__name__)


@dataclass
class EmailDispatchResult:
    delivered: bool
    preview_url: str | None = None


def email_delivery_enabled(settings: Settings | None = None) -> bool:
    active_settings = settings or get_settings()
    return bool(
        active_settings.smtp_user.strip()
        and active_settings.smtp_password.strip()
        and active_settings.base_url.strip()
    )


def _allow_local_preview(settings: Settings) -> bool:
    return bool(settings.allow_auth_link_preview)


def auth_email_flow_available(settings: Settings | None = None) -> bool:
    active_settings = settings or get_settings()
    return email_delivery_enabled(active_settings) or _allow_local_preview(active_settings)


def _sender(settings: Settings) -> str:
    return settings.smtp_user.strip() or "no-reply@adaptive-trading.local"


def _build_message(recipient: str, *, subject: str, text_body: str) -> EmailMessage:
    settings = get_settings()
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = _sender(settings)
    message["To"] = recipient
    message.set_content(text_body)
    return message


def _send_message_sync(message: EmailMessage, settings: Settings) -> None:
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
        server.starttls()
        server.login(settings.smtp_user, settings.smtp_password)
        server.send_message(message)


def _preview_path(preview_url: str | None) -> str | None:
    if not preview_url:
        return None
    try:
        return urlsplit(preview_url).path or None
    except ValueError:
        return None


async def _deliver_email(
    recipient: str,
    *,
    subject: str,
    text_body: str,
    preview_url: str | None = None,
) -> EmailDispatchResult:
    settings = get_settings()
    if not email_delivery_enabled(settings):
        if preview_url and _allow_local_preview(settings):
            logger.info(
                "auth_email_preview",
                recipient=recipient,
                preview_path=_preview_path(preview_url),
                subject=subject,
            )
            return EmailDispatchResult(delivered=False, preview_url=preview_url)
        logger.warning("auth_email_unavailable", recipient=recipient, subject=subject)
        return EmailDispatchResult(delivered=False, preview_url=None)

    message = _build_message(recipient, subject=subject, text_body=text_body)
    try:
        await asyncio.to_thread(_send_message_sync, message, settings)
        logger.info("auth_email_sent", recipient=recipient, subject=subject)
        return EmailDispatchResult(delivered=True, preview_url=None)
    except Exception as exc:  # pragma: no cover - network failure path
        logger.warning(
            "auth_email_send_failed",
            recipient=recipient,
            subject=subject,
            error_type=type(exc).__name__,
        )
        if preview_url and _allow_local_preview(settings):
            logger.info(
                "auth_email_preview",
                recipient=recipient,
                preview_path=_preview_path(preview_url),
                subject=subject,
            )
            return EmailDispatchResult(delivered=False, preview_url=preview_url)
        return EmailDispatchResult(delivered=False, preview_url=None)


async def send_verification_email(email: str, token: str) -> EmailDispatchResult:
    settings = get_settings()
    verification_url = f"{settings.base_url.rstrip('/')}/verify-email?token={quote(token)}"
    text_body = (
        "Verify your Adaptive Trading account.\n\n"
        f"Open this link to finish setup:\n{verification_url}\n\n"
        "This link expires in 24 hours. If you did not request this account, you can ignore this email.\n"
    )
    return await _deliver_email(
        email,
        subject="Verify your Adaptive Trading account",
        text_body=text_body,
        preview_url=verification_url,
    )


async def send_password_reset_email(email: str, token: str) -> EmailDispatchResult:
    settings = get_settings()
    reset_url = f"{settings.base_url.rstrip('/')}/reset-password?token={quote(token)}"
    text_body = (
        "Reset your Adaptive Trading password.\n\n"
        f"Open this link to choose a new password:\n{reset_url}\n\n"
        "This link expires in 30 minutes. If you did not request a reset, you can ignore this email.\n"
    )
    return await _deliver_email(
        email,
        subject="Reset your Adaptive Trading password",
        text_body=text_body,
        preview_url=reset_url,
    )
