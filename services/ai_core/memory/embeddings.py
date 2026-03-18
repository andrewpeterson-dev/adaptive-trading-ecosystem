"""Embedding service — generates vector embeddings via OpenAI."""
from __future__ import annotations

from typing import Optional

import structlog

from config.settings import get_settings

logger = structlog.get_logger(__name__)


class EmbeddingService:
    """Wraps the OpenAI embeddings API (text-embedding-3-large).

    Gracefully returns empty results when no OpenAI API key is configured,
    since embeddings require OpenAI (Anthropic doesn't offer an embeddings API).
    """

    def __init__(self, model: Optional[str] = None):
        settings = get_settings()
        self._model = model or settings.openai_embedding_model
        self._api_key = settings.openai_api_key

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts.

        Returns a list of float vectors, one per input text.
        Returns empty list if no OpenAI API key is configured.
        """
        if not texts:
            return []

        if not self._api_key:
            logger.warning("embeddings_skipped_no_openai_key", text_count=len(texts))
            return []

        try:
            import openai

            client = openai.AsyncOpenAI(api_key=self._api_key)
            response = await client.embeddings.create(
                model=self._model,
                input=texts,
            )
            embeddings = [item.embedding for item in response.data]
            logger.debug(
                "embeddings_generated",
                count=len(embeddings),
                model=self._model,
            )
            return embeddings

        except Exception:
            logger.exception("embedding_error", text_count=len(texts))
            return []

    async def embed_single(self, text: str) -> list[float]:
        """Generate an embedding for a single text string."""
        results = await self.embed([text])
        if not results:
            return []
        return results[0]
