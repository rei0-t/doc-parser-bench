"""
RAGFlow-based parser — the optional deep-learning counterpart.

RAGFlow (https://github.com/infiniflow/ragflow) is an open-source document
parsing service. It runs as a server (usually via Docker) and exposes a REST
API. This parser uploads a document, waits for RAGFlow to finish parsing it,
then converts the returned HTML into the project's ``Table`` structure.

This parser is **optional**: it is only enabled when both ``RAGFLOW_API_KEY``
and ``RAGFLOW_BASE_URL`` are set. The benchmark runs perfectly well with just
the pdfplumber baseline, and the report renders a clear "not available" note
for parsers that cannot run.

Scope note (v1): the HTML -> ``Table`` conversion below is complete and unit
tested, while the REST calls follow RAGFlow's v1 API shape. Endpoint paths have
changed between RAGFlow releases, so verify them against the version you
deploy before relying on this parser in anger.
"""

import os
import time
from html.parser import HTMLParser
from typing import List, Optional

import requests

from .base import DocumentParser, Table, TableCell


class _TableHTMLParser(HTMLParser):
    """Collect ``<table>`` elements from an HTML string into ``Table`` objects."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: List[Table] = []
        self._in_table = False
        self._in_cell = False
        self._text_buffer: List[str] = []
        self._current_row: List[TableCell] = []
        self._current_table: List[List[TableCell]] = []
        self._row_index = 0
        self._page = 1
        self._rowspan = 1
        self._colspan = 1

    # -- HTMLParser hooks ------------------------------------------------
    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self._in_table = True
            self._current_table = []
            self._row_index = 0
        elif tag == "tr" and self._in_table:
            self._current_row = []
        elif tag in ("td", "th") and self._in_table:
            self._in_cell = True
            self._text_buffer = []
            attributes = dict(attrs)
            try:
                self._rowspan = max(1, int(attributes.get("rowspan", 1) or 1))
                self._colspan = max(1, int(attributes.get("colspan", 1) or 1))
            except (TypeError, ValueError):
                self._rowspan = self._colspan = 1

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._in_cell:
            text = " ".join(part.strip() for part in self._text_buffer if part.strip())
            if text:
                self._current_row.append(
                    TableCell(
                        row=self._row_index,
                        col=len(self._current_row),
                        text=text,
                        rowspan=self._rowspan,
                        colspan=self._colspan,
                    )
                )
            self._in_cell = False
        elif tag == "tr" and self._in_table:
            if self._current_row:
                self._current_table.append(self._current_row)
            self._row_index += 1
        elif tag == "table" and self._in_table:
            if self._current_table:
                cells: List[TableCell] = []
                num_cols = 0
                for row_index, row in enumerate(self._current_table):
                    for cell in row:
                        cell.row = row_index
                        cells.append(cell)
                        num_cols = max(num_cols, cell.col + cell.colspan)
                self.tables.append(
                    Table(
                        cells=cells,
                        num_rows=len(self._current_table),
                        num_cols=num_cols,
                        page=self._page,
                    )
                )
            self._in_table = False

    def handle_data(self, data):
        if self._in_cell:
            self._text_buffer.append(data)


def tables_from_html(html: str, page: int = 1) -> List[Table]:
    """Convert an HTML fragment containing ``<table>`` elements into ``Table``s."""
    parser = _TableHTMLParser()
    parser._page = page
    parser.feed(html)
    parser.close()
    return parser.tables


class RagflowParser(DocumentParser):
    """Delegate table extraction to a running RAGFlow server."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        dataset_id: Optional[str] = None,
        timeout: int = 180,
    ) -> None:
        self.api_key = api_key or os.environ.get("RAGFLOW_API_KEY")
        self.base_url = (base_url or os.environ.get("RAGFLOW_BASE_URL", "")).rstrip("/")
        self.dataset_id = dataset_id or os.environ.get("RAGFLOW_DATASET_ID")
        self.timeout = timeout

    @staticmethod
    def is_configured() -> bool:
        """True when the environment provides everything the parser needs."""
        return bool(os.environ.get("RAGFLOW_API_KEY")) and bool(
            os.environ.get("RAGFLOW_BASE_URL")
        )

    @property
    def name(self) -> str:
        return "ragflow"

    def parse_tables(self, file_path: str) -> List[Table]:
        """Upload, parse and convert a document through RAGFlow."""
        if not self.is_configured():
            raise RuntimeError(
                "RAGFlow is not configured. Set RAGFLOW_API_KEY and "
                "RAGFLOW_BASE_URL, or run the benchmark without this parser."
            )

        dataset_id = self.dataset_id or self._ensure_dataset()
        doc_id = self._upload_document(dataset_id, file_path)
        self._wait_for_parsing(dataset_id, doc_id)
        html = self._retrieve_parsed_html(dataset_id, doc_id)
        return tables_from_html(html)

    # -- REST helpers ----------------------------------------------------
    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}"}

    def _ensure_dataset(self) -> str:
        url = f"{self.base_url}/api/v1/datasets"
        response = requests.get(url, headers=self._headers(), timeout=self.timeout)
        response.raise_for_status()
        for dataset in response.json().get("data", []):
            if dataset.get("name") == "doc-parser-bench":
                return dataset["id"]
        response = requests.post(
            url,
            headers=self._headers(),
            json={"name": "doc-parser-bench", "permission": "me"},
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()["data"]["id"]

    def _upload_document(self, dataset_id: str, file_path: str) -> str:
        url = f"{self.base_url}/api/v1/datasets/{dataset_id}/documents"
        with open(file_path, "rb") as handle:
            response = requests.post(
                url,
                headers=self._headers(),
                files={"file": handle},
                timeout=self.timeout,
            )
        response.raise_for_status()
        return response.json()["data"]["id"]

    def _wait_for_parsing(self, dataset_id: str, doc_id: str, poll: int = 3) -> None:
        url = f"{self.base_url}/api/v1/datasets/{dataset_id}/documents/{doc_id}"
        deadline = time.time() + self.timeout
        while time.time() < deadline:
            response = requests.get(url, headers=self._headers(), timeout=self.timeout)
            response.raise_for_status()
            run_status = response.json().get("data", {}).get("run", "DONE")
            if run_status == "DONE":
                return
            time.sleep(poll)
        raise TimeoutError("RAGFlow did not finish parsing within the timeout.")

    def _retrieve_parsed_html(self, dataset_id: str, doc_id: str) -> str:
        url = f"{self.base_url}/api/v1/datasets/{dataset_id}/documents/{doc_id}/parse"
        response = requests.get(url, headers=self._headers(), timeout=self.timeout)
        response.raise_for_status()
        return response.json().get("data", {}).get("content", "")
