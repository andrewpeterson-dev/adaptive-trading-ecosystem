"""
Sentiment classification using Claude API.
Classifies news articles for trading signal generation.
"""

import json
import time

import structlog

from config.settings import get_settings

logger = structlog.get_logger(__name__)


class SentimentClassifier:
    """Classify news sentiment using Claude API."""

    def __init__(self):
        self.settings = get_settings()
        self._client = None

    def _get_client(self):
        """Lazy-init Anthropic client."""
        if self._client is not None:
            return self._client
        if not self.settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY not set. Add it to your .env file.")
        import anthropic
        self._client = anthropic.Anthropic(api_key=self.settings.anthropic_api_key)
        return self._client

    def classify(self, article: dict, symbol: str) -> dict:
        """
        Classify a single article's sentiment for a ticker.
        Returns: {
            "sentiment": "positive" | "neutral" | "negative",
            "score": float,  # -5 to +5
            "relevance": float,  # 0 to 1
            "reasoning": str
        }
        """
        return self.classify_batch([article], symbol)[0]

    def classify_batch(self, articles: list[dict], symbol: str) -> list[dict]:
        """Classify multiple articles in a single LLM call for efficiency."""
        if not articles:
            return []

        # Build compact article summaries for the prompt
        article_texts = []
        for i, a in enumerate(articles):
            article_texts.append(
                f"[{i}] \"{a.get('title', 'No title')}\" — {a.get('source', 'Unknown')} "
                f"({a.get('published_at', 'Unknown date')})\n"
                f"Summary: {(a.get('summary', '') or 'N/A')[:300]}"
            )

        articles_block = "\n\n".join(article_texts)

        prompt = f"""Analyze the following {len(articles)} news articles for their sentiment impact on ticker {symbol}.

{articles_block}

For EACH article, output a JSON array with one object per article in order:
[
  {{
    "index": 0,
    "sentiment": "positive" | "neutral" | "negative",
    "score": <float from -5.0 to +5.0>,
    "relevance": <float from 0.0 to 1.0, how directly relevant to {symbol}>,
    "reasoning": "<1 sentence>"
  }},
  ...
]

Rules:
- score: -5 = extremely bearish, 0 = neutral, +5 = extremely bullish for {symbol}
- relevance: 1.0 = directly about {symbol}, 0.0 = unrelated
- If article is not about {symbol}, set relevance < 0.3 and score near 0
- Output ONLY the JSON array, no markdown fences"""

        start_ms = int(time.time() * 1000)
        client = self._get_client()

        for attempt in range(self.settings.llm_max_retries + 1):
            try:
                response = client.messages.create(
                    model=self.settings.llm_model,
                    max_tokens=1024,
                    temperature=0.2,
                    messages=[{"role": "user", "content": prompt}],
                )
                raw = response.content[0].text
                break
            except Exception as e:
                logger.warning("sentiment_llm_failed", attempt=attempt, error=str(e))
                if attempt == self.settings.llm_max_retries:
                    return [self._fallback_sentiment(a, symbol) for a in articles]

        latency_ms = int(time.time() * 1000) - start_ms
        logger.info("sentiment_classified", articles=len(articles), symbol=symbol, latency_ms=latency_ms)

        return self._parse_batch_response(raw, articles, symbol)

    def _parse_batch_response(self, raw: str, articles: list[dict], symbol: str) -> list[dict]:
        """Parse LLM JSON array response."""
        text = raw.strip()
        # Strip markdown fences
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        try:
            results = json.loads(text)
        except json.JSONDecodeError:
            # Try extracting JSON array
            start = text.find("[")
            end = text.rfind("]") + 1
            if start >= 0 and end > start:
                try:
                    results = json.loads(text[start:end])
                except json.JSONDecodeError:
                    logger.error("sentiment_json_parse_failed", raw=text[:200])
                    return [self._fallback_sentiment(a, symbol) for a in articles]
            else:
                logger.error("sentiment_no_json_found", raw=text[:200])
                return [self._fallback_sentiment(a, symbol) for a in articles]

        if not isinstance(results, list):
            return [self._fallback_sentiment(a, symbol) for a in articles]

        # Map results back to articles, handling missing/extra entries
        parsed = []
        for i, article in enumerate(articles):
            if i < len(results):
                r = results[i]
                parsed.append(self._validate_result(r, article, symbol))
            else:
                parsed.append(self._fallback_sentiment(article, symbol))
        return parsed

    def _validate_result(self, result: dict, article: dict, symbol: str) -> dict:
        """Validate and sanitize a single classification result."""
        valid_sentiments = {"positive", "neutral", "negative"}
        sentiment = result.get("sentiment", "neutral")
        if sentiment not in valid_sentiments:
            sentiment = "neutral"

        score = max(-5.0, min(5.0, float(result.get("score", 0.0))))
        relevance = max(0.0, min(1.0, float(result.get("relevance", 0.5))))

        return {
            "title": article.get("title", ""),
            "source": article.get("source", ""),
            "url": article.get("url", ""),
            "published_at": article.get("published_at", ""),
            "symbol": symbol,
            "sentiment": sentiment,
            "score": round(score, 2),
            "relevance": round(relevance, 2),
            "reasoning": result.get("reasoning", ""),
        }

    def _fallback_sentiment(self, article: dict, symbol: str) -> dict:
        """Return neutral sentiment when LLM is unavailable."""
        return {
            "title": article.get("title", ""),
            "source": article.get("source", ""),
            "url": article.get("url", ""),
            "published_at": article.get("published_at", ""),
            "symbol": symbol,
            "sentiment": "neutral",
            "score": 0.0,
            "relevance": 0.5,
            "reasoning": "Fallback: LLM unavailable",
        }
