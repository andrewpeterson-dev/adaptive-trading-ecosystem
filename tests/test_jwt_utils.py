"""Tests for fail-closed JWT helpers."""

import pytest

from config.settings import Settings
from services.security.jwt_utils import JWTConfigurationError, decode_jwt, encode_jwt


def test_jwt_round_trip_with_configured_secret():
    settings = Settings(jwt_secret="unit-test-secret-0123456789abcdef", _env_file=None)
    token = encode_jwt({"user_id": 42, "scope": "chat"}, settings)

    payload = decode_jwt(token, settings)

    assert payload["user_id"] == 42
    assert payload["scope"] == "chat"


def test_jwt_encoding_fails_when_secret_missing():
    settings = Settings(jwt_secret="", _env_file=None)

    with pytest.raises(JWTConfigurationError):
        encode_jwt({"user_id": 42}, settings)
