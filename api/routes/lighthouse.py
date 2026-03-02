"""
Lighthouse audit API endpoints — view reports, trigger audits, browse history.
"""

from typing import Optional

from fastapi import APIRouter

from config.settings import get_settings
from monitor.lighthouse import LighthouseAuditor
from monitor.lighthouse_scheduler import trigger_lighthouse_audit
from monitor.scheduler import JobScheduler

router = APIRouter()

# Shared instances — lazy-initialized
_auditor: Optional[LighthouseAuditor] = None
_scheduler: Optional[JobScheduler] = None


def _get_auditor() -> LighthouseAuditor:
    global _auditor
    if _auditor is None:
        _auditor = LighthouseAuditor()
    return _auditor


def _get_scheduler() -> JobScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = JobScheduler()
    return _scheduler


@router.get("/lighthouse")
async def get_latest_lighthouse():
    """Return the most recent Lighthouse audit report."""
    auditor = _get_auditor()
    report = auditor.get_latest_report()
    if report is None:
        return {"status": "no_report", "message": "No Lighthouse report found. Trigger an audit first."}
    return report


@router.post("/lighthouse/run")
async def trigger_audit():
    """Queue an on-demand Lighthouse audit and return the job name."""
    settings = get_settings()
    auditor = _get_auditor()
    scheduler = _get_scheduler()
    job_name = trigger_lighthouse_audit(scheduler, auditor, settings.frontend_url)
    return {"status": "queued", "job": job_name, "url": settings.frontend_url}


@router.get("/lighthouse/history")
async def get_lighthouse_history(limit: int = 10):
    """Return recent Lighthouse audit history."""
    auditor = _get_auditor()
    history = auditor.get_history(limit=limit)
    return {"count": len(history), "reports": history}
