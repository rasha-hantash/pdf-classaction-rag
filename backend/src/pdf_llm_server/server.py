"""FastAPI REST API for the RAG pipeline."""

import os
import shutil
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import UUID

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel, Field

from .logger import logger
from .rag import (
    EmbeddingClient,
    PathValidationError,
    PgVectorStore,
    RAGIngestionPipeline,
    RAGRetriever,
    ReductoParser,
)
from .rag.reranker import CohereReranker, CrossEncoderReranker, Reranker

# Maximum file size for uploads (50MB)
MAX_UPLOAD_SIZE = 50 * 1024 * 1024

# Maximum number of files in a single batch upload
MAX_BATCH_SIZE = 100

# Directory for persistent PDF storage
PDF_STORAGE_DIR = Path(os.getenv("PDF_STORAGE_DIR", "./data/pdfs"))


# --- Request/Response Models ---


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=10000)
    top_k: int = Field(default=5, ge=1, le=20)


class SourceResponse(BaseModel):
    chunk_id: UUID | None = None
    document_id: UUID | None = None
    file_path: str
    page_number: int | None
    content: str
    content_preview: str
    bbox: list[float] | None = None


class QueryResponse(BaseModel):
    answer: str
    sources: list[SourceResponse]
    chunks_used: int


class BatchIngestItemResponse(BaseModel):
    file_name: str
    document_id: UUID | None = None
    chunks_count: int = 0
    was_duplicate: bool = False
    error: str | None = None


class BatchIngestResponse(BaseModel):
    results: list[BatchIngestItemResponse]
    successful: int = 0
    duplicates: int = 0
    failed: int = 0


class HealthResponse(BaseModel):
    status: str
    checks: dict[str, bool] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    code: str
    message: str


# --- App State ---

db: PgVectorStore | None = None
_embedding_client: EmbeddingClient | None = None
_reducto_parser: ReductoParser | None = None
_reranker: Reranker | None = None
_retriever: RAGRetriever | None = None


def get_embedding_client() -> EmbeddingClient:
    """Lazy initialization of embedding client."""
    global _embedding_client
    if _embedding_client is None:
        _embedding_client = EmbeddingClient()
    return _embedding_client


def get_reducto_parser() -> ReductoParser | None:
    """Lazy initialization of Reducto parser. Returns None if not configured."""
    global _reducto_parser
    if _reducto_parser is None and os.getenv("PDF_PARSER", "pymupdf").lower() == "reducto":
        _reducto_parser = ReductoParser()
    return _reducto_parser


def get_reranker() -> Reranker | None:
    """Lazy initialization of reranker. Returns None if not configured.

    Reads the RERANKER env var:
        - "cohere": uses Cohere rerank API (requires COHERE_API_KEY)
        - "cross-encoder": uses local cross-encoder model
        - unset/empty: no reranking
    """
    global _reranker
    if _reranker is None:
        reranker_type = os.getenv("RERANKER", "").lower()
        if reranker_type == "cohere":
            _reranker = CohereReranker()
        elif reranker_type == "cross-encoder":
            _reranker = CrossEncoderReranker()
    return _reranker


def get_retriever() -> RAGRetriever:
    """Lazy initialization of retriever."""
    global _retriever
    if _retriever is None:
        _retriever = RAGRetriever(
            db=db,
            embedding_client=get_embedding_client(),
            reranker=get_reranker(),
        )
    return _retriever


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    global db

    logger.info("starting server")

    PDF_STORAGE_DIR.mkdir(parents=True, exist_ok=True)

    db = PgVectorStore()
    db.connect()

    yield

    if db:
        db.disconnect()
    logger.info("server shutdown")


app = FastAPI(
    title="PDF RAG API",
    description="Document ingestion and retrieval-augmented generation API",
    version="0.1.0",
    lifespan=lifespan,
)


# --- Exception Handlers ---


@app.exception_handler(PathValidationError)
async def path_validation_handler(request, exc: PathValidationError):
    return JSONResponse(
        status_code=403,
        content=ErrorResponse(code="ACCESS_DENIED", message=str(exc)).model_dump(),
    )


@app.exception_handler(FileNotFoundError)
async def file_not_found_handler(request, exc: FileNotFoundError):
    return JSONResponse(
        status_code=404,
        content=ErrorResponse(code="FILE_NOT_FOUND", message=str(exc)).model_dump(),
    )


# --- Health Endpoints ---


@app.get("/health", response_model=HealthResponse)
def health():
    """Liveness check."""
    return HealthResponse(status="healthy")


@app.get("/ready", response_model=HealthResponse)
def ready():
    """Readiness check - verifies database connectivity."""
    checks = {"database": False}

    if db and db.conn:
        try:
            with db.conn.cursor() as cur:
                cur.execute("SELECT 1")
            checks["database"] = True
        except Exception as e:
            logger.debug("health check db query failed", error=str(e))

    status = "healthy" if all(checks.values()) else "unhealthy"
    return HealthResponse(status=status, checks=checks)


# --- RAG Endpoints ---


