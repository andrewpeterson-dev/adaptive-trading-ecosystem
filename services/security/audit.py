"""
Persistent trade audit logger — append-only JSONL file for full trade history.
Thread-safe writes ensure no data loss under concurrent execution.
"""

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

import structlog

from config.settings import get_settings

logger = structlog.get_logger(__name__)


class AuditLogger:
    """
    Append-only JSONL trade audit log.

    Each line is a self-contained JSON object with trade details.
    Thread-safe for concurrent writes from multiple execution threads.
    """

    def __init__(self, log_path: Optional[str] = None):
        settings = get_settings()
        self._path = Path(log_path or settings.audit_log_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def log_trade(
        self,
        symbol: str,
        direction: str,
        quantity: float,
        model: str,
        signal_strength: float,
        status: str,
        mode: str,
        order_id: str = "",
        detail: str = "",
    ) -> None:
        """Append a trade record to the audit log."""
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "symbol": symbol,
            "direction": direction,
            "quantity": quantity,
            "model": model,
            "signal_strength": signal_strength,
            "status": status,
            "mode": mode,
            "order_id": order_id,
            "detail": detail,
        }
        self._write(entry)

    def get_log(self, limit: int = 100) -> list[dict]:
        """Read the most recent entries from the audit log."""
        if not self._path.exists():
            return []

        entries = []
        with self._lock:
            with open(self._path, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

        return entries[-limit:]

    def _write(self, entry: dict) -> None:
        """Thread-safe append to the JSONL file."""
        line = json.dumps(entry, default=str) + "\n"
        with self._lock:
            with open(self._path, "a") as f:
                f.write(line)
        logger.debug("audit_logged", symbol=entry.get("symbol"), status=entry.get("status"))
