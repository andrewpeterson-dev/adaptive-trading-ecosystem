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
