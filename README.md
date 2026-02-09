# PDF RAG Pipeline

A retrieval-augmented generation system for querying legal documents (e.g. class-action settlement PDFs). Upload PDFs, ingest them into a vector store, and ask questions with source-backed answers.

## Architecture

```
┌──────────────┐       ┌──────────────────┐       ┌──────────────────────┐
│   Frontend   │──────▶│  Backend (API)   │──────▶│  PostgreSQL+pgvector │
│  React/TS    │◀──────│  FastAPI/Python  │◀──────│                      │
└──────────────┘       └──────┬───────────┘       └──────────────────────┘
                              │
                   ┌──────────┴──────────┐
                   │                     │
             ┌─────▼─────┐        ┌──────▼──────┐
             │  OpenAI   │        │   Claude    │
             │ Embeddings│        │ Generation  │
             └───────────┘        └─────────────┘
```

**Pipeline:**

1. **Ingestion** — Parse PDFs (PyMuPDF or Reducto), chunk text semantically, generate embeddings (OpenAI `text-embedding-3-small`), store in pgvector.
2. **Retrieval** — Embed the user's query, run cosine similarity search against stored chunks, return top-k results.
3. **Generation** — Build context from retrieved chunks (with source file + page number), send to Claude with a grounded system prompt, return answer + citations.

## Requirements

- Python 3.14+
- Node.js 18+
- Docker (for PostgreSQL + pgvector)
- OpenAI API key (for embeddings)
- Anthropic API key (for RAG responses)
- Reducto API key (optional, for cloud PDF parsing)

## Setup

### 1. Start the database

```bash
docker compose up -d
```

This starts PostgreSQL 16 with pgvector on port 5432.

### 2. Install backend dependencies

```bash
cd backend && uv sync
```

### 3. Install frontend dependencies

```bash
cd frontend && npm install
```

### 4. Set environment variables

```bash
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/pdf_llm_rag
export OPENAI_API_KEY=sk-...
export ANTHROPIC_API_KEY=sk-ant-...
# Optional: provide REDUCTO_API_KEY if using the reducto parser
export REDUCTO_API_KEY=...
```

## Running

### Backend

```bash
cd backend && uv run python main.py
```

Use `--pdf-parser` to select the parsing backend:

```bash
cd backend && uv run python main.py --pdf-parser reducto
```

The API runs at http://localhost:8000. Docs at http://localhost:8000/docs.

### Frontend

```bash
cd frontend && npm run dev
```

The UI runs at http://localhost:3000 and proxies API requests to the backend.

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Liveness check |
| GET | `/ready` | Readiness check (DB connectivity) |
| POST | `/api/v1/rag/ingest/batch` | Upload and ingest PDF files |
| POST | `/api/v1/rag/query` | Ask a question using RAG |
| GET | `/api/v1/rag/documents` | List ingested documents |

## Usage Examples

### Ingest PDFs

```bash
curl -X POST http://localhost:8000/api/v1/rag/ingest/batch \
  -F "files=@document1.pdf" \
  -F "files=@document2.pdf"
```

### Query the documents

```bash
curl -X POST http://localhost:8000/api/v1/rag/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What is this document about?", "top_k": 5}'
```

## Running Tests

```bash
cd backend && uv run pytest tests/ -v
```

Tests require the database to be running. The test suite uses table truncation for isolation between tests.

## Project Structure

```
pdf-classaction-rag/
├── backend/
│   ├── main.py                          # Server entry point
│   ├── migrations/                      # Database migrations (golang-migrate)
│   ├── src/pdf_llm_server/
│   │   ├── server.py                    # FastAPI REST API
│   │   ├── logger.py                    # Structured JSON logging
│   │   └── rag/
│   │       ├── database.py              # PgVectorStore
│   │       ├── embeddings.py            # OpenAI embeddings
│   │       ├── ingestion.py             # PDF ingestion pipeline
│   │       ├── retriever.py             # RAG query with Claude
│   │       ├── pdf_parser.py            # PyMuPDF parsing + parser dispatch
│   │       ├── reducto_parser.py        # Reducto cloud API parser
│   │       ├── parser_models.py         # Shared parser data models
│   │       ├── chunking.py              # Text chunking strategies
│   │       └── ocr.py                   # OCR detection
│   └── tests/
├── frontend/
│   └── src/
│       ├── routes/                      # TanStack Router file-based routes
│       ├── components/                  # React components
│       ├── hooks/                       # Custom hooks (useIngest, useRagQuery)
│       ├── lib/                         # Types and API client
│       └── styles/                      # TailwindCSS globals
├── docker-compose.yaml                  # PostgreSQL + pgvector
└── Taskfile.yml                         # Task runner config
```

## Features

- [x] PDF parsing with PyMuPDF (text blocks, tables, font/heading classification)
- [x] Reducto cloud API parser (configurable via `PDF_PARSER` env var)
- [x] OCR support via Tesseract (auto-fallback for pages with corrupted/garbage text)
- [x] Semantic chunking (paragraph-aware) and fixed-size chunking
- [x] OpenAI embeddings (`text-embedding-3-small`, 1536 dimensions)
- [x] Vector similarity search with pgvector (cosine distance)
- [x] Relevance score threshold filtering
- [x] RAG generation with Claude (grounded answers with source citations)
- [x] Batch PDF upload with parallel ingestion (ThreadPoolExecutor)
- [x] File deduplication via SHA-256 hashing
- [x] File size validation and path traversal protection
- [x] React frontend with chat UI, evidence panel, and PDF page viewer
- [x] Structured JSON logging (slog-compatible)
- [x] Database migrations (golang-migrate)

## TODO

- [ ] **Rate limiting** — Add API rate limiting to protect against abuse
- [ ] **Telemetry** — Integrate OpenTelemetry with Grafana for observability (traces, metrics, logs)
- [ ] **Hybrid search** — Add BM25/keyword search alongside vector search for better exact-match retrieval (case numbers, dates)
- [ ] **Reranking** — Use a cross-encoder to rerank retrieval results before sending to the LLM
- [ ] **Chunk size tuning** — Experiment with chunk sizes based on retrieval quality metrics
