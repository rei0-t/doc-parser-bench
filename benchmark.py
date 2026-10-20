"""
Core of the benchmark: run parsers on a document, score them, and build the
view-model consumed by the HTML template.

Both ``report.py`` (single document) and ``run_all.py`` (whole sample set) are
thin CLI wrappers around :func:`evaluate_document`.
"""

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from ground_truth import load_ground_truth
from metrics.table import (
    BenchmarkResult,
    MetricResult,
    aggregate,
    evaluate_many,
    normalize_cell_key,
)
from parsers import available_parsers
from parsers.base import DocumentParser, Table

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_PATH = os.path.join(HERE, "templates", "report.html")

# Marker for grid slots that are covered by a rowspan/colspan cell.
COVERED = "covered"


@dataclass
class CellView:
    """A cell prepared for rendering, with its diff status."""

    text: str
    row: int
    col: int
    rowspan: int
    colspan: int
    status: str  # "correct" | "missing" | "extra"


@dataclass
class TableView:
    """One ground-truth / prediction pair prepared for rendering."""

    page: int
    gt_cells: List[CellView]
    pred_cells: List[CellView]
    gt_grid: List[List[Optional[CellView]]]
    pred_grid: List[List[Optional[CellView]]]
    num_correct: int
    num_gt_cells: int
    num_pred_cells: int
    missed: bool = False  # ground truth table the parser never reported


@dataclass
class ParserEvaluation:
    """Everything the report needs to know about one parser on one document."""

    name: str
    error: Optional[str] = None
    metrics: Optional[MetricResult] = None
    results: List[MetricResult] = field(default_factory=list)
    tables: List[TableView] = field(default_factory=list)
    num_gt_tables: int = 0
    num_predicted_tables: int = 0

    @property
    def num_missed_tables(self) -> int:
        return sum(1 for t in self.tables if t.missed)

    @property
    def num_extra_tables(self) -> int:
        return max(0, self.num_predicted_tables - (self.num_gt_tables - self.num_missed_tables))


def _cell_views(
    cells, reference: set, missing_status: str
) -> List[CellView]:
    """Turn raw cells into views, tagging each one against ``reference``."""
    views: List[CellView] = []
    for cell in cells:
        key = normalize_cell_key(cell)
        views.append(
            CellView(
                text=cell.text,
                row=cell.row,
                col=cell.col,
                rowspan=cell.rowspan,
                colspan=cell.colspan,
                status="correct" if key in reference else missing_status,
            )
        )
    return views


def _build_grid(
    views: Sequence[CellView], num_rows: int, num_cols: int
) -> List[List[Optional[CellView]]]:
    """Lay cell views out on a grid, marking slots covered by a span."""
    grid: List[List[Optional[CellView]]] = [
        [None for _ in range(max(num_cols, 1))] for _ in range(max(num_rows, 1))
    ]

    for view in views:
        if view.row >= len(grid) or view.col >= len(grid[view.row]):
            continue
        grid[view.row][view.col] = view
        # Slots covered by this cell's span are skipped when rendering.
        for r in range(view.row + 1, view.row + view.rowspan):
            if r < len(grid):
                for c in range(view.col, view.col + view.colspan):
                    if c < len(grid[r]):
                        grid[r][c] = CellView(
                            text="",
                            row=r,
                            col=c,
                            rowspan=1,
                            colspan=1,
                            status=COVERED,
                        )

    return grid


def _table_view(gt: Table, pred: Optional[Table]) -> TableView:
    """Build the side-by-side view for one table pair.

    ``pred`` is ``None`` when the parser did not report this table at all.
    """
    gt_keys = {normalize_cell_key(c) for c in gt.cells}
    pred_keys = (
        {normalize_cell_key(c) for c in pred.cells} if pred is not None else set()
    )

    gt_views = _cell_views(gt.cells, pred_keys, "missing")
    pred_views = _cell_views(pred.cells, gt_keys, "extra") if pred is not None else []

    return TableView(
        page=gt.page,
        gt_cells=gt_views,
        pred_cells=pred_views,
        gt_grid=_build_grid(gt_views, gt.num_rows, gt.num_cols),
        pred_grid=(
            _build_grid(pred_views, pred.num_rows, pred.num_cols)
            if pred is not None
            else _build_grid([], gt.num_rows, gt.num_cols)
        ),
        num_correct=len(gt_keys & pred_keys),
        num_gt_cells=len(gt_keys),
        num_pred_cells=len(pred_keys),
        missed=pred is None,
    )


def evaluate_document(
    document_path: str,
    ground_truth_path: str,
    parsers: Optional[Sequence[DocumentParser]] = None,
) -> List[ParserEvaluation]:
    """Run every parser on ``document_path`` and score it against the truth."""
    ground_truths = load_ground_truth(ground_truth_path)
    parsers = list(parsers) if parsers is not None else available_parsers()

    evaluations: List[ParserEvaluation] = []
    for parser in parsers:
        try:
            predictions = parser.parse_tables(document_path)
        except Exception as exc:  # noqa: BLE001 - a broken parser must not abort the run
            evaluations.append(
                ParserEvaluation(name=parser.name, error=str(exc))
            )
            continue

        benchmark: BenchmarkResult = evaluate_many(ground_truths, predictions)
        metrics = aggregate(benchmark.results) if benchmark.results else None

        # Rebuild the table views with the same pairing rule as evaluate_many().
        gt_sorted = sorted(ground_truths, key=lambda t: t.page)
        pred_sorted = sorted(predictions, key=lambda t: t.page)
        views: List[TableView] = []
        for index in range(len(gt_sorted)):
            pred = pred_sorted[index] if index < len(pred_sorted) else None
            views.append(_table_view(gt_sorted[index], pred))

        evaluations.append(
            ParserEvaluation(
                name=parser.name,
                error=None,
                metrics=metrics,
                results=list(benchmark.results),
                tables=views,
                num_gt_tables=benchmark.num_gt_tables,
                num_predicted_tables=benchmark.num_predicted_tables,
            )
        )

    return evaluations


def metrics_to_dict(metrics: Optional[MetricResult]) -> Optional[Dict]:
    """Serialize a ``MetricResult`` for the template."""
    if metrics is None:
        return None
    return {
        "precision": metrics.precision,
        "recall": metrics.recall,
        "f1": metrics.f1,
        "num_correct": metrics.num_correct,
        "num_predicted": metrics.num_predicted,
        "num_ground_truth": metrics.num_ground_truth,
    }
