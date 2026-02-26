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

## Recommended test PDFs

All PDFs live in `data/pdfs/` and are named by their document UUID from the `documents` table. The following subset covers the key extraction edge cases:

| UUID filename                 | Original name                              | Pages | Edge case                                                                       |
| ----------------------------- | ------------------------------------------ | ----: | ------------------------------------------------------------------------------- |
| `ccf0c8b4-…-5ffbfab51123.pdf` | 1189.pdf                                   |     1 | Minimal single-page filing — fastest feedback loop                              |
| `203acc4f-…-8642e5aa9d3e.pdf` | Facebook User Privacy Long Form Notice.pdf |    10 | Settlement notice with embedded image + mixed layout (tables, bullets, headers) |
| `53d37647-…-7d11f51a9509.pdf` | 2023-03-29 Order [dckt 1130_0].pdf         |     8 | Court order with line numbers in margins — common extraction pitfall            |
| `8bb8b610-…-fc484241b695.pdf` | Feldman Appeal 0039 Pl Answering Brief.pdf |    72 | Appeals brief with Unicode special characters (⎯◆⎯)                             |
| `d2a369cf-…-cb26c333bbcf.pdf` | 2nd Amnd Consolidated Complaint.pdf        |   366 | Longest document — stress test for memory and `--pages` flag                    |

### Quick-start examples

```bash
cd backend

# Baseline — single-page PDF, fastest way to verify the report works
uv run python scripts/generate_report.py data/pdfs/ccf0c8b4-742f-4e22-9a0d-5ffbfab51123.pdf

# Mixed layout — settlement notice with image, tables, and bullet points
uv run python scripts/generate_report.py data/pdfs/203acc4f-2d49-4e05-bbc5-8642e5aa9d3e.pdf

# Line numbers — court order where margin numbers can pollute block text
uv run python scripts/generate_report.py data/pdfs/53d37647-7d31-4db4-b7b4-7d11f51a9509.pdf

# Unicode — appeals brief with special characters in headings
uv run python scripts/generate_report.py data/pdfs/8bb8b610-ca28-4905-a2db-fc484241b695.pdf --pages 10

# Stress test — first 10 pages of the longest document
uv run python scripts/generate_report.py data/pdfs/d2a369cf-a435-4150-88f6-cb26c333bbcf.pdf --pages 10

# Compare parsers side-by-side (requires REDUCTO_API_KEY)
uv run python scripts/generate_report.py data/pdfs/203acc4f-2d49-4e05-bbc5-8642e5aa9d3e.pdf --compare

# Score after annotating (export ground truth JSON from the HTML report first)
uv run python scripts/score_extraction.py data/pdfs/ccf0c8b4-742f-4e22-9a0d-5ffbfab51123.pdf ground_truth.json

# Cross-parser score
uv run python scripts/score_extraction.py data/pdfs/ccf0c8b4-742f-4e22-9a0d-5ffbfab51123.pdf ground_truth.json --parser reducto
```

## Bbox coordinate handling

- **PyMuPDF** bboxes: absolute PDF points. Converted to pixels via `coord * (dpi / 72)`
- **Reducto** bboxes: normalized 0-1 values as `[x0, y0, x1, y1]`. Converted via `coord * page_dimension_pts * (dpi / 72)`
- The renderer auto-detects coordinate space based on the parser name key in the results dict
