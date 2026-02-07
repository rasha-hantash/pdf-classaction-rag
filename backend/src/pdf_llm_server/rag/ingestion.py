"""Document ingestion pipeline for the RAG system."""

import hashlib
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from pydantic import BaseModel

from ..logger import logger
from .chunking import ChunkData, chunk_parsed_document
from .database import PgVectorStore
from .embeddings import EmbeddingClient
from .models import IngestedDocument
from .ocr import assess_needs_ocr
from .pdf_parser import parse_pdf


class PathValidationError(ValueError):
    """Raised when a file path fails security validation."""

    pass


class IngestResult(BaseModel):
    """Result of a document ingestion."""

    document: IngestedDocument | None = None
    chunks_count: int = 0
    was_duplicate: bool = False
    error: str | None = None


def validate_file_path(
    file_path: Path, allowed_dirs: list[Path] | None = None
) -> Path:
    """Validate a file path to prevent directory traversal attacks.

    Args:
        file_path: Path to validate.
        allowed_dirs: Optional list of allowed directories. If provided,
            the resolved path must be within one of these directories.

    Returns:
        Resolved absolute path.

    Raises:
        PathValidationError: If path is outside allowed directories.
        FileNotFoundError: If the file does not exist.
    """
    resolved = file_path.resolve()

    if not resolved.exists():
        raise FileNotFoundError(f"File not found: {resolved}")

    if allowed_dirs is not None:
        allowed_resolved = [d.resolve() for d in allowed_dirs]
        if not any(
            resolved.is_relative_to(allowed_dir) for allowed_dir in allowed_resolved
        ):
            raise PathValidationError(
                f"Path {resolved} is not within allowed directories"
            )

    return resolved


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
    embedding_client: EmbeddingClient | None = None,
    metadata: dict | None = None,
    chunking_strategy: str = "semantic",
    allowed_dirs: list[Path] | None = None,
    original_filename: str | None = None,
) -> IngestResult:
    """Ingest a single PDF document into the RAG system.

    Args:
        file_path: Path to the PDF file.
        db: PgVectorStore database connection.
        embedding_client: Optional EmbeddingClient for generating embeddings.
            If None, chunks are stored without embeddings.
        metadata: Optional metadata to attach to the document.
        chunking_strategy: "semantic" or "fixed" chunking strategy.
        allowed_dirs: Optional list of allowed directories for path validation.
            If provided, file_path must be within one of these directories.
        original_filename: Optional original filename to store in the database.
            If None, the file_path basename is used.

    Returns:
        IngestResult with document info and chunk count.

    Raises:
        PathValidationError: If file_path is outside allowed directories.
    """
    file_path = Path(file_path)

    # Validate path if allowed_dirs is specified
    if allowed_dirs is not None:
        file_path = validate_file_path(file_path, allowed_dirs)

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

    # Step 3: Assess OCR needs (skip for Reducto - it handles OCR internally)
    parser = os.getenv("PDF_PARSER", "pymupdf").lower()
    if parser == "reducto":
        needs_ocr = False
    else:
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

    # Step 6: Generate embeddings for chunks
    if embedding_client and chunk_data_list:
        texts = [chunk.content for chunk in chunk_data_list]
        embed_start = time.perf_counter()
        embedding_result = embedding_client.generate_embeddings(texts)
        embed_duration_ms = (time.perf_counter() - embed_start) * 1000

        # Validate embedding count matches chunk count
        if len(embedding_result.embeddings) != len(chunk_data_list):
            logger.error(
                "embedding count mismatch",
                file_path=str(file_path),
                expected=len(chunk_data_list),
                received=len(embedding_result.embeddings),
            )
            raise ValueError(
                f"Embedding count mismatch: expected {len(chunk_data_list)}, got {len(embedding_result.embeddings)}"
            )

        # Assign embeddings to chunks
        for i, chunk in enumerate(chunk_data_list):
            chunk.embedding = embedding_result.embeddings[i]

        if embedding_result.failed_indices:
            logger.warn(
                "some embeddings failed",
                file_path=str(file_path),
                failed_count=len(embedding_result.failed_indices),
                total_count=len(texts),
            )

        logger.info(
            "embeddings generated",
            file_path=str(file_path),
            chunks_count=len(texts),
            success_count=embedding_result.success_count,
            duration_ms=round(embed_duration_ms, 2),
        )

    # Step 7: Insert document and chunks atomically in a single transaction
    stored_path = original_filename if original_filename else str(file_path)
    document, chunk_records = db.insert_document_with_chunks(
        file_hash=file_hash,
        file_path=stored_path,
        chunks=chunk_data_list,
        metadata=metadata or {},
    )

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
        embedding_client: EmbeddingClient | None = None,
        chunking_strategy: str = "semantic",
        allowed_dirs: list[Path] | None = None,
    ):
        """Initialize the ingestion pipeline.

        Args:
            db: PgVectorStore database connection.
            embedding_client: Optional EmbeddingClient for generating embeddings.
                If None, chunks are stored without embeddings.
            chunking_strategy: Default chunking strategy ("semantic" or "fixed").
            allowed_dirs: Optional list of allowed directories for path validation.
                If provided, all ingested files must be within these directories.
        """
        self.db = db
        self.embedding_client = embedding_client
        self.chunking_strategy = chunking_strategy
        self.allowed_dirs = allowed_dirs
        # Store connection string for creating worker connections in parallel mode
        self._connection_string = db.connection_string

    def ingest(
        self,
        file_path: str | Path,
        metadata: dict | None = None,
        original_filename: str | None = None,
    ) -> IngestResult:
        """Ingest a single document.

        Args:
            file_path: Path to the PDF file.
            metadata: Optional metadata to attach.
            original_filename: Optional original filename to store in the database.

        Returns:
            IngestResult with document info and chunk count.
        """
        return ingest_document(
            file_path=file_path,
            db=self.db,
            embedding_client=self.embedding_client,
            metadata=metadata,
            chunking_strategy=self.chunking_strategy,
            allowed_dirs=self.allowed_dirs,
            original_filename=original_filename,
        )

    def _ingest_worker(
        self,
        file_path: str | Path,
        metadata: dict | None,
        original_filename: str | None = None,
    ) -> IngestResult:
        """Worker function for parallel ingestion with its own DB connection.

        Creates a new database connection for thread safety.
        OpenAI client is thread-safe, so we reuse the embedding_client.
        """
        worker_db = PgVectorStore(self._connection_string)
        worker_db.connect()
        try:
            return ingest_document(
                file_path=file_path,
                db=worker_db,
                embedding_client=self.embedding_client,
                metadata=metadata,
                chunking_strategy=self.chunking_strategy,
                allowed_dirs=self.allowed_dirs,
                original_filename=original_filename,
            )
        finally:
            worker_db.disconnect()

    def ingest_batch(
        self,
        file_paths: list[str | Path],
        metadata: dict | None = None,
        max_workers: int = 4,
        original_filenames: list[str] | None = None,
    ) -> list[IngestResult]:
        """Ingest multiple documents in parallel.

        Args:
            file_paths: List of paths to PDF files.
            metadata: Optional metadata to attach to all documents.
            max_workers: Maximum number of parallel workers (default: 4).
                Set to 1 for sequential processing.
            original_filenames: Optional list of original filenames, one per file_path.

        Returns:
            List of IngestResult objects in the same order as input file_paths.
        """
        if original_filenames and len(original_filenames) != len(file_paths):
            raise ValueError(
                f"original_filenames length ({len(original_filenames)}) must match file_paths length ({len(file_paths)})"
            )

        total = len(file_paths)
        if total == 0:
            return []

        logger.info(
            "starting batch ingestion",
            total_files=total,
            max_workers=max_workers,
        )
        start = time.perf_counter()

        # Use dict to preserve order: index -> result
        results_dict: dict[int, IngestResult] = {}

        if max_workers == 1:
            # Sequential processing (original behavior)
            for i, file_path in enumerate(file_paths):
                try:
                    fname = original_filenames[i] if original_filenames else None
                    result = self.ingest(file_path, metadata, original_filename=fname)
                    results_dict[i] = result
                except Exception as e:
                    logger.error(
                        "failed to ingest document",
                        file_path=str(file_path),
                        error=str(e),
                    )
                    results_dict[i] = IngestResult(error=str(e))

                if (i + 1) % 10 == 0 or (i + 1) == total:
                    logger.info(
                        "batch progress",
                        processed=i + 1,
                        total=total,
                        percent=round((i + 1) / total * 100, 1),
                    )
        else:
            # Parallel processing with ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit all tasks and track by index
                future_to_index = {
                    executor.submit(
                        self._ingest_worker,
                        fp,
                        metadata,
                        original_filenames[i] if original_filenames else None,
                    ): i
                    for i, fp in enumerate(file_paths)
                }

                completed = 0
                for future in as_completed(future_to_index):
                    idx = future_to_index[future]
                    file_path = file_paths[idx]
                    try:
                        result = future.result()
                        results_dict[idx] = result
                    except Exception as e:
                        logger.error(
                            "failed to ingest document",
                            file_path=str(file_path),
                            error=str(e),
                        )
                        results_dict[idx] = IngestResult(error=str(e))

                    completed += 1
                    if completed % 10 == 0 or completed == total:
                        logger.info(
                            "batch progress",
                            processed=completed,
                            total=total,
                            percent=round(completed / total * 100, 1),
                        )

        # Convert dict to ordered list
        results = [results_dict[i] for i in range(total)]

        duration_ms = (time.perf_counter() - start) * 1000
        successful = sum(1 for r in results if r.document and not r.was_duplicate)
        duplicates = sum(1 for r in results if r.was_duplicate)
        failed = sum(1 for r in results if r.error)

        logger.info(
            "batch ingestion complete",
            total_files=total,
            successful=successful,
            duplicates=duplicates,
            failed=failed,
            duration_ms=round(duration_ms, 2),
        )

        return results
