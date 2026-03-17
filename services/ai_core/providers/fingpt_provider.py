"""FinGPT provider for financial sentiment analysis via HuggingFace Inference API."""
from __future__ import annotations

import asyncio
import json
import re
from typing import Any, AsyncIterator, Dict, Optional

import httpx
import structlog

from config.settings import get_settings
from .base import (
    BaseProvider, ProviderMessage, ProviderToolDef,
    ProviderResponse, StreamChunk,
)

logger = structlog.get_logger(__name__)

HUGGINGFACE_INFERENCE_URL = "https://api-inference.huggingface.co/models"
DEFAULT_FINGPT_MODEL = "FinGPT/fingpt-sentiment_llama2-13b_lora"

_FINANCE_SENTIMENT_SYSTEM_PROMPT = (
    "You are a financial sentiment analysis expert. "
    "Analyze the provided text and determine the market sentiment. "
    "Respond ONLY with valid JSON in this exact format:\n"
    '{"sentiment": "bullish" or "bearish" or "neutral", '
    '"score": <float from -1.0 (most bearish) to 1.0 (most bullish)>, '
    '"confidence": <float from 0.0 to 1.0>}\n'
    "Consider the financial implications, market impact, and tone of the text. "
    "Do not include any other text, only the JSON object."
)

_FINGPT_PROMPT_TEMPLATE = (
    "Instruction: What is the sentiment of this news? "
    "Please choose an answer from {{negative/neutral/positive}}.\n"
    "Input: {text}\n"
    "Answer: "
)

_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 529}


def _parse_fingpt_response(raw_output: str) -> Dict[str, Any]:
    text = raw_output.strip().lower()
    if "positive" in text:
        sentiment, score = "bullish", 0.7
    elif "negative" in text:
        sentiment, score = "bearish", -0.7
    elif "neutral" in text:
        sentiment, score = "neutral", 0.0
    else:
        sentiment, score = "neutral", 0.0

    score_match = re.search(r"[-+]?\d*\.?\d+", text)
    if score_match:
        try:
            extracted = float(score_match.group())
            if -1.0 <= extracted <= 1.0:
                score = extracted
        except ValueError:
            pass

    confidence = min(abs(score) + 0.3, 1.0) if score != 0.0 else 0.5
    return {"sentiment": sentiment, "score": round(score, 4), "confidence": round(confidence, 4)}


def _parse_gpt_sentiment_response(content: str) -> Dict[str, Any]:
    try:
        json_match = re.search(r"\{[^}]+\}", content)
        if json_match:
            data = json.loads(json_match.group())
            sentiment = data.get("sentiment", "neutral").lower()
            if sentiment not in ("bullish", "bearish", "neutral"):
                sentiment = "neutral"
            score = max(-1.0, min(1.0, float(data.get("score", 0.0))))
            confidence = max(0.0, min(1.0, float(data.get("confidence", 0.5))))
            return {"sentiment": sentiment, "score": round(score, 4), "confidence": round(confidence, 4)}
    except (json.JSONDecodeError, ValueError, TypeError):
        pass
    return {"sentiment": "neutral", "score": 0.0, "confidence": 0.0}


