"""Evaluation metrics for table extraction."""

from .table import (
    BenchmarkResult,
    MetricResult,
    aggregate,
    evaluate_many,
    evaluate_table,
    normalize_cell_key,
)

__all__ = [
    "BenchmarkResult",
    "MetricResult",
    "aggregate",
    "evaluate_many",
    "evaluate_table",
    "normalize_cell_key",
]
