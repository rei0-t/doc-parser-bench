"""
PDFPlumber-based parser — the rule-based baseline.

pdfplumber finds tables by looking for ruling lines (and optionally text
alignment heuristics). That makes it fast, dependency-light and fully local,
but it struggles with:
- borderless tables,
- multi-level / merged headers,
- tables whose cells span several grid slots.

That weakness is exactly the reason this parser exists: it is the *lower
bound* every ML-based parser should be compared against.
"""

from typing import List

import pdfplumber

from .base import DocumentParser, Table, TableCell


class PDFPlumberParser(DocumentParser):
    """Extract tables from a PDF using pdfplumber's built-in detection."""

    @property
    def name(self) -> str:
        return "pdfplumber"

    def parse_tables(self, file_path: str) -> List[Table]:
        """Extract all tables from the PDF at ``file_path``.

        pdfplumber returns each table as ``list[list[str | None]]``. ``None``
        marks an empty or covered cell; those slots are skipped, matching the
        annotation rules in ``samples/annotation_guide.md``.
        """
        tables: List[Table] = []

        with pdfplumber.open(file_path) as pdf:
            for page_number, page in enumerate(pdf.pages, start=1):
                for raw_table in page.extract_tables():
                    if not raw_table:
                        continue

                    num_rows = len(raw_table)
                    num_cols = max((len(row) for row in raw_table), default=0)
                    cells: List[TableCell] = []

                    for row_index, row in enumerate(raw_table):
                        for col_index, raw_text in enumerate(row):
                            if raw_text is None:
                                continue  # empty / covered cell
                            text = str(raw_text).strip()
                            if not text:
                                continue
                            cells.append(
                                TableCell(
                                    row=row_index,
                                    col=col_index,
                                    text=text,
                                    rowspan=1,
                                    colspan=1,
                                )
                            )

                    if not cells:
                        continue

                    tables.append(
                        Table(
                            cells=cells,
                            num_rows=num_rows,
                            num_cols=num_cols,
                            page=page_number,
                        )
                    )

        return tables
