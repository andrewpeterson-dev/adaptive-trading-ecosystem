"""
LLM status endpoint — reports which backend is active and health stats.
"""

from fastapi import APIRouter, Request

from config.settings import get_settings
from typing import Optional
from intelligence.ollama_client import OllamaClient
from services.security.access_control import require_admin

router = APIRouter()

_ollama_client: Optional[OllamaClient] = None


def _get_ollama_client() -> OllamaClient:
    global _ollama_client
    if _ollama_client is None:
        _ollama_client = OllamaClient()
    return _ollama_client


@router.get("/llm-status")
async def llm_status(request: Request):
    """Return LLM backend status, health, and availability."""
    await require_admin(request)
    settings = get_settings()
    ollama = _get_ollama_client()

    ollama_health = await ollama.health_check()
    ollama_available = ollama_health.get("available", False)

    # Determine primary backend
    if settings.ollama_enabled and ollama_available:
        primary_backend = "ollama"
        active_model = settings.ollama_model
    else:
        configured_backend = (settings.llm_provider or "anthropic").lower()
        primary_backend = "openai" if configured_backend == "openai" else "claude"
        active_model = settings.llm_model

    claude_available = bool(settings.anthropic_api_key)
    openai_available = bool(settings.openai_api_key)

    return {
        "primary_backend": primary_backend,
        "active_model": active_model,
        "ollama": {
            "enabled": settings.ollama_enabled,
            "available": ollama_available,
            "model": settings.ollama_model,
            "latency_ms": ollama_health.get("latency_ms"),
            "model_loaded": ollama_health.get("model_loaded", False),
            "error": ollama_health.get("error"),
        },
        "claude": {
            "available": claude_available,
            "model": settings.llm_model if primary_backend == "claude" else settings.anthropic_fallback_model,
        },
        "openai": {
            "available": openai_available,
            "model": settings.llm_model if primary_backend == "openai" else settings.openai_primary_model,
        },
        "router_stats": ollama.get_stats(),
    }
