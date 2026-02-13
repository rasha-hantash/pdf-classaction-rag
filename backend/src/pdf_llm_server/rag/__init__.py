from .models import IngestedDocument, ChunkRecord, SearchResult
from .database import PgVectorStore
from .parser_models import ParsedDocument, ParsedPage, TextBlock, TableData
from .pdf_parser import parse_pdf, parse_pdf_pymupdf
from .reducto_parser import ReductoParser
from .chunking import (
    fixed_size_chunking,
    semantic_chunking_by_paragraphs,
    chunk_parsed_document,
    detect_content_type,
    ChunkData,
)
from .ocr import assess_needs_ocr, ocr_pdf_with_tesseract
from .ingestion import (
    RAGIngestionPipeline,
    ingest_document,
    compute_file_hash,
    validate_file_path,
    IngestResult,
    PathValidationError,
)
from .embeddings import (
    EmbeddingClient,
    EmbeddingResult,
    generate_embedding,
    generate_embeddings,
)
from .retriever import (
    RAGRetriever,
    RAGResponse,
    SourceReference,
)
from .reranker import (
    Reranker,
    CohereReranker,
    CrossEncoderReranker,
)

__all__ = [
    # Models
    "IngestedDocument",
    "ChunkRecord",
    "SearchResult",
    # Database
    "PgVectorStore",
    # PDF Parser
    "parse_pdf",
    "parse_pdf_pymupdf",
    "ReductoParser",
    "ParsedDocument",
    "ParsedPage",
    "TextBlock",
    "TableData",
    # Chunking
    "fixed_size_chunking",
    "semantic_chunking_by_paragraphs",
    "chunk_parsed_document",
    "detect_content_type",
    "ChunkData",
    # OCR
    "assess_needs_ocr",
    "ocr_pdf_with_tesseract",
    # Ingestion
    "RAGIngestionPipeline",
    "ingest_document",
    "compute_file_hash",
    "validate_file_path",
    "IngestResult",
    "PathValidationError",
    # Embeddings
    "EmbeddingClient",
    "EmbeddingResult",
    "generate_embedding",
    "generate_embeddings",
    # Retriever
    "RAGRetriever",
    "RAGResponse",
    "SourceReference",
    # Re-ranking
    "Reranker",
    "CohereReranker",
    "CrossEncoderReranker",
]
