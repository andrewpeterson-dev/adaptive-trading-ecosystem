"""Celery application configuration for background workers."""
from __future__ import annotations

from celery import Celery

from config.settings import get_settings

settings = get_settings()

app = Celery(
    "cerberus_workers",
    broker=settings.effective_celery_broker_url,
    backend=settings.effective_celery_broker_url,
)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "services.workers.tasks.ingest_document": {"queue": "documents"},
        "services.workers.tasks.run_backtest": {"queue": "backtests"},
        "services.workers.tasks.refresh_analytics": {"queue": "default"},
        "services.workers.tasks.summarize_thread": {"queue": "default"},
        "services.workers.tasks.run_research_job": {"queue": "default"},
    },
    task_default_queue="default",
)

app.autodiscover_tasks(["services.workers"])
