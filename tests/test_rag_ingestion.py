"""Integration tests for the RAG ingestion pipeline."""

import os
from pathlib import Path

import fitz
import pytest

from psycopg2.extras import RealDictCursor

from pdf_llm_server.rag import (
    PgVectorStore,
    RAGIngestionPipeline,
    compute_file_hash,
    ingest_document,
)

MIGRATIONS_DIR = Path(__file__).parent.parent / "migrations"


@pytest.fixture(scope="module")
def db():
    """Create database connection for tests."""
    connection_string = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/pdf_llm_rag",
    )
    store = PgVectorStore(connection_string)
    store.connect()
    store.run_migrations(MIGRATIONS_DIR)
    yield store
    store.disconnect()


@pytest.fixture(autouse=True)
def truncate_tables(db):
    """Truncate tables before each test for isolation."""
    db.truncate_tables()
    yield


@pytest.fixture(scope="module")
def sample_pdf_path(tmp_path_factory) -> Path:
    """Create a sample PDF for testing."""
    tmp_dir = tmp_path_factory.mktemp("pdfs")
    pdf_path = tmp_dir / "sample.pdf"

    doc = fitz.open()

    # Page 1
    page = doc.new_page()
    page.insert_text((72, 72), "Document Title", fontsize=24)
    page.insert_text(
        (72, 120),
        "This is the first paragraph of the document. It contains "
        "information that will be chunked and stored in the database.",
        fontsize=12,
    )
    page.insert_text(
        (72, 160),
        "This is the second paragraph with additional content.",
        fontsize=12,
    )

    # Page 2
    page2 = doc.new_page()
    page2.insert_text((72, 72), "Chapter Two", fontsize=18)
    page2.insert_text(
        (72, 120),
        "Content on the second page of the document.",
        fontsize=12,
    )

    doc.save(pdf_path)
    doc.close()

    return pdf_path


@pytest.fixture(scope="module")
def another_pdf_path(tmp_path_factory) -> Path:
    """Create another PDF for batch testing."""
    tmp_dir = tmp_path_factory.mktemp("pdfs2")
    pdf_path = tmp_dir / "another.pdf"

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Another Document", fontsize=18)
    page.insert_text((72, 120), "Different content here.", fontsize=12)
    doc.save(pdf_path)
    doc.close()

    return pdf_path


