"""
API routes for the autonomous self-improvement loop.
"""

from typing import Optional

import structlog
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from autonomous.task_queue import TaskQueue, VALID_TYPES
from autonomous.loop import AutonomousLoop
from autonomous.seed_tasks import seed_initial_tasks
from config.settings import get_settings
from services.security.access_control import require_admin

logger = structlog.get_logger(__name__)

router = APIRouter()

# Shared instances
_queue: Optional[TaskQueue] = None
_loop: Optional[AutonomousLoop] = None


def _get_queue() -> TaskQueue:
    global _queue
    if _queue is None:
        _queue = TaskQueue()
    return _queue


def _get_loop() -> AutonomousLoop:
    global _loop
    settings = get_settings()
    queue = _get_queue()
    if _loop is None:
        _loop = AutonomousLoop(queue=queue, dry_run=settings.auto_loop_dry_run)
    return _loop


class AddTaskRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1)
    type: str = Field(..., description="Task type: refactor, test, docs, optimize, feature")
    target_files: list[str] = Field(default_factory=list)
    priority: int = Field(default=3, ge=1, le=5)


@router.get("/auto-loop/status")
async def get_status(request: Request):
    """Get current loop status and queue stats."""
    await require_admin(request)
    settings = get_settings()
    loop = _get_loop()
    queue = _get_queue()
    return {
        "enabled": settings.auto_loop_enabled,
        "running": loop.is_running(),
        "dry_run": loop.dry_run,
        "stats": queue.get_stats(),
    }


@router.get("/auto-loop/queue")
async def get_queue(request: Request):
    """List all tasks in the queue."""
    await require_admin(request)
    queue = _get_queue()
    return queue.load()


@router.post("/auto-loop/queue")
async def add_task(body: AddTaskRequest, request: Request):
    """Add a new task to the queue."""
    await require_admin(request)
    if body.type not in VALID_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid type. Must be one of: {VALID_TYPES}")

    queue = _get_queue()
    task = queue.add_task(
        title=body.title,
        description=body.description,
        task_type=body.type,
        target_files=body.target_files,
        priority=body.priority,
    )
    return task


@router.post("/auto-loop/run")
async def run_loop(
    request: Request,
    max_tasks: int = Query(default=1, ge=1, le=10),
    dry_run: bool = Query(default=True),
):
    """Trigger execution of pending tasks."""
    await require_admin(request)
    settings = get_settings()
    if not settings.auto_loop_enabled:
        raise HTTPException(status_code=403, detail="Autonomous loop is disabled in settings")

    queue = _get_queue()
    loop = AutonomousLoop(queue=queue, dry_run=dry_run)

    if loop.is_running():
        raise HTTPException(status_code=409, detail="Loop is already running")

    results = await loop.run_loop(max_tasks=max_tasks)
    return {"executed": len(results), "results": results}


@router.get("/auto-loop/history")
async def get_history(request: Request, limit: int = Query(default=20, ge=1, le=100)):
    """Get recent completed/failed tasks."""
    await require_admin(request)
    loop = _get_loop()
    return loop.get_history(limit=limit)


@router.post("/auto-loop/seed")
async def seed_tasks(request: Request):
    """Seed the queue with initial improvement tasks (only if empty)."""
    await require_admin(request)
    queue = _get_queue()
    created = seed_initial_tasks(queue)
    return {"seeded": len(created), "tasks": created}
