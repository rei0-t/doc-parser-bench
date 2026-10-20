"""
Table quality metrics.

Current implementation: cell-level precision / recall / F1.
Future: TEDS (Tree Edit Distance-based Similarity) for structure-aware scores.

Why cell-level (and not TEDS) in v1:
- TEDS requires parsing HTML into a tree and implementing tree-edit distance,
  which is a meaningful project on its own.
- The ``apted`` dependency that ships it has installation friction.
- Cell-level metrics are enough to demonstrate the benchmark end-to-end, and
  their limitation (they cannot see structure errors) is stated openly in the
  README instead of being hidden.
"""

from dataclasses import dataclass, field
from typing import List, Set, Tuple

from parsers.base import Table, TableCell


@dataclass
class MetricResult:
    """Evaluation metrics for a single table."""

    precision: float
    recall: float
    f1: float
    num_correct: int
    num_predicted: int
    num_ground_truth: int


@dataclass
class BenchmarkResult:
    """The outcome of comparing one parser against one document's ground truth."""

    results: List[MetricResult] = field(default_factory=list)
    num_gt_tables: int = 0
    num_predicted_tables: int = 0
    num_matched_tables: int = 0

    @property
    def num_missed_tables(self) -> int:
        """Ground-truth tables the parser did not report at all."""
        return max(0, self.num_gt_tables - self.num_matched_tables)

    @property
    def num_extra_tables(self) -> int:
        """Tables the parser reported that have no ground-truth counterpart."""
        return max(0, self.num_predicted_tables - self.num_matched_tables)

    def aggregate(self) -> MetricResult:
        return aggregate(self.results)


def normalize_cell_key(cell: TableCell) -> Tuple[int, int, str]:
    """Normalize a cell to ``(row, col, normalized_text)`` for comparison.

    Normalization rules:
    - strip surrounding whitespace,
    - lowercase,
    - collapse internal whitespace runs into a single space.

    Rationale: OCR output and different parsers disagree on trailing spaces and
    casing. Normalizing removes that noise without making the comparison
    lax about content.
    """
    text = " ".join(cell.text.strip().lower().split())
    return (cell.row, cell.col, text)


def evaluate_table(ground_truth: Table, predicted: Table) -> MetricResult:
    """Evaluate one predicted table against its ground-truth counterpart.

    Note:
        This is a *cell-level* comparison. It does NOT catch:
        - swapped rows / columns (structure errors),
        - wrong ``rowspan`` / ``colspan``,
        - tables the parser failed to detect at all (see ``evaluate_many``).
        TEDS would cover the first two; ``evaluate_many`` covers the third.
    """
    gt_cells: Set[Tuple[int, int, str]] = {
        normalize_cell_key(c) for c in ground_truth.cells
    }
    pred_cells: Set[Tuple[int, int, str]] = {
        normalize_cell_key(c) for c in predicted.cells
    }

    correct = len(gt_cells & pred_cells)
    num_predicted = len(pred_cells)
    num_gt = len(gt_cells)

    precision = correct / num_predicted if num_predicted > 0 else 0.0
    recall = correct / num_gt if num_gt > 0 else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall) > 0
        else 0.0
    )

    return MetricResult(
        precision=precision,
        recall=recall,
        f1=f1,
        num_correct=correct,
        num_predicted=num_predicted,
        num_ground_truth=num_gt,
    )


def evaluate_many(ground_truths: List[Table], predictions: List[Table]) -> BenchmarkResult:
    """Compare a document's ground truth with everything a parser found.

    Tables are paired positionally (both lists sorted by page). Two cases are
    handled explicitly so a parser cannot look better than it is:

    - a ground-truth table with **no** counterpart counts as a total miss
      (precision 0, recall 0) — a parser that finds nothing scores 0, not 1;
    - a predicted table with **no** counterpart is reported as an *extra* table
      (not scored, but visible in the report).
    """
    gt_sorted = sorted(ground_truths, key=lambda t: t.page)
    pred_sorted = sorted(predictions, key=lambda t: t.page)

    results: List[MetricResult] = []
    paired = min(len(gt_sorted), len(pred_sorted))

    for index in range(paired):
        results.append(evaluate_table(gt_sorted[index], pred_sorted[index]))

    # Ground-truth tables the parser did not report at all -> a full miss.
    for missed in gt_sorted[paired:]:
        results.append(
            MetricResult(
                precision=0.0,
                recall=0.0,
                f1=0.0,
                num_correct=0,
                num_predicted=0,
                num_ground_truth=len(missed.cells),
            )
        )

    return BenchmarkResult(
        results=results,
        num_gt_tables=len(gt_sorted),
        num_predicted_tables=len(pred_sorted),
        num_matched_tables=paired,
    )


def aggregate(results: List[MetricResult]) -> MetricResult:
    """Aggregate per-table results using micro-averaging (summed counts).

    Micro-averaging is used because tables differ in size: a large table
    should count for more than a tiny one.
    """
    total_correct = sum(r.num_correct for r in results)
    total_predicted = sum(r.num_predicted for r in results)
    total_ground_truth = sum(r.num_ground_truth for r in results)

    precision = total_correct / total_predicted if total_predicted > 0 else 0.0
    recall = total_correct / total_ground_truth if total_ground_truth > 0 else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall) > 0
        else 0.0
    )

    return MetricResult(
        precision=precision,
        recall=recall,
        f1=f1,
        num_correct=total_correct,
        num_predicted=total_predicted,
        num_ground_truth=total_ground_truth,
    )
