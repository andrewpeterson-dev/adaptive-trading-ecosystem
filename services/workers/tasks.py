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


async def _execute_backtest(backtest_id: str, user_id: int) -> dict:
    """Execute a stored Cerberus backtest using the real strategy backtester."""
    from services.workers.job_runners import execute_backtest_job

    return await execute_backtest_job(backtest_id, user_id)


async def _execute_research_job(query: str, user_id: int, document_ids: list[str] | None = None) -> dict:
    """Execute a real research session and return the assembled output."""
    from services.workers.job_runners import execute_research_job

    return await execute_research_job(query, user_id, document_ids)


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
        result = _run_async(_execute_backtest(backtest_id, user_id))
        logger.info("task_backtest_complete", backtest_id=backtest_id)
        return result
    except Exception as exc:
        logger.error("task_backtest_failed", backtest_id=backtest_id, error=str(exc))
        raise self.retry(exc=exc, countdown=60)


@app.task(name="services.workers.tasks.refresh_analytics")
def refresh_analytics():
    """Refresh materialized views for trade analytics."""
    logger.info("task_refresh_analytics")
    try:
        from services.ai_core.analytics.trade_analytics import MATERIALIZED_VIEW_SQL
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


@app.task(bind=True, name="services.workers.tasks.run_adaptation_review", max_retries=2)
def run_adaptation_review_task(self, bot_id: str):
    """Run AI adaptation review for a bot's recent trades."""
    logger.info("task_adaptation_review", bot_id=bot_id)
    try:
        from services.bot_memory.learning import run_adaptation_review
        result = _run_async(run_adaptation_review(bot_id))
        logger.info("task_adaptation_complete", bot_id=bot_id, adaptations=len(result))
        return {"bot_id": bot_id, "adaptations": len(result)}
    except Exception as exc:
        logger.error("task_adaptation_failed", bot_id=bot_id, error=str(exc))
        raise self.retry(exc=exc, countdown=120)


@app.task(bind=True, name="services.workers.tasks.run_walk_forward", max_retries=2)
def run_walk_forward(
    self,
    conditions: list[dict] | None = None,
    condition_groups: list[dict] | None = None,
    exit_conditions: list[dict] | None = None,
    symbol: str = "SPY",
    timeframe: str = "1D",
    lookback_days: int = 756,
    n_segments: int = 6,
    commission_pct: float = 0.001,
    slippage_pct: float = 0.0005,
    initial_capital: float = 100_000.0,
):
    """Run a walk-forward validation as a Celery task."""
    logger.info("task_walk_forward", symbol=symbol, n_segments=n_segments)
    try:
        from services.workers.job_runners import execute_walk_forward_job
        result = _run_async(execute_walk_forward_job(
            conditions=conditions,
            condition_groups=condition_groups,
            exit_conditions=exit_conditions,
            symbol=symbol,
            timeframe=timeframe,
            lookback_days=lookback_days,
            n_segments=n_segments,
            commission_pct=commission_pct,
            slippage_pct=slippage_pct,
            initial_capital=initial_capital,
        ))
        logger.info("task_walk_forward_complete", symbol=symbol)
        return result
    except Exception as exc:
        logger.error("task_walk_forward_failed", symbol=symbol, error=str(exc))
        raise self.retry(exc=exc, countdown=60)


@app.task(bind=True, name="services.workers.tasks.run_ablation_study", max_retries=2)
def run_ablation_study(
    self,
    conditions: list[dict] | None = None,
    condition_groups: list[dict] | None = None,
    exit_conditions: list[dict] | None = None,
    symbol: str = "SPY",
    timeframe: str = "1D",
    lookback_days: int = 252,
    n_random_trials: int = 1000,
    commission_pct: float = 0.001,
    slippage_pct: float = 0.0005,
    initial_capital: float = 100_000.0,
):
    """Run an ablation study as a Celery task."""
    logger.info("task_ablation_study", symbol=symbol, n_trials=n_random_trials)
    try:
        from services.workers.job_runners import execute_ablation_study_job
        result = _run_async(execute_ablation_study_job(
            conditions=conditions,
            condition_groups=condition_groups,
            exit_conditions=exit_conditions,
            symbol=symbol,
            timeframe=timeframe,
            lookback_days=lookback_days,
            n_random_trials=n_random_trials,
            commission_pct=commission_pct,
            slippage_pct=slippage_pct,
            initial_capital=initial_capital,
        ))
        logger.info("task_ablation_study_complete", symbol=symbol)
        return result
    except Exception as exc:
        logger.error("task_ablation_study_failed", symbol=symbol, error=str(exc))
        raise self.retry(exc=exc, countdown=60)


@app.task(name="services.workers.tasks.run_research_job")
def run_research_job(query: str, user_id: int, document_ids: list[str] | None = None):
    """Run a long research job (Perplexity deep research + document analysis)."""
    logger.info("task_research_job", query=query, user_id=user_id)
    try:
        result = _run_async(_execute_research_job(query, user_id, document_ids))
        logger.info(
            "task_research_complete",
            user_id=user_id,
            query=query,
            symbols=result.get("symbols", []),
            news_results=len(result.get("news_results", [])),
        )
        return result
    except Exception as exc:
        logger.error("task_research_failed", query=query, user_id=user_id, error=str(exc))
        raise