class FinGPTProvider(BaseProvider):
    """FinGPT provider for financial sentiment analysis."""

    provider_name = "fingpt"

    def __init__(self) -> None:
        settings = get_settings()
        self._hf_api_key: str = settings.fingpt_api_key
        self._hf_endpoint: str = settings.fingpt_endpoint
        self._enabled: bool = settings.fingpt_enabled
        self._openai_api_key: str = settings.openai_api_key
        self._openai_fallback_model: str = settings.openai_primary_model
        self._openai_client: Optional[Any] = None

    def _get_openai_client(self) -> Any:
        if self._openai_client is None:
            import openai
            self._openai_client = openai.AsyncOpenAI(api_key=self._openai_api_key)
        return self._openai_client

    async def analyze_sentiment(self, text: str) -> Dict[str, Any]:
        if self._enabled and self._hf_api_key:
            try:
                result = await self._analyze_with_fingpt(text)
                if result is not None:
                    return result
            except Exception as exc:
                logger.warning("fingpt_primary_failed", error=str(exc))
        return await self._analyze_with_gpt_fallback(text)

    async def _analyze_with_fingpt(self, text: str) -> Optional[Dict[str, Any]]:
        prompt = _FINGPT_PROMPT_TEMPLATE.format(text=text[:2000])
        endpoint = self._hf_endpoint or f"{HUGGINGFACE_INFERENCE_URL}/{DEFAULT_FINGPT_MODEL}"
        headers = {"Authorization": f"Bearer {self._hf_api_key}", "Content-Type": "application/json"}
        payload = {"inputs": prompt, "parameters": {"max_new_tokens": 50, "temperature": 0.1, "return_full_text": False}}

        settings = get_settings()
        max_retries = settings.llm_max_retries

        for attempt in range(max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.post(endpoint, headers=headers, json=payload)
                    if resp.status_code in _RETRYABLE_STATUS_CODES and attempt < max_retries:
                        delay = 2 ** attempt
                        logger.warning("fingpt_retry", attempt=attempt + 1, delay=delay, status=resp.status_code)
                        await asyncio.sleep(delay)
                        continue
                    resp.raise_for_status()
                    data = resp.json()

                raw_output = ""
                if isinstance(data, list) and data:
                    raw_output = data[0].get("generated_text", "")
                elif isinstance(data, dict):
                    raw_output = data.get("generated_text", "")

                if not raw_output:
                    logger.warning("fingpt_empty_response", data=data)
                    return None

                result = _parse_fingpt_response(raw_output)
                logger.info("fingpt_sentiment_result", sentiment=result["sentiment"], score=result["score"], text_preview=text[:80])
                return result
            except httpx.HTTPStatusError:
                raise
            except Exception as exc:
                if attempt < max_retries:
                    delay = 2 ** attempt
                    logger.warning("fingpt_retry", attempt=attempt + 1, delay=delay, error=str(exc))
                    await asyncio.sleep(delay)
                else:
                    raise
        return None

    async def _analyze_with_gpt_fallback(self, text: str) -> Dict[str, Any]:
        logger.info("fingpt_gpt_fallback", text_preview=text[:80])
        client = self._get_openai_client()
        messages = [
            {"role": "system", "content": _FINANCE_SENTIMENT_SYSTEM_PROMPT},
            {"role": "user", "content": f"Analyze the financial sentiment of this text:\n\n{text[:3000]}"},
        ]
        try:
            response = await client.responses.create(model=self._openai_fallback_model, input=messages, temperature=0.1, max_output_tokens=256, store=False)
            content = ""
            for item in response.output:
                if item.type == "message":
                    for block in item.content:
                        if hasattr(block, "text"):
                            content += block.text
            return _parse_gpt_sentiment_response(content)
        except Exception as exc:
            logger.error("fingpt_gpt_fallback_failed", error=str(exc))
            return {"sentiment": "neutral", "score": 0.0, "confidence": 0.0}

    async def complete(self, messages: list[ProviderMessage], model: str, tools: Optional[list[ProviderToolDef]] = None, temperature: float = 0.1, max_tokens: int = 256, response_format: Optional[dict] = None, store: bool = False, **kwargs: Any) -> ProviderResponse:
        user_text = ""
        for msg in reversed(messages):
            if msg.role == "user":
                user_text = msg.content
                break
        if not user_text:
            return ProviderResponse(content=json.dumps({"sentiment": "neutral", "score": 0.0, "confidence": 0.0}), model=model)
        result = await self.analyze_sentiment(user_text)
        return ProviderResponse(content=json.dumps(result), model=model, finish_reason="stop")

    async def stream(self, messages: list[ProviderMessage], model: str, tools: Optional[list[ProviderToolDef]] = None, temperature: float = 0.1, max_tokens: int = 256, response_format: Optional[dict] = None, store: bool = False, **kwargs: Any) -> AsyncIterator[StreamChunk]:
        response = await self.complete(messages, model, tools, temperature, max_tokens, response_format, store, **kwargs)
        yield StreamChunk(delta_text=response.content, finish_reason="stop")
