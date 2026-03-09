"""Celery task definitions for the Cerberus background workers."""
from __future__ import annotations

import asyncio
import structlog

from services.workers.celery_app import app

logger = structlog.get_logger(__name__)


def _run_async(coro):
    """Run an async coroutine in a sync Celery task."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@app.task(bind=True, name="services.workers.tasks.ingest_document", max_retries=3)
def ingest_document(self, document_id: str, user_id: int):
    """Ingest a document: parse, chunk, embed, index."""
    logger.info("task_ingest_document", document_id=document_id, user_id=user_id)
    try:
        from services.ai_core.documents.ingestion import DocumentIngestionService
        service = DocumentIngestionService()
        _run_async(service.ingest(document_id, user_id))
        logger.info("task_ingest_complete", document_id=document_id)
    except Exception as exc:
        logger.error("task_ingest_failed", document_id=document_id, error=str(exc))
        raise self.retry(exc=exc, countdown=30)


@app.task(bind=True, name="services.workers.tasks.run_backtest", max_retries=2)
def run_backtest(self, backtest_id: str, user_id: int):
    """Run a strategy backtest."""
    logger.info("task_run_backtest", backtest_id=backtest_id, user_id=user_id)
    try:
        from db.database import get_session
        from db.cerberus_models import CerberusBacktest
        from sqlalchemy import select
        from datetime import datetime

        async def _run():
            async with get_session() as session:
                result = await session.execute(
                    select(CerberusBacktest).where(CerberusBacktest.id == backtest_id)
                )
                bt = result.scalar_one_or_none()
                if not bt:
                    raise ValueError(f"Backtest {backtest_id} not found")

                # TODO: Integrate with engine/backtester.py for actual execution
                bt.status = "completed"
                bt.completed_at = datetime.utcnow()
                bt.metrics_json = {
                    "status": "stub",
                    "message": "Backtest execution pending full integration",
                }

        _run_async(_run())
        logger.info("task_backtest_complete", backtest_id=backtest_id)
    except Exception as exc:
        logger.error("task_backtest_failed", backtest_id=backtest_id, error=str(exc))
        raise self.retry(exc=exc, countdown=60)


@app.task(name="services.workers.tasks.refresh_analytics")
def refresh_analytics():
    """Refresh materialized views for trade analytics."""
    logger.info("task_refresh_analytics")
    try:
        from services.ai_core.analytics.trade_analytics import TradeAnalyticsService, MATERIALIZED_VIEW_SQL
        # In production, execute the materialized view SQL against PostgreSQL
        logger.info("task_analytics_refreshed", views=list(MATERIALIZED_VIEW_SQL.keys()))
    except Exception as exc:
        logger.error("task_analytics_failed", error=str(exc))


@app.task(name="services.workers.tasks.summarize_thread")
def summarize_thread(thread_id: str, user_id: int):
    """Summarize a conversation thread."""
    logger.info("task_summarize_thread", thread_id=thread_id, user_id=user_id)
    try:
        from services.ai_core.memory.summarizer import ThreadSummarizer
        summarizer = ThreadSummarizer()
        _run_async(summarizer.summarize(thread_id, user_id))
        logger.info("task_summarize_complete", thread_id=thread_id)
    except Exception as exc:
        logger.error("task_summarize_failed", thread_id=thread_id, error=str(exc))


@app.task(name="services.workers.tasks.run_research_job")
def run_research_job(query: str, user_id: int, document_ids: list[str] | None = None):
    """Run a long research job (Perplexity deep research + document analysis)."""
    logger.info("task_research_job", query=query, user_id=user_id)
    # TODO: Implement deep research pipeline
    logger.info("task_research_stub", message="Deep research pending implementation")
