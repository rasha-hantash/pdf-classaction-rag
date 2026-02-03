import os
from pathlib import Path
from uuid import UUID

import psycopg2
from pgvector.psycopg2 import register_vector
from psycopg2.extras import Json, RealDictCursor, execute_values

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
        self.conn = psycopg2.connect(self.connection_string)

    def _ensure_vector_registered(self):
        if not self._vector_registered:
            register_vector(self.conn)
            self._vector_registered = True

    def disconnect(self):
        if self.conn:
            self.conn.close()
            self.conn = None
            self._vector_registered = False

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()

    def run_migrations(self, migrations_dir: str | Path | None = None):
        if migrations_dir is None:
            migrations_dir = Path(__file__).parent.parent.parent.parent / "migrations"
        migrations_dir = Path(migrations_dir)

        migration_files = sorted(migrations_dir.glob("*.up.sql"))
        try:
            with self.conn.cursor() as cur:
                for migration_file in migration_files:
                    sql = migration_file.read_text()
                    cur.execute(sql)
            self.conn.commit()
            self._ensure_vector_registered()
        except Exception:
            self.conn.rollback()
            raise

    def insert_document(
        self,
        file_hash: str,
        file_path: str,
        metadata: dict | None = None,
    ) -> IngestedDocument:
        metadata = metadata or {}
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
            return IngestedDocument(**row)
        except Exception:
            self.conn.rollback()
            raise

    def insert_chunks(self, chunks: list[ChunkRecord]) -> list[ChunkRecord]:
        if not chunks:
            return []

        self._ensure_vector_registered()
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
                    )
                    for chunk in chunks
                ]
                inserted_rows = execute_values(
                    cur,
                    """
                    INSERT INTO chunks (document_id, content, chunk_type, page_number, position, embedding)
                    VALUES %s
                    RETURNING id, document_id, content, chunk_type, page_number, position, embedding, created_at
                    """,
                    values,
                    fetch=True,
                )
            self.conn.commit()
            return [ChunkRecord(**row) for row in inserted_rows]
        except Exception:
            self.conn.rollback()
            raise

    def similarity_search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
    ) -> list[SearchResult]:
        self._ensure_vector_registered()
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    c.id, c.document_id, c.content, c.chunk_type, c.page_number,
                    c.position, c.embedding, c.created_at,
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

    def delete_document(self, document_id: UUID) -> bool:
        try:
            with self.conn.cursor() as cur:
                cur.execute("DELETE FROM documents WHERE id = %s", (str(document_id),))
                deleted = cur.rowcount > 0
            self.conn.commit()
            return deleted
        except Exception:
            self.conn.rollback()
            raise
