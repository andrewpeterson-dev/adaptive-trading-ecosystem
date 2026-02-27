"""Tests for broker credential encryption."""

import pytest
from unittest.mock import patch, MagicMock
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