@app.post("/api/v1/rag/ingest/batch", response_model=BatchIngestResponse)
def ingest_batch(files: list[UploadFile] = File(...)):
    """Ingest multiple PDF files via batch upload."""
    if len(files) > MAX_BATCH_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"Too many files. Maximum batch size is {MAX_BATCH_SIZE}",
        )

    results: list[BatchIngestItemResponse] = []
    valid_tmp_paths: list[Path] = []
    valid_filenames: list[str] = []
    valid_file_sizes: list[int] = []
    all_tmp_paths: list[Path] = []

    # Phase 1: Validate each file and save to temp
    for file in files:
        file_name = file.filename or "unknown.pdf"

        if not file_name.lower().endswith(".pdf"):
            results.append(
                BatchIngestItemResponse(
                    file_name=file_name, error="Only PDF files are supported"
                )
            )
            continue

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp_path = Path(tmp.name)
            shutil.copyfileobj(file.file, tmp)
        all_tmp_paths.append(tmp_path)

        actual_size = tmp_path.stat().st_size
        if actual_size > MAX_UPLOAD_SIZE:
            results.append(
                BatchIngestItemResponse(
                    file_name=file_name,
                    error=f"File too large. Maximum size is {MAX_UPLOAD_SIZE // (1024 * 1024)}MB",
                )
            )
            continue

        with open(tmp_path, "rb") as f:
            header = f.read(5)
        if header != b"%PDF-":
            results.append(
                BatchIngestItemResponse(
                    file_name=file_name,
                    error="Invalid PDF file. File does not have valid PDF header.",
                )
            )
            continue

        valid_tmp_paths.append(tmp_path)
        valid_filenames.append(file_name)
        valid_file_sizes.append(actual_size)

    # Phase 2: Batch ingest valid files
    try:
        if valid_tmp_paths:
            pipeline = RAGIngestionPipeline(
                db=db,
                embedding_client=get_embedding_client(),
                reducto_parser=get_reducto_parser(),
            )
            ingest_results = pipeline.ingest_batch(
                file_paths=valid_tmp_paths,
                original_filenames=valid_filenames,
                file_sizes=valid_file_sizes,
            )

            for i, result in enumerate(ingest_results):
                file_name = valid_filenames[i]
                if result.error:
                    results.append(
                        BatchIngestItemResponse(
                            file_name=file_name, error=result.error
                        )
                    )
                else:
                    if result.document and not result.was_duplicate:
                        pdf_dest = PDF_STORAGE_DIR / f"{result.document.id}.pdf"
                        shutil.copy2(valid_tmp_paths[i], pdf_dest)

                    results.append(
                        BatchIngestItemResponse(
                            file_name=file_name,
                            document_id=result.document.id
                            if result.document
                            else None,
                            chunks_count=result.chunks_count,
                            was_duplicate=result.was_duplicate,
                        )
                    )
    finally:
        for tmp_path in all_tmp_paths:
            tmp_path.unlink(missing_ok=True)

    successful = sum(
        1
        for r in results
        if r.document_id and not r.was_duplicate and not r.error
    )
    duplicates = sum(1 for r in results if r.was_duplicate)
    failed = sum(1 for r in results if r.error)

    return BatchIngestResponse(
        results=results,
        successful=successful,
        duplicates=duplicates,
        failed=failed,
    )


@app.post("/api/v1/rag/query", response_model=QueryResponse)
def query(request: QueryRequest):
    """Answer a question using RAG."""
    response = get_retriever().query(request.question, top_k=request.top_k)
    return QueryResponse(
        answer=response.answer,
        sources=[
            SourceResponse(
                chunk_id=s.chunk_id,
                document_id=s.document_id,
                file_path=s.file_path,
                page_number=s.page_number,
                content=s.content,
                content_preview=s.content_preview,
                bbox=s.bbox,
            )
            for s in response.sources
        ],
        chunks_used=response.chunks_used,
    )


# --- Document Endpoints ---


class DocumentResponse(BaseModel):
    id: UUID
    file_path: str
    chunks_count: int
    status: str
    file_size: int | None = None
    created_at: str


@app.get("/api/v1/documents", response_model=list[DocumentResponse])
def list_documents():
    """List all ingested documents with chunk counts."""
    with db.conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """SELECT d.id, d.file_path, d.status, d.file_size, d.created_at,
                      COUNT(c.id) AS chunks_count
               FROM documents d
               LEFT JOIN chunks c ON c.document_id = d.id
               GROUP BY d.id
               ORDER BY d.created_at DESC"""
        )
        rows = cur.fetchall()

    return [
        DocumentResponse(
            id=row["id"],
            file_path=row["file_path"],
            chunks_count=row["chunks_count"],
            status=row["status"],
            file_size=row["file_size"],
            created_at=row["created_at"].isoformat(),
        )
        for row in rows
    ]


@app.get("/api/v1/documents/{document_id}/file")
def get_document_file(document_id: UUID):
    """Serve the original PDF file for a document."""
    pdf_path = PDF_STORAGE_DIR / f"{document_id}.pdf"
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF file not found")
    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=f"{document_id}.pdf",
    )
