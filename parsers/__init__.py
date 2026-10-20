"""
Parser registry.

``available_parsers()`` returns the parsers that can actually run in the
current environment. The RAGFlow parser is only included when it is
configured, so the benchmark never fails because of a missing service.
"""

from typing import List

from .base import DocumentParser, Table, TableCell
from .pdfplumber_parser import PDFPlumberParser


def available_parsers() -> List[DocumentParser]:
    """Return the list of parsers enabled in this environment."""
    parsers: List[DocumentParser] = [PDFPlumberParser()]

    # Imported lazily so that `requests` is only required when RAGFlow is used.
    try:
        from .ragflow import RagflowParser

        if RagflowParser.is_configured():
            parsers.append(RagflowParser())
    except ImportError:  # pragma: no cover - requests not installed
        pass

    return parsers


__all__ = [
    "DocumentParser",
    "Table",
    "TableCell",
    "PDFPlumberParser",
    "available_parsers",
]
