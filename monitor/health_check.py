"""
System health monitoring.
Checks API, database, Redis, broker, disk, and memory status.
"""

import shutil
import time
from typing import Optional

import httpx
import psutil
import structlog

from config.settings import get_settings

logger = structlog.get_logger(__name__)

_start_time = time.monotonic()


class HealthChecker:
    """System health monitoring."""

    def __init__(self, webhook_url: str = ""):
        self.settings = get_settings()
        self._webhook_url = webhook_url or self.settings.webhook_url

    async def check_all(self) -> dict:
        """Run all health checks, return status report."""
        checks = {}

        checks["api"] = self._check_api()
        checks["database"] = await self._check_database()
        checks["redis"] = await self._check_redis()
        checks["broker"] = await self._check_broker()
        checks["disk"] = self._check_disk()
        checks["memory"] = self._check_memory()

        # Derive overall status
        # Critical services: database + Redis — app cannot function without these
        # Optional services: broker — degraded but operational without credentials
        critical = {k: checks[k] for k in ("database", "redis")}
        optional = {k: checks[k] for k in ("broker",)}

        critical_statuses = [c["status"] for c in critical.values()]
        all_statuses = [c["status"] for c in checks.values()]

        if any(s == "down" for s in critical_statuses):
            overall = "unhealthy"
        elif all(s in ("up", "ok") for s in all_statuses):
            overall = "healthy"
        else:
            overall = "degraded"

        uptime = time.monotonic() - _start_time

        result = {
            "status": overall,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "checks": checks,
            "uptime_seconds": round(uptime, 1),
        }

        if overall == "unhealthy":
            failed = [k for k, v in critical.items() if v["status"] == "down"]
            for name in failed:
                await self.notify_failure(name, checks[name].get("error", "unknown"))

        return result

    def _check_api(self) -> dict:
        """API is alive if we're running this code."""
        return {"status": "up", "latency_ms": 0}

    async def _check_database(self) -> dict:
        """Check PostgreSQL/SQLite connectivity."""
        start = time.monotonic()
        try:
            from sqlalchemy import text
            from db.database import get_session

            async with get_session() as session:
                await session.execute(text("SELECT 1"))

            latency = round((time.monotonic() - start) * 1000, 1)
            return {"status": "up", "latency_ms": latency}
        except Exception as e:
            return {"status": "down", "error": str(e)}

    async def _check_redis(self) -> dict:
        """Check Redis connectivity."""
        start = time.monotonic()
        try:
            import redis.asyncio as aioredis

            r = aioredis.from_url(self.settings.redis_url, socket_timeout=2)
            await r.ping()
            await r.aclose()

            latency = round((time.monotonic() - start) * 1000, 1)
            return {"status": "up", "latency_ms": latency}
        except Exception as e:
            return {"status": "down", "error": str(e)}

    async def _check_broker(self) -> dict:
        """Check broker API connectivity (async to avoid blocking event loop)."""
        mode = self.settings.trading_mode.value
        if not self.settings.alpaca_api_key:
            return {"status": "down", "error": "no API key configured", "mode": mode}

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    f"{self.settings.alpaca_base_url}/v2/account",
                    headers={
                        "APCA-API-KEY-ID": self.settings.alpaca_api_key,
                        "APCA-API-SECRET-KEY": self.settings.alpaca_secret_key,
                    },
                )
            if resp.status_code == 200:
                return {"status": "up", "mode": mode}
            return {"status": "down", "error": f"HTTP {resp.status_code}", "mode": mode}
        except Exception as e:
            return {"status": "down", "error": str(e), "mode": mode}

    def _check_disk(self) -> dict:
        """Check available disk space."""
        usage = shutil.disk_usage("/")
        free_gb = round(usage.free / (1024 ** 3), 1)
        if free_gb < 1.0:
            return {"status": "critical", "free_gb": free_gb}
        return {"status": "ok", "free_gb": free_gb}

    def _check_memory(self) -> dict:
        """Check system memory usage."""
        mem = psutil.virtual_memory()
        used_pct = round(mem.percent, 1)
        if used_pct > 95:
            return {"status": "critical", "used_pct": used_pct}
        if used_pct > 85:
            return {"status": "warning", "used_pct": used_pct}
        return {"status": "ok", "used_pct": used_pct}

    async def notify_failure(self, check_name: str, error: str):
        """Send webhook notification on failure."""
        if not self._webhook_url:
            logger.warning("health_check_failed_no_webhook", check=check_name, error=error)
            return

        payload = {
            "event": "health_check_failure",
            "check": check_name,
            "error": error,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

        try:
            async with httpx.AsyncClient() as client:
                await client.post(self._webhook_url, json=payload, timeout=5)
            logger.info("health_failure_notified", check=check_name)
        except Exception as e:
            logger.error("webhook_send_failed", error=str(e))
