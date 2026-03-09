"""Document parsers — extract text from various file formats."""
from __future__ import annotations

from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)

# Mapping of MIME types to parser functions
_MIME_PARSERS: dict[str, str] = {
    "application/pdf": "parse_pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "parse_docx",
    "text/csv": "parse_csv",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "parse_xlsx",
    "application/vnd.ms-excel": "parse_xlsx",
    "text/plain": "parse_text",
    "text/markdown": "parse_text",
    "application/json": "parse_text",
}


def parse_document(filepath: str, mime_type: str) -> str:
    """Dispatch to the appropriate parser based on MIME type.

    Falls back to plain-text parsing for unrecognised types.
    """
    parser_name = _MIME_PARSERS.get(mime_type, "parse_text")
    parser_fn = globals()[parser_name]
    logger.info("parsing_document", filepath=filepath, mime_type=mime_type, parser=parser_name)
    return parser_fn(filepath)


def parse_pdf(filepath: str) -> str:
    """Extract text from a PDF using pypdf."""
    from pypdf import PdfReader

    reader = PdfReader(filepath)
    pages: list[str] = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        if text.strip():
            pages.append(f"[Page {i + 1}]\n{text}")
    return "\n\n".join(pages)


def parse_docx(filepath: str) -> str:
    """Extract text from a DOCX using python-docx."""
    import docx

    doc = docx.Document(filepath)
    paragraphs: list[str] = []
    for para in doc.paragraphs:
        text = para.text.strip()
        if text:
            paragraphs.append(text)
    return "\n\n".join(paragraphs)


def parse_csv(filepath: str) -> str:
    """Read a CSV and return a text representation using pandas."""
    import pandas as pd

    df = pd.read_csv(filepath)
    # Include shape info and a stringified version of the data
    header = f"CSV: {df.shape[0]} rows x {df.shape[1]} columns\nColumns: {', '.join(df.columns.tolist())}\n"
    return header + df.to_string(index=False, max_rows=500)


def parse_xlsx(filepath: str) -> str:
    """Read an Excel file and return a text representation using pandas + openpyxl."""
    import pandas as pd

    sheets = pd.read_excel(filepath, sheet_name=None, engine="openpyxl")
    parts: list[str] = []
    for sheet_name, df in sheets.items():
        header = f"Sheet: {sheet_name} ({df.shape[0]} rows x {df.shape[1]} columns)"
        parts.append(header + "\n" + df.to_string(index=False, max_rows=500))
    return "\n\n".join(parts)


def parse_text(filepath: str) -> str:
    """Read a plain text file."""
    return Path(filepath).read_text(encoding="utf-8", errors="replace")
