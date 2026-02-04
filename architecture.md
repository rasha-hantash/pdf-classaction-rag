# RAG Pipeline Architecture

## Overview

A document ingestion and retrieval-augmented generation (RAG) system for PDF processing, built with PostgreSQL + pgvector for vector storage and Claude for response generation.

## Implementation Status

| Component | Status | Files |
|-----------|--------|-------|
| Infrastructure | ✅ Complete | docker-compose.yaml, migrations/ |
| Database Layer | ✅ Complete | rag/database.py, rag/models.py |
| PDF Parsing | ✅ Complete | rag/pdf_parser.py |
| Chunking | ✅ Complete | rag/chunking.py |
| OCR Detection | ✅ Complete | rag/ocr.py |
| Ingestion Pipeline | ✅ Complete | rag/ingestion.py |
| Embeddings | ✅ Complete | rag/embeddings.py |
| Retriever | ❌ Not Started | rag/retriever.py |
| REST API | ❌ Not Started | server.py |

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              REST API (FastAPI)                          │
│  POST /rag/ingest    POST /rag/query    GET /rag/documents              │
└────────────┬─────────────────┬──────────────────┬───────────────────────┘
             │                 │                  │
             ▼                 ▼                  ▼
┌─────────────────────┐  ┌─────────────────────────────────────────────────┐
│  Ingestion Pipeline │  │              RAG Retriever                       │
│  ─────────────────  │  │  ───────────────────────────────────────────    │
│  1. Compute hash    │  │  1. Generate query embedding (OpenAI)           │
│  2. Check duplicate │  │  2. Similarity search (pgvector)                │
│  3. Parse PDF       │  │  3. Build context from chunks                   │
│  4. Chunk content   │  │  4. Generate response (Claude)                  │
│  5. Gen embeddings  │  │  5. Return answer + sources                     │
│  6. Store in DB     │  └─────────────────────────────────────────────────┘
└─────────┬───────────┘                    │
          │                                │
          ▼                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        PostgreSQL + pgvector                             │
│  ┌─────────────────────┐    ┌────────────────────────────────────────┐  │
│  │     documents       │    │              chunks                     │  │
│  │  ───────────────    │    │  ────────────────────────────────────  │  │
│  │  id (UUID PK)       │◄───│  document_id (FK)                      │  │
│  │  file_hash (unique) │    │  content (TEXT)                        │  │
│  │  file_path          │    │  chunk_type                            │  │
│  │  metadata (JSONB)   │    │  page_number, position                 │  │
│  │  created_at         │    │  embedding vector(1536)                │  │
│  └─────────────────────┘    │  bbox (JSONB)                          │  │
│                              └────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

## File Structure

```
lagos/
├── docker-compose.yaml           # PostgreSQL 16 + pgvector
├── migrations/
│   ├── 000001_create_documents_table.up.sql
│   ├── 000002_create_chunks_table.up.sql
│   └── 000003_add_bbox_to_chunks.up.sql
├── src/pdf_llm_server/
│   ├── logger.py                 # Structured JSON logging
│   ├── server.py                 # [TODO] FastAPI REST API
│   └── rag/
│       ├── __init__.py           # Module exports
│       ├── models.py             # Pydantic models (IngestedDocument, ChunkRecord, SearchResult)
│       ├── database.py           # PgVectorStore (connection, CRUD, similarity_search)
│       ├── pdf_parser.py         # PyMuPDF parsing with font analysis, table extraction
│       ├── chunking.py           # Fixed-size and semantic chunking strategies
│       ├── ocr.py                # OCR detection and Tesseract integration
│       ├── ingestion.py          # RAGIngestionPipeline (hash, parse, chunk, store)
│       ├── embeddings.py         # EmbeddingClient (OpenAI text-embedding-3-small)
│       └── retriever.py          # [TODO] RAGRetriever (search + Claude generation)
└── tests/
    ├── test_rag_database.py
    ├── test_rag_ingestion.py
    ├── test_rag_embeddings.py
    └── test_rag_api.py           # [TODO]
```

## Remaining Work

### 1. Integrate Embeddings into Ingestion
Currently, ingestion stores chunks without embeddings. Need to:
- Call `EmbeddingClient.generate_embeddings()` after chunking
- Update `insert_document_with_chunks()` call to include embeddings

### 2. Implement Retriever (`rag/retriever.py`)
```python
class RAGRetriever:
    def retrieve(query: str, top_k: int = 5) -> list[SearchResult]
    def query(question: str, top_k: int = 5) -> RAGResponse
```
- Generate query embedding
- Call `db.similarity_search()`
- Build context from retrieved chunks
- Call Claude for response generation

### 3. Implement REST API (`server.py`)
FastAPI endpoints:
- `POST /rag/ingest` - Ingest PDF files
- `POST /rag/query` - RAG query
- `GET /rag/documents` - List documents
- `DELETE /rag/documents/{id}` - Delete document

### 4. Add Vector Index (after data load)
```sql
CREATE INDEX ON chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```

## Environment Variables

```bash
# Database
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/pdf_llm_rag

# Embeddings (OpenAI)
OPENAI_API_KEY=sk-...

# RAG Generation (Anthropic)
ANTHROPIC_API_KEY=sk-ant-...
```

## Design Decisions

- **Single-tenant**: No tenant_id isolation (simplifies schema)
- **OpenAI for embeddings**: text-embedding-3-small (1536 dimensions)
- **Claude for generation**: Anthropic API for RAG responses
- **Semantic chunking**: Paragraph-aware with fallback to fixed-size
- **Deduplication**: SHA-256 file hash prevents re-ingestion
