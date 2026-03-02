"""
Lighthouse audit automation — runs Google Lighthouse via npx and tracks results.
"""

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import structlog

logger = structlog.get_logger(__name__)

DEFAULT_CATEGORIES = ["performance", "accessibility", "best-practices", "seo"]
DEFAULT_REPORT_PATH = "monitor/lighthouse-report.json"
DEFAULT_HISTORY_PATH = "monitor/lighthouse-history.jsonl"
AUDIT_TIMEOUT = 120


class LighthouseAuditor:
    """Runs Lighthouse audits via npx and persists results."""

    def __init__(
        self,
        report_path: str = DEFAULT_REPORT_PATH,
        history_path: str = DEFAULT_HISTORY_PATH,
    ):
        self.report_path = Path(report_path)
        self.history_path = Path(history_path)

    async def run_audit(
        self,
        url: str,
        categories: Optional[list[str]] = None,
    ) -> dict:
        """Run a Lighthouse audit against *url* and return parsed results."""
        cats = categories or DEFAULT_CATEGORIES
        cats_arg = ",".join(cats)

        cmd = [
            "npx", "lighthouse", url,
            "--output=json",
            "--chrome-flags=--headless --no-sandbox",
            f"--only-categories={cats_arg}",
        ]

        logger.info("lighthouse_audit_start", url=url, categories=cats)

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=AUDIT_TIMEOUT
            )
        except FileNotFoundError:
            logger.error("lighthouse_not_installed")
            return {
                "error": "lighthouse CLI not found — install with: npm install -g lighthouse",
                "url": url,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except asyncio.TimeoutError:
            logger.error("lighthouse_timeout", url=url, timeout=AUDIT_TIMEOUT)
            proc.kill()
            return {
                "error": f"Lighthouse audit timed out after {AUDIT_TIMEOUT}s",
                "url": url,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        if proc.returncode != 0:
            err_msg = stderr.decode(errors="replace").strip()
            logger.error("lighthouse_failed", returncode=proc.returncode, stderr=err_msg)
            return {
                "error": f"Lighthouse exited with code {proc.returncode}: {err_msg}",
                "url": url,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        try:
            raw = json.loads(stdout)
        except json.JSONDecodeError as exc:
            logger.error("lighthouse_bad_json", error=str(exc))
            return {
                "error": f"Failed to parse Lighthouse JSON output: {exc}",
                "url": url,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        report = self._parse_report(url, raw)
        logger.info("lighthouse_audit_complete", url=url, scores=report["scores"])
        return report

    async def save_report(
        self,
        report: dict,
        path: Optional[str] = None,
    ) -> None:
        """Persist *report* as the latest JSON file and append to history JSONL."""
        dest = Path(path) if path else self.report_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(report, indent=2))
        logger.info("lighthouse_report_saved", path=str(dest))

        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        with self.history_path.open("a") as fh:
            fh.write(json.dumps(report) + "\n")
        logger.debug("lighthouse_history_appended", path=str(self.history_path))

    def get_latest_report(self) -> Optional[dict]:
        """Return the latest saved report, or None if no report exists."""
        if not self.report_path.exists():
            return None
        try:
            return json.loads(self.report_path.read_text())
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("lighthouse_read_error", error=str(exc))
            return None

    def get_history(self, limit: int = 10) -> list[dict]:
        """Return the last *limit* audit entries from the history JSONL."""
        if not self.history_path.exists():
            return []
        lines: list[str] = []
        try:
            with self.history_path.open() as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        lines.append(line)
        except OSError as exc:
            logger.warning("lighthouse_history_read_error", error=str(exc))
            return []

        entries: list[dict] = []
        for line in lines[-limit:]:
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return entries

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_report(url: str, raw: dict) -> dict:
        """Extract scores and top failing audits from raw Lighthouse JSON."""
        categories = raw.get("categories", {})
        scores: dict[str, float] = {}
        for key, cat in categories.items():
            score_val = cat.get("score")
            scores[key] = round(score_val * 100, 1) if score_val is not None else 0.0

        audits = raw.get("audits", {})
        failing: list[dict] = []
        for audit_id, audit in audits.items():
            score = audit.get("score")
            if score is not None and score < 1:
                failing.append({
                    "id": audit_id,
                    "title": audit.get("title", ""),
                    "description": audit.get("description", ""),
                    "score": score,
                })
        failing.sort(key=lambda a: a["score"])
        top_failing = failing[:5]

        return {
            "url": url,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "scores": scores,
            "audits_summary": top_failing,
            "raw_score_details": {k: {"score": v} for k, v in scores.items()},
        }
