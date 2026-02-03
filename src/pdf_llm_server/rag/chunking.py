"""Text chunking utilities for the RAG pipeline."""

import re

from pydantic import BaseModel

from .pdf_parser import ParsedDocument


class ChunkData(BaseModel):
    """A chunk of content ready for embedding."""

    content: str
    chunk_type: str
    page_number: int
    position: int
    bbox: list[float] | None = None


def fixed_size_chunking(
    text: str, chunk_size: int = 1000, overlap: int = 200
) -> list[str]:
    """Split text into fixed-size chunks with overlap.

    Args:
        text: The text to chunk.
        chunk_size: Maximum characters per chunk.
        overlap: Number of overlapping characters between chunks.

    Returns:
        List of text chunks.
    """
    if not text or chunk_size <= 0:
        return []

    if overlap >= chunk_size:
        raise ValueError("overlap must be less than chunk_size to avoid infinite loops")

    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size

        # Try to break at word boundary
        if end < len(text):
            # Look for last space within chunk
            last_space = text.rfind(" ", start, end)
            if last_space > start:
                end = last_space

        chunks.append(text[start:end].strip())

        # Break after processing the final chunk
        if end >= len(text):
            break

        start = end - overlap

    return [c for c in chunks if c]


def semantic_chunking_by_paragraphs(
    text: str, max_chunk_size: int = 1500
) -> list[str]:
    """Split text by paragraphs, merging small paragraphs.

    Args:
        text: The text to chunk.
        max_chunk_size: Maximum characters per chunk.

    Returns:
        List of text chunks preserving paragraph boundaries.
    """
    if not text:
        return []

    # Split by double newlines (paragraph boundaries)
    paragraphs = re.split(r"\n\s*\n", text)
    paragraphs = [p.strip() for p in paragraphs if p.strip()]

    if not paragraphs:
        return []

    chunks = []
    current_chunk = []
    current_size = 0

    for para in paragraphs:
        para_size = len(para)

        # If single paragraph exceeds max, use fixed-size chunking
        if para_size > max_chunk_size:
            # Flush current chunk first
            if current_chunk:
                chunks.append("\n\n".join(current_chunk))
                current_chunk = []
                current_size = 0
            # Chunk the large paragraph
            chunks.extend(fixed_size_chunking(para, max_chunk_size, overlap=200))
            continue

        # Check if adding this paragraph exceeds max
        new_size = current_size + para_size + (2 if current_chunk else 0)
        if new_size > max_chunk_size and current_chunk:
            chunks.append("\n\n".join(current_chunk))
            current_chunk = []
            current_size = 0

        current_chunk.append(para)
        current_size += para_size + (2 if len(current_chunk) > 1 else 0)

    # Flush remaining
    if current_chunk:
        chunks.append("\n\n".join(current_chunk))

    return chunks


def detect_content_type(text: str) -> str:
    """Detect the type of content in a text block.

    Args:
        text: The text to classify.

    Returns:
        Content type: "heading", "paragraph", "list", or "table".
    """
    if not text:
        return "paragraph"

    stripped = text.strip()
    lines = stripped.split("\n")

    # Check for table-like content (multiple | characters)
    if "|" in stripped and lines[0].count("|") >= 2:
        return "table"

    # Check for list items
    list_patterns = [
        r"^[\s]*[•◦▪▸►\-\*]",  # Bullet patterns
        r"^[\s]*\d+[\.\)]",  # Numbered list
        r"^[\s]*[a-zA-Z][\.\)]",  # Lettered list
    ]
    list_count = sum(
        1 for line in lines if any(re.match(p, line) for p in list_patterns)
    )
    if list_count > len(lines) / 2:
        return "list"

    # Short uppercase text is likely a heading
    if len(stripped) < 100 and stripped.isupper():
        return "heading"

    # Short text with no punctuation at end might be heading
    if len(stripped) < 80 and not stripped.endswith((".", "!", "?", ":")):
        return "heading"

    return "paragraph"


def chunk_parsed_document(
    doc: ParsedDocument, strategy: str = "semantic"
) -> list[ChunkData]:
    """Chunk a parsed PDF document.

    Args:
        doc: ParsedDocument from parse_pdf().
        strategy: "semantic" for paragraph-aware or "fixed" for fixed-size.

    Returns:
        List of ChunkData ready for database insertion.
    """
    chunks = []
    position = 0

    for page in doc.pages:
        # Group consecutive blocks of same type
        page_text_parts = []
        current_type = None
        current_texts = []
        current_bbox = None

        for block in page.blocks:
            if block.block_type != current_type and current_texts:
                # Flush accumulated text
                combined_text = " ".join(current_texts)
                page_text_parts.append((combined_text, current_type, current_bbox))
                current_texts = []
                current_bbox = None

            current_type = block.block_type
            current_texts.append(block.text)
            # Keep first bbox for the group
            if current_bbox is None:
                current_bbox = block.bbox

        # Flush final group
        if current_texts:
            combined_text = " ".join(current_texts)
            page_text_parts.append((combined_text, current_type, current_bbox))

        # Apply chunking strategy to each group
        for text, block_type, bbox in page_text_parts:
            if strategy == "fixed":
                text_chunks = fixed_size_chunking(text)
            else:  # semantic
                text_chunks = semantic_chunking_by_paragraphs(text)

            for chunk_text in text_chunks:
                if chunk_text.strip():
                    chunks.append(
                        ChunkData(
                            content=chunk_text,
                            chunk_type=block_type or "paragraph",
                            page_number=page.page_number,
                            position=position,
                            bbox=bbox,
                        )
                    )
                    position += 1

        # Handle tables as separate chunks
        for table in page.tables:
            # Convert table to text representation
            table_lines = []
            if table.headers:
                table_lines.append(" | ".join(table.headers))
                table_lines.append("-" * 40)
            for row in table.rows:
                table_lines.append(" | ".join(row))

            if table_lines:
                chunks.append(
                    ChunkData(
                        content="\n".join(table_lines),
                        chunk_type="table",
                        page_number=page.page_number,
                        position=position,
                        bbox=None,
                    )
                )
                position += 1

    return chunks
