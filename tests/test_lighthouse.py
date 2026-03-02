"""Tests for Lighthouse audit automation."""

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from monitor.lighthouse import LighthouseAuditor


@pytest.fixture
def auditor(tmp_path):
    return LighthouseAuditor(
        report_path=str(tmp_path / "report.json"),
        history_path=str(tmp_path / "history.jsonl"),
    )


@pytest.fixture
def lighthouse_raw_output():
    return {
        "categories": {
            "performance": {"score": 0.92},
            "accessibility": {"score": 0.85},
            "best-practices": {"score": 0.95},
            "seo": {"score": 1.0},
        },
        "audits": {
            "first-contentful-paint": {
                "title": "First Contentful Paint",
                "description": "FCP measures...",
                "score": 0.8,
            },
            "speed-index": {
                "title": "Speed Index",
                "description": "Speed Index shows...",
                "score": 0.6,
            },
            "interactive": {
                "title": "Time to Interactive",
                "description": "TTI...",
                "score": 1.0,
            },
        },
    }


class TestRunAudit:
    async def test_successful_audit(self, auditor, lighthouse_raw_output):
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(
            return_value=(json.dumps(lighthouse_raw_output).encode(), b"")
        )
        mock_proc.returncode = 0

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            with patch("asyncio.wait_for", new_callable=lambda: AsyncMock) as mock_wait:
                mock_wait.return_value = (json.dumps(lighthouse_raw_output).encode(), b"")
                mock_proc.communicate = mock_wait
                result = await auditor.run_audit("http://localhost:3000")

        assert "scores" in result
        assert result["scores"]["performance"] == 92.0
        assert result["scores"]["seo"] == 100.0
        assert result["url"] == "http://localhost:3000"

    async def test_lighthouse_not_installed(self, auditor):
        with patch(
            "asyncio.create_subprocess_exec",
            side_effect=FileNotFoundError("npx not found"),
        ):
            result = await auditor.run_audit("http://localhost:3000")

        assert "error" in result
        assert "not found" in result["error"].lower()

    async def test_lighthouse_timeout(self, auditor):
        mock_proc = AsyncMock()
        mock_proc.kill = MagicMock()

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError()):
                result = await auditor.run_audit("http://localhost:3000")

        assert "error" in result
        assert "timed out" in result["error"].lower()

    async def test_nonzero_exit(self, auditor):
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"", b"Error occurred"))
        mock_proc.returncode = 1

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            with patch("asyncio.wait_for", new_callable=lambda: AsyncMock) as mock_wait:
                mock_wait.return_value = (b"", b"Error occurred")
                mock_proc.communicate = mock_wait
                result = await auditor.run_audit("http://localhost:3000")

        assert "error" in result


class TestSaveReport:
    async def test_writes_json_and_jsonl(self, auditor, tmp_path):
        report = {
            "url": "http://localhost:3000",
            "scores": {"performance": 90.0},
            "timestamp": "2024-01-15T10:00:00Z",
        }
        await auditor.save_report(report)

        # Check JSON report
        assert auditor.report_path.exists()
        saved = json.loads(auditor.report_path.read_text())
        assert saved["scores"]["performance"] == 90.0

        # Check JSONL history
        assert auditor.history_path.exists()
        lines = auditor.history_path.read_text().strip().split("\n")
        assert len(lines) == 1
        assert json.loads(lines[0])["url"] == "http://localhost:3000"

    async def test_appends_to_history(self, auditor):
        r1 = {"url": "http://a.com", "scores": {}, "timestamp": "t1"}
        r2 = {"url": "http://b.com", "scores": {}, "timestamp": "t2"}
        await auditor.save_report(r1)
        await auditor.save_report(r2)

        lines = auditor.history_path.read_text().strip().split("\n")
        assert len(lines) == 2


class TestGetLatestReport:
    def test_no_file(self, auditor):
        assert auditor.get_latest_report() is None

    async def test_returns_saved_report(self, auditor):
        report = {"url": "http://x.com", "scores": {"performance": 85.0}}
        await auditor.save_report(report)
        latest = auditor.get_latest_report()
        assert latest["url"] == "http://x.com"


class TestGetHistory:
    def test_empty_history(self, auditor):
        assert auditor.get_history() == []

    async def test_history_with_data(self, auditor):
        for i in range(5):
            await auditor.save_report({"url": f"http://site{i}.com", "scores": {}})

        history = auditor.get_history(limit=3)
        assert len(history) == 3
        assert history[-1]["url"] == "http://site4.com"

    async def test_history_respects_limit(self, auditor):
        for i in range(10):
            await auditor.save_report({"url": f"http://site{i}.com", "scores": {}})

        history = auditor.get_history(limit=5)
        assert len(history) == 5
