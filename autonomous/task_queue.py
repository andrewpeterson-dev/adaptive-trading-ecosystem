"""
Thread-safe task queue backed by a JSON file.
"""

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import structlog

logger = structlog.get_logger(__name__)

TASK_FILE = Path(__file__).parent / "task-queue.json"

VALID_TYPES = {"refactor", "test", "docs", "optimize", "feature"}
VALID_STATUSES = {"pending", "in_progress", "completed", "failed", "skipped"}


class TaskQueue:
    """Manages a persistent task queue stored in task-queue.json."""

    def __init__(self, path: Optional[Path] = None):
        self._path = path or TASK_FILE
        self._lock = threading.Lock()

    def load(self) -> list[dict]:
        """Read all tasks from disk."""
        with self._lock:
            return self._read()

    def save(self, tasks: list[dict]) -> None:
        """Write tasks back to disk."""
        with self._lock:
            self._write(tasks)

    def add_task(
        self,
        title: str,
        description: str,
        task_type: str,
        target_files: list[str],
        priority: int = 3,
    ) -> dict:
        """Create and persist a new task. Returns the created task."""
        if task_type not in VALID_TYPES:
            raise ValueError(f"Invalid task type: {task_type}. Must be one of {VALID_TYPES}")
        if not 1 <= priority <= 5:
            raise ValueError("Priority must be between 1 and 5")

        task = {
            "id": str(uuid.uuid4()),
            "title": title,
            "description": description,
            "type": task_type,
            "target_files": target_files,
            "status": "pending",
            "priority": priority,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "completed_at": None,
            "result": None,
            "branch": None,
        }

        with self._lock:
            tasks = self._read()
            tasks.append(task)
            self._write(tasks)

        logger.info("task_added", task_id=task["id"], title=title, priority=priority)
        return task

    def get_next_pending(self) -> Optional[dict]:
        """Return the highest-priority pending task, or None."""
        with self._lock:
            tasks = self._read()

        pending = [t for t in tasks if t["status"] == "pending"]
        if not pending:
            return None

        # Higher priority number = higher priority
        pending.sort(key=lambda t: t["priority"], reverse=True)
        return pending[0]

    def update_task(self, task_id: str, **updates) -> Optional[dict]:
        """Update fields on a task by ID. Returns the updated task or None."""
        with self._lock:
            tasks = self._read()
            for task in tasks:
                if task["id"] == task_id:
                    for key, value in updates.items():
                        if key in task:
                            task[key] = value
                    self._write(tasks)
                    logger.info("task_updated", task_id=task_id, updates=list(updates.keys()))
                    return task
        logger.warning("task_not_found", task_id=task_id)
        return None

    def get_stats(self) -> dict:
        """Return aggregate stats about the queue."""
        tasks = self.load()
        return {
            "total": len(tasks),
            "pending": sum(1 for t in tasks if t["status"] == "pending"),
            "in_progress": sum(1 for t in tasks if t["status"] == "in_progress"),
            "completed": sum(1 for t in tasks if t["status"] == "completed"),
            "failed": sum(1 for t in tasks if t["status"] == "failed"),
        }

    # -- internal helpers --

    def _read(self) -> list[dict]:
        if not self._path.exists():
            return []
        try:
            return json.loads(self._path.read_text())
        except (json.JSONDecodeError, OSError):
            logger.warning("task_queue_read_error", path=str(self._path))
            return []

    def _write(self, tasks: list[dict]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(tasks, indent=2, default=str))
