"""FastAPI REST API for the RAG pipeline."""

import asyncio
import shutil
import tempfile
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from uuid import UUID

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .logger import logger
from .rag import (
    EmbeddingClient,
    PathValidationError,
    PgVectorStore,
    RAGRetriever,
    ingest_document,
)

# Maximum file size for uploads (50MB)
MAX_UPLOAD_SIZE = 50 * 1024 * 1024


# --- Request/Response Models ---


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=10000)
    top_k: int = Field(default=5, ge=1, le=20)


class SourceResponse(BaseModel):
    file_path: str
    page_number: int | None
    content_preview: str


class QueryResponse(BaseModel):
    answer: str
    sources: list[SourceResponse]
    chunks_used: int


class IngestResponse(BaseModel):
    document_id: UUID | None = None
    file_path: str
    chunks_count: int = 0
    was_duplicate: bool = False


class DocumentResponse(BaseModel):
    id: UUID
    file_hash: str
    file_path: str
    metadata: dict
    created_at: datetime


class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse]
    count: int


class DeleteResponse(BaseModel):
    deleted: bool
    document_id: UUID


class HealthResponse(BaseModel):
    status: str
    checks: dict[str, bool] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    code: str
    message: str


# --- App State ---

db: PgVectorStore | None = None
_embedding_client: EmbeddingClient | None = None
_retriever: RAGRetriever | None = None


def get_embedding_client() -> EmbeddingClient:
    """Lazy initialization of embedding client."""
    global _embedding_client
    if _embedding_client is None:
        _embedding_client = EmbeddingClient()
    return _embedding_client


def get_retriever() -> RAGRetriever:
    """Lazy initialization of retriever."""
    global _retriever
    if _retriever is None:
        _retriever = RAGRetriever(db=db, embedding_client=get_embedding_client())
    return _retriever


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    global db

    logger.info("starting server")

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
async def health():
    """Liveness check."""
    return HealthResponse(status="healthy")


@app.get("/ready", response_model=HealthResponse)
async def ready():
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


def _validate_pdf_content(file_path: Path) -> bool:
    """Validate file is a PDF by checking magic bytes."""
    with open(file_path, "rb") as f:
        header = f.read(5)
    return header == b"%PDF-"


def _save_upload_to_temp(file_obj, tmp_path: Path) -> None:
    """Save uploaded file to temp path."""
    with open(tmp_path, "wb") as f:
        shutil.copyfileobj(file_obj, f)


def _run_ingest(tmp_path: Path, db_instance, embedding_client):
    """Run the synchronous ingest operation."""
    return ingest_document(
        file_path=tmp_path,
        db=db_instance,
        embedding_client=embedding_client,
    )


@app.post("/api/v1/rag/ingest", response_model=IngestResponse)
async def ingest_file(file: UploadFile = File(...)):
    """Ingest a PDF file via upload."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    # Check file size
    if file.size and file.size > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {MAX_UPLOAD_SIZE // (1024 * 1024)}MB",
        )

    # Save to temp file (run in thread pool to avoid blocking)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp_path = Path(tmp.name)

    try:
        await asyncio.to_thread(_save_upload_to_temp, file.file, tmp_path)

        # Validate PDF magic bytes
        is_valid_pdf = await asyncio.to_thread(_validate_pdf_content, tmp_path)
        if not is_valid_pdf:
            raise HTTPException(
                status_code=400,
                detail="Invalid PDF file. File does not have valid PDF header.",
            )

        # Run ingestion in thread pool to avoid blocking event loop
        result = await asyncio.to_thread(
            _run_ingest, tmp_path, db, get_embedding_client()
        )
        if result.error:
            raise HTTPException(status_code=500, detail=result.error)
        return IngestResponse(
            document_id=result.document.id if result.document else None,
            file_path=file.filename,
            chunks_count=result.chunks_count,
            was_duplicate=result.was_duplicate,
        )
    finally:
        tmp_path.unlink(missing_ok=True)


@app.post("/api/v1/rag/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """Answer a question using RAG."""
    # Run in thread pool to avoid blocking event loop (DB + LLM calls)
    response = await asyncio.to_thread(
        get_retriever().query, request.question, top_k=request.top_k
    )
    return QueryResponse(
        answer=response.answer,
        sources=[
            SourceResponse(
                file_path=s.file_path,
                page_number=s.page_number,
                content_preview=s.content_preview,
            )
            for s in response.sources
        ],
        chunks_used=response.chunks_used,
    )


@app.get("/api/v1/rag/documents", response_model=DocumentListResponse)
async def list_documents():
    """List all ingested documents."""
    # Run in thread pool to avoid blocking event loop
    docs = await asyncio.to_thread(db.get_documents)
    return DocumentListResponse(
        documents=[
            DocumentResponse(
                id=d.id,
                file_hash=d.file_hash,
                file_path=d.file_path,
                metadata=d.metadata,
                created_at=d.created_at,
            )
            for d in docs
        ],
        count=len(docs),
    )


@app.delete("/api/v1/rag/documents/{document_id}", response_model=DeleteResponse)
async def delete_document(document_id: UUID):
    """Delete a document and its chunks."""
    # Run in thread pool to avoid blocking event loop
    deleted = await asyncio.to_thread(db.delete_document, document_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")
    return DeleteResponse(deleted=True, document_id=document_id)
