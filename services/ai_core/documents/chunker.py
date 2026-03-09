"""Document chunker — splits text into overlapping chunks for embedding."""
from __future__ import annotations

import re

import structlog

logger = structlog.get_logger(__name__)

# Rough approximation: 1 token ~= 4 characters for English text
_CHARS_PER_TOKEN = 4

# Regex to detect headings (Markdown-style or all-caps lines)
_HEADING_RE = re.compile(
    r"^(?:#{1,6}\s+.+|[A-Z][A-Z\s]{4,}[A-Z])$",
    re.MULTILINE,
)

# Regex to detect page markers like [Page 1]
_PAGE_RE = re.compile(r"\[Page\s+(\d+)\]")


def chunk_document(
    text: str,
    target_tokens: int = 800,
    overlap_tokens: int = 150,
) -> list[dict]:
    """Split text into chunks with metadata.

    Each chunk is a dict with:
      - content: the chunk text
      - chunk_index: 0-based position
      - estimated_page: page number if page markers are found
      - heading: nearest preceding heading, if detected

    The chunker tries to split on paragraph boundaries to avoid cutting
    mid-sentence.
    """
    if not text or not text.strip():
        return []

    target_chars = target_tokens * _CHARS_PER_TOKEN
    overlap_chars = overlap_tokens * _CHARS_PER_TOKEN

    # Pre-scan for page markers
    page_positions: list[tuple[int, int]] = []
    for match in _PAGE_RE.finditer(text):
        page_positions.append((match.start(), int(match.group(1))))

    # Pre-scan for headings
    heading_positions: list[tuple[int, str]] = []
    for match in _HEADING_RE.finditer(text):
        heading_positions.append((match.start(), match.group(0).strip()))

    chunks: list[dict] = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = min(start + target_chars, text_len)

        # Try to break at a paragraph boundary (double newline)
        if end < text_len:
            # Search for a paragraph break near the target end
            search_start = max(start + target_chars // 2, start)
            para_break = text.rfind("\n\n", search_start, end + overlap_chars)
            if para_break > start:
                end = para_break + 2  # include the newlines
            else:
                # Fall back to single newline
                line_break = text.rfind("\n", search_start, end + overlap_chars)
                if line_break > start:
                    end = line_break + 1

        chunk_text = text[start:end].strip()
        if not chunk_text:
            start = end
            continue

        # Determine estimated page number
        estimated_page = _get_page_at(start, page_positions)

        # Determine nearest heading
        heading = _get_heading_at(start, heading_positions)

        chunks.append({
            "content": chunk_text,
            "chunk_index": len(chunks),
            "estimated_page": estimated_page,
            "heading": heading,
        })

        # Advance with overlap
        start = max(end - overlap_chars, start + 1)
        if end >= text_len:
            break

    logger.debug("document_chunked", chunk_count=len(chunks), text_length=text_len)
    return chunks


def _get_page_at(position: int, page_positions: list[tuple[int, int]]) -> int | None:
    """Return the estimated page number at a given character position."""
    page = None
    for pos, page_num in page_positions:
        if pos <= position:
            page = page_num
        else:
            break
    return page


def _get_heading_at(position: int, heading_positions: list[tuple[int, str]]) -> str | None:
    """Return the nearest preceding heading at a given character position."""
    heading = None
    for pos, heading_text in heading_positions:
        if pos <= position:
            heading = heading_text
        else:
            break
    return heading
