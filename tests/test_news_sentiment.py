"""Tests for the sentiment classifier."""

import json
import os

os.environ.setdefault("ALPACA_API_KEY", "test")
os.environ.setdefault("ALPACA_SECRET_KEY", "test")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")

from unittest.mock import MagicMock, patch

import pytest

from news.sentiment import SentimentClassifier


@pytest.fixture
def classifier():
    with patch("news.sentiment.get_settings") as mock_gs:
        mock_gs.return_value = MagicMock(
            anthropic_api_key="test-key",
            llm_model="claude-sonnet-4-20250514",
            llm_max_retries=1,
        )
        return SentimentClassifier()


@pytest.fixture
def sample_articles():
    return [
        {
            "title": "Apple beats earnings expectations",
            "source": "Bloomberg",
            "published_at": "2024-01-15T10:00:00Z",
            "summary": "Apple reported Q4 earnings above analyst estimates.",
            "url": "https://example.com/1",
        },
        {
            "title": "Tech sector faces headwinds",
            "source": "Reuters",
            "published_at": "2024-01-15T11:00:00Z",
            "summary": "Rising rates create uncertainty for technology companies.",
            "url": "https://example.com/2",
        },
    ]


class TestClassifyBatch:
    def test_successful_classification(self, classifier, sample_articles):
        llm_response = json.dumps([
            {
                "index": 0,
                "sentiment": "positive",
                "score": 3.5,
                "relevance": 0.95,
                "reasoning": "Beat earnings.",
            },
            {
                "index": 1,
                "sentiment": "negative",
                "score": -2.0,
                "relevance": 0.6,
                "reasoning": "Sector headwinds.",
            },
        ])

        mock_message = MagicMock()
        mock_message.content = [MagicMock(text=llm_response)]
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_message

        with patch.object(classifier, "_get_client", return_value=mock_client):
            results = classifier.classify_batch(sample_articles, "AAPL")

        assert len(results) == 2
        assert results[0]["sentiment"] == "positive"
        assert results[0]["score"] == 3.5
        assert results[0]["relevance"] == 0.95
        assert results[1]["sentiment"] == "negative"
        assert results[1]["score"] == -2.0

    def test_empty_list(self, classifier):
        results = classifier.classify_batch([], "AAPL")
        assert results == []


class TestMalformedResponse:
    def test_invalid_json_falls_back(self, classifier, sample_articles):
        mock_message = MagicMock()
        mock_message.content = [MagicMock(text="This is not JSON at all")]
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_message

        with patch.object(classifier, "_get_client", return_value=mock_client):
            results = classifier.classify_batch(sample_articles, "AAPL")

        assert len(results) == 2
        # Fallback returns neutral
        for r in results:
            assert r["sentiment"] == "neutral"
            assert r["score"] == 0.0
            assert "Fallback" in r["reasoning"]

    def test_partial_json_extracted(self, classifier, sample_articles):
        partial = 'Some text before [{"index": 0, "sentiment": "positive", "score": 2.0, "relevance": 0.8, "reasoning": "good"}] after'
        mock_message = MagicMock()
        mock_message.content = [MagicMock(text=partial)]
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_message

        with patch.object(classifier, "_get_client", return_value=mock_client):
            results = classifier.classify_batch(sample_articles, "AAPL")

        # First article gets parsed result, second gets fallback
        assert results[0]["sentiment"] == "positive"
        assert results[1]["sentiment"] == "neutral"  # fallback

    def test_api_failure_returns_fallback(self, classifier, sample_articles):
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("API error")

        with patch.object(classifier, "_get_client", return_value=mock_client):
            results = classifier.classify_batch(sample_articles, "AAPL")

        assert len(results) == 2
        for r in results:
            assert r["sentiment"] == "neutral"
            assert "Fallback" in r["reasoning"]

    def test_markdown_fences_stripped(self, classifier, sample_articles):
        fenced = '```json\n[{"index": 0, "sentiment": "negative", "score": -1.0, "relevance": 0.9, "reasoning": "bad"}]\n```'
        mock_message = MagicMock()
        mock_message.content = [MagicMock(text=fenced)]
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_message

        with patch.object(classifier, "_get_client", return_value=mock_client):
            results = classifier.classify_batch(sample_articles, "AAPL")

        assert results[0]["sentiment"] == "negative"
