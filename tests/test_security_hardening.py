from __future__ import annotations

import json
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes.intelligence import router as intelligence_router
from config.settings import Settings
from services.security.request_origin import websocket_origin_allowed


def test_websocket_origin_allowed_matches_configured_frontend_origins():
    settings = Settings(
        base_url="https://app.example.com",
        frontend_url="https://app.example.com",
        cors_origins="https://app.example.com,https://staging.example.com",
    )

    assert websocket_origin_allowed(
        SimpleNamespace(headers={"origin": "https://app.example.com"}),
        settings,
    )
    assert websocket_origin_allowed(
        SimpleNamespace(headers={"origin": "https://staging.example.com"}),
        settings,
    )
    assert not websocket_origin_allowed(
        SimpleNamespace(headers={"origin": "https://evil.example.com"}),
        settings,
    )
    assert not websocket_origin_allowed(
        SimpleNamespace(headers={}),
        settings,
    )


def test_intelligence_analyze_requires_structured_json(monkeypatch):
    class StubRouter:
        async def route(self, prompt: str):
            return {
                "response": json.dumps(
                    {
                        "direction": "long",
                        "confidence_score": 72,
                        "analysis": "Momentum is improving on strong breadth.",
                        "risk_level": "medium",
                        "key_factors": ["breadth expansion", "earnings revisions"],
                    }
                ),
                "backend": "stub",
            }

    monkeypatch.setattr("api.routes.intelligence._llm_router", StubRouter())
    app = FastAPI()
    app.include_router(intelligence_router, prefix="/api/intelligence")

    with TestClient(app) as client:
        response = client.post(
            "/api/intelligence/analyze",
            json={"symbol": "AAPL", "context": "Focus on near-term momentum"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["direction"] == "long"
    assert payload["confidence_score"] == 72
    assert payload["risk_level"] == "medium"
    assert payload["key_factors"] == ["breadth expansion", "earnings revisions"]


def test_intelligence_analyze_rejects_unstructured_payload(monkeypatch):
    class StubRouter:
        async def route(self, prompt: str):
            return {
                "response": "Bullish with confidence 80 and low risk.",
                "backend": "stub",
            }

    monkeypatch.setattr("api.routes.intelligence._llm_router", StubRouter())
    app = FastAPI()
    app.include_router(intelligence_router, prefix="/api/intelligence")

    with TestClient(app) as client:
        response = client.post("/api/intelligence/analyze", json={"symbol": "MSFT"})

    assert response.status_code == 502
    assert response.json()["detail"] == "LLM returned an invalid analysis payload"
