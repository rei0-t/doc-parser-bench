"""
Generate an evaluation report for a single document.

Usage:
    python report.py --input samples/sample_001.pdf \
                     --output reports/sample_001.html

The ground-truth file is auto-discovered as ``<sample>_gt.json`` next to the
document, and can be overridden with ``--ground-truth``.
"""

import argparse
import os
import sys

from jinja2 import Template

from benchmark import TEMPLATE_PATH, evaluate_document
from ground_truth import ground_truth_path_for


def render_report(document_path: str, ground_truth_path: str) -> str:
    """Evaluate the document with every available parser and render HTML."""
    evaluations = evaluate_document(document_path, ground_truth_path)

    with open(TEMPLATE_PATH, "r", encoding="utf-8") as handle:
        template = Template(handle.read(), autoescape=True)

    return template.render(
        filename=os.path.basename(document_path),
        parsers=evaluations,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a parser evaluation report for one document."
    )
    parser.add_argument("--input", required=True, help="Path to the document (PDF).")
    parser.add_argument(
        "--ground-truth",
        default=None,
        help="Path to the ground-truth JSON. Derived from --input if omitted.",
    )
    parser.add_argument(
        "--output", required=True, help="Path of the HTML report to write."
    )
    args = parser.parse_args()

    document_path = args.input
    ground_truth_path = args.ground_truth or ground_truth_path_for(document_path)

    if not os.path.exists(document_path):
        print(f"error: document not found: {document_path}", file=sys.stderr)
        return 1
    if not os.path.exists(ground_truth_path):
        print(
            f"error: ground truth not found: {ground_truth_path}\n"
            "       (expected '<sample>_gt.json' next to the document)",
            file=sys.stderr,
        )
        return 1

    html = render_report(document_path, ground_truth_path)

    output_path = os.path.abspath(args.output)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write(html)

    print(f"report written: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
