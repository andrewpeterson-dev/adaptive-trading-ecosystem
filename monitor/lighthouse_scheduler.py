"""
Schedule recurring Lighthouse audits using the existing JobScheduler.
"""

import structlog

from monitor.lighthouse import LighthouseAuditor
from monitor.scheduler import JobScheduler

logger = structlog.get_logger(__name__)

JOB_NAME = "lighthouse_audit"


def setup_lighthouse_schedule(
    scheduler: JobScheduler,
    auditor: LighthouseAuditor,
    settings,
) -> None:
    """Register a recurring Lighthouse audit with *scheduler*.

    The audit runs against ``settings.frontend_url`` every
    ``settings.lighthouse_schedule_hours`` hours.
    """
    url = settings.frontend_url
    interval_seconds = settings.lighthouse_schedule_hours * 3600

    async def _run():
        logger.info("lighthouse_scheduled_run", url=url)
        report = await auditor.run_audit(url)
        if "error" not in report:
            await auditor.save_report(report)
        else:
            logger.warning("lighthouse_scheduled_run_error", error=report["error"])

    scheduler.schedule(JOB_NAME, _run, interval_seconds)
    logger.info(
        "lighthouse_schedule_registered",
        url=url,
        interval_hours=settings.lighthouse_schedule_hours,
    )


def trigger_lighthouse_audit(
    scheduler: JobScheduler,
    auditor: LighthouseAuditor,
    url: str,
) -> str:
    """Queue a one-off Lighthouse audit and return the job name."""
    job_name = f"lighthouse_ondemand_{url}"

    async def _run():
        report = await auditor.run_audit(url)
        if "error" not in report:
            await auditor.save_report(report)

    scheduler.run_once(job_name, _run)
    logger.info("lighthouse_ondemand_triggered", url=url, job=job_name)
    return job_name
