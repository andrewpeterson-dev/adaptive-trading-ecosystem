"""Tests for the autonomous improvement loop and task queue."""

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from autonomous.loop import AutonomousLoop, _is_protected
from autonomous.task_queue import TaskQueue


@pytest.fixture
def tmp_queue(tmp_path):
    """TaskQueue backed by a temporary file."""
    return TaskQueue(path=tmp_path / "test-tasks.json")


@pytest.fixture
def loop(tmp_queue):
    return AutonomousLoop(queue=tmp_queue, dry_run=True)


class TestProtectedPaths:
    def test_exact_match(self):
        assert _is_protected("engine/executor.py") is True

    def test_subpath_match(self):
        assert _is_protected("services/security/auth.py") is True

    def test_unprotected_path(self):
        assert _is_protected("intelligence/ensemble_engine.py") is False

    def test_config_settings(self):
        assert _is_protected("config/settings.py") is True

    def test_normalized_slashes(self):
        assert _is_protected("engine\\executor.py") is True


class TestTaskQueue:
    def test_add_task(self, tmp_queue):
        task = tmp_queue.add_task(
            title="Add unit tests",
            description="Write tests for ensemble engine",
            task_type="test",
            target_files=["tests/test_ensemble.py"],
            priority=3,
        )
        assert task["id"]
        assert task["status"] == "pending"
        assert task["priority"] == 3

    def test_invalid_type_raises(self, tmp_queue):
        with pytest.raises(ValueError, match="Invalid task type"):
            tmp_queue.add_task(
                title="Bad task",
                description="desc",
                task_type="invalid",
                target_files=[],
            )

    def test_invalid_priority_raises(self, tmp_queue):
        with pytest.raises(ValueError, match="Priority"):
            tmp_queue.add_task(
                title="Bad priority",
                description="desc",
                task_type="test",
                target_files=[],
                priority=10,
            )

    def test_get_update_task(self, tmp_queue):
        task = tmp_queue.add_task(
            title="Test task",
            description="desc",
            task_type="refactor",
            target_files=["file.py"],
        )
        updated = tmp_queue.update_task(task["id"], status="in_progress")
        assert updated["status"] == "in_progress"

    def test_get_next_pending_priority(self, tmp_queue):
        tmp_queue.add_task("Low", "desc", "test", [], priority=1)
        tmp_queue.add_task("High", "desc", "test", [], priority=5)
        tmp_queue.add_task("Mid", "desc", "test", [], priority=3)

        highest = tmp_queue.get_next_pending()
        assert highest["title"] == "High"
        assert highest["priority"] == 5

    def test_get_next_pending_none(self, tmp_queue):
        result = tmp_queue.get_next_pending()
        assert result is None

    def test_stats(self, tmp_queue):
        tmp_queue.add_task("T1", "d", "test", [])
        tmp_queue.add_task("T2", "d", "test", [])
        task = tmp_queue.add_task("T3", "d", "test", [])
        tmp_queue.update_task(task["id"], status="completed")

        stats = tmp_queue.get_stats()
        assert stats["total"] == 3
        assert stats["pending"] == 2
        assert stats["completed"] == 1

    def test_load_empty_file(self, tmp_path):
        queue = TaskQueue(path=tmp_path / "nonexistent.json")
        assert queue.load() == []


class TestDryRunMode:
    async def test_dry_run_completes_task(self, loop, tmp_queue):
        tmp_queue.add_task(
            title="Safe refactor",
            description="Refactor intelligence module",
            task_type="refactor",
            target_files=["intelligence/ensemble_engine.py"],
        )
        result = await loop.execute_one()
        assert result is not None
        assert result["status"] == "completed"
        assert result["result"] == "dry-run"

    async def test_dry_run_rejects_protected(self, loop, tmp_queue):
        tmp_queue.add_task(
            title="Modify executor",
            description="Change executor",
            task_type="refactor",
            target_files=["engine/executor.py"],
        )
        result = await loop.execute_one()
        assert result["status"] == "failed"
        assert "protected" in result["result"].lower()


class TestLoopControl:
    async def test_stop_flag(self, loop, tmp_queue):
        tmp_queue.add_task("T1", "d", "test", [])
        tmp_queue.add_task("T2", "d", "test", [])
        tmp_queue.add_task("T3", "d", "test", [])

        loop.stop()
        results = await loop.run_loop(max_tasks=3)
        assert len(results) == 0

    async def test_no_pending_returns_none(self, loop):
        result = await loop.execute_one()
        assert result is None

    async def test_loop_runs_multiple(self, loop, tmp_queue):
        tmp_queue.add_task("T1", "d", "test", [])
        tmp_queue.add_task("T2", "d", "test", [])

        results = await loop.run_loop(max_tasks=5)
        assert len(results) == 2

    def test_is_running_flag(self, loop):
        assert loop.is_running() is False

    def test_dry_run_property(self, loop):
        assert loop.dry_run is True
