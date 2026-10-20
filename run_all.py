"""
Run the benchmark over every sample and write one HTML report per sample.

Usage:
    python run_all.py

Scans ``samples/`` for ``*_gt.json`` files, pairs each with its document,
evaluates all available parsers, writes ``reports/<sample>.html`` and prints
an aggregate summary (also saved to ``reports/summary.json``).
"""

import glob
import json
import os
import sys
from collections import defaultdict

from jinja2 import Template

from benchmark import TEMPLATE_PATH, evaluate_document
from metrics.table import aggregate
from parsers import available_parsers

HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLES_DIR = os.path.join(HERE, "samples")
REPORTS_DIR = os.path.join(HERE, "reports")


def find_samples(samples_dir: str = SAMPLES_DIR):
    """Pair every ``*_gt.json`` with its document.

    ``sample_001_gt.json`` describes the document ``sample_001.pdf``.
    """
    pairs = []
    for gt_path in sorted(glob.glob(os.path.join(samples_dir, "*_gt.json"))):
        document_path = gt_path.replace("_gt.json", ".pdf")
        if os.path.exists(document_path):
            pairs.append((document_path, gt_path))
        else:
            print(f"[warn] no document for {gt_path}, skipping", file=sys.stderr)
    return pairs


def main() -> int:
    os.makedirs(REPORTS_DIR, exist_ok=True)
    samples = find_samples()
    if not samples:
        print("No samples found in samples/.", file=sys.stderr)
        return 1

    parsers = available_parsers()
    parser_names = [p.name for p in parsers]
    collected = defaultdict(list)

    with open(TEMPLATE_PATH, "r", encoding="utf-8") as handle:
        template = Template(handle.read(), autoescape=True)

    for document_path, gt_path in samples:
        evaluations = evaluate_document(document_path, gt_path, parsers=parsers)
        name = os.path.splitext(os.path.basename(document_path))[0]

        html = template.render(
            filename=os.path.basename(document_path), parsers=evaluations
        )
        report_path = os.path.join(REPORTS_DIR, name + ".html")
        with open(report_path, "w", encoding="utf-8") as handle:
            handle.write(html)
        print(f"[ok] {report_path}")

        # Collect per-table results so the cross-sample summary counts every
        # ground-truth cell, including tables a parser failed to detect.
        for evaluation in evaluations:
            if evaluation.error is None:
                collected[evaluation.name].extend(evaluation.results)

    summary = {}
    for name in parser_names:
        results = collected.get(name, [])
        if not results:
            summary[name] = None
            continue
        agg = aggregate(results)
        summary[name] = {
            "precision": agg.precision,
            "recall": agg.recall,
            "f1": agg.f1,
            "num_correct": agg.num_correct,
            "num_predicted": agg.num_predicted,
            "num_ground_truth": agg.num_ground_truth,
        }

    summary_path = os.path.join(REPORTS_DIR, "summary.json")
    with open(summary_path, "w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2, ensure_ascii=False)

    print("\n=== Summary over all samples ===")
    print(f"{'Parser':<14}{'Precision':>10}{'Recall':>10}{'F1':>10}")
    for name in parser_names:
        metrics = summary.get(name)
        if metrics:
            print(
                f"{name:<14}{metrics['precision']:>10.3f}"
                f"{metrics['recall']:>10.3f}{metrics['f1']:>10.3f}"
            )
        else:
            print(f"{name:<14}{'n/a':>10}{'n/a':>10}{'n/a':>10}")
    print(f"\nsummary written: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