class TestComputeFileHash:
    """Tests for compute_file_hash function."""

    def test_computes_hash(self, sample_pdf_path):
        """Test that a hash is computed."""
        file_hash = compute_file_hash(sample_pdf_path)
        assert isinstance(file_hash, str)
        assert len(file_hash) == 64  # SHA-256 hex length

    def test_same_file_same_hash(self, sample_pdf_path):
        """Test that same file produces same hash."""
        hash1 = compute_file_hash(sample_pdf_path)
        hash2 = compute_file_hash(sample_pdf_path)
        assert hash1 == hash2

    def test_different_files_different_hash(self, sample_pdf_path, another_pdf_path):
        """Test that different files produce different hashes."""
        hash1 = compute_file_hash(sample_pdf_path)
        hash2 = compute_file_hash(another_pdf_path)
        assert hash1 != hash2

    def test_file_not_found(self, tmp_path):
        """Test FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError):
            compute_file_hash(tmp_path / "nonexistent.pdf")


class TestIngestDocument:
    """Tests for ingest_document function."""

    def test_ingests_document(self, db, sample_pdf_path):
        """Test basic document ingestion."""
        result = ingest_document(sample_pdf_path, db)

        assert result.document is not None
        assert result.document.id is not None
        assert result.chunks_count > 0
        assert result.was_duplicate is False

    def test_detects_duplicate(self, db, sample_pdf_path):
        """Test that duplicate documents are detected."""
        # First ingestion
        result1 = ingest_document(sample_pdf_path, db)
        assert result1.was_duplicate is False

        # Second ingestion of same file
        result2 = ingest_document(sample_pdf_path, db)
        assert result2.was_duplicate is True
        assert result2.document.id == result1.document.id
        assert result2.chunks_count == 0

    def test_stores_metadata(self, db, sample_pdf_path):
        """Test that metadata is stored."""
        metadata = {"source": "test", "category": "legal"}
        result = ingest_document(sample_pdf_path, db, metadata=metadata)

        assert result.document.metadata == metadata

    def test_semantic_chunking(self, db, sample_pdf_path):
        """Test ingestion with semantic chunking."""
        result = ingest_document(
            sample_pdf_path, db, chunking_strategy="semantic"
        )
        assert result.chunks_count > 0

    def test_fixed_chunking(self, db, sample_pdf_path):
        """Test ingestion with fixed-size chunking."""
        result = ingest_document(
            sample_pdf_path, db, chunking_strategy="fixed"
        )
        assert result.chunks_count > 0


class TestRAGIngestionPipeline:
    """Tests for RAGIngestionPipeline class."""

    def test_pipeline_init(self, db):
        """Test pipeline initialization."""
        pipeline = RAGIngestionPipeline(db)
        assert pipeline.db == db
        assert pipeline.chunking_strategy == "semantic"

    def test_pipeline_custom_strategy(self, db):
        """Test pipeline with custom chunking strategy."""
        pipeline = RAGIngestionPipeline(db, chunking_strategy="fixed")
        assert pipeline.chunking_strategy == "fixed"

    def test_pipeline_ingest(self, db, sample_pdf_path):
        """Test single document ingestion via pipeline."""
        pipeline = RAGIngestionPipeline(db)
        result = pipeline.ingest(sample_pdf_path)

        assert result.document is not None
        assert result.chunks_count > 0

    def test_pipeline_ingest_with_metadata(self, db, sample_pdf_path):
        """Test ingestion with metadata via pipeline."""
        pipeline = RAGIngestionPipeline(db)
        metadata = {"batch_id": "test-batch"}
        result = pipeline.ingest(sample_pdf_path, metadata=metadata)

        assert result.document.metadata == metadata

    def test_pipeline_batch_ingest(self, db, sample_pdf_path, another_pdf_path):
        """Test batch ingestion."""
        pipeline = RAGIngestionPipeline(db)
        results = pipeline.ingest_batch([sample_pdf_path, another_pdf_path])

        assert len(results) == 2
        assert all(r.document is not None for r in results)
        assert all(r.chunks_count > 0 for r in results)

    def test_pipeline_batch_with_duplicates(self, db, sample_pdf_path):
        """Test batch ingestion handles duplicates."""
        pipeline = RAGIngestionPipeline(db)

        # First batch
        results1 = pipeline.ingest_batch([sample_pdf_path])
        assert results1[0].was_duplicate is False

        # Second batch with same file
        results2 = pipeline.ingest_batch([sample_pdf_path])
        assert results2[0].was_duplicate is True

    def test_pipeline_batch_continues_on_error(self, db, sample_pdf_path, tmp_path):
        """Test that batch continues processing after errors."""
        pipeline = RAGIngestionPipeline(db)
        nonexistent = tmp_path / "missing.pdf"

        # Mix of valid and invalid files
        results = pipeline.ingest_batch([sample_pdf_path, nonexistent])

        # Should have results for both files (success and error)
        assert len(results) == 2
        assert results[0].document is not None  # valid file succeeded
        assert results[1].error is not None  # missing file failed


class TestEndToEndIntegration:
    """End-to-end integration tests."""

    def test_full_pipeline_flow(self, db, sample_pdf_path):
        """Test complete ingestion and retrieval flow."""
        # Ingest document
        pipeline = RAGIngestionPipeline(db)
        result = pipeline.ingest(
            sample_pdf_path,
            metadata={"test": "integration"},
        )

        # Verify document stored
        assert result.document is not None
        doc_id = result.document.id

        # Verify can retrieve by hash
        file_hash = compute_file_hash(sample_pdf_path)
        retrieved = db.get_document_by_hash(file_hash)
        assert retrieved is not None
        assert retrieved.id == doc_id

        # Verify document appears in list
        all_docs = db.get_documents()
        assert any(d.id == doc_id for d in all_docs)

    def test_chunks_have_correct_fields(self, db, sample_pdf_path):
        """Test that ingested chunks have all required fields."""
        pipeline = RAGIngestionPipeline(db)
        result = pipeline.ingest(sample_pdf_path)

        # Query chunks directly to verify fields
        with db.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM chunks WHERE document_id = %s",
                (str(result.document.id),),
            )
            rows = cur.fetchall()

        assert len(rows) == result.chunks_count
        # Each row should have content, chunk_type, page_number, position
        for row in rows:
            assert row["content"]
            assert row["page_number"] is not None
            assert row["position"] is not None
