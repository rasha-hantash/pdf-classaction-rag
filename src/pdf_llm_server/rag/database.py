import os
import time
from pathlib import Path
from uuid import UUID

import psycopg2
from pgvector.psycopg2 import register_vector
from psycopg2.extras import Json, RealDictCursor, execute_values

from ..logger import logger
from .chunking import ChunkData
from .models import ChunkRecord, IngestedDocument, SearchResult


class PgVectorStore:
    def __init__(self, connection_string: str | None = None):
        self.connection_string = connection_string or os.getenv(
            "DATABASE_URL",
            "postgresql://postgres:postgres@localhost:5432/pdf_llm_rag",
        )
        self.conn = None
        self._vector_registered = False

    def connect(self):
        start = time.perf_counter()
        self.conn = psycopg2.connect(self.connection_string)
        duration_ms = (time.perf_counter() - start) * 1000
        logger.info("connected to database", duration_ms=round(duration_ms, 2))

    def _ensure_vector_registered(self):
        if not self._vector_registered:
            register_vector(self.conn)
            self._vector_registered = True

    def disconnect(self):
        if self.conn:
            self.conn.close()
            self.conn = None
            self._vector_registered = False
            logger.info("disconnected from database")

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()

    def run_migrations(self, migrations_dir: str | Path):
        """Run database migrations from the specified directory.

        Args:
            migrations_dir: Path to the directory containing migration files.
                           This is required to avoid fragile path traversal.
        """
        migrations_dir = Path(migrations_dir)

        migration_files = sorted(migrations_dir.glob("*.up.sql"))
        start = time.perf_counter()
        try:
            with self.conn.cursor() as cur:
                for migration_file in migration_files:
                    sql = migration_file.read_text()
                    cur.execute(sql)
            self.conn.commit()
            self._ensure_vector_registered()
            duration_ms = (time.perf_counter() - start) * 1000
            logger.info(
                "migrations completed",
                migrations_count=len(migration_files),
                duration_ms=round(duration_ms, 2),
            )
        except Exception as e:
            self.conn.rollback()
            logger.error("migrations failed", error=str(e))
            raise

    def insert_document(
        self,
        file_hash: str,
        file_path: str,
        metadata: dict | None = None,
    ) -> IngestedDocument:
        metadata = metadata or {}
        start = time.perf_counter()
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    INSERT INTO documents (file_hash, file_path, metadata)
                    VALUES (%s, %s, %s)
                    RETURNING id, file_hash, file_path, metadata, created_at
                    """,
                    (file_hash, file_path, Json(metadata)),
                )
                row = cur.fetchone()
            self.conn.commit()
            doc = IngestedDocument(**row)
            duration_ms = (time.perf_counter() - start) * 1000
            logger.info(
                "document inserted",
                document_id=str(doc.id),
                file_hash=file_hash,
                duration_ms=round(duration_ms, 2),
            )
            return doc
        except Exception as e:
            self.conn.rollback()
            logger.error("document insert failed", file_hash=file_hash, error=str(e))
            raise

    def insert_chunks(self, chunks: list[ChunkRecord]) -> list[ChunkRecord]:
        if not chunks:
            return []

        self._ensure_vector_registered()
        start = time.perf_counter()
        document_id = str(chunks[0].document_id)
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                values = [
                    (
                        str(chunk.document_id),
                        chunk.content,
                        chunk.chunk_type,
                        chunk.page_number,
                        chunk.position,
                        chunk.embedding,
                        Json(chunk.bbox) if chunk.bbox else None,
                    )
                    for chunk in chunks
                ]
                inserted_rows = execute_values(
                    cur,
                    """
                    INSERT INTO chunks (document_id, content, chunk_type, page_number, position, embedding, bbox)
                    VALUES %s
                    RETURNING id, document_id, content, chunk_type, page_number, position, embedding, bbox, created_at
                    """,
                    values,
                    fetch=True,
                )
            self.conn.commit()
            result = [ChunkRecord(**row) for row in inserted_rows]
            duration_ms = (time.perf_counter() - start) * 1000
            logger.info(
                "chunks inserted",
                document_id=document_id,
                chunks_count=len(result),
                duration_ms=round(duration_ms, 2),
            )
            return result
        except Exception as e:
            self.conn.rollback()
            logger.error(
                "chunks insert failed",
                document_id=document_id,
                chunks_count=len(chunks),
                error=str(e),
            )
            raise

    def similarity_search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
    ) -> list[SearchResult]:
        self._ensure_vector_registered()
        start = time.perf_counter()
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    c.id, c.document_id, c.content, c.chunk_type, c.page_number,
                    c.position, c.embedding, c.bbox, c.created_at,
                    d.id as doc_id, d.file_hash, d.file_path, d.metadata, d.created_at as doc_created_at,
                    1 - (c.embedding <=> %s::vector) as score
                FROM chunks c
                JOIN documents d ON c.document_id = d.id
                WHERE c.embedding IS NOT NULL
                ORDER BY c.embedding <=> %s::vector
                LIMIT %s
                """,
                (query_embedding, query_embedding, top_k),
            )
            rows = cur.fetchall()

        results = []
        for row in rows:
            chunk = ChunkRecord(
                id=row["id"],
                document_id=row["document_id"],
                content=row["content"],
                chunk_type=row["chunk_type"],
                page_number=row["page_number"],
                position=row["position"],
                embedding=row["embedding"],
                bbox=row.get("bbox"),
                created_at=row["created_at"],
            )
            document = IngestedDocument(
                id=row["doc_id"],
                file_hash=row["file_hash"],
                file_path=row["file_path"],
                metadata=row["metadata"],
                created_at=row["doc_created_at"],
            )
            results.append(SearchResult(chunk=chunk, score=row["score"], document=document))

        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "similarity search completed",
            top_k=top_k,
            results_count=len(results),
            duration_ms=round(duration_ms, 2),
        )
        return results

    def get_documents(self) -> list[IngestedDocument]:
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id, file_hash, file_path, metadata, created_at FROM documents ORDER BY created_at DESC"
            )
            rows = cur.fetchall()
        return [IngestedDocument(**row) for row in rows]

    def get_document_by_hash(self, file_hash: str) -> IngestedDocument | None:
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id, file_hash, file_path, metadata, created_at FROM documents WHERE file_hash = %s",
                (file_hash,),
            )
            row = cur.fetchone()
        return IngestedDocument(**row) if row else None

    def insert_document_with_chunks(
        self,
        file_hash: str,
        file_path: str,
        chunks: list[ChunkData],
        metadata: dict | None = None,
    ) -> tuple[IngestedDocument, list[ChunkRecord]]:
        """Insert a document and its chunks atomically in a single transaction.

        Args:
            file_hash: SHA-256 hash of the file.
            file_path: Path to the file.
            chunks: List of ChunkData objects from the chunking module.
            metadata: Optional metadata to attach to the document.

        Returns:
            Tuple of (IngestedDocument, list of inserted ChunkRecords).
        """
        metadata = metadata or {}
        self._ensure_vector_registered()
        start = time.perf_counter()

        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Insert document
                cur.execute(
                    """
                    INSERT INTO documents (file_hash, file_path, metadata)
                    VALUES (%s, %s, %s)
                    RETURNING id, file_hash, file_path, metadata, created_at
                    """,
                    (file_hash, file_path, Json(metadata)),
                )
                doc_row = cur.fetchone()
                doc = IngestedDocument(**doc_row)

                # Insert chunks with the new document_id
                inserted_chunks = []
                if chunks:
                    values = [
                        (
                            str(doc.id),
                            chunk.content,
                            chunk.chunk_type,
                            chunk.page_number,
                            chunk.position,
                            None,  # embedding - added by separate process
                            Json(chunk.bbox) if chunk.bbox else None,
                        )
                        for chunk in chunks
                    ]
                    inserted_rows = execute_values(
                        cur,
                        """
                        INSERT INTO chunks (document_id, content, chunk_type, page_number, position, embedding, bbox)
                        VALUES %s
                        RETURNING id, document_id, content, chunk_type, page_number, position, embedding, bbox, created_at
                        """,
                        values,
                        fetch=True,
                    )
                    inserted_chunks = [ChunkRecord(**row) for row in inserted_rows]

            # Commit both operations together
            self.conn.commit()

            duration_ms = (time.perf_counter() - start) * 1000
            logger.info(
                "document and chunks inserted",
                document_id=str(doc.id),
                file_hash=file_hash,
                chunks_count=len(inserted_chunks),
                duration_ms=round(duration_ms, 2),
            )
            return doc, inserted_chunks

        except Exception as e:
            self.conn.rollback()
            logger.error(
                "document and chunks insert failed",
                file_hash=file_hash,
                error=str(e),
            )
            raise

    def delete_document(self, document_id: UUID) -> bool:
        start = time.perf_counter()
        try:
            with self.conn.cursor() as cur:
                cur.execute("DELETE FROM documents WHERE id = %s", (str(document_id),))
                deleted = cur.rowcount > 0
            self.conn.commit()
            duration_ms = (time.perf_counter() - start) * 1000
            logger.info(
                "document deleted",
                document_id=str(document_id),
                deleted=deleted,
                duration_ms=round(duration_ms, 2),
            )
            return deleted
        except Exception as e:
            self.conn.rollback()
            logger.error("document delete failed", document_id=str(document_id), error=str(e))
            raise

    def truncate_tables(self) -> None:
        """Truncate all tables. Use only in tests for isolation between test runs."""
        try:
            with self.conn.cursor() as cur:
                cur.execute("TRUNCATE TABLE chunks, documents CASCADE")
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
