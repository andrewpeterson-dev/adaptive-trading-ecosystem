"""
Autonomous improvement loop — picks tasks off the queue and executes them safely.
"""

import asyncio
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import structlog

from autonomous.task_queue import TaskQueue

logger = structlog.get_logger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent

PROTECTED_PATHS: frozenset[str] = frozenset({
    "engine/executor.py",
    "services/security",
    "engine/alpaca_executor.py",
    "engine/webull_client.py",
    "config/settings.py",
    "api/main.py",
})


def _is_protected(filepath: str) -> bool:
    """Check if a file path matches or is under any protected path."""
    normalized = filepath.replace("\\", "/").strip("/")
    for protected in PROTECTED_PATHS:
        if normalized == protected or normalized.startswith(protected + "/"):
            return True
    return False


def _sanitize_branch_name(title: str) -> str:
    """Turn a task title into a safe git branch suffix."""
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug[:40]


async def _run_cmd(*args: str, cwd: "Optional[Path]" = None) -> "tuple[int, str, str]":
    """Run a subprocess command and return (returncode, stdout, stderr)."""
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd or PROJECT_ROOT,
    )
    stdout, stderr = await proc.communicate()
    return proc.returncode, stdout.decode(), stderr.decode()


class AutonomousLoop:
    """Executes queued improvement tasks with safety validation."""

    def __init__(self, queue: TaskQueue, dry_run: bool = True):
        self._queue = queue
        self._dry_run = dry_run
        self._should_stop = False
        self._running = False

    @property
    def dry_run(self) -> bool:
        return self._dry_run

    async def execute_one(self) -> "Optional[dict]":
        """Pick the next pending task, validate safety, and run it."""
        task = self._queue.get_next_pending()
        if task is None:
            logger.info("no_pending_tasks")
            return None

        task_id = task["id"]
        self._queue.update_task(task_id, status="in_progress")
        logger.info("task_started", task_id=task_id, title=task["title"])

        # Safety check: reject protected paths
        blocked = [f for f in task.get("target_files", []) if _is_protected(f)]
        if blocked:
            msg = f"Rejected: target files include protected paths: {blocked}"
            logger.warning("task_rejected_protected", task_id=task_id, blocked=blocked)
            self._queue.update_task(
                task_id,
                status="failed",
                result=msg,
                completed_at=datetime.now(timezone.utc).isoformat(),
            )
            return {**task, "status": "failed", "result": msg}

        try:
            if self._dry_run:
                result = await self._dry_run_task(task)
            else:
                result = await self._real_task(task)

            self._queue.update_task(
                task_id,
                status="completed",
                result=result,
                completed_at=datetime.now(timezone.utc).isoformat(),
            )
            logger.info("task_completed", task_id=task_id, result=result)
            return {**task, "status": "completed", "result": result}

        except Exception as e:
            error_msg = f"{type(e).__name__}: {e}"
            self._queue.update_task(
                task_id,
                status="failed",
                result=error_msg,
                completed_at=datetime.now(timezone.utc).isoformat(),
            )
            logger.error("task_failed", task_id=task_id, error=error_msg)
            return {**task, "status": "failed", "result": error_msg}

    async def _dry_run_task(self, task: dict) -> str:
        """Simulate task without making changes."""
        plan = (
            f"[DRY RUN] Would run '{task['type']}' task: {task['title']}\n"
            f"Target files: {', '.join(task.get('target_files', []))}\n"
            f"Description: {task['description']}"
        )
        logger.info("dry_run_task", task_id=task["id"], plan=plan)
        return "dry-run"

    async def _real_task(self, task: dict) -> str:
        """Branch, generate placeholder plan, validate, commit."""
        task_id = task["id"]
        slug = _sanitize_branch_name(task["title"])
        branch = f"auto/{task_id[:8]}-{slug}"

        # Create branch
        rc, _, err = await _run_cmd("git", "checkout", "-b", branch)
        if rc != 0:
            raise RuntimeError(f"git checkout -b failed: {err.strip()}")

        try:
            # Placeholder: write an implementation plan file
            plan_path = PROJECT_ROOT / f"autonomous/plans/{task_id[:8]}.md"
            plan_path.parent.mkdir(parents=True, exist_ok=True)
            plan_content = (
                f"# Task: {task['title']}\n\n"
                f"**Type:** {task['type']}\n"
                f"**Priority:** {task['priority']}\n"
                f"**Target files:** {', '.join(task.get('target_files', []))}\n\n"
                f"## Description\n{task['description']}\n\n"
                f"## Implementation Plan\n"
                f"_Placeholder — real code generation requires LLM integration._\n"
            )
            plan_path.write_text(plan_content)

            # Validate any target .py files compile
            for filepath in task.get("target_files", []):
                full = PROJECT_ROOT / filepath
                if full.exists() and full.suffix == ".py":
                    rc, _, err = await _run_cmd(
                        "python", "-m", "py_compile", str(full)
                    )
                    if rc != 0:
                        raise RuntimeError(
                            f"py_compile failed for {filepath}: {err.strip()}"
                        )

            # Stage and commit
            await _run_cmd("git", "add", str(plan_path))
            rc, _, err = await _run_cmd(
                "git", "commit", "-m",
                f"auto: {task['type']} — {task['title']}",
            )
            if rc != 0:
                raise RuntimeError(f"git commit failed: {err.strip()}")

            self._queue.update_task(task_id, branch=branch)
            return f"branch:{branch}"

        except Exception:
            # Return to previous branch on failure
            await _run_cmd("git", "checkout", "-")
            raise

    async def run_loop(self, max_tasks: int = 1) -> list[dict]:
        """Run up to max_tasks pending tasks sequentially."""
        self._running = True
        self._should_stop = False
        results = []

        try:
            for _ in range(max_tasks):
                if self._should_stop:
                    logger.info("loop_stopped_by_flag")
                    break
                result = await self.execute_one()
                if result is None:
                    break
                results.append(result)
        finally:
            self._running = False

        return results

    def stop(self) -> None:
        """Signal the loop to stop after the current task."""
        self._should_stop = True

    def is_running(self) -> bool:
        return self._running

    def get_history(self, limit: int = 20) -> list[dict]:
        """Return recent completed/failed tasks."""
        all_tasks = self._queue.load()
        finished = [t for t in all_tasks if t["status"] in ("completed", "failed")]
        finished.sort(
            key=lambda t: t.get("completed_at") or "",
            reverse=True,
        )
        return finished[:limit]
