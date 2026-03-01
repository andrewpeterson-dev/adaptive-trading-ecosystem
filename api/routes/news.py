"""
News sentiment endpoints — fetch news, classify sentiment, generate reports.
"""

from fastapi import APIRouter, HTTPException

import structlog

from news.ingestion import NewsIngestion
from news.sentiment import SentimentClassifier
from news.report import SentimentReportGenerator

logger = structlog.get_logger(__name__)

router = APIRouter()

# Shared instances (lazy init)
_ingestion = NewsIngestion()
_classifier = SentimentClassifier()
_report_gen = SentimentReportGenerator()


@router.get("/sentiment")
async def get_sentiment(symbols: str = "SPY,QQQ,AAPL,TSLA,NVDA"):
    """
    Get news sentiment for given symbols.
    Query param `symbols` is a comma-separated list of tickers.
    """
    symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    if not symbol_list:
        raise HTTPException(status_code=400, detail="No symbols provided")

    articles = _ingestion.fetch_news(symbol_list, limit=10)
    if not articles:
        return {"symbols": symbol_list, "articles": 0, "sentiments": {}}

    # Classify per symbol
    sentiments: dict[str, list[dict]] = {}
    for symbol in symbol_list:
        # Filter articles relevant to this symbol
        symbol_articles = [
            a for a in articles
            if symbol in a.get("symbols", [])
        ]
        if not symbol_articles:
            # Use all articles as fallback
            symbol_articles = articles[:3]

        classified = _classifier.classify_batch(symbol_articles, symbol)
        sentiments[symbol] = classified

    # Generate report
    report = _report_gen.generate(sentiments)
    return report


@router.get("/sentiment/report")
async def get_sentiment_report():
    """Get the latest saved sentiment report."""
    report = _report_gen.load_latest()
    if report is None:
        raise HTTPException(status_code=404, detail="No sentiment report available. Run /sentiment first.")
    return report
