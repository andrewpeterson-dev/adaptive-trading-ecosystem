"""Citation assembler — extracts and formats citations from model outputs and tool results."""

from __future__ import annotations

import re

import structlog

logger = structlog.get_logger(__name__)


class CitationAssembler:
    """Extracts and formats citations, separating internal from external sources."""

    def extract_citations(self, content: str, tool_calls: list[dict]) -> list[dict]:
        """Extract citations from content and tool call results."""
        citations: list[dict] = []

        # Extract inline citations from content [source](url) or [doc:id]
        citations.extend(self._extract_inline_citations(content))

        # Extract citations from tool call results (document searches, news searches)
        for tc in tool_calls:
            output = tc.get("output", {})
            data = output.get("data", {}) if isinstance(output, dict) else {}
            if isinstance(data, dict):
                # Document search results
                if "chunks" in data:
                    for chunk in data["chunks"]:
                        citations.append({
                            "source": "internal",
                            "title": chunk.get("heading", chunk.get("filename", "Document")),
                            "documentId": chunk.get("document_id"),
                            "chunkIds": [chunk.get("id")] if chunk.get("id") else [],
                            "pageNumber": chunk.get("page_number"),
                            "snippet": chunk.get("content", "")[:200],
                        })
                # External search results
                if "sources" in data:
                    for source in data["sources"]:
                        citations.append({
                            "source": "external",
                            "title": source.get("title", ""),
                            "url": source.get("url", ""),
                            "snippet": source.get("snippet", "")[:200],
                            "date": source.get("date"),
                        })

        return citations

    def _extract_inline_citations(self, content: str) -> list[dict]:
        """Extract markdown-style citations from content."""
        citations: list[dict] = []
        # Match [title](url) patterns
        url_pattern = r"\[([^\]]+)\]\((https?://[^\)]+)\)"
        for match in re.finditer(url_pattern, content):
            citations.append({
                "source": "external",
                "title": match.group(1),
                "url": match.group(2),
            })
        return citations
