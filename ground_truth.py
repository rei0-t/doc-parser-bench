"""
Loading of ground-truth annotations.

Ground truth lives next to the document it describes, in a JSON file named
``<sample>_gt.json`` (e.g. ``sample_001.pdf`` -> ``sample_001_gt.json``).

Schema
------
{
  "filename": "sample_001.pdf",
  "tables": [
    {
      "page": 1,
      "num_rows": 3,
      "num_cols": 3,
      "cells": [
        {"row": 0, "col": 0, "text": "Sales", "rowspan": 1, "colspan": 1}
      ]
    }
  ]
}

The annotation rules that produce this file are documented in
``samples/annotation_guide.md``.
"""

import json
import os
from typing import List

from parsers.base import Table, TableCell


def ground_truth_path_for(document_path: str) -> str:
    """Return the conventional ground-truth path for a document path."""
    base, _ = os.path.splitext(document_path)
    return base + "_gt.json"


def load_ground_truth(path: str) -> List[Table]:
    """Load a ``*_gt.json`` file into a list of ``Table`` objects."""
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)

    tables: List[Table] = []
    for raw_table in payload.get("tables", []):
        cells = [
            TableCell(
                row=int(cell["row"]),
                col=int(cell["col"]),
                text=str(cell["text"]),
                rowspan=int(cell.get("rowspan", 1) or 1),
                colspan=int(cell.get("colspan", 1) or 1),
            )
            for cell in raw_table.get("cells", [])
        ]
        tables.append(
            Table(
                cells=cells,
                num_rows=int(raw_table.get("num_rows", 0)),
                num_cols=int(raw_table.get("num_cols", 0)),
                page=int(raw_table.get("page", 1)),
            )
        )
    return tables
