# doc-parser-bench

Benchmark tool for evaluating **document parsers** on table-extraction quality,
against hand-annotated ground truth.

> A deliberately small v1: one parser interface, cell-level precision / recall /
> F1, and side-by-side HTML reports with per-cell diff highlighting.

![status](https://img.shields.io/badge/python-3.10%2B-blue)
![license](https://img.shields.io/badge/license-MIT-green)

## Why This Tool

When picking a document parser (RAGFlow, MinerU, Unstructured, …) most people
either:

- trust public academic benchmarks (e.g. PubTabNet) that are built from papers,
  not from the kind of documents *you* actually have to parse, or
- eyeball two outputs side by side, which is subjective and not reproducible.

This tool lets you:

- run several parsers on **your own documents**,
- get **quantitative metrics** (precision / recall / F1) against ground truth,
- read a **side-by-side HTML report** where wrong cells are highlighted.

## Features

- ✅ Parser abstraction layer — adding a backend is one class
- ✅ Cell-level precision / recall / F1, micro-averaged
- ✅ Missed tables are scored as misses (a parser that finds nothing scores 0)
- ✅ 6 bundled synthetic samples with matching ground truth
- ✅ HTML report per document with per-cell diff highlighting
- ✅ Unit tests (`python tests/test_metrics.py`)
- ⚠️ **Current limitation:** cell-level metrics cannot see *structure* errors
  (row/column swaps, wrong spans). See [Future Work](#future-work).

## Project Layout

```
doc-parser-bench/
├── parsers/
│   ├── base.py               # abstract interface + Table / TableCell
│   ├── pdfplumber_parser.py  # rule-based baseline (default)
│   └── ragflow.py            # optional deep-learning parser (needs a server)
├── metrics/table.py          # cell-level P/R/F1
├── templates/report.html     # Jinja2 + Bootstrap report template
├── samples/                  # 6 synthetic PDFs + *_gt.json ground truth
│   └── annotation_guide.md   # how the ground truth is produced
├── scripts/generate_samples.py   # regenerates the bundled samples
├── tests/test_metrics.py
├── benchmark.py              # core: run parsers, score, build the view-model
├── ground_truth.py           # load *_gt.json -> Table objects
├── report.py                 # CLI: one document -> one HTML report
└── run_all.py                # CLI: every sample -> reports + summary
```

## Installation

**Prerequisites:** Python 3.10+ (developed on 3.13).

```bash
git clone https://github.com/rei0-t/doc-parser-bench.git
cd doc-parser-bench

python -m venv venv
source venv/Scripts/activate      # Windows
# source venv/bin/activate        # Linux / macOS

pip install -r requirements.txt
```

> If `pip install` is slow, a mirror usually fixes it:
> `pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple`

## Usage

### Evaluate one document

```bash
python report.py --input samples/sample_001.pdf --output reports/sample_001.html
```

The ground truth is auto-discovered as `samples/sample_001_gt.json`
(override with `--ground-truth`).

### Evaluate every sample

```bash
python run_all.py
# -> reports/sample_00X.html  +  reports/summary.json
```

```
=== Summary over all samples ===
Parser         Precision    Recall        F1
pdfplumber         1.000     0.800     0.889
```

### Read a report

Open `reports/sample_003.html` in a browser:

- a precision / recall / F1 badge per parser,
- ground truth and parser output side by side,
- green = correct, red = false positive, yellow = false negative,
- tables the parser never found are called out explicitly.

### Run the tests

```bash
python tests/test_metrics.py
```

### Regenerate the bundled samples

```bash
python scripts/generate_samples.py
```

## Architecture

### Design Decisions

**Why an abstraction layer?**

Parsers differ wildly in API and output format:

| parser | kind | returns |
|---|---|---|
| `pdfplumber` | in-process library | `list[list[str]]` |
| `ragflow` | REST service | HTML with embedded `<table>` |

`parsers/base.py` defines one contract — `parse_tables() -> List[Table]` — so
the evaluation code never knows which backend produced a table. Adding a
backend means implementing a single class; nothing else changes.

**Why cell-level metrics instead of TEDS?**

TEDS (Tree-Edit-Distance-based Similarity) is the gold standard for table
evaluation, but:

- it needs HTML-to-tree parsing plus a tree-edit-distance implementation,
  which is a project in itself,
- the `apted` dependency has real installation friction.

For v1 the metric is cell-level:

```
precision = correct_cells / detected_cells
recall    = correct_cells / ground_truth_cells
f1        = 2 * precision * recall / (precision + recall)
```

**Limitation (stated honestly):** cell-level metrics cannot see structure
errors. `sample_003` shows it: the truth says *Warranty* spans two columns,
pdfplumber reports it as a normal cell — identical text, identical position,
so the metric still says “correct”, while a TEDS score would penalise the lost
span. A future version must migrate to TEDS.

**Why are missed tables scored instead of skipped?**

If a parser finds zero tables, silently dropping those ground-truth tables
would make it look *better* than a parser that found most tables. So an
unmatched ground-truth table is scored as a full miss (precision 0, recall 0),
and extra tables the parser invented are reported but not penalised.

**Why is the cell text normalized?**

`metrics/table.py:normalize_cell_key()` lowercases and collapses whitespace
before comparing. OCR output and different parsers disagree on trailing
spaces and casing; normalizing removes that noise without loosening the
comparison on content.

## Samples

Six **synthetic** documents, generated by `scripts/generate_samples.py` from a
single description that produces the PDF *and* the ground truth at the same
time — so the annotation and the document can never drift apart.

| File | Scenario | Difficulty |
|---|---|---|
| `sample_001.pdf` | Invoice | Plain bordered table |
| `sample_002.pdf` | Annual report | Two tables on one page |
| `sample_003.pdf` | Product spec | Merged cell (`colspan`) |
| `sample_004.pdf` | Regional sales | Section headers spanning 3 columns |
| `sample_005.pdf` | Product list | Plain bordered table |
| `sample_006.pdf` | Statistical yearbook | **Borderless** table (no ruling lines) |

Annotation rules: [`samples/annotation_guide.md`](samples/annotation_guide.md).

> To use *real* public documents (GB standards, annual reports, statistics
> yearbooks), swap the PDFs and re-annotate with the same JSON schema.
> **Never** use company-internal documents.

## Results

Measured on the 6 bundled samples (100 ground-truth cells) with
`python run_all.py`:

| Parser | Precision | Recall | F1 | Notes |
|---|---|---|---|---|
| `pdfplumber` | 1.000 | 0.800 | 0.889 | Rule-based baseline; blind to borderless tables |
| `ragflow` | n/a | n/a | n/a | Optional; needs a running RAGFlow server |

Per sample:

| Sample | Precision | Recall | F1 | Ground-truth cells | Observed |
|---|---|---|---|---|---|
| sample_001 | 1.000 | 1.000 | 1.000 | 18 | 18/18 correct |
| sample_002 | 1.000 | 1.000 | 1.000 | 24 | 24/24 correct |
| sample_003 | 1.000 | 1.000 | 1.000 | 9 | 9/9 correct (span structure still lost) |
| sample_004 | 1.000 | 1.000 | 1.000 | 17 | 17/17 correct |
| sample_005 | 1.000 | 1.000 | 1.000 | 12 | 12/12 correct |
| sample_006 | 0.000 | 0.000 | 0.000 | 20 | table not detected at all |

The interesting row is `sample_006`: pdfplumber detects tables by ruling lines,
so a borderless table is invisible to it. It is not a bug in the benchmark —
it is exactly the failure mode a rule-based baseline has, and precisely the
reason an ML-based parser is worth its cost. Reproduce it with
`python report.py --input samples/sample_006.pdf --output reports/sample_006.html`.

## Future Work

- [ ] **TEDS metric** — tree-edit distance for structure-aware evaluation
- [ ] **More parsers** — MinerU, Unstructured
- [ ] **Better table matching** — align predicted/ground-truth tables by page +
      bounding box instead of by position
- [ ] **Reading-order metric** — detect multi-column layout errors
- [ ] **OCR evaluation** — character-level accuracy, not just cell text
- [ ] **Real public documents** — swap the synthetic set for GB standards /
      annual reports with the same annotation schema
- [ ] **Larger sample set** — 20+ documents across more types

## Contributing

This is a personal learning project. Issues and PRs are welcome, but response
time may be slow.

## License

MIT — see [LICENSE](LICENSE).

## Acknowledgments

- [pdfplumber](https://github.com/jsvine/pdfplumber) for the rule-based baseline
- [RAGFlow](https://github.com/infiniflow/ragflow) for the open-source parsing service
- [PubTabNet](https://github.com/ibm-aur-nlp/PubTabNet) for inspiration on table evaluation
