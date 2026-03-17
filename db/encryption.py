"""Fernet symmetric encryption for broker API credentials."""

import structlog
from cryptography.fernet import Fernet, InvalidToken

from config.settings import get_settings

logger = structlog.get_logger(__name__)


def _get_fernet() -> Fernet:
    key = get_settings().encryption_key
    if not key:
        raise RuntimeError(
            "ENCRYPTION_KEY not set. Generate one with: "
            "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    try:
        return Fernet(key.encode())
    except (ValueError, Exception) as exc:
        raise RuntimeError(
            f"ENCRYPTION_KEY is invalid (not a valid Fernet key): {exc}. "
            "Generate a new one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        ) from exc


def encrypt_value(plaintext: str) -> str:
    """Encrypt a string and return base64-encoded ciphertext."""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_value(ciphertext: str) -> str:
    """Decrypt a base64-encoded ciphertext back to plaintext."""
    try:
        return _get_fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        logger.error(
            "decryption_failed",
            hint="ENCRYPTION_KEY may have changed since this value was encrypted — credentials need re-entry",
        )
        raise RuntimeError(
            "Unable to decrypt stored credentials. The encryption key may have changed. "
            "Please re-enter your broker credentials."
        )
