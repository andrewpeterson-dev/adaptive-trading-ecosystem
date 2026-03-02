"""
Structured sentiment report generation.
Aggregates per-symbol sentiments into a comprehensive market report.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)

REPORT_PATH = Path(__file__).parent / "sentiment-report.json"


class SentimentReportGenerator:
    """Generate structured sentiment reports from classified articles."""

    def generate(self, sentiments: dict[str, list[dict]]) -> dict:
        """
        Generate full sentiment report.

        Args:
            sentiments: {symbol: [list of classification dicts]}

        Returns:
            Structured report dict.
        """
        total_articles = sum(len(v) for v in sentiments.values())
        symbol_summaries = {}

        for symbol, classifications in sentiments.items():
            if not classifications:
                continue
            scores = [c["score"] for c in classifications]
            relevances = [c["relevance"] for c in classifications]
            avg_score = sum(scores) / len(scores)
            avg_relevance = sum(relevances) / len(relevances)

            if avg_score > 1.0:
                sentiment_label = "positive"
            elif avg_score < -1.0:
                sentiment_label = "negative"
            else:
                sentiment_label = "neutral"

            symbol_summaries[symbol] = {
                "score": round(avg_score, 2),
                "articles": len(classifications),
                "sentiment": sentiment_label,
                "relevance": round(avg_relevance, 2),
            }

        # Determine overall market mood from aggregate scores
        all_scores = [s["score"] for s in symbol_summaries.values()]
        if all_scores:
            avg_market = sum(all_scores) / len(all_scores)
            if avg_market > 2.0:
                market_mood = "bullish"
            elif avg_market > 0.5:
                market_mood = "cautiously_optimistic"
            elif avg_market > -0.5:
                market_mood = "mixed"
            elif avg_market > -2.0:
                market_mood = "cautiously_pessimistic"
            else:
                market_mood = "bearish"
        else:
            market_mood = "no_data"

        # Top positive and negative articles across all symbols
        all_classifications = []
        for classifications in sentiments.values():
            all_classifications.extend(classifications)

        top_positive = sorted(all_classifications, key=lambda x: x["score"], reverse=True)[:5]
        top_negative = sorted(all_classifications, key=lambda x: x["score"])[:5]
        # Only include actually negative articles
        top_negative = [a for a in top_negative if a["score"] < 0]

        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "articles_analyzed": total_articles,
            "sentiments": symbol_summaries,
            "market_mood": market_mood,
            "top_positive": [
                {"title": a["title"], "symbol": a["symbol"], "score": a["score"], "source": a["source"]}
                for a in top_positive
            ],
            "top_negative": [
                {"title": a["title"], "symbol": a["symbol"], "score": a["score"], "source": a["source"]}
                for a in top_negative
            ],
        }

        # Write to disk
        self._save(report)

        logger.info(
            "sentiment_report_generated",
            symbols=len(symbol_summaries),
            articles=total_articles,
            mood=market_mood,
        )
        return report

    def load_latest(self) -> "dict | None":
        """Load the most recently saved report from disk."""
        if REPORT_PATH.exists():
            try:
                return json.loads(REPORT_PATH.read_text())
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("report_load_failed", error=str(e))
        return None

    def _save(self, report: dict):
        """Persist report to JSON file."""
        try:
            REPORT_PATH.write_text(json.dumps(report, indent=2))
            logger.debug("report_saved", path=str(REPORT_PATH))
        except OSError as e:
            logger.error("report_save_failed", error=str(e))
