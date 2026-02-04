# PDF RAG Pipeline

A document ingestion and retrieval-augmented generation (RAG) system for PDF processing.

## Requirements

- Python 3.14+
- Docker (for PostgreSQL + pgvector)
- OpenAI API key (for embeddings)
- Anthropic API key (for RAG responses)

## Setup

### 1. Start the database

```bash
docker compose up -d
```

This starts PostgreSQL 16 with pgvector on port 5432.

### 2. Install dependencies

```bash
uv sync
```

### 3. Set environment variables

```bash
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/pdf_llm_rag
export OPENAI_API_KEY=sk-...
export ANTHROPIC_API_KEY=sk-ant-...
```

## Running the Server

```bash
uv run python main.py
```

The server runs at http://localhost:8000. API docs available at http://localhost:8000/docs.

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Liveness check |
| GET | `/ready` | Readiness check (DB connectivity) |
| POST | `/api/v1/rag/ingest` | Upload and ingest a PDF file |
| POST | `/api/v1/rag/query` | Ask a question using RAG |

## Usage Examples

### Ingest a PDF

```bash
curl -X POST http://localhost:8000/api/v1/rag/ingest \
  -F "file=@document.pdf"
```

Response:
```json
{
  "document_id": "uuid-here",
  "file_path": "document.pdf",
  "chunks_count": 42,
  "was_duplicate": false
}
```

### Query the documents

```bash
curl -X POST http://localhost:8000/api/v1/rag/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What is this document about?", "top_k": 5}'
```

Response:
```json
{
  "answer": "The document discusses...",
  "sources": [
    {
      "file_path": "document.pdf",
      "page_number": 1,
      "content_preview": "First 200 characters..."
    }
  ],
  "chunks_used": 5
}
```

## Running Tests

```bash
uv run pytest tests/ -v
```

Tests require the database to be running. The test suite uses table truncation for isolation between tests.

## Project Structure

```
conakry/
├── main.py                      # Server entry point
├── docker-compose.yaml          # PostgreSQL + pgvector
├── migrations/                  # Database migrations
├── src/pdf_llm_server/
│   ├── server.py               # FastAPI REST API
│   ├── logger.py               # Structured JSON logging
│   └── rag/
│       ├── database.py         # PgVectorStore
│       ├── embeddings.py       # OpenAI embeddings
│       ├── ingestion.py        # PDF ingestion pipeline
│       ├── retriever.py        # RAG query with Claude
│       ├── pdf_parser.py       # PyMuPDF parsing
│       ├── chunking.py         # Text chunking strategies
│       └── ocr.py              # OCR detection
└── tests/
```
