"""
Document parser base interface.

Every parser in this project implements the same tiny contract:

    parse_tables(file_path) -> List[Table]

The evaluation code therefore never needs to know whether a table came from a
rule-based PDF library or from a deep-learning parsing service.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List


@dataclass
class TableCell:
    """A single cell of a table.

    ``row`` / ``col`` are 0-based grid coordinates. ``rowspan`` / ``colspan``
    describe how many grid slots the cell occupies (1 for a normal cell).
    """

    row: int
    col: int
    text: str
    rowspan: int = 1
    colspan: int = 1


@dataclass
class Table:
    """A table extracted from a document."""

    cells: List[TableCell]
    num_rows: int
    num_cols: int
    page: int = 1  # 1-based page number the table was found on


class DocumentParser(ABC):
    """Abstract base class for all document parsers."""

    @abstractmethod
    def parse_tables(self, file_path: str) -> List[Table]:
        """Extract every table found in ``file_path``.

        Args:
            file_path: Path to the document (PDF, Excel, ...).

        Returns:
            The tables found in the document, in reading order.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If the file format is not supported.
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def name(self) -> str:
        """Short parser name used in reports (``"pdfplumber"``, ``"ragflow"``)."""
        raise NotImplementedError
