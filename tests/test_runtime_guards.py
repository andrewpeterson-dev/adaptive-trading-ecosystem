"""Focused runtime guardrail tests for recent backend fixes."""

from config.settings import Settings
from api.main import _is_readiness_exempt_path
from api.routes.webull import _client_cache, invalidate_user_client_cache


def test_database_url_sync_uses_sqlite_when_enabled(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)

    settings = Settings(use_sqlite=True, _env_file=None)

    assert settings.database_url_sync == "sqlite:///trading_ecosystem.db"


def test_invalidate_user_client_cache_clears_all_modes():
    _client_cache.clear()
    _client_cache[(7, "paper")] = object()
    _client_cache[(7, "real")] = object()
    _client_cache[(8, "paper")] = object()

    removed = invalidate_user_client_cache(7)

    assert removed == 2
    assert (7, "paper") not in _client_cache
    assert (7, "real") not in _client_cache
    assert (8, "paper") in _client_cache
    _client_cache.clear()


def test_readiness_guard_exempts_only_public_startup_paths():
    assert _is_readiness_exempt_path("/health") is True
    assert _is_readiness_exempt_path("/health/ready") is True
    assert _is_readiness_exempt_path("/api/auth/login") is True
    assert _is_readiness_exempt_path("/ws/socket") is True
    assert _is_readiness_exempt_path("/api/models/list") is False
