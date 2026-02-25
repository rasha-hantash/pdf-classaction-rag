# Extraction Evaluation Tools

Tools for measuring PDF extraction quality by comparing parser output against human-annotated ground truth.

## Workflow

### 1. Generate an interactive report

```bash
cd backend
uv run python scripts/generate_report.py <pdf_path> [options]
```

Options:

- `--parser pymupdf|reducto` — parser to use (default: pymupdf)
- `--compare` — run both parsers side-by-side
- `--pages N` — limit to first N pages
- `--dpi N` — rendering DPI (default: 150)
- `-o PATH` — output path (default: `<pdf_name>.report.html`)

### 2. Annotate in the browser

Open the generated HTML file. For each block:

- Select a verdict: **correct**, **partial**, or **wrong**
- For partial/wrong, enter the corrected text
- Use "Add Missing Block" for content the parser missed entirely
- Add page-level notes as needed

Click **Download Ground Truth JSON** to export annotations.

### 3. Score extraction quality

```bash
cd backend
uv run python scripts/score_extraction.py <pdf_path> <ground_truth.json> [options]
```

Options:

- `--parser pymupdf|reducto` — parser to score (default: same as ground truth)
- `--json` — output as JSON instead of text table

### Metrics

| Metric              | Definition                                                                  |
| ------------------- | --------------------------------------------------------------------------- |
| **Accuracy**        | `(correct + partial * 0.5) / total_annotated`                               |
| **Precision**       | `matched_blocks / total_extracted`                                          |
| **Recall**          | `matched_blocks / (annotated + missing)`                                    |
| **Text Similarity** | Average `SequenceMatcher.ratio()` for partial/wrong blocks with corrections |
| **Missing Rate**    | `missing_count / (annotated + missing)`                                     |

### Cross-parser scoring

Ground truth annotated against one parser (e.g. pymupdf) can be scored against a different parser (e.g. reducto). Cross-parser alignment uses fuzzy text matching (`difflib.SequenceMatcher` with 0.6 threshold) instead of direct block index mapping.

## Files

| File                     | Purpose                                                     |
| ------------------------ | ----------------------------------------------------------- |
| `ground_truth.py`        | Pydantic models for annotation schema + JSON persistence    |
| `report_renderer.py`     | Page rendering, bbox overlays (PIL), HTML report generation |
| `scoring.py`             | Block alignment, fuzzy matching, metrics computation        |
| `../generate_report.py`  | CLI: generate interactive HTML report                       |
| `../score_extraction.py` | CLI: score parser output against ground truth               |

## Bbox coordinate handling

- **PyMuPDF** bboxes: absolute PDF points. Converted to pixels via `coord * (dpi / 72)`
- **Reducto** bboxes: normalized 0-1 values as `[x0, y0, x1, y1]`. Converted via `coord * page_dimension_pts * (dpi / 72)`
- The renderer auto-detects coordinate space based on the parser name key in the results dict
