"""Document ingestion pipeline for the RAG system."""

import hashlib
import time
from pathlib import Path

from pydantic import BaseModel

from ..logger import logger
from .chunking import ChunkData, chunk_parsed_document
from .database import PgVectorStore
from .models import ChunkRecord, IngestedDocument
from .ocr import assess_needs_ocr
from .pdf_parser import parse_pdf


class IngestResult(BaseModel):
    """Result of a document ingestion."""

    document: IngestedDocument
    chunks_count: int
    was_duplicate: bool = False


def compute_file_hash(file_path: str | Path) -> str:
    """Compute SHA-256 hash of a file for deduplication.

    Args:
        file_path: Path to the file.

    Returns:
        Hex-encoded SHA-256 hash string.
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)

    return sha256.hexdigest()


def ingest_document(
    file_path: str | Path,
    db: PgVectorStore,
    metadata: dict | None = None,
    chunking_strategy: str = "semantic",
) -> IngestResult:
    """Ingest a single PDF document into the RAG system.

    Args:
        file_path: Path to the PDF file.
        db: PgVectorStore database connection.
        metadata: Optional metadata to attach to the document.
        chunking_strategy: "semantic" or "fixed" chunking strategy.

    Returns:
        IngestResult with document info and chunk count.
    """
    file_path = Path(file_path)
    start = time.perf_counter()

    # Step 1: Compute file hash for deduplication
    file_hash = compute_file_hash(file_path)

    # Step 2: Check for duplicates
    existing = db.get_document_by_hash(file_hash)
    if existing:
        logger.info(
            "document already exists",
            file_path=str(file_path),
            document_id=str(existing.id),
            file_hash=file_hash,
        )
        return IngestResult(document=existing, chunks_count=0, was_duplicate=True)

    # Step 3: Assess OCR needs
    needs_ocr = assess_needs_ocr(file_path)
    if needs_ocr:
        logger.warn(
            "document may need ocr",
            file_path=str(file_path),
            message="Text extraction may be incomplete for scanned documents",
        )

    # Step 4: Parse PDF
    parsed_doc = parse_pdf(file_path)

    # Step 5: Chunk content
    chunk_data_list = chunk_parsed_document(parsed_doc, strategy=chunking_strategy)

    # Step 6: Insert document record
    document = db.insert_document(
        file_hash=file_hash,
        file_path=str(file_path),
        metadata=metadata or {},
    )

    # Step 7: Convert ChunkData to ChunkRecord and insert
    chunk_records = [
        ChunkRecord(
            document_id=document.id,
            content=cd.content,
            chunk_type=cd.chunk_type,
            page_number=cd.page_number,
            position=cd.position,
            bbox=cd.bbox,
            embedding=None,  # Embeddings added by separate process
        )
        for cd in chunk_data_list
    ]

    if chunk_records:
        db.insert_chunks(chunk_records)

    duration_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "document ingested",
        document_id=str(document.id),
        file_path=str(file_path),
        chunks_count=len(chunk_records),
        duration_ms=round(duration_ms, 2),
    )

    return IngestResult(
        document=document,
        chunks_count=len(chunk_records),
        was_duplicate=False,
    )


class RAGIngestionPipeline:
    """Pipeline for ingesting documents into the RAG system."""

    def __init__(
        self,
        db: PgVectorStore,
        chunking_strategy: str = "semantic",
    ):
        """Initialize the ingestion pipeline.

        Args:
            db: PgVectorStore database connection.
            chunking_strategy: Default chunking strategy ("semantic" or "fixed").
        """
        self.db = db
        self.chunking_strategy = chunking_strategy

    def ingest(
        self,
        file_path: str | Path,
        metadata: dict | None = None,
    ) -> IngestResult:
        """Ingest a single document.

        Args:
            file_path: Path to the PDF file.
            metadata: Optional metadata to attach.

        Returns:
            IngestResult with document info and chunk count.
        """
        return ingest_document(
            file_path=file_path,
            db=self.db,
            metadata=metadata,
            chunking_strategy=self.chunking_strategy,
        )

    def ingest_batch(
        self,
        file_paths: list[str | Path],
        metadata: dict | None = None,
    ) -> list[IngestResult]:
        """Ingest multiple documents.

        Args:
            file_paths: List of paths to PDF files.
            metadata: Optional metadata to attach to all documents.

        Returns:
            List of IngestResult objects.
        """
        results = []
        total = len(file_paths)

        logger.info("starting batch ingestion", total_files=total)
        start = time.perf_counter()

        for i, file_path in enumerate(file_paths, 1):
            try:
                result = self.ingest(file_path, metadata)
                results.append(result)

                if i % 10 == 0 or i == total:
                    logger.info(
                        "batch progress",
                        processed=i,
                        total=total,
                        percent=round(i / total * 100, 1),
                    )
            except Exception as e:
                logger.error(
                    "failed to ingest document",
                    file_path=str(file_path),
                    error=str(e),
                )
                # Continue with next file

        duration_ms = (time.perf_counter() - start) * 1000
        successful = sum(1 for r in results if not r.was_duplicate)
        duplicates = sum(1 for r in results if r.was_duplicate)

        logger.info(
            "batch ingestion complete",
            total_files=total,
            successful=successful,
            duplicates=duplicates,
            failed=total - len(results),
            duration_ms=round(duration_ms, 2),
        )

        return results
