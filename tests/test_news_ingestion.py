"""Tests for news ingestion with mocked HTTP calls."""

import os
import time

os.environ.setdefault("ALPACA_API_KEY", "test")
os.environ.setdefault("ALPACA_SECRET_KEY", "test")

from unittest.mock import MagicMock, patch

import pytest

from news.ingestion import NewsIngestion


@pytest.fixture
def ingestion():
    with patch("news.ingestion.get_settings") as mock_gs:
        mock_gs.return_value = MagicMock(
            alphavantage_api_key="test-av-key",
            finnhub_api_key="test-fh-key",
        )
        with patch("news.ingestion.TickerValidator") as mock_tv:
            mock_tv.return_value.is_valid = MagicMock(return_value=True)
            ing = NewsIngestion()
    return ing


@pytest.fixture
def av_response():
    return {
        "feed": [
            {
                "title": "Apple earnings beat",
                "url": "https://example.com/1",
                "source": "Bloomberg",
                "time_published": "20240115T100000",
                "summary": "Apple beat earnings",
                "ticker_sentiment": [{"ticker": "AAPL", "relevance_score": "0.9"}],
            },
            {
                "title": "Tech rally continues",
                "url": "https://example.com/2",
                "source": "Reuters",
                "time_published": "20240115T110000",
                "summary": "Tech stocks rising",
                "ticker_sentiment": [{"ticker": "AAPL", "relevance_score": "0.7"}],
            },
        ]
    }


class TestFetchArticles:
    def test_fetch_alphavantage_success(self, ingestion, av_response):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = av_response
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.get", return_value=mock_resp):
            articles = ingestion.fetch_news(["AAPL"], limit=10)

        assert len(articles) == 2
        assert articles[0]["title"] == "Apple earnings beat"
        assert articles[0]["source"] == "Bloomberg"
        assert "AAPL" in articles[0]["symbols"]

    def test_fetch_fallback_to_finnhub(self, ingestion):
        av_resp = MagicMock()
        av_resp.status_code = 200
        av_resp.json.return_value = {}  # No "feed" key
        av_resp.raise_for_status = MagicMock()

        fh_resp = MagicMock()
        fh_resp.status_code = 200
        fh_resp.json.return_value = [
            {
                "headline": "Finnhub article",
                "url": "https://example.com/fh",
                "source": "Finnhub",
                "datetime": 1705312800,
                "summary": "From Finnhub",
            }
        ]
        fh_resp.raise_for_status = MagicMock()

        with patch("httpx.get", side_effect=[av_resp, fh_resp]):
            articles = ingestion.fetch_news(["AAPL"], limit=10)

        assert len(articles) >= 1
        assert articles[0]["title"] == "Finnhub article"

    def test_fetch_empty_symbols(self, ingestion):
        ingestion._validator.is_valid = MagicMock(return_value=False)
        articles = ingestion.fetch_news(["INVALID123"], limit=10)
        assert articles == []


class TestRateLimiting:
    def test_rate_limit_enforced(self, ingestion):
        ingestion._min_request_interval = 0.1
        ingestion._last_request_time = time.time()
        start = time.time()
        ingestion._rate_limit()
        elapsed = time.time() - start
        # Should have waited at least some time
        assert elapsed >= 0.05  # Allow some tolerance


class TestCacheTTL:
    def test_cache_hit(self, ingestion, av_response):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = av_response
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.get", return_value=mock_resp) as mock_get:
            articles1 = ingestion.fetch_news(["AAPL"], limit=10)
            articles2 = ingestion.fetch_news(["AAPL"], limit=10)

        # Second call should hit cache, so httpx.get called only for first fetch
        # (AV is called once, not twice)
        assert len(articles1) == len(articles2)
        # httpx.get should be called once (for alphavantage)
        assert mock_get.call_count == 1

    def test_cache_expires(self, ingestion, av_response):
        ingestion._cache_ttl = 0  # Expire immediately

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = av_response
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.get", return_value=mock_resp) as mock_get:
            ingestion.fetch_news(["AAPL"], limit=10)
            time.sleep(0.01)
            ingestion.fetch_news(["AAPL"], limit=10)

        # Both calls should hit API since TTL is 0
        assert mock_get.call_count == 2
