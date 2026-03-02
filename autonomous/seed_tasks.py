"""
Seed the task queue with initial improvement tasks.
"""

import structlog

from autonomous.task_queue import TaskQueue

logger = structlog.get_logger(__name__)


def seed_initial_tasks(queue: TaskQueue) -> list[dict]:
    """Populate the queue with starter tasks if it is empty. Returns created tasks."""
    existing = queue.load()
    if existing:
        logger.info("queue_not_empty", count=len(existing))
        return []

    seeds = [
        {
            "title": "Add unit tests for news/sentiment.py",
            "description": (
                "Write pytest unit tests covering the public functions in news/sentiment.py. "
                "Include tests for score normalization, empty-input handling, and error cases."
            ),
            "task_type": "test",
            "target_files": ["news/sentiment.py", "tests/test_sentiment.py"],
            "priority": 4,
        },
        {
            "title": "Add docstrings to risk/analytics.py public methods",
            "description": (
                "Add Google-style docstrings to all public methods in risk/analytics.py. "
                "Include parameter descriptions, return types, and brief usage examples."
            ),
            "task_type": "docs",
            "target_files": ["risk/analytics.py"],
            "priority": 2,
        },
        {
            "title": "Optimize news/ingestion.py caching TTL logic",
            "description": (
                "Review and optimize the TTL-based caching logic in news/ingestion.py. "
                "Ensure expired entries are pruned efficiently and cache size is bounded."
            ),
            "task_type": "optimize",
            "target_files": ["news/ingestion.py"],
            "priority": 3,
        },
    ]

    created = []
    for s in seeds:
        task = queue.add_task(**s)
        created.append(task)

    logger.info("seed_tasks_created", count=len(created))
    return created
