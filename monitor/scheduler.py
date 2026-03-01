"""
Lightweight background job scheduler using asyncio.
No external dependencies — runs recurring and one-off jobs with error recovery.
"""

import asyncio
import time
import traceback
from typing import Callable, Optional

import structlog

logger = structlog.get_logger(__name__)


class JobScheduler:
    """Background job scheduler with error recovery."""

    def __init__(self):
        self._jobs: dict[str, dict] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._history: list[dict] = []
        self._max_history = 100

    def schedule(self, name: str, func: Callable, interval_seconds: int):
        """Schedule a recurring async job."""
        if name in self._jobs:
            logger.warning("job_already_scheduled", name=name)
            return

        self._jobs[name] = {
            "name": name,
            "type": "recurring",
            "interval": interval_seconds,
            "status": "scheduled",
            "runs": 0,
            "failures": 0,
            "last_run": None,
            "last_error": None,
        }

        task = asyncio.create_task(self._run_recurring(name, func, interval_seconds))
        self._tasks[name] = task
        logger.info("job_scheduled", name=name, interval=interval_seconds)

    def run_once(self, name: str, func: Callable):
        """Run a one-off async job."""
        self._jobs[name] = {
            "name": name,
            "type": "one_off",
            "interval": None,
            "status": "scheduled",
            "runs": 0,
            "failures": 0,
            "last_run": None,
            "last_error": None,
        }

        task = asyncio.create_task(self._run_once(name, func))
        self._tasks[name] = task
        logger.info("job_queued", name=name, type="one_off")

    async def _run_recurring(self, name: str, func: Callable, interval: int):
        """Execute a recurring job on an interval."""
        while True:
            await self._execute_job(name, func)
            await asyncio.sleep(interval)

    async def _run_once(self, name: str, func: Callable):
        """Execute a one-off job."""
        await self._execute_job(name, func)
        self._jobs[name]["status"] = "completed"

    async def _execute_job(self, name: str, func: Callable):
        """Execute a job with error handling."""
        job = self._jobs[name]
        job["status"] = "running"
        start = time.monotonic()

        try:
            if asyncio.iscoroutinefunction(func):
                await func()
            else:
                func()

            elapsed = round((time.monotonic() - start) * 1000)
            job["runs"] += 1
            job["status"] = "idle" if job["type"] == "recurring" else "completed"
            job["last_run"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            job["last_error"] = None

            self._record_history(name, "success", elapsed)
            logger.debug("job_executed", name=name, elapsed_ms=elapsed)

        except Exception as e:
            elapsed = round((time.monotonic() - start) * 1000)
            job["failures"] += 1
            job["status"] = "error"
            job["last_error"] = str(e)
            job["last_run"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

            self._record_history(name, "failure", elapsed, str(e))
            logger.error(
                "job_failed",
                name=name,
                error=str(e),
                traceback=traceback.format_exc(),
            )

    def _record_history(
        self,
        name: str,
        result: str,
        elapsed_ms: int,
        error: Optional[str] = None,
    ):
        """Record job execution in history ring buffer."""
        entry = {
            "name": name,
            "result": result,
            "elapsed_ms": elapsed_ms,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        if error:
            entry["error"] = error

        self._history.append(entry)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

    def cancel(self, name: str):
        """Cancel a scheduled job."""
        if name in self._tasks:
            self._tasks[name].cancel()
            del self._tasks[name]
        if name in self._jobs:
            self._jobs[name]["status"] = "cancelled"
        logger.info("job_cancelled", name=name)

    def cancel_all(self):
        """Cancel all scheduled jobs."""
        for name in list(self._tasks.keys()):
            self.cancel(name)

    def get_status(self) -> dict:
        """Get all job statuses."""
        return {
            "jobs": {name: {k: v for k, v in job.items()} for name, job in self._jobs.items()},
            "recent_history": self._history[-10:],
            "total_jobs": len(self._jobs),
            "active_tasks": len(self._tasks),
        }
