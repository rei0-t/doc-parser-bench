"""
Generate the bundled synthetic sample documents and their ground truth.

Every sample is FAKE data created for this project. That is deliberate: the
benchmark must be reproducible offline, and no real (or confidential) document
should ever end up in a public repository.

Each sample is described as a rectangular grid of cells:
  - ``"text"``  -> a normal 1x1 cell,
  - ``None``    -> an empty cell, or a slot covered by a span,
  - a span      -> declared separately via ``spans`` as (row, col, colspan, rowspan)
                    and anchored on the top-left cell of the covered block.

The ground-truth JSON is derived from the very same description, so the
annotation and the document can never drift apart.

Output:
    samples/sample_00X.pdf
    samples/sample_00X_gt.json

Run:
    python scripts/generate_samples.py
"""

import json
import os

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

SAMPLES = {
    "sample_001": {
        "title": "Synthetic Invoice",
        "note": "Plain bordered table — the easy case.",
        "tables": [
            {
                "grid": [
                    ["Item", "Qty", "Unit Price", "Amount"],
                    ["Wireless Mouse", "2", "59.00", "118.00"],
                    ["USB-C Cable", "5", "19.90", "99.50"],
                    ["Desk Lamp", "1", "129.00", "129.00"],
                    ["Total", "", "", "346.50"],
                ],
                "spans": [],
            }
        ],
    },
    "sample_002": {
        "title": "Synthetic Annual Report",
        "note": "Two tables on one page.",
        "tables": [
            {
                "grid": [
                    ["Segment", "2025", "2024", "YoY"],
                    ["Cloud", "1200", "980", "+22%"],
                    ["Devices", "640", "700", "-9%"],
                    ["Services", "430", "380", "+13%"],
                ],
                "spans": [],
            },
            {
                "grid": [
                    ["Cost Category", "Amount"],
                    ["R&D", "520"],
                    ["S&M", "310"],
                    ["G&A", "180"],
                ],
                "spans": [],
            },
        ],
    },
    "sample_003": {
        "title": "Synthetic Product Specification",
        "note": "Contains a merged cell (colspan).",
        "tables": [
            {
                "grid": [
                    ["Attribute", "Value"],
                    ["Dimensions", "210 x 297 mm"],
                    ["Colour", "White"],
                    ["Warranty", None],
                    ["Weight", "350 g"],
                ],
                "spans": [(3, 0, 2, 1)],
            }
        ],
    },
    "sample_004": {
        "title": "Synthetic Regional Sales Report",
        "note": "Section headers spanning three columns, repeated column headers.",
        "tables": [
            {
                "grid": [
                    ["North America", None, None],
                    ["Product", "Units", "Revenue"],
                    ["Alpha", "100", "1000"],
                    ["Beta", "150", "1800"],
                    ["Asia", None, None],
                    ["Product", "Units", "Revenue"],
                    ["Gamma", "90", "900"],
                ],
                "spans": [(0, 0, 3, 1), (4, 0, 3, 1)],
            }
        ],
    },
    "sample_005": {
        "title": "Synthetic Product List",
        "note": "Plain bordered table, used as a second easy case.",
        "tables": [
            {
                "grid": [
                    ["SKU", "Name", "Price"],
                    ["A-01", "Widget", "9.99"],
                    ["A-02", "Gadget", "14.50"],
                    ["A-03", "Gizmo", "7.25"],
                ],
                "spans": [],
            }
        ],
    },
    "sample_006": {
        "title": "Synthetic Statistical Yearbook (borderless)",
        "note": "No ruling lines: rule-based line detection cannot see this table.",
        "borderless": True,
        "tables": [
            {
                "grid": [
                    ["Year", "Population (10k)", "GDP (100M)", "Growth"],
                    ["2019", "140005", "986515", "6.0%"],
                    ["2020", "141212", "1013567", "4.8%"],
                    ["2021", "141260", "1149237", "8.1%"],
                    ["2022", "141175", "1204724", "3.0%"],
                ],
                "spans": [],
            }
        ],
    },
}


def grid_to_annotation(grid, spans):
    """Turn a visual grid into the annotation record used by the benchmark."""
    span_map = {(row, col): (colspan, rowspan) for row, col, colspan, rowspan in spans}
    cells = []
    for row_index, row in enumerate(grid):
        for col_index, value in enumerate(row):
            if not isinstance(value, str) or value == "":
                continue
            colspan, rowspan = span_map.get((row_index, col_index), (1, 1))
            cells.append(
                {
                    "row": row_index,
                    "col": col_index,
                    "text": value,
                    "rowspan": rowspan,
                    "colspan": colspan,
                }
            )
    return {
        "num_rows": len(grid),
        "num_cols": max((len(row) for row in grid), default=0),
        "cells": cells,
    }


def build_annotation(spec, filename):
    """Build the ``*_gt.json`` payload for one sample."""
    tables = []
    for table in spec["tables"]:
        annotation = grid_to_annotation(table["grid"], table.get("spans", []))
        annotation["page"] = 1
        tables.append(annotation)
    return {"filename": filename, "tables": tables}


def build_pdf(spec, path):
    """Render one sample to PDF."""
    styles = getSampleStyleSheet()
    document = SimpleDocTemplate(
        path,
        pagesize=A4,
        leftMargin=60,
        rightMargin=60,
        topMargin=60,
        bottomMargin=60,
    )
    flow = [
        Paragraph(spec["title"], styles["Title"]),
        Paragraph(spec["note"], styles["Italic"]),
        Spacer(1, 16),
    ]

    for table_spec in spec["tables"]:
        grid = table_spec["grid"]
        data = [[("" if value is None else value) for value in row] for row in grid]
        table = Table(data, colWidths=[120, 120, 120, 120][: len(grid[0])])
        style = [
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]

        if not spec.get("borderless"):
            style += [
                ("GRID", (0, 0), (-1, -1), 0.6, colors.black),
                ("ROWBACKGROUNDS", (0, 0), (-1, 0), [colors.lightgrey]),
            ]
        else:
            style += [
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]

        for row, col, colspan, rowspan in table_spec.get("spans", []):
            style.append(("SPAN", (col, row), (col + colspan - 1, row + rowspan - 1)))
            style.append(("ALIGN", (col, row), (col + colspan - 1, row + rowspan - 1), "CENTER"))
            style.append(
                ("BACKGROUND", (col, row), (col + colspan - 1, row + rowspan - 1), colors.lightblue)
            )

        table.setStyle(TableStyle(style))
        flow.append(table)
        flow.append(Spacer(1, 18))

    document.build(flow)


def main():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    samples_dir = os.path.join(project_root, "samples")
    os.makedirs(samples_dir, exist_ok=True)

    for name, spec in SAMPLES.items():
        pdf_path = os.path.join(samples_dir, name + ".pdf")
        gt_path = os.path.join(samples_dir, name + "_gt.json")

        build_pdf(spec, pdf_path)
        with open(gt_path, "w", encoding="utf-8") as handle:
            json.dump(build_annotation(spec, name + ".pdf"), handle, ensure_ascii=False, indent=2)

        print(f"[ok] {os.path.relpath(pdf_path, project_root)}")
        print(f"[ok] {os.path.relpath(gt_path, project_root)}")


if __name__ == "__main__":
    main()
