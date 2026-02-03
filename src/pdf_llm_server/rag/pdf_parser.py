"""PDF parsing module using PyMuPDF for text and structure extraction."""

import statistics
from pathlib import Path

import fitz  # PyMuPDF
from pydantic import BaseModel

from ..logger import logger


class TextBlock(BaseModel):
    """A text block extracted from a PDF page."""

    block_index: int
    block_type: str  # "heading", "paragraph", "list_item"
    text: str
    font_size: float
    is_bold: bool
    bbox: list[float] | None = None  # [x0, y0, x1, y1], None if unavailable


class TableData(BaseModel):
    """Table data extracted from a PDF page."""

    table_index: int
    headers: list[str]
    rows: list[list[str]]


class ParsedPage(BaseModel):
    """A parsed PDF page containing blocks and tables."""

    page_number: int
    blocks: list[TextBlock]
    tables: list[TableData]


class ParsedDocument(BaseModel):
    """A fully parsed PDF document."""

    file_path: str
    total_pages: int
    pages: list[ParsedPage]


def _extract_spans_info(block_dict: dict) -> tuple[str, float, bool]:
    """Extract text, font size, and bold status from a block's spans.

    Args:
        block_dict: A block dictionary from PyMuPDF's get_text("dict").

    Returns:
        Tuple of (text, average_font_size, is_bold).
    """
    texts = []
    font_sizes = []
    bold_count = 0
    total_spans = 0

    for line in block_dict.get("lines", []):
        for span in line.get("spans", []):
            text = span.get("text", "").strip()
            if text:
                texts.append(text)
                font_sizes.append(span.get("size", 12.0))
                total_spans += 1
                # Check for bold via font flags or font name
                flags = span.get("flags", 0)
                font_name = span.get("font", "").lower()
                if (flags & 2**4) or "bold" in font_name:
                    bold_count += 1

    if not texts:
        return "", 12.0, False

    combined_text = " ".join(texts)
    avg_font_size = statistics.mean(font_sizes) if font_sizes else 12.0
    is_bold = bold_count > total_spans / 2 if total_spans > 0 else False

    return combined_text, avg_font_size, is_bold


def _classify_block(
    text: str, font_size: float, median_size: float, is_bold: bool
) -> str:
    """Classify a text block based on its properties.

    Args:
        text: The block's text content.
        font_size: Average font size of the block.
        median_size: Median font size across the document.
        is_bold: Whether the block is predominantly bold.

    Returns:
        Block type: "heading", "list_item", or "paragraph".
    """
    # Check for list items
    stripped = text.strip()
    if stripped and (
        stripped[0] in "•◦▪▸►-*"
        or (len(stripped) > 2 and stripped[0].isdigit() and stripped[1] in ".)")
    ):
        return "list_item"

    # Headings: larger font or bold with short text
    if font_size > median_size * 1.2:
        return "heading"
    if is_bold and len(text) < 100:
        return "heading"

    return "paragraph"


def parse_pdf(file_path: str | Path) -> ParsedDocument:
    """Parse a PDF file and extract structured content.

    Args:
        file_path: Path to the PDF file.

    Returns:
        ParsedDocument containing all extracted pages, blocks, and tables.
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"PDF file not found: {file_path}")

    doc = fitz.open(file_path)
    try:
        logger.info("parsing pdf", file_path=str(file_path), total_pages=doc.page_count)

        # First pass: collect all font sizes to calculate median
        all_font_sizes = []
        for page in doc:
            page_dict = page.get_text("dict")
            for block in page_dict.get("blocks", []):
                if block.get("type") == 0:  # Text block
                    _, font_size, _ = _extract_spans_info(block)
                    if font_size > 0:
                        all_font_sizes.append(font_size)

        median_size = statistics.median(all_font_sizes) if all_font_sizes else 12.0

        # Second pass: extract and classify blocks
        parsed_pages = []
        for page_num, page in enumerate(doc):
            page_dict = page.get_text("dict")
            blocks = []

            for block_idx, block in enumerate(page_dict.get("blocks", [])):
                if block.get("type") != 0:  # Skip non-text blocks (images, etc.)
                    continue

                text, font_size, is_bold = _extract_spans_info(block)
                if not text.strip():
                    continue

                bbox = block.get("bbox")
                if bbox is None:
                    logger.warn(
                        "missing bbox for text block",
                        file_path=str(file_path),
                        page_number=page_num + 1,
                        block_index=block_idx,
                    )

                block_type = _classify_block(text, font_size, median_size, is_bold)

                blocks.append(
                    TextBlock(
                        block_index=block_idx,
                        block_type=block_type,
                        text=text,
                        font_size=font_size,
                        is_bold=is_bold,
                        bbox=list(bbox) if bbox else None,
                    )
                )

            # Extract tables using PyMuPDF's table finder
            tables = []
            try:
                page_tables = page.find_tables()
                for table_idx, table in enumerate(page_tables):
                    extracted = table.extract()
                    if extracted and len(extracted) > 0:
                        headers = [str(cell) if cell else "" for cell in extracted[0]]
                        rows = [
                            [str(cell) if cell else "" for cell in row]
                            for row in extracted[1:]
                        ]
                        tables.append(
                            TableData(table_index=table_idx, headers=headers, rows=rows)
                        )
            except Exception as e:
                logger.warn(
                    "table extraction failed",
                    page_number=page_num + 1,
                    error=str(e),
                )

            parsed_pages.append(
                ParsedPage(page_number=page_num + 1, blocks=blocks, tables=tables)
            )

        logger.info(
            "pdf parsed successfully",
            file_path=str(file_path),
            total_pages=len(parsed_pages),
            total_blocks=sum(len(p.blocks) for p in parsed_pages),
            total_tables=sum(len(p.tables) for p in parsed_pages),
        )

        return ParsedDocument(
            file_path=str(file_path),
            total_pages=len(parsed_pages),
            pages=parsed_pages,
        )
    finally:
        doc.close()
