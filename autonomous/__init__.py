"""
Autonomous self-improvement loop for the trading ecosystem.
Manages a task queue and executes safe, validated code improvements.
"""

from autonomous.task_queue import TaskQueue
from autonomous.loop import AutonomousLoop
from autonomous.seed_tasks import seed_initial_tasks

__all__ = ["TaskQueue", "AutonomousLoop", "seed_initial_tasks"]
