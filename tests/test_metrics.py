"""
Unit tests for the evaluation metrics and the HTML conversion.

Run without any test framework:
    python tests/test_metrics.py

Or with pytest:
    python -m pytest tests/
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from metrics.table import (  # noqa: E402
    aggregate,
    evaluate_many,
    evaluate_table,
    normalize_cell_key,
)
from parsers.base import Table, TableCell  # noqa: E402
from parsers.ragflow import tables_from_html  # noqa: E402


def _table(cells, num_rows=3, num_cols=3, page=1):
    return Table(cells=cells, num_rows=num_rows, num_cols=num_cols, page=page)


def test_perfect_match():
    gt = _table([TableCell(0, 0, "A"), TableCell(0, 1, "B"), TableCell(1, 0, "C")])
    pred = _table([TableCell(0, 0, "A"), TableCell(0, 1, "B"), TableCell(1, 0, "C")])
    result = evaluate_table(gt, pred)
    assert result.precision == 1.0
    assert result.recall == 1.0
    assert result.f1 == 1.0


def test_whitespace_and_case_are_normalized():
    gt = _table([TableCell(0, 0, "Sales")])
    pred = _table([TableCell(0, 0, "  sALes  ")])
    assert evaluate_table(gt, pred).num_correct == 1


def test_position_matters():
    """The same text in a different cell is a different cell."""
    gt = _table([TableCell(0, 0, "100"), TableCell(1, 0, "50")])
    pred = _table([TableCell(0, 0, "100"), TableCell(0, 1, "50")])
    result = evaluate_table(gt, pred)
    assert result.num_correct == 1
    assert abs(result.precision - 0.5) < 1e-9
    assert abs(result.recall - 0.5) < 1e-9


def test_missing_and_extra_cells():
    gt = _table([TableCell(0, 0, "A"), TableCell(0, 1, "B"), TableCell(1, 0, "C")])
    pred = _table([TableCell(0, 0, "A"), TableCell(0, 1, "B"), TableCell(2, 2, "Z")])
    result = evaluate_table(gt, pred)
    assert result.num_correct == 2
    assert result.num_predicted == 3
    assert result.num_ground_truth == 3
    assert abs(result.precision - 2 / 3) < 1e-9
    assert abs(result.recall - 2 / 3) < 1e-9


def test_a_parser_that_finds_nothing_scores_zero():
    """A missing table must be scored as a miss, not silently dropped."""
    gt = [_table([TableCell(0, 0, "A"), TableCell(0, 1, "B")])]
    benchmark = evaluate_many(gt, [])
    assert benchmark.num_gt_tables == 1
    assert benchmark.num_missed_tables == 1
    assert benchmark.results[0].f1 == 0.0
    assert benchmark.results[0].num_ground_truth == 2


def test_extra_tables_are_counted_but_not_penalized():
    gt = [_table([TableCell(0, 0, "A")])]
    pred = [
        _table([TableCell(0, 0, "A")]),
        _table([TableCell(0, 0, "B")]),
    ]
    benchmark = evaluate_many(gt, pred)
    assert benchmark.num_extra_tables == 1
    assert benchmark.results[0].f1 == 1.0


def test_aggregate_is_micro_averaged():
    first = evaluate_table(
        _table([TableCell(0, 0, "A"), TableCell(0, 1, "B")]),
        _table([TableCell(0, 0, "A")]),
    )
    second = evaluate_table(
        _table([TableCell(0, 0, "C")]),
        _table([TableCell(0, 0, "C")]),
    )
    agg = aggregate([first, second])
    assert agg.num_correct == 2
    assert agg.num_predicted == 2
    assert agg.num_ground_truth == 3
    assert abs(agg.recall - 2 / 3) < 1e-9


def test_normalize_cell_key_collapses_whitespace():
    cell = TableCell(0, 0, "  Hello \n  World ")
    assert normalize_cell_key(cell) == (0, 0, "hello world")


def test_html_tables_are_converted():
    html = """
    <table>
      <tr><td>A</td><td>B</td></tr>
      <tr><td>C</td><td>D</td></tr>
    </table>
    """
    tables = tables_from_html(html)
    assert len(tables) == 1
    assert tables[0].num_rows == 2
    assert tables[0].num_cols == 2
    assert {c.text for c in tables[0].cells} == {"A", "B", "C", "D"}


def test_html_tables_keep_spans():
    html = '<table><tr><td colspan="2">Wide</td></tr><tr><td>x</td><td>y</td></tr></table>'
    tables = tables_from_html(html)
    assert len(tables) == 1
    wide = [c for c in tables[0].cells if c.text == "Wide"][0]
    assert wide.colspan == 2


def main():
    tests = [
        value
        for name, value in sorted(globals().items())
        if name.startswith("test_") and callable(value)
    ]
    failures = []
    for test in tests:
        try:
            test()
            print(f"PASS {test.__name__}")
        except AssertionError as error:
            failures.append(test.__name__)
            print(f"FAIL {test.__name__}: {error}")
    print(f"\n{len(tests) - len(failures)}/{len(tests)} passed")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
